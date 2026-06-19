# 架构补充决议：边界碎格处理方案

**关联指令**：04_arch_lod_pyramid  
**时间**：2026-06-19  

---

## 问题

桐庐渔网覆盖县域不规则边界。N×N 矩形聚合在边界处产生"碎格"——凑不满完整 N×N 矩形的剩余网格。

## 决议

**边界碎格合并为不规则多边形，作为一个聚合网格参与 LOD。**

### 算法补充

```
Step 1: 按 N×N 规则划分 → 完整的 N×N 块（矩形几何）
Step 2: 收集不在任何完整块内的剩余网格
Step 3: 将剩余网格按空间邻近合并为不规则多边形（ST_Union）
Step 4: 每个不规则多边形作为一条聚合记录入库
  - geometry = Union 后 WKB（不规则）
  - min_lng/max_lng = 外接矩形坐标
  - grid_count_original = 实际包含的原始网格数
  - grid_id 特殊标记：grid_L{level}_edge_{seq}
```

### 字段差异

| 字段 | 完整矩形块 | 边界碎格块 |
|------|:--:|:--:|
| geometry | 矩形 WKB | 不规则 WKB（Union） |
| grid_id | `grid_L{level}_{r}_{c}` | `grid_L{level}_edge_{seq}` |
| area_sqm | N² × 10000 | 实际合并面积（< 完整块） |

### 示例

3200m 聚合（32×32 块），县域东北角只剩 12×18 个 100m 网格。这些网格合并为一个不规则多边形，geometry 是它们的 Union。
