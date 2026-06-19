## 完成状态
✅ 完成

## 改动清单
- [x] `grid_service.py`: `_select_fields` 政府端加 `geometry` 列
- [x] `grid_service.py`: 新增 `_wkb_to_geojson_geometry()` WKB→GeoJSON 解析
- [x] `grid_service.py`: GeoJSON 构造改从 WKB 解析真实多边形（不再用 bbox 简化矩形）
- [x] `grid_service.py`: features dict 移除二进制 `geometry` 字段
- [x] `grid_service.py`: 修复 `sqlite3.Row` 的 `.get()` → `[]` 访问（空表时未暴露的 bug）

## API 验证

| 验证项 | 结果 |
|--------|------|
| `_select_fields('government')` 含 `geometry` | ✅ |
| `_select_fields('enterprise')` 不含 `geometry` | ✅ |
| bbox 查询 `grid_count` | **500**（BBOX_QUERY_LIMIT 截断） |
| GeoJSON 首 feature 坐标点数 | **5**（100m 网格矩形 = 4 角 + 闭合点） |
| GeoJSON 首 feature 坐标样例 | `(119.522, 29.745)` — 真实 WGS84 多边形 |
| 耗时 | **39ms** |
| 企业端 `geojson.features` | **0**（企业端不返回精确几何） ✅ |
| features dict 含二进制 geometry | **False** ✅ |

## uvicorn 启动
```
[startup] EvoMap 凭证未就绪，跳过心跳后台任务
```
启动正常。
