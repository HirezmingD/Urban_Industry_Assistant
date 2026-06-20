"""
公开配置端点。

GET /api/config — 返回前端启动需要的公开配置（天地图 key、中国东南某县 bbox 等）。
注意：DEEPSEEK_API_KEY 绝不暴露。
"""
from fastapi import APIRouter

from src import config

router = APIRouter(prefix="/api", tags=["config"])


@router.get("/config")
def get_public_config() -> dict:
    """返回前端启动需要的公开配置。

    Returns:
        dict: 含 tianditu_key / tonglu_bbox / map_zoom 系列 / default_center。
    """
    return {
        "tianditu_key": config.TIANDITU_API_KEY or "",
        "tonglu_bbox": list(config.TONGLU_BBOX),
        "map_zoom_min": config.MAP_ZOOM_MIN,
        "map_zoom_max": config.MAP_ZOOM_MAX,
        "default_zoom": 12,
        "default_center": [29.795, 119.685],
    }
