## 完成状态
✅ 完成

## 改动清单
- [x] `app.js` `_loadFull()` — L.geoJSON 加 `interactive: false`
- [x] `app.js` `_loadViewport()` — 视口层 + 补全层均加 `interactive: false`
- [x] `app.js` `StickyNote.show()` — 标题栏更新为 `📋 grid_xxx`
- [x] `app.js` `_bindEvents()` — 评估按钮预填消息并自动发送

## 验证
| 项 | 结果 |
|------|:--:|
| zoom 13 鼠标移动九宫格 | 透明层不再截获事件 ✅ |
| sticky note 标题栏 | 显示 `📋 grid_xxx` ✅ |
| "评估此地块"按钮 | 切对话 tab + 预填"评估网格 grid_xxx" + 自动 send ✅ |
