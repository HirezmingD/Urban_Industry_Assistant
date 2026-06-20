"""
渔网指标体系 Shapefile → SQLite 导入管线。

输入: tonglu_data/渔网最终指标/Tonglu_grid_SD_POI_RASTER_SCORE_CN.*
输出: land_grid_indicators 表（全量替换）

使用 pyshp 读取 DBF 属性，批量 INSERT 到 SQLite。
容错策略：编码 fallback、字段缺失补 NULL、grid_id 不匹配跳过。
"""
from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from pathlib import Path
from typing import Any

import shapefile

# 项目根目录
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.database import get_connection, init_db

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ============================================================
# 预期字段列表（架构文档定义 74 字段 + WGBH/X_RID）
# ============================================================

_EXPECTED_INDICATOR_FIELDS: set[str] = {
    "NLD", "YLD", "ZNZZ", "WLCC", "YLQX", "SPJG",
    "BESTCY", "BESTSC", "ZHDF",
    "DLSX", "DLBM", "DLMC", "DLSL", "SFHHDL", "HHDLBM",
    "HHDLMC", "DLHHQK", "DLPD",
    "QSSX", "QSDWMC", "QSDWSL", "SFHHQSDW", "HHQSDW",
    "QSHHQK", "ZLSX", "ZLDWMC", "ZLDWSL", "SFHHZLDW",
    "HHZLDW", "ZLHHQK", "QSXT",
    "ELEV", "SLOPE", "JSYT",
    "NDVI", "STMG", "STSP", "PRECIP", "ARID", "PET", "TEMP",
    "PPFS", "ZJTBJL", "ZTBNBBH", "R_NAFLAG",
    "DIST_QY", "CNT_QY1K", "JJD",
    "DIST_JT", "CNT_JT1K", "DIST_DLFS", "CNT_DLFS1K",
    "DIST_TX", "CNT_TX1K", "JTKD",
    "DIST_GG", "CNT_GG1K", "GGZC",
    "DIST_SWZZ", "CNT_SWZZ5", "DIST_KJ", "CNT_KJ5",
    "DIST_YL", "CNT_YL5", "SHPT",
    "MGFX", "MGSP",
    "NTL", "HFP", "GDPDEN", "KFQD",
    "POPDEN", "RJJJ", "RJXT",
}


def _detect_encoding(shp_path: str) -> str:
    """尝试从 CPG 文件检测编码，否则 fallback GBK。

    Args:
        shp_path: Shapefile 路径。

    Returns:
        str: 编码名。
    """
    cpg_path = Path(shp_path).with_suffix(".cpg")
    if cpg_path.exists():
        try:
            enc = cpg_path.read_text(encoding="ascii").strip()
            logger.info("CPG 编码: %s", enc)
            return enc
        except Exception:
            pass

    # Shapefile 中 WGBH 字段格式为 grid_L0_xxx_xxx，需确认编码
    logger.info("未找到 CPG 文件，尝试 utf-8，fallback GBK")
    return "utf-8"


def extract_features_from_shapefile(
    shapefile_path: str,
    encoding: str = "utf-8",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """从 Shapefile 中提取属性字段。

    WGBH → grid_id 映射，字段名保留原始缩写。

    Args:
        shapefile_path: .shp 文件路径。
        encoding: DBF 编码（utf-8 / gbk / gb2312）。

    Returns:
        tuple: (features, stats)
            features: list of dict, 每行含 grid_id + 指标字段。
            stats: {"total_rows": int, "fields_found": list[str], "encoding_used": str}
    """
    encodings_to_try = [encoding, "gbk", "gb2312", "latin1"]

    for enc in encodings_to_try:
        try:
            reader = shapefile.Reader(shapefile_path, encoding=enc)
            field_names = [f[0] for f in reader.fields[1:]]
            _ = reader.shape(0)  # 触发一次读取确认编码
            _ = reader.record(0)
            logger.info("编码 %s 可用，字段数: %d", enc, len(field_names))
            break
        except (UnicodeDecodeError, Exception):
            if enc == encodings_to_try[-1]:
                raise RuntimeError(f"所有编码尝试失败: {encodings_to_try}")
            continue

    features: list[dict[str, Any]] = []
    total = len(reader)

    for i in range(total):
        try:
            rec = reader.record(i)
            row = dict(zip(field_names, rec))

            # WGBH（序号）→ grid_id（L0 格式: grid_{序号}）
            wgbh = row.get("WGBH", "")
            if wgbh == "" or wgbh is None:
                continue
            grid_id = f"grid_{wgbh}"

            # 提取预期字段（排除 WGBH 和 X_RID）
            indicator: dict[str, Any] = {"grid_id": grid_id}
            for f in _EXPECTED_INDICATOR_FIELDS:
                if f in row:
                    val = row[f]
                    # 处理 bytes → str（编码问题时的 fallback）
                    if isinstance(val, bytes):
                        try:
                            val = val.decode(enc)
                        except (UnicodeDecodeError, LookupError):
                            val = val.decode("gbk", errors="replace")
                    indicator[f] = val

            features.append(indicator)

            if (i + 1) % 20000 == 0:
                logger.info("  已提取 %d/%d 行...", i + 1, total)
        except Exception:
            continue

    stats = {
        "total_rows": total,
        "extracted": len(features),
        "fields_found": field_names,
        "encoding_used": enc,
    }
    return features, stats


def validate_features(
    features: list[dict[str, Any]],
) -> dict[str, Any]:
    """验证字段完整性和数据质量。

    Args:
        features: extract_features_from_shapefile 的输出。

    Returns:
        dict: 验证统计 — field_coverage / fields_missing / fields_extra /
              null_rate_by_field / grid_id_dup_count。
    """
    if not features:
        return {
            "total_rows": 0,
            "field_coverage": 0.0,
            "fields_missing": list(_EXPECTED_INDICATOR_FIELDS),
            "fields_extra": [],
            "null_rate_by_field": {},
            "grid_id_dup_count": 0,
        }

    # 字段覆盖率
    actual_fields = set(features[0].keys()) - {"grid_id"}
    fields_missing = sorted(_EXPECTED_INDICATOR_FIELDS - actual_fields)
    fields_extra = sorted(actual_fields - _EXPECTED_INDICATOR_FIELDS)
    field_coverage = len(_EXPECTED_INDICATOR_FIELDS - set(fields_missing)) / len(_EXPECTED_INDICATOR_FIELDS)

    # NULL 率
    null_rate: dict[str, float] = {}
    for f in sorted(_EXPECTED_INDICATOR_FIELDS & actual_fields):
        null_count = sum(1 for feat in features if feat.get(f) is None)
        null_rate[f] = null_count / len(features)

    # grid_id 重复
    seen: set[str] = set()
    dup_count = 0
    for feat in features:
        gid = feat.get("grid_id", "")
        if gid in seen:
            dup_count += 1
        seen.add(gid)

    return {
        "total_rows": len(features),
        "field_coverage": field_coverage,
        "fields_missing": fields_missing,
        "fields_extra": fields_extra,
        "null_rate_by_field": null_rate,
        "grid_id_dup_count": dup_count,
    }


def match_with_land_grid_L0(
    features: list[dict[str, Any]],
    db_path: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """将 features 的 grid_id 与 land_grid_L0.grid_id 做匹配。

    Args:
        features: 已提取的指标 dict 列表。
        db_path: SQLite 数据库路径。

    Returns:
        tuple: (matched_features, match_stats)
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        # 批量取 L0 的 grid_id 集合
        l0_ids = {
            r["grid_id"]
            for r in conn.execute("SELECT grid_id FROM land_grid_L0").fetchall()
        }
    finally:
        conn.close()

    matched: list[dict[str, Any]] = []
    unmatched_ids: list[str] = []

    for feat in features:
        gid = feat.get("grid_id", "")
        if gid in l0_ids:
            matched.append(feat)
        else:
            unmatched_ids.append(gid)

    match_rate = len(matched) / len(features) if features else 0.0
    return matched, {
        "total": len(features),
        "matched": len(matched),
        "unmatched": len(unmatched_ids),
        "unmatched_ids_sample": unmatched_ids[:10],
        "match_rate": match_rate,
    }


def import_to_sqlite(
    features: list[dict[str, Any]],
    db_path: str,
    batch_size: int = 1000,
) -> dict[str, Any]:
    """全量替换 land_grid_indicators 表。

    BEGIN → DELETE FROM → INSERT batches → COMMIT
    失败时 ROLLBACK 保留旧数据。

    Args:
        features: 待导入的指标 dict 列表（已匹配）。
        db_path: SQLite 数据库路径。
        batch_size: 批量 INSERT 大小。

    Returns:
        dict: {"imported": int, "batches": int, "elapsed_sec": float}
    """
    import time
    start = time.time()

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    # 确定实际字段（基于第一条记录）
    if not features:
        conn.close()
        return {"imported": 0, "batches": 0, "elapsed_sec": 0.0}

    sample = features[0]
    columns = ["grid_id"] + sorted(
        f for f in _EXPECTED_INDICATOR_FIELDS if f in sample
    )
    placeholders = ",".join("?" * len(columns))
    col_str = ",".join(columns)
    sql = f"INSERT OR REPLACE INTO land_grid_indicators ({col_str}) VALUES ({placeholders})"

    try:
        conn.execute("DELETE FROM land_grid_indicators")
        batch_count = 0
        for i in range(0, len(features), batch_size):
            batch = features[i : i + batch_size]
            tuples = [
                tuple(row.get(c) for c in columns)
                for row in batch
            ]
            conn.executemany(sql, tuples)
            batch_count += 1
            if batch_count % 10 == 0:
                logger.info("  已写入 %d/%d 行 (%d 批)...", i + len(batch), len(features), batch_count)

        conn.commit()
        elapsed = time.time() - start
        logger.info("导入完成: %d 行, %d 批, 耗时 %.1fs", len(features), batch_count, elapsed)
        return {"imported": len(features), "batches": batch_count, "elapsed_sec": elapsed}
    except Exception:
        conn.rollback()
        logger.exception("导入失败，已回滚")
        raise
    finally:
        conn.close()


# ============================================================
# CLI
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="渔网指标体系 Shapefile → SQLite 导入")
    parser.add_argument(
        "--input", "-i",
        default=str(
            _PROJECT_ROOT
            / "tonglu_data"
            / "渔网最终指标"
            / "Tonglu_grid_SD_POI_RASTER_SCORE_CN.shp"
        ),
        help="Shapefile 路径",
    )
    parser.add_argument(
        "--db", "-d",
        default=str(_PROJECT_ROOT / "db" / "uia.db"),
        help="SQLite 数据库路径",
    )
    parser.add_argument(
        "--encoding", "-e",
        default="utf-8",
        help="DBF 编码 (默认 utf-8, fallback gbk)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅验证不写入",
    )
    args = parser.parse_args()

    if not Path(args.input).exists():
        logger.error("Shapefile 不存在: %s", args.input)
        sys.exit(1)

    # 确保数据库和表已初始化
    logger.info("初始化数据库...")
    init_db()

    # Step 1: 提取
    logger.info("Step 1: 从 Shapefile 提取属性...")
    features, extract_stats = extract_features_from_shapefile(args.input, args.encoding)
    logger.info(
        "  提取完成: %d/%d 行 (编码: %s)",
        extract_stats["extracted"],
        extract_stats["total_rows"],
        extract_stats["encoding_used"],
    )

    # Step 2: 验证
    logger.info("Step 2: 字段验证...")
    validation = validate_features(features)
    logger.info("  字段覆盖率: %.1f%%", validation["field_coverage"] * 100)
    if validation["fields_missing"]:
        logger.warning("  缺失字段 (%d): %s", len(validation["fields_missing"]), validation["fields_missing"])
    if validation["fields_extra"]:
        logger.info("  额外字段 (%d): %s", len(validation["fields_extra"]), validation["fields_extra"])
    if validation["grid_id_dup_count"]:
        logger.warning("  grid_id 重复: %d", validation["grid_id_dup_count"])

    # NULL 率 Top 10
    null_items = sorted(validation["null_rate_by_field"].items(), key=lambda x: -x[1])[:10]
    if null_items:
        logger.info("  NULL 率 Top 10:")
        for f, rate in null_items:
            logger.info("    %-10s: %.1f%%", f, rate * 100)

    # Step 3: 匹配
    logger.info("Step 3: 匹配 land_grid_L0...")
    matched, match_stats = match_with_land_grid_L0(features, args.db)
    logger.info(
        "  匹配率: %.1f%% (%d/%d)",
        match_stats["match_rate"] * 100,
        match_stats["matched"],
        match_stats["total"],
    )
    if match_stats["unmatched_ids_sample"]:
        logger.warning("  未匹配 ID 样例: %s", match_stats["unmatched_ids_sample"][:5])

    # Step 4: 导入
    if args.dry_run:
        logger.info("Step 4: (dry-run) 跳过写入")
        return

    if match_stats["match_rate"] < 0.5:
        logger.error("匹配率 %.1f%% 过低 (<50%%), 中止导入", match_stats["match_rate"] * 100)
        sys.exit(1)

    logger.info("Step 4: 导入 SQLite...")
    result = import_to_sqlite(matched, args.db)
    logger.info("导入完成: %d 行, 耗时 %.1fs", result["imported"], result["elapsed_sec"])


if __name__ == "__main__":
    main()
