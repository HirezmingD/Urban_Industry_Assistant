# 批次 E 热修复：框选 Cancel 后矩形残留

**指令编号**：05_hotfix_2  
**目标 Agent**：实现 Agent  
**优先级**：P1（UI 瑕疵）  
**预估工作量**：2 分钟

---

## 背景

批次 E 完成后联调发现：用户用 Leaflet.Draw 框选后，再次点击绘制按钮 → 点击 "Cancel"，**之前的矩形框不会消失**，残留在地图上，直到画下一个矩形才被替换。

## 根因

`static/app.js` 的 `setupDrawControl()` 函数（第 91-109 行）只处理了 `L.Draw.Event.CREATED`（新矩形画完），没有处理进入绘制模式时清除旧矩形的逻辑。

Leaflet.Draw 的交互流程：
1. 用户点击 Draw 按钮 → `draw:drawstart` 事件
2. 用户完成绘制 → `draw:created` 事件（代码已有处理）
3. 用户点 Cancel → `draw:drawstop` 事件（代码未处理，旧矩形残留）

## 修改

**文件**：`static/app.js`

在 `setupDrawControl()` 函数中，`map.on(L.Draw.Event.CREATED, ...)` 之前新增 `draw:drawstart` 监听器。

**当前代码**（第 100-108 行）：
```javascript
  map.on(L.Draw.Event.CREATED, (e) => {
    if (state.drawnRect) map.removeLayer(state.drawnRect);
    state.drawnRect = e.layer;
    map.addLayer(e.layer);
    const b = e.layer.getBounds();
    state.currentBbox = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()].join(',');
    handleBboxQuery(state.currentBbox);
  });
```

**改为**：
```javascript
  map.on('draw:drawstart', () => {
    // 开始新绘制时清除旧矩形，防止 Cancel 后残留
    if (state.drawnRect) {
      map.removeLayer(state.drawnRect);
      state.drawnRect = null;
      state.currentBbox = null;
    }
    // 清除旧的高亮层和候选网格
    if (state.candidateLayer) {
      map.removeLayer(state.candidateLayer);
      state.candidateLayer = null;
    }
    state.candidateGrids = [];
    // 隐藏 info bar
    const infoBar = document.getElementById('chat-info-bar');
    if (infoBar) infoBar.classList.add('hidden');
  });

  map.on(L.Draw.Event.CREATED, (e) => {
    if (state.drawnRect) map.removeLayer(state.drawnRect);
    state.drawnRect = e.layer;
    map.addLayer(e.layer);
    const b = e.layer.getBounds();
    state.currentBbox = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()].join(',');
    handleBboxQuery(state.currentBbox);
  });
```

## 验证标准

| 项 | 标准 |
|------|------|
| 画矩形 → 点 Cancel | 矩形消失，地图干净 |
| 画矩形 → 再画新矩形 | 旧矩形被替换，新矩形正常 |
| Cancel 后 info bar | 隐藏 |
| Cancel 后再次框选+对话 | 正常带 bbox 发送请求 |

---

## 完成后

汇报写入 `D:\Projects\Urban_Industry_Assistant\outputs\handoffs\05_report_impl_hotfix_cancel.md`。
