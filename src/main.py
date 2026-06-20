"""
FastAPI 应用入口。

挂载 4 个子路由（map / agent / enterprise / evomap），
启动时初始化数据库、seed 虚构企业、启动 EvoMap 心跳（凭证就绪时）。
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src import config, database
from src.services.evo_service import evo_client, get_evolution_stats

logger = logging.getLogger(__name__)

# ============================================================
# 企业 seed 数据
# ============================================================

_SEED_ENTERPRISES: list[dict] = [
    {
        "id": "ENT_001",
        "name": "桐江精密科技有限公司",
        "industry": "精密制造",
        "industry_code": "C34",
        "employee_count": 180,
        "annual_revenue": "1.2亿",
        "space_demand": json.dumps({
            "min_area_sqm": 5000, "max_area_sqm": 10000,
            "preferred_town": "城镇四", "fallback_towns": ["城镇二", "城镇五"],
        }, ensure_ascii=False),
        "requirements": json.dumps({
            "water_supply": True, "electricity_level": "工业用电",
            "waste_treatment": False, "transport_access": "需货车通行",
        }, ensure_ascii=False),
        "priority_tags": json.dumps(["精密制造", "智能装备"], ensure_ascii=False),
    },
    {
        "id": "ENT_002",
        "name": "主要河流智能装备有限公司",
        "industry": "智能装备",
        "industry_code": "C35",
        "employee_count": 320,
        "annual_revenue": "8.5亿",
        "space_demand": json.dumps({
            "min_area_sqm": 20000, "max_area_sqm": 40000,
            "preferred_town": "街道一", "fallback_towns": ["街道三"],
        }, ensure_ascii=False),
        "requirements": json.dumps({
            "water_supply": True, "electricity_level": "高压工业用电",
            "waste_treatment": True, "transport_access": "需临近高速口",
        }, ensure_ascii=False),
        "priority_tags": json.dumps(["智能装备", "龙头型企业"], ensure_ascii=False),
    },
    {
        "id": "ENT_003",
        "name": "城关街道生物医药科技有限公司",
        "industry": "大健康",
        "industry_code": "C27",
        "employee_count": 95,
        "annual_revenue": "6000万",
        "space_demand": json.dumps({
            "min_area_sqm": 3000, "max_area_sqm": 8000,
            "preferred_town": "城镇一", "fallback_towns": ["街道一"],
        }, ensure_ascii=False),
        "requirements": json.dumps({
            "water_supply": True, "electricity_level": "工业用电",
            "waste_treatment": True, "transport_access": "不限",
        }, ensure_ascii=False),
        "priority_tags": json.dumps(["大健康", "生物医药"], ensure_ascii=False),
    },
    {
        "id": "ENT_004",
        "name": "韵通物流科技有限公司",
        "industry": "快递物流",
        "industry_code": "G60",
        "employee_count": 500,
        "annual_revenue": "20亿",
        "space_demand": json.dumps({
            "min_area_sqm": 50000, "max_area_sqm": 100000,
            "preferred_town": "街道三", "fallback_towns": ["街道一", "城镇二"],
        }, ensure_ascii=False),
        "requirements": json.dumps({
            "water_supply": True, "electricity_level": "工业用电",
            "waste_treatment": False, "transport_access": "必须临近高速/高铁",
        }, ensure_ascii=False),
        "priority_tags": json.dumps(["快递物流", "龙头企业", "超大"], ensure_ascii=False),
    },
    {
        "id": "ENT_005",
        "name": "乡镇一农产品深加工有限公司",
        "industry": "农产品深加工",
        "industry_code": "C13",
        "employee_count": 40,
        "annual_revenue": "2000万",
        "space_demand": json.dumps({
            "min_area_sqm": 2000, "max_area_sqm": 5000,
            "preferred_town": "城镇五", "fallback_towns": ["城镇四"],
        }, ensure_ascii=False),
        "requirements": json.dumps({
            "water_supply": True, "electricity_level": "普通工业用电",
            "waste_treatment": True, "transport_access": "需货车通行",
        }, ensure_ascii=False),
        "priority_tags": json.dumps(["农产品加工", "小微企业"], ensure_ascii=False),
    },
    {
        "id": "ENT_006",
        "name": "乡镇四文创设计工作室",
        "industry": "文创设计",
        "industry_code": "R87",
        "employee_count": 12,
        "annual_revenue": "300万",
        "space_demand": json.dumps({
            "min_area_sqm": 200, "max_area_sqm": 800,
            "preferred_town": "乡镇一", "fallback_towns": ["城镇四"],
        }, ensure_ascii=False),
        "requirements": json.dumps({
            "water_supply": False, "electricity_level": "商业用电",
            "waste_treatment": False, "transport_access": "不限",
        }, ensure_ascii=False),
        "priority_tags": json.dumps(["文创", "微企业"], ensure_ascii=False),
    },
    {
        "id": "ENT_007",
        "name": "中国东南某县云数信息技术有限公司",
        "industry": "数字经济",
        "industry_code": "I65",
        "employee_count": 25,
        "annual_revenue": "800万",
        "space_demand": json.dumps({
            "min_area_sqm": 300, "max_area_sqm": 1000,
            "preferred_town": "街道三", "fallback_towns": ["街道一"],
        }, ensure_ascii=False),
        "requirements": json.dumps({
            "water_supply": False, "electricity_level": "商业用电",
            "waste_treatment": False, "transport_access": "不限",
        }, ensure_ascii=False),
        "priority_tags": json.dumps(["数字经济", "小微企业"], ensure_ascii=False),
    },
    {
        "id": "ENT_008",
        "name": "主要河流新能源科技有限公司",
        "industry": "新能源",
        "industry_code": "C38",
        "employee_count": 150,
        "annual_revenue": "3.5亿",
        "space_demand": json.dumps({
            "min_area_sqm": 10000, "max_area_sqm": 20000,
            "preferred_town": "城镇二", "fallback_towns": ["城镇四", "街道一"],
        }, ensure_ascii=False),
        "requirements": json.dumps({
            "water_supply": True, "electricity_level": "高压工业用电",
            "waste_treatment": True, "transport_access": "需货车通行",
        }, ensure_ascii=False),
        "priority_tags": json.dumps(["新能源", "绿色经济"], ensure_ascii=False),
    },
    {
        "id": "ENT_009",
        "name": "中国东南某县南部家居制造有限公司",
        "industry": "家居制造",
        "industry_code": "C21",
        "employee_count": 80,
        "annual_revenue": "5000万",
        "space_demand": json.dumps({
            "min_area_sqm": 4000, "max_area_sqm": 8000,
            "preferred_town": "城镇四", "fallback_towns": ["城镇五"],
        }, ensure_ascii=False),
        "requirements": json.dumps({
            "water_supply": True, "electricity_level": "工业用电",
            "waste_treatment": True, "transport_access": "需货车通行",
        }, ensure_ascii=False),
        "priority_tags": json.dumps(["家居制造", "中小企业"], ensure_ascii=False),
    },
    {
        "id": "ENT_010",
        "name": "中部纺织服饰有限公司",
        "industry": "纺织服装",
        "industry_code": "C17",
        "employee_count": 200,
        "annual_revenue": "1.5亿",
        "space_demand": json.dumps({
            "min_area_sqm": 6000, "max_area_sqm": 12000,
            "preferred_town": "城镇二", "fallback_towns": ["城镇四"],
        }, ensure_ascii=False),
        "requirements": json.dumps({
            "water_supply": True, "electricity_level": "工业用电",
            "waste_treatment": True, "transport_access": "需货车通行",
        }, ensure_ascii=False),
        "priority_tags": json.dumps(["纺织服装", "传统产业", "限制新供地"], ensure_ascii=False),
    },
    {
        "id": "ENT_011",
        "name": "桐江化工新材料有限公司",
        "industry": "化工",
        "industry_code": "C26",
        "employee_count": 65,
        "annual_revenue": "7000万",
        "space_demand": json.dumps({
            "min_area_sqm": 8000, "max_area_sqm": 15000,
            "preferred_town": "城镇五", "fallback_towns": [],
        }, ensure_ascii=False),
        "requirements": json.dumps({
            "water_supply": True, "electricity_level": "高压工业用电",
            "waste_treatment": True, "transport_access": "需货车通行",
        }, ensure_ascii=False),
        "priority_tags": json.dumps(["化工", "限制类", "高排放"], ensure_ascii=False),
    },
    {
        "id": "ENT_012",
        "name": "中国东南某县味鼎餐饮管理有限公司",
        "industry": "餐饮",
        "industry_code": "H62",
        "employee_count": 8,
        "annual_revenue": "80万",
        "space_demand": json.dumps({
            "min_area_sqm": 100, "max_area_sqm": 300,
            "preferred_town": "街道一", "fallback_towns": ["街道三"],
        }, ensure_ascii=False),
        "requirements": json.dumps({
            "water_supply": True, "electricity_level": "商业用电",
            "waste_treatment": True, "transport_access": "不限",
        }, ensure_ascii=False),
        "priority_tags": json.dumps(["餐饮", "微型企业"], ensure_ascii=False),
    },
]


def _seed_enterprises_if_empty() -> None:
    """检查 enterprises 表，为空时插入虚构企业种子数据。"""
    conn = database.get_connection()
    try:
        count = conn.execute("SELECT COUNT(*) FROM enterprises").fetchone()[0]
        if count > 0:
            return

        conn.executemany(
            """
            INSERT INTO enterprises
                (id, name, industry, industry_code, employee_count,
                 annual_revenue, space_demand, requirements, priority_tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    ent["id"], ent["name"], ent["industry"], ent["industry_code"],
                    ent["employee_count"], ent["annual_revenue"],
                    ent["space_demand"], ent["requirements"], ent["priority_tags"],
                )
                for ent in _SEED_ENTERPRISES
            ],
        )
        conn.commit()
        print(f"[startup] 已插入 {len(_SEED_ENTERPRISES)} 家虚构企业种子数据")
    finally:
        conn.close()


# ============================================================
# FastAPI 应用
# ============================================================

app = FastAPI(title="Urban_Industry_Assistant", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载路由
from src.api.map_routes import router as map_router      # noqa: E402
from src.api.agent_routes import router as agent_router  # noqa: E402
from src.api.evo_routes import router as evo_router      # noqa: E402
from src.api.ent_routes import router as ent_router      # noqa: E402
from src.api.config_routes import router as config_router  # noqa: E402

app.include_router(map_router)
app.include_router(agent_router)
app.include_router(evo_router)
app.include_router(ent_router)
app.include_router(config_router)


# ============================================================
# 启动事件
# ============================================================

@app.on_event("startup")
async def startup() -> None:
    """应用启动：初始化数据库、seed 企业、启动 EvoMap 心跳（如凭证就绪）。"""
    # 确保目录存在
    Path("static").mkdir(exist_ok=True)
    Path("data/tiles").mkdir(parents=True, exist_ok=True)

    database.init_db()
    _seed_enterprises_if_empty()

    # 尝试恢复 OAuth2 token（如 SQLite 中有持久化的 refresh_token）
    from src.services.oauth_client import oauth_client as _oauth_startup
    _oauth_startup._restore_tokens()

    if config.EVOMAP_NODE_ID and config.EVOMAP_NODE_SECRET:
        asyncio.create_task(evo_client.start_heartbeat_loop())
        print("[startup] EvoMap 心跳后台任务已启动")
    else:
        print("[startup] EvoMap 凭证未就绪，跳过心跳后台任务")


# ============================================================
# 静态文件挂载（startup 后才挂载，避免目录不存在报错）
# ============================================================

app.mount("/static", StaticFiles(directory="static", html=True), name="static")
try:
    app.mount("/data/tiles", StaticFiles(directory="data/tiles"), name="tiles")
except Exception:
    pass  # tiles 目录可能为空或不存在


# ============================================================
# 根路径 + 健康检查
# ============================================================

@app.get("/")
async def root() -> dict:
    """根路径：返回项目基本信息。"""
    return {
        "name": "Urban_Industry_Assistant",
        "version": "1.0.0",
        "docs": "/docs",
        "description": "县域产业用地智能评估 Agent",
    }


@app.get("/health")
async def health() -> dict:
    """健康检查。

    Returns:
        dict: 含 status / db / evomap_online。
    """
    db_ok = False
    try:
        conn = database.get_connection()
        conn.execute("SELECT 1")
        conn.close()
        db_ok = True
    except Exception:
        pass

    evo_online = False
    try:
        evo_status = await evo_client.status()
        evo_online = evo_status.get("online", False)
    except Exception:
        pass

    return {
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
        "evomap_online": evo_online,
    }
