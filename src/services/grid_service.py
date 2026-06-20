"""
渔网空间查询服务（V1.1 多级 LOD 金字塔）。

提供按 bbox、grid_id、九宫格定位的查询功能。
使用 SQLite R-tree 两步法加速空间查询。
支持 8 级 LOD 金字塔（zoom 11→L1 3200m ... zoom 16-18→L0 100m）。

R-tree 两步法：
  1. 通过对应层级 R-tree 索引定位候选 rowid（O(log N)）
  2. JOIN 主表获取完整字段
  避免全表扫描，框选查询满足 PRD < 200ms。
"""
from __future__ import annotations

import logging
from typing import Any

from src.config import BBOX_QUERY_LIMIT
from src.database import get_connection
from shapely import wkb
from shapely.geometry import mapping

logger = logging.getLogger(__name__)

# 亩换算常数
_SQM_PER_MU = 666.67

# ============================================================
# LOD 金字塔路由
# ============================================================

_ZOOM_TABLE_MAP: dict[int, tuple[str, int]] = {
    11: ("land_grid_L1", 1),
    12: ("land_grid_L2", 2),
    13: ("land_grid_L3", 3),
    14: ("land_grid_L4", 4),
    15: ("land_grid_L5", 5),
    16: ("land_grid_L0", 0),
    17: ("land_grid_L0", 0),
    18: ("land_grid_L0", 0),
}

_ZOOM_GRID_DEG: dict[int, float] = {
    11: 3200 / 111320.0,
    12: 1600 / 111320.0,
    13: 800 / 111320.0,
    14: 400 / 111320.0,
    15: 200 / 111320.0,
    16: 0.001,
    17: 0.001,
    18: 0.001,
}


def _get_table_for_zoom(zoom: int) -> str:
    """根据 zoom 返回对应数据表名。"""
    table_name, _ = _ZOOM_TABLE_MAP.get(zoom, ("land_grid_L0", 0))
    return table_name


def _get_nine_grid_radius(zoom: int) -> int:
    """九宫格模式：zoom 11-12 仅中心格（radius=0），13+ 3×3（radius=1）。"""
    return 0 if zoom <= 12 else 1


def _get_grid_deg_for_zoom(zoom: int) -> float:
    """根据 zoom 返回网格边长对应度数（九宫格邻格步长）。"""
    return _ZOOM_GRID_DEG.get(zoom, 0.001)


def _get_table_safe(zoom: int) -> tuple[str, int, bool]:
    """安全获取表名：聚合表不存在时 fallback 到 L0。

    Returns:
        (table_name, level, fallback_flag)
    """
    table_name, level = _ZOOM_TABLE_MAP.get(zoom, ("land_grid_L0", 0))
    if level == 0:
        return table_name, level, False

    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        if cursor.fetchone():
            return table_name, level, False
    finally:
        conn.close()
    return "land_grid_L0", 0, True


# ============================================================
# 内部辅助函数
# ============================================================

def _select_fields(role: str, is_aggregated: bool = False) -> str:
    """根据角色和表类型返回 SELECT 字段列表。

    Args:
        role: 用户角色。
        is_aggregated: L1-L5 聚合表（字段与 L0 不同）。

    Returns:
        SQL SELECT 字段列表。
    """
    role_lower = role.lower()

    if is_aggregated:
        base = (
            "grid_id, level, min_lng, min_lat, max_lng, max_lat, "
            "land_type, land_code, land_type_top3, area_sqm, "
            "ownership, town, mixed_type, geometry, extras, grid_count_original"
        )
    else:
        base = (
            "grid_id, min_lng, min_lat, max_lng, max_lat, "
            "land_type, land_code, area_sqm, ownership, town, "
            "mixed_type, nl_mean, ndvi_mean, pm25_mean, "
            "geometry, extras"
        )

    if role_lower in ("enterprise", "enterprise"):
        for f in ["ownership", "land_code", "nl_mean", "ndvi_mean", "pm25_mean", "geometry"]:
            base = base.replace(f + ", ", "").replace(", " + f, "").replace(f, "")
        base = base.rstrip(", ")

    return base


def _row_to_dict(
    row: sqlite3.Row, role: str, is_aggregated: bool = False
) -> dict[str, Any]:
    """将数据库行转为 dict，适配聚合表额外字段。

    Args:
        row: sqlite3.Row 对象。
        role: 用户角色。
        is_aggregated: 是否聚合表。

    Returns:
        dict: 字段字典。
    """
    d = dict(row)
    if not is_aggregated:
        d.setdefault("land_type_top3", "[]")
        d.setdefault("level", 0)
        d.setdefault("grid_count_original", 1)

    role_lower = role.lower()
    if role_lower not in ("government", "gov"):
        d.pop("ownership", None)
        d.pop("land_code", None)
        d.pop("nl_mean", None)
        d.pop("ndvi_mean", None)
        d.pop("pm25_mean", None)

    return d


def _wkb_to_geojson_geometry(geometry_blob: bytes) -> dict[str, Any] | None:
    """WKB → GeoJSON geometry dict。"""
    if not geometry_blob:
        return None
    try:
        geom = wkb.loads(geometry_blob)
        return mapping(geom)
    except Exception:
        return None


def _wkb_to_coords(geometry_blob: bytes) -> list | None:
    """WKB → 坐标数组（仅提取 coordinates）。"""
    if not geometry_blob:
        return None
    try:
        geom = wkb.loads(geometry_blob)
        geo = mapping(geom)
        return geo.get("coordinates") if geo else None
    except Exception:
        return None


# ============================================================
# 公开查询函数
# ============================================================

def query_by_bbox(
    bbox_wgs84: tuple[float, float, float, float],
    zoom: int,
    role: str,
) -> dict[str, Any]:
    """按 WGS84 边界框查询渔网单元（V1.1：支持 LOD 金字塔）。

    Args:
        bbox_wgs84: (min_lng, min_lat, max_lng, max_lat)。
        zoom: 地图缩放级别 11-18。
        role: 用户角色。

    Returns:
        dict: 含 grid_count, total_area_mu, land_types, features, geojson,
              truncated, fallback。
    """
    min_lng, min_lat, max_lng, max_lat = bbox_wgs84
    table_name, level, fallback = _get_table_safe(zoom)
    rtree_name = f"{table_name}_rtree"
    is_aggregated = level > 0

    conn = get_connection()
    try:
        fields = _select_fields(role, is_aggregated)

        # R-tree 两步法：步骤 1 — R-tree 过滤
        rtree_sql = f"""
            SELECT r.id FROM {rtree_name} r
            WHERE r.min_lng <= ? AND r.max_lng >= ?
              AND r.min_lat <= ? AND r.max_lat >= ?
            LIMIT ?
        """
        rtree_ids = conn.execute(
            rtree_sql, (max_lng, min_lng, max_lat, min_lat, BBOX_QUERY_LIMIT + 1)
        ).fetchall()

        truncated = len(rtree_ids) > BBOX_QUERY_LIMIT
        rtree_ids = rtree_ids[:BBOX_QUERY_LIMIT]

        if not rtree_ids:
            return {
                "grid_count": 0, "total_area_mu": 0.0, "land_types": [],
                "features": [], "geojson": {"type": "FeatureCollection", "features": []},
                "truncated": False, "fallback": fallback,
            }

        rowids = [r["id"] for r in rtree_ids]
        placeholders = ",".join("?" for _ in rowids)

        main_sql = f"""
            SELECT {fields} FROM {table_name} g
            WHERE g.rowid IN ({placeholders})
        """
        rows = conn.execute(main_sql, rowids).fetchall()

        features = [_row_to_dict(r, role, is_aggregated) for r in rows]
        for f in features:
            f.pop("geometry", None)

        land_types = list(set(r["land_type"] for r in rows if r["land_type"]))
        total_area_sqm = sum(r["area_sqm"] or 0 for r in rows)
        total_area_mu = total_area_sqm / _SQM_PER_MU

        geojson: dict[str, Any] = {"type": "FeatureCollection", "features": []}
        if role.lower() in ("government", "gov"):
            geojson["features"] = [
                {
                    "type": "Feature",
                    "properties": {
                        "grid_id": r["grid_id"],
                        "land_type": r["land_type"],
                        "level": level,
                        "score": None,
                    },
                    "geometry": _wkb_to_geojson_geometry(r["geometry"]),
                }
                for r in rows if r["geometry"]
            ]

        return {
            "grid_count": len(features), "total_area_mu": round(total_area_mu, 1),
            "land_types": land_types, "features": features,
            "geojson": geojson, "truncated": truncated, "fallback": fallback,
        }
    finally:
        conn.close()


def query_by_grid_id(grid_id: str, role: str) -> dict[str, Any] | None:
    """查询单个渔网单元详情。

    企业端无权访问，直接返回 None。
    """
    role_lower = role.lower()
    if role_lower in ("enterprise", "enterprise"):
        return None

    conn = get_connection()
    try:
        # 尝试在所有表中查找
        for tn in ["land_grid_L0", "land_grid_L1", "land_grid_L2",
                    "land_grid_L3", "land_grid_L4", "land_grid_L5"]:
            row = conn.execute(
                f"SELECT * FROM {tn} WHERE grid_id = ?", (grid_id,)
            ).fetchone()
            if row:
                is_agg = tn != "land_grid_L0"
                return _row_to_dict(row, role, is_agg)
        return None
    finally:
        conn.close()


def query_nine_grid(
    lng: float,
    lat: float,
    zoom: int,
    role: str,
) -> list[dict[str, Any]]:
    """根据经纬度定位九宫格渔网单元（V1.1 LOD）。

    zoom 11-12：仅中心格；zoom 13-18：3×3 九宫格。
    企业端返回空列表。

    Args:
        lng, lat: 鼠标坐标（WGS84）。
        zoom: 地图缩放级别。
        role: 用户角色。

    Returns:
        list[dict]: 最多 9 个网格详情。企业端返回 []。
    """
    role_lower = role.lower()
    if role_lower in ("enterprise", "enterprise"):
        return []

    table_name, level, _ = _get_table_safe(zoom)
    is_aggregated = level > 0
    radius = _get_nine_grid_radius(zoom)
    margin = _get_grid_deg_for_zoom(zoom)

    conn = get_connection()
    try:
        fields = _select_fields(role, is_aggregated)

        # 1. 找中心格
        center = conn.execute(
            f"""
            SELECT {fields} FROM {table_name}
            WHERE min_lng <= ? AND max_lng >= ?
              AND min_lat <= ? AND max_lat >= ?
            LIMIT 1
            """,
            (lng, lng, lat, lat),
        ).fetchone()

        if center is None:
            return []

        center_dict = _row_to_dict(center, role, is_aggregated)
        result = [center_dict]

        # 2. 扩展邻格（仅 radius > 0）
        if radius > 0:
            neighbors = conn.execute(
                f"""
                SELECT {fields} FROM {table_name}
                WHERE min_lng <= ? AND max_lng >= ?
                  AND min_lat <= ? AND max_lat >= ?
                  AND grid_id != ?
                LIMIT 8
                """,
                (lng + margin, lng - margin, lat + margin, lat - margin,
                 center_dict["grid_id"]),
            ).fetchall()

            for row in neighbors:
                result.append(_row_to_dict(row, role, is_aggregated))

        # === Step A: WKB → coords（必须在 pop geometry 之前）===
        for d in result:
            geom_blob = d.get("geometry")
            if geom_blob:
                try:
                    geom = wkb.loads(geom_blob)
                    d["coords"] = mapping(geom).get("coordinates")
                except Exception:
                    d["coords"] = None
            else:
                d["coords"] = None

        # === Step B: 精简字段 ===
        keep = {"grid_id", "min_lng", "min_lat", "max_lng", "max_lat", "coords"}
        for d in result:
            for k in list(d.keys()):
                if k not in keep:
                    del d[k]

        return result
    finally:
        conn.close()


def _parse_bbox(bbox_str: str) -> tuple[float, float, float, float]:
    """解析 bbox 字符串 "lng1,lat1,lng2,lat2" → 元组。"""
    parts = [float(p) for p in bbox_str.split(",")]
    return (parts[0], parts[1], parts[2], parts[3])


def query_grid_layer(zoom: int, bbox: str | None = None) -> dict[str, Any]:
    """返回指定 zoom 层级的轻量 GeoJSON FeatureCollection。

    仅含 geometry + 标识/定位字段，不含完整属性（payload 缩减约 60%）。

    Args:
        zoom: 地图缩放级别。
        bbox: 可选的视口范围 "lng1,lat1,lng2,lat2"。

    Returns:
        dict: GeoJSON FeatureCollection。
    """
    table_name = _get_table_for_zoom(zoom)
    conn = get_connection()
    try:
        fields = ("grid_id, land_type, land_code, "
                   "min_lng, min_lat, max_lng, max_lat, geometry")

        if bbox:
            min_lng, min_lat, max_lng, max_lat = _parse_bbox(bbox)
            rtree_name = f"{table_name}_rtree"
            rtree_ids = conn.execute(
                f"""SELECT r.id FROM {rtree_name} r
                   WHERE r.min_lng <= ? AND r.max_lng >= ?
                     AND r.min_lat <= ? AND r.max_lat >= ?
                   LIMIT 60000""",
                (max_lng, min_lng, max_lat, min_lat),
            ).fetchall()
            if not rtree_ids:
                return {"type": "FeatureCollection", "features": []}
            rowids = [r["id"] for r in rtree_ids]
            placeholders = ",".join("?" for _ in rowids)
            rows = conn.execute(
                f"SELECT {fields} FROM {table_name} WHERE rowid IN ({placeholders})",
                rowids,
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT {fields} FROM {table_name}"
            ).fetchall()

        features = []
        for r in rows:
            geom_dict = _wkb_to_geojson_geometry(r["geometry"])
            if not geom_dict:
                continue
            features.append({
                "type": "Feature",
                "id": r["grid_id"],
                "geometry": geom_dict,
                "properties": {
                    "grid_id": r["grid_id"],
                    "land_type": r["land_type"],
                    "land_code": r["land_code"] or "",
                    "min_lng": r["min_lng"],
                    "min_lat": r["min_lat"],
                    "max_lng": r["max_lng"],
                    "max_lat": r["max_lat"],
                },
            })

        return {"type": "FeatureCollection", "features": features}
    finally:
        conn.close()


def get_grid_indicators(grid_ids: list[str]) -> dict[str, dict[str, Any]]:
    """返回指定网格的完整指标体系。

    查询 land_grid_indicators 表，按 grid_id 返回指标 dict。
    不 JOIN land_grid_L0——调用方若需空间信息，自行查 L0。

    Args:
        grid_ids: 待查询的 grid_id 列表。

    Returns:
        dict: { "grid_1": {"NLD": 0.85, "YLD": 0.72, ...}, ... }
              不存在的 grid_id 不出现在返回结果中。
    """
    if not grid_ids:
        return {}

    conn = get_connection()
    try:
        placeholders = ",".join("?" for _ in grid_ids)
        rows = conn.execute(
            f"SELECT * FROM land_grid_indicators WHERE grid_id IN ({placeholders})",
            grid_ids,
        ).fetchall()
        return {r["grid_id"]: dict(r) for r in rows}
    finally:
        conn.close()


_SCENARIO_FIELDS: dict[str, str] = {
    "智能制造": "ZNZZ",
    "物流仓储": "WLCC",
    "医疗器械": "YLQX",
    "食品加工": "SPJG",
}


def get_scenario_scores(grid_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    """返回四大场景适配度排序结果。

    对给定的 grid_ids，分别按 ZNZZ / WLCC / YLQX / SPJG 降序排列，
    返回每个场景的 Top N 网格及其得分。

    Args:
        grid_ids: 待评估的网格列表。

    Returns:
        dict: {
            "智能制造": [{"grid_id": "...", "score": 0.85}, ...],
            "物流仓储": [{"grid_id": "...", "score": 0.78}, ...],
            "医疗器械": [{"grid_id": "...", "score": 0.72}, ...],
            "食品加工": [{"grid_id": "...", "score": 0.65}, ...],
        }
        每类最多返回 10 条。
    """
    if not grid_ids:
        return {k: [] for k in _SCENARIO_FIELDS}

    conn = get_connection()
    try:
        placeholders = ",".join("?" for _ in grid_ids)
        result: dict[str, list[dict[str, Any]]] = {}
        for scenario, field in _SCENARIO_FIELDS.items():
            rows = conn.execute(
                f"""SELECT grid_id, {field} AS score
                    FROM land_grid_indicators
                    WHERE grid_id IN ({placeholders}) AND {field} IS NOT NULL
                    ORDER BY {field} DESC LIMIT 10""",
                grid_ids,
            ).fetchall()
            result[scenario] = [
                {"grid_id": r["grid_id"], "score": round(r["score"], 3)}
                for r in rows
            ]
        return result
    finally:
        conn.close()


def get_grid_stats(grid_ids: list[str]) -> dict[str, Any]:
    """批量查询指定 grid_id 列表的聚合统计。

    自动识别 grid_id 所属层级（L0-L5），查对应聚合表。
    """
    if not grid_ids:
        return {
            "grid_count": 0, "total_area_sqm": 0.0,
            "total_area_mu": 0.0, "land_type_distribution": {},
        }

    # 从第一个 grid_id 推断表名
    table_name = "land_grid_L0"
    for level in range(5, 0, -1):
        if f"_L{level}_" in grid_ids[0]:
            table_name = f"land_grid_L{level}"
            break

    conn = get_connection()
    try:
        placeholders = ",".join("?" for _ in grid_ids)

        if table_name == "land_grid_L0":
            row = conn.execute(
                f"""
                SELECT COUNT(*) AS grid_count, COALESCE(SUM(area_sqm), 0) AS total_area_sqm
                FROM land_grid_L0 WHERE grid_id IN ({placeholders})
                """, grid_ids,
            ).fetchone()
            dist_rows = conn.execute(
                f"""
                SELECT land_type, COUNT(*) AS cnt
                FROM land_grid_L0 WHERE grid_id IN ({placeholders})
                GROUP BY land_type ORDER BY cnt DESC
                """, grid_ids,
            ).fetchall()
            total_sqm = float(row["total_area_sqm"] or 0)
            land_dist = {r["land_type"]: r["cnt"] for r in dist_rows}
        else:
            # 聚合表：直接用已聚合的 area_sqm + land_type_top3
            row = conn.execute(
                f"""
                SELECT COUNT(*) AS grid_count,
                       COALESCE(SUM(area_sqm), 0) AS total_area_sqm,
                       land_type, land_type_top3
                FROM {table_name} WHERE grid_id IN ({placeholders})
                """, grid_ids,
            ).fetchone()
            total_sqm = float(row["total_area_sqm"] or 0)
            land_dist = {}
            if row["land_type_top3"]:
                try:
                    import json
                    top3 = json.loads(row["land_type_top3"])
                    land_dist = {t["name"]: int(t["pct"] * 100) for t in top3}
                except (json.JSONDecodeError, KeyError, TypeError):
                    land_dist = {row["land_type"]: 1} if row["land_type"] else {}

        return {
            "grid_count": row["grid_count"],
            "total_area_sqm": total_sqm,
            "total_area_mu": round(total_sqm / _SQM_PER_MU, 1),
            "land_type_distribution": land_dist,
        }
    finally:
        conn.close()
