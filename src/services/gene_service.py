"""
Gene 生命周期管理服务。

提供评估基因的创建、查询、比较、持久化，以及政府反馈解析与权重调整。
不依赖 EvoMap Hub，仅操作本地 SQLite。
"""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any

from src.database import get_connection

logger = logging.getLogger(__name__)

# ============================================================
# DEFAULT_GENE — 基线 Gene
# ============================================================

DEFAULT_GENE: dict[str, Any] = {
    "version": 0.0,
    "created_at": "",
    "updated_at": "",
    "parent_version": None,
    "weights": {
        "nld": 0.40,
        "yld": 0.35,
        "xld": 0.25,
        "sub_weights": {
            "nld_dlpd": 0.25,
            "nld_qsxt": 0.30,
            "nld_jsyt": 0.25,
            "nld_stsp": 0.20,
            "yld_jjd": 0.25,
            "yld_jtkd": 0.25,
            "yld_ggzc": 0.15,
            "yld_shpt": 0.10,
            "yld_mgfx": 0.15,
            "yld_kfqd": 0.10,
        },
    },
    "preferences": [],
    "context": {
        "region": "中国东南某县",
        "evaluation_count": 0,
        "feedback_count": 0,
        "capsule_count": 0,
    },
    "change_log": {"description": "默认基线 Gene", "diff": {}},
}

# ============================================================
# 反馈规则
# ============================================================

_FEEDBACK_RULES: list[dict[str, Any]] = [
    {"pattern": r"权属.*分散|权属.*复杂|权属.*协调", "field": "nld_qsxt", "multiplier": 1.5},
    {"pattern": r"生态.*敏感|植被.*高|NDVI.*高", "field": "nld_stsp", "multiplier": 1.3},
    {"pattern": r"交通.*差|不通.*路|偏远", "field": "yld_jtkd", "multiplier": 1.3},
    {"pattern": r"配套.*少|配套.*差|设施.*缺", "field": "yld_ggzc", "multiplier": 1.2},
    {"pattern": r"人口.*多|聚居|扰民", "field": "yld_mgfx", "multiplier": 1.3},
    {"pattern": r"物流|仓储.*不.*开发区", "field": "yld_jtkd", "multiplier": 1.2},
]

_FEEDBACK_PATTERNS: list[str] = [
    r"不要推荐", r"不要优先", r"先不推荐",
    r"权属.*复杂", r"权属.*分散",
    r"调整.*权重", r"修正",
    r"生态.*敏感", r"植被.*高",
    r"交通.*差", r"配套.*少",
]

FIELD_DISPLAY: dict[str, str] = {
    "nld_qsxt": "权属协调度", "nld_stsp": "生态适配度",
    "nld_dlpd": "地类适配度", "nld_jsyt": "建设适宜度",
    "yld_jjd": "产业集聚度",  "yld_jtkd": "交通可达性",
    "yld_ggzc": "公共设施支撑度", "yld_shpt": "生活配套度",
    "yld_mgfx": "敏感设施冲突风险", "yld_kfqd": "开发强度",
}


def is_feedback_message(message: str) -> bool:
    """检测消息是否为反馈修正类型。"""
    return any(re.search(p, message) for p in _FEEDBACK_PATTERNS)


# ============================================================
# 权重归一化
# ============================================================

def _normalize_weights(sub_weights: dict[str, float]) -> dict[str, float]:
    """层级内归一化。"""
    total = sum(sub_weights.values())
    if total == 0:
        return sub_weights
    return {k: round(v / total, 6) for k, v in sub_weights.items()}


# ============================================================
# Gene CRUD
# ============================================================

def get_latest_gene() -> dict[str, Any]:
    """获取最新版本的 Gene 快照。"""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM gene_snapshots ORDER BY version DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return dict(DEFAULT_GENE)
    return {
        "version": row["version"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "parent_version": None,
        "weights": json.loads(row["weights"]),
        "preferences": json.loads(row["preferences"]),
        "context": json.loads(row["context"]),
        "change_log": json.loads(row["change_log"]),
    }


def save_gene_snapshot(gene: dict[str, Any], evaluation_id: int | None = None) -> int:
    """持久化 Gene 快照。"""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """INSERT INTO gene_snapshots
               (version, created_at, updated_at, parent_id,
                weights, preferences, context, change_log, evaluation_id)
               VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?)""",
            (
                gene.get("version", 0.0),
                gene.get("created_at", datetime.now(timezone.utc).isoformat()),
                gene.get("updated_at", datetime.now(timezone.utc).isoformat()),
                json.dumps(gene.get("weights", {}), ensure_ascii=False),
                json.dumps(gene.get("preferences", []), ensure_ascii=False),
                json.dumps(gene.get("context", {}), ensure_ascii=False),
                json.dumps(gene.get("change_log", {}), ensure_ascii=False),
                evaluation_id,
            ),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_gene_history(limit: int = 20) -> list[dict[str, Any]]:
    """获取 Gene 版本历史（P1-1 json_extract 版本）。"""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT version, created_at,
               json_extract(weights, '$.sub_weights.nld_qsxt') AS nld_qsxt,
               json_extract(weights, '$.sub_weights.nld_dlpd') AS nld_dlpd,
               json_extract(weights, '$.sub_weights.yld_jjd') AS yld_jjd,
               json_extract(weights, '$.sub_weights.yld_jtkd') AS yld_jtkd,
               json_extract(context, '$.evaluation_count') AS eval_count,
               json_extract(context, '$.feedback_count') AS feedback_count,
               json_extract(change_log, '$.description') AS change_desc
               FROM gene_snapshots ORDER BY version DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ============================================================
# Gene 比较与提取
# ============================================================

def compare_genes(new_gene: dict[str, Any], previous_gene: dict[str, Any]) -> dict[str, Any]:
    """比较两个 Gene 快照，返回差异摘要。"""
    try:
        prev_sw = previous_gene.get("weights", {}).get("sub_weights", {})
        new_sw = new_gene.get("weights", {}).get("sub_weights", {})
        prev_prefs = previous_gene.get("preferences", [])
        new_prefs = new_gene.get("preferences", [])
        threshold = 0.05
        diffs = []
        all_keys = set(prev_sw.keys()) | set(new_sw.keys())
        for k in all_keys:
            old_val = prev_sw.get(k, 0)
            new_val = new_sw.get(k, 0)
            delta = round(new_val - old_val, 4)
            if abs(delta) > threshold:
                diffs.append({"field": k, "old": old_val, "new": new_val, "delta": delta})
        prev_rules = {p.get("rule", "") for p in prev_prefs}
        added_prefs = [p for p in new_prefs if p.get("rule", "") not in prev_rules]
        has_changed = len(diffs) > 0 or len(added_prefs) > 0
        diff_descs = []
        for d in diffs:
            direction = "+" if d["delta"] > 0 else ""
            diff_descs.append(f"{d['field']} {direction}{d['delta']:.2f}")
        description = "; ".join(diff_descs) if diff_descs else ""
        if added_prefs:
            description += f"（新增 {len(added_prefs)} 条偏好规则）" if description else f"新增 {len(added_prefs)} 条偏好规则"
        impacts = []
        for d in diffs:
            if "qsxt" in d["field"] and d["delta"] > 0:
                impacts.append("权属分散地块排序下调")
            elif "stsp" in d["field"] and d["delta"] > 0:
                impacts.append("生态敏感区地块降低推荐档位")
            elif "jtkd" in d["field"] and d["delta"] > 0:
                impacts.append("交通可达性在后续评估中权重提升")
            elif "mgfx" in d["field"] and d["delta"] > 0:
                impacts.append("敏感设施冲突风险权重提升")
            elif "ggzc" in d["field"] and d["delta"] > 0:
                impacts.append("公共设施支撑度权重提升")
        impact = "; ".join(impacts) if impacts else "权重微调"
        return {"has_changed": has_changed, "threshold": threshold, "diffs": diffs,
                "new_preferences": added_prefs, "description": description, "impact": impact}
    except Exception:
        logger.debug("compare_genes 异常，降级为无变化", exc_info=True)
        return {"has_changed": False, "threshold": 0.05, "diffs": [], "new_preferences": [],
                "description": "", "impact": ""}


def extract_gene_from_evaluation(
    result: dict[str, Any],
    indicators: dict[str, dict[str, Any]],
    previous_gene: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """从评估结果中提取新的 Gene 快照。"""
    prev = previous_gene if previous_gene else dict(DEFAULT_GENE)
    sub_weights = prev.get("weights", {}).get("sub_weights", {}).copy()
    now = datetime.now(timezone.utc).isoformat()
    context = prev.get("context", {}).copy()
    context["evaluation_count"] = context.get("evaluation_count", 0) + 1
    return {
        "version": prev.get("version", 0.0),
        "created_at": now,
        "updated_at": now,
        "parent_version": prev.get("version"),
        "weights": {
            "nld": prev.get("weights", {}).get("nld", 0.40),
            "yld": prev.get("weights", {}).get("yld", 0.35),
            "xld": prev.get("weights", {}).get("xld", 0.25),
            "sub_weights": sub_weights,
        },
        "preferences": prev.get("preferences", []).copy(),
        "context": context,
        "change_log": {"description": f"评估 #{context['evaluation_count']} — Gene 快照", "diff": {}},
    }


# ============================================================
# 反馈处理
# ============================================================

def apply_feedback(message: str, current_gene: dict[str, Any]) -> dict[str, Any]:
    """解析政府反馈文本，生成调整后的 Gene。"""
    matched_rule = None
    for rule in _FEEDBACK_RULES:
        if re.search(rule["pattern"], message):
            matched_rule = rule
            break
    if not matched_rule:
        return dict(current_gene)
    field = matched_rule["field"]
    multiplier = matched_rule["multiplier"]
    weights = json.loads(json.dumps(current_gene.get("weights", {})))
    sub_weights = weights.get("sub_weights", {})
    if field not in sub_weights:
        logger.warning("apply_feedback: field %s not in sub_weights", field)
        return dict(current_gene)
    old_val = sub_weights[field]
    new_val = round(old_val * multiplier, 4)
    sub_weights[field] = new_val
    normalized = _normalize_weights(sub_weights)
    weights["sub_weights"] = normalized
    new_version = current_gene.get("version", 0.0) + 1.0  # 反馈升主版本
    now = datetime.now(timezone.utc).isoformat()
    new_pref = {
        "rule": f"用户反馈「{message[:50]}」触发 {field} 权重调整",
        "effect": f"{field} × {multiplier}",
        "source": "government_feedback",
        "evaluation_id": None,
        "created_at": now,
    }
    preferences = list(current_gene.get("preferences", [])) + [new_pref]
    context = current_gene.get("context", {}).copy()
    context["feedback_count"] = context.get("feedback_count", 0) + 1
    delta = round(normalized.get(field, 0) - old_val, 4)
    field_display = FIELD_DISPLAY.get(field, field)
    change_log = {
        "description": f"反馈修正：{field_display} 权重 {old_val}→{normalized.get(field, old_val)} (×{multiplier})",
        "diff": {field: {"old": old_val, "new": normalized.get(field, 0), "delta": delta}},
    }
    return {
        "version": new_version,
        "created_at": now, "updated_at": now,
        "parent_version": current_gene.get("version"),
        "weights": weights, "preferences": preferences,
        "context": context, "change_log": change_log,
    }


# ============================================================
# F9: 反馈回复可读化
# ============================================================

def _build_feedback_reply(new_gene: dict[str, Any]) -> str:
    """根据 Gene.change_log 生成人类可读的反馈回复。"""
    change_log = new_gene.get("change_log", {})
    diff = change_log.get("diff", {})
    if not diff:
        return ""

    lines = ["📋 反馈已采纳，评估基因已更新\n"]
    old_ver = new_gene.get("parent_version", "?")
    new_ver = new_gene.get("version", "?")

    for field_key, change in diff.items():
        display_name = FIELD_DISPLAY.get(field_key, field_key)
        old_val = change.get("old", 0)
        new_val = change.get("new", 0)
        multiplier = round(new_val / old_val, 1) if old_val > 0 else 0

        lines.append(f"变更维度：{display_name}")
        lines.append(f"权重调整：{old_val:.2f} → {new_val:.2f}（×{multiplier}）")
        lines.append(f"版本演进：v{old_ver} → v{new_ver}\n")

        impacts = []
        if "qsxt" in field_key and multiplier > 1:
            impacts.append("权属分散的地块在近期招商场景中排序将下调")
            impacts.append("系统在推荐理由中会增加「权属协调复杂度」风险提示")
        elif "stsp" in field_key and multiplier > 1:
            impacts.append("生态敏感区地块将降低推荐档位")
            impacts.append("NDVI>0.55 的地块会被优先标记为「谨慎推荐」")
        elif "jtkd" in field_key and multiplier > 1:
            impacts.append("交通可达性在后续评估中权重提升")
            impacts.append("靠近高速口、主干路的网格将获得更高排序")
        elif "ggzc" in field_key and multiplier > 1:
            impacts.append("公共设施配套在后续评估中权重提升")
            impacts.append("邻近污水处理/变电站等设施的地块优先推荐")
        elif "mgfx" in field_key and multiplier > 1:
            impacts.append("敏感设施冲突风险权重提升")
            impacts.append("邻近居民区、学校、医院的地块会降低产业适配评分")
        if impacts:
            lines.append("对后续评估的影响：")
            for imp in impacts:
                lines.append(f"  · {imp}")
            lines.append("")

    if len(lines) <= 3:
        return ""
    return "\n".join(lines)


# ============================================================
# v2.1: 脱敏 + 震荡保护 + 版本演进
# ============================================================

_DESENSITIZE_MAP: dict[str, str] = {
    # 长串优先，避免部分匹配（如"富春江镇"必须在"富春江"前面）
    "桐君街道": "城关街道", "旧县街道": "城东街道", "城南街道": "城南片区", "凤川街道": "城北片区",
    "富春江镇": "沿江镇区", "横村镇": "中部镇区", "江南镇": "南部镇区", "分水镇": "西部镇区",
    "瑶琳镇": "北部镇区", "百江镇": "西南镇区",
    "莪山畲族乡": "少数民族乡", "钟山乡": "东部乡镇", "新合乡": "东南乡镇", "合村乡": "西北乡镇",
    "桐庐县": "中国东南某县", "杭州市": "省会城市", "浙江省": "东南沿海某省",
    "富春江": "境内主要水系",
}


def desensitize_text(text: str) -> str:
    """将文本中的真实地名替换为脱敏代称。"""
    result = text
    for real, alias in _DESENSITIZE_MAP.items():
        result = result.replace(real, alias)
    return result


_SHAKE_PROTECTION: dict[str, float] = {}
_SHAKE_WINDOW_SEC = 3600


def _is_in_shake_protection(dimension: str, now: float) -> bool:
    """检查某维度是否在 1 小时震荡保护窗口内。"""
    last_cross = _SHAKE_PROTECTION.get(dimension)
    if last_cross is None:
        return False
    return (now - last_cross) < _SHAKE_WINDOW_SEC


def _mark_shake(dimension: str, now: float) -> None:
    """标记某维度刚跨越阈值。"""
    _SHAKE_PROTECTION[dimension] = now


def _apply_version_evolution(
    new_gene: dict[str, Any],
    diff: dict[str, Any],
    is_feedback: bool,
    previous_gene: dict[str, Any],
) -> None:
    """应用 F4 版本演进规则（原地修改 new_gene["version"]）。"""
    now = time.time()
    old_ver = previous_gene.get("version", 0.0)
    new_ver = old_ver
    upgrade_desc = ""

    if is_feedback:
        major = int(old_ver) + 1
        new_ver = float(f"{major}.0")
        upgrade_desc = "反馈修正 → 主版本升级"
    elif diff.get("diffs"):
        significant = [d for d in diff["diffs"] if abs(d["delta"]) > 0.05]
        if significant:
            protected = [d for d in significant if _is_in_shake_protection(d["field"], now)]
            unprotected = [d for d in significant if d not in protected]
            if unprotected:
                major = int(old_ver)
                minor_part = round(old_ver - major, 1)
                minor = int(minor_part * 10) + 1
                new_ver = float(f"{major}.{minor}")
                upgrade_desc = "权重变化>5% → 次版本升级"
                for d in unprotected:
                    _mark_shake(d["field"], now)
            if protected:
                logger.debug("震荡保护: 维度 %s 1h内已跨越阈值，跳过版本升级",
                             ",".join(d["field"] for d in protected))

    new_gene["version"] = new_ver
    if upgrade_desc:
        prev = new_gene.get("change_log", {}).get("description", "")
        new_gene["change_log"]["description"] = f"{upgrade_desc} (v{old_ver}→v{new_ver}). {prev}"
        logger.info("Gene 版本升级 | v%s→v%s | reason=%s", old_ver, new_ver, upgrade_desc)
