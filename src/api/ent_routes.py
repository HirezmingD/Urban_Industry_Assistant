"""
企业相关 REST 端点。

GET  /api/enterprise/list     — 企业列表（模糊搜索）
POST /api/enterprise/match    — 政府端多企业批量匹配
POST /api/enterprise/suggest  — 企业端单企用地建议（P3 可砍）
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.schemas import AgentReply, EnterpriseMatchRequest, EnterpriseMatchResult
from src.services import ent_service

router = APIRouter(prefix="/api/enterprise", tags=["enterprise"])


@router.get("/list")
async def list_enterprises(
    search: str = Query("", max_length=100, description="模糊搜索关键词"),
) -> list[dict]:
    """企业列表查询。

    Args:
        search: 按名称/行业/行业代码模糊搜索，为空返回全部。

    Returns:
        list[dict]: 企业列表。
    """
    return ent_service.list_enterprises(search)


@router.post("/match", response_model=list[EnterpriseMatchResult])
async def match(req: EnterpriseMatchRequest) -> list:
    """政府端多企业批量匹配。

    Args:
        req: EnterpriseMatchRequest（enterprise_ids + role）。

    Returns:
        list[EnterpriseMatchResult]: 匹配结果列表。

    Raises:
        HTTPException: 400（列表为空/超限）或 403（非政府端）。
    """
    if not req.enterprise_ids:
        raise HTTPException(status_code=400, detail="enterprise_ids 不能为空")

    # 解析 int id
    try:
        ids = [int(eid) for eid in req.enterprise_ids]
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="enterprise_ids 必须为整数")

    if len(ids) > 50:
        raise HTTPException(status_code=400, detail="单次最多匹配 50 家企业")

    try:
        results = await ent_service.match_enterprises(ids, "government")
    except PermissionError:
        raise HTTPException(status_code=403, detail="企业匹配仅政府端可用")

    return results


# 企业端 P3 可砍接口，主路演不依赖此接口
@router.post("/suggest", response_model=AgentReply)
async def suggest(
    industry: str = Query(..., description="所属行业"),
    area_mu: float = Query(..., description="用地面积（亩）"),
    location_prefs: Optional[list[str]] = Query(None, description="区位偏好"),
    facility_needs: Optional[list[str]] = Query(None, description="配套要求"),
) -> dict:
    """企业端单企用地建议（P3 可砍）。

    Args:
        industry: 所属行业。
        area_mu: 用地面积需求（亩）。
        location_prefs: 区位偏好列表。
        facility_needs: 配套要求列表。

    Returns:
        AgentReply。
    """
    if not industry or not industry.strip():
        raise HTTPException(status_code=400, detail="industry 不能为空")

    result = await ent_service.match_single_enterprise(
        industry=industry.strip(),
        area_mu=area_mu,
        location_prefs=location_prefs or [],
        facility_needs=facility_needs or [],
    )

    return {
        "summary": result.get("summary", ""),
        "items": result.get("items", []),
        "policy_citations": result.get("policy_citations", []),
        "risks": result.get("risks", []),
        "candidate_grids": result.get("candidate_grids", []),
    }
