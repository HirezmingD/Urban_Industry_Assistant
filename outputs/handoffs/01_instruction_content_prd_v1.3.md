# 指令：PRD v1.3 — 回退九宫格预加载方案，恢复实时 HTTP 查询

**发出方**：Orchestrator  
**接收方**：内容 Agent  
**时间**：2026-06-19  
**项目**：Urban_Industry_Assistant  

---

## 任务背景

PRD v1.2 的「修订 1：九宫格预加载 + 透明切换」在浏览器实测中发现两个致命问题：

1. **Leaflet DOM 同步缺陷**：透明层（opacity:0）上 `setStyle` 不更新 DOM CSS，视觉不可见
2. **性能反而更差**：改用工建可见高亮层方案后，每次 mousemove 需遍历 943 个图层匹配网格→提取 geometry→新建 GeoJSON 层，远慢于 v1.0 的轻量 HTTP 查询 + 创建 9 格图层

v1.0 方案（mousemove → throttle 200ms → HTTP `/api/map/ninegrid` → render 9 格 GeoJSON）反而丝滑流畅。**决定回退**。

---

## 输入材料

- `specs/src/prd_v1.2.md` — 当前 PRD（需修订）
- `specs/src/prd.md`（v1.0）— 原始九宫格定义参考

---

## 你的任务

将 `specs/src/prd_v1.2.md` 修订为 **v1.3**，具体操作：

### 1. 删除「修订 1」

删除 §1.1 到 §1.8（第 21-160 行）全部内容，包含：
- 1.1 功能定位
- 1.2 方案对比
- 1.3 分级加载策略
- 1.4 预加载执行流程
- 1.5 悬停样式切换机制（含 setStyle 伪代码）
- 1.6 新增 API 端点（GET /api/map/grid_layer）
- 1.7 性能指标
- 1.8 端差异

### 2. 原「修订 2」→ 重编号为「修订 1」

将 §2（点选弹窗 sticky note）从「修订 2」重编号为「修订 1」。内部子编号保持（2.1→1.1, 2.2→1.2, …），或直接去子编号用平铺标题。

### 3. 新增「修订 2」：九宫格方案回退说明

在 sticky note 章节之后，新增简短回退说明：

```markdown
## 修订 2：九宫格方案回退——恢复实时 HTTP 查询

### 2.1 回退原因

v1.2 预加载 + setStyle 方案在浏览器实测中暴露出两个致命缺陷：
1. Leaflet 透明层 setStyle 不更新 DOM CSS（样式同步缺陷）
2. 替代方案（每次 mousemove 新建可见 GeoJSON 层）反而比 HTTP 查询更卡

### 2.2 回退后的方案

恢复 v1.0 原始方案：

| 维度 | 规格 |
|------|------|
| 触发 | mousemove 事件，throttle 200ms |
| 数据源 | `GET /api/map/ninegrid?lng={lng}&lat={lat}&zoom={zoom}` |
| 渲染 | 每次 mousemove 请求返回最多 9 格，新建 L.geoJSON 层覆盖旧层 |
| zoom 11-12 | 仅中心格（后端 radius=0） |
| zoom 13-18 | 3×3 九宫格（后端 radius=1） |
| 视觉 | 中心格 fillOpacity 0.45 / 蓝色边框，外围 8 格 fillOpacity 0.25 / 浅蓝边框 |
| 离开 | mouseout → 移除九宫格层 |

### 2.3 保留项

`GET /api/map/grid_layer` 后端端点保留（不删除），为未来可能的行政区划悬停高亮、离线导出等需求预留接口。前端不再调用。

### 2.4 交叉影响分析（回退影响面）

回退砍掉的是 `GridLayerManager` 前端类（约 80 行），影响面如下：

| 受影响功能 | 当前如何依赖 GridLayerManager | 回退后走什么路径 | 是否引入新风险 |
|-----------|------------------------------|-----------------|:--:|
| 九宫格 mousemove | `isActive` → `findGridAt` → `highlightNineGrid` | 直接走 HTTP fallback：`GET /api/map/ninegrid` + `renderNineGrid()` | ❌ 无风险（回退路径已验证可用） |
| 九宫格 mouseout | `highlightNineGrid(null)` + `highlightLayer` 清理 | 仅保留 `state.nineGridLayer` 移除 | ❌ 无风险（清理逻辑更简单） |
| click → sticky note | `findGridAt` 获取 grid_id | HTTP fallback：`GET /api/map/ninegrid` → `cells[0].grid_id` | ❌ 无风险（已有 fallback） |
| zoomend 事件 | `onZoomChange(zoom)` 触发预加载 | 删除回调，无操作 | ❌ 无风险（无副作用） |

**不受影响的功能**（独立路径，不碰）：

| 功能 | 原因 |
|------|------|
| `renderNineGrid()` | 独立函数，HTTP 九宫格渲染——回退后成为主力 |
| StickyNote 类 | 不引用 GridLayerManager，仅接收 gridData + point |
| "评估此地块"按钮 | 发消息 → `chat()` 正则提取 grid_id，完全独立 |
| `loadGridLight()` 渔网精简层 | 独立的静态 GeoJSON 层，与预加载无关 |
| `setupDrawControl()` 框选 | 独立的 Leaflet.Draw，与九宫格无关 |
| 所有后端 API | 一个不动（包括 `grid_layer` 端点保留） |

**结论**：回退是净删除，所有受影响路径都有现成且已验证的 HTTP 回退，不引入新 bug。
```

### 4. 更新版本修订记录

在版本修订记录表中新增：

```
| v1.3 | 2026-06-19 | 回退九宫格预加载方案，恢复实时 HTTP 查询；原修订 2（sticky note）保留为重编号修订 1 | 和洲 → Orchestrator → 内容 Agent |
```

### 5. 更新基准版本声明

将文件头部「目标版本：v1.2」改为「目标版本：v1.3」，修订类型改为「回退 + 重编号」。

---

## 输出要求

- 覆盖写入 `specs/src/prd_v1.2.md`（保持同名，内容升级为 v1.3）
- 改动范围仅限上述 5 项，不动 sticky note 章节的内容
- 不改 v1.0（`specs/src/prd.md`）和 v1.1（`specs/src/prd_v1.1.md`）

---

## 汇报要求

完成后将汇报写入：`D:\Projects\Urban_Industry_Assistant\outputs\handoffs\01_report_content_prd_v1.3.md`

汇报写完后，告知主人"已完成，请查阅汇报文件"。
