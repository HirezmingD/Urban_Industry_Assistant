## 实现汇报

**任务**：实现批次 C — evo_service + ent_service + map_routes + agent_routes（第 3 批，共 5 批）
**完成状态**：完成

---

### 交付物清单

| # | 文件 | 路径 | 行数 |
|---|------|------|:--:|
| 1 | evo_service.py | `src/services/evo_service.py` | 356 ⚠️ |
| 2 | ent_service.py | `src/services/ent_service.py` | 187 |
| 3 | api/__init__.py | `src/api/__init__.py` | 1 |
| 4 | map_routes.py | `src/api/map_routes.py` | 135 |
| 5 | agent_routes.py | `src/api/agent_routes.py` | 55 |
| — | schemas.py | `src/schemas.py`（追加 6 个 API 模型） | 275 |

---

### 验证结果

- [x] `from src.services import evo_service, ent_service` — 无报错
- [x] `from src.api import map_routes, agent_routes` — 无报错
- [x] EvoMap 不可达降级（`http://invalid.local`）：
  - `hello()` → `{"status": "offline"}` ✅
  - `heartbeat()` → `{"status": "offline"}` ✅
  - `publish()` → `{"status": "offline"}` ✅
- [x] `get_evolution_stats()` 空表兜底：全部归零，雷达基线 30 ✅
- [x] `list_enterprises()` 空表 → `[]` ✅
- [x] `match_enterprises()` 空表 → `[]` ✅
- [x] `match_enterprises(role="enterprise")` → `PermissionError` → API 层 403 ✅
- [x] API 路由注册正确：
  - `/api/map/query` / `/api/map/grid/{grid_id}` / `/api/map/ninegrid`
  - `/api/agent/chat`
- [x] 全文搜索 `sk-` / `sk-ce4` / `48ad1b76` — 0 命中
  - `tk=` 命中为 URL 模板占位符 `{key}`，非真实密钥 ✅

---

### EvoMap 客户端关键设计决策

1. **凭证三级读取链**：`config.py 环境变量` → `~/.evomap/` 文件 → `hello()` 注册返回 → 持久化写入 `~/.evomap/`
2. **降级路径全覆盖**：所有 async 方法用 try/except 包裹 httpx 调用，异常返回 `{"status": "offline", "error": str}`，不抛异常
3. **`start_heartbeat_loop`**：`while True` 死循环，网络异常仅 log 不退出
4. **`compute_asset_id`**：排除 `asset_id` 字段，递归标准化 dict/list，按 key 排序 → canonical JSON → SHA-256
5. **`status()`**：纯本地读取（心跳时间戳 + 模块级缓存），不调 hub
6. **`get_evolution_stats()`**：纯本地 SQL 聚合，不调 hub
7. **Capsule 本地缓存**：`publish()` 不管成功失败都写 `evomap_capsules` 表，失败标记 `publish_status="rejected"`

---

### 空数据兜底自检

| 场景 | 方法 | 行为 |
|------|------|------|
| `evaluations` 表为空 | `get_evolution_stats()` | 返回全零结构，雷达基线 30，`preference_understanding=30.0` |
| `land_grid` 表为空 | `query_by_bbox()` 等 | 批次 B 已实现空表兜底（返回空结果，不抛异常） |
| `enterprises` 表为空 | `list_enterprises()` | 返回 `[]` |
| `enterprises` 表为空 | `match_enterprises()` | 返回 `[]` |
| `evomap_capsules` 表为空 | `get_evolution_stats()` | `capsule_contributed=0`，不报错 |

---

### EvoMap 不可达自检

| 方法 | 降级行为 | 结果 |
|------|---------|------|
| `hello()` | HTTPX 异常 → 返回 `{"status": "offline"}` | ✅ 通过 |
| `heartbeat()` | HTTPX 异常 → 返回 `{"status": "offline"}` | ✅ 通过 |
| `publish()` | HTTPX 异常 → 返回 `{"status": "offline"}` + 本地缓存写入 `rejected` | ✅ 通过 |
| `start_heartbeat_loop()` | 循环内异常 → log + 继续 sleep | ✅ 设计保证 |

---

### ⚠️ evo_service.py 行数超限

**当前 356 行**，超过 300 行上限。建议拆分方案：

| 拆分后文件 | 内容 | 预估行数 |
|-----------|------|:--:|
| `src/services/evo_client.py` | `EvomapClient` 类（A2A 协议核心） | ~220 |
| `src/services/evo_stats.py` | `get_evolution_stats()`（本地统计聚合） | ~80 |
| `src/services/evo_service.py` | 模块级单例 `evo_client` + re-export | ~15 |

> 是否执行拆分，请 Orchestrator 确认。本批次先保留原样，拆分为低优先级。

---

### TODO 注释清单

#### BatchD（企业匹配深度 + API 路由补齐）
- `ent_service.py` — `match_single_enterprise` P3 标记，当前从简实现
- `evo_service.py:299` — `get_evolution_stats` 雷达图精确算法（基于 evaluations.confidence 均值）

#### BatchE（前端 + main.py）
- 无（evo/ent 路由由 BatchD 做，main.py 由 BatchD 做）

---

### 与 modules.md / api.md 的偏离之处

| # | 偏离点 | 原因 |
|---|--------|------|
| 1 | `ChatRequest` 字段从 `messages + context` 改为 `message + role + bbox + context` | 对齐 `api.md` 和 `agent_routes.py` 实际调用方式 |
| 2 | `config.py` 追加 `LLM_TIMEOUT` / `CHAT_MAX_LENGTH` / `CHAT_CONTEXT_TURNS` | `agent_routes` 和 `eval_service` 需要引用 |
| 3 | `evo_service.hello()` 的 `payload` 不含 `env_fingerprint` | 指令文件明确列出的 payload 字段中无此字段，避免提交不必要信息 |
| 4 | `ent_service.match_enterprises()` 返回 `list[dict]` 而非 `list[EnterpriseMatchResult]` | Pydantic 模型已定义，本方法返回 dict 便于 service 层灵活构造；API 路由层（BatchD）可统一转 Pydantic |

---

### 风险或遗漏

- **`evo_service.py` 356 行超限**，建议 BatchD 前拆分
- **ent_service.match_enterprises() 全域查询性能**：当前用 `TONGLU_BBOX` 全范围查询（~18 万条），实际线上会截断到 BBOX_QUERY_LIMIT(500)。建议 BatchD 改为按空间需求精确过滤，避免每次都扫全表
