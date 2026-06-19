# 指令：九宫格简化为单格高亮 — renderNineGrid → renderSingleGrid

**发出方**：Orchestrator  
**接收方**：实现 Agent  
**时间**：2026-06-19  
**项目**：Urban_Industry_Assistant  

---

## 任务背景

PRD v1.4 + 架构文档：鼠标悬停从 3×3 九宫格简化为单格高亮。后端 `/api/map/ninegrid` 不变（仍返回 ≤9 格），前端仅取 `cells[0]` 渲染。

---

## 输入材料

- `specs/arch/preload_sticky_design.md` §1（单格悬停简化方案）
- `static/app.js`（当前 351 行）

---

## 你的任务

**仅改 `static/app.js`**

---

### 改动 1：state 变量重命名

**位置**：约第 33 行

```javascript
// 旧
nineGridLayer: null,

// 新
highlightLayer: null,
```

---

### 改动 2：mousemove 中仅渲染 cells[0]

**位置**：`setupMouseInteraction()` 内 mousemove 处理器，约第 117-118 行

```javascript
// 旧
fetch(`${API_BASE}/api/map/ninegrid?...`)
  .then(r => r.json()).then(cells => renderNineGrid(cells)).catch(() => {});

// 新
fetch(`${API_BASE}/api/map/ninegrid?...`)
  .then(r => r.json())
  .then(cells => {
    if (!cells || cells.length === 0) return;
    renderSingleGrid(cells[0]);
  })
  .catch(() => {});
```

---

### 改动 3：mouseout 变量名同步

**位置**：约第 121-122 行

```javascript
// 旧
if (state.nineGridLayer) { map.removeLayer(state.nineGridLayer); state.nineGridLayer = null; }

// 新
if (state.highlightLayer) { map.removeLayer(state.highlightLayer); state.highlightLayer = null; }
```

---

### 改动 4：替换 `renderNineGrid` → `renderSingleGrid`

**位置**：约第 146-160 行

**删除**整个 `renderNineGrid` 函数，**替换**为：

```javascript
function renderSingleGrid(cell) {
  if (state.highlightLayer) { map.removeLayer(state.highlightLayer); state.highlightLayer = null; }
  if (!cell || !cell.coords) return;
  state.highlightLayer = L.geoJSON({
    type: 'Feature',
    properties: { grid_id: cell.grid_id },
    geometry: { type: 'Polygon', coordinates: cell.coords },
  }, {
    style: {
      fillOpacity: 0.45,
      fillColor: getLandColor(cell.land_type || ''),
      color: getLandColor(cell.land_type || ''),
      weight: 2,
    },
  }).addTo(map);
}
```

---

### 不改的代码

| 代码 | 说明 |
|------|------|
| click 事件（`cells[0]?.grid_id`） | 本身就用 cells[0]，不变 |
| StickyNote 类 | 不碰 |
| 后端 API | 不碰 |
| 所有其他功能 | 不碰 |

---

## 验证

- [ ] 鼠标移动 → 仅显示 1 个网格高亮（不是 9 个）
- [ ] 高亮跟随鼠标移动
- [ ] mouseout → 高亮消失
- [ ] click → sticky note 正常弹出
- [ ] "评估此地块" 正常工作
- [ ] Console 无报错
- [ ] `nineGridLayer` 全文件搜索结果为 0
- [ ] `renderNineGrid` 全文件搜索结果为 0

---

## 汇报要求

完成后将汇报写入：`D:\Projects\Urban_Industry_Assistant\outputs\handoffs\05_report_impl_single_grid.md`
