"""
企业匹配服务。

政府端：多选企业 → 全域最优地块匹配
企业端：单企业需求 → 公开数据推荐（P3 可砍，保留接口）
"""
from __future__ import annotations

import json
import logging
import random
from typing import Any

from src.config import TONGLU_BBOX
from src.database import get_connection
from src.schemas import EnterpriseMatchResult  # kept for suggest endpoint
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
    enterprise_ids: list[str],
    role: str,
    bbox: str | None = None,
) -> dict[str, Any]:
    """政府端多企业综合布局分析。

    按当前地图视口范围查询候选网格，用户看到哪片区域就分析哪片。

    Args:
        enterprise_ids: 选中的企业 ID 列表。
        role: 用户角色。
        bbox: 可选，当前地图视口 "lng1,lat1,lng2,lat2"，不传则用全县范围。

    Args:
        enterprise_ids: 选中的企业 ID 列表。
        role: 用户角色，必须为 "government"。

    Returns:
        dict: 含 summary / items / enterprise_names / total_area_mu 等。

    Raises:
        PermissionError: role 非 government。
    """
    if role.lower() not in ("government", "gov"):
        raise PermissionError("企业匹配仅政府端可用")
    if not enterprise_ids:
        return {"summary": "", "items": []}

    # 1. 查企业信息
    conn = get_connection()
    try:
        placeholders = ",".join("?" for _ in enterprise_ids)
        rows = conn.execute(
            f"""SELECT id, name, industry, industry_code,
                       space_demand, requirements, priority_tags
                FROM enterprises WHERE id IN ({placeholders})""",
            enterprise_ids,
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return {"summary": "未找到所选企业", "items": []}

    # 2. 构建企业信息段
    ent_lines: list[str] = []
    total_area = 0.0
    for row in rows:
        ent = dict(row)
        try:
            sd = json.loads(ent.get("space_demand") or "{}")
        except Exception:
            sd = {}
        area_mu = sd.get("max_area_sqm", 0) / 666.67 if sd.get("max_area_sqm") else 0
        total_area += area_mu
        town = sd.get("preferred_town", "未指定")
        ent_lines.append(
            f"- {ent['name']}（{ent.get('industry', '')}行业）"
            f"：用地需求约 {area_mu:.0f} 亩，意向区域 {town}"
        )

    # 3. 构造综合 prompt
    user_msg = (
        f"以下 {len(rows)} 家企业拟在本县落位，请综合评估如何在县域空间内布局，"
        f"实现产业协同和整体最优：\n\n"
        + "\n".join(ent_lines) +
        f"\n\n合计用地需求约 {total_area:.0f} 亩。"
        f"请从产业协同、空间布局、政策匹配、风险管控四个维度给出综合建议。"
    )

    # 4. 当前视口范围查候选网格（或全县 fallback）
    if bbox:
        try:
            parts = [float(p) for p in bbox.split(",")]
            query_bbox = (parts[0], parts[1], parts[2], parts[3])
        except Exception:
            query_bbox = (TONGLU_BBOX[0], TONGLU_BBOX[1], TONGLU_BBOX[2], TONGLU_BBOX[3])
    else:
        query_bbox = (TONGLU_BBOX[0], TONGLU_BBOX[1], TONGLU_BBOX[2], TONGLU_BBOX[3])
    query_result = grid_service.query_by_bbox(query_bbox, zoom=20, role=role)
    features = query_result.get("features", [])
    # 随机采样均匀覆盖全县，而非按 grid_id 字母序取前 N 个
    all_gids = [f["grid_id"] for f in features if f.get("grid_id")]
    random.shuffle(all_gids)
    grid_ids = all_gids[:900]

    # 5. 调 AI 评估
    result = await eval_service.evaluate_grids(grid_ids, user_msg, role)

    return {
        "summary": result.get("summary", ""),
        "items": result.get("items", []),
        "policy_citations": result.get("policy_citations", []),
        "risks": result.get("risks", []),
        "candidate_grids": result.get("candidate_grids", []),
        "enterprise_names": [r["name"] for r in rows],
        "total_area_mu": round(total_area, 1),
    }


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
