# 架构指令：多级渔网 LOD 金字塔 + 行政区悬停高亮

**发出方**：Orchestrator  
**接收方**：架构 Agent  
**指令编号**：04_arch_lod_pyramid  
**时间**：2026-06-19  
**项目**：Urban_Industry_Assistant  

---

## 任务背景

V1.0 系统已跑通，但渔网仅 100m 单一级别。PRD v1.1（`specs/src/prd_v1.1.md`）定义了两项架构级升级：

1. **多级渔网 LOD 金字塔**（核心）：8 级（zoom 11-18），5 级预聚合（L1-L5）+ 3 级原始（L0），自动按 zoom 切表
2. **行政区划悬停高亮**（辅助）：纯前端，不涉及架构

你只需设计**修订 1（金字塔）的架构方案**。修订 2（行政区悬停）不涉及后端，跳过。

---

## 输入材料

| 路径 | 说明 |
|------|------|
| `specs/src/prd_v1.1.md` | PRD v1.1，重点读 §2.2-2.7 |
| `specs/src/prd.md` | V1.0 PRD |
| `specs/arch/architecture.md` | V1.0 系统架构 |
| `specs/arch/database.md` | V1.0 数据库设计 |
| `specs/arch/api.md` | V1.0 API 定义 |
| `src/services/grid_service.py` | 当前渔网服务（R-tree + WKB） |
| `src/schemas.py` | 当前 Pydantic 模型 |
| `src/database.py` | 当前建表逻辑 |

---

## 设计任务

### 任务 1：多表架构——L0-L5 的建表方案

当前只有 `land_grid` 一张表。需要设计 6 张表架构：

- `land_grid_L0`（原表重命名，100m 原始）
- `land_grid_L1`（3200m 聚合）
- `land_grid_L2`（1600m 聚合）
- `land_grid_L3`（800m 聚合）
- `land_grid_L4`（400m 聚合）
- `land_grid_L5`（200m 聚合）

请设计：
- L1-L5 的表 schema（字段名、类型、约束）——对比 L0 的差异
- R-tree 空间索引是否每张表都建
- 表命名约定和建表 SQL

### 任务 2：zoom→table 映射与路由

`grid_service.py` 的 `query_by_bbox()` 和 `query_nine_grid()` 需要根据 zoom 参数选择目标表。

请设计：
- zoom→level 映射函数（11→L1, 12→L2, ... 16-18→L0）
- 函数签名变更（两个查询函数的入参和返回值变化）
- API 入参变更（`/api/map/query` 和 `/api/map/ninegrid` 新增 `zoom` 参数）

### 任务 3：聚合预处理算法

请设计 `scripts/preprocess_fishnet_pyramid.py` 的核心算法：

- 输入：`land_grid_L0`（185,564 条 100m 网格）
- 输出：L1-L5 聚合表
- 聚合逻辑：如何将 N×N 个 100m 网格合并为 1 个聚合网格
- 字段计算：
  - `land_type`：众数（出现最多的 DLMC）
  - `land_type_top3`：JSON 格式 `[{"name":"乔木林地","pct":0.65},...]`
  - `ownership`：JSON 格式 `{"大源村": 0.45, "芦茨村": 0.35, ...}`（存储各单位精确比例）
  - `geometry`：合并后的外接矩形 WKB
  - `min_lng/max_lng`：外接矩形坐标
  - `grid_count_original`：被合并的原始网格数
- 空间分组策略：如何将 100m 格网按 N×N 分组（利用 grid_id 的行列号？还是用空间索引？）

### 任务 4：GridFeature schema 扩展

PRD 要求 `GridFeature` 新增 `min_lng/min_lat/max_lng/max_lat` 四个字段（九宫格修复）。请确认 `schemas.py` 中：

- `GridFeature` 新增 4 个坐标字段
- `GridCell` 是否也需要同步扩展
- 聚合表的 `GridFeature` 是否还需要 `land_type_top3` 字段

### 任务 5：性能设计

- 聚合预处理耗时预估（5 级 × ~18 万条 → 聚合后约 1.7 万条聚合记录）
- 框选查询预估：各 zoom 级单次查询延迟
- 降级策略：聚合表不存在时的 fallback 逻辑
- 数据库体积预估：L0（~180MB）+ L1-L5 聚合表

---

## 输出要求

交付物：`specs/arch/lod_pyramid_design.md`

必须包含：

```markdown
# 多级渔网 LOD 金字塔架构设计

## 1. 多表架构
### 1.1 L0-L5 建表 SQL
### 1.2 与 V1.0 schema 的差异对比
### 1.3 索引方案

## 2. zoom→table 映射与 API 变更
### 2.1 映射函数
### 2.2 grid_service.py 函数签名变更
### 2.3 API 入参变更（/api/map/query, /api/map/ninegrid）

## 3. 聚合预处理算法
### 3.1 算法流程（伪代码）
### 3.2 字段计算规则（含 ownership 精确比例的 JSON 格式）
### 3.3 空间分组策略

## 4. Schema 扩展
### 4.1 GridFeature 新增字段
### 4.2 GridCell / 聚合模型

## 5. 性能预估
```

---

## 汇报要求

完成后将汇报写入 `D:\Projects\Urban_Industry_Assistant\outputs\handoffs\04_report_arch_lod_pyramid.md`。

汇报只写 3-5 句核心设计决策。完整内容在交付物中。
