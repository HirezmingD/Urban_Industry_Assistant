"""
EvoMap 自进化展示 REST 端点。

GET /api/evomap/status — 返回 EvoMap 连接状态和本地进化统计数据。
所有降级路径已在 service 层处理，路由直接 return。
"""
from __future__ import annotations

from fastapi import APIRouter

from src.schemas import EvoStatusResponse
from src.services import evo_service

router = APIRouter(prefix="/api/evomap", tags=["evomap"])


@router.get("/status", response_model=EvoStatusResponse)
async def evo_status() -> dict:
    """自进化展示数据。

    Returns:
        EvoStatusResponse: 含在线状态 + 本地进化统计 + 五维雷达。
    """
    stats = evo_service.get_evolution_stats()
    evo_status_data = await evo_service.evo_client.status()

    return {
        "online": evo_status_data.get("online", False),
        "node_id": evo_status_data.get("node_id"),
        "credit_balance": evo_status_data.get("credit_balance"),
        "capsules_published": stats.get("capsule_contributed", 0),
        "evolution_count": stats.get("evolution_count", 0),
        "preference_understanding": stats.get("preference_understanding", 0.0),
        "radar_values": stats.get("radar_values", {}),
    }
