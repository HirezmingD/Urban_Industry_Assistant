"""
地图相关 REST 端点。

提供框选查询、单格详情、九宫格悬停查询的 HTTP API。
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from src.config import TONGLU_BBOX
from src.schemas import GridFeature, GridDetailResponse, MapQueryResponse
from src.services import grid_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/map", tags=["map"])

# 亩换算常数
_SQM_PER_MU = 666.67


# ============================================================
# Helper
# ============================================================

def _validate_role(role: str) -> None:
    """校验 role 参数，不接受 government/enterprise 以外的值。

    Args:
        role: 用户角色字符串。

    Raises:
        HTTPException: role 不合法时 400。
    """
    role_lower = role.lower()
    if role_lower not in ("government", "gov", "enterprise", "enterprise"):
        raise HTTPException(
            status_code=400,
            detail=f"无效的 role 参数: {role}，仅接受 government 或 enterprise",
        )


def _parse_bbox(bbox_str: str) -> tuple[float, float, float, float]:
    """解析 bbox 字符串为浮点元组。

    Args:
        bbox_str: "lng1,lat1,lng2,lat2" 格式。

    Returns:
        (min_lng, min_lat, max_lng, max_lat)。

    Raises:
        HTTPException: 格式错误或超出桐庐范围时 400。
    """
    parts = bbox_str.split(",")
    if len(parts) != 4:
        raise HTTPException(status_code=400, detail="bbox 参数格式错误，需为 lng1,lat1,lng2,lat2")
    try:
        coords = [float(p) for p in parts]
    except ValueError:
        raise HTTPException(status_code=400, detail="bbox 参数含非数字值")

    min_lng, min_lat, max_lng, max_lat = coords
    # 范围检查
    if min_lng < TONGLU_BBOX[0] or max_lng > TONGLU_BBOX[2] or \
       min_lat < TONGLU_BBOX[1] or max_lat > TONGLU_BBOX[3]:
        raise HTTPException(
            status_code=400,
            detail=f"bbox 超出桐庐范围 {TONGLU_BBOX}",
        )

    return (min_lng, min_lat, max_lng, max_lat)


# ============================================================
# Routes
# ============================================================

@router.get("/query", response_model=MapQueryResponse)
async def query_map(
    bbox: str = Query(..., description="WGS84 边界框 lng1,lat1,lng2,lat2"),
    zoom: int = Query(12, ge=11, le=18, description="地图缩放级别"),
    role: str = Query("government", description="用户角色"),
) -> dict[str, Any]:
    """框选范围内渔网查询。

    Args:
        bbox: 边界框字符串。
        role: 用户角色。

    Returns:
        MapQueryResponse。
    """
    _validate_role(role)
    bbox_tuple = _parse_bbox(bbox)

    try:
        result = grid_service.query_by_bbox(bbox_tuple, zoom, role)
    except PermissionError:
        raise HTTPException(status_code=403, detail="企业端不可访问此接口")
    except Exception as e:
        logger.exception("query_by_bbox 异常")
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "grid_count": result.get("grid_count", 0),
        "total_area_mu": result.get("total_area_mu", 0.0),
        "land_types": result.get("land_types", []),
        "features": result.get("features", []),
        "geojson": result.get("geojson", {}),
        "truncated": result.get("truncated", False),
    }


@router.get("/grid/{grid_id}", response_model=GridDetailResponse)
async def grid_detail(
    grid_id: str,
    role: str = Query("government", description="用户角色"),
) -> dict[str, Any]:
    """单渔网单元详情。

    Args:
        grid_id: 网格 ID。
        role: 必须为 government。

    Returns:
        GridDetailResponse。
    """
    _validate_role(role)

    try:
        detail = grid_service.query_by_grid_id(grid_id, role)
    except Exception as e:
        logger.exception("query_by_grid_id 异常")
        raise HTTPException(status_code=500, detail=str(e))

    if detail is None:
        # None 可能因为企业端访问（返回 None）或 grid_id 不存在
        if role.lower() in ("enterprise", "enterprise"):
            raise HTTPException(status_code=403, detail="企业端不可查看单格详情")
        raise HTTPException(status_code=404, detail="grid_id 不存在")

    # 转换 area_sqm → area_mu
    area_mu = (detail.get("area_sqm", 0) or 0) / _SQM_PER_MU

    return {
        "grid_id": detail.get("grid_id", grid_id),
        "land_type": detail.get("land_type", ""),
        "area_mu": round(area_mu, 1),
        "ownership": detail.get("ownership", ""),
        "town": detail.get("town", detail.get("township", "")),
        "mixed_type": detail.get("mixed_type"),
        "nl_mean": detail.get("nl_mean"),
        "ndvi_mean": detail.get("ndvi_mean"),
        "pm25_mean": detail.get("pm25_mean"),
    }


@router.get("/ninegrid")
async def nine_grid(
    lng: float = Query(..., description="鼠标经度"),
    lat: float = Query(..., description="鼠标纬度"),
    zoom: int = Query(12, ge=11, le=18, description="地图缩放级别"),
    role: str = Query("government", description="用户角色"),
) -> list[dict[str, Any]]:
    """鼠标悬停九宫格查询。

    Args:
        lng: 鼠标经度（WGS84）。
        lat: 鼠标纬度（WGS84）。
        role: 必须为 government。

    Returns:
        list[GridFeature] 最多 9 个网格。
    """
    _validate_role(role)

    # 坐标范围检查
    if not (TONGLU_BBOX[0] <= lng <= TONGLU_BBOX[2] and
            TONGLU_BBOX[1] <= lat <= TONGLU_BBOX[3]):
        # 超出范围返回空列表，不报错
        return []

    try:
        cells = grid_service.query_nine_grid(lng, lat, zoom, role)
    except Exception as e:
        logger.exception("query_nine_grid 异常")
        raise HTTPException(status_code=500, detail=str(e))

    return cells


@router.get("/grid_layer")
async def grid_layer(
    zoom: int = Query(..., ge=11, le=18, description="地图缩放级别"),
    bbox: str | None = Query(None, description="视口 bbox lng1,lat1,lng2,lat2"),
) -> dict:
    """返回指定 zoom 层级的轻量渔网 GeoJSON。"""
    return grid_service.query_grid_layer(zoom, bbox)
