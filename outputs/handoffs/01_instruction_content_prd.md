# 指令：编写 Urban_Industry_Assistant 产品需求文档（PRD）

**发出方**：Orchestrator
**接收方**：内容 Agent
**时间**：2026-06-18
**项目**：Urban_Industry_Assistant

---

## 任务背景

Urban_Industry_Assistant 是一个面向县域政府的产业用地智能评估 Agent，用于黑客松比赛（The Pearl·自进化赛道，19 日中午—21 日中午）。研究 Agent 已完成数据源、政策和 EvoMap 技术摸底，现在需要将需求固化为可验收的 PRD。

本项目在整体流程中的位置：**研究完成 → 需求固化 → 下一阶段架构 Agent 依据 PRD 设计系统架构**。

---

## 输入材料

- `D:\Projects\Urban_Industry_Assistant\outputs\PPT_方案_城市用地价值评估与产业适配Agent.md` — 项目理念、场景、自进化叙事
- `D:\Projects\Urban_Industry_Assistant\outputs\开发流程_内部方案.md` — 开发流程、技术栈、架构草图
- `D:\Projects\Urban_Industry_Assistant\research\evomap_integration_plan.md` — EvoMap 最小接入方案（注册→心跳→发布）
- `D:\Projects\Urban_Industry_Assistant\research\tonglu_data_sources.md` — 数据源摸底（夜间灯光/PM2.5/NDVI 等）
- `D:\Projects\Urban_Industry_Assistant\research\tonglu_policy_research.md` — 四级产业政策体系 + 七维评估模型

---

## 你的任务

编写一份完整的 PRD，覆盖以下内容：

### 1. 产品概述
- 产品定位一句话
- 目标用户说明
- 核心价值主张

### 2. 用户画像与场景

**政府端用户**：
- 角色：县级政府规划/经信部门人员
- 场景 A：框选地块 → 查看评估结果（地块属性、周边可用地、产业适配评分）
- 场景 B：从企业列表多选企业 → AI 给出针对所选企业集合的全域最优用地匹配
- 场景 C：对话框打字描述发展需求 → AI 给出发展分析建议 + 地图高亮候选地块 + 降序列表
- 数据权限：可访问三调保密数据

**企业端用户**：
- 角色：中小企业主
- 场景 D：录入企业信息（行业、面积需求、区位偏好、配套要求）
- 场景 E：对话框打字描述需求 → AI 给出针对该企业的个体最优建议
- 数据权限：仅公开数据，不做用地匹配

### 3. 功能需求（具体到交互细节）

**3.1 地图面板**
- 底图：卫星图瓦片
- 叠加层：三调矢量图斑（GeoJSON），按用地性质着色
- 交互：框选（绘制矩形）→ 范围内图斑高亮；点选 → 单个图斑弹窗显示属性
- 匹配时：候选地块高亮 + 气泡标签（序号、面积、性质、评分）

**3.2 对话面板**
- 输入框支持自然语言
- Agent 回复结构：评估摘要 → 评分卡片 → 推荐列表 → 政策依据引用

**3.3 企业面板**
- 企业列表（可搜索、可多选，支持 Shift/Ctrl 批量）
- 选中企业以标签形式显示在顶部
- 点击"分析选中企业"→ 触发全域最优匹配

**3.4 状态面板**
- EvoMap 节点状态（在线/离线）
- 已发布 Capsule 数量
- 最近一次进化时间

### 4. 非功能需求
- 响应时间：地图查询 < 0.5s，LLM 评估 < 15s
- 并发：支持 2-3 人同时访问（比赛场景）
- 浏览器兼容：Chrome / Edge

### 5. 数据需求
- 列出所有需要的数据及其来源（引用 tonglu_data_sources.md）
- 标注每个数据的加载方式（GeoJSON 直读 / SQLite 查询 / 实时 API）

### 6. 验收标准（必须可量化）

格式示例：
```
| 验收项 | 验收标准 | 验证方式 |
|--------|---------|---------|
| 地图框选 | 框选 1 秒内返回范围内图斑数量 | 手动操作计时 |
| 对话评估 | 输入"城东30亩适合什么产业"，15秒内返回结构化结果 | 手动测试 |
```

---

## 输出要求

- 交付物路径：`D:\Projects\Urban_Industry_Assistant\specs\src\prd.md`
- 格式要求：Markdown，分章节，每章用 `##` 标题
- 必须包含：
  - 用户画像中的每个场景有完整的操作流程描述（从用户打开页面到看到结果的每一步）
  - 功能需求中对两个端的差异明确标注（政府端 vs 企业端）
  - 验收标准全部可量化（"能跑通"这类描述不可接受，要具体到操作和时间）

---

## 汇报要求

完成后将汇报写入：`D:\Projects\Urban_Industry_Assistant\outputs\handoffs\01_report_content_prd.md`
汇报写完后，告知主人"已完成，请查阅汇报文件"。
