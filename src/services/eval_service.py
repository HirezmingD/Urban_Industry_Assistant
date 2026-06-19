"""
核心评估编排服务。

编排网格查询 + 政策匹配 + LLM 调用 → 结构化评估结果 → 存储评估记录。
使用 httpx.AsyncClient 调用 DeepSeek API（OpenAI 兼容格式）。
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
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

def record_evaluation(eval_data: dict[str, Any]) -> None:
    """写入 evaluations 表（自进化经验池）。

    写入失败仅日志告警，不影响主流程。

    Args:
        eval_data: 评估记录，含 role / user_message / bbox / grid_ids /
                   grid_count / total_area_mu / llm_response /
                   structured_result / user_feedback。
    """
    try:
        conn = get_connection()
        try:
            conn.execute(
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
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        logger.exception("写入 evaluations 表失败（不影响主流程）")


# ============================================================
# 核心评估逻辑
# ============================================================

async def evaluate_grids(
    grid_ids: list[str],
    user_message: str,
    role: str,
    context: list[dict[str, str]] | None = None,
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
    # Step 1: 网格聚合统计
    stats = grid_service.get_grid_stats(grid_ids)

    # 转为 grid_data 列表格式供 build_eval_prompt 使用
    grid_data = [stats]

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
    record_evaluation({
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

    return result


async def chat(
    message: str,
    role: str,
    context: list[dict[str, str]] | None = None,
    bbox: str | None = None,
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
                    role,
                )
                grid_ids = [
                    f["grid_id"] for f in query_result.get("features", [])
                    if f.get("grid_id")
                ]
                if grid_ids:
                    return await evaluate_grids(grid_ids, message, role, context)
            except (ValueError, TypeError):
                logger.warning("bbox 格式无效: %s", bbox)

    # 尝试从消息中提取 grid_id（如 sticky note "评估此地块" 按钮触发）
    grid_match = re.match(r'评估网格\s+(grid_\S+)', message)
    if grid_match:
        grid_id = grid_match.group(1)
        return await evaluate_grids([grid_id], message, role, context)

    # 无框选或 bbox 无效 → 纯产业咨询
    # TODO[BatchD]: 实现纯咨询路径（不查渔网，调用 LLM 做产业建议）
    #  当前退回 evaluate_grids 但 grid_ids 为空
    return await evaluate_grids([], message, role, context)


# ============================================================
# 模块级变量：完整政策文本映射（供 evaluate_grids 内部使用）
# ============================================================

from src.services.policy_service import POLICY_LIBRARY as POLICY_LIBRARY_FULL  # noqa: E402
