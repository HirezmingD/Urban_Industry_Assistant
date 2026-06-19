# V1.2：渔网数据预处理——CGCS2000→WGS84 + 入库

**指令编号**：05_impl_preprocess_fishnet  
**目标 Agent**：实现 Agent  
**优先级**：P0（没有渔网数据，框选评估永远是 "0 个网格"）  
**预估耗时**：1-2 小时（主要是 ~18 万条数据入库时间）

---

## 背景

同伴已完成渔网空间连接，交付文件：

```
E:\【资源】数据\桐庐建德三调\桐庐geojson\
├── 渔网_空间连接_土地利用信息.geojson    ← 带完整属性（179MB, ~18万条）
└── 渔网_空间连接_土地利用信息_属性表表头缩写说明.txt
```

渔网坐标系为 **CGCS2000 投影**（非 WGS84 地理坐标），需转换为 WGS84 (EPSG:4326) 后才能在前端天地图（img_w 服务）上正确渲染。数据含 26 个属性字段：用地类型（DLMC/DLBM）、权属（QSSX/QSDWMC）、坐落（ZLDWMC）、混合地类（SFHHDL/HHDLMC）、匹配方式（PPFS）等。

**核心任务：写一个预处理脚本，读 GeoJSON → 转坐标系 → 写入 land_grid 表。**

---

## 数据字段映射

| 渔网字段 | 含义 | land_grid 表字段 | 说明 |
|----------|------|:---|------|
| `WGBH` | 网格编号 | `grid_id` | 加前缀，格式 `grid_{WGBH}` |
| `DLMC` | 地类名称 | `land_type` | 如"乔木林地""工业用地" |
| `DLBM` | 地类编码 | `land_code` | 如 0301, 0601 |
| (固定值) | 面积 | `area_sqm` | 100m 网格 = 10000.0 |
| `QSSX` | 权属属性 | `ownership` | 如"大源村""国有" |
| `ZLDWMC` | 坐落单位名称 | `town` | 如"芦茨村""渡济村" |
| `HHDLMC` | 混合地类名称 | `mixed_type` | `SFHHDL="是"` 时赋值，否则 NULL |
| (计算) | 外接矩形 | `min_lng/max_lng/min_lat/max_lat` | 从 WGS84 Polygon 计算 |
| Polygon | 几何 | `geometry` | WKB 二进制格式（pyproj 转换后） |
| — | 遥感指标 | `nl_mean/ndvi_mean/pm25_mean` | 当前全部 NULL（同伴后续提供） |
| 多个字段 | 完整属性 | `extras` | JSON 存 PPFS/ZJTBJL/DLSL/QSDWMC 等余下字段 |

---

## 预处理脚本设计

### 文件：`scripts/preprocess_fishnet.py`

```python
"""
渔网数据预处理：CGCS2000 → WGS84 + 入库。
执行环境: D:\TOOLS\MiniConda\envs\agent_gpu_py311\python.exe
预计耗时: 10-20 分钟（~18万条逐条转换+入库）
依赖: pyproj（已安装）
"""

import json
import sys
from pathlib import Path
from pyproj import Transformer

# === 路径 ===
INPUT = Path(r"E:\【资源】数据\桐庐建德三调\桐庐geojson\渔网_空间连接_土地利用信息.geojson")
OUTPUT_WGS84 = Path("data/processed/tonglu_fishnet_wgs84.geojson")

# === 坐标系转换（CGCS2000 3-degree GK zone 40 → WGS84）===
# 注意：渔网坐标可能是 EPSG:4525（CGCS2000 / 3-degree GK zone 40，单位米）
# 也可能是加带号的变体。先用 EPSG:4525 试，验证转换后是否落入桐庐 WGS84 范围。
# 验证标准：转换后的 lng 应在 119.0~120.0，lat 应在 29.0~31.0。
# 如偏移过大，尝试 EPSG:4547（CGCS2000 / 3-degree GK CM 120E）等备选。

try:
    transformer = Transformer.from_crs("EPSG:4525", "EPSG:4326", always_xy=True)
    # 测试转换第一个点验证
    test_x, test_y = 40479107.617, 3285182.295
    test_lng, test_lat = transformer.transform(test_x, test_y)
    if not (119.0 < test_lng < 120.5 and 29.0 < test_lat < 30.5):
        raise ValueError(f"坐标验证失败: ({test_lng:.4f}, {test_lat:.4f}) 不在桐庐范围内")
    print(f"[OK] 坐标验证通过: EPSG:4525 → WGS84 ({test_lng:.6f}, {test_lat:.6f})")
except Exception as e:
    print(f"[ERROR] EPSG:4525 转换验证失败: {e}")
    print("请检查渔网坐标系，可能需要不同的 EPSG 代码")
    sys.exit(1)
```

### 关键点

1. **坐标系验证**（最高优先级）：脚本启动时必须转换第一个点并验证是否落在桐庐 WGS84 范围（119.0-120.0, 29.0-31.0）。如不通过，调整 EPSG 代码重试。

2. **geometry 存储格式**：使用 **WKB**（Well-Known Binary），SQLite R-tree 支持 WKB 几何的空间索引。用 `shapely.wkb.dumps()` 转换。

3. **批量插入**：~18 万条数据，必须用事务批量提交（每 5000 条 commit 一次），否则 SQLite 逐条插入会极慢。

4. **extras 字段**：将 PPFS（匹配方式）、ZJTBJL（最近图斑距离）、DLSX（地类属性）、DLSL（地类数量）、SFHHDL（是否混合地类）、HHDLBM（混合地类编码）、QSDWMC（权属单位名称）、QSDWSL（权属单位数量）、SFHHQSDW（是否混合权属）、HHQSDW（混合权属清单）、QSHHQK（权属混合情况）、ZLSX（坐落属性）、ZLDWSL（坐落单位数量）、SFHHZLDW（是否混合坐落）、HHZLDW（混合坐落清单）、ZLHHQK（坐落混合情况）、ZTBNBBH（主图斑内部编号）等字段打包为 JSON 存入 extras。

5. **不输出完整 WGS84 GeoJSON**（可选）：18 万条 Polygon 的 GeoJSON 文件会非常大，当前先存 SQLite，后端查询时实时构造 GeoJSON 响应。如需静态文件兜底，可选择性输出。

---

## 交付物

| # | 文件 | 说明 |
|---|------|------|
| 1 | `scripts/preprocess_fishnet.py` | 预处理脚本 |
| 2 | `data/processed/` 目录 | 可选：WGS84 GeoJSON 备份 |

---

## 执行

```bash
cd /d/Projects/Urban_Industry_Assistant && D:/TOOLS/MiniConda/envs/agent_gpu_py311/python.exe scripts/preprocess_fishnet.py
```

脚本末尾打印：
- 总条数 / 成功条数 / 失败条数
- 耗时
- 用地类型分布 Top 10
- 乡镇分布 Top 10

---

## 后续（批次 F 另开指令）

入库后需要改三处才能让前端真正看到数据：
- `grid_service.py`：bbox 查询返回真实数据
- `map_routes.py`：`/api/map/query` 返回真实 GeoJSON
- `eval_service.py`：`evaluate_grids()` 基于真实地块属性做评估

本批次只做到**数据入库 + 验证查询**，代码改造下一批。

---

## 验证标准

| 项 | 标准 |
|------|------|
| 坐标系验证通过 | 转换后点落入桐庐 WGS84 范围 |
| land_grid 表有数据 | `SELECT COUNT(*) FROM land_grid` ≈ 18 万 |
| bbox 查询可用 | `SELECT COUNT(*) FROM land_grid WHERE min_lng > 119.5 AND max_lng < 119.6` 返回 >0 |
| 用地类型分布 | Top 10 打印在脚本输出中 |
| 混合地类处理正确 | `SFHHDL="是"` 的网格 mixed_type 非空 |

---

## 完成后

汇报写入 `D:\Projects\Urban_Industry_Assistant\outputs\handoffs\05_report_impl_preprocess_fishnet.md`。

汇报格式：
```
## 执行结果
✅ / ❌

## 坐标系
- 采用 EPSG: XXXX
- 验证点: (原始) → (WGS84 lng, lat)

## 入库统计
- 总条数: 
- 成功: 
- 失败: 
- 耗时: 

## 用地类型分布 Top 5
| 类型 | 数量 |
|------|------|

## 乡镇分布 Top 5
| 乡镇 | 数量 |
|------|------|

## bbox 查询验证
- 查询 SQL:
- 返回条数:
```
