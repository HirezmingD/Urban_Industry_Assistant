# 批次 F：渔网数据接入后端——真实查询 + GeoJSON 返回

**指令编号**：05_impl_batchF  
**目标 Agent**：实现 Agent  
**优先级**：P0（没有这步，前端框选永远是 "0 个网格"）  
**预估耗时**：45 分钟  

---

## 背景

V1.2 渔网预处理已完成，`land_grid` 表有 185,564 条真实数据（含用地类型/权属/坐落/WKB 几何）。但 `grid_service.py` 的 `query_by_bbox()` 有两处问题导致前端看到的 GeoJSON 几何是简化矩形而非真实多边形：

1. `_select_fields()` 未包含 `geometry` 列
2. GeoJSON 构造用的是 bbox 四边形坐标，未解析 WKB

---

## 修改清单

### 改动 1：`src/services/grid_service.py` — `_select_fields()` 加 geometry 列

**当前**（第 46-50 行）：
```python
return (
    "grid_id, min_lng, min_lat, max_lng, max_lat, "
    "land_type, land_code, area_sqm, ownership, town, "
    "mixed_type, nl_mean, ndvi_mean, pm25_mean, extras"
)
```

**改为**：
```python
return (
    "grid_id, min_lng, min_lat, max_lng, max_lat, "
    "land_type, land_code, area_sqm, ownership, town, "
    "mixed_type, nl_mean, ndvi_mean, pm25_mean, "
    "geometry, extras"
)
```

### 改动 2：`src/services/grid_service.py` — GeoJSON 几何改从 WKB 解析

**当前**（第 151-172 行）：用 bbox 构造矩形 GeoJSON。

**改为**：从 `geometry` BLOB 字段解析 WKB → 转 GeoJSON 坐标。新增辅助函数：

```python
from shapely import wkb
from shapely.geometry import mapping

def _wkb_to_geojson_geometry(geometry_blob: bytes) -> dict | None:
    """WKB → GeoJSON geometry dict。"""
    if not geometry_blob:
        return None
    try:
        geom = wkb.loads(geometry_blob)
        return mapping(geom)
    except Exception:
        return None
```

然后 GeoJSON 构造改为：
```python
geojson["features"] = [
    {
        "type": "Feature",
        "properties": {
            "grid_id": r.get("grid_id"),
            "land_type": r.get("land_type"),
            "score": None,
        },
        "geometry": _wkb_to_geojson_geometry(r.get("geometry")),
    }
    for r in rows
    if r.get("geometry")
]
```

### 改动 3：`src/services/grid_service.py` — WKB 字段从 results 中移除

`_row_to_dict()` 返回的 dict 在传给前端 features 时不应包含二进制 `geometry` 字段。在 features 构建后移除（或在 `_row_to_dict` 中过滤 `geometry` 键）：

```python
# 在第 144 行 features 构建后：
for f in features:
    f.pop("geometry", None)  # 二进制 geometry 不传给前端 dict
```

### 改动 4：`src/services/grid_service.py` — Nine Grid 也返回真实几何

`query_nine_grid()` 只返回属性无几何。不需改——九宫格悬停用的是 `GridFeature` schema（不含几何），正确。但**确认九宫格查询现在能返回真实数据**（以前数据库空时返回 []）。

---

## 验证标准

| 项 | 标准 | 验证方法 |
|------|------|------|
| `_select_fields` 含 geometry | gov 端 SELECT 有 geometry 列 | read file |
| GeoJSON 坐标非矩形 | 检查坐标数组是否 > 5 个点（真多边形） | API 响应抽样 |
| bbox 查询有结果 | `GET /api/map/query?bbox=119.5,29.7,119.6,29.8&role=government` → `grid_count > 0` | curl 或浏览器 |
| 企业端不返回几何 | `role=enterprise` 时 geojson.features 为空 | curl |
| 性能 | bbox 查询 < 200ms | curl 计时 |
| 九宫格查询 | 鼠标悬停政府端地图有数据返回 | 前端实测 |

---

## 注意事项

- **不要在 _select_fields 的企业端分支加 geometry**——企业端不返回精确几何
- **WKB 解析失败不崩溃**——`_wkb_to_geojson_geometry` 已处理 None/异常，失败的 feature 跳过不返回
- **extras 字段**：JSON 字符串已在入库时存好，前端可以直接用 `JSON.parse()`
- **不碰 eval_service.py**——`get_grid_stats()` 已经用 SQL 聚合，数据到位后自动工作

---

## 完成后

汇报写入 `D:\Projects\Urban_Industry_Assistant\outputs\handoffs\05_report_impl_batchF.md`。

汇报格式：
```
## 完成状态
✅ / ❌

## 改动清单
- [x] grid_service.py: _select_fields 加 geometry
- [x] grid_service.py: GeoJSON 改从 WKB 解析
- [x] grid_service.py: features 中移除二进制 geometry

## API 验证
- bbox 查询 grid_count: (贴结果)
- GeoJSON 第一个 feature 坐标点数量: (应 > 5)
- 耗时: (ms)

## uvicorn 启动
(贴启动日志最后 5 行)
```
