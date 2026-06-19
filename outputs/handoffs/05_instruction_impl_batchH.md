# 批次 H：九宫格预加载 + 点选 sticky note 实现

**指令编号**：05_impl_batchH  
**目标 Agent**：实现 Agent  
**优先级**：P0（PRD v1.2 核心交互升级）  
**预估耗时**：2 小时  

---

## 背景

架构 Agent 已完成九宫格预加载 + 点选 sticky note 设计（`specs/arch/preload_sticky_design.md`，1000 行，含完整伪代码）。严格按架构文档实现。

## 输入材料

| 路径 | 说明 |
|------|------|
| `specs/arch/preload_sticky_design.md` | ⭐ 主参考——按 §1-4 顺序实现 |
| `specs/src/prd_v1.2.md` | PRD v1.2（验收标准） |

---

## 实现清单（按文件）

### 后端

#### 1. `src/services/grid_service.py` — 新增 `query_grid_layer()`

按 §1.2 伪代码实现。关键点：
- 轻量 SELECT：仅 `grid_id, land_type, land_code, min_lng~max_lat, geometry`
- bbox 非空时：R-tree + shapely 过滤
- bbox 为空时：全量 SELECT
- WKB→GeoJSON coords

#### 2. `src/api/map_routes.py` — 新增路由

按 §1.4：
```python
@router.get("/api/map/grid_layer")
async def grid_layer(zoom: int = Query(...), bbox: str | None = Query(None)):
    return query_grid_layer(zoom, bbox)
```

### 前端

#### 3. `static/index.html` — 新增 sticky note DOM + 删除旧 overlay

- **新增**：`#sticky-note` DOM 片段（§3.1）
- **删除**：`#panel-overlay` + `#detail-panel` 旧结构

#### 4. `static/app.css` — 替换样式

- **删除**：约 60 行 `.detail-card` / `.panel-overlay` CSS
- **新增**：约 80 行 sticky note CSS（§3.5）+ 三角箭头 CSS（§3.2）

#### 5. `static/app.js` — 核心改动（最大）

按 §2 + §3 + §4：

| 新增 | 删除 |
|------|------|
| `GridLayerManager` 类（~120行，§2.1） | `openDetail()` |
| `StickyNote` 类（~100行，§3.2-3.4） | `closeDetail()` |
| `initPreload()` 初始化（~30行，§4.5） | `renderDetail()` |
| | `highlightGridOnMap()` |
| | `_highlightedLayer` |

| 改写 | 位置 |
|------|------|
| mousemove 事件 | §4.4——zoom 11-15 → GridLayerManager；16-18 → HTTP |
| click 事件 | §4.3——优先 GridLayerManager 查找，fallback HTTP |
| mouseout 事件 | §4.4 末尾——清除预加载高亮 + HTTP 九宫格 |
| `zoomend` 事件 | §4.5——追加 `gridLayerManager.onZoomChange(zoom)` |

---

## 关键约束

| 约束 | 说明 |
|------|------|
| `findGridAt()` 性能 | zoom 14 时遍历 13K 个 Map entry，纯 JS 运算 <1ms，不要额外优化 |
| 三角箭头 | 4 种 CSS 类 `sticky-arrow--{top-left\|top-right\|bottom-left\|bottom-right}`，随弹窗位置切换 |
| sticky note 放在 `#map` 容器内 | 非 `#panel`，非 Leaflet Popup |
| 动画缓动 | `cubic-bezier(0.34, 1.56, 0.64, 1)` 弹出 / `ease-in` 关闭 |
| zoom 15 后台补全 | 静默，不给用户提示 |
| zoom 16-18 | GridLayerManager.isActive=false，全部走旧 HTTP 路径 |
| `/api/map/ninegrid` | 保留不动，zoom 16-18 仍需要 |
| `#sticky-eval-btn` | 仅政府端显示（`state.role === 'government'`） |

---

## 验证标准

| 编号 | 项 | 标准 |
|:--:|------|------|
| V1 | `/api/map/grid_layer?zoom=13` | 返回 FeatureCollection，features > 0，payload < 3MB |
| V2 | zoom 11-14 全量预加载 | 切换 zoom → 透明层加载完毕 < 500ms，无 UI 阻塞 |
| V3 | zoom 15 视口懒加载 | 视口内网格先出现（<400ms），后台静默补全 |
| V4 | zoom 11-15 九宫格流畅 | 鼠标快速移动，九宫格无延迟跟随，< 16ms/帧 |
| V5 | zoom 16-18 旧路径 | mousemove 仍发 HTTP，九宫格正常工作 |
| V6 | 点选弹出 sticky note | 光标右下方 12px，弹窗含标题/属性/按钮 |
| V7 | 四方向避让 | 右边缘向左弹、下边缘向上弹 |
| V8 | 三角箭头指向网格 | 箭头始终在弹窗对应角落，指向点击位置 |
| V9 | 弹出动画 | scale 0.9→1.0 回弹，150ms |
| V10 | 关闭动画 | scale 1.0→0.9，100ms |
| V11 | 5 种关闭方式 | ×/空白/Esc/另选/toggle 全部正常 |
| V12 | 聚合表内容 | L1-L5 弹窗含 top3 折叠 + 原始网格数 |
| V13 | 旧 overlay 清除 | `#panel-overlay` 不在 DOM 中，无残留 CSS |
| V14 | uvicorn 启动 | 无 import/SQL 报错 |

---

## 完成后

汇报写入 `D:\Projects\Urban_Industry_Assistant\outputs\handoffs\05_report_impl_batchH.md`。

汇报格式：
```
## 完成状态
✅ / ❌

## 实现清单
- [x] grid_service.py — query_grid_layer()
- [x] map_routes.py — /api/map/grid_layer 路由
- [x] index.html — sticky note DOM + 删旧 overlay
- [x] app.css — sticky note CSS + 删旧样式
- [x] app.js — GridLayerManager 类
- [x] app.js — StickyNote 类
- [x] app.js — mousemove/click/mouseout/zoomend 重写
- [x] app.js — 初始化流程

## API 验证
- GET /api/map/grid_layer?zoom=13: features 数 = ?
- curl 耗时: ?ms

## 交互验证
- zoom 12 九宫格: 流畅/卡顿
- 点选 sticky note: 位置/箭头/动画
```
