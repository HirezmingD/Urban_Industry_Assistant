# 批次 G 热修复（重做）：九宫格 coords 缺失 + 响应未精简

**指令编号**：05_hotfix_grid_ux_v2  
**目标 Agent**：实现 Agent  
**优先级**：P0  
**预估耗时**：20 分钟  

---

## 问题

上轮声称已修复但实测未生效：

| 声称 | 实测 |
|------|------|
| 响应含 `coords` 字段 | ❌ 9 格全部 `coords=False` |
| 响应精简到 11 字段 | ❌ 仍 17 字段（含 land_type/ownership/extras 等） |

根因：`_wkb_to_coords()` 函数可能未定义、未调用，或 `geometry` 在被转换前已被 pop。

---

## 修复（必须严格按此执行）

### 文件 1：`src/services/grid_service.py`

在 `query_nine_grid()` 函数末尾，**return result 之前**，确保：

```python
# === Step A: 先转 WKB → coords（必须在 pop geometry 之前）===
from shapely import wkb
from shapely.geometry import mapping

for d in result:
    geom_blob = d.get("geometry")
    if geom_blob:
        try:
            geom = wkb.loads(geom_blob)
            d["coords"] = mapping(geom).get("coordinates")
        except Exception:
            d["coords"] = None
    else:
        d["coords"] = None

# === Step B: 再精简字段 ===
keep = {"grid_id", "min_lng", "min_lat", "max_lng", "max_lat", "coords"}
for d in result:
    for k in list(d.keys()):
        if k not in keep:
            del d[k]

return result
```

**关键顺序**：先转 coords（从 geometry 取），再删字段（包括 geometry）。

### 文件 2：`static/app.js`

`renderNineGrid()` 第 216-218 行，当前有 fallback 逻辑。改**只用 coords，不 fallback**：

```javascript
geometry: c.coords
  ? { type: 'Polygon', coordinates: c.coords }
  : null,  // coords 为空时跳过该 feature
```

并在 `.filter(f => f.geometry)` 过滤掉无 coords 的 feature。

---

## 验证（修复后必须自测）

在 cmd 执行：

```bash
curl -s "http://127.0.0.1:8000/api/map/ninegrid?lng=119.685&lat=29.795&zoom=14&role=government" | D:/TOOLS/MiniConda/envs/agent_gpu_py311/python.exe -c "import sys,json;d=json.load(sys.stdin);c=d[0];print('coords' in c,c['coords'] is not None,len(list(c.keys())))"
```

**必须输出**：`True True 6`（coords 存在、非空、总共 6 个 key）

如不为 `True True 6`，说明修复未生效，不要汇报。

---

## 完成后

汇报写入 `D:\Projects\Urban_Industry_Assistant\outputs\handoffs\05_report_impl_hotfix_grid_ux_v2.md`。

**汇报必须贴验证命令的输出**，格式：

```
$ curl ... | python -c "..."
True True 6
```
