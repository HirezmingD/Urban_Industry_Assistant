# 架构指令：九宫格预加载 + 点选 sticky note

**发出方**：Orchestrator  
**接收方**：架构 Agent  
**指令编号**：04_arch_preload_sticky  
**时间**：2026-06-19  

---

## 背景

PRD v1.2（`specs/src/prd_v1.2.md`）定义了两项架构级变更：

1. **九宫格预加载+透明切换**：替换每次 mousemove HTTP 请求模式，改为 zoom 切换时预加载全层透明网格，mousemove 仅 `setStyle()`，目标 <16ms
2. **点选 sticky note**：替换浮动叠加层方案 B，改为光标旁即时贴，四方向避让+三角指示器+弹出动画

---

## 输入材料

| 路径 | 说明 |
|------|------|
| `specs/src/prd_v1.2.md` | PRD v1.2（⭐ 主参考） |
| `specs/arch/lod_pyramid_design.md` | LOD 金字塔架构（上下文） |
| `specs/arch/api.md` | 现有 API 定义 |
| `static/index.html` | 现有 HTML |
| `static/app.js` | 现有 JS（参考当前九宫格+点选实现） |

---

## 设计任务

### 任务 1：`GET /api/map/grid_layer` 端点设计

按 PRD v1.2 §1.6：

- 入参：`zoom`（必填，11-18），`bbox`（可选，zoom 15 用）
- 返回：轻量 GeoJSON FeatureCollection（仅 geometry + grid_id/land_type/land_code/min_lng~max_lat，无完整属性）
- 后端：`grid_service.py` 新增函数，按 zoom 选表，按 bbox 过滤，WKB→GeoJSON coords
- 性能：zoom 14 全量 ~13K 网格，payload <3MB

### 任务 2：前端预加载+透明切换架构

按 PRD v1.2 §1.3-1.5：

| Zoom | 策略 | 架构要点 |
|:--:|------|------|
| 11-14 | 全量预加载 | 1 次 fetch，全部渲染为透明 GeoJSON Layer，建 grid_id→Layer 索引 |
| 15 | 视口懒加载 | 先加载视口内，异步补全视口外 |
| 16-18 | 按点查询 | 保持现有 `/api/map/ninegrid` 方案 |

请设计：
- `GridLayerManager` 模块结构（函数/状态/生命周期）
- zoom 切换时的旧层清理+新层加载流程
- 网格索引 Map 的数据结构
- `setStyle()` 高亮/还原的调用时序

### 任务 3：点选 sticky note 架构

按 PRD v1.2 §2.2-2.7：

- **定位逻辑**：从 `containerPoint` 计算像素坐标 → 四方向避让判断 → 设置 div `left/top`
- **三角指示器**：4 方向 × 4 位置 = 16 种 CSS 类组合，箭头始终指向点击的网格
- **动画**：CSS `transform: scale()` + `transition`，缓动 `cubic-bezier(0.34, 1.56, 0.64, 1)`
- **内容映射**：L0 和 L1-L5 字段差异（聚合表显示 `land_type_top3` 折叠展开）
- **DOM 结构**：绝对定位 div，不依赖 Leaflet Popup

### 任务 4：与现有代码的共存

- 旧的方案 B（`#panel-overlay` + `.detail-card`）需保留还是删除？
- 旧的 `showGridDetail()` 函数如何迁移
- `/api/map/ninegrid` 在 zoom 11-15 是否仍需要（预加载模式下九宫格不调它）

---

## 输出要求

交付物：`specs/arch/preload_sticky_design.md`

```markdown
# 九宫格预加载 + 点选 sticky note 架构设计

## 1. `/api/map/grid_layer` 端点
### 1.1 路由定义
### 1.2 grid_service 新增函数
### 1.3 返回体格式

## 2. 前端预加载架构
### 2.1 GridLayerManager 模块
### 2.2 分级加载流程
### 2.3 透明层 setStyle 机制
### 2.4 zoom 切换生命周期

## 3. 点选 sticky note 架构
### 3.1 DOM 结构
### 3.2 四方向定位+三角指示器
### 3.3 动画方案
### 3.4 内容渲染（L0 vs L1-L5 差异）

## 4. 旧代码迁移方案
```

---

## 补充决议

- zoom 15 后台补全：静默，不给用户提示
- sticky note 三角指示器：与四方向避让联动（弹窗在右下→箭头在左上，弹窗在左上→箭头在右下）

---

## 完成后

汇报写入 `outputs/handoffs/04_report_arch_preload_sticky.md`。
