# 指令：九宫格渲染方案修复（setStyle → 可见高亮层）

**发出方**：Orchestrator
**接收方**：实现 Agent
**时间**：2026-06-19
**项目**：Urban_Industry_Assistant

---

## 任务背景

九宫格鼠标悬停效果至今未出现。Orchestrator 已完成三轮浏览器端诊断，定位根因：

1. `GridLayerManager.isActive = true` ✅
2. `gridIndex.size = 943` ✅（透明网格层已加载）
3. `findGridAt` 全量 HIT ✅（空间定位正常）
4. HTTP 九宫格 API 返回 200 ✅（回退路径正常）
5. **CSS 诊断**：`fill-opacity: 0`、`stroke: none`——`setStyle` 更新了 Leaflet options 但 **DOM CSS style 未同步**

**根因**：Leaflet 在初始 `opacity: 0` + `stroke: false` 的条件下，后续 `setStyle({ fillOpacity: 0.45, stroke: true, opacity: 1 })` 不更新 DOM 元素的内联样式，导致视觉上永远不可见。

**修复方案**：放弃 `setStyle` 改样式，改为每次鼠标悬停时**新建一个可见的 GeoJSON 高亮层**，叠加在透明索引层上方。透明层仅作空间索引，不参与渲染。

---

## 输入材料

- `static/app.js` — GridLayerManager 类（第 297-341 行）+ setupMouseInteraction（第 110-134 行）

---

## 你的任务

改 3 个位置，全部在 `static/app.js`：

### 任务 1：构造函数加字段

在 `GridLayerManager` 构造函数中，`this.gridLayer = null` 后面加一行：

```javascript
this.highlightLayer = null;
```

### 任务 2：重写 `highlightNineGrid`

将约第 321-328 行的 `highlightNineGrid` **整个替换**为：

```javascript
  highlightNineGrid(centerGridId, zoom) {
    // 清除上一次高亮
    if (this.highlightLayer) { this.map.removeLayer(this.highlightLayer); this.highlightLayer = null; }
    if (!this.isActive || !centerGridId) return;

    const nineIds = this._computeNineGrid(centerGridId, zoom);
    const features = [];
    nineIds.forEach((id, i) => {
      const l = this.gridIndex.get(id);
      if (!l || !l.feature || !l.feature.geometry) return;
      features.push({
        type: 'Feature',
        properties: {
          isCenter: i === 0,
          land_type: l.feature.properties.land_type,
        },
        geometry: l.feature.geometry,
      });
    });
    if (features.length === 0) return;

    this.highlightLayer = L.geoJSON(
      { type: 'FeatureCollection', features },
      {
        style: (f) => ({
          fillOpacity: f.properties.isCenter ? 0.45 : 0.25,
          fillColor: getLandColor(f.properties.land_type),
          color: getLandColor(f.properties.land_type),
          weight: f.properties.isCenter ? 2 : 1,
        }),
      }
    ).addTo(this.map);
  }
```

### 任务 3：`_cleanup` 和 `mouseout` 增加清除

**3a**：在 `_cleanup()` 方法开头加一行：

```javascript
if (this.highlightLayer) { this.map.removeLayer(this.highlightLayer); this.highlightLayer = null; }
```

**3b**：在 `setupMouseInteraction()` 的 `map.on('mouseout', ...)` 处理函数末尾加：

```javascript
if (gridLayerManager && gridLayerManager.highlightLayer) {
  gridLayerManager.map.removeLayer(gridLayerManager.highlightLayer);
  gridLayerManager.highlightLayer = null;
}
```

---

## 输出要求

- 改完 `app.js` 即可，无新增文件
- Python 后端不动
- 保持 `renderNineGrid`（HTTP 回退路径）不变

---

## 验证

浏览器 `Ctrl+Shift+R`：

- [ ] zoom 12-14 鼠标移动 → 彩色九宫格出现（中心 45% + 周围 8 格 25%）
- [ ] 鼠标移出地图 → 九宫格消失
- [ ] zoom 15-18 HTTP 回退也正常
- [ ] Console 无红色报错

---

## 汇报要求

完成后将汇报写入：`D:\Projects\Urban_Industry_Assistant\outputs\handoffs\05_report_impl_hotfix_ninegrid_render.md`

汇报写完后，**告知主人"已完成，请查阅汇报文件"**。
