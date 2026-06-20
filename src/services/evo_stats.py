"""
自进化统计数据聚合（批次 D 从 evo_service.py 拆分）。

从本地 SQLite 数据库聚合评估记录、Capsule 发布数、
偏好理解度、五维雷达图数据。不调 EvoMap Hub。
"""
from __future__ import annotations

import logging
from typing import Any

from src.database import get_connection

logger = logging.getLogger(__name__)


def _get_gene_version(conn) -> int:
    """查最新 Gene 版本号。表不存在时返回 0。"""
    try:
        row = conn.execute(
            "SELECT version FROM gene_snapshots ORDER BY version DESC LIMIT 1"
        ).fetchone()
        return row["version"] if row else 0
    except Exception:
        return 0


def get_evolution_stats() -> dict[str, Any]:
    """从本地数据库聚合自进化统计数据。

    不调 hub，全部从 evaluations / evomap_capsules 表读取。

    Returns:
        dict: 含 evolution_count / preference_understanding /
              methodology_count / capsule_contributed / radar_values。
              表为空时所有数值归零，雷达基线 30。
    """
    conn = get_connection()
    try:
        # 评估总数
        eval_count = conn.execute(
            "SELECT COUNT(*) FROM evaluations"
        ).fetchone()[0]

        # Capsule 数
        capsule_count = conn.execute(
            "SELECT COUNT(*) FROM evomap_capsules"
        ).fetchone()[0]

        # 偏好理解度：基线 30%，每次评估 +5%，封顶 95%
        preference = min(95.0, 30.0 + eval_count * 5.0)

        # 雷达图五维（基于交互类型计数 + 基线）
        interaction_counts: dict[str, int] = {}
        for row in conn.execute(
            "SELECT action_type, COUNT(*) AS cnt FROM interactions GROUP BY action_type"
        ).fetchall():
            interaction_counts[row["action_type"]] = row["cnt"]

        def _radar_val(base: int, action: str) -> float:
            cnt = interaction_counts.get(action, 0)
            return min(100.0, base + cnt * 2.0)

        radar_values = {
            "产业匹配": _radar_val(50, "chat"),
            "政策理解": _radar_val(55, "chat"),
            "空间分析": _radar_val(40, "bbox_select"),
            "风险识别": _radar_val(35, "chat"),
            "企业匹配": _radar_val(30, "match"),
        }

        return {
            "evolution_count": eval_count,
            "preference_understanding": round(preference, 1),
            "methodology_count": capsule_count,
            "capsule_contributed": capsule_count,
            "radar_values": radar_values,
            "gene_version": _get_gene_version(conn),
        }
    finally:
        conn.close()
