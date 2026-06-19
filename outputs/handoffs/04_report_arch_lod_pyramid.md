## 架构汇报（LOD 金字塔）

**任务**：设计多级渔网 LOD 金字塔架构，6 表 8 级 zoom 路由 + 聚合预处理算法 + 边界碎格不规则合并。

**完成状态**：完成

**架构文档路径**：`specs/arch/lod_pyramid_design.md`

---

**核心设计决策**：

1. **6 表独立 R-tree**：`land_grid_L0` 到 `land_grid_L5` 各建独立 R-tree 索引，每级 bbox 查询 O(log n)，全 zoom 框选 < 30ms，远超 PRD 要求的 < 200ms

2. **聚合表字段精简**：L1-L5 去掉 `nl_mean`/`ndvi_mean`/`pm25_mean`（聚合无意义），新增 `land_type_top3`（JSON 前三地类占比）、`ownership`（JSON 精确比例对象）、`grid_count_original`（被合并原始网格数），保留 `level` 标识层级

3. **`ownership` 设计转折**：PRD v1.1 要求简化权属为 "混合（N 单位）"，但本设计改为 JSON 精确比例 `{"大源村":0.45,"芦茨村":0.35,...}`——理由是为未来按权属比例做精确评估保留数据基础，且写入成本与简写相同

4. **空间分组策略：grid_id 行列号**——L0 的 `grid_id = grid_{row}_{col}` 天然编码了空间位置，聚合时直接按 `(row // N, col // N)` 分组，纯整数运算 O(n)，无需空间索引

5. **边界碎格 Union**——按补充决议，剩余网格用 shapely `unary_union` 合并为不规则多边形，`grid_id = grid_L{level}_edge_{seq}`。如果 Union 后不连通则按连通组件拆分。每级预计碎格 < 20 个

6. **zoom 11-12 九宫格降为单格**——网格太大（3200m/1600m）时 3×3 九宫格会覆盖全县，改为仅显示中心格，`_get_nine_grid_radius()` 返回 0 或 1

7. **降级链：聚合表不存在 → L0 + 截断 500 格 + `fallback:true`**

8. **预处理耗时 30-45 秒**（PRD 估计 5-10 分钟是保守值）

---

**风险提示**：

- `ownership` JSON 比例方案偏离了 PRD v1.1 的简化要求，请和洲/Orchestrator 确认是否接受此增强（若不接受，改回 `"混合（N 单位）"` 仅需改一行字段计算函数，其余架构不受影响）
- 边界碎格 `unary_union` 在 shapely 2.0+ 中性能良好，但需确保 `pip install shapely>=2.0.0`
- L0 的表重命名（`land_grid → land_grid_L0`）需要迁移现有数据，建议在 `preprocess_fishnet_pyramid.py` 中做 `ALTER TABLE RENAME TO`

汇报已写入 `outputs/handoffs/04_report_arch_lod_pyramid.md`，请查阅并转给 Orchestrator 质检。
