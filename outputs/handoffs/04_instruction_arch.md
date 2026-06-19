# 指令：编写 Urban_Industry_Assistant 系统架构与接口设计文档

**发出方**：Orchestrator
**接收方**：架构 Agent
**时间**：2026-06-19
**项目**：Urban_Industry_Assistant

---

## 任务背景

PRD 已经过三轮修订，需求完全固化。研究 Agent 已完成 EvoMap 接入方案、桐庐数据源、产业政策三份报告。现在需要将需求转换为**可指导编码的系统架构**：模块拆分、接口定义、数据流、技术选型。

本项目在整体流程中的位置：**研究 → 内容（已完成）→ 架构（本任务）→ 实现 → 测试**。架构产出将直接指导实现 Agent 的编码工作。

**关键时间约束**：比赛 19 日中午开赛，21 日中午截止。架构产出必须服务于 20 小时的开发节奏，**重落地、轻完美**。

---

## 输入材料（按重要性排序）

1. `D:\Projects\Urban_Industry_Assistant\specs\src\prd.md` — **核心需求文档**（689 行，必须通读）
2. `D:\Projects\Urban_Industry_Assistant\research\evomap_integration_plan.md` — EvoMap 接入方案（含 Python 代码骨架）
3. `D:\Projects\Urban_Industry_Assistant\research\tonglu_data_sources.md` — 数据源清单（含预处理脚本）
4. `D:\Projects\Urban_Industry_Assistant\research\tonglu_policy_research.md` — 产业政策（七维评估模型）
5. `D:\Projects\Urban_Industry_Assistant\outputs\开发流程_内部方案.md` — 开发节奏与技术栈选型
6. `D:\Projects\Urban_Industry_Assistant\DLTB_2020.xlsx` — 桐庐土地利用数据（46 类用地，约 5000 图斑）
7. `D:\Projects\Urban_Industry_Assistant\XZQ.xlsx` — 桐庐行政区划数据（14 个乡镇/街道）

---

## 你的任务

### 任务 1：系统整体架构

输出一份完整的系统架构图（用 Markdown 或 Mermaid 表达），包含：

- 前端层 / 后端层 / 数据层 / 外部服务层四层划分
- 各层内部的核心模块（如后端的 API 路由、业务服务、Agent 核心、EvoMap 客户端等）
- 模块之间的调用方向与数据流
- 标注政府端 vs 企业端的差异路径

### 任务 2：技术选型清单

明确每一项技术栈的选择与版本，至少覆盖：

| 类别 | 待选项 |
|------|-------|
| 后端框架 | FastAPI / Flask |
| 前端框架 | 纯 HTML+JS / Vue / React |
| 地图库 | Leaflet / Mapbox GL JS |
| 图表库 | Chart.js / ECharts（v1.0 必做雷达图） |
| 数据库 | SQLite / PostgreSQL |
| GIS 处理 | geopandas / shapely / GDAL |
| LLM 客户端 | openai-python / httpx + 自封装 |
| EvoMap 客户端 | httpx（按研究报告） |
| Python 版本 | **必须 3.11**（主人指定环境：`D:\TOOLS\MiniConda\envs\agent_gpu_py311\python.exe`） |

每个选择必须给出理由（不超过两行）。

### 任务 3：模块设计与目录结构

对照 PRD 5 章功能需求，给出后端代码模块的最终目录结构。必须遵循项目现有骨架：

```
src/
├── api/              ← FastAPI 路由
├── services/         ← 业务逻辑
├── main.py           ← 入口
```

在此基础上扩展。**每个模块标注**：
- 文件名（如 `services/grid_service.py`）
- 职责（一句话）
- 依赖关系（依赖哪些其他模块）
- 暴露的核心函数签名（不要写实现，只写函数名 + 参数 + 返回类型）

### 任务 4：API 接口定义

列出后端对前端暴露的所有 REST API。每个接口必须包含：

| 字段 | 要求 |
|------|------|
| 路径 | 如 `POST /api/grid/select` |
| 用途 | 一句话说明 |
| 入参 | JSON schema 或字段表 |
| 出参 | JSON schema 或字段表 |
| 端权限 | 政府端 / 企业端 / 通用 |
| 错误码 | 主要错误码及含义 |

**至少覆盖以下接口**（根据 PRD 推导，可补充更多）：
- 地图渔网查询（按范围 / 按九宫格 / 按 grid_id）
- 地块评估（单地块详情）
- 多企业匹配（政府端：多选企业 → 全域最优）
- 单企业建议（企业端：自身需求 → 个体最优）
- 对话接口（自然语言 → 结构化结果）
- 自进化展示数据（雷达图五维数值 + 经验计数）
- EvoMap 状态查询

### 任务 5：数据库设计

输出建表 SQL 草案（SQLite 兼容）。必须覆盖：

- `land_grid` 渔网主表（100m×100m，含 46 类用地属性、权属、area、混合用地说明）
  - **必须为后续扩展字段预留方案**（JSON 字段 / 独立扩展表，二选一并说明理由）
- `enterprises` 企业画像表（虚构企业 case，建议覆盖全行业，含规模）
- `evaluations` 评估记录表（用于自进化经验池）
- `evomap_capsules` 已发布 Capsule 本地缓存表
- `interactions` 用户交互日志表（用于雷达图能力计算）

建表 SQL 不需完整可执行，但字段名、类型、主键、外键、关键索引必须清楚。

### 任务 6：关键数据流时序图

至少画出以下 4 个核心场景的时序图（用 Mermaid sequenceDiagram 或文字描述均可）：

1. **政府端框选场景**：用户在地图框选 → 后端 GIS 查询 → 返回范围内渔网集合 → 前端渲染
2. **多企业匹配场景**：政府端多选企业 → 后端聚合需求 → LLM 评估 → 渔网评分 → 排序返回 → 地图高亮
3. **九宫格悬停**：鼠标移动 → 前端计算渔网坐标 → 后端返回 9 格属性（或本地缓存）→ 透显渲染
4. **EvoMap 发布**：评估完成 → 本地经验池存储 → 提炼脱敏方法论 → POST /a2a/publish → 更新雷达图

时序图重点回答：**哪些是同步调用？哪些是异步？哪些做缓存？**

### 任务 7：渔网预处理方案（独立专题）

PRD 已明确：渔网生成 + 空间连接采用**一次性预处理**（不在线计算）。请输出：

1. 预处理脚本的执行流程（伪代码或 Python 草案）
2. 输出格式：GeoJSON / Shapefile / SQLite GeoPackage 三选一并说明理由
3. 预估数据量与耗时（基于桐庐 1829 km² + 100m 网格 ≈ 18 万格）
4. 失败回退方案（如 100m 太密，降级到 200m / 500m 的判断标准）

### 任务 8：性能与扩展性预案

回答以下三个具体问题：

1. **数十人并发**：FastAPI 默认配置能不能撑？需要 uvicorn workers / 异步队列吗？
2. **18 万渔网查询**：每次框选都做空间查询，需要 R-tree 索引吗？SQLite 的 SpatiaLite 扩展能用吗？
3. **LLM 调用成本**：政府端多选 10 个企业一次评估，可能调多次 LLM。是否做请求合并 / 缓存？

每个问题给出**Demo 阶段的简化决策**（不要追求生产级方案）。

---

## 关键约束（不可违反）

1. **Python 环境**：所有 Python 代码默认 `D:\TOOLS\MiniConda\envs\agent_gpu_py311\python.exe` 执行
2. **数据脱敏**：架构中凡涉及"三调"措辞一律改为"土地利用数据"或"渔网底层数据"
3. **文档语言**：所有文档用中文编写（代码注释、变量名可英文）
4. **开发节奏**：架构必须能让实现 Agent 在 12 小时内完成主干，不允许出现需要 1 天以上才能搞定的模块
5. **EvoMap 接入方式**：通用协议接入（HTTP REST 调用 evomap.ai），不使用任何 Evolver 插件
6. **离线兜底**：地图瓦片必须支持本地加载兜底，LLM 调用失败必须有降级路径

---

## 输出要求

- **交付物路径**：`D:\Projects\Urban_Industry_Assistant\specs\arch\` 下分以下文件：
  - `architecture.md` — 任务 1（整体架构）+ 任务 2（技术选型）
  - `modules.md` — 任务 3（模块设计与目录结构）
  - `api.md` — 任务 4（API 接口定义）
  - `database.md` — 任务 5（数据库设计）
  - `sequence.md` — 任务 6（时序图）
  - `grid_preprocessing.md` — 任务 7（渔网预处理）
  - `performance.md` — 任务 8（性能预案）

- **必须包含**：
  - 每个文件的开头有 1-2 段"本文档要解决什么问题"的导言
  - 每个技术决策附带"为什么这么选"的简短理由
  - 接口定义必须有完整的入参/出参示例（JSON）
  - 时序图至少 4 个完整场景
  - 模块依赖关系必须画清楚（避免循环依赖）

- **质量底线**：
  - 实现 Agent 拿到这套文档后，能够无歧义地开始写代码
  - 不允许出现"待定"、"看情况"、"由实现决定"这类含糊措辞
  - 出现的每一个 API、每一张表、每一个模块都必须有用途说明

---

## 汇报要求

完成后将汇报写入：`D:\Projects\Urban_Industry_Assistant\outputs\handoffs\04_report_arch.md`

汇报内容必须包含：
1. 七份交付物的完整路径列表
2. 关键技术决策的摘要（5-10 条要点）
3. 自己识别出的风险点或需要主人确认的事项
4. 完成度自检（PRD 中哪些功能在架构中明确落地了，哪些有遗漏）

汇报写完后，告知主人"已完成，请查阅汇报文件"。
