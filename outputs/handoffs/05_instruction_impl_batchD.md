# 指令：批次 D — 剩余路由 + main.py + 三处修复 + 渔网预处理脚本

**发出方**：Orchestrator
**接收方**：实现 Agent
**时间**：2026-06-19
**项目**：Urban_Industry_Assistant
**批次**：D（共 5 批次的第 4 批）

---

## 任务背景

批次 C 已完成 evo_service / ent_service / map_routes / agent_routes。本批次完成：
1. 剩余路由：`evo_routes.py` / `ent_routes.py`
2. 应用入口：`main.py`
3. 一次性预处理脚本：`preprocessing/generate_grid.py`
4. 离线瓦片下载脚本：`scripts/download_tiles.py`
5. **三处修复**（批次 C 遗留）
6. **虚构企业 seed 数据**（10-15 家覆盖全行业 + 不同规模）

完成本批次后，**整个后端可以启动并跑通**。

---

## 输入材料（必读）

1. `D:\Projects\Urban_Industry_Assistant\specs\arch\modules.md` — 第 2.12 / 2.13 / 2.14 节
2. `D:\Projects\Urban_Industry_Assistant\specs\arch\api.md` — evo/ent 路由的完整入参/出参
3. `D:\Projects\Urban_Industry_Assistant\specs\arch\grid_preprocessing.md` — 渔网预处理完整伪代码（**几乎可直接抄**）
4. `D:\Projects\Urban_Industry_Assistant\outputs\handoffs\04_addendum_arch_decisions.md` — 七项决议（决议 4 天地图、决议 6 瓦片、决议 7 渔网坐标）
5. 批次 A/B/C 已实现的所有模块

---

## 任务 0：三处修复（先做完再继续）

### 修复 1：`evo_service.get_evolution_stats()` 字段名

**当前实测返回字段名**：`radar`
**modules.md 约定**：`radar_values`

**操作**：把 `evo_service.py` 中 `get_evolution_stats()` 返回的字典里 `"radar"` 键改为 `"radar_values"`，调用方目前没有引用，安全替换。

### 修复 2：拆分 evo_service.py（356 行 → 3 文件）

按汇报建议执行：

| 拆分后文件 | 内容 |
|-----------|------|
| `src/services/evo_client.py` | `EvomapClient` 类（A2A 协议核心） |
| `src/services/evo_stats.py` | `get_evolution_stats()` 函数 |
| `src/services/evo_service.py` | 仅作为门面：`from .evo_client import EvomapClient, evo_client` + `from .evo_stats import get_evolution_stats` |

**目的**：保持外部 `from src.services import evo_service` / `from src.services.evo_service import evo_client, get_evolution_stats` 不变，向后兼容。

### 修复 3：Bearer 头空值导致非法 header

**当前症状**：`secret` 为空时拼出 `"Authorization: Bearer ***`（注意尾部空格），httpx 抛 `Illegal header value`。

**修复**：在构造 headers 前判断 `node_secret` 是否为空。

```python
def _auth_headers(self):
    if not self.node_secret:
        return {"Content-Type": "application/json"}
    return {
        "Authorization": f"Bearer ***,
        "Content-Type": "application/json",
    }
```

降级路径仍走 try/except，但避免无意义的 httpx 异常日志。

### 修复 4（额外）：`ent_service.match_enterprises()` 返回类型对齐

当前返回 `list[dict]`，按 schemas 应返回 `list[EnterpriseMatchResult]`。**保留 dict 实现**，但在函数末尾用 `[EnterpriseMatchResult.model_validate(d) for d in result_list]` 包一层 Pydantic 校验后返回。这样 service 层灵活、API 层类型严格。

---

## 任务 1：`src/api/evo_routes.py`

**职责**：EvoMap 自进化展示数据 + 状态查询 REST 端点。

```python
from fastapi import APIRouter
from src.services import evo_service
from src.schemas import EvoStatusResponse

router = APIRouter(prefix="/api/evomap", tags=["evomap"])

@router.get("/status", response_model=EvoStatusResponse)
async def evo_status(): ...
```

**关键要求**：

- `/api/evomap/status`：
  - 调 `evo_service.get_evolution_stats()` 拿本地统计
  - 调 `evo_service.evo_client.status()` 拿在线状态
  - 合并返回 `EvoStatusResponse`：
    - `online: bool`
    - `node_id: str | None`
    - `credit_balance: int | None`
    - `capsules_published: int`
    - `evolution_count: int`
    - `preference_understanding: float`
    - `radar_values: dict[str, float]`（5 维）
  - **不抛异常**：所有降级路径已在 service 层处理，路由直接 return

---

## 任务 2：`src/api/ent_routes.py`

**职责**：企业相关 REST 端点（含 P3 企业端 suggest）。

```python
from fastapi import APIRouter, Query, HTTPException
from src.services import ent_service
from src.schemas import EnterpriseMatchRequest, EnterpriseMatchResult, AgentReply

router = APIRouter(prefix="/api/enterprise", tags=["enterprise"])

@router.get("/list")
async def list_enterprises(search: str = Query("", max_length=100)): ...

@router.post("/match", response_model=list[EnterpriseMatchResult])
async def match(req: EnterpriseMatchRequest): ...

@router.post("/suggest", response_model=AgentReply)
async def suggest(
    industry: str,
    area_mu: float,
    location_prefs: list[str] | None = None,
    facility_needs: list[str] | None = None,
): ...
```

**关键要求**：

- `/api/enterprise/list`：
  - 调 `ent_service.list_enterprises(search)`
  - 返回 dict 列表（包含 id/name/industry/industry_code/employee_count/annual_revenue/priority_tags）
  - 空表 → 200 + 空列表
  - 不做 role 校验（前端目录展示用，公开数据）

- `/api/enterprise/match`：
  - 调 `ent_service.match_enterprises(enterprise_ids, role)`
  - `role != "government"` → service 层抛 `PermissionError`，路由层转 403 `{"detail": "企业匹配仅政府端可用"}`
  - 空列表请求 → 400 `{"detail": "enterprise_ids 不能为空"}`
  - `len(enterprise_ids) > 50` → 400 `{"detail": "单次最多匹配 50 家"}`

- `/api/enterprise/suggest`：
  - 调 `ent_service.match_single_enterprise(...)`
  - 标记 P3：在 docstring 顶部写 `企业端 P3 可砍接口，主路演不依赖此接口`
  - 入参缺失（如 industry 为空）→ 400
  - **本路由对前端来说是占位**，可工作但不一定演示

---

## 任务 3：`src/main.py`

**职责**：FastAPI 应用入口。

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from pathlib import Path

from src import config, database
from src.services.evo_service import evo_client
from src.api.map_routes import router as map_router
from src.api.agent_routes import router as agent_router
from src.api.evo_routes import router as evo_router
from src.api.ent_routes import router as ent_router

app = FastAPI(title="Urban_Industry_Assistant", version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

app.include_router(map_router)
app.include_router(agent_router)
app.include_router(evo_router)
app.include_router(ent_router)
```

**关键要求**：

- **启动事件**：
  ```python
  @app.on_event("startup")
  async def startup():
      database.init_db()
      _seed_enterprises_if_empty()
      # EvoMap 心跳后台任务（仅当凭证就绪时启动，否则跳过）
      if config.EVOMAP_NODE_ID and config.EVOMAP_NODE_SECRET:
          asyncio.create_task(evo_client.start_heartbeat_loop())
      else:
          print("[startup] EvoMap 凭证未就绪，跳过心跳后台任务")
  ```

- **静态文件挂载**：
  - `/static` → `static/` 目录（前端 HTML/JS/CSS，本批次目录为空，批次 E 填充）
  - `/data/tiles` → `data/tiles/` 目录（离线瓦片，可能为空，批次 D 之后由主人手动下载）
  - 如果目录不存在，启动时自动创建（避免 StaticFiles 报错）：
    ```python
    Path("static").mkdir(exist_ok=True)
    Path("data/tiles").mkdir(parents=True, exist_ok=True)
    ```

- **根路径**：
  - `GET /` → 返回 `static/index.html`（批次 E 才有，本批次返回简单提示页面 HTML 即可，避免 404）
  - 简单方案：`@app.get("/")` 返回 `{"name": "Urban_Industry_Assistant", "version": "1.0.0", "docs": "/docs"}`

- **健康检查**：
  - `GET /health` → 返回 `{"status": "ok", "db": <bool>, "evomap_online": <bool>}`
  - 用于路演现场快速确认服务是否活着

- **企业 seed 函数**：
  - 在 `main.py` 末尾或独立函数中实现 `_seed_enterprises_if_empty()`
  - 启动时检查 enterprises 表行数，为 0 时插入 12 家虚构企业
  - 字段完整对齐 Pydantic Enterprise 模型（含 JSON 字段 dumps）
  - **覆盖范围**：
    - 行业至少 10 种：精密制造、智能装备、大健康/生物医药、快递物流、农产品深加工、文创设计、数字经济、新能源、家居制造、纺织服装、化工（限制类）、餐饮（小微）
    - 规模分布：超大（年营收>10亿）×1、大（1-10亿）×2、中（5000万-1亿）×4、小（<5000万）×4、微（<500万）×1
    - 区位偏好覆盖桐庐主要乡镇：桐君街道、城南街道、分水镇、横村镇、富春江镇、瑶琳镇、莪山畲族乡
  - JSON 字段示例：
    ```python
    {
      "id": "ENT_001",
      "name": "桐江精密科技有限公司",
      "industry": "精密制造",
      "industry_code": "C34",
      "employee_count": 180,
      "annual_revenue": "1.2亿",
      "space_demand": json.dumps({
        "min_area_sqm": 5000,
        "max_area_sqm": 10000,
        "preferred_town": "分水镇",
        "fallback_towns": ["横村镇", "瑶琳镇"]
      }, ensure_ascii=False),
      "requirements": json.dumps({
        "water_supply": True,
        "electricity_level": "工业用电",
        "waste_treatment": False,
        "transport_access": "需货车通行"
      }, ensure_ascii=False),
      "priority_tags": json.dumps(["精密制造", "智能装备"], ensure_ascii=False)
    }
    ```

---

## 任务 4：`preprocessing/__init__.py` + `preprocessing/generate_grid.py`

**职责**：一次性渔网预处理脚本。

**直接参考** `specs/arch/grid_preprocessing.md` 第 1 节的完整 Python 伪代码，**几乎可以原样实现**，但必须做以下适配：

1. **输入路径调整**（按七项决议 + 项目实际结构）：
   ```python
   BOUNDARY_PATH = "data/processed/tonglu_boundary.geojson"
   LANDUSE_PATH = "data/processed/tonglu_landuse.geojson"
   DB_PATH = "db/uia.db"  # 注意：不是 data/urban_industry.db
   LIGHT_OUTPUT = "data/processed/grid_light.geojson"
   ```

2. **桐庐外接矩形落入 `config.TONGLU_BBOX`**（脚本结束后打印实际外接矩形，便于和洲手动更新 config）

3. **入参支持**：
   ```python
   if __name__ == "__main__":
       import argparse
       parser = argparse.ArgumentParser()
       parser.add_argument("--grid-size", type=int, default=100, help="渔网边长（米），降级时改为 200")
       parser.add_argument("--skip-landuse", action="store_true", help="土地利用数据缺失时跳过空间连接")
       args = parser.parse_args()
       main(grid_size=args.grid_size, skip_landuse=args.skip_landuse)
   ```

4. **写库后自动建 R-tree 索引 + 常规索引**（按 grid_preprocessing.md 步骤 5）

5. **不要在主程序中调用此脚本**，主人会手动执行：
   ```
   D:\TOOLS\MiniConda\envs\agent_gpu_py311\python.exe preprocessing/generate_grid.py
   ```

6. **数据不存在时优雅退出**：
   - 输入文件不存在 → 打印明确提示 + `sys.exit(2)`
   - 不抛裸异常

7. **依赖追加**：在 `requirements.txt` 中追加（如未存在）：
   - `geopandas>=0.14.0`
   - `shapely>=2.0.0`
   - `pyproj>=3.6.0`

---

## 任务 5：`scripts/__init__.py` + `scripts/download_tiles.py`

**职责**：离线天地图瓦片下载脚本。

**核心逻辑**：

```python
"""
download_tiles.py — 桐庐范围天地图卫星瓦片离线下载脚本
执行环境: D:\TOOLS\MiniConda\envs\agent_gpu_py311\python.exe
执行方式: python scripts/download_tiles.py --zoom-min 12 --zoom-max 15
预计耗时: 30-60 分钟（取决于天地图限速）
"""
```

**关键要求**：

- 入参：
  - `--zoom-min` 默认 12
  - `--zoom-max` 默认 15
  - `--bbox` 默认从 `config.TONGLU_BBOX` 读
  - `--key` 默认从 `config.TIANDITU_API_KEY` 读
  - `--output-dir` 默认 `data/tiles/`
- 算法：
  - 对每个 zoom level，根据 bbox 计算瓦片 x/y 范围
  - 用 `slippy_map_tile = (lng, lat, z) → (x, y)` 标准公式
  - 多线程下载（线程池 8 线程，加 `time.sleep(0.05)` 限速避免封号）
  - URL 模板：决议 4 中的天地图 `img_w` 服务
  - 已下载的瓦片跳过（按文件存在判断）
  - 失败重试 3 次，最终失败记到 `failed_tiles.txt`
- 进度展示：每 100 张打印一次 `[zoom=12] 进度 1234/5678`
- 完成后打印统计：总瓦片数、成功数、失败数、总大小、耗时

**API key 来源**：
- 优先 `--key` 命令行参数
- 否则 `config.TIANDITU_API_KEY`
- 都没有 → 提示并 `sys.exit(2)`

**注意**：本脚本主人会赛前一晚手动跑，不在主程序启动时调用。

---

## 关键约束（不可违反）

1. **Python 环境**：`D:\TOOLS\MiniConda\envs\agent_gpu_py311\python.exe`
2. **密钥管理**：全部从 `config` 读
3. **代码语言**：注释/docstring 中文
4. **不要修复任何架构遗留**（除明确列出的 4 处修复以外，不要改动批次 A/B/C 模块的其他细节）
5. **新增依赖**：geopandas / shapely / pyproj，加入 requirements.txt
6. **seed 企业数据**：仅在表为空时插入，幂等
7. **EvoMap 心跳条件启动**：凭证缺失时不启动，避免无意义日志

---

## 输出要求

- **交付物**：
  - `src/services/evo_client.py`（拆分新文件）
  - `src/services/evo_stats.py`（拆分新文件）
  - `src/services/evo_service.py`（改为门面，re-export）
  - `src/api/evo_routes.py`
  - `src/api/ent_routes.py`
  - `src/main.py`
  - `preprocessing/__init__.py`
  - `preprocessing/generate_grid.py`
  - `scripts/__init__.py`
  - `scripts/download_tiles.py`
  - `requirements.txt`（追加 geopandas/shapely/pyproj）

- **质量底线**：
  - `D:\TOOLS\MiniConda\envs\agent_gpu_py311\python.exe -c "from src.main import app; print(len(app.routes))"` 能输出路由数（≥ 8 个业务路由 + /health + /）
  - `D:\TOOLS\MiniConda\envs\agent_gpu_py311\python.exe -m uvicorn src.main:app --port 0 --log-level error` 能启动到 startup 完成（实现 Agent 可用 `uvicorn` 短启动验证）
  - 启动后 `enterprises` 表至少 12 条 seed 数据
  - 修复 1（字段名）/ 修复 3（Bearer 头）/ 修复 4（类型对齐）实测验证
  - 全文 `sk-ce4` / `48ad1b76` 无命中

---

## 汇报要求

完成后将汇报写入：`D:\Projects\Urban_Industry_Assistant\outputs\handoffs\05_report_impl_batchD.md`

汇报必须包含：
1. 11 份交付物完整路径与行数
2. **三处修复 + 一处补充** 的实测验证（特别是 `radar_values` 字段名、Bearer 头空值、Pydantic 类型对齐）
3. seed 数据插入自检（12 家企业，行业分布列表，规模分布列表）
4. uvicorn 启动验证结果（启动日志摘要 + 路由数）
5. EvoMap 心跳条件启动验证（凭证缺失场景）
6. 预处理脚本本身不必执行，但输入路径检查、入参解析、空数据降级三处必须验证逻辑正确
7. 离线瓦片脚本同上：不执行，但 dry-run 列出会下载多少张瓦片
8. 风险或遗漏（特别是企业端 P3 接口是否完整）

汇报写完后，告知主人"批次 D 已完成，请查阅"。
