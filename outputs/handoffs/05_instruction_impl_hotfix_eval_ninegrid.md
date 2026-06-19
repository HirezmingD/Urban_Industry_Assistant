# 05 实现 Agent 指令 — Hotfix: 评估 0 亩 + 九宫格无效果

## 背景

Orchestrator 已诊断两个 bug 的根因：

| # | 问题 | 根因 | 涉及文件 |
|:--:|------|------|------|
| 1 | "评估此地块"→AI 报 0.0 亩 | `eval_service.py` `chat()` 不解析消息中的 grid_id，sticky note 发"评估网格 grid_xxx"时 bbox=null → 走 `evaluate_grids([], ...)` 空列表 | `src/services/eval_service.py` |
| 2 | 鼠标移动九宫格无效果 | `app.js` mousemove 在 GridLayerManager.isActive=true 时，findGridAt 返回 null 也直接 return，HTTP ninegrid API 回退被阻断 | `static/app.js` |

---

## 任务 1：修复 `eval_service.py` — 解析消息中的 grid_id

**文件**：`src/services/eval_service.py`

**位置**：`chat()` 函数，在最后的 fallback（约第 317-320 行）之前插入 grid_id 提取逻辑。

**改动**：

在 `# 无框选或 bbox 无效 → 纯产业咨询` 注释块之前，插入：

```python
    # 尝试从消息中提取 grid_id（如 sticky note "评估此地块" 按钮触发）
    import re
    grid_match = re.match(r'评估网格\s+(grid_\S+)', message)
    if grid_match:
        grid_id = grid_match.group(1)
        return await evaluate_grids([grid_id], message, role, context)
```

**插入位置示意**（在原有 `# 无框选或 bbox 无效 → 纯产业咨询` 上方）：

```python
    # ... bbox 处理逻辑 ...

    # === 新增：从消息提取 grid_id ===
    import re
    grid_match = re.match(r'评估网格\s+(grid_\S+)', message)
    if grid_match:
        grid_id = grid_match.group(1)
        return await evaluate_grids([grid_id], message, role, context)

    # 无框选或 bbox 无效 → 纯产业咨询  <-- 原有代码
```

> **注意**：`import re` 放到文件顶部其他 import 一起，不要放在函数体内。上面示意是为了标注插入位置。

---

## 任务 2：修复 `app.js` — 预加载路径加 HTTP 回退

**文件**：`static/app.js`

**位置**：`setupMouseInteraction()` 中的 mousemove 事件处理器，约第 115-127 行。

**当前代码**（第 115-127 行）：

```javascript
    if (gridLayerManager && gridLayerManager.isActive) {
      const now = performance.now();
      if (now - _lastHoverTs < 16) return;
      _lastHoverTs = now;
      const gridId = gridLayerManager.findGridAt(lng, lat);
      gridLayerManager.highlightNineGrid(gridId, zoom);
      return;   // ← 这里直接 return，即使 gridId 为 null 也不回退
    }
    const now = Date.now();
    if (now - _lastQueryTs < 200) return;
    _lastQueryTs = now;
    fetch(`${API_BASE}/api/map/ninegrid?lng=${lng}&lat=${lat}&zoom=${zoom}&role=government`)
      .then(r => r.json()).then(cells => renderNineGrid(cells)).catch(() => {});
```

**修改为**：

```javascript
    if (gridLayerManager && gridLayerManager.isActive) {
      const now = performance.now();
      if (now - _lastHoverTs < 16) return;
      _lastHoverTs = now;
      const gridId = gridLayerManager.findGridAt(lng, lat);
      if (gridId) {
        gridLayerManager.highlightNineGrid(gridId, zoom);
        return;   // 找到了 → 用预加载路径，不回退
      }
      // findGridAt 返回 null（网格未覆盖此位置 / 加载中）→ 继续走 HTTP 回退
    }
    const now = Date.now();
    if (now - _lastQueryTs < 200) return;
    _lastQueryTs = now;
    fetch(`${API_BASE}/api/map/ninegrid?lng=${lng}&lat=${lat}&zoom=${zoom}&role=government`)
      .then(r => r.json()).then(cells => renderNineGrid(cells)).catch(() => {});
```

**关键变化**：`if (gridId)` 包裹 `highlightNineGrid` + `return`，gridId 为 null 时不 return，穿透到 HTTP 回退。

---

## 任务 3（诊断用）：验证 grid_layer API 是否返回数据

在生产环境修复前后，请在浏览器 DevTools Network 面板检查：

```
GET /api/map/grid_layer?zoom=12
```

1. **HTTP 状态码**是否为 200？
2. **Response** 中 `features` 数组长度是否 > 0？
3. **features[0].properties.grid_id** 格式是什么？（应为 `grid_L2_xxx_xxx` 之类）

将检查结果写入汇报。

---

## 验证清单

修复后，在浏览器 `Ctrl+Shift+R` 刷新，验证：

- [ ] **评估此地块**：点 sticky note 的"评估此地块"→ 自动切对话 tab → AI 回复含网格的实际面积（非 0.0 亩）
- [ ] **九宫格鼠标悬停**：zoom 12-13 下鼠标移动 → 出现九宫格透明度效果（中心格 45% 不透明 + 周围 8 格 25%）
- [ ] **HTTP 回退**：zoom 15+ 或边缘位置 → 九宫格仍能通过 HTTP API 正常显示
- [ ] **Console 无报错**

---

## 交付

将修复汇报写入 `D:\Projects\Urban_Industry_Assistant\outputs\handoffs\05_report_impl_hotfix_eval_ninegrid.md`，含：

1. 改动文件清单 + diff 摘要
2. 任务 3 诊断结果（grid_layer API 返回状态）
3. 以上 4 项验证结果（每项 ✅/❌）
