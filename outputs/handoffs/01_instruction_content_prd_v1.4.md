# 指令：PRD v1.4 — 九宫格简化为单格高亮

**发出方**：Orchestrator  
**接收方**：内容 Agent  
**时间**：2026-06-19  
**项目**：Urban_Industry_Assistant  

---

## 任务背景

和洲决定：去掉周边 8 个格子的显示，鼠标悬停只高亮鼠标所在的那**一个**网格。交互从「3×3 九宫格」降为「单格高亮」。

这是产品简化决策，非技术问题——减少视觉干扰，让用户聚焦当前网格。

---

## 输入材料

- `specs/src/prd_v1.2.md`（当前 v1.3 内容）

---

## 你的任务

在 v1.3 基础上修订为 **v1.4**，仅改一处章节：

### 修改 §2.2「回退后的方案」→ 重命名为「单格高亮方案」

将 §2.2 的表格从九宫格规格改为单格高亮规格：

**旧表**（当前内容）：

| 维度 | 规格 |
|------|------|
| 触发 | mousemove 事件，throttle 200ms |
| 数据源 | `GET /api/map/ninegrid?lng={lng}&lat={lat}&zoom={zoom}` |
| 渲染 | 每次 mousemove 请求返回最多 9 格，新建 L.geoJSON 层覆盖旧层 |
| zoom 11-12 | 仅中心格（后端 radius=0） |
| zoom 13-18 | 3×3 九宫格（后端 radius=1） |
| 视觉 | 中心格 fillOpacity 0.45 / 蓝色边框，外围 8 格 fillOpacity 0.25 / 浅蓝边框 |
| 离开 | mouseout → 移除九宫格层 |

**新表**：

| 维度 | 规格 |
|------|------|
| 触发 | mousemove 事件，throttle 200ms |
| 数据源 | `GET /api/map/ninegrid?lng={lng}&lat={lat}&zoom={zoom}`（仍查 9 格以定位中心格，前端仅渲染第 1 个） |
| 渲染 | 取返回的第一个网格（cells[0]），创建单格 L.geoJSON 层 |
| 全 zoom | zoom 11-18 均只显示单格高亮 |
| 视觉 | 网格 fillOpacity 0.45，边框色调用 `getLandColor(land_type)` |
| 离开 | mouseout → 移除单格高亮层 |

### 同时更新

1. §2.4 交叉影响分析中「九宫格 mousemove」→ 改为「单格高亮 mousemove」
2. 验收标准 R1：改为「单格高亮 HTTP 查询恢复」
3. 版本修订记录追加 v1.4 行

---

## 输出要求

- 覆盖写入 `specs/src/prd_v1.2.md`（内容升级为 v1.4）
- 改动仅限 §2.2 + 关联引用
- 不改 sticky note 章节

---

## 汇报要求

完成后将汇报写入：`D:\Projects\Urban_Industry_Assistant\outputs\handoffs\01_report_content_prd_v1.4.md`

汇报写完后，告知主人"已完成，请查阅汇报文件"。
