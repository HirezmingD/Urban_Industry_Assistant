# 指令：批次 A — 数据准备层（config / schemas / database）

**发出方**：Orchestrator
**接收方**：实现 Agent
**时间**：2026-06-19
**项目**：Urban_Industry_Assistant
**批次**：A（共 5 批次的第 1 批）

---

## 任务背景

PRD、研究报告、架构文档、补充决议已全部完成。本次任务是分批次实现的第一批，专注**数据准备层**：配置加载、数据模型定义、数据库表创建与连接。

**关键约束**：本批次只做 3 个步骤（架构 Agent 14 步实现顺序的前 3 步），上下文聚焦，避免幻觉。

---

## 输入材料（必读，按重要性排序）

1. `D:\Projects\Urban_Industry_Assistant\specs\arch\architecture.md` — 整体架构
2. `D:\Projects\Urban_Industry_Assistant\specs\arch\modules.md` — 模块设计（重点看 config / schemas / database 三个模块）
3. `D:\Projects\Urban_Industry_Assistant\specs\arch\database.md` — 数据库设计（建表 SQL）
4. `D:\Projects\Urban_Industry_Assistant\specs\arch\api.md` — API 接口（用于反推 schemas 字段）
5. `D:\Projects\Urban_Industry_Assistant\outputs\handoffs\04_addendum_arch_decisions.md` — 七项决议（必须严格遵守）

---

## 本批次任务（3 个文件）

### 任务 1：`src/config.py`

加载并暴露全局配置。

**必须实现**：
- 从 `.env` 加载所有密钥与配置（`python-dotenv`）
- 暴露以下变量供其他模块导入：
  - `DEEPSEEK_API_KEY` — DeepSeek API key
  - `DEEPSEEK_BASE_URL` — DeepSeek API 基础 URL（默认 `https://api.deepseek.com`）
  - `DEEPSEEK_MODEL` — 使用的模型名（默认 `deepseek-chat`）
  - `TIANDITU_API_KEY` — 天地图 API key
  - `TIANDITU_TILE_URL_TEMPLATE` — 天地图瓦片 URL 模板（按决议 4 的 `img_w` 服务）
  - `EVOMAP_HUB_URL` — `https://evomap.ai`
  - `EVOMAP_NODE_ID` — 从 `~/.evomap/node_id` 读取（若存在）
  - `EVOMAP_NODE_SECRET` — 从 `~/.evomap/node_secret` 读取（若存在）
  - `DATABASE_PATH` — `db/uia.db`
  - `DATA_DIR` — `data/`
  - `PROCESSED_DATA_DIR` — `data/processed/`
  - `RAW_DATA_DIR` — `data/raw/`
  - `TILES_DIR` — `data/tiles/`
  - `TONGLU_BBOX` — 桐庐外接矩形 (min_lng, min_lat, max_lng, max_lat) — 写为 Python 常量 `(119.16, 29.58, 119.80, 30.12)`，注释说明实际值由数据预处理阶段精确推算
  - `LLM_SEMAPHORE_LIMIT` — 1（按决议）
  - `LLM_QUEUE_DEPTH` — 10
- 缺失关键配置时（如 `DEEPSEEK_API_KEY`）打印警告但不崩溃（允许仅前端运行）

**同时创建**：
- `.env.example` — 模板文件（所有 key 留空），写到项目根目录
- `.gitignore` — 必须包含 `.env`、`db/`、`data/raw/`、`data/processed/`、`data/tiles/`、`__pycache__/`、`*.pyc`

### 任务 2：`src/schemas.py`

定义所有 Pydantic 数据模型。

**必须实现**（参考 `api.md` 的入参/出参 JSON 示例反推）：

- **渔网相关**
  - `GridCell` — 单个渔网单元（grid_id, land_type, land_code, area_sqm, ownership, township, mixed_type, extras, geom_wgs84）
  - `GridSelectRequest` — 框选请求（bbox 或 polygon）
  - `GridSelectResponse` — 框选响应（cells: List[GridCell], total_count, total_area）
  - `NineGridRequest` — 九宫格请求（lng, lat）
  - `NineGridResponse` — 九宫格响应（cells: List[GridCell]，9 个）

- **评估相关**
  - `EvaluationRequest` — 地块评估请求（grid_ids: List[str], intent: Optional[str]）
  - `EvaluationResponse` — 评估结果（summary, scores: Dict, recommendations: List, policy_refs: List）

- **对话相关**
  - `ChatMessage` — 单条消息（role: Literal["user", "assistant"], content）
  - `ChatRequest` — 对话请求（messages: List[ChatMessage], context: Dict）
  - `ChatResponse` — 对话响应（reply, structured_result: Optional）

- **企业相关**（保留接口，企业端 P3 可砍但 schema 不删）
  - `Enterprise` — 企业画像（id, name, industry, industry_code, employee_count, annual_revenue, space_demand, requirements, priority_tags）
  - `EnterpriseMatchRequest` — 政府端多企业匹配（enterprise_ids: List[str]）
  - `EnterpriseMatchResponse` — 匹配结果（matches: List, summary）

- **自进化展示相关**
  - `EvolutionStats` — 自进化统计（experience_count, preference_understanding, methodology_count, capsule_contributed, radar: Dict[str, float]）

- **通用**
  - `Role` — 枚举 `government` / `enterprise`
  - `ErrorResponse` — 错误响应（code, message, detail）

**字段类型严格遵守 `api.md`**，命名一致。

### 任务 3：`src/database.py`

数据库连接与建表。

**必须实现**：
- 使用 SQLite 内建模块（不引入 SQLAlchemy ORM，按架构决策）
- 使用 `sqlite3.Row` 作为 row_factory，方便 dict 化
- 启用 `PRAGMA journal_mode=WAL`（并发友好）
- 启用 R-tree 扩展（`sqlite3.enable_load_extension` 默认开，R-tree 模块在 SQLite 标准发行中自带）
- 暴露的核心函数：
  - `get_connection() -> sqlite3.Connection` — 获取连接（每个请求一个）
  - `init_db()` — 创建所有表（按 `database.md` 的 SQL）
  - `close_connection(conn)` — 关闭连接
- 在 `init_db()` 中按以下顺序建表：
  1. `land_grid` 主表（含 `extras` JSON 字段，按决议 2 同时保留 `land_code` + `land_type`）
  2. `land_grid_rtree` R-tree 空间索引（min_lng, max_lng, min_lat, max_lat）
  3. `enterprises` 企业画像表
  4. `evaluations` 评估记录表
  5. `evomap_capsules` Capsule 缓存表
  6. `interactions` 交互日志表
- 所有 SQL 写在 `database.md` 指定的位置，**严格按架构文档的字段名和类型**
- `init_db()` 必须幂等（重复执行不报错），用 `CREATE TABLE IF NOT EXISTS`

**额外要求**：
- 文件顶部加注释说明 R-tree 两步法查询的设计思路
- 提供一个 `seed_demo_enterprises()` 占位函数（先 pass，实现 Agent 后续批次会填充虚构企业）

---

## 关键约束（不可违反）

1. **Python 环境**：使用 `D:\TOOLS\MiniConda\envs\agent_gpu_py311\python.exe`（Python 3.11）
2. **密钥管理**：
   - 绝不在任何代码中硬编码 `sk-`、`tk=`、API key
   - 所有密钥必读自环境变量
   - `.env` 必须列入 `.gitignore`
3. **代码语言**：注释和 docstring 用中文，变量名/函数名用英文
4. **不要写测试**：本批次只产出 3 个核心文件 + `.env.example` + `.gitignore`，不写单元测试
5. **不要启动服务**：不要写 main.py，不要跑 uvicorn
6. **不要安装新依赖**：本批次只用 Python 3.11 内置模块 + `pydantic` + `python-dotenv`（如未装，在 requirements.txt 中加入即可，由主人安装）

---

## 输出要求

- **交付物**：
  - `src/config.py`
  - `src/schemas.py`
  - `src/database.py`
  - `.env.example`（项目根目录）
  - `.gitignore`（项目根目录）
  - `requirements.txt`（项目根目录，列出本批次新增依赖）

- **代码质量底线**：
  - 每个文件顶部有 docstring 说明用途
  - 每个公开函数有 docstring 说明参数与返回值
  - 不能有未实现的占位（除 `seed_demo_enterprises()` 明确说明的占位）
  - 不能有硬编码的密钥
  - 必须能通过 `python -c "from src import config, schemas, database; database.init_db()"` 测试导入与建表

---

## 汇报要求

完成后将汇报写入：`D:\Projects\Urban_Industry_Assistant\outputs\handoffs\05_report_impl_batchA.md`

汇报必须包含：
1. 6 份交付物的完整路径
2. 关键设计决策（如有偏离架构文档的地方，必须说明原因）
3. 自检结果：是否通过导入测试（`python -c "from src import config, schemas, database; database.init_db()"`）
4. 是否发现 `database.md` 或 `architecture.md` 中含糊或矛盾的地方（如有，列出待主人确认）
5. 风险或遗漏

汇报写完后，告知主人"批次 A 已完成，请查阅"。
