"""
数据库连接与建表模块。

使用 SQLite 内建模块管理数据库连接、建表、索引创建。
建表策略：CREATE TABLE IF NOT EXISTS，确保幂等执行。

设计思路——R-tree 两步法空间查询：
  1. 先通过 land_grid_rtree 索引快速定位候选 rowid（O(log N)）
  2. 再 JOIN land_grid 主表获取完整字段
  这样做可以避免全表扫描 ~18 万条记录，框选查询 < 100ms。
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

# ----------------------------------------------------------
# 数据库路径解析（基于 config 或直接构造）
# ----------------------------------------------------------
try:
    from src.config import DATABASE_PATH
except ImportError:
    # 兜底：从项目根目录拼接
    _ROOT = Path(__file__).resolve().parent.parent
    DATABASE_PATH = str(_ROOT / "db" / "uia.db")


def _resolve_db_path() -> str:
    """将相对路径转为项目根目录下的绝对路径。"""
    p = Path(DATABASE_PATH)
    if p.is_absolute():
        return str(p)
    root = Path(__file__).resolve().parent.parent
    return str(root / p)


def get_connection() -> sqlite3.Connection:
    """获取数据库连接。

    每个请求创建一个新连接（线程安全）。
    启用 WAL 模式（并发友好）、外键约束、R-tree 扩展。

    Returns:
        sqlite3.Connection: 已配置的数据库连接。
    """
    db_path = _resolve_db_path()
    # 确保父目录存在
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    # 尝试启用 R-tree 扩展（SQLite 标准发行自带）
    try:
        conn.enable_load_extension(True)
        # rtree 模块在 Windows 上通常名为 'rtree' 或已内建
        conn.load_extension("rtree" if sys.platform != "win32" else "rtree")
    except (sqlite3.OperationalError, AttributeError):
        # R-tree 可能已内建或不可用（不影响核心功能）
        pass

    return conn


def init_db() -> None:
    """初始化数据库：创建所有表和索引（幂等，可重复执行）。

    建表顺序：
      1. land_grid_L0 — 100m 原始渔网
      2. land_grid_L0_rtree — R-tree 空间索引
      3. land_grid_L1-L5 — 聚合表（3200m→200m）
      4. enterprises — 企业画像表
      5. evaluations — 评估记录表（自进化经验池）
      6. evomap_capsules — Capsule 缓存表
      7. interactions — 交互日志表

    迁移（V1.0→V1.1）：如 land_grid 表存在且 land_grid_L0 不存在，执行重命名。
    """
    conn = get_connection()
    try:
        # ---- 迁移：land_grid → land_grid_L0 ----
        old_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='land_grid'"
        ).fetchone()
        new_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='land_grid_L0'"
        ).fetchone()
        if old_exists and not new_exists:
            conn.execute("ALTER TABLE land_grid RENAME TO land_grid_L0")
            # R-tree 虚拟表不能用 ALTER，需重建
            old_rtree = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='land_grid_rtree'"
            ).fetchone()
            if old_rtree:
                # 把旧 R-tree 数据 INSERT 到新名
                conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS land_grid_L0_rtree USING rtree(
                        id, min_lng, max_lng, min_lat, max_lat
                    )
                """)
                try:
                    conn.execute("""
                        INSERT INTO land_grid_L0_rtree
                        SELECT id, min_lng, max_lng, min_lat, max_lat
                        FROM land_grid_rtree
                    """)
                except Exception:
                    # 可能已空，忽略
                    pass
                conn.execute("DROP TABLE IF EXISTS land_grid_rtree")
            conn.commit()
            print("[init_db] 已迁移: land_grid → land_grid_L0")

        # ---- 1. land_grid_L0 — 100m 原始渔网 ----
        conn.execute("""
            CREATE TABLE IF NOT EXISTS land_grid_L0 (
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

        # ---- 常规索引 ----
        conn.execute("CREATE INDEX IF NOT EXISTS idx_land_grid_L0_town ON land_grid_L0(town)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_land_grid_L0_land_type ON land_grid_L0(land_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_land_grid_L0_ownership ON land_grid_L0(ownership)")

        # ---- 2. land_grid_L0_rtree ----
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS land_grid_L0_rtree USING rtree(
                id, min_lng, max_lng, min_lat, max_lat
            )
        """)

        # ---- 3. L1-L5 聚合表 ----
        for level, grid_size, merge_size in [
            (1, 3200, 32), (2, 1600, 16), (3, 800, 8),
            (4, 400, 4), (5, 200, 2),
        ]:
            tn = f"land_grid_L{level}"
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {tn} (
                    grid_id              TEXT PRIMARY KEY,
                    level                INTEGER NOT NULL DEFAULT {level},
                    min_lng              REAL NOT NULL,
                    min_lat              REAL NOT NULL,
                    max_lng              REAL NOT NULL,
                    max_lat              REAL NOT NULL,
                    land_type            TEXT NOT NULL,
                    land_code            TEXT NOT NULL DEFAULT '',
                    land_type_top3       TEXT NOT NULL DEFAULT '[]',
                    area_sqm             REAL NOT NULL,
                    ownership            TEXT NOT NULL DEFAULT '{{}}',
                    town                 TEXT NOT NULL,
                    mixed_type           TEXT,
                    geometry             BLOB NOT NULL,
                    extras               TEXT DEFAULT '{{}}',
                    grid_count_original  INTEGER NOT NULL
                )
            """)
            conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{tn}_town ON {tn}(town)")
            conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{tn}_land_type ON {tn}(land_type)")
            conn.execute(f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS {tn}_rtree USING rtree(
                    id, min_lng, max_lng, min_lat, max_lat
                )
            """)

        # ---- 3. enterprises 企业画像表（批次 B 统一：对齐 Pydantic Enterprise schema） ----
        conn.execute("""
            CREATE TABLE IF NOT EXISTS enterprises (
                id              TEXT PRIMARY KEY,
                name            TEXT NOT NULL,
                industry        TEXT NOT NULL,
                industry_code   TEXT,
                employee_count  INTEGER,
                annual_revenue  TEXT,
                space_demand    TEXT,
                requirements    TEXT,
                priority_tags   TEXT,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_enterprises_industry
                ON enterprises(industry)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_enterprises_name
                ON enterprises(name)
        """)

        # ---- 4. evaluations 评估记录表 ----
        conn.execute("""
            CREATE TABLE IF NOT EXISTS evaluations (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                role             TEXT NOT NULL,
                user_message     TEXT NOT NULL,
                bbox             TEXT,
                grid_ids         TEXT,
                grid_count       INTEGER,
                total_area_mu    REAL,
                llm_response     TEXT NOT NULL,
                structured_result TEXT NOT NULL,
                user_feedback    TEXT,
                created_at       TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_evaluations_created
                ON evaluations(created_at)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_evaluations_role
                ON evaluations(role)
        """)

        # ---- 4.5. evomap_tokens OAuth2 Token 持久化表 ----
        conn.execute("""
            CREATE TABLE IF NOT EXISTS evomap_tokens (
                id            INTEGER PRIMARY KEY CHECK (id = 1),
                access_token  TEXT,
                refresh_token TEXT,
                expires_at    TEXT,
                scope         TEXT,
                updated_at    TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)

        # ---- 5. evomap_capsules Capsule 缓存表 ----
        conn.execute("""
            CREATE TABLE IF NOT EXISTS evomap_capsules (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                gene_asset_id    TEXT NOT NULL,
                capsule_asset_id TEXT NOT NULL,
                evaluation_id    INTEGER,
                summary          TEXT NOT NULL,
                confidence       REAL NOT NULL,
                publish_status   TEXT DEFAULT 'candidate',
                publish_response TEXT,
                created_at       TEXT DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (evaluation_id) REFERENCES evaluations(id)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_capsules_gene
                ON evomap_capsules(gene_asset_id)
        """)

        # ---- 5.3. gene_snapshots Gene 快照表 ----
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gene_snapshots (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                version         INTEGER NOT NULL,
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL,
                parent_id       INTEGER,
                weights         TEXT NOT NULL,
                preferences     TEXT NOT NULL DEFAULT '[]',
                context         TEXT NOT NULL,
                change_log      TEXT NOT NULL DEFAULT '{}',
                evaluation_id   INTEGER,
                capsule_id      INTEGER,
                FOREIGN KEY (parent_id) REFERENCES gene_snapshots(id),
                FOREIGN KEY (evaluation_id) REFERENCES evaluations(id),
                FOREIGN KEY (capsule_id) REFERENCES evomap_capsules(id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_gene_version ON gene_snapshots(version DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_gene_eval ON gene_snapshots(evaluation_id)")

        # ---- 5.5. land_grid_indicators 渔网74字段指标体系 ----
        conn.execute("""
            CREATE TABLE IF NOT EXISTS land_grid_indicators (
                grid_id     TEXT PRIMARY KEY,
                NLD         REAL, YLD         REAL, ZNZZ        REAL,
                WLCC        REAL, YLQX        REAL, SPJG        REAL,
                BESTCY      TEXT, BESTSC      REAL, ZHDF        REAL,
                DLSX        TEXT, DLBM        TEXT, DLMC        TEXT,
                DLSL        INTEGER, SFHHDL  TEXT, HHDLBM      TEXT,
                HHDLMC      TEXT, DLHHQK      TEXT, DLPD        REAL,
                QSSX        TEXT, QSDWMC      TEXT, QSDWSL      INTEGER,
                SFHHQSDW    TEXT, HHQSDW      TEXT, QSHHQK      TEXT,
                ZLSX        TEXT, ZLDWMC      TEXT, ZLDWSL      INTEGER,
                SFHHZLDW    TEXT, HHZLDW      TEXT, ZLHHQK      TEXT,
                QSXT        REAL,
                ELEV        REAL, SLOPE       REAL, JSYT        REAL,
                NDVI        REAL, STMG        REAL, STSP        REAL,
                PRECIP      REAL, ARID        REAL, PET         REAL,
                TEMP        REAL,
                PPFS        TEXT, ZJTBJL      REAL, ZTBNBBH     TEXT,
                R_NAFLAG    TEXT,
                DIST_QY     REAL, CNT_QY1K    INTEGER, JJD     REAL,
                DIST_JT     REAL, CNT_JT1K    INTEGER,
                DIST_DLFS   REAL, CNT_DLFS1K  INTEGER,
                DIST_TX     REAL, CNT_TX1K    INTEGER, JTKD    REAL,
                DIST_GG     REAL, CNT_GG1K    INTEGER, GGZC    REAL,
                DIST_SWZZ   REAL, CNT_SWZZ5   INTEGER,
                DIST_KJ     REAL, CNT_KJ5     INTEGER,
                DIST_YL     REAL, CNT_YL5     INTEGER, SHPT    REAL,
                MGFX        REAL, MGSP        REAL,
                NTL         REAL, HFP         REAL,
                GDPDEN      REAL, KFQD        REAL,
                POPDEN      REAL, RJJJ        REAL, RJXT       REAL,
                FOREIGN KEY (grid_id) REFERENCES land_grid_L0(grid_id)
            )
        """)

        # 场景适配度排名索引
        conn.execute("CREATE INDEX IF NOT EXISTS idx_indicators_znzz ON land_grid_indicators(ZNZZ DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_indicators_wlcc ON land_grid_indicators(WLCC DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_indicators_ylqx ON land_grid_indicators(YLQX DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_indicators_spjg ON land_grid_indicators(SPJG DESC)")

        # 综合得分排序索引
        conn.execute("CREATE INDEX IF NOT EXISTS idx_indicators_zhdf ON land_grid_indicators(ZHDF DESC)")

        # 权属协调度索引
        conn.execute("CREATE INDEX IF NOT EXISTS idx_indicators_qsxt ON land_grid_indicators(QSXT)")

        # ---- 6. interactions 交互日志表 ----
        conn.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                action_type      TEXT NOT NULL,
                grid_ids         TEXT,
                params           TEXT,
                result_count     INTEGER,
                response_time_ms INTEGER,
                created_at       TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_interactions_action
                ON interactions(action_type)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_interactions_created
                ON interactions(created_at)
        """)

        # P1-1: evomap_capsules 扩展展示字段（try/except 防列已存在）
        for col_def in [
            ("scene", "TEXT DEFAULT ''"),
            ("trigger_reason", "TEXT DEFAULT ''"),
            ("change_reason", "TEXT DEFAULT ''"),
            ("impact", "TEXT DEFAULT ''"),
        ]:
            try:
                conn.execute(f"ALTER TABLE evomap_capsules ADD COLUMN {col_def[0]} {col_def[1]}")
            except Exception:
                pass  # 列已存在

        conn.commit()
    finally:
        conn.close()


def close_connection(conn: sqlite3.Connection) -> None:
    """安全关闭数据库连接。

    Args:
        conn: 要关闭的 sqlite3.Connection 对象。
    """
    try:
        conn.close()
    except sqlite3.Error:
        pass


def seed_demo_enterprises(conn: sqlite3.Connection | None = None) -> None:
    """填充虚构企业示例数据到 enterprises 表。

    本函数为占位实现，后续批次由实现 Agent 填充 5-8 条虚构企业记录。

    Args:
        conn: 可选的数据库连接。若为 None，内部创建临时连接。
    """
    pass  # 占位，后续批次实现
