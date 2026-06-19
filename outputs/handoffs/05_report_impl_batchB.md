## 实现汇报

**任务**：实现批次 B — 核心服务层 4 个文件 + enterprises 表字段统一（第 2 批，共 5 批）
**完成状态**：完成

---

### 交付物清单

| # | 文件 | 路径 | 行数 |
|---|------|------|:--:|
| 1 | `__init__.py` | `src/prompts/__init__.py` | 1 |
| 2 | `system_prompt.py` | `src/prompts/system_prompt.py` | 132 |
| 3 | `__init__.py` | `src/services/__init__.py` | 1 |
| 4 | `grid_service.py` | `src/services/grid_service.py` | 263 |
| 5 | `policy_service.py` | `src/services/policy_service.py` | 198 |
| 6 | `eval_service.py` | `src/services/eval_service.py` | 257 |
| 7 | `database.py` | `src/database.py`（修改 enterprises 表） | 197 |
| 8 | `requirements.txt` | 追加 httpx≥0.27.0 | 13 |

---

### enterprises 表统一自检

| 检查项 | 状态 |
|--------|:--:|
| 旧字段 `area_mu` 已删除 | ✅ |
| 旧字段 `location_pref` 已删除 | ✅ |
| 旧字段 `facility_needs` 已删除 | ✅ |
| 旧字段 `investment` 已删除 | ✅ |
| 旧字段 `annual_output` 已删除 | ✅ |
| 新字段 `id` → TEXT PRIMARY KEY（对齐 Pydantic） | ✅ |
| 新字段 `annual_revenue` → TEXT（对齐 Pydantic） | ✅ |
| 新字段 `space_demand` → TEXT JSON（对齐 Pydantic） | ✅ |
| 新字段 `requirements` → TEXT JSON（对齐 Pydantic） | ✅ |
| 新字段 `priority_tags` → TEXT JSON（对齐 Pydantic） | ✅ |
| `created_at` → TIMESTAMP | ✅ |
| JSON 字段写入约定：`json.dumps` / 读取 `json.loads` | ✅（`ent_service` 批次 D 实现） |

---

### 验证结果

- [x] `from src.prompts import system_prompt` — 无报错
- [x] `from src.services import grid_service, policy_service, eval_service` — 无报错
- [x] `database.init_db()` — 幂等建表成功，enterprises 表字段与 Pydantic `Enterprise` 完全对齐
- [x] `get_system_prompt("government")` → 1495 字政府端 prompt
- [x] `get_system_prompt("enterprise")` → 603 字企业端 prompt
- [x] `build_eval_prompt()` → 拼接正常（284 字）
- [x] `calculate_weights()` → 返回 7 维权重
- [x] `get_policy_refs()` → 返回 10 条政策 key
- [x] `get_tonglu_industry_preference("精密制造")` → "优先供地"
- [x] `query_by_bbox()` — 空表兜底，不抛异常
- [x] `query_nine_grid()` — 空表兜底，返回空列表
- [x] `evaluate_grids()` — 无 API key 时返回降级结果
- [x] `parse_llm_response()` — JSON 解析 + 降级容错
- [x] 全文搜索 `sk-` / `tk=` / `48ad1b76` — 0 命中

---

### 关键设计决策

1. **`grid_service` 配置补充**：`config.py` 新增 `GRID_SIZE`、`BBOX_QUERY_LIMIT`、`MAP_ZOOM_MIN/MAX/INIT`、`GRID_VISIBLE_ZOOM`，来自 architecture.md §6，grid_service 直接引用。

2. **R-tree 两步法**：`query_by_bbox` 先查 `land_grid_rtree` 找 rowid，再 JOIN 主表取字段。`query_nine_grid` 用相同模式生成 3×3 邻格查询。shapely 精确过滤留 TODO（BatchD）。

3. **角色字段过滤在 SQL 层做**：`_select_fields(role)` 根据角色动态 SELECT 不同字段，企业端不返回 `ownership`/`land_code`/`geometry`。

4. **政策数据硬编码**：`POLICY_LIBRARY`（18 条）、`TONGLU_INDUSTRY_PREFERENCE`（26 条）、`_INDUSTRY_POLICY_MAP` 全部硬编码在 `policy_service.py` 中，不读文件不调 API。

5. **LLM 降级链**：无 API key → 降级；API 超时 → 降级；HTTP 错误 → 降级；JSON 解析失败 → 降级。降级结果始终含 `summary` 提示，前端可正常渲染。

6. **`config.py` 中模块级别 print 警告**：`DEEPSEEK_API_KEY` 和 `TIANDITU_API_KEY` 未设置时打印英文警告，避免 Windows GBK 编码问题。

---

### TODO 注释清单（按批次分组）

#### BatchC（API 路由层）
- 无。本批次 4 个模块的 API 封装留给 BatchC 的 `api/*.py` 调用。

#### BatchD（企业匹配 + 深度功能）
- `policy_service.py:44` — `calculate_weights` 动态微调权重（开发区/健康城/高碳排等地方调整）
- `policy_service.py:115` — `get_policy_refs` 根据 `land_type` 细化政策匹配
- `policy_service.py:119` — `get_policy_refs` 根据 `town` 细化政策匹配
- `eval_service.py:133` — `evaluate_grids` 中基于 `land_type_distribution` 和规则推断主导产业
- `eval_service.py:205` — `chat` 中无 bbox 纯文本咨询路径（当前退回 evaluate_grids）
- `grid_service.py` — shapely 精确过滤 `bbox` 结果（当前仅 R-tree 近似）

#### BatchE（前端 + 主程序）
- 无。

---

### 风险或遗漏

- **`grid_service.py` 264 行**，接近 300 行上限。若后续 BatchD 添加 shapely 精确过滤，建议拆分为 `grid_service.py`（核心查询）+ `grid_geoservice.py`（几何精确过滤）。
- **`eval_service.py`** 中的 LLM 调用已实装但未端到端测试（当前无 API key，所有路径走降级）。建议 BatchC 配置 key 后对 LLM 调用路径做一次端到端验证。
