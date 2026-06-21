# Urban_Industry_Assistant — 城市产业空间智能助手

> **2026「Beyond the Maze」EvoMap 黑客松参赛作品 · The Pearl 赛道（智能体自进化）**
>
> 当单体 Agent 的每一次评估、每一次匹配都在进化，它就不再是工具——而是县域政府身边最懂产业用地的 AI 参谋长。

---

## 作品简介

**Urban_Industry_Assistant** 是一个面向县域政府的产业用地智能评估系统。以中国东南某县为 Demo 样本区域，基于现状土地利用数据，通过 AI 对话式交互为规划部门提供地块评估、产业适配建议和企业需求匹配。

**核心命题**：中国县域经济中，土地一级市场由政府主导，但"这块地适合什么产业"的决策高度依赖人工经验。本作品让 AI Agent 在每次评估中自进化，逐渐逼近最优的"地-产"匹配逻辑。

*Agent主界面：四种交互模式*

![Demo界面截图1](https://obsidian-1-1315010744.cos.ap-shanghai.myqcloud.com/pic/2022/202606211038650.png)
![Demo界面截图2](https://obsidian-1-1315010744.cos.ap-shanghai.myqcloud.com/pic/2022/202606211038749.png)
![Demo界面截图3](https://obsidian-1-1315010744.cos.ap-shanghai.myqcloud.com/pic/2022/202606211038759.png)
![Demo界面截图4](https://obsidian-1-1315010744.cos.ap-shanghai.myqcloud.com/pic/2022/202606211038768.png)

---

## 赛道定位

| 赛道 | 方向 | 本作品对应 |
|------|------|------|
| **The Pearl** | 垂类领域自进化 | 空间规划 × 产业经济交叉领域 |

本作品深度应用 EvoMap 的 Gene（经验基因）/ Capsule（经验胶囊）/ Hub（集体智能）机制，让 Agent 的产业评估方法论随着使用逐步进化，形成"越用越懂本地"的正反馈。

---

## 技术架构

```
浏览器 (Leaflet + Chart.js)
    │
    ├─ 天地图卫星底图 (WMTS)
    ├─ 渔网矢量叠加层 (CGCS2000 → WGS84)
    ├─ 单格悬停高亮 / 点选 sticky note
    └─ 对话面板 / 企业匹配 / 自进化雷达
         │
    FastAPI 后端 (Python 3.11)
    ├─ /api/map/query     — 框选查询
    ├─ /api/map/ninegrid  — 鼠标悬停定位
    ├─ /api/map/grid/{id} — 单格详情
    ├─ /api/agent/chat    — AI 对话评估 (DeepSeek)
    ├─ /api/enterprise/*  — 企业匹配
    └─ /api/evomap/*      — 自进化状态
         │
    SQLite + R-tree 空间索引
    ├─ land_grid_L0 (100m × 185,564 格)
    └─ land_grid_L1~L5 (5 级聚合金字塔, 72K 格)
```

### 数据底座

- **现状土地利用数据**：185,564 个 100m×100m 渔网单元，CGCS2000 坐标系 → WGS84 转换入库
- **6 级 LOD 金字塔**：zoom 11-18 对应 3200m→100m 网格，R-tree 空间索引，框选查询 <200ms
- **12 家虚构企业**：覆盖智能制造 / 生物医药 / 文旅康养 / 快递物流等 12 个行业

### 隐私方案：公私分离

敏感决策数据（原始土地利用矢量、完整字段）永久留在本地 SQLite。通过 EvoMap 发布到 Hub 的只有脱敏后的评估方法论（Gene/Capsule）——**数据不出域，经验可共享**。

---

## 核心功能

| 功能 | 说明 |
|------|------|
| 🗺️ **卫星底图** | 天地图 WMTS 卫星影像，maxBounds 约束在县域范围 |
| 📐 **框选查询** | Leaflet.Draw 框选 → 空间查询 → 实时显示网格数与总面积 |
| 🖱️ **单格悬停** | 鼠标移动 → throttle 200ms → HTTP 单格高亮（fillOpacity 0.45） |
| 📋 **点选标签** | 点击网格 → 光标旁 sticky note（4 方向避让 + 三角箭头） |
| 🧠 **AI 评估** | 点"评估此地块" → DeepSeek 对话 → 产业适配评分 + 政策依据 |
| 🏭 **企业匹配** | 多选企业 → 全域最优用地匹配（政府端） |
| 📊 **自进化面板** | 能力雷达图（Chart.js）+ EvoMap 经验计数 + 进化曲线 |

---

## 两大使用角色

| | 政府端（默认） | 企业端 |
|------|:--:|:--:|
| 用户 | 地方规划与经信部门 | 中小企业主 |
| 可见数据 | 权属、用地代码、环境指标 | 仅公开属性 |
| 框选查询 | ✅ | ✅ |
| AI 评估立场 | 全县产业最优 | 企业个体最优 |
| 企业匹配 | ✅ 地图高亮 + 排序 | ❌ 仅建议 |

---

## 快速启动

### 环境要求

- Python 3.11
- 浏览器（Chrome / Edge）
- DeepSeek API Key
- 天地图 API Key（浏览器端）

### 安装

```bash
git clone <your-repo-url>
cd Urban_Industry_Assistant

# 配置密钥
cp .env.example .env
# 编辑 .env 填入 DEEPSEEK_API_KEY 和 TIANDITU_KEY

# 安装依赖
pip install -r requirements.txt

# 初始化数据库（需要渔网预处理脚本，见 preprocessing/）
# 或从备份恢复 db/uia.db

# 启动
python src/main.py
# 访问 http://127.0.0.1:8000
```

---

## 目录结构

```
Urban_Industry_Assistant/
├── data/              ← 原始数据（土地利用GeoJSON、卫星图）
├── research/          ← 研究文档（EvoMap方案、数据源、政策调研）
├── specs/
│   ├── arch/          ← 架构设计（LOD金字塔、sticky note、预加载方案）
│   └── src/           ← PRD 产品需求文档（v1.0 → v1.4）
├── src/
│   ├── api/           ← FastAPI 路由（map_routes / agent_routes / ent_routes / evo_routes）
│   ├── services/      ← 业务逻辑（grid_service / eval_service / policy_service）
│   ├── prompts/       ← System Prompt 模板
│   ├── config.py      ← 全局配置
│   ├── database.py    ← SQLite 连接 + R-tree
│   ├── schemas.py     ← Pydantic 模型
│   └── main.py        ← 应用入口
├── static/
│   ├── index.html     ← 单页应用
│   ├── app.js         ← 前端交互逻辑（351行）
│   └── app.css        ← 样式
├── db/                ← SQLite 数据库（186MB，.gitignore）
├── outputs/
│   └── handoffs/      ← Agent 协作日志（指令+汇报，84文件）
├── tests/             ← 测试
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## EvoMap 自进化设计

```
评估完成
  ↓
提取 Gene（经验基因）：地类-产业匹配偏好、评分权重偏移
  ↓
打包为 Capsule（经验胶囊）→ publish 到 EvoMap Hub
  ↓
下次评估时，Agent 检索 Hub 上的历史 Capsule
  ↓
System Prompt 注入进化后的方法论 → 评估更准确
```

- **Gene**：单次评估中提炼的微观经验（如"本地工业用地优先匹配精密制造"）
- **Capsule**：多次 Gene 压缩成的可发布经验单元
- **Hub**：EvoMap 集体智能，让异地 Agent 可复用本地经验

---

## 技术栈

| 层 | 技术 |
|------|------|
| 前端 | Leaflet.js · Chart.js · 天地图 WMTS · Vanilla JS |
| 后端 | FastAPI · Python 3.11 · httpx (async) |
| 数据 | SQLite · R-tree · pyproj (CGCS2000→WGS84) · Shapely (WKB) |
| AI | DeepSeek Chat API · System Prompt 工程 |
| 自进化 | EvoMap OAuth2 开发者平台 · A2A 协议 |
| 工具链 | 4 Agent 协作（内容/研究/架构/实现）· handoffs 文件驱动 |

---

## 致谢

- **EvoMap** — 自进化基础设施
- **相关数据提供方** — 土地利用数据（Demo 学术用途）
- **天地图** — 卫星影像底图服务

---

*Built in 48 hours for 「Beyond the Maze」Hackathon, June 19-21, 2026 · Hangzhou*
