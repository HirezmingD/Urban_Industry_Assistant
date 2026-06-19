# 指令：回退九宫格预加载 — 删除 GridLayerManager，恢复纯 HTTP 查询

**发出方**：Orchestrator  
**接收方**：实现 Agent  
**时间**：2026-06-19  
**项目**：Urban_Industry_Assistant  

---

## 任务背景

PRD v1.3 + 架构文档已确定回退方案。**仅改前端**，后端一个文件不动。

---

## 输入材料

- `specs/arch/preload_sticky_design.md` §3 迁移表（删除/保留清单）
- `static/app.js` — 当前代码（443 行）

---

## 你的任务

### 所有改动仅在 `static/app.js` 一个文件

---

### 改动 1：删除全局变量

**位置**：第 40 行

```javascript
// 旧
let map, gridLayerManager, stickyNote;

// 新
let map, stickyNote;
```

**位置**：第 41 行 — 删除整行

```javascript
let _lastHoverTs = 0;  // ← 删除此行（仅预加载路径使用）
```

---

### 改动 2：重写 `setupMouseInteraction()` 函数

**位置**：第 110-160 行（整个函数）

**替换为**：

```javascript
function setupMouseInteraction() {
  map.on('mousemove', (e) => {
    if (state.role !== 'government') return;
    const now = Date.now();
    if (now - _lastQueryTs < 200) return;
    _lastQueryTs = now;
    const { lat, lng } = e.latlng;
    const zoom = map.getZoom();
    fetch(`${API_BASE}/api/map/ninegrid?lng=${lng}&lat=${lat}&zoom=${zoom}&role=government`)
      .then(r => r.json()).then(cells => renderNineGrid(cells)).catch(() => {});
  });

  map.on('mouseout', () => {
    if (state.nineGridLayer) { map.removeLayer(state.nineGridLayer); state.nineGridLayer = null; }
  });

  map.on('click', async (e) => {
    if (state.role !== 'government') return;
    const { lat, lng } = e.latlng;
    const zoom = map.getZoom();
    let gridId;
    try {
      const cells = await (await fetch(`${API_BASE}/api/map/ninegrid?lng=${lng}&lat=${lat}&zoom=${zoom}&role=government`)).json();
      gridId = cells[0]?.grid_id;
    } catch {}
    if (!gridId) { stickyNote.hide(); return; }
    try {
      const r = await fetch(`${API_BASE}/api/map/grid/${gridId}?role=government`);
      if (!r.ok) return;
      const data = await r.json();
      data.level = [11,12,13,14,15].reduce((a,z,i) => zoom<=z?i+1:a, 0);
      const point = map.latLngToContainerPoint(e.latlng);
      stickyNote.toggle(data, point);
    } catch {}
  });
}
```

---

### 改动 3：删除 `GridLayerManager` 类

**位置**：第 297-374 行 — 整个类定义（含 `_loadFull`、`_loadViewport`、`highlightNineGrid`、`findGridAt`、`_computeNineGrid`、`_cleanup`），全部删除。

> **确认范围**：从 `// ===== 12. GridLayerManager` 注释块开始，到 `// ===== 13. StickyNote` 注释块之前结束。

---

### 改动 4：清理 `DOMContentLoaded` 中的 GridLayerManager 引用

**位置**：第 435 行 — 删除

```javascript
gridLayerManager = new GridLayerManager(map);  // ← 删除
```

**位置**：第 437 行 — zoomend 回调中删除预加载触发

```javascript
// 旧
map.on('zoomend', () => { const z = map.getZoom(); gridLayerManager.onZoomChange(z); if (state.currentBbox) handleBboxQuery(state.currentBbox); });

// 新
map.on('zoomend', () => { if (state.currentBbox) handleBboxQuery(state.currentBbox); });
```

**位置**：第 438 行 — 删除

```javascript
gridLayerManager.onZoomChange(map.getZoom());  // ← 删除
```

---

### 不改的代码（逐条确认）

| 代码单元 | 确认 |
|----------|:--:|
| `renderNineGrid()` 函数 | ✅ 保留（主力渲染） |
| `state.nineGridLayer` | ✅ 保留 |
| `_lastQueryTs` 变量 | ✅ 保留（200ms throttle） |
| `StickyNote` 类 + `stickyNote` 变量 + 实例化 | ✅ 保留 |
| `loadGridLight()` 渔网精简层 | ✅ 保留 |
| `setupDrawControl()` 框选 | ✅ 保留 |
| 所有后端 API（含 `grid_layer`） | ✅ 不动 |
| `stickyNote = new StickyNote('map')`（第 436 行） | ✅ 保留 |

---

## 输出要求

- 仅修改 `static/app.js` 一个文件
- 无新增文件
- 净删除约 90 行，净新增约 15 行

---

## 验证

浏览器 `Ctrl+Shift+R`：

- [ ] zoom 12-14 鼠标移动 → 九宫格出现（HTTP API + renderNineGrid）
- [ ] 鼠标移出 → 九宫格消失
- [ ] 点击网格 → sticky note 弹出
- [ ] 点"评估此地块" → 跳到对话 tab 正确评估
- [ ] Console 无红色报错
- [ ] `gridLayerManager` 全文件搜索结果为 0

---

## 汇报要求

完成后将汇报写入：`D:\Projects\Urban_Industry_Assistant\outputs\handoffs\05_report_impl_rollback_preload.md`

汇报写完后，告知主人"已完成，请查阅汇报文件"。
