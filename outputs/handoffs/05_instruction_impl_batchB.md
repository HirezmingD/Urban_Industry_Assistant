# 指令：批次 B — 核心服务层（4 个文件）

**发出方**：Orchestrator
**接收方**：实现 Agent
**时间**：2026-06-19
**项目**：Urban_Industry_Assistant
**批次**：B（共 5 批次的第 2 批）

---

## 任务背景

批次 A（config / schemas / database）已完成并通过质检。本批次实现**核心服务层**：LLM prompt 模板、渔网空间查询、政策匹配、评估编排。

**关键约束**：
- 4 个文件，按顺序实现（后者依赖前者）
- 不写 API 路由（批次 C 才做）
- 不启动服务、不写测试
- 本批次还要顺手做一次 **enterprises 表字段统一**，拆掉批次 A 留下的雷

---

## 输入材料（必读，按重要性排序）

1. `D:\Projects\Urban_Industry_Assistant\specs\arch\modules.md` — 4 个模块的完整函数签名（第 2.4 / 2.5 / 2.6 / 2.7 节）
2. `D:\Projects\Urban_Industry_Assistant\specs\arch\database.md` — 数据库表与查询模式
3. `D:\Projects\Urban_Industry_Assistant\research\tonglu_policy_research.md` — 七维评估模型 + 政策对照表（policy_service 直接引用）
4. `D:\Projects\Urban_Industry_Assistant\outputs\handoffs\04_addendum_arch_decisions.md` — 七项决议
5. `D:\Projects\Urban_Industry_Assistant\specs\src\prd.md` — 用户场景（理解 prompt 怎么写）
6. `D:\Projects\Urban_Industry_Assistant\src\schemas.py` — 已实现的 Pydantic 模型（你要导入复用）
7. `D:\Projects\Urban_Industry_Assistant\src\database.py` — 已实现的数据库连接（你要导入复用）

---

## 前置任务：enterprises 表字段统一（拆雷）

批次 A 报告指出 `enterprises` 表的字段和 `Enterprise` Pydantic 模型不一致。本批次开始前必须先统一。

### 决议：以 Pydantic schema 为准，改表结构

**新 enterprises 表结构**：

```sql
CREATE TABLE IF NOT EXISTS enterprises (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  industry TEXT NOT NULL,
  industry_code TEXT,
  employee_count INTEGER,
  annual_revenue TEXT,
  space_demand TEXT,    -- JSON: {min_area_sqm, max_area_sqm, preferred_town, fallback_towns}
  requirements TEXT,    -- JSON: {water_supply, electricity_level, waste_treatment, transport_access}
  priority_tags TEXT,   -- JSON 数组
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 你必须执行的动作

1. **修改 `src/database.py`**：把 `enterprises` 表的建表 SQL 替换为上面的版本
2. **删除旧字段**：删除 `area_mu` / `location_pref` / `facility_needs` / `investment` / `annual_output` 等字段
3. **JSON 字段存储约定**：写入时 `json.dumps`，读取时 `json.loads`，后续 `ent_service` 中统一处理
4. **验证**：删除 `db/uia.db`（如果存在），重跑 `database.init_db()` 确认新表结构正确
5. **不要写 seed 数据**：`seed_demo_enterprises()` 仍为占位，留给批次 D 做

---

## 本批次任务（4 个文件）

### 任务 1：`src/prompts/system_prompt.py`

**职责**：政府端 / 企业端两套 LLM system prompt + 评估 prompt 构造器。

**必须实现的函数签名**（按 modules.md 2.4 节）：

```python
def get_system_prompt(role: str) -> str: ...
def build_eval_prompt(grid_data: list[dict], policy_context: dict, role: str) -> str: ...
```

**关键要求**：

- **政府端 system prompt** 要点：
  - 你是面向县域政府的产业用地评估助手
  - 立场：全域产业最优、税收/就业/土地利用效率综合考量
  - 可见数据：渔网底层数据（含权属、面积、用地类型）
  - 输出格式：必须返回结构化 JSON，含 `summary` / `items[rank, industry, score, reason, policy_refs, risk]` / `policy_citations` / `risks` / `candidate_grids`
  - 必须对标桐庐"十五五"产业政策，每条建议要有政策依据

- **企业端 system prompt** 要点：
  - 你是面向中小企业主的用地咨询助手
  - 立场：该企业利益最优
  - 可见数据：仅公开数据（地理范围、用地类型分布、统计指标，不含权属、不含精确坐标）
  - 输出格式：与政府端一致，但 `candidate_grids` 仅返回聚合轮廓中心点

- **`build_eval_prompt`** 要点：
  - 把 grid_data（聚合统计 + 用地类型分布）+ policy_context（七维权重 + 政策引用）拼接为 user prompt
  - 用 Markdown 结构化（## 网格概况 / ## 政策环境 / ## 用户需求）
  - 末尾强制要求"请按 JSON 格式返回，字段为：summary, items, policy_citations, risks, candidate_grids"

- **不要写 JSON schema 校验**（解析在 eval_service 做）

### 任务 2：`src/services/grid_service.py`

**职责**：渔网空间查询。

**必须实现的函数签名**（按 modules.md 2.5 节）：

```python
def query_by_bbox(bbox_wgs84: tuple[float,float,float,float], role: str) -> dict: ...
def query_by_grid_id(grid_id: str, role: str) -> dict | None: ...
def query_nine_grid(lng: float, lat: float, role: str) -> list[dict]: ...
def get_grid_stats(grid_ids: list[str]) -> dict: ...
```

**关键要求**：

- **R-tree 两步法**：
  - 第一步：`SELECT grid_id FROM land_grid_rtree WHERE min_lng <= ? AND max_lng >= ? AND min_lat <= ? AND max_lat >= ?`
  - 第二步（可选）：用 shapely 做精确过滤（本批次先实现第一步，shapely 留 TODO 注释说明何时启用）
  - 查询结果数量超过 `BBOX_QUERY_LIMIT`（500）必须截断并在返回中标注 `truncated: true`

- **角色字段过滤**：
  - `role == "government"`：返回完整字段（含 `ownership`、`geom_wgs84`）
  - `role == "enterprise"`：返回精简字段（不含 `ownership`、不含 `geom_wgs84`、不含 `land_code`）
  - 在 SELECT 层就过滤，不在 Python 里删字段（性能）

- **九宫格定位算法**：
  - 给定 (lng, lat)，找出包含该点的渔网单元（grid_id）
  - 基于该格的边界坐标，向四周扩展 ±100m（CGCS2000 投影下 100m ≈ 0.001 度，可近似 ±0.001 lng/lat）
  - 用 R-tree 查询周围 8 格
  - 返回 9 个 GridFeature 字典（中心格在第 0 位）
  - **企业端返回空列表**（按 PRD：九宫格仅政府端可见）

- **`get_grid_stats` 聚合**：
  - `grid_count` / `total_area_sqm` / `total_area_mu`（1 亩 ≈ 666.67 ㎡）
  - `land_type_distribution: {type: count}`
  - 用 SQL 聚合，不在 Python 循环

- **空数据兜底**：
  - 渔网预处理未完成时（`land_grid` 表为空），所有查询返回空集合并打 warning 日志，不抛异常

### 任务 3：`src/services/policy_service.py`

**职责**：七维评估权重 + 政策匹配。

**必须实现的函数签名**（按 modules.md 2.6 节）：

```python
def calculate_weights(land_type: str, town: str, industry: str) -> dict[str, float]: ...
def get_policy_refs(industry: str, land_type: str, town: str) -> list[str]: ...
def get_tonglu_industry_preference(industry: str) -> str: ...
```

**关键要求**：

- **七维权重表**（直接引用 `tonglu_policy_research.md` §七 七维评估模型）：
  - 用地合规性 0.15 / 新质生产力适配 0.10 / 产业适配度 0.25 / 经济效益 0.15 / 环境约束 0.20 / 基础设施 0.05 / 政策红利 0.10
  - `calculate_weights` 当前先返回静态权重表，后续可根据 land_type/town/industry 微调（留 TODO 注释）

- **政策引用库**：
  - 在模块顶部维护一个 Python dict 常量 `POLICY_LIBRARY`，结构：
    ```python
    POLICY_LIBRARY = {
        "national_15_5": "国家十五五规划纲要（2026-2030）",
        "zhejiang_industrial_5+1": "浙江省亩均论英雄县域指标体系",
        "tonglu_industrial_baseline": "桐庐县工业用地最低出让价（10.2万/亩）",
        # ... 至少 8 条，覆盖 tonglu_policy_research.md §六 政策对照总表 18 条中的核心条目
    }
    ```
  - `get_policy_refs` 根据 industry/land_type/town 命中条件返回 dict 的 key 列表（不返回完整文本，由前端按 key 渲染）

- **桐庐产业供地偏好**（直接引用 `tonglu_policy_research.md` §五 桐庐县供地偏好矩阵）：
  - 维护一个 `TONGLU_INDUSTRY_PREFERENCE` dict：
    ```python
    TONGLU_INDUSTRY_PREFERENCE = {
        "大健康": "优先供地",
        "智能制造": "优先供地",
        "现代物流": "优先供地",
        "数字经济": "正常供地",
        "文旅康养": "正常供地",
        "传统服装": "限制新供地",
        "高碳排化工": "禁止新供地",
        # ... 至少 10 条
    }
    ```
  - 未命中返回 "未知"

- **不引入外部依赖**（不读文件、不调 API），全部硬编码在 Python dict 里，方便后续直接修改

### 任务 4：`src/services/eval_service.py`

**职责**：核心评估编排——网格 + 政策 + LLM 调用 → 结构化结果 → 存评估记录。

**必须实现的函数签名**（按 modules.md 2.7 节）：

```python
async def evaluate_grids(
    grid_ids: list[str],
    user_message: str,
    role: str,
    context: list[dict] | None = None
) -> AgentReply: ...

async def chat(
    message: str,
    role: str,
    context: list[dict] | None = None,
    bbox: str | None = None
) -> AgentReply: ...

def parse_llm_response(raw: str) -> AgentReply: ...
def record_evaluation(eval_data: dict) -> None: ...
```

**关键要求**：

- **LLM 客户端**：用 `httpx.AsyncClient`，POST 到 `DEEPSEEK_BASE_URL + "/chat/completions"`，model = `DEEPSEEK_MODEL`（即 `deepseek-v4-pro`）
- **请求结构**（DeepSeek 兼容 OpenAI Chat Completions API）：
  ```python
  {
      "model": config.DEEPSEEK_MODEL,
      "messages": [
          {"role": "system", "content": get_system_prompt(role)},
          *context,  # 历史对话
          {"role": "user", "content": build_eval_prompt(...)}
      ],
      "temperature": 0.3,
      "response_format": {"type": "json_object"},
  }
  ```
- **超时**：`LLM_TIMEOUT = 30s`（来自 config）
- **并发控制**：用 `asyncio.Semaphore(LLM_SEMAPHORE_LIMIT=1)`，全局单实例，串行 LLM 调用
  - Semaphore 实例放在 `eval_service.py` 模块级别 `_llm_semaphore = asyncio.Semaphore(1)`
  - 调用时 `async with _llm_semaphore: ...`

- **`evaluate_grids` 编排步骤**：
  1. 调 `grid_service.get_grid_stats(grid_ids)` 拿聚合数据
  2. 推断主导产业类型（从 LLM 之前先用规则猜，或留给 LLM 自己决定）
  3. 调 `policy_service.calculate_weights(...)` + `get_policy_refs(...)` 拿政策上下文
  4. 调 `build_eval_prompt(...)` 拼 user prompt
  5. 调 LLM API
  6. 调 `parse_llm_response(raw)` 解析为 `AgentReply`
  7. 调 `record_evaluation(...)` 存评估记录
  8. 返回 AgentReply

- **`chat` 分支**：
  - 若 `bbox` 非空，先调 `grid_service.query_by_bbox` 拿 grid_ids，再走 `evaluate_grids`
  - 若 `bbox` 为空，仅做产业咨询对话（不查渔网，纯 LLM 应答）

- **`parse_llm_response` 容错**：
  - LLM 返回 JSON 字符串，用 `json.loads` 解析
  - 解析失败时返回降级结果（`summary` 含错误提示，`items` 为空，`candidate_grids` 为空）
  - 不抛异常（保证前端始终能渲染）

- **`record_evaluation` 写库**：
  - 写入 `evaluations` 表，字段对应 `database.md` 定义
  - 失败仅日志告警，不影响主流程

- **LLM 不可用降级**：
  - `DEEPSEEK_API_KEY` 未设置 → 返回静态降级 AgentReply（含"LLM 未配置，返回基线建议"提示）
  - HTTPX 调用异常 → 同上降级

---

## 关键约束（不可违反）

1. **Python 环境**：`D:\TOOLS\MiniConda\envs\agent_gpu_py311\python.exe`
2. **密钥管理**：全部从 `config` 读，无任何硬编码
3. **代码语言**：注释/docstring 中文，变量/函数英文
4. **不要写测试**、**不要启动服务**、**不要建 API 路由**
5. **新增依赖**：
   - `httpx`（LLM 客户端）
   - `shapely`（geometry 精确过滤，本批次留 TODO 即可，不必导入）
   - 加入 `requirements.txt`，由主人手动 pip install
6. **enterprises 表必须重建**：删 `db/uia.db` → 重跑 `init_db()`
7. **TODO 注释规范**：所有暂未实现的细节用 `# TODO[BatchC/D]: 描述` 标注，便于后续批次接手

---

## 输出要求

- **交付物**：
  - `src/prompts/__init__.py`
  - `src/prompts/system_prompt.py`
  - `src/services/__init__.py`
  - `src/services/grid_service.py`
  - `src/services/policy_service.py`
  - `src/services/eval_service.py`
  - `src/database.py`（修改 enterprises 表）
  - `requirements.txt`（追加 httpx）

- **质量底线**：
  - 每个文件顶部有 docstring
  - 每个公开函数有 docstring（参数、返回、异常）
  - 模块导入测试通过：`from src.prompts import system_prompt; from src.services import grid_service, policy_service, eval_service` 不报错
  - `database.init_db()` 重跑后 enterprises 表字段与新结构完全一致
  - 全文搜索 `sk-` / `tk=` / `48ad1b76` 无命中
  - 所有 TODO 注释明确标注批次（BatchC / BatchD / BatchE）

---

## 汇报要求

完成后将汇报写入：`D:\Projects\Urban_Industry_Assistant\outputs\handoffs\05_report_impl_batchB.md`

汇报必须包含：
1. 8 份交付物的完整路径与行数
2. enterprises 表统一情况自检（旧字段全部清除？新字段与 Pydantic 完全对齐？）
3. 4 个模块的导入测试结果
4. 关键设计决策（特别是与 modules.md 偏离之处，说明原因）
5. TODO 注释清单（按批次分组列出，方便后续 Agent 接手）
6. 风险/遗漏

汇报写完后，告知主人"批次 B 已完成，请查阅"。
