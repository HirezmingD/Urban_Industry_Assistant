"""
EvoMap 自进化展示 REST 端点。

GET /api/evomap/auth     — 触发 OAuth2 授权（返回跳转 URL）
GET /api/evomap/callback — OAuth2 回调处理（code → token）
GET /api/evomap/status   — 返回 EvoMap 连接状态和本地进化统计数据
GET /api/evomap/capsules — 查询本地 Capsule 发布历史
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from src.config import EVOMAP_HUB_URL
from src.database import get_connection
from src.schemas import EvoStatusResponse
from src.services import evo_service
from src.services.oauth_client import oauth_client

router = APIRouter(prefix="/api/evomap", tags=["evomap"])


@router.get("/auth")
async def evomap_auth():
    """Step 1: 返回 EvoMap OAuth2 授权 URL。

    用户浏览器访问该 URL 完成授权（PKCE S256 流程）。

    Returns:
        dict: 含 authorize_url 和 message。
    """
    authorize_url = oauth_client.build_authorize_url()
    return {
        "authorize_url": authorize_url,
        "message": "请在浏览器中打开此链接完成 EvoMap OAuth2 授权",
    }


@router.get("/callback")
async def evomap_callback(code: str = Query(...), state: str = Query(...)):
    """Step 2: OAuth2 回调——用 authorization code 交换 access_token。

    EvoMap 授权服务器完成用户授权后回跳至此端点。

    Args:
        code: EvoMap 回调中的 authorization code。
        state: EvoMap 回调中的 state 参数（CSRF 校验）。

    Returns:
        dict: 授权结果，含 status 和 scopes。
    """
    result = await oauth_client.exchange_code(code, state)
    if "error" in result:
        return {"status": "failed", "error": result["error"]}
    return {
        "status": "authorized",
        "test_mode": result.get("test_mode", False),
        "scopes": result.get("scope", oauth_client.scope or ""),
    }


@router.get("/capsules")
async def evomap_capsules(limit: int = 20, offset: int = 0):
    """查询本地 Capsule 发布历史（P1-1 增强：含 scene/trigger/reason/impact）。

    从 evomap_capsules 表读取，支持分页。

    Args:
        limit: 每页条数，默认 20。
        offset: 偏移量，默认 0。

    Returns:
        dict: 含 capsules 列表和 total 总数。
    """
    try:
        conn = get_connection()
        try:
            total_row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM evomap_capsules"
            ).fetchone()
            total = total_row["cnt"] if total_row else 0
            rows = conn.execute(
                """SELECT id, scene, trigger_reason, change_reason, impact,
                          summary, confidence, publish_status, created_at
                   FROM evomap_capsules ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                (limit, offset),
            ).fetchall()
            capsules = [dict(row) for row in rows]
        finally:
            conn.close()
    except Exception:
        return {"capsules": [], "total": 0, "limit": limit, "offset": offset}

    return {"capsules": capsules, "total": total, "limit": limit, "offset": offset}


@router.get("/gene")
async def evomap_gene(version: int | None = None):
    """获取当前或指定版本的评估基因。

    Args:
        version: 可选，指定版本号。不传时返回最新版本。

    Returns:
        dict: Gene 快照（反序列化后）。
    """
    from src.services.gene_service import get_latest_gene, get_gene_history

    if version is not None:
        history = get_gene_history(limit=100)
        for g in history:
            if g.get("version") == version:
                return {"status": "ok", "gene": g}
        return {"status": "not_found", "message": f"版本 {version} 不存在"}

    gene = get_latest_gene()
    return {"status": "ok", "gene": gene}


@router.get("/status")
async def evo_status() -> dict:
    """自进化展示数据（P1-1 增强：含 gene_history）。

    Returns:
        dict: 含在线状态 + 本地进化统计 + 五维雷达 + 进化曲线数据。
    """
    stats = evo_service.get_evolution_stats()
    evo_status_data = await evo_service.evo_client.status()

    from src.services.gene_service import get_gene_history
    gene_history = get_gene_history(limit=20)

    return {
        "online": evo_status_data.get("online", False),
        "node_id": evo_status_data.get("node_id"),
        "credit_balance": evo_status_data.get("credit_balance"),
        "capsules_published": stats.get("capsule_contributed", 0),
        "evolution_count": stats.get("evolution_count", 0),
        "preference_understanding": stats.get("preference_understanding", 0.0),
        "radar_values": stats.get("radar_values", {}),
        "gene_history": gene_history,
        "degraded": evo_service.evo_client.degraded,
        "heartbeat_fail_count": evo_service.evo_client.heartbeat_fail_count,
    }
