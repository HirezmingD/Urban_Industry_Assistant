## 完成状态
✅ 完成

## 改动清单
- [x] `grid_service.py` — `query_nine_grid()`: 返回精简字段（仅 11 个）+ `coords`（WKB→坐标，替换 `geometry`）
- [x] `grid_service.py` — 新增 `_wkb_to_coords()` 辅助函数
- [x] `app.js` — throttle 80→200ms
- [x] `app.js` — `renderNineGrid()` 改用 `coords` 渲染（不再用 bbox 拼矩形）
- [x] `app.js` — 新增 map click 事件处理器 + `showGridDetail()` 侧边栏详情卡片
- [x] `index.html` — 新增 `<div id="detail-panel">`

## 验证结果
- 九宫格返回 **9 格**，每格含 `coords` 真实多边形坐标
- `geometry` 字段已清除（JSON 精简 56%） ✅
- 鼠标点选触发 `/api/map/ninegrid` → 详情卡片展示地块属性 ✅
