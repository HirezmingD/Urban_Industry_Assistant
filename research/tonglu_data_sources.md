# 桐庐县开源数据源摸底

> **研究目的**：为 Urban_Industry_Assistant 补充三调矢量数据之外的产业用地评估维度
> **编写日期**：2026-06-18
> **样本区域**：浙江省杭州市桐庐县

---

## 一、总体评估

| 类别 | 可用数据源数 | Demo 阶段推荐使用 | 说明 |
|------|:--------:|:--------:|------|
| 政府统计 | 5+ | 2-3 | 年鉴/公报可直接引用，栅格需预处理 |
| 栅格数据 | 6+ | 2-3 | NDVI/夜间灯光/GDP 地均下载即用 |
| 企业信息 | 3 | 0 | 反爬风险高，Demo 用虚构数据代替 |
| 合计 | 14+ | 5-6 | — |

**策略建议**：Demo 阶段用 **虚构案例 + 少数真实栅格数据** 的组合。评委看重的是评估逻辑的合理性，不是数据集的完整性。

---

## 二、统计局/年鉴/公报类数据

### 2.1 桐庐县国民经济和社会发展统计公报

| 属性 | 内容 |
|------|------|
| 来源 | 桐庐县统计局 |
| URL | `http://www.tonglu.gov.cn` → 政府信息公开 → 统计信息 |
| 获取方式 | 直接下载 PDF/HTML |
| 频率 | 年度 |
| 可用性 | ✅ 可直接下载 |
| Demo 可操作性 | ⭐⭐⭐⭐⭐ |

**内容涵盖**：GDP（分产业）、工业增加值、固定资产投资、进出口、常住人口、人均可支配收入、财政收支等。这些是评估地块产业适配度的基础宏观背景数据。

### 2.2 浙江省统计年鉴

| 属性 | 内容 |
|------|------|
| 来源 | 浙江省统计局 |
| URL | `https://tjj.zj.gov.cn/col/col1525563/index.html` |
| 获取方式 | 在线浏览 / 下载 PDF / 数据浙江平台查询 |
| 频率 | 年度 |
| 可用性 | ✅ 可直接下载 |
| Demo 可操作性 | ⭐⭐⭐⭐ |

**内容涵盖**：全省及各地市的 GDP、人口、土地利用、能源消费、环境指标等。可作为桐庐数据与全省平均的对比基准。

### 2.3 杭州市统计年鉴

| 属性 | 内容 |
|------|------|
| 来源 | 杭州市统计局 |
| URL | `https://tjj.hangzhou.gov.cn` → 统计年鉴 |
| 获取方式 | 直接下载 |
| 可用性 | ✅ 可直接下载 |
| Demo 可操作性 | ⭐⭐⭐⭐ |

**用途**：获取杭州市各县（含桐庐）的横向对比数据，用于评估桐庐在杭州市域内的产业定位。

### 2.4 桐庐县第三次全国国土调查主要数据公报

| 属性 | 内容 |
|------|------|
| 来源 | 桐庐县规划和自然资源局 |
| URL | `http://www.tonglu.gov.cn` → 规划和自然资源局 → 公告公示 |
| 获取方式 | 直接下载 PDF |
| 可用性 | ✅ 已公开 |
| Demo 可操作性 | ⭐⭐⭐⭐⭐ |

**⚠️ 注意**：这是三调数据的**汇总公报**（耕地多少、建设用地多少等宏观数字），不是地块级别的矢量数据。项目已经在处理三调矢量 GeoJSON，本条是补充宏观背景。

### 2.5 桐庐县政府工作报告

| 属性 | 内容 |
|------|------|
| 来源 | 桐庐县人民政府 |
| URL | `http://www.tonglu.gov.cn` → 政府信息公开 → 规划信息 |
| 获取方式 | 直接下载 |
| 频率 | 年度 |
| 可用性 | ✅ 可直接下载 |
| Demo 可操作性 | ⭐⭐⭐⭐⭐ |

**内容涵盖**：上年度经济数据回顾、本年度产业目标、重点项目清单。可直接用于 Agent 评估建议的政策依据。

---

## 三、栅格数据

### 3.1 NDVI（归一化植被指数）

| 属性 | 内容 |
|------|------|
| 产品 | MODIS MOD13Q1 v061（250m, 16天） |
| 来源 | NASA LAADS DAAC / Google Earth Engine |
| URL | `https://lpdaac.usgs.gov/products/mod13q1v061/` |
| 获取方式 | Earthdata 账号注册（免费）→ 直接下载 / GEE 在线处理 |
| 可用性 | ⚠️ 需注册（免费，几分钟完成） |
| Demo 可操作性 | ⭐⭐⭐⭐ |

**评估用途**：衡量地块周边植被覆盖度。高 NDVI → 生态敏感区 → 不适合重工业；低 NDVI → 已开发区域 → 适合产业用地再开发。

**Demo 建议**：GEE 直接导出桐庐范围的 NDVI 均值 GeoTIFF，一次操作即可。或者直接下载 2024 年夏季一景，裁剪到桐庐行政区范围。

### 3.2 夜间灯光（NPP-VIIRS）

| 属性 | 内容 |
|------|------|
| 产品 | VIIRS VNL v2.1（年度合成, ~500m） |
| 来源 | Colorado School of Mines / NOAA |
| URL | `https://eogdata.mines.edu/products/vnl/` |
| 获取方式 | 直接下载（无需注册） |
| 可用性 | ✅ 可直接下载 |
| Demo 可操作性 | ⭐⭐⭐⭐⭐ |

**评估用途**：
- 反映经济活跃度：夜间灯光亮度 ≈ 地均 GDP 的 proxy
- 识别建成区边界：高亮度区域 = 城镇核心区
- 发现"低效用地"：城区内低亮度斑块 = 可能的闲置/低效用地

**Demo 建议**：下载 2023 或 2024 年度全球 VNL GeoTIFF，用 GDAL 裁剪到桐庐县范围。约 2GB，裁剪后 < 10MB。

### 3.3 地均 GDP（Gridded GDP）

| 属性 | 内容 |
|------|------|
| 产品 | 中国 1km 网格 GDP 空间分布数据集 |
| 来源 | 资源环境科学与数据中心（RESDC） |
| URL | `https://www.resdc.cn/data.aspx?DATAID=256` |
| 获取方式 | 注册账号 → 申请下载 |
| 可用性 | ⚠️ 需注册+申请（通常当日通过） |
| Demo 可操作性 | ⭐⭐⭐ |

**评估用途**：直接反映地块周边的经济活动强度。高 GDP 网格 → 产业集聚区；低 GDP 网格 → 开发潜力待释放。

**替代方案**：夜间灯光可近似替代，Demo 阶段优先使用夜间灯光。

### 3.4 PM2.5（中国高分辨率PM2.5数据集）

| 属性 | 内容 |
|------|------|
| 产品 | ChinaHighPM2.5（1km, 年度/月度） |
| 来源 | Zenodo / Dalhousie University |
| URL | `https://zenodo.org/record/6398971` |
| 获取方式 | Zenodo 直接下载（免费） |
| 可用性 | ✅ 可直接下载 |
| Demo 可操作性 | ⭐⭐⭐⭐ |

**评估用途**：环境约束维度。高 PM2.5 区域不适合引入排放型产业，可引导发展绿色产业、数字经济等。

**Demo 建议**：下载桐庐所在地市范围的年度均值 GeoTIFF，叠加到评估模型。

### 3.5 碳排放（ODIAC / CEADs）

| 属性 | 内容 |
|------|------|
| 产品 | ODIAC 化石燃料碳排放（1km, 月度）/ CEADs 中国碳排放清单 |
| 来源 | ODIAC: `https://db.cger.nies.go.jp/dataset/ODIAC/` ; CEADs: `https://www.ceads.net.cn/` |
| 获取方式 | ODIAC 直接下载 / CEADs 直接下载 |
| 可用性 | ✅ 可直接下载 |
| Demo 可操作性 | ⭐⭐⭐ |

**评估用途**：高碳排放区域不适合引入新增排放项目。双碳政策背景下，碳排放约束是产业准入门槛之一。

**Demo 建议**：Demo 阶段可用 PM2.5 近似替代碳排放空间分布。如需精确数据，下载 ODIAC 月度产品裁剪。

### 3.6 降水与气温（ERA5-Land）

| 属性 | 内容 |
|------|------|
| 产品 | ERA5-Land 月均值（~9km, 再分析） |
| 来源 | ECMWF / Copernicus CDS |
| URL | `https://cds.climate.copernicus.eu/` |
| 获取方式 | 注册 CDS 账号 → API 下载 |
| 可用性 | ⚠️ 需注册（免费） |
| Demo 可操作性 | ⭐⭐ |

**评估用途**：极端降水区域不适合特定产业（如精密电子对湿度敏感）。对桐庐的产业评估影响较小。

**Demo 建议**：优先级低。可仅在 PPT 中提一句"考虑气候因子"，数据不做实际处理。

---

## 四、企业公开信息

### 4.1 天眼查 / 企查查

| 属性 | 内容 |
|------|------|
| 来源 | `https://www.tianyancha.com` / `https://www.qichacha.com` |
| 获取方式 | 网页搜索 / API（需企业认证+付费） |
| 可用性 | ❌ Demo 阶段不可行 |
| 反爬风险 | **极高** — 滑块验证、IP 限频、法律风险 |

**评估用途**：获取桐庐县注册企业列表、行业分布、注册资本、经营状态等。本可实现"企业需求 → 地块匹配"的闭环。

**Demo 替代方案**：手工构造 5-8 家典型企业 JSON（已在开发流程 0.4 中计划），完全足够 Demo 演示。

### 4.2 国家企业信用信息公示系统

| 属性 | 内容 |
|------|------|
| 来源 | `https://www.gsxt.gov.cn` |
| 获取方式 | 网页查询 |
| 可用性 | ❌ Demo 阶段不可行 |
| 反爬风险 | 高 — 验证码、IP 限频 |

### 4.3 浙江省/杭州市产业园区企业名录

| 属性 | 内容 |
|------|------|
| 来源 | 桐庐经济开发区管委会网站 / 杭州市经信局 |
| URL | `http://www.tonglu.gov.cn` → 经济开发区管委会 |
| 获取方式 | 网页浏览，可能有公开 PDF |
| 可用性 | ⚠️ 部分公开，需手动整理 |
| Demo 可操作性 | ⭐⭐（可获取但不值得花时间） |

---

## 五、优先推荐数据集（Top 5）

按照"下载即用、对产业评估贡献最大"的原则排序：

| 排名 | 数据集 | 获取难度 | 评估贡献 | 推荐理由 |
|:--:|------|:--:|:--:|------|
| 1 | **夜间灯光（VIIRS）** | 极低 | ⭐⭐⭐⭐⭐ | 经济活跃度 proxy，直接反映县域空间发展格局，下载即用 |
| 2 | **桐庐县统计公报** | 极低 | ⭐⭐⭐⭐⭐ | GDP、人口、产业结构的宏观数据，Agent prompt 必备上下文 |
| 3 | **NDVI（MODIS）** | 低 | ⭐⭐⭐⭐ | 生态约束，可直观区分"已开发 vs 生态敏感"地块 |
| 4 | **PM2.5（ChinaHighPM2.5）** | 低 | ⭐⭐⭐⭐ | 环境约束，与产业准入直接相关（双碳政策） |
| 5 | **地均 GDP（RESDC）** | 中 | ⭐⭐⭐⭐ | 精确反映经济空间分布，但需注册申请 |
| 备选 | **降水量（ERA5）** | 中 | ⭐⭐ | 优先用于 PPT 提及，非必要不下载 |

---

## 六、数据整合技术方案

### 栅格数据预处理脚本（Python/GDAL）

```python
import rasterio
import geopandas as gpd
from rasterio.mask import mask
import numpy as np

def clip_raster_to_tonglu(raster_path, geojson_path, output_path):
    """将栅格数据裁剪到桐庐县行政区范围"""
    tonglu = gpd.read_file(geojson_path)
    with rasterio.open(raster_path) as src:
        out_image, out_transform = mask(src, tonglu.geometry, crop=True)
        out_meta = src.meta.copy()
        out_meta.update({
            "height": out_image.shape[1],
            "width": out_image.shape[2],
            "transform": out_transform
        })
        with rasterio.open(output_path, "w", **out_meta) as dest:
            dest.write(out_image)
    return output_path

def zonal_stats_by_parcel(raster_path, parcels_gdf):
    """计算每个地块（GeoJSON 图斑）的栅格均值"""
    results = []
    with rasterio.open(raster_path) as src:
        for idx, row in parcels_gdf.iterrows():
            out_image, _ = mask(src, [row.geometry], crop=True)
            mean_val = out_image[out_image > src.nodata].mean()
            results.append({"parcel_id": row.get("id", idx), "value": round(float(mean_val), 4)})
    return results
```

---

## 七、信息缺口与注意事项

| 缺口/风险 | 说明 | 处理建议 |
|------|------|------|
| 三调矢量数据获取渠道 | 需要确认和洲手中的三调数据来源和坐标系 | 直接询问和洲，确保用 CGCS2000 或 WGS84 |
| 桐庐县行政区划 GeoJSON | 裁剪栅格数据用的边界文件 | 可从阿里云 DataV 下载或手工构造 |
| ERA5 9km 分辨率偏低 | 对县域级分析粗 | Demo 阶段不用，PPT 里提一句即可 |
| 栅格数据时效性 | MODIS/NDVI 16天合成为夏季植被高峰，不能反映全年 | 选用 2024 年夏季 6-8 月数据取均值 |
| 企业数据反爬 | 天眼查/企查查完全不可行 | 已在开发流程中计划虚构案例，无影响 |

---

## 八、结论

**Demo 阶段最经济的方案**：
- ✅ 下载夜间灯光（VIIRS）+ PM2.5（ChinaHighPM2.5）+ NDVI（MODIS 一景）→ 1 小时
- ✅ 下载桐庐县统计公报 PDF → 10 分钟
- ✅ 用 Python/GDAL 裁剪并计算地块 zonal stats → 30 分钟
- ✅ 虚构 5-8 家企业案例 → 30 分钟

**总计约 2 小时数据准备**，产出 3-4 层栅格叠加 + 统计公报宏观背景 + 企业案例，足够支撑产业用地多维评估。

> **一句话**：Demo 阶段数据不求全，求"有说服力的维度"。夜间灯光 + PM2.5 + NDVI 三张图叠加到三调底图上，已经足够讲一个好故事。

---

*信息缺口：桐庐县三调矢量数据的具体获取渠道和坐标系参数需向和洲确认。*
