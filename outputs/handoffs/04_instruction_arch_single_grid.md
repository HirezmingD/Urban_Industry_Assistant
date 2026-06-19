# 指令：架构调整 — 九宫格简化为单格高亮

**发出方**：Orchestrator  
**接收方**：架构 Agent  
**时间**：2026-06-19  
**项目**：Urban_Industry_Assistant  

---

## 任务背景

PRD v1.4：鼠标悬停从「3×3 九宫格」简化为「单格高亮」。后端 `/api/map/ninegrid` 不变（仍返回最多 9 格），前端仅取 `cells[0]` 渲染。

---

## 输入材料

- `specs/src/prd_v1.2.md`（v1.4 内容）§2.2 单格高亮方案
- `specs/arch/preload_sticky_design.md`（当前架构文档）

---

## 你的任务

修订 `specs/arch/preload_sticky_design.md`：

### 1. 更新 §1.1 数据流

```
mousemove (throttle 200ms)
  → GET /api/map/ninegrid?lng={}&lat={}&zoom={}&role=government
  → 后端 query_nine_grid() 返回 ≤9 格
  → 前端取 cells[0]，渲染单格 L.geoJSON 层
  → mouseout → 移除单格高亮层
```

### 2. 更新 §1.2 前端组件

mousemove 中的 `renderNineGrid(cells)` 改为仅渲染 `cells[0]`：

```javascript
// mousemove 内：
fetch(`/api/map/ninegrid?...`)
  .then(r => r.json())
  .then(cells => {
    if (!cells || cells.length === 0) return;
    renderSingleGrid(cells[0]);
  })
  .catch(() => {});
```

新增 `renderSingleGrid(cell)` 函数签名（替代 `renderNineGrid` 的批量渲染逻辑）：

```javascript
function renderSingleGrid(cell) {
  if (state.nineGridLayer) map.removeLayer(state.nineGridLayer);
  if (!cell || !cell.coords) return;
  state.nineGridLayer = L.geoJSON({
    type: 'Feature',
    properties: { grid_id: cell.grid_id },
    geometry: { type: 'Polygon', coordinates: cell.coords },
  }, {
    style: {
      fillOpacity: 0.45,
      fillColor: getLandColor(cell.land_type),
      color: getLandColor(cell.land_type),
      weight: 2,
    },
  }).addTo(map);
}
```

### 3. 更新保留清单

- `renderNineGrid()` 函数：标注为「**重构**：改为仅渲染 cells[0]，或新增 `renderSingleGrid` 替代」
- `state.nineGridLayer` → 标注为 `state.highlightLayer`（可选重命名，兼容旧名也可）

### 4. 更新文档元信息

头部基准 PRD → v1.4，日期 → 2026-06-19

---

## 输出要求

- 覆盖写入 `specs/arch/preload_sticky_design.md`
- 仅改 §1 九宫格简化方案章节 + 关联引用
- sticky note 章节不动

---

## 汇报要求

完成后将汇报写入：`D:\Projects\Urban_Industry_Assistant\outputs\handoffs\04_report_arch_single_grid.md`
