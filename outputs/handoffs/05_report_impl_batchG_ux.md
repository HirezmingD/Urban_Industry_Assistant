## 完成状态
✅ 完成

## 改动清单

### 任务 1：九宫格 coords 修复 + 精简
- [x] `grid_service.py` — `query_nine_grid()`: Step A WKB→coords + Step B 精简至 6 字段
- [x] `app.js` — `renderNineGrid()`: 只用 coords 渲染，无 coords 则跳过

### 任务 2：点选详情浮动叠加层（方案 B）
- [x] `index.html` — 替换为 `.panel-overlay` + `.detail-card` 完整结构
- [x] `app.css` — 新增 ~100 行叠加层 CSS（遮罩/卡片/header/body/footer/row）
- [x] `app.js` — `openDetail()` / `renderDetail()` / `closeDetail()` 完整实现
- [x] `app.js` — map click 事件 + Esc 键关闭 + 遮罩点击关闭 + × 按钮关闭
- [x] `app.js` — "评估此地块"按钮跳转对话 tab

## 验证命令输出

```
cd D:\Projects\Urban_Industry_Assistant
python -c "from src.services.grid_service import query_nine_grid; r=query_nine_grid(119.685,29.795,14,'government'); c=r[0]; print('coords' in c, c['coords'] is not None, len(list(c.keys())))"
```

**输出**：
```
True True 6
```

## 交互行为
| 触发 | 行为 |
|------|------|
| 点击网格 | 遮罩+浮动卡片弹出，调 `/api/map/grid/{id}` 渲染 9 行属性 |
| × 按钮 | 遮罩和卡片消失 |
| 点遮罩 | 关闭 |
| Esc 键 | 关闭 |
| 再点另一网格 | 刷新卡片内容（不关闭再打开） |
| "评估此地块" | 关闭详情 → 切到对话 tab |
| 企业端 | 不触发点选详情 |
