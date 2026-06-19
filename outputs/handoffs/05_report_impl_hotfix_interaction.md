## 完成状态
✅ 完成

## 改动清单
- [x] `grid_service.py` `query_nine_grid()`: 返回前移除 dict 中二进制 `geometry` 字段
- [x] `grid_service.py` `query_nine_grid()`: 修复 JOIN rtree 导致 `ambiguous column name` 的 bug（改直接查 land_grid）
- [x] `app.js` `initMap()`: `minZoom` 10 → 11

## 验证结果
- 九宫格查询返回 **9** 格（完整 3×3） ✅
- dict 无 bytes 字段，JSON 序列化正常 ✅
- dict 无 `geometry` 键 ✅
