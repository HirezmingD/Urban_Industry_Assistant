"""
generate_grid.py — 一次性渔网预处理脚本

执行环境: D:\TOOLS\MiniConda\envs\agent_gpu_py311\python.exe
执行方式: D:\TOOLS\MiniConda\envs\agent_gpu_py311\python.exe preprocessing/generate_grid.py
预计耗时: 1-2 分钟 (不含栅格 zonal stats)

在桐庐行政区划边界内生成 100m×100m 规则渔网，
与土地利用数据做空间连接，赋予用地属性，
写入 SQLite land_grid 表 + 建 R-tree 索引 + 导出精简 GeoJSON。

基于 specs/arch/grid_preprocessing.md 伪代码实现。
"""
from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ========== 配置 ==========
GRID_SIZE = 100  # 米

# 桐庐位于 EPSG:4527（CGCS2000 3度带，中央经线 120°）
TARGET_CRS = "EPSG:4527"
WGS84 = "EPSG:4326"

# 输入路径
BOUNDARY_PATH = "data/processed/tonglu_boundary.geojson"
LANDUSE_PATH = "data/processed/tonglu_landuse.geojson"

# 输出路径
DB_PATH = "db/uia.db"
LIGHT_OUTPUT = "data/processed/grid_light.geojson"

# 土地利用 → 用地类型大类映射
LAND_TYPE_L1_MAP: dict[str, str] = {
    "工业用地": "产业用地",
    "物流仓储用地": "产业用地",
    "商业用地": "商业用地",
    "城镇住宅用地": "居住用地",
    "农村宅基地": "居住用地",
    "水田": "农用地",
    "旱地": "农用地",
    "果园": "农用地",
    "茶园": "农用地",
    "乔木林地": "林地",
    "竹林地": "林地",
    "灌木林地": "林地",
    "河流水面": "水域",
    "水库水面": "水域",
    "坑塘水面": "水域",
    "公路用地": "交通用地",
    "铁路用地": "交通用地",
    "机关团体新闻出版用地": "公服用地",
    "科教文卫用地": "公服用地",
}


def main(
    grid_size: int = 100,
    skip_landuse: bool = False,
) -> None:
    """渔网预处理主入口。

    Args:
        grid_size: 渔网边长（米），默认 100，降级时可改为 200。
        skip_landuse: 跳过土地利用空间连接。
    """
    t0 = time.time()

    # ---- 检查输入文件 ----
    if not Path(BOUNDARY_PATH).exists():
        print(f"[ERROR] 边界文件不存在: {BOUNDARY_PATH}")
        sys.exit(2)
    if not skip_landuse and not Path(LANDUSE_PATH).exists():
        print(f"[WARN] 土地利用文件不存在: {LANDUSE_PATH}，将跳过空间连接")
        skip_landuse = True

    # ---- 延迟导入（避免未安装依赖时 import 报错） ----
    try:
        import geopandas as gpd
        import pandas as pd
        from shapely.geometry import box
    except ImportError as e:
        print(f"[ERROR] 缺少依赖: {e}。请先 pip install geopandas shapely pyproj")
        sys.exit(2)

    # ---- 1. 加载桐庐行政区划边界 ----
    print(f"[1/6] 加载桐庐行政区划边界: {BOUNDARY_PATH}")
    boundary = gpd.read_file(BOUNDARY_PATH)
    if boundary.crs is None:
        boundary = boundary.set_crs(WGS84)
    boundary_proj = boundary.to_crs(TARGET_CRS)
    bounds = boundary_proj.total_bounds
    print(f"  投影边界 (CGCS2000): {bounds}")
    print(f"  原始边界 (WGS84): {boundary.to_crs(WGS84).total_bounds}")

    # 打印实际 WGS84 外接矩形（便于和洲手动更新 config.TONGLU_BBOX）
    wgs84_bounds = boundary.to_crs(WGS84).total_bounds
    print(f"  ★ 实际 WGS84 外接矩形: ({wgs84_bounds[0]:.4f}, {wgs84_bounds[1]:.4f}, "
          f"{wgs84_bounds[2]:.4f}, {wgs84_bounds[3]:.4f})")
    print(f"    建议更新 config.py TONGLU_BBOX 为以上精确值")

    # ---- 2. 生成规则渔网 ----
    print(f"[2/6] 生成 {grid_size}m×{grid_size}m 规则渔网...")
    min_x = (bounds[0] // grid_size) * grid_size
    min_y = (bounds[1] // grid_size) * grid_size
    max_x = ((bounds[2] // grid_size) + 1) * grid_size
    max_y = ((bounds[3] // grid_size) + 1) * grid_size

    cols = int((max_x - min_x) / grid_size)
    rows = int((max_y - min_y) / grid_size)
    print(f"  网格维度: {rows} 行 × {cols} 列, 共 {rows * cols} 个候选格")

    cells: list[dict] = []
    for r in range(rows):
        for c in range(cols):
            x0 = min_x + c * grid_size
            y0 = min_y + r * grid_size
            x1 = x0 + grid_size
            y1 = y0 + grid_size
            cells.append({
                "grid_id": f"grid_{r}_{c}",
                "row": r,
                "col": c,
                "geometry": box(x0, y0, x1, y1),
            })
    grid_gdf = gpd.GeoDataFrame(cells, crs=TARGET_CRS)
    print(f"  生成 {len(grid_gdf)} 个候选渔网单元")

    # ---- 3. 过滤：仅保留落在桐庐边界内的渔网 ----
    print("[3/6] 过滤：仅保留落在桐庐边界内的渔网单元...")
    grid_clipped = gpd.sjoin(
        grid_gdf, boundary_proj[["geometry"]],
        how="inner", predicate="intersects",
    )
    if "index_right" in grid_clipped.columns:
        grid_clipped = grid_clipped.drop(columns=["index_right"])
    grid_clipped = grid_clipped[~grid_clipped.index.duplicated()]
    print(f"  保留 {len(grid_clipped)} 个有效渔网单元 "
          f"(丢弃 {len(grid_gdf) - len(grid_clipped)} 个)")

    # ---- 4. 空间连接：赋予用地属性 ----
    if not skip_landuse:
        print("[4/6] 空间连接：渔网单元格 ← 赋予用地属性...")
        landuse = gpd.read_file(LANDUSE_PATH)
        if landuse.crs is None:
            landuse = landuse.set_crs(WGS84)
        landuse_proj = landuse.to_crs(TARGET_CRS)

        joined = gpd.sjoin(
            grid_clipped,
            landuse_proj[["geometry"] + [
                c for c in ["land_type", "ownership", "town"]
                if c in landuse_proj.columns
            ]],
            how="left", predicate="intersects",
        )

        grid_attrs = joined.groupby("grid_id").first().reset_index()

        # 标注混合用地
        multi_hit = joined.groupby("grid_id").size()
        grid_attrs["mixed_type"] = grid_attrs["grid_id"].map(
            lambda gid: "含混合用地" if multi_hit.get(gid, 1) > 1 else None
        )
        print(f"  空间连接完成: {len(grid_attrs)} 个渔网单元已赋予用地属性")
    else:
        print("[4/6] 跳过空间连接（--skip-landuse）")
        grid_attrs = grid_clipped.copy()
        grid_attrs["land_type"] = "未分类"
        grid_attrs["ownership"] = "未知"
        grid_attrs["town"] = "未知"
        grid_attrs["mixed_type"] = None

    # ---- 5. 写入 SQLite + 建索引 ----
    print("[5/6] 转换为 WGS84 坐标并写入 SQLite...")
    grid_wgs84 = grid_attrs.to_crs(WGS84)
    grid_wgs84["min_lng"] = grid_wgs84.geometry.bounds.minx
    grid_wgs84["min_lat"] = grid_wgs84.geometry.bounds.miny
    grid_wgs84["max_lng"] = grid_wgs84.geometry.bounds.maxx
    grid_wgs84["max_lat"] = grid_wgs84.geometry.bounds.maxy

    # 确保 db 目录存在
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)

    # 建表（幂等）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS land_grid (
            grid_id       TEXT PRIMARY KEY,
            min_lng       REAL NOT NULL,
            min_lat       REAL NOT NULL,
            max_lng       REAL NOT NULL,
            max_lat       REAL NOT NULL,
            land_type     TEXT NOT NULL,
            land_code     TEXT NOT NULL DEFAULT '',
            area_sqm      REAL NOT NULL,
            ownership     TEXT NOT NULL,
            town          TEXT NOT NULL,
            mixed_type    TEXT,
            nl_mean       REAL,
            ndvi_mean     REAL,
            pm25_mean     REAL,
            geometry      BLOB NOT NULL,
            extras        TEXT DEFAULT '{}'
        )
    """)

    # 批量插入
    rows = []
    for _, row in grid_wgs84.iterrows():
        rows.append((
            row["grid_id"],
            row["min_lng"], row["min_lat"], row["max_lng"], row["max_lat"],
            row.get("land_type", "未分类"),
            "",  # land_code（预处理脚本不填充，由脚本外逻辑处理）
            grid_size * grid_size,
            row.get("ownership", "未知"),
            row.get("town", "未知"),
            row.get("mixed_type"),
            None, None, None,  # nl_mean, ndvi_mean, pm25_mean
            row.geometry.wkb,
            "{}",
        ))

    conn.executemany(
        """INSERT OR REPLACE INTO land_grid
           (grid_id, min_lng, min_lat, max_lng, max_lat,
            land_type, land_code, area_sqm, ownership, town, mixed_type,
            nl_mean, ndvi_mean, pm25_mean, geometry, extras)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    conn.commit()
    print(f"  SQLite 写入完成: {len(rows)} 行")

    # R-tree 索引
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS land_grid_rtree USING rtree(
            id, min_lng, max_lng, min_lat, max_lat
        )
    """)
    # 清空旧索引数据（若存在）
    conn.execute("DELETE FROM land_grid_rtree")
    conn.execute("""
        INSERT INTO land_grid_rtree(rowid, min_lng, max_lng, min_lat, max_lat)
        SELECT rowid, min_lng, max_lng, min_lat, max_lat FROM land_grid
    """)

    # 常规索引
    conn.execute("CREATE INDEX IF NOT EXISTS idx_land_grid_town ON land_grid(town)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_land_grid_land_type ON land_grid(land_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_land_grid_ownership ON land_grid(ownership)")
    conn.commit()
    conn.close()
    print("  R-tree 索引 + 常规索引创建完成")

    # ---- 6. 导出精简 GeoJSON ----
    print("[6/6] 导出精简 GeoJSON（供前端九宫格缓存）...")
    Path(LIGHT_OUTPUT).parent.mkdir(parents=True, exist_ok=True)
    light_gdf = grid_wgs84[["grid_id", "land_type", "geometry"]].copy()
    light_gdf["land_type_l1"] = (
        light_gdf["land_type"].map(LAND_TYPE_L1_MAP).fillna("其他用地")
    )
    light_gdf.to_file(LIGHT_OUTPUT, driver="GeoJSON")
    print(f"  精简 GeoJSON 已导出: {LIGHT_OUTPUT}")

    # ---- 总结 ----
    elapsed = time.time() - t0
    print(f"\n{'='*50}")
    print(f"  预处理完成")
    print(f"  有效渔网单元: {len(grid_wgs84)} 个")
    print(f"  网格边长: {grid_size}m")
    print(f"  总耗时: {elapsed:.1f} 秒")
    print(f"  输出: {DB_PATH} (land_grid 表 + R-tree)")
    print(f"       {LIGHT_OUTPUT} (前端缓存)")

    # 验证
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute("SELECT COUNT(*) FROM land_grid").fetchone()[0]
    print(f"  验证: land_grid 表共 {count} 行")
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="桐庐渔网预处理脚本")
    parser.add_argument("--grid-size", type=int, default=100,
                        help="渔网边长（米），降级时可改为 200")
    parser.add_argument("--skip-landuse", action="store_true",
                        help="土地利用数据缺失时跳过空间连接")
    args = parser.parse_args()
    main(grid_size=args.grid_size, skip_landuse=args.skip_landuse)
