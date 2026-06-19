# 批次 F 热修复：九宫格悬停不显示 + 地图缩放范围过大

**指令编号**：05_hotfix_3  
**目标 Agent**：实现 Agent  
**优先级**：P0（PRD 核心交互缺失）  
**预估耗时**：10 分钟  

---

## Bug 1：九宫格悬停不显示

### 根因

`grid_service.py` 的 `query_nine_grid()` 函数（第 216 行起）调用 `_row_to_dict()`，政府端返回的 dict 包含二进制 `geometry` 字段。`map_routes.py` 的 `/api/map/ninegrid` 返回这些 dict 时，FastAPI JSON 序列化遇到 `bytes` 类型报 500 错。前端 `mousemove` 的 `.catch(() => {})` 静默吞掉异常，用户看不到任何效果。

### 修复

**文件**：`src/services/grid_service.py`  
**位置**：`query_nine_grid()` 函数末尾，return 前

在 `return result` 前加一行，移除每个 dict 中的 `geometry` 字段：

```python
    for row in neighbors:
        result.append(_row_to_dict(row, role))

    # 移除二进制 geometry（JSON 不可序列化）
    for d in result:
        d.pop("geometry", None)

    return result
```

注意：`center_dict` 和 `neighbors` 的 dict 都要清 `geometry`。`center_dict` 是 `_row_to_dict(center, role)` 返回的，同样含 `geometry`。

**完整改动后的代码段**（约第 256-283 行区域）：

```python
        center_dict = _row_to_dict(center, role)
        result = [center_dict]

        # 2. 扩展 ±_DEG_PER_100M 查询周围 8 格
        margin = _DEG_PER_100M
        neighbors = conn.execute(
            # ... 不变 ...
        ).fetchall()

        for row in neighbors:
            result.append(_row_to_dict(row, role))

        # 移除二进制 geometry 字段（JSON 不可序列化）
        for d in result:
            d.pop("geometry", None)

        return result
```

---

## Bug 2：地图可缩放到看见杭州

### 根因

`static/app.js` 第 62 行 `minZoom: 10` 太低。Leaflet `maxBounds` 只限制**平移**，不限制**缩放**。桐庐 bbox 约 0.64°×0.54°，zoom 10 时视口覆盖 ~2.6°×1.5°——远超桐庐范围，杭州、建德都看得到。

### 修复

**文件**：`static/app.js`  
**位置**：`initMap()` 函数，第 62 行

```javascript
// 当前
map = L.map('map', {
    center, zoom: 12, minZoom: 10, maxZoom: 18,
    ...
});

// 改为
map = L.map('map', {
    center, zoom: 12, minZoom: 11, maxZoom: 18,
    ...
});
```

zoom 11 时视口 ~1.3°×0.74°，桐庐 bbox 至少有两边在视口内，周边城市不可见。

---

## 验证标准

| 项 | 标准 |
|------|------|
| 政府端鼠标滑过地图 | 出现 3×3 九宫格叠加（中心格蓝色高亮，周围淡蓝） |
| 鼠标移出地图 | 九宫格消失 |
| 缩放到底（zoom 11） | 视口边界为桐庐四至，看不到杭州 |
| cmd 无 500 报错 | ninegrid 请求无红色 ERROR |

---

## 完成后

汇报写入 `D:\Projects\Urban_Industry_Assistant\outputs\handoffs\05_report_impl_hotfix_interaction.md`。
