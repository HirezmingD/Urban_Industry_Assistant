# 指令：批次 C — EvoMap 客户端 + 企业服务 + 地图 / 对话 API 路由

**发出方**：Orchestrator
**接收方**：实现 Agent
**时间**：2026-06-19
**项目**：Urban_Industry_Assistant
**批次**：C（共 5 批次的第 3 批）

---

## 任务背景

批次 A（数据准备）与批次 B（核心服务层）已通过质检。本批次实现：
- 后台服务层补齐：**EvoMap 客户端**、**企业匹配服务**
- 前台暴露入口：**地图路由**、**对话路由**

批次 D 才做 evo/ent 的 API 路由 + main.py，本批次先把 service 层和两个最关键的 routes 完成。

**关键约束**：4 个文件，按 architecture.md 第 8/9/10/11 步顺序实现。

---

## 输入材料（必读，按重要性排序）

1. `D:\Projects\Urban_Industry_Assistant\specs\arch\modules.md` — 4 个模块的完整函数签名（第 2.8 / 2.9 / 2.10 / 2.11 节）
2. `D:\Projects\Urban_Industry_Assistant\specs\arch\api.md` — REST API 完整定义（map / agent 相关）
3. `D:\Projects\Urban_Industry_Assistant\research\evomap_integration_plan.md` — EvoMap A2A 协议接入方案（含 Python 代码骨架）
4. `D:\Projects\Urban_Industry_Assistant\outputs\handoffs\04_addendum_arch_decisions.md` — 七项决议（决议 1 密钥管理、决议 7 渔网坐标系）
5. `D:\Projects\Urban_Industry_Assistant\specs\src\prd.md` — 用户场景与端差异
6. 批次 A/B 已实现的全部模块（`src/config.py` / `src/schemas.py` / `src/database.py` / `src/prompts/*` / `src/services/{grid,policy,eval}_service.py`）

---

## 本批次任务（4 个文件）

### 任务 1：`src/services/evo_service.py`

**职责**：EvoMap A2A 通用协议客户端 + 自进化统计聚合。

**必须实现**（按 modules.md 2.8 节）：

```python
class EvomapClient:
    def __init__(self) -> None: ...
    async def hello(self) -> dict: ...
    async def heartbeat(self) -> dict: ...
    async def start_heartbeat_loop(self, interval: int = 300) -> None: ...
    async def publish(self, gene_summary: str, capsule_summary: str,
                      confidence: float, grid_count: int) -> dict: ...
    async def status(self) -> dict: ...
    @staticmethod
    def compute_asset_id(asset: dict) -> str: ...

def get_evolution_stats() -> dict: ...
```

**关键要求**：

- **凭证读取**：
  - 优先从 `config.EVOMAP_NODE_ID` / `config.EVOMAP_NODE_SECRET` 读
  - 如未设置，再尝试读 `~/.evomap/node_id` 与 `~/.evomap/node_secret`（按官方 skill.md 约定）
  - 都没有 → `hello()` 注册时把返回的 `node_id` / `node_secret` **持久化到 `~/.evomap/`**，权限 0700 / 0600（按 skill.md 要求），Windows 上忽略权限设置但仍然写入
  - 写入失败 → 仅记 warning，不抛异常（Demo 不应因凭证持久化失败崩溃）

- **HTTP 客户端**：`httpx.AsyncClient`，base_url = `config.EVOMAP_HUB_URL`，timeout = 15s
- **鉴权**：所有非 hello 请求都加 `Authorization: Bearer {node_secret}` 头

- **`hello()` 请求体**（按 03-for-ai-agents.md，最小 payload）：
  - `protocol="gep-a2a"`, `protocol_version="1.0.0"`, `message_type="hello"`
  - `message_id` 用 `f"msg_{int(time.time()*1000)}_{secrets.token_hex(4)}"`
  - `sender_id="node_urban_industry_assistant"`（首次注册的临时 ID，hub 返回正式 node_id）
  - `timestamp` ISO8601 + `Z`
  - `payload` 必须含：
    - `capabilities`: `{"land_evaluation": "县域产业用地智能评估", "gis_analysis": "渔网+卫星图多源叠加", "industry_matching": "产业适配评分与推荐"}`
    - `model`: `config.DEEPSEEK_MODEL`（即 `deepseek-v4-pro`）
    - `gene_count`: 0
    - `capsule_count`: 0
    - `identity_doc`: "Urban_Industry_Assistant 是面向县域政府的产业用地智能评估 Agent，基于开放下载的城市存量数据、既有数据、历史积累数据，融合多维栅格数据和十五五产业政策知识库，提供产业适配评分与发展建议。"
    - `constitution`: "1. 评估结论必须基于数据，不可凭空推测。\n2. 产业发展建议必须对标当地政策规划。\n3. 风险提示优先于乐观推荐。"
  - **严禁**在 payload 出现"三调"、地块坐标、企业名等敏感词

- **`heartbeat()`**：POST `/a2a/heartbeat`，payload `{"node_id": node_id}`
- **`start_heartbeat_loop(interval=300)`**：
  - 死循环 `while True: try: await heartbeat() except: log; await asyncio.sleep(interval)`
  - 网络异常不退出循环

- **`publish()`** 构造规则：
  - Gene 必填：`type="Gene"`, `schema_version="1.5.0"`, `category="innovate"`, `signals_match`, `summary`, `model_name`, `domain="data_analysis"`, `asset_id`
  - Capsule 必填：`type="Capsule"`, `schema_version="1.5.0"`, `trigger`, `gene=<gene_asset_id>`, `summary`, `confidence`, `blast_radius`, `outcome`, `env_fingerprint`, `success_streak=1`, `model_name`, `domain`, `asset_id`
  - 通过 `compute_asset_id` 计算 SHA-256
  - 发布成功后写入 `evomap_capsules` 表（本地缓存）
  - 发布失败 → 记日志 + 写入本地缓存但标 `published=false`

- **`compute_asset_id(asset)`**：
  - `clean = {k: v for k, v in asset.items() if k != "asset_id"}`
  - `s = json.dumps(clean, sort_keys=True, ensure_ascii=False)`
  - 返回 `"sha256:" + hashlib.sha256(s.encode()).hexdigest()`

- **`status()`**：本地读取（不要为此专门调 hub）：
  - `online`: 上次心跳是否在 15 分钟内（查 `interactions` 表或模块级变量）
  - `node_id`: 凭证文件 / 配置
  - `credit_balance`: 上次心跳响应缓存（模块级变量，初始 None）
  - `survival_status`: "alive" / "unknown"

- **`get_evolution_stats()`**：本地聚合，**不调 hub**：
  - `evolution_count` = `evaluations` 表总行数
  - `preference_understanding` = 简单递增：`min(95, 30 + evolution_count * 5)`（基线 30%，每次 +5%，封顶 95%）
  - `radar_values` = 5 维 `{产业匹配, 政策理解, 空间分析, 风险识别, 企业匹配}`，每维基于 evaluations 表里的字段统计算出 0-100 分（具体算法：根据 evaluations.confidence 平均值 × 100 ± 维度偏移，**可以走简单实现，给出可视化数据即可**，BatchD 再做精确算法）
  - `capsules_published` = `evomap_capsules` 表 `WHERE published=true` 计数
  - `methodology_count` = 同上，对应 PRD 第 3.4 节"遗传方法论"字段

- **降级路径**：
  - `EVOMAP_HUB_URL` 不可达 → 所有 async 方法捕获异常 → 记日志 + 返回 `{"status": "offline", "error": str(e)}`
  - 主流程不抛异常
  - `get_evolution_stats()` 即使 evaluations 表为空，也要返回完整结构（数字归 0、雷达图维度均为 30 基线值）

- **模块级单例**：
  - 在文件末尾导出 `evo_client = EvomapClient()`
  - 后续被 main.py 的 startup 事件引用

---

### 任务 2：`src/services/ent_service.py`

**职责**：企业匹配——政府端多选企业、企业端单企推荐。

**必须实现**（按 modules.md 2.9 节）：

```python
async def match_enterprises(
    enterprise_ids: list[int],
    role: str
) -> list[EnterpriseMatchResult]: ...

async def match_single_enterprise(
    industry: str,
    area_mu: float,
    location_prefs: list[str],
    facility_needs: list[str]
) -> AgentReply: ...

def list_enterprises(search: str = "") -> list[dict]: ...
```

**关键要求**：

- **`list_enterprises(search)`**：
  - 查 `enterprises` 表
  - `search` 为空 → 返回全部
  - `search` 非空 → 对 `name` / `industry` / `industry_code` 做 `LIKE %?%` 模糊匹配
  - 返回字段：`id` / `name` / `industry` / `industry_code` / `employee_count` / `annual_revenue` / `priority_tags`
  - **不要返回** `space_demand` / `requirements` 详情（前端列表不需要，减少数据量）

- **`match_enterprises(enterprise_ids, role)`** 编排：
  1. 查 `enterprises` 表拿到企业列表（每条含 `space_demand`、`requirements` 解析 JSON）
  2. 对每家企业：
     - 调用 `grid_service.query_by_bbox`（用桐庐外接矩形 `config.TONGLU_BBOX`）拿到所有候选渔网
     - **简化筛选**：按 `space_demand.preferred_town` 过滤渔网的 `township` 字段
     - **简化评分**：调 `eval_service.evaluate_grids` 拿 LLM 评估结果
     - 取前 3 个候选作为该企业的结果
  3. 返回 `list[EnterpriseMatchResult]`，每条含 `enterprise_id` / `enterprise_name` / `candidates`
  - **企业端不走这条路径**（仅政府端可用）→ `role != "government"` 时抛 `PermissionError`
  - **空表兜底**：`enterprises` 表为空时返回 `[]`，不报错

- **`match_single_enterprise(...)`** 编排（企业端 P3 可砍模块）：
  - 这是企业端入口，**仅基于公开数据**
  - 实现可以**简单**：
    1. 构造 user_message：`f"我是 {industry} 行业企业，需要 {area_mu} 亩用地，区位偏好 {location_prefs}，配套需求 {facility_needs}"`
    2. 直接调用 `eval_service.chat(message=user_message, role="enterprise", bbox=None)`
    3. 返回 AgentReply
  - **不连接渔网查询**，让 LLM 给出宽泛建议
  - 企业端 P3 标记：函数开头加注释 `# 企业端 P3 可砍，本函数仅保留接口以备扩展`

- **JSON 字段读取**：
  - 从 enterprises 表读出的 `space_demand` / `requirements` / `priority_tags` 是 TEXT，必须 `json.loads`
  - 写入时（本批次不写入，留给 seed）`json.dumps`

- **不要写 seed 函数**：虚构企业的 seed 数据由批次 D 在 main.py 启动时插入（或独立脚本）

---

### 任务 3：`src/api/__init__.py` + `src/api/map_routes.py`

**职责**：地图相关 REST 端点。

**必须实现**（按 modules.md 2.10 节 + api.md）：

```python
# src/api/__init__.py
# 空文件

# src/api/map_routes.py
from fastapi import APIRouter, Query, HTTPException
from src.services import grid_service
from src.schemas import MapQueryResponse, GridDetailResponse, GridFeature

router = APIRouter(prefix="/api/map", tags=["map"])

@router.get("/query", response_model=MapQueryResponse)
async def query_map(bbox: str = Query(...), role: str = Query("government")): ...

@router.get("/grid/{grid_id}", response_model=GridDetailResponse)
async def grid_detail(grid_id: str, role: str = Query("government")): ...

@router.get("/ninegrid", response_model=list[GridFeature])
async def nine_grid(lng: float = Query(...), lat: float = Query(...),
                    role: str = Query("government")): ...
```

**关键要求**：

- **`/api/map/query`**：
  - 入参：`bbox` 形如 `"119.16,29.58,119.80,30.12"`（4 个浮点数，逗号分隔）
  - 解析失败 → 400 `{"detail": "bbox 参数格式错误"}`
  - `bbox` 范围检查：所有坐标必须落在 `config.TONGLU_BBOX` 内，超出 → 400
  - 调 `grid_service.query_by_bbox`，封装为 `MapQueryResponse` 返回

- **`/api/map/grid/{grid_id}`**：
  - 调 `grid_service.query_by_grid_id`
  - 返回 None（企业端访问）→ 403 `{"detail": "企业端不可查看单格详情"}`
  - 未找到 → 404 `{"detail": "grid_id 不存在"}`

- **`/api/map/ninegrid`**：
  - 入参：`lng` / `lat`（浮点）
  - 调 `grid_service.query_nine_grid`
  - 企业端返回空列表（不报错，前端会自行不渲染）
  - 坐标范围检查：必须在 `config.TONGLU_BBOX` 内，超出 → 返回空列表 + warning header

- **统一错误处理**：
  - 所有路由不抛裸异常，统一返回 `HTTPException(status_code, detail)`
  - 服务层 PermissionError → 403
  - 服务层 ValueError → 400
  - 其他异常 → 500（含 message 到 detail 用于调试）

- **role 校验**：
  - 仅接受 `"government"` 或 `"enterprise"`，其他值 → 400
  - 抽一个 helper 函数 `_validate_role(role)` 复用

---

### 任务 4：`src/api/agent_routes.py`

**职责**：对话 REST 端点。

**必须实现**（按 modules.md 2.11 节 + api.md）：

```python
# src/api/agent_routes.py
from fastapi import APIRouter, HTTPException
from src.services import eval_service
from src.schemas import ChatRequest, AgentReply

router = APIRouter(prefix="/api/agent", tags=["agent"])

@router.post("/chat", response_model=AgentReply)
async def chat(req: ChatRequest): ...
```

**关键要求**：

- **`/api/agent/chat`**：
  - 入参：`ChatRequest`（参考 schemas.py 中的字段）
  - 校验 `req.message` 长度 ≤ `config.CHAT_MAX_LENGTH`（500），超长 → 400
  - 校验 `req.role` ∈ {government, enterprise}
  - 调 `eval_service.chat(message=req.message, role=req.role, context=req.context, bbox=req.bbox)`
  - 返回 `AgentReply`
  - LLM 调用本身已有降级路径（批次 B 实现），路由层不再加保护

- **错误处理**：
  - LLM 超时 / API 不可用 → 已由 service 层降级处理，路由层不介入
  - JSON 解析失败 → 同上

---

## 关键约束（不可违反）

1. **Python 环境**：`D:\TOOLS\MiniConda\envs\agent_gpu_py311\python.exe`
2. **密钥管理**：全部从 `config` / `~/.evomap/` 读，无任何硬编码
3. **代码语言**：注释/docstring 中文，变量/函数英文
4. **不要写测试**、**不要启动服务**、**不要写 evo/ent 路由 + main.py**（批次 D 做）
5. **新增依赖**：
   - 本批次已有依赖（fastapi / httpx）足够，无需新增
   - 如果发现需要新依赖，先列在汇报里，由 Orchestrator 决定是否加入 requirements.txt
6. **TODO 注释规范**：未实现的细节 `# TODO[BatchD/E]: 描述`
7. **EvoMap 凭证持久化**：
   - 写到 `~/.evomap/node_id` 与 `~/.evomap/node_secret`
   - Windows 用 `pathlib.Path.home() / ".evomap"`
   - 失败仅 warning，不崩溃

---

## 输出要求

- **交付物**：
  - `src/services/evo_service.py`
  - `src/services/ent_service.py`
  - `src/api/__init__.py`
  - `src/api/map_routes.py`
  - `src/api/agent_routes.py`

- **质量底线**：
  - 每个文件顶部有中文 docstring
  - 每个公开函数有 docstring（参数、返回、异常）
  - 模块导入测试通过：
    ```
    from src.services import evo_service, ent_service
    from src.api import map_routes, agent_routes
    ```
  - 空数据兜底：所有服务方法在 enterprises / land_grid / evaluations 表为空时**不抛异常**
  - 全文搜索 `sk-` / `tk=` / `48ad1b76` / `sk-ce4` 无命中
  - EvoMap 不可达时所有方法**降级返回，不崩溃**

---

## 汇报要求

完成后将汇报写入：`D:\Projects\Urban_Industry_Assistant\outputs\handoffs\05_report_impl_batchC.md`

汇报必须包含：
1. 5 份交付物的完整路径与行数
2. EvoMap 客户端的关键设计决策（凭证读写策略、降级路径、心跳循环异常处理）
3. 4 个模块的导入测试结果
4. **空数据兜底自检**：分别说明 `enterprises` 表为空 / `land_grid` 表为空时，各方法的行为
5. **EvoMap 不可达自检**：模拟 `EVOMAP_HUB_URL = "http://invalid.local"` 时，所有方法是否安全降级
6. TODO 注释清单（按批次分组）
7. 与 modules.md / api.md 的偏离之处（如有）及原因
8. 风险或遗漏

汇报写完后，告知主人"批次 C 已完成，请查阅"。
