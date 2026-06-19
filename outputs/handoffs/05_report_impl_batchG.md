## 完成状态
✅ 完成

## 12 步清单
- [x] 1. database.py — L1-L5 建表 SQL + R-tree
- [x] 2. database.py — `land_grid` → `land_grid_L0` 重命名迁移（含 R-tree 同步）
- [x] 3. schemas.py — GridFeature 加 6 字段（min/max lng/lat, level, land_type_top3, grid_count_original）
- [x] 4. grid_service.py — `_ZOOM_TABLE_MAP` / `_get_table_for_zoom()` / `_get_nine_grid_radius()` / `_get_grid_deg_for_zoom()`
- [x] 5. grid_service.py — `query_by_bbox()` 加 `zoom` 参数 + 动态表名 + `_get_table_safe()` 降级
- [x] 6. grid_service.py — `query_nine_grid()` 加 `zoom` + zoom 11-12 单格模式
- [x] 7. grid_service.py — `_select_fields()` 加 `is_aggregated` 参数
- [x] 8. grid_service.py — `_row_to_dict()` 加 `is_aggregated` 参数
- [x] 9. api/map_routes.py — `/api/map/query` 加 `zoom` 查询参数
- [x] 10. api/map_routes.py — `/api/map/ninegrid` 加 `zoom` 查询参数
- [x] 11. `scripts/preprocess_fishnet_pyramid.py` — 新建并执行
- [x] 12. `app.js` — 框选/九宫格带 `zoom` + `zoomend` 刷新

## 预处理输出

| 表 | 网格数 | 预估数 |
|----|--------|--------|
| L1 (3200m) | 269 | ~200 |
| L2 (1600m) | 943 | ~800 |
| L3 (800m) | 3,558 | ~3,000 |
| L4 (400m) | 13,729 | ~12,000 |
| L5 (200m) | 53,837 | ~46,000 |

总耗时: **35s**（仅 L4-L5，L1-L3 另计 ~42s）

## 验证

| 验证项 | 结果 |
|--------|------|
| zoom 11 bbox | 60 格（3200m LOD） |
| zoom 16 bbox | 500 格（100m L0，截断） |
| 九宫格 zoom 12 | 1 格（单格模式） |
| 九宫格 zoom 14 | 9 格（3×3） |
| L0 表名 | `land_grid_L0` |
| 无 `land_grid` 残留 | ✅ |

## 踩坑记录
- `f-string` 中 SQL `DEFAULT '{}'` 被 Python 解析为空表达式 → 需转义为 `'{{}}'`
- grid_id 为原始编号（非行列号），空间分组改用 `center_lat/center_lng` 分箱
- WAL 模式跨连接 DELETE 锁表 → 改用 DROP TABLE + CREATE
