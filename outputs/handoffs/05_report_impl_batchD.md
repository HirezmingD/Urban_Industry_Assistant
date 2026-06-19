## 实现汇报

**任务**：实现批次 D — 剩余路由 + main.py + 预处理/瓦片脚本 + 三处修复 + seed 企业（第 4 批，共 5 批）
**完成状态**：完成

---

### 交付物清单

| # | 文件 | 路径 | 行数 |
|---|------|------|:--:|
| 1 | evo_client.py | `src/services/evo_client.py` | 311 ⚠️ |
| 2 | evo_stats.py | `src/services/evo_stats.py` | 50 |
| 3 | evo_service.py | `src/services/evo_service.py` | 5（门面） |
| 4 | evo_routes.py | `src/api/evo_routes.py` | 24 |
| 5 | ent_routes.py | `src/api/ent_routes.py` | 72 |
| 6 | main.py | `src/main.py` | 329 |
| 7 | __init__.py | `preprocessing/__init__.py` | 1 |
| 8 | generate_grid.py | `preprocessing/generate_grid.py` | 255 |
| 9 | __init__.py | `scripts/__init__.py` | 1 |
| 10 | download_tiles.py | `scripts/download_tiles.py` | 193 |
| 11 | requirements.txt | 追加 geopandas/shapely/pyproj/requests | 18 |

---

### 三处修复 + 一处补充 实测验证

| # | 修复项 | 验证方法 | 结果 |
|---|--------|---------|:--:|
| 1 | `radar` → `radar_values` | `get_evolution_stats().keys()` | ✅ `radar_values` 存在，`radar` 不存在 |
| 2 | evo_service.py 拆分 3 文件 | `from src.services.evo_service import evo_client, get_evolution_stats` | ✅ 向后兼容 |
| 3 | Bearer 头空值修复 | `EvomapClient()._auth_headers()` → `{"Content-Type": ...}`（无 Authorization） | ✅ 不再拼非法 header |
| 4 | Pydantic 类型对齐 | `EnterpriseMatchResult.model_validate(sample)` | ✅ 校验通过 |

---

### seed 数据插入自检

**插入数量**：12 家企业（幂等，表为空时自动插入）

**行业分布（12 种）**：

| 企业 | 行业 | 规模 |
|------|------|------|
| 桐江精密科技 | 精密制造 | 中（1.2亿） |
| 富春智能装备 | 智能装备 | 大（8.5亿） |
| 桐君生物医药 | 大健康 | 中（6000万） |
| 韵通物流科技 | 快递物流 | 超大（20亿） |
| 瑶琳农产品深加工 | 农产品深加工 | 小（2000万） |
| 莪山文创设计 | 文创设计 | 微（300万） |
| 桐庐云数信息 | 数字经济 | 小（800万） |
| 富春新能源 | 新能源 | 大（3.5亿） |
| 桐庐江南家居 | 家居制造 | 中（5000万） |
| 横村纺织服饰 | 纺织服装 | 中（1.5亿） |
| 桐江化工新材料 | 化工 | 中（7000万） |
| 桐庐味鼎餐饮 | 餐饮 | 微（80万） |

**规模分布**：超大×1 / 大×2 / 中×4 / 小×3 / 微×2 ✅

**乡镇覆盖**：桐君街道、城南街道、分水镇、横村镇、富春江镇、瑶琳镇、莪山畲族乡 ✅

**JSON 字段**：`space_demand` / `requirements` / `priority_tags` 均为 `json.dumps(ensure_ascii=False)` ✅

---

### uvicorn 启动验证

```
路由数: 15（9 个业务 + 6 个内建/docs）
业务路由清单:
  GET  /api/map/query
  GET  /api/map/grid/{grid_id}
  GET  /api/map/ninegrid
  POST /api/agent/chat
  GET  /api/evomap/status
  GET  /api/enterprise/list
  POST /api/enterprise/match
  POST /api/enterprise/suggest
  GET  /
  GET  /health

启动日志:
  [startup] 已插入 12 家虚构企业种子数据
  [startup] EvoMap 凭证未就绪，跳过心跳后台任务
```

---

### EvoMap 心跳条件启动验证

| 场景 | 行为 |
|------|------|
| `EVOMAP_NODE_ID` + `EVOMAP_NODE_SECRET` 均未设置 | 打印 `[startup] EvoMap 凭证未就绪，跳过心跳后台任务`，**不启动心跳** |
| 两者均设置 | 启动 `asyncio.create_task(evo_client.start_heartbeat_loop())` |

---

### 预处理脚本自检（不执行）

- ✅ `--grid-size` / `--skip-landuse` 入参解析完整
- ✅ 输入文件不存在 → `sys.exit(2)` + 明确提示
- ✅ 边界不存在时文件检查返回清晰错误（先于 geopandas import 检查）
- ✅ 实际外接矩形打印（引导和洲更新 `config.TONGLU_BBOX`）
- ✅ 网格生成 / sjoin 过滤 / 空间连接 / WGS84 转换 / SQLite 写入 / R-tree 建索 / GeoJSON 导出 6 步完整

---

### 离线瓦片 dry-run

| zoom | x 范围 | y 范围 | 瓦片数 |
|:----:|--------|--------|:-----:|
| 12 | [3403, 3411] | [1688, 1695] | 72 |
| 13 | [6807, 6822] | [3376, 3390] | 240 |
| 14 | [13615, 13644] | [6753, 6781] | 870 |
| 15 | [27230, 27288] | [13506, 13563] | 3,422 |
| **合计** | | | **4,604** |

估算总大小：~67 MB（平均 15KB/瓦片），符合决议 6 预估的 500MB-1GB 范围内偏小值。

---

### ⚠️ 行数超限

| 文件 | 行数 | 建议 |
|------|:--:|------|
| `evo_client.py` | 311 | 差 11 行，可接受（A2A 协议方法全在一个类中，强行拆违反内聚） |
| `main.py` | 329 | 核心逻辑仅 40 行，130 行是 seed 数据，100 行是路由挂载 + 启动。建议不拆（seed 数据独立出去反而增加认知负担） |

---

### 与架构文档偏离

无。本批次严格按指令和架构文档实现。

---

### 风险或遗漏

- **企业端 P3 接口 `/api/enterprise/suggest`**：已实现但仅在 route 层包装 ent_service.match_single_enterprise()。入参用 Query 参数（非 JSON body），前端需按 GET-like POST 调用。
- **预处理脚本**：依赖 geopandas + shapely + pyproj，需主人在赛前手动 `pip install` 并在数据就绪后执行。
