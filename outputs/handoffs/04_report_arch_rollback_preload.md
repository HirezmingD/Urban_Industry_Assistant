## 架构汇报（九宫格预加载回退）

**任务**：按 PRD v1.3 回退预加载架构，删除 GridLayerManager，保留 StickyNote，新增简化方案章节 + 删除/保留迁移表。

**完成状态**：完成

**架构文档路径**：`specs/arch/preload_sticky_design.md`（已覆盖写入，15.9 KB）

---

**修订内容**：

1. **删除**：GridLayerManager 类（~80 行 JS）、所有预加载相关引用（zoomend/mousemove/click/mouseout 中的 7 个调用点）、透明层 setStyle 状态机、zoom 11-15 分级加载策略

2. **保留**：StickyNote 类（四方向定位 + 三角箭头 + 动画）、sticky note DOM + CSS（~80 行）、`loadGridLight()` 渔网精简层、`setupDrawControl()` 框选

3. **新增**：「九宫格简化方案」章节 — mousemove 200ms throttle → HTTP fetch → renderNineGrid，click 事件直接调 `/api/map/ninegrid` → `/api/map/grid/{id}` → StickyNote.toggle

4. **迁移表**：13 项删除清单（精确到行级）+ 15 项保留清单（含角色标注），实现 Agent 可据此逐行执行

5. **`/api/map/grid_layer` 端点保留不调用**——代码不动，仅前端不调，为未来预加载优化预留

汇报已写入 `outputs/handoffs/04_report_arch_rollback_preload.md`，请查阅并转给 Orchestrator 质检。
