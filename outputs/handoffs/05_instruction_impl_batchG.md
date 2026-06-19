# 批次 G：多级渔网 LOD 金字塔实现

**指令编号**：05_impl_batchG  
**目标 Agent**：实现 Agent  
**优先级**：P0（PRD v1.1 核心功能）  
**预估耗时**：2-3 小时  

---

## 背景

架构 Agent 已完成多级渔网 LOD 金字塔设计（`specs/arch/lod_pyramid_design.md`，771 行）。包含 12 步实现清单、完整 SQL、聚合算法伪代码、字段计算规则。

## 输入材料

| 路径 | 说明 |
|------|------|
| `specs/arch/lod_pyramid_design.md` | 架构设计文档（⭐ 主参考） |
| `specs/arch/lod_pyramid_design.md` §6 | 12 步实现清单 |
| `specs/src/prd_v1.1.md` | PRD v1.1（已修正 ownership 为 JSON 精确比例） |
| `specs/arch/architecture.md` | V1.0 系统架构（上下文参考） |

## 执行

遵循架构文档 §6 的 12 步顺序，不可跳步：

| 步 | 文件 | 改动 |
|:--:|------|------|
| 1 | `database.py` | 新增 L1-L5 建表 SQL + R-tree（`init_db()` 追加） |
| 2 | `database.py` | `land_grid` → `land_grid_L0` 重命名迁移 |
| 3 | `schemas.py` | GridFeature 加 6 字段（min_lng/lat、max_lng/lat、level、land_type_top3、grid_count_original） |
| 4 | `grid_service.py` | 新增 `_ZOOM_TABLE_MAP`、`_get_table_for_zoom()`、`_get_nine_grid_radius()`、`_get_grid_deg_for_zoom()` |
| 5 | `grid_service.py` | `query_by_bbox()` 加 `zoom` 参数 + 动态表名 + 降级 |
| 6 | `grid_service.py` | `query_nine_grid()` 加 `zoom` 参数 + zoom 11-12 单格 |
| 7 | `grid_service.py` | `_select_fields()` 加 `is_aggregated` 参数 |
| 8 | `grid_service.py` | `_row_to_dict()` 加 `is_aggregated` 参数 |
| 9 | `api/map_routes.py` | `/api/map/query` 加 `zoom` 查询参数 |
| 10 | `api/map_routes.py` | `/api/map/ninegrid` 加 `zoom` 查询参数 |
| 11 | `scripts/preprocess_fishnet_pyramid.py` | **新建**——按架构文档 §3 算法实现 |
| 12 | `static/app.js` | 框选/九宫格请求带 `zoom` 参数；`zoomend` 事件刷新图层 |

## 特殊注意事项

- **步 11 预处理脚本不要跳**：跑完后 L1-L5 表才存在
- **步 2 重命名迁移**：`ALTER TABLE land_grid RENAME TO land_grid_L0`，需处理 R-tree 同步
- **ownership 格式**：JSON 精确比例对象，不是 "混合（N 单位）"
- **邻格步长**：不再固定 `_DEG_PER_100M`，改用 `_get_grid_deg_for_zoom(zoom)`
- **降级逻辑**：聚合表不存在时 fallback 到 L0 + 截断，返回 `"fallback": true`

## 验证标准

| 项 | 标准 |
|------|------|
| uvicorn 启动正常 | 无 import/SQL 报错 |
| L0 表名正确 | `SELECT name FROM sqlite_master WHERE name='land_grid_L0'` 返回 1 |
| 预处理脚本可执行 | 无异常退出，耗时 < 60s |
| L1-L5 表有数据 | `SELECT COUNT(*) FROM land_grid_L1` > 0 |
| zoom=11 框选 | `grid_count` < 500，返回 3200m 网格 |
| zoom=16 框选 | 返回 100m 网格 |
| 九宫格 zoom=12 | 仅 1 格 |
| 九宫格 zoom=14 | 3×3 |
| 前端带 zoom 请求 | F12 Network 看 `/api/map/query?bbox=...&zoom=...` |

## 完成后

1. 运行预处理脚本：`D:\TOOLS\MiniConda\envs\agent_gpu_py311\python.exe scripts/preprocess_fishnet_pyramid.py`
2. 汇报写入 `D:\Projects\Urban_Industry_Assistant\outputs\handoffs\05_report_impl_batchG.md`

汇报格式：
```
## 完成状态
✅ / ❌

## 12 步清单
- [x] 1. L1-L5 建表 SQL
- [x] 2. 重命名 land_grid → L0
...

## 预处理输出
（贴脚本末尾打印：各表行数、耗时、用地类型分布）

## 验证
- zoom 11 bbox: grid_count=?
- zoom 16 bbox: grid_count=?
- 九宫格 zoom 12: 返回 ? 格
- uvicorn 启动: 正常/异常
```
