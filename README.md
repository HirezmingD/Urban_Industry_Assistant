# Urban_Industry_Assistant — 城市产业空间智能助手

> 面向县域政府的 AI 自进化产业用地评估系统——让每一块地都有数据支撑的产业答案。

---

## 项目简介

**Urban_Industry_Assistant** 是一个面向县域政府的 AI 自进化产业用地评估系统。基于现状土地利用数据，通过 AI 对话式交互为规划部门提供地块评估、产业适配建议和企业需求匹配。

**核心命题**：中国县域经济中，土地一级市场由政府主导，但"这块地适合什么产业"的决策高度依赖人工经验。本系统让 AI Agent 在每次评估中自进化，逐渐逼近最优的"地-产"匹配逻辑。

> 🔗 **在线 Demo**：[http://124.222.191.117:8000/static/index.html](http://124.222.191.117:8000/static/index.html)

### Agent 主界面：四种交互模式

#### 场景一：询问 AI → 整体政策咨询
![Demo界面截图1](https://obsidian-1-1315010744.cos.ap-shanghai.myqcloud.com/pic/2022/202606211038650.png)

#### 场景二：单选/多选企业 → 企业选址匹配
![Demo界面截图2](https://obsidian-1-1315010744.cos.ap-shanghai.myqcloud.com/pic/2022/202606211038749.png)

#### 场景三：框选地块 → 合适产业推荐
![Demo界面截图3](https://obsidian-1-1315010744.cos.ap-shanghai.myqcloud.com/pic/2022/202606211038759.png)

#### 场景四：点选地块 → 用地及区位分析
![Demo界面截图4](https://obsidian-1-1315010744.cos.ap-shanghai.myqcloud.com/pic/2022/202606211038768.png)

---

## 技术架构

```
浏览器 (Leaflet + Chart.js + 智慧蓝 UI)
    │
    ├─ 天地图卫星底图 (WMTS)
    ├─ 渔网矢量叠加层 (CGCS2000 → WGS84)
    ├─ 单格悬停高亮 / 点选 sticky note / 行政区划悬停
    └─ 对话面板 / 企业匹配 / 自进化雷达
         │
    FastAPI 后端 (Python 3.11)
    ├─ /api/map/query       — 框选查询
    ├─ /api/map/ninegrid    — 鼠标悬停定位
    ├─ /api/map/grid/{id}   — 单格详情
    ├─ /api/agent/chat      — AI 对话评估 (DeepSeek)
    ├─ /api/enterprise/match — 企业择地匹配 (v2.4 独立引擎)
    └─ /api/evomap/*        — 自进化状态 & 经验胶囊
         │
    SQLite + R-tree 空间索引
    ├─ land_grid_L0 (100m × 185,564 格)
    └─ land_grid_L1~L7 (多级聚合金字塔)
```

### 数据底座

- **现状土地利用数据**：185,564 个 100m×100m 渔网单元，CGCS2000 坐标系 → WGS84 转换入库
- **74 字段评估指标体系**：含交通可达性、产业集聚度、权属协调度、设施距离等
- **多级 LOD 金字塔**：L0-L7 共 8 级，R-tree 空间索引，框选查询 <200ms
- **企业数据库**：覆盖精密制造、生物制药、物流仓储、数字经济等 14 个产业方向

### 隐私方案：公私分离

敏感决策数据（原始土地利用矢量、完整指标字段）永久留在本地 SQLite。通过 EvoMap 自进化协议发布的只有脱敏后的评估方法论（Gene/Capsule）——**数据不出域，经验可共享**。

---

## 核心功能

| 功能 | 版本 | 日期 | 说明 |
|------|:--:|:--:|------|
| 🗺️ **卫星底图** | v1.0 | 2026-06-19 | 天地图 WMTS 卫星影像，县域范围约束 |
| 📐 **框选查询** | v1.0 | 2026-06-19 | Leaflet.Draw 框选 → 空间查询 → 实时显示网格数与总面积 |
| 🖱️ **单格悬停** | v1.0 | 2026-06-19 | 鼠标移动 → 200ms 节流 → 单格高亮 |
| 📋 **点选标签** | v1.0 | 2026-06-19 | 点击网格 → sticky note（4 方向避让 + 三角箭头） |
| 🏷️ **行政区划悬停** | v1.3 | 2026-06-20 | 鼠标移入 → 乡镇边界高亮 + 名称 Tooltip |
| 🧠 **AI 评估** | v1.0 | 2026-06-19 | 框选 + 对话 → 七维模型评分 + 产业推荐 + 政策依据 |
| 🏭 **企业匹配** | v1.0 | 2026-06-19 | 多选企业 → 全域最优用地匹配（政府端） |
| 📊 **自进化面板** | v2.1 | 2026-06-20 | 能力雷达图 + 进化曲线 + 经验胶囊列表 |
| 🎨 **智慧蓝 UI** | v2.2 | 2026-06-21 | 15 CSS 变量双主题色彩系统，WCAG AA 通过 |
| 💬 **AI 回复卡片** | v2.3 | 2026-06-21 | 结构化卡片渲染 + 一键最大化模式 |
| 🗺️ **对话地图联动** | v2.3 | 2026-06-21 | 框选/视图网格硬编码推荐 → 地图高亮持久化 |
| 🎯 **企业择地匹配** | v2.4 | 2026-06-21 | 独立引擎：企业画像 × 视口网格 → 多维匹配（面积/产业/设施 40/40/20）→ 分组着色 |

---

## 两大使用角色

| | 政府端（默认） | 企业端 |
|------|:--:|:--:|
| 用户 | 地方规划与经信部门 | 中小企业主 |
| 可见数据 | 权属比例、用地代码、74 指标 | 仅公开属性 |
| 框选查询 | ✅ | ✅ |
| AI 评估立场 | 全县产业最优 | 企业个体最优 |
| 企业择地匹配 | ✅ 地图高亮 + 分组着色 | ✅ 开放权限 |

---

## 快速启动

### 环境要求

- Python 3.11
- 浏览器（Chrome / Edge）
- DeepSeek API Key
- 天地图 API Key（浏览器端）

### 安装

```bash
git clone <repo-url>
cd Urban_Industry_Assistant

# 配置密钥
cp .env.example .env
# 编辑 .env 填入 DEEPSEEK_API_KEY 和 TIANDITU_KEY

# 安装依赖
pip install -r requirements.txt

# 初始化数据库（需渔网预处理脚本，见 preprocessing/）
# 或从备份恢复 db/uia.db

# 启动
python src/main.py
# 访问 http://127.0.0.1:8000
```

---

## 目录结构

```
Urban_Industry_Assistant/
├── src/
│   ├── api/              ← FastAPI 路由
│   ├── services/         ← 业务逻辑（grid / eval / ent / gene）
│   ├── prompts/          ← System Prompt + 企业择地 Prompt
│   ├── config.py         ← 全局配置
│   ├── database.py       ← SQLite 连接 + R-tree
│   ├── schemas.py        ← Pydantic 模型
│   └── main.py           ← 应用入口
├── static/
│   ├── index.html        ← 三栏布局单页应用
│   ├── app.js            ← 前端交互逻辑
│   └── app.css           ← 智慧蓝色彩系统样式
├── preprocessing/        ← 数据预处理脚本（渔网生成/指标导入）
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## 自进化机制（集成 EvoMap）

本系统集成 [EvoMap](https://clawhub.ai/segasonicye/skills/evomap) 自进化 Skill（[开源](https://github.com/EvoMap/evolver)），让 Agent 的产业评估方法论随每次评估逐步优化。

```
评估完成
  ↓
提取 Gene（经验基因）：七维权重分布 + 产业-地类匹配偏好
  ↓
打包为 Capsule（经验胶囊）→ 通过 EvoMap 协议发布
  ↓
下次评估注入进化后的方法论 → System Prompt 动态更新
  ↓
反馈修正触发版本演进 → Gene v1.0 → v2.0
```

- **Gene**：单次评估中提炼的评估策略快照——七维权重、推荐产业、置信度
- **Capsule**：附带有场景/触发原因/影响摘要的经验单元，支持去重与震荡保护
- **集体智能**：通过 EvoMap Hub 共享评估经验，让异地实例可复用本地积累的产业评估方法论
- **版本演进**：反馈修正触发主版本升级，权重变化 >5% 触发次版本迭代，1 小时震荡保护防频繁跳动

---

## 技术栈

| 层 | 技术 |
|------|------|
| 前端 | Leaflet.js · Chart.js · 天地图 WMTS · Vanilla JS |
| 后端 | FastAPI · Python 3.11 · httpx (async) |
| 数据 | SQLite · R-tree · pyproj (CGCS2000→WGS84) · Shapely (WKB) |
| AI | DeepSeek Chat API · System Prompt 工程 · 多 Prompt 模板 |
| 自进化 | EvoMap 协议 · Gene/Capsule 经验管理 · 去重 & 震荡保护 |
| 工具链 | 多 Agent 协作 · handoffs 文件驱动 · 5 阶段开发流水线 |

---

## 致谢

- **EvoMap** — 自进化基础设施（[Clawhub Skill](https://clawhub.ai/segasonicye/skills/evomap) · [开源](https://github.com/EvoMap/evolver)）
- **相关数据提供方** — 土地利用数据（学术用途）
- **天地图** — 卫星影像底图服务
