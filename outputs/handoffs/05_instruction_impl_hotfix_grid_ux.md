# 批次 G 热修复：九宫格三问题——卡顿 + 重叠 + 点选

**指令编号**：05_hotfix_grid_ux  
**目标 Agent**：实现 Agent  
**优先级**：P0（交互体验）  
**预估耗时**：45 分钟  

---

## Bug 1：九宫格卡顿

### 根因

`app.js` mousemove 80ms throttle，每秒 ~12 次 API 往返。响应含 17 字段太肥。

### 修复

**文件**：`static/app.js`

```javascript
// 第 173 行
if (now - lastHoverTime < 80) return; // throttle
// 改为
if (now - lastHoverTime < 200) return;
```

**文件**：`src/services/grid_service.py` — `query_nine_grid()`

在 `_row_to_dict()` 返回后，精简 dict 仅保留渲染必需字段：

```python
# 在 return result 前
for d in result:
    # 仅保留前端渲染所需字段
    keep = {"grid_id", "min_lng", "min_lat", "max_lng", "max_lat", "geometry"}
    for k in list(d.keys()):
        if k not in keep:
            del d[k]
```

---

## Bug 2：网格矩形重叠

### 根因

前端 `renderNineGrid()` 用 `min_lng/max_lng` 重建矩形，但 WGS84 球面下网格不是矩形——投影转换后四个角微变形，bbbox 重建会产生重叠。

### 修复

**后端**：`query_nine_grid()` 返回真实多边形坐标（WKB → GeoJSON coords）。

在 `query_nine_grid()` 末尾，将 WKB geometry 转为坐标数组：

```python
from shapely import wkb
from shapely.geometry import mapping

def _wkb_to_coords(geometry_blob: bytes) -> list | None:
    if not geometry_blob:
        return None
    try:
        geom = wkb.loads(geometry_blob)
        return mapping(geom).get("coordinates")
    except Exception:
        return None
```

返回的每个 dict 中新增 `coords` 字段（替换 `geometry` 二进制）：

```python
for d in result:
    d["coords"] = _wkb_to_coords(d.pop("geometry", None))
```

**前端**：`renderNineGrid()` 改用 `coords` 而非 bbox 重建。

**文件**：`static/app.js`，`renderNineGrid()` 函数（第 192-206 行）

```javascript
// 当前：用 min_lng/min_lat/max_lng/max_lat 拼矩形
coordinates: [[
  [c.min_lng, c.min_lat], [c.max_lng, c.min_lat],
  [c.max_lng, c.max_lat], [c.min_lng, c.max_lat],
  [c.min_lng, c.min_lat],
]]

// 改为：直接用后端返回的真实坐标
geometry: {
  type: 'Polygon',
  coordinates: c.coords,
}
```

---

## Bug 3：地图点选无反应

### 需求

PRD v1.0 §3.1.4：点击地图上任意渔网单元 → 侧边栏展示该网格详情（用地类型、面积、权属、乡镇等）。

### 实现

**文件**：`static/app.js`

在 `initMap()` 中新增 click 事件（约第 88 行 `setupMouseHover()` 之后）：

```javascript
map.on('click', (e) => {
  if (state.role !== 'government') return;
  const { lat, lng } = e.latlng;
  const zoom = map.getZoom();
  fetch(`${API_BASE}/api/map/ninegrid?lng=${lng}&lat=${lat}&zoom=${zoom}&role=government`)
    .then(r => r.json())
    .then(cells => {
      if (!cells || cells.length === 0) return;
      const cell = cells[0]; // 中心格
      showGridDetail(cell);  // 新函数：侧边栏弹出详情
    })
    .catch(() => {});
});
```

新增 `showGridDetail()` 函数：

```javascript
function showGridDetail(cell) {
  // 在右侧面板顶部插入详情卡片
  const panel = document.getElementById('detail-panel');
  if (!panel) return;
  panel.innerHTML = `
    <div class="grid-detail">
      <h4>📍 网格 ${cell.grid_id}</h4>
      <p>用地类型：${cell.land_type || '未知'}</p>
      <p>面积：${(cell.area_sqm / 666.67).toFixed(1)} 亩</p>
      <p>权属：${cell.ownership || '—'}</p>
      <p>乡镇：${cell.town || '—'}</p>
      <p>混合地类：${cell.mixed_type || '无'}</p>
      <button onclick="document.getElementById('detail-panel').innerHTML=''">关闭</button>
    </div>
  `;
}
```

**文件**：`static/index.html`

在右侧面板区域加一个 `<div id="detail-panel"></div>`，放在三个标签页上方。

---

## 验证标准

| 项 | 标准 |
|------|------|
| 九宫格 hover | 不卡顿，鼠标快速移动时网格平滑跟随 |
| 网格无重叠 | zoom 14+ 放大看相邻网格边界，无重叠线 |
| 网格坐标正确 | 九宫格多边形形状匹配天地图底图 |
| 点选有反应 | 点击地图网格 → 侧边栏弹出详情卡片 |
| 点选详情正确 | land_type/town/ownership/area_mu 与数据库一致 |
| 不影响框选 | 点选和框选互不干扰 |

---

## 完成后

汇报写入 `D:\Projects\Urban_Industry_Assistant\outputs\handoffs\05_report_impl_hotfix_grid_ux.md`。
