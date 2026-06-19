"""
企业匹配服务。

政府端：多选企业 → 全域最优地块匹配
企业端：单企业需求 → 公开数据推荐（P3 可砍，保留接口）
"""
from __future__ import annotations

import json
import logging
from typing import Any

from src.config import TONGLU_BBOX
from src.database import get_connection
from src.schemas import EnterpriseMatchResult
from src.services import eval_service, grid_service

logger = logging.getLogger(__name__)


# ============================================================
# 企业列表查询
# ============================================================

def list_enterprises(search: str = "") -> list[dict[str, Any]]:
    """查询企业列表。

    Args:
        search: 模糊搜索字符串，为空返回全部。

    Returns:
        list[dict]: 企业列表，每项含 id/name/industry/industry_code/
                    employee_count/annual_revenue/priority_tags。
    """
    conn = get_connection()
    try:
        if search:
            like = f"%{search}%"
            rows = conn.execute(
                """
                SELECT id, name, industry, industry_code,
                       employee_count, annual_revenue, priority_tags
                FROM enterprises
                WHERE name LIKE ? OR industry LIKE ? OR industry_code LIKE ?
                ORDER BY name
                """,
                (like, like, like),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, name, industry, industry_code,
                       employee_count, annual_revenue, priority_tags
                FROM enterprises
                ORDER BY name
                """
            ).fetchall()

        result: list[dict[str, Any]] = []
        for row in rows:
            d = dict(row)
            # 解析 JSON 字段
            tags_raw = d.get("priority_tags", "")
            try:
                d["priority_tags"] = json.loads(tags_raw) if tags_raw else []
            except (json.JSONDecodeError, TypeError):
                d["priority_tags"] = []
            result.append(d)
        return result
    finally:
        conn.close()


# ============================================================
# 企业匹配（政府端）
# ============================================================

async def match_enterprises(
    enterprise_ids: list[int],
    role: str,
) -> list[dict[str, Any]]:
    """政府端多企业批量匹配。

    编排步骤：
      1. 查 enterprises 表拿企业画像
      2. 对每家企业：在全域 grid 中筛选 → LLM 评估 → 取前 3 候选
      3. 返回 EnterpriseMatchResult 列表

    Args:
        enterprise_ids: 选中的企业 ID 列表（最多 5 个）。
        role: 用户角色，必须为 "government"。

    Returns:
        list[dict]: EnterpriseMatchResult 列表。

    Raises:
        PermissionError: role 非 government。
    """
    if role.lower() not in ("government", "gov"):
        raise PermissionError("企业匹配仅政府端可用")

    if not enterprise_ids:
        return []

    conn = get_connection()
    try:
        # 查企业
        placeholders = ",".join("?" for _ in enterprise_ids)
        rows = conn.execute(
            f"""
            SELECT id, name, industry, industry_code,
                   space_demand, requirements, priority_tags
            FROM enterprises
            WHERE id IN ({placeholders})
            """,
            [str(eid) for eid in enterprise_ids],
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        # 空表兜底
        return []

    results: list[dict[str, Any]] = []
    for row in rows:
        ent: dict[str, Any] = dict(row)

        # 解析 JSON 字段
        try:
            space_demand = json.loads(ent.get("space_demand") or "{}")
        except (json.JSONDecodeError, TypeError):
            space_demand = {}
        try:
            requirements = json.loads(ent.get("requirements") or "{}")
        except (json.JSONDecodeError, TypeError):
            requirements = {}

        area_mu = space_demand.get("max_area_sqm", 0) / 666.67 if isinstance(space_demand.get("max_area_sqm"), (int, float)) else 0.0

        # 全域查询候选地块
        query_result = grid_service.query_by_bbox(
            (TONGLU_BBOX[0], TONGLU_BBOX[1], TONGLU_BBOX[2], TONGLU_BBOX[3]),
            role,
        )

        features = query_result.get("features", [])
        # 按 preferred_town 过滤
        preferred_town = space_demand.get("preferred_town", "")
        if preferred_town:
            features = [f for f in features if f.get("town", "") == preferred_town]

        if not features:
            results.append({
                "enterprise_id": ent["id"],
                "enterprise_name": ent["name"],
                "candidates": [],
            })
            continue

        # 取前 500 个候选 grid_ids（BBOX_QUERY_LIMIT）
        grid_ids = [f["grid_id"] for f in features[:500] if f.get("grid_id")]

        # 调 eval_service 评估
        user_msg = (
            f"为企业「{ent['name']}」（{ent.get('industry', '')}行业）寻找用地。"
            f"面积需求约 {area_mu:.0f} 亩。"
        )
        eval_result = await eval_service.evaluate_grids(grid_ids, user_msg, role)

        # 构建候选人列表（取前 3）
        items = eval_result.get("items", [])
        candidates: list[dict[str, Any]] = []
        for i, item in enumerate(items[:3]):
            # 为每项分配候选 grid_ids（均匀分割）
            chunk_size = max(1, len(grid_ids) // max(1, len(items)))
            start = i * chunk_size
            end = min(len(grid_ids), start + chunk_size)
            cand_grid_ids = grid_ids[start:end] if grid_ids else []

            # 计算中心点
            cand_features = [f for f in features if f.get("grid_id") in cand_grid_ids]
            center: list[float] = [119.5, 29.8]  # 默认桐庐中心
            if cand_features:
                lngs = [
                    (f.get("min_lng", 0) + f.get("max_lng", 0)) / 2
                    for f in cand_features
                ]
                lats = [
                    (f.get("min_lat", 0) + f.get("max_lat", 0)) / 2
                    for f in cand_features
                ]
                if lngs and lats:
                    center = [sum(lngs) / len(lngs), sum(lats) / len(lats)]

            candidates.append({
                "grid_ids": cand_grid_ids,
                "area_mu": len(cand_grid_ids) * 10000 / 666.67 if cand_grid_ids else area_mu,
                "score": item.get("score", 0),
                "reason": item.get("reason", ""),
                "center": center,
            })

        results.append({
            "enterprise_id": ent["id"],
            "enterprise_name": ent["name"],
            "candidates": candidates,
        })

    return [EnterpriseMatchResult.model_validate(d) for d in results]


# ============================================================
# 企业端单企推荐（P3 可砍）
# ============================================================

# 企业端 P3 可砍，本函数仅保留接口以备扩展
async def match_single_enterprise(
    industry: str,
    area_mu: float,
    location_prefs: list[str],
    facility_needs: list[str],
) -> dict[str, Any]:
    """企业端单企用地建议。

    基于公开数据（不含渔网精确定位）给出宽泛产业咨询。
    P3 可砍模块，实现从简。

    Args:
        industry: 所属行业。
        area_mu: 用地面积需求（亩）。
        location_prefs: 区位偏好列表。
        facility_needs: 配套要求列表。

    Returns:
        dict: AgentReply 字典。
    """
    user_message = (
        f"我是 {industry} 行业企业，需要 {area_mu} 亩用地。"
        f"区位偏好：{', '.join(location_prefs) if location_prefs else '不限'}。"
        f"配套需求：{', '.join(facility_needs) if facility_needs else '无特殊需求'}。"
    )
    return await eval_service.chat(
        message=user_message,
        role="enterprise",
        bbox=None,
    )
