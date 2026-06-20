"""
核心评估编排服务。

编排网格查询 + 政策匹配 + LLM 调用 → 结构化评估结果 → 存储评估记录。
使用 httpx.AsyncClient 调用 DeepSeek API（OpenAI 兼容格式）。
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import time
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any

import httpx

from src.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    LLM_SEMAPHORE_LIMIT,
)
from src.database import get_connection
from src.prompts.system_prompt import build_eval_prompt, get_system_prompt
from src.services import grid_service, policy_service

logger = logging.getLogger(__name__)

# 全局 LLM 并发控制（单实例，串行调用）
_llm_semaphore = asyncio.Semaphore(LLM_SEMAPHORE_LIMIT)

# LLM 超时
LLM_TIMEOUT = 30  # 秒

# ============================================================
# v2.1: F1 去重机制（模块级）
# ============================================================

_DEDUP_TABLE: OrderedDict[str, float] = OrderedDict()
_DEDUP_MAX_SIZE = 200
_DEDUP_WINDOW_SEC = 5


def _make_dedup_key(user_id: str, bbox: str | None, now: float) -> str:
    """构造去重 key = hash(user_id + bbox + 5s 窗口)。"""
    if bbox:
        parts = bbox.split(",")
        bbox_normalized = ",".join(f"{float(p):.4f}" for p in parts[:4])
    else:
        bbox_normalized = "no_bbox"
    time_bucket = int(now / _DEDUP_WINDOW_SEC)
    raw = f"{user_id}|{bbox_normalized}|{time_bucket}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _cleanup_dedup_table(now: float) -> None:
    """清理过期去重条目。"""
    cutoff = now - _DEDUP_WINDOW_SEC
    expired = [k for k, v in _DEDUP_TABLE.items() if v < cutoff]
    for k in expired:
        del _DEDUP_TABLE[k]


def _record_dedup(key: str, now: float) -> None:
    """记录去重 key，超容 FIFO 淘汰。"""
    _cleanup_dedup_table(now)
    if len(_DEDUP_TABLE) >= _DEDUP_MAX_SIZE:
        _DEDUP_TABLE.popitem(last=False)
    _DEDUP_TABLE[key] = now


def _is_duplicate(key: str, now: float) -> bool:
    """检查是否为 5 秒内重复。"""
    _cleanup_dedup_table(now)
    return key in _DEDUP_TABLE


# ============================================================
# 降级 AgentReply
# ============================================================

def _fallback_reply(reason: str) -> dict[str, Any]:
    """生成 LLM 不可用时的降级结果。

    Args:
        reason: 降级原因描述。

    Returns:
        dict: AgentReply 字典。
    """
    return {
        "summary": f"LLM 服务当前不可用（{reason}），以下为基线建议。",
        "items": [],
        "policy_citations": [],
        "risks": ["LLM 服务不可用，建议稍后重试"],
        "candidate_grids": [],
    }


# ============================================================
# LLM 响应解析
# ============================================================

def parse_llm_response(raw: str) -> dict[str, Any]:
    """将 LLM 文本回复解析为结构化字典。

    容错设计：解析失败时返回降级结果，不抛异常。

    Args:
        raw: LLM 返回的原始 JSON 字符串。

    Returns:
        dict: AgentReply 字典。
    """
    try:
        # 尝试直接解析
        data = json.loads(raw)
    except json.JSONDecodeError:
        # 尝试提取 ```json ... ``` 代码块
        try:
            if "```json" in raw:
                block = raw.split("```json", 1)[1].split("```", 1)[0]
                data = json.loads(block)
            elif "```" in raw:
                block = raw.split("```", 1)[1].split("```", 1)[0]
                data = json.loads(block)
            else:
                raise ValueError("无法定位 JSON 代码块")
        except (json.JSONDecodeError, ValueError, IndexError):
            logger.warning("LLM 响应解析失败，返回降级结果。原始响应前200字: %s", raw[:200])
            return _fallback_reply("响应解析失败")

    # 确保必填字段存在
    result: dict[str, Any] = {
        "summary": data.get("summary", ""),
        "items": data.get("items", []),
        "policy_citations": data.get("policy_citations", []),
        "risks": data.get("risks", []),
        "candidate_grids": data.get("candidate_grids", []),
    }
    return result


# ============================================================
# 评估记录写入
# ============================================================

def record_evaluation(eval_data: dict[str, Any]) -> int:
    """写入 evaluations 表（自进化经验池）。

    写入失败仅日志告警，不影响主流程。

    Args:
        eval_data: 评估记录，含 role / user_message / bbox / grid_ids /
                   grid_count / total_area_mu / llm_response /
                   structured_result / user_feedback。

    Returns:
        int: 新插入行的 id。失败返回 0。
    """
    try:
        conn = get_connection()
        try:
            cursor = conn.execute(
                """
                INSERT INTO evaluations
                    (role, user_message, bbox, grid_ids, grid_count,
                     total_area_mu, llm_response, structured_result,
                     user_feedback)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    eval_data.get("role", ""),
                    eval_data.get("user_message", ""),
                    eval_data.get("bbox"),
                    json.dumps(eval_data.get("grid_ids", []), ensure_ascii=False),
                    eval_data.get("grid_count", 0),
                    eval_data.get("total_area_mu", 0.0),
                    eval_data.get("llm_response", ""),
                    json.dumps(eval_data.get("structured_result", {}), ensure_ascii=False),
                    eval_data.get("user_feedback"),
                )
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()
    except Exception:
        logger.exception("写入 evaluations 表失败（不影响主流程）")
        return 0


# ============================================================
# 核心评估逻辑
# ============================================================

async def evaluate_grids(
    grid_ids: list[str],
    user_message: str,
    role: str,
    context: list[dict[str, str]] | None = None,
    bbox: str | None = None,
    user_id: str = "anonymous",
) -> dict[str, Any]:
    """核心评估入口。

    编排步骤：
      1. 调用 grid_service.get_grid_stats 获取聚合数据
      2. 推断主导产业类型
      3. 调用 policy_service 获取政策上下文
      4. 构造 prompt
      5. 调用 LLM API
      6. 解析 LLM 返回为结构化结果
      7. 存储评估记录到 evaluations 表

    Args:
        grid_ids: 待评估的渔网 grid_id 列表。
        user_message: 用户输入文本。
        role: 用户角色。
        context: 可选的对话历史列表。

    Returns:
        dict: AgentReply 字典。
    """
    # Step 1: 网格完整指标体系
    stats = grid_service.get_grid_stats(grid_ids)
    indicators = grid_service.get_grid_indicators(grid_ids)
    scenario_scores = grid_service.get_scenario_scores(grid_ids)

    grid_data = [{
        **stats,
        "indicators": indicators,
        "scenario_scores": scenario_scores,
    }]

    # Step 2: 推断主导产业类型
    # TODO[BatchD]: 基于 land_type_distribution 和规则推断主导产业
    #  当前临时取分布最高的用地类型对应常见产业方向
    dominant_land = ""
    if stats.get("land_type_distribution"):
        dominant_land = max(
            stats["land_type_distribution"],
            key=stats["land_type_distribution"].get,  # type: ignore[arg-type]
        )

    # 简单映射：用地类型 → 推荐产业方向
    _LAND_TO_INDUSTRY = {
        "工业用地": "精密制造",
        "物流仓储用地": "快递物流装备",
        "商业服务业设施用地": "数字经济",
        "科研用地": "数字经济",
        "水田": "绿色经济",
        "旱地": "绿色经济",
        "乔木林地": "文旅康养",
    }
    inferred_industry = _LAND_TO_INDUSTRY.get(dominant_land, "智能制造")

    # Step 3: 政策上下文
    weights = policy_service.calculate_weights(dominant_land, "", inferred_industry)
    refs = policy_service.get_policy_refs(inferred_industry, dominant_land, "")
    pref = policy_service.get_tonglu_industry_preference(inferred_industry)

    policy_context: dict[str, Any] = {
        "weights": weights,
        "policy_refs": [POLICY_LIBRARY_FULL.get(r, r) for r in refs],
        "industry_preference": pref,
        "user_message": user_message,
    }

    # Step 4: 构建 prompt
    system_prompt = get_system_prompt(role)
    user_prompt = build_eval_prompt(grid_data, policy_context, role)

    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
    ]
    if context:
        messages.extend(context)
    messages.append({"role": "user", "content": user_prompt})

    # ── Step 4.5: EvoMap + Gene 检索增强（可降级）──
    from src.services.gene_service import get_latest_gene
    from src.services.oauth_client import oauth_client
    from src.prompts.system_prompt import build_gene_injection

    gene = get_latest_gene()  # 返回 DEFAULT_GENE 若无历史

    recipes: list[dict] = []
    community_genes: list[dict] = []
    try:
        if oauth_client.is_available:
            async with asyncio.timeout(5):
                recipes = await oauth_client.search_recipes(user_message, limit=5)
                community_genes = await oauth_client.get_top_genes(limit=3)
    except (asyncio.TimeoutError, Exception):
        logger.info("EvoMap 检索不可用，跳过社区智能增强")

    injection = build_gene_injection(gene, recipes, community_genes)
    if injection:
        user_prompt = user_prompt + "\n\n" + injection

    # Step 5: LLM API 调用
    if not DEEPSEEK_API_KEY:
        logger.warning("DEEPSEEK_API_KEY 未设置，返回降级结果")
        return _fallback_reply("API key 未配置")

    async with _llm_semaphore:
        try:
            async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
                response = await client.post(
                    f"{DEEPSEEK_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": DEEPSEEK_MODEL,
                        "messages": messages,
                        "temperature": 0.3,
                    },
                )
                response.raise_for_status()
                body = response.json()
                raw_content = body["choices"][0]["message"]["content"]
        except httpx.TimeoutException:
            logger.warning("LLM API 超时（%ds）", LLM_TIMEOUT)
            return _fallback_reply(f"API 超时（{LLM_TIMEOUT}s）")
        except httpx.HTTPStatusError as e:
            logger.warning("LLM API HTTP 错误: %s", e)
            return _fallback_reply(f"API 返回错误（{e.response.status_code}）")
        except Exception as e:
            logger.exception("LLM API 调用异常")
            return _fallback_reply(str(e))

    # Step 6: 解析结果
    result = parse_llm_response(raw_content)

    # Step 7: 存储评估记录
    eval_record_id = record_evaluation({
        "role": role,
        "user_message": user_message,
        "bbox": None,
        "grid_ids": grid_ids,
        "grid_count": stats.get("grid_count", 0),
        "total_area_mu": stats.get("total_area_mu", 0.0),
        "llm_response": raw_content,
        "structured_result": result,
        "user_feedback": None,
    })

    # ── Step 8: Gene 快照 + Capsule 发布（异步，不阻塞）──
    logger.info("eval: Step 8 entered | role=%s | grids=%d | bbox=%s", role, len(grid_ids), bbox or "none")
    if role == "government":
        asyncio.create_task(_evolution_post_eval(
            result=result,
            indicators=indicators,
            grid_ids=grid_ids,
            previous_gene=gene,
            evaluation_id=eval_record_id,
            bbox=bbox,
            user_message=user_message,
            user_id=user_id,
        ))

    # P1-2: 增强 candidate_grids（附加坐标 + 产业 + 评分）
    result["candidate_grids"] = _enhance_candidate_grids(
        result.get("candidate_grids", []), result.get("items", []), grid_ids
    )

    return result


# ============================================================
# P1-2: Candidate Grids 增强
# ============================================================

def _enhance_candidate_grids(
    candidate_grids: list,
    items: list[dict[str, Any]],
    grid_ids: list[str],
) -> list[dict[str, Any]]:
    """为每个候选网格附加 center_lng/center_lat/industry/score/reason。

    Args:
        candidate_grids: LLM 返回的候选网格列表（可能为空或旧格式）。
        items: 评估结果 items（含 industry/score/reason）。
        grid_ids: 本次评估涉及的所有 grid_id（用于关联）。

    Returns:
        list[dict]: 增强后的候选网格列表。
    """
    if not candidate_grids:
        return []

    best_item = items[0] if items else {}

    # ★ 格式检测：如果条目已有 lng/lat，直接增强
    first = candidate_grids[0]
    is_coord_obj = isinstance(first, dict) and "lng" in first

    if is_coord_obj:
        # 坐标对象格式：[{lng, lat}, ...] — 直接用，不加 grid_id
        return [
            {
                "lng": round(c.get("lng", 119.5), 6),
                "lat": round(c.get("lat", 29.8), 6),
                "industry": best_item.get("industry", ""),
                "score": best_item.get("score", 0),
                "reason": (best_item.get("reason", "") or "")[:80],
            }
            for c in candidate_grids
        ]

    # grid_id 格式：["grid_1", ...] 或 [{grid_id: "grid_1"}, ...]
    # 批量查 L0 中心坐标
    conn = get_connection()
    try:
        all_ids = [g.get("grid_id", g) if isinstance(g, dict) else str(g) for g in candidate_grids]
        placeholders = ",".join("?" for _ in all_ids)
        rows = conn.execute(
            f"""SELECT grid_id,
                       (min_lng + max_lng) / 2.0 AS center_lng,
                       (min_lat + max_lat) / 2.0 AS center_lat
                FROM land_grid_L0 WHERE grid_id IN ({placeholders})""",
            all_ids,
        ).fetchall()
        coords = {r["grid_id"]: (r["center_lng"], r["center_lat"]) for r in rows}
    finally:
        conn.close()

    best_item = items[0] if items else {}
    enhanced = []
    for entry in candidate_grids:
        gid = entry.get("grid_id", entry) if isinstance(entry, dict) else entry
        lng, lat = coords.get(gid, (119.5, 29.8))
        enhanced.append({
            "grid_id": str(gid),
            "lng": round(lng, 6),
            "lat": round(lat, 6),
            "industry": best_item.get("industry", ""),
            "score": best_item.get("score", 0),
            "reason": (best_item.get("reason", "") or "")[:80],
        })
    return enhanced


async def _evolution_post_eval(
    result: dict[str, Any],
    indicators: dict[str, dict[str, Any]],
    grid_ids: list[str],
    previous_gene: dict[str, Any],
    evaluation_id: int,
    bbox: str | None = None,
    user_message: str | None = None,
    user_id: str = "anonymous",
) -> None:
    """v2.1 自进化闭环：保存 Gene 快照 + 版本演进 + 去重 + 发布。"""
    try:
        from src.services.gene_service import (
            extract_gene_from_evaluation,
            compare_genes,
            save_gene_snapshot,
            _apply_version_evolution,
        )
        from src.services.evo_client import (
            evo_client,
            _build_gene_summary,
            _build_capsule_summary,
        )
        from src.services import grid_service as gs

        # Step 1: 提取本次评估 Gene
        new_gene = extract_gene_from_evaluation(result, indicators, previous_gene)

        # Step 2: 比较变化
        diff = compare_genes(new_gene, previous_gene)

        # Step 3: 保存快照
        save_gene_snapshot(new_gene, evaluation_id)

        # Step 4: F4 版本演进
        _apply_version_evolution(
            new_gene, diff, is_feedback=False, previous_gene=previous_gene
        )

        # ── F1 去重判定 ──
        now = time.time()
        dedup_key = _make_dedup_key(user_id, bbox, now)
        if _is_duplicate(dedup_key, now):
            logger.info(
                "EvoMap publish 跳过 | reason=dedup_5s | user=%s | bbox=%s",
                user_id, bbox or "none",
            )
            return
        _record_dedup(dedup_key, now)

        # ── 无效结果检测 ──
        items = result.get("items", [])
        if not items or all(i.get("score", 0) < 3 for i in items):
            logger.info(
                "EvoMap publish 跳过 | reason=invalid_result"
            )
            return

        # ── 构造 payload ──
        stats = gs.get_grid_stats(grid_ids)
        policy_ctx = {}
        gene_summary = _build_gene_summary(result, stats, policy_ctx, new_gene["version"])
        capsule_summary = _build_capsule_summary(result, stats, bbox, grid_ids, new_gene["version"])

        top_item = items[0] if items else {}
        scene = "产业用地评估"
        trigger_event = "政府端-框选评估" if bbox else "政府端-评估"

        top3_str = "/".join(
            f"{i.get('industry','?')}{i.get('score','?')}分" for i in items[:3]
        )
        confidence = top_item.get("score", 7.0) / 10.0

        gene_payload: dict[str, Any] = {
            "type": "Gene",
            "schema_version": "1.5.0",
            "category": "innovate",
            "signals_match": [
                "产业用地评估-能落层-地类适配",
                f"需落层-{top_item.get('industry', '产业')}场景",
                "县域产业空间规划-三层决策",
            ],
            "title": "产业用地三层评估策略",
            "summary": gene_summary,
            "model_name": "deepseek-chat",
            "domain": "data_analysis",
        }

        capsule_payload: dict[str, Any] = {
            "type": "Capsule",
            "schema_version": "1.5.0",
            "trigger": [
                "产业用地评估-框选触发",
                f"需落层-{top_item.get('industry', '产业')}场景",
            ],
            "gene": "",  # publish 内填充
            "summary": capsule_summary,
            "confidence": confidence,
            "blast_radius": {"files": 1, "lines": len(grid_ids) * 3},
            "outcome": {"status": "success", "score": confidence},
            "env_fingerprint": {"platform": os.name, "arch": "x64"},
            "success_streak": 1,
            "model_name": "deepseek-chat",
            "domain": "data_analysis",
            "capsule_data": {
                "scene": scene,
                "trigger_event": trigger_event,
                "input_summary": f"bbox {bbox}" if bbox else "全县范围",
                "grid_context": f"{stats.get('grid_count',0)}个网格",
                "recommendations": top3_str + f", 置信度{confidence:.2f}",
                "gene_version": f"v{new_gene['version']}",
                "feedback": None,
            },
        }

        logger.info(
            "EvoMap publish 开始 | scene=%s | grids=%d | gene_ver=v%s",
            scene, len(grid_ids), new_gene["version"],
        )

        await evo_client.publish(
            gene_payload=gene_payload,
            capsule_payload=capsule_payload,
            scene=scene,
            trigger=trigger_event,
        )

    except Exception:
        logger.warning("自进化后处理异常", exc_info=True)


async def _run_consultation_llm(
    message: str, role: str, context: list[dict[str, str]] | None = None
) -> dict[str, Any]:
    """纯咨询场景：不查渔网，直接 LLM 分析政策/产业方向。"""
    system_prompt = get_system_prompt(role)
    user_prompt = (
        f"当前用户咨询：{message}\n\n"
        "请以产业政策咨询专家身份，分析本地产业政策环境、产业方向和供地条件。"
        "不推荐具体地块。items 必须为空数组。"
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    if context:
        recent = [m for m in context[-6:] if m.get("role") in ("user", "assistant")]
        messages = messages[:1] + recent + messages[1:]
    try:
        from openai import OpenAI
        async with _llm_semaphore:
            client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=DEEPSEEK_MODEL,
                messages=messages,
                temperature=0.6,
                max_tokens=1500,
                timeout=LLM_TIMEOUT,
            )
        raw_content = response.choices[0].message.content or ""
    except Exception:
        logger.exception("咨询 LLM 调用失败")
        return {"summary": "咨询分析暂时不可用，请稍后重试", "items": [], "policy_citations": [], "risks": [], "candidate_grids": []}
    result = parse_llm_response(raw_content)
    result["items"] = []
    return result


async def _publish_feedback_capsule(
    prev_gene: dict[str, Any],
    new_gene: dict[str, Any],
    message: str,
) -> None:
    """v2.1: 反馈 Capsule 发布（异步，不阻塞）。"""
    try:
        from src.services.evo_client import evo_client
        diff_desc = new_gene.get("change_log", {}).get("description", "反馈修正")
        gene_payload: dict[str, Any] = {
            "type": "Gene",
            "schema_version": "1.5.0",
            "category": "innovate",
            "signals_match": ["产业用地评估-反馈修正", "权重自适应"],
            "title": f"产业用地评估策略（反馈修正 v{new_gene.get('version',0)}）",
            "summary": diff_desc[:1000],
            "model_name": "deepseek-chat",
            "domain": "data_analysis",
        }
        capsule_payload: dict[str, Any] = {
            "type": "Capsule",
            "schema_version": "1.5.0",
            "trigger": ["产业用地评估-反馈修正"],
            "gene": "",
            "summary": diff_desc[:500],
            "confidence": 0.9,
            "blast_radius": {"files": 1, "lines": 3},
            "outcome": {"status": "success", "score": 0.9},
            "env_fingerprint": {"platform": os.name, "arch": "x64"},
            "success_streak": 1,
            "model_name": "deepseek-chat",
            "domain": "data_analysis",
            "capsule_data": {
                "scene": "反馈修正",
                "trigger_event": "政府用户反馈",
                "input_summary": message[:80],
                "grid_context": "",
                "recommendations": diff_desc[:200],
                "gene_version": f"v{new_gene.get('version',0)}",
                "feedback": message[:100],
            },
        }
        await evo_client.publish(
            gene_payload=gene_payload,
            capsule_payload=capsule_payload,
            scene="反馈修正",
            trigger="政府用户反馈",
        )
    except Exception:
        logger.debug("反馈 Capsule 发布跳过（不影响主流程）", exc_info=True)


async def chat(
    message: str,
    role: str,
    context: list[dict[str, str]] | None = None,
    bbox: str | None = None,
    user_id: str = "anonymous",
) -> dict[str, Any]:
    """对话接口。

    若 bbox 非空，先查网格再评估；否则仅做纯文本产业咨询。

    Args:
        message: 用户输入文本（≤500 字符）。
        role: 用户角色。
        context: 可选的对话历史列表。
        bbox: 可选的 WGS84 边界框 "lng1,lat1,lng2,lat2"。

    Returns:
        dict: AgentReply 字典。
    """
    if bbox:
        # 有框选 → 先查网格
        parts = bbox.split(",")
        if len(parts) == 4:
            try:
                bbox_tuple = tuple(float(p) for p in parts)
                query_result = grid_service.query_by_bbox(
                    (bbox_tuple[0], bbox_tuple[1], bbox_tuple[2], bbox_tuple[3]),
                    zoom=20,
                    role=role,
                )
                grid_ids = [
                    f["grid_id"] for f in query_result.get("features", [])
                    if f.get("grid_id")
                ]
                if grid_ids:
                    return await evaluate_grids(grid_ids, message, role, context, bbox=bbox, user_id=user_id)
            except (ValueError, TypeError):
                logger.warning("bbox 格式无效: %s", bbox)

    # 尝试从消息中提取 grid_id（如 sticky note "评估此地块" 按钮触发）
    grid_match = re.match(r'评估网格\s+(grid_\S+)', message)
    if grid_match:
        grid_id = grid_match.group(1)
        return await evaluate_grids([grid_id], message, role, context, bbox=bbox, user_id=user_id)

    # 无框选或 bbox 无效 → 纯产业咨询
    # 检测是否为政府反馈修正
    role_lower = role.lower() if isinstance(role, str) else role
    if role_lower in ("government", "gov"):
        from src.services.gene_service import (
            is_feedback_message, get_latest_gene, apply_feedback, save_gene_snapshot
        )
        if is_feedback_message(message):
            current_gene = get_latest_gene()
            new_gene = apply_feedback(message, current_gene)
            if new_gene.get("version") != current_gene.get("version"):
                save_gene_snapshot(new_gene, None)
                asyncio.create_task(_publish_feedback_capsule(
                    current_gene, new_gene, message
                ))
                from src.services.gene_service import _build_feedback_reply
                reply = _build_feedback_reply(new_gene)
                if not reply:
                    reply = (
                        f"📋 反馈已采纳，评估基因已更新"
                        f"（v{current_gene.get('version', 0)}→v{new_gene.get('version', 0)}）。"
                    )
                return {
                    "summary": reply,
                    "items": [],
                    "policy_citations": [],
                    "risks": [],
                    "candidate_grids": [],
                }
            else:
                return {
                    "summary": (
                        "未识别到可执行的权重调整规则。"
                        "请尝试更具体的反馈（如\"权属分散地块不要优先推荐\"）。"
                    ),
                    "items": [],
                    "policy_citations": [],
                    "risks": [],
                    "candidate_grids": [],
                }

    # 纯咨询场景 → 调咨询 LLM
    return await _run_consultation_llm(message, role, context)


# ============================================================
# 模块级变量：完整政策文本映射（供 evaluate_grids 内部使用）
# ============================================================

from src.services.policy_service import POLICY_LIBRARY as POLICY_LIBRARY_FULL  # noqa: E402
