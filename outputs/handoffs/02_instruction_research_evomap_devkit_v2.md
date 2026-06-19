# 研究指令：EvoMap 开发者套件 → Urban_Industry_Assistant 集成方案（修订版）

**发出方**：Orchestrator  
**接收方**：研究 Agent  
**时间**：2026-06-19  
**项目**：Urban_Industry_Assistant  
**指令编号**：02_supplement_v2  
**修订原因**：evomap_developer 源码到位后发现接入模式与旧版假设完全不同

---

## ⚠️ 重大发现（务必先读）

EvoMap 官方转发的 `evomap_developer` 仓库揭示了一个**全新的接入模式**：

| | 旧方案（A2A 协议） | 新方案（OAuth2 开发者平台） |
|------|------|------|
| 接入方式 | per-node 密钥（hello/heartbeat） | OAuth2 + PKCE（client_id/secret） |
| API 端点 | `/a2a/hello` `/a2a/heartbeat` `/a2a/publish` | `/developer/oauth/recipes` `/genes` `/reuse` |
| 认证 | Bearer `node_secret` | Bearer `access_token`（OAuth2） |
| 范围 | 节点级操作 | scope 授权（`recipe:read` `gene:read`等） |
| 测试模式 | 无 | ✅ test mode 沙箱（零真实副作用） |
| 黑客松 Demo | 无指引 | ✅ HACKATHON.md 含完整 10 分钟上手 |

**我们现有代码（`evo_service.py`）基于旧方案。本次研究的关键问题是：继续 A2A 还是切换到 OAuth2 平台？**

---

## 输入材料

### 开发者套件（必读）

| 路径 | 内容 |
|------|------|
| `D:\TOOLS\Evomap_wiki\evomap_developer\developers\README.zh-CN.md` | 开发者平台总览（中文） |
| `D:\TOOLS\Evomap_wiki\evomap_developer\developers\HACKATHON.md` | 黑客松 10 分钟上手（⭐ 核心） |
| `D:\TOOLS\Evomap_wiki\evomap_developer\developers\examples\quickstart\README.md` | Quickstart 说明 |
| `D:\TOOLS\Evomap_wiki\evomap_developer\developers\examples\quickstart\index.js` | OAuth2 PKCE + API 调用完整示例（Node.js） |
| `D:\TOOLS\Evomap_wiki\evomap_developer\developers\examples\quickstart\.env.example` | 环境变量模板 |

### 官方在线资源（必须查阅）

| URL | 内容 |
|------|------|
| `https://evomap.ai/dev/portal` | App 注册门户 |
| `https://evomap.ai/dev/docs` | 交互式 API 文档 |
| `https://evomap.ai/openapi.json` | OpenAPI 规范（机器可读） |

### 旧版 A2A 协议文档（对照参考）

| 路径 | 内容 |
|------|------|
| `D:\TOOLS\Evomap_wiki\docs\03-for-ai-agents.md` | Agent 接入指南（A2A 协议） |
| `D:\TOOLS\Evomap_wiki\docs\05-a2a-protocol.md` | A2A 协议细节 |
| `D:\TOOLS\Evomap_wiki\docs\16-gep-protocol.md` | Gene/Capsule/EvolutionEvent 数据模型 |

### 项目现有代码

| 路径 | 内容 |
|------|------|
| `D:\Projects\Urban_Industry_Assistant\src\services\evo_service.py` | 当前 EvoMap 服务（A2A 协议，需评估是否重写） |
| `D:\Projects\Urban_Industry_Assistant\src\api\evo_routes.py` | EvoMap API 路由 |
| `D:\Projects\Urban_Industry_Assistant\src\services\eval_service.py` | LLM 评估服务（需插入 gene/recipe 检索） |
| `D:\Projects\Urban_Industry_Assistant\specs\arch\architecture.md` | 系统架构 |
| `D:\Projects\Urban_Industry_Assistant\specs\src\prd.md` | PRD（含自进化展示面板需求） |

---

## 研究问题

### 问题 1：A2A 协议 vs OAuth2 开发者平台——我们该用哪个？

两个方案同时存在。请回答：

- 两个方案的关系是什么？（互补？替代？不同场景？）
- HACKATHON.md 明确推荐 OAuth2 平台用于黑客松——A2A 协议是否已过时？
- OAuth2 平台的 `recipe:read` `gene:read` `reuse:query` 三个 scope 能覆盖我们的需求吗？
- 如果需要"发布进化胶囊"（`recipe:publish`），是否需要申请开发者资格？
- **结论**：建议采用哪个方案？如果两个都保留，如何分工？

### 问题 2：「提示词增强器」模式如何嵌入我们的评估流程？

HACKATHON.md 的 Demo 是：用户需求 → 检索 EvoMap 可复用 recipe → 拼进增强 prompt → 喂给 LLM。

**这个模式与我们的 LLM 评估管线高度契合。** 请设计：

- 在 `eval_service.py` 的 `evaluate_grids()` 中，LLM 调用前插入 EvoMap 检索的正确位置
- 检索策略：用 `user_message` 做 recipe 全文搜（`/developer/oauth/recipes?q=...`）、再用 `genes` 做通用能力补充
- 检索结果如何注入 System Prompt 或 User Prompt（格式建议）
- 降级策略：EvoMap API 不可用时如何优雅降级（保持现有评估管线不受影响）

### 问题 3：OAuth2 PKCE 流程如何在 Python/FastAPI 中实现？

Quickstart 是 Node.js Express。我们需要 Python 版本：

- PKCE code_verifier / code_challenge 的生成逻辑
- 授权 URL 构造
- `/callback` 端点用 code 换 token
- Token 存储与刷新策略
- 是否需要一个 `/api/evomap/auth` 路由？还是启动时一次性授权？

### 问题 4：路演叙事——"从集体智能中学习"vs"本地自进化"

旧叙事：本地评估积累 → 发布 Capsule → 本地变聪明（单机自进化）

新叙事：搜索 EvoMap 价值网络 → 检索他人已验证的 recipe/gene → 注入评估 → **借助集体智能给出更优建议**（网络自进化）

请设计 5 分钟路演中的"自进化"演示时序：
- Step 1：关闭 EvoMap 检索 → 做一次评估（基线结果）
- Step 2：开启 EvoMap 检索 → 同一问题再做一次 → 展示"检索到 N 条相关经验，评估更精准"
- Step 3：自进化面板展示进化前后对比

### 问题 5：Test Mode —— 我们该怎么用？

- Test mode app 能否在路演中演示？（响应逼真但数据不碰线上）
- 是否需要准备 live mode 作为备选？
- Test mode 下 publish recipe 的行为是什么？

---

## 输出要求

交付物：`D:\Projects\Urban_Industry_Assistant\research\evomap_devkit_integration_v2.md`

必须包含：

```markdown
# EvoMap 开发者套件集成研究报告（修订版）

## 1. 接入方案选型（A2A vs OAuth2 开发者平台）
## 2. 提示词增强器集成设计（eval_service.py 改造方案）
## 3. Python OAuth2 PKCE 实现方案
## 4. 路演叙事设计（集体智能版自进化）
## 5. Test Mode 使用建议
## 6. 实施优先级清单（按 P0-P3 分级）
```

关键要求：
- 回答问题 1 时必须给出**明确的选型结论**，不能模棱两可
- 问题 2 必须给出**具体的代码插入位置**（文件+行号+伪代码）
- 所有设计必须引用原文（README/HACKATHON.md/quickstart 源码）作为证据

---

## 汇报要求

完成后将汇报写入 `D:\Projects\Urban_Industry_Assistant\outputs\handoffs\02_report_research_evomap_devkit_v2.md`。

汇报只写 3-5 句核心发现和选型结论。完整内容在交付物中。

---

## 时间约束

50 分钟内完成。优先问题 1 和问题 2。
