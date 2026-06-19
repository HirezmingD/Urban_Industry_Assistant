# 批次 G 合并实现：九宫格 coords 修复 + 点选详情面板（浮动叠加层）

**指令编号**：05_impl_batchG_ux  
**目标 Agent**：实现 Agent  
**优先级**：P0  
**预估耗时**：45 分钟  

---

## 本批次包含两项任务

| # | 任务 | 类型 | 参考文件 |
|:--:|------|:--:|------|
| 1 | 九宫格 coords 缺失修复 + 响应精简 | Bug 修复 | 无（本指令内联） |
| 2 | 点选详情面板（浮动叠加层方案 B） | 新增功能 | `specs/arch/click_detail_ui_design.md` |

---

## 任务 1：九宫格 coords 修复 + 精简

### 问题简述

`/api/map/ninegrid` 返回的 dict 不含 `coords` 字段（WKB 未转换），且含 17 个冗余字段。

### 修复

**文件**：`src/services/grid_service.py`  
**位置**：`query_nine_grid()` 末尾，return result 之前

```python
# === Step A: WKB → coords（必须在 pop geometry 之前）===
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

# === Step B: 精简字段 ===
keep = {"grid_id", "min_lng", "min_lat", "max_lng", "max_lat", "coords"}
for d in result:
    for k in list(d.keys()):
        if k not in keep:
            del d[k]

return result
```

**文件**：`static/app.js`  
`renderNineGrid()` 函数，geometry 构造改为**只用 coords，有空则跳过**：

```javascript
geometry: c.coords
  ? { type: 'Polygon', coordinates: c.coords }
  : null,
```

并在 `.filter(f => f.geometry)` 过滤。

### 验证命令

```bash
curl -s "http://127.0.0.1:8000/api/map/ninegrid?lng=119.685&lat=29.795&zoom=14&role=government" | D:/TOOLS/MiniConda/envs/agent_gpu_py311/python.exe -c "import sys,json;d=json.load(sys.stdin);c=d[0];print('coords' in c,c['coords'] is not None,len(list(c.keys())))"
```

**必须输出**：`True True 6`

---

## 任务 2：点选详情面板（浮动叠加层）

### 架构文档

**严格按** `specs/arch/click_detail_ui_design.md` 的方案 B 实现。

### 实现清单

#### 文件 1：`static/index.html`

按架构 §3 改 HTML 结构：
- `#detail-panel` 改为含 `.detail-header` / `.detail-body` / `.detail-footer` 的完整卡片
- 新增 `#panel-overlay` 遮罩 div
- 两者默认 `.hidden`

#### 文件 2：`static/style.css`

追加架构 §4 的完整 CSS（~140 行），包括：
- `.panel-overlay` — 半透明遮罩
- `.detail-card` / `.detail-header` / `.detail-body` / `.detail-footer`
- `.detail-row` / `.detail-label` / `.detail-value`
- `.detail-close` / `.detail-eval-btn`
- `.hidden` / `.visible` 状态

#### 文件 3：`static/app.js`

按架构 §5 实现：
- `openDetail(gridId)` — 显示遮罩+卡片 → 调 `/api/map/grid/{gridId}` → 渲染
- `renderDetail(data)` — 按架构 §6 字段清单渲染属性行
- `closeDetail()` — 隐藏遮罩+卡片 → 清除地图高亮
- `map.on('click', ...)` 事件处理器（架构 §5.2 事件绑定表）
- `Esc` 键关闭监听
- 遮罩点击关闭
- 地图空白处点击关闭
- "评估此地块"按钮跳转对话 tab

#### 文件 4：`static/api.js`（如需要）

确保 `/api/map/grid/{grid_id}` 有对应的 fetch 封装函数。如无，在 `app.js` 中直接 `fetch`。

### 关键行为规则

1. 标签页按钮在详情打开时仍可点击，切换标签不关闭详情
2. 点击另一网格时重新 fetch 并更新卡片内容（不关闭再打开）
3. 企业端不触发点选详情
4. "评估此地块"按钮仅在政府端可见

---

## 验证标准

| 项 | 标准 |
|------|------|
| 九宫格 coords | 验证命令输出 `True True 6` |
| 网格无重叠 | zoom 14+ 看相邻网格边界线清晰、无重叠 |
| 九宫格响应精简 | 6 个 key（不含 land_type/ownership 等） |
| 点选有详情卡片 | 点击网格 → 遮罩+浮动卡片弹出 |
| 卡片内容正确 | 用地类型/面积/权属/乡镇 与数据库一致 |
| × 关闭 | 点 × 按钮，遮罩和卡片消失 |
| 遮罩关闭 | 点遮罩区域，详情关闭 |
| Esc 关闭 | 按 Esc 键，详情关闭 |
| 切换标签不关闭详情 | 详情打开时点"自进化"标签，详情保持 |
| 评估按钮 | 点"评估此地块"→ 切到对话 tab |

---

## 完成后

汇报写入 `D:\Projects\Urban_Industry_Assistant\outputs\handoffs\05_report_impl_batchG_ux.md`。

**必须贴九宫格验证命令的输出**。
