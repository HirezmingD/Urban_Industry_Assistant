# 指令：架构设计 — 九宫格预加载回退，简化 mousemove 交互

**发出方**：Orchestrator  
**接收方**：架构 Agent  
**时间**：2026-06-19  
**项目**：Urban_Industry_Assistant  

---

## 任务背景

PRD v1.3 已将九宫格方案从「预加载 + setStyle」回退为「实时 HTTP 查询」。需更新架构设计文档，移除 `GridLayerManager` 及相关预加载架构，保留 sticky note 设计。

---

## 输入材料

- `specs/src/prd_v1.2.md`（已升级为 v1.3）— 尤其 §2.4 交叉影响分析
- `specs/arch/preload_sticky_design.md` — 当前架构文档（含预加载 + sticky note）

---

## 你的任务

### 任务 1：修订 `preload_sticky_design.md`

在该文档基础上做以下修改（保持文件名不变，内容升级）：

#### 1a. 删除预加载相关章节

移除以下内容：
- GridLayerManager 类设计（含构造函数、`_loadFull`、`_loadViewport`、`findGridAt`、`_computeNineGrid`、`highlightNineGrid`、`_cleanup`）
- 分级加载策略（zoom 11-14 全量 / zoom 15 视口 / zoom 16-18 按点）
- `GET /api/map/grid_layer` 端点前端调用设计
- 透明层样式状态机（setStyle 方案）

#### 1b. 保留 sticky note 设计

StickyNote 类设计、四方向定位逻辑、三角箭头、弹出动画全部保留，不改。

#### 1c. 新增「九宫格简化方案」章节

在文档开头（或 sticky note 之前）新增简短章节：

```markdown
## 九宫格鼠标悬停（v1.3 简化方案）

### 数据流

```
mousemove (throttle 200ms)
  → GET /api/map/ninegrid?lng={}&lat={}&zoom={}&role=government
  → 后端 query_nine_grid() 返回最多 9 格（含 coords）
  → 前端 renderNineGrid() 创建 L.geoJSON 层
```

### 前端组件

无独立类。逻辑内联在 `setupMouseInteraction()` 的 mousemove 事件处理器中：

- `_lastQueryTs` 变量做 200ms throttle
- `state.nineGridLayer` 存储当前九宫格 GeoJSON 层
- mouseout → `map.removeLayer(state.nineGridLayer)`
- zoom 11-12：后端 `_get_nine_grid_radius(zoom)` 返回 0，仅中心格
- zoom 13-18：后端返回 3×3 九宫格

### click → sticky note 回退路径

click 事件不再依赖 GridLayerManager.findGridAt。直接调用 HTTP API 获取 grid_id：

```
map.on('click')
  → GET /api/map/ninegrid?lng={}&lat={}&zoom={}
  → 取 cells[0].grid_id
  → GET /api/map/grid/{grid_id}
  → StickyNote.show(data, point)
```

### 后端端点

| 端点 | 用途 | 变更 |
|------|------|:--:|
| `GET /api/map/ninegrid` | 九宫格查询（已有） | 不变 |
| `GET /api/map/grid/{id}` | 单格详情（已有） | 不变 |
| `GET /api/map/grid_layer` | 轻量渔网层 | **保留但不调用**（为未来预留） |
```

#### 1d. 更新迁移表

将原有「旧代码 → 新代码」迁移表改为「删除清单 + 保留清单」：

| 代码单元 | 操作 |
|----------|:--:|
| `GridLayerManager` 类（app.js 约 80 行） | 删除 |
| `gridLayerManager` 全局变量 | 删除 |
| `new GridLayerManager(map)` 实例化 | 删除 |
| `map.on('zoomend', gridLayerManager.onZoomChange)` | 删除 |
| `gridLayerManager.onZoomChange(map.getZoom())` 初始调用 | 删除 |
| mousemove 中 `if (gridLayerManager...isActive)` 分支 | 删除（保留 HTTP fallback 部分） |
| mouseout 中 `gridLayerManager.highlightNineGrid(null)` | 删除 |
| mouseout 中 `gridLayerManager.highlightLayer` 清理 | 删除 |
| click 中 `gridLayerManager.findGridAt` 分支 | 删除（保留 HTTP fallback 部分） |
| `renderNineGrid()` 函数 | **保留**（成为主力） |
| `StickyNote` 类 | **保留**（不碰） |
| `loadGridLight()` 渔网精简层 | **保留**（不碰） |
| `setupDrawControl()` 框选 | **保留**（不碰） |

#### 1e. 更新文档元信息

在文档头部标注：基准 PRD v1.3 / 修订类型「回退 + 简化」/ 日期 2026-06-19。

### 任务 2（可选）：架构网关确认

以下改动类型无需新架构设计，可在后续实现指令中直接交付实现 Agent：

- [x] 纯代码删除（GridLayerManager 类 + 相关引用）
- [x] 现有 fallback 路径提升为主路径（不新增逻辑）
- [x] 不新增 API / 不改 schema / 不改变布局结构

---

## 输出要求

- 覆盖写入 `specs/arch/preload_sticky_design.md`（保持同名）
- sticky note 设计内容不丢失
- 迁移表准确完整（实现 Agent 可据此逐行删除）

---

## 汇报要求

完成后将汇报写入：`D:\Projects\Urban_Industry_Assistant\outputs\handoffs\04_report_arch_rollback_preload.md`

汇报写完后，告知主人"已完成，请查阅汇报文件"。
