"""
全局配置模块。

从 .env 加载密钥与配置，暴露统一的配置常量供所有模块导入。
缺失关键配置时打印警告但不崩溃（允许仅前端运行）。
"""
import os
import sys
from pathlib import Path

# ============================================================
# .env 加载（依赖 python-dotenv）
# ============================================================
try:
    from dotenv import load_dotenv
    _ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
    if _ENV_PATH.exists():
        load_dotenv(_ENV_PATH)
except ImportError:
    pass  # python-dotenv 未安装，仅从系统环境变量读取

# ============================================================
# DeepSeek LLM 配置
# ============================================================
DEEPSEEK_API_KEY: str | None = os.getenv("DEEPSEEK_API_KEY")
"""DeepSeek API key。从 DEEPSEEK_API_KEY 环境变量读取。"""

DEEPSEEK_BASE_URL: str = os.getenv(
    "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
)
"""DeepSeek API 基础 URL。默认 https://api.deepseek.com。"""

DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
"""使用的模型名。默认 deepseek-v4-pro。"""

LLM_SEMAPHORE_LIMIT: int = 1
"""LLM 并发限制（按决议，单次只允许一个 LLM 请求）。"""

LLM_QUEUE_DEPTH: int = 10
"""LLM 请求队列深度。超出此值返回 503。"""

LLM_TIMEOUT: int = 30
"""LLM API 超时（秒）。"""

CHAT_MAX_LENGTH: int = 500
"""对话消息最大字符数。"""

CHAT_CONTEXT_TURNS: int = 10
"""保留最近 N 轮对话历史。"""

if not DEEPSEEK_API_KEY:
    print("[config] WARNING: DEEPSEEK_API_KEY not set, LLM features unavailable.")

# ============================================================
# 天地图 API 配置
# ============================================================
TIANDITU_API_KEY: str | None = os.getenv("TIANDITU_API_KEY")
"""天地图 API key。从 TIANDITU_API_KEY 环境变量读取。"""

TIANDITU_TILE_URL_TEMPLATE: str = os.getenv(
    "TIANDITU_TILE_URL_TEMPLATE",
    (
        "http://t{s}.tianditu.gov.cn/img_w/wmts"
        "?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0"
        "&LAYER=img&STYLE=default&TILEMATRIXSET=w"
        "&FORMAT=tiles&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}"
        "&tk={key}"
    ),
)
"""天地图卫星影像瓦片 URL 模板（img_w 服务，WGS84 球面墨卡托，按决议 4）。"""

if not TIANDITU_API_KEY:
    print("[config] WARNING: TIANDITU_API_KEY not set, online tiles unavailable.")

# ============================================================
# EvoMap Hub 配置
# ============================================================
EVOMAP_HUB_URL: str = os.getenv("EVOMAP_HUB_URL", "https://evomap.ai")
"""EvoMap Hub 基础 URL。"""

# === EvoMap OAuth2 开发者平台 ===
EVOMAP_OAUTH_CLIENT_ID: str = os.getenv(
    "EVOMAP_OAUTH_CLIENT_ID",
    os.getenv("EVOMAP_CLIENT_ID", ""),
)
"""EvoMap OAuth2 客户端 ID。优先新变量名，fallback 到旧 EVOMAP_CLIENT_ID。"""

EVOMAP_OAUTH_CLIENT_SECRET: str = os.getenv(
    "EVOMAP_OAUTH_CLIENT_SECRET",
    os.getenv("EVOMAP_CLIENT_SECRET", ""),
)
"""EvoMap OAuth2 客户端密钥。优先新变量名，fallback 到旧 EVOMAP_CLIENT_SECRET。"""

EVOMAP_OAUTH_REDIRECT_URI: str = os.getenv(
    "EVOMAP_OAUTH_REDIRECT_URI",
    os.getenv(
        "EVOMAP_REDIRECT_URI",
        "http://127.0.0.1:8000/api/evomap/callback",
    ),
)
"""EvoMap OAuth2 回调地址。优先新变量名，fallback 到旧 EVOMAP_REDIRECT_URI。"""


def _read_evomap_file(filename: str) -> str | None:
    """从 ~/.evomap/ 目录读取节点凭据文件。"""
    evomap_dir = Path.home() / ".evomap"
    file_path = evomap_dir / filename
    if file_path.exists():
        try:
            return file_path.read_text(encoding="utf-8").strip()
        except OSError:
            pass
    return None


EVOMAP_NODE_ID: str | None = (
    os.getenv("EVOMAP_NODE_ID") or _read_evomap_file("node_id")
)
"""EvoMap 节点 ID。优先读环境变量，否则从 ~/.evomap/node_id 读取。"""

EVOMAP_NODE_SECRET: str | None = (
    os.getenv("EVOMAP_NODE_SECRET") or _read_evomap_file("node_secret")
)
"""EvoMap 节点密钥。优先读环境变量，否则从 ~/.evomap/node_secret 读取。"""

# ============================================================
# 数据库配置
# ============================================================
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "db/uia.db")
"""SQLite 数据库文件路径。默认 db/uia.db（相对于项目根目录）。"""

# ============================================================
# 数据目录配置
# ============================================================
_ProjectRoot = Path(__file__).resolve().parent.parent

DATA_DIR: str = os.getenv("DATA_DIR", str(_ProjectRoot / "data"))
"""数据根目录。"""

PROCESSED_DATA_DIR: str = os.path.join(DATA_DIR, "processed")
"""处理后数据目录。"""

RAW_DATA_DIR: str = os.path.join(DATA_DIR, "raw")
"""原始数据目录（只读拷贝）。"""

TILES_DIR: str = os.path.join(DATA_DIR, "tiles")
"""离线瓦片存储目录。data/tiles/{z}/{x}/{y}.png。"""

# ============================================================
# 中国东南某县地理边界
# ============================================================
# 实际值由数据预处理阶段精确推算（从 XZQ 图层外接矩形）
# 当前为预估值
TONGLU_BBOX: tuple[float, float, float, float] = (
    119.16,   # min_lng
    29.58,    # min_lat
    119.80,   # max_lng
    30.12,    # max_lat
)
"""中国东南某县域外接矩形 (min_lng, min_lat, max_lng, max_lat)，WGS84 坐标系。
注释：实际精确值由数据预处理阶段从 XZQ 图层外接矩形推算。"""

# ============================================================
# 渔网查询配置
# ============================================================
GRID_SIZE: int = 100
"""渔网单元边长（米），100m × 100m 网格。"""

BBOX_QUERY_LIMIT: int = 500
"""单次框选最多返回网格数，超出截断并在结果中标注 truncated。"""

# ============================================================
# 地图配置
# ============================================================
MAP_ZOOM_MIN: int = 10
MAP_ZOOM_MAX: int = 18
MAP_ZOOM_INIT: int = 12
GRID_VISIBLE_ZOOM: int = 13
"""zoom ≥ 13 才显示渔网层。"""
