# 研究指令：EvoMap 开发者套件 → Urban_Industry_Assistant 集成方案

**发出方**：Orchestrator  
**接收方**：研究 Agent  
**时间**：2026-06-19  
**项目**：Urban_Industry_Assistant  
**指令编号**：02_supplement  

---

## 任务背景

Urban_Industry_Assistant 是桐庐县城市产业空间智能助手，赛道 The Pearl（自进化）。已实现 V1.0：FastAPI 后端 + Leaflet 前端 + 天地图卫星底图 + LLM 对话评估 + 企业匹配 + 雷达图。当前正在接入 EvoMap 通用协议（HTTP REST /a2a/hello、/a2a/heartbeat、/a2a/publish）。

EvoMap 官方转发了开发者套件，已下载到本机。需要深入研究后回答：**在已完成的 V1.0 架构基础上，如何最大化利用 EvoMap 开发者套件来完成自进化叙事？**

---

## 输入材料

### 开发者套件（必读）

| 路径 | 内容 | 重要性 |
|------|------|:--:|
| `D:\TOOLS\Evomap_wiki\evolver_v1.89.13\SKILL.md` | Evolver 的 SKILL.md——Agent 接入规范 | ⭐⭐⭐ |
| `D:\TOOLS\Evomap_wiki\evolver_v1.89.13\README.md` | Evolver 主 README | ⭐⭐⭐ |
| `D:\TOOLS\Evomap_wiki\evolver_v1.89.13\README.zh-CN.md` | 中文 README | ⭐⭐⭐ |
| `D:\TOOLS\Evomap_wiki\evolver_v1.89.13\examples\hello-world.md` | Hello World 示例 | ⭐⭐ |
| `D:\TOOLS\Evomap_wiki\evolver_v1.89.13\examples\atp-consumer-quickstart.md` | ATP Consumer 快速入门 | ⭐⭐ |

### 官方文档（按需查阅）

`D:\TOOLS\Evomap_wiki\docs\` 下 36 份文档，重点查阅：

| 文档 | 内容 |
|------|------|
| `03-for-ai-agents.md` | Agent 接入完整指南 |
| `05-a2a-protocol.md` | A2A 协议细节 |
| `16-gep-protocol.md` | Gene/Capsule/EvolutionEvent 数据模型 |
| `34-evolver.md` | Evolver CLI 完整文档 |
| `28-api-access.md` | API 接入方式 |
| `01-quick-start.md` | 快速入门 |

### 项目现有 EvoMap 集成代码

| 路径 | 内容 |
|------|------|
| `D:\Projects\Urban_Industry_Assistant\src\services\evo_service.py` | 当前 EvoMap 服务（hello/heartbeat/publish 封装） |
| `D:\Projects\Urban_Industry_Assistant\src\api\evo_routes.py` | EvoMap API 路由 |
| `D:\Projects\Urban_Industry_Assistant\specs\arch\evomap_integration_plan.md` | 既有集成方案文档 |

### 项目既有设计文档

| 路径 | 内容 |
|------|------|
| `D:\Projects\Urban_Industry_Assistant\specs\arch\architecture.md` | 系统架构 |
| `D:\Projects\Urban_Industry_Assistant\specs\arch\database.md` | 数据库设计（含 evaluations / evomap_capsules 表） |
| `D:\Projects\Urban_Industry_Assistant\specs\src\prd.md` | PRD（含自进化展示面板需求） |

---

## 研究问题

### 问题 1：通用协议接入 vs Evolver CLI——我们该用哪个？

当前项目走 HTTP REST 直调（通用协议接入），Evolver CLI（`evolver_v1.89.13`）是备选方案。请回答：

- Evolver CLI 相比 HTTP 直调的**增量价值**是什么？
- Evolver CLI 对 Python/FastAPI 后端的**侵入性**多大？是否需要 Node.js 运行时？
- 如果继续用 HTTP 直调，是否遗漏了 Evolver CLI 提供的核心能力？
- **结论**：建议维持 HTTP 直调还是引入 Evolver CLI？为什么？

### 问题 2：自进化闭环——从评估到发布 Capsule 的完整链路

V1.0 每次 LLM 评估结果写入 `evaluations` 表，但尚未发布到 EvoMap Hub。请回答：

- 什么条件下触发 Capsule 发布？（评估次数阈值？置信度阈值？用户手动触发？）
- Capsule 的 `payload.assets` 应该包含什么？如何从 `evaluations` 表提取 Gene 和 Capsule 内容？
- 环境指纹（`env_fingerprint`）应该包含哪些维度？
- 记忆召回（`/a2a/memory/recall`）应该在什么时候调用？如何影响后续评估？

### 问题 3：路演叙事——如何在 5 分钟演示中展现自进化？

赛道 The Pearl 要求评委感知到"自进化"。请设计：

- 演示前预埋 n 条评估记录（让雷达图不是 0）
- 演示中做一次新评估 → 展示"学习后变得更聪明"的效果
- 雷达图五维指标的合理变化幅度
- 自进化面板的展示时序（先看初始状态 → 评估 → 看进化后状态）

### 问题 4：隐私方案验证

当前设计：敏感决策数据留本地，Hub 只传脱敏方法论。请验证：

- GEP 协议对 Gene/Capsule 的脱敏要求
- `EVOLVER_TRACE_LEVEL` 的配置建议
- 如何在 publish 时确保不泄露桐庐县具体地块数据

---

## 输出要求

交付物：`D:\Projects\Urban_Industry_Assistant\research\evomap_devkit_integration.md`

必须包含以下章节：

```markdown
# EvoMap 开发者套件集成研究报告

## 1. 接入方式对比（HTTP 直调 vs Evolver CLI）
## 2. 自进化闭环设计（评估→Capsule 发布→记忆召回）
## 3. 路演叙事方案（5 分钟自进化演示流程）
## 4. 隐私方案验证
## 5. 实施建议（按优先级排序的 TODO 清单）
```

每节必须引用原文行或工具行为作为证据，不能只写结论。

---

## 汇报要求

完成后将汇报写入 `D:\Projects\Urban_Industry_Assistant\outputs\handoffs\02_report_research_evomap_devkit.md`。

汇报只写摘要（3-5 句核心发现），完整内容在交付物中。

---

## 时间约束

45 分钟内完成。如时间不够，优先回答问题 1 和问题 2。
