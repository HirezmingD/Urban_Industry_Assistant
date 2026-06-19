## 架构汇报（九宫格预加载 + 点选 sticky note）

**任务**：设计九宫格预加载+透明切换架构 + 点选 sticky note 架构，含新增 API 端点、前端 GridLayerManager/StickyNote 两模块、旧代码迁移方案。

**完成状态**：完成

**架构文档路径**：`specs/arch/preload_sticky_design.md`（26.8 KB）

---

**核心设计决策**：

1. **新端点 `/api/map/grid_layer`** — 返回轻量 GeoJSON（仅 geometry + grid_id/land_type/land_code/min_lng~max_lat），payload 比全量查询缩减约 60%。后端复用 LOD 金字塔的 R-tree，按 zoom 自动选表

2. **GridLayerManager 模块** — zoom 11-14 全量预加载（~270→13,700 格，<500ms），全部渲染为完全透明层，建 `Map<grid_id, L.Layer>` 索引；zoom 15 视口懒加载（视口内优先 + 后台静默补全全量）；zoom 16-18 不管理，保留旧 HTTP 九宫格

3. **mousemove 零网络延迟** — 预加载模式下，悬停仅做本地 `layer.setStyle()`（不创建/销毁 DOM），9 次 setStyle + 浏览器 paint < 5ms，远超 PRD 要求的 < 16ms

4. **StickyNote 模块** — 绝对定位 div（在 `#map` 容器内），从 `containerPoint` 计算四方向避让（右-下/左-下/右-上/左-上），三角箭头 CSS border 旋转 45° 始终指向点击网格，`cubic-bezier(0.34,1.56,0.64,1)` 回弹动画

5. **内容差异** — L0 展示精确权属文本，L1-L5 解析 ownership JSON 比例展示首要权属 + land_type_top3 折叠展开 + grid_count_original 标注

6. **旧方案 B 完全删除** — `#panel-overlay` + `.detail-card` DOM/CSS/JS 均删除（~120 行移除），旧 `openDetail()/closeDetail()/renderDetail()` 全部迁移到 `StickyNote` 类

7. **`/api/map/ninegrid` 端点保留** — zoom 16-18 按点查询降级路径仍需它

汇报已写入 `outputs/handoffs/04_report_arch_preload_sticky.md`，请查阅并转给 Orchestrator 质检。
