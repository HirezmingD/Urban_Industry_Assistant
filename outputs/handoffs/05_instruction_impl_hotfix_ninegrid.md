# 批次 F 热修复：九宫格悬停不显示（最终定位）

**指令编号**：05_hotfix_ninegrid  
**目标 Agent**：实现 Agent  
**优先级**：P0  
**预估耗时**：5 分钟  

---

## 根因

前面清掉了 `geometry` 二进制字段，但九宫格依然不显示。最终定位：**`GridFeature` 模型缺少坐标字段**。

```
query_nine_grid() 返回 dict:
  {grid_id, min_lng, min_lat, max_lng, max_lat, land_type, ...}

  ↓ FastAPI response_model=list[GridFeature]

GridFeature 只定义了:
  grid_id, land_type, area_sqm, ownership, town, mixed_type,
  nl_mean, ndvi_mean, pm25_mean
  ← 没有 min_lng/min_lat/max_lng/max_lat！

  ↓ min_lng等4个字段被 Pydantic 过滤

前端 renderNineGrid() 读 c.min_lng → undefined
  → GeoJSON 坐标 [undefined, undefined, ...] → Polygon 退化 → 不可见
```

---

## 修复

**文件**：`src/schemas.py`  
**位置**：`GridFeature` 类（约第 265 行）

```python
class GridFeature(BaseModel):
    grid_id: str
    land_type: str
    area_sqm: float = 10000.0
    ownership: Optional[str] = None
    town: str = ""
    mixed_type: Optional[str] = None
    nl_mean: Optional[float] = None
    ndvi_mean: Optional[float] = None
    pm25_mean: Optional[float] = None
```

**在后面加 4 个字段**：

```python
class GridFeature(BaseModel):
    grid_id: str
    land_type: str
    area_sqm: float = 10000.0
    ownership: Optional[str] = None
    town: str = ""
    mixed_type: Optional[str] = None
    nl_mean: Optional[float] = None
    ndvi_mean: Optional[float] = None
    pm25_mean: Optional[float] = None
    min_lng: Optional[float] = None   # ← 新增
    min_lat: Optional[float] = None   # ← 新增
    max_lng: Optional[float] = None   # ← 新增
    max_lat: Optional[float] = None   # ← 新增
```

---

## 验证

重启 uvicorn，政府端鼠标滑过地图 → 应出现 3×3 九宫格。

---

## 完成后

汇报写入 `05_report_impl_hotfix_ninegrid.md`（一行即可：✅/❌）。
