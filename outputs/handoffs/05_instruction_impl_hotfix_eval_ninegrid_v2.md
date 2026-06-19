# 05 实现 Agent 指令 — Hotfix: get_grid_stats 适配聚合表 + 九宫格诊断

## 背景

Orchestrator 已定位问题 2 的根因；问题 1 待诊断。

---

## 任务 1：修复 `get_grid_stats` — 支持聚合网格查询

**文件**：`src/services/grid_service.py`

**根因**：`get_grid_stats()` 第 477 行硬编码 `FROM land_grid_L0`。sticky note 点击聚合网格（如 `grid_L2_2076_8324`）时，该 ID 在 L0 表中不存在 → COUNT=0 → 评估报 0 亩。

**修改**：将 `get_grid_stats` 从只查 L0 改为根据 grid_id 前缀自动选表。

**替换位置**：第 464-497 行，整个 `get_grid_stats` 函数体。

**新代码**：

```python
def get_grid_stats(grid_ids: list[str]) -> dict[str, Any]:
    """批量查询指定 grid_id 列表的聚合统计。

    自动识别 grid_id 所属层级（L0-L5），查对应聚合表。
    聚合表（L1-L5）直接取 area_sqm + land_type_top3；
    原始表（L0）用 GROUP BY 计算分布。
    """
    if not grid_ids:
        return {
            "grid_count": 0, "total_area_sqm": 0.0,
            "total_area_mu": 0.0, "land_type_distribution": {},
        }

    # 从第一个 grid_id 推断表名
    # 格式：grid_L{level}_{row}_{col}，如 grid_L2_2076_8324
    table_name = "land_grid_L0"
    for level in range(5, 0, -1):  # L5→L1 优先匹配长串
        if f"_L{level}_" in grid_ids[0]:
            table_name = f"land_grid_L{level}"
            break

    conn = get_connection()
    try:
        placeholders = ",".join("?" for _ in grid_ids)

        if table_name == "land_grid_L0":
            # L0 原始表：逐格 GROUP BY
            row = conn.execute(
                f"""SELECT COUNT(*) AS grid_count,
                    COALESCE(SUM(area_sqm), 0) AS total_area_sqm
                    FROM land_grid_L0 WHERE grid_id IN ({placeholders})""",
                grid_ids,
            ).fetchone()
            dist_rows = conn.execute(
                f"""SELECT land_type, COUNT(*) AS cnt
                    FROM land_grid_L0 WHERE grid_id IN ({placeholders})
                    GROUP BY land_type ORDER BY cnt DESC""",
                grid_ids,
            ).fetchall()
            total_sqm = float(row["total_area_sqm"] or 0)
            land_dist = {r["land_type"]: r["cnt"] for r in dist_rows}
        else:
            # 聚合表（L1-L5）：直接取已聚合的 area_sqm + land_type_top3
            row = conn.execute(
                f"""SELECT COUNT(*) AS grid_count,
                    COALESCE(SUM(area_sqm), 0) AS total_area_sqm,
                    land_type, land_type_top3
                    FROM {table_name} WHERE grid_id IN ({placeholders})""",
                grid_ids,
            ).fetchone()
            total_sqm = float(row["total_area_sqm"] or 0)
            # 从 land_type_top3 JSON 解析分布
            land_dist = {}
            if row["land_type_top3"]:
                try:
                    top3 = json.loads(row["land_type_top3"])
                    land_dist = {t["name"]: int(t["pct"] * 100) for t in top3}
                except (json.JSONDecodeError, KeyError, TypeError):
                    land_dist = {row["land_type"]: 1} if row["land_type"] else {}

        return {
            "grid_count": row["grid_count"],
            "total_area_sqm": total_sqm,
            "total_area_mu": round(total_sqm / _SQM_PER_MU, 1),
            "land_type_distribution": land_dist,
        }
    finally:
        conn.close()
```

> **注意**：文件顶部已有 `import json`（第 10 行），无需新增 import。

---

## 任务 2：九宫格浏览器端诊断

**不要改代码**，先在浏览器 F12 Console 中执行以下诊断命令，将输出完整贴到汇报中：

### 诊断 A：GridLayerManager 状态

```javascript
console.log('isActive:', gridLayerManager.isActive);
console.log('currentZoom:', gridLayerManager.currentZoom);
console.log('gridIndex.size:', gridLayerManager.gridIndex.size);
console.log('gridLayer on map:', map.hasLayer(gridLayerManager.gridLayer));
```

### 诊断 B：取一个样本网格

```javascript
const first = gridLayerManager.gridIndex.entries().next().value;
if (first) {
    const [gridId, layer] = first;
    console.log('sample gridId:', gridId);
    console.log('sample properties:', layer.feature?.properties);
    console.log('layer._path:', layer._path);  // SVG path 元素是否存在
}
```

### 诊断 C：mousemove 路径追踪

在 Console 中执行以下临时插桩（不修改源文件），然后在地图上移动鼠标 3-5 秒，观察输出：

```javascript
const orig = map._events?.mousemove;
// 监听 Network 九宫格请求
const origFetch = window.fetch;
window.fetch = function(...args) {
    if (args[0]?.includes('ninegrid')) console.log('>>> HTTP ninegrid fetch:', args[0]);
    return origFetch.apply(this, args);
};
// 监听 findGridAt
const origFind = gridLayerManager.findGridAt.bind(gridLayerManager);
gridLayerManager.findGridAt = function(lng, lat) {
    const r = origFind(lng, lat);
    if (r) console.log('>>> findGridAt HIT:', r);
    return r;
};
```

### 诊断 D：Network 面板

打开 F12 → Network 标签 → 过滤 `ninegrid` → 在地图上移动鼠标 → 观察：

1. 是否有 `/api/map/ninegrid?lng=...&lat=...&zoom=...` 请求发出？
2. 响应状态码是什么？（200 / 500 / CORS 错误？）
3. 响应内容是什么？（features 数量？空数组？）

---

## 验证

- [ ] 任务 1：点 sticky note「评估此地块」→ AI 回复含实际面积（非 0.0 亩）
- [ ] 任务 2：诊断 A-D 结果写入汇报

---

## 交付

将修复 + 诊断汇报写入：
`D:\Projects\Urban_Industry_Assistant\outputs\handoffs\05_report_impl_hotfix_eval_ninegrid_v2.md`

含：
1. 任务 1 改动验证（`get_grid_stats` 替换确认）
2. 任务 2 诊断 A-D 的完整输出
3. 九宫格问题根因判断（基于诊断结果）
