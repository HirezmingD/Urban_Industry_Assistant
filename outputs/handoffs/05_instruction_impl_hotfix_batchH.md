# 批次 H 热修复：九宫格不显示 + sticky note 两缺陷

**指令编号**：05_hotfix_batchH  
**目标 Agent**：实现 Agent  
**优先级**：P0  

---

## Bug 1：九宫格透明层截获 mousemove

### 根因

`GridLayerManager._loadFull()` 创建的 `L.geoJSON` 默认 `interactive: true`，透明网格多边形捕获了所有 mousemove 事件，地图 handler 收不到。

### 修复

**文件**：`static/app.js`，`_loadFull()` 和 `_loadViewport()` 两处。

```javascript
// 改前（约第 311 行）
this.gridLayer = L.geoJSON(fc, {
  style: () => ({ fillOpacity: 0, stroke: false, opacity: 0 }),
  onEachFeature: (f, l) => this.gridIndex.set(f.properties.grid_id, l)
}).addTo(this.map);

// 改后
this.gridLayer = L.geoJSON(fc, {
  style: () => ({ fillOpacity: 0, stroke: false, opacity: 0 }),
  interactive: false,    // ★ 不捕获鼠标事件
  onEachFeature: (f, l) => this.gridIndex.set(f.properties.grid_id, l)
}).addTo(this.map);
```

`_loadViewport()` 同样加 `interactive: false`（视口内和补全都需要）。

---

## Bug 2：sticky note 标题栏不显示网格 ID

### 根因

HTML 写死 `📋 ...`，`_renderContent()` 未更新标题。

### 修复

**文件**：`static/app.js`，`StickyNote.show()` 方法（约第 362 行），`_renderContent()` 调用前加一行：

```javascript
this.el.querySelector('.sticky-grid-id').textContent = '📋 ' + gridData.grid_id;
```

---

## Bug 3："评估此地块"按钮不预填消息

### 根因

按钮只关闭+切标签，没填输入框。

### 修复

**文件**：`static/app.js`，`_bindEvents()` 中 eval 按钮 handler（约第 385 行）：

```javascript
// 改前
this.el.querySelector('#sticky-eval-btn').addEventListener('click', () => {
  this.hide(); switchTab('chat');
});

// 改后
this.el.querySelector('#sticky-eval-btn').addEventListener('click', () => {
  const msg = '评估网格 ' + this.currentGridId;
  const input = document.getElementById('chat-input');
  if (input) input.value = msg;
  this.hide();
  switchTab('chat');
  // 自动触发发送
  document.getElementById('chat-send-btn')?.click();
});
```

---

## 验证

| 项 | 标准 |
|------|------|
| zoom 13 鼠标移动 | 九宫格出现，流畅跟随 |
| 点选网格 | sticky note 标题栏显示 `📋 grid_xxx` |
| 点"评估此地块" | 切换到对话 tab，输入框有"评估网格 grid_xxx"，自动发送 |

---

## 完成后

汇报写入 `05_report_impl_hotfix_batchH.md`。
