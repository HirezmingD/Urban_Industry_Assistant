# 指令：批次 E — 前端（静态 HTML + Leaflet 地图 + 对话面板 + 雷达图）

**发出方**：Orchestrator
**接收方**：实现 Agent
**时间**：2026-06-19
**项目**：Urban_Industry_Assistant
**批次**：E（共 5 批次的最后一批）

---

## 任务背景

批次 A/B/C/D 已完成所有后端工作，后端可启动、API 全通。本批次实现**前端单页应用**，挂载在 `static/index.html`，由 FastAPI 静态文件路由分发。

**关键约束**：
- 纯 HTML/JS/CSS，**无构建工具**，全部 CDN 引入
- 前端必须容忍**渔网属性逐步到位**（最早渔网仅有 Id + 几何，无 land_type/ownership/township，需灰色降级渲染）
- 政府端为 P0 主战场；企业端 P3 留接入点但不做完整 UI

---

## 输入材料（必读）

1. `D:\Projects\Urban_Industry_Assistant\specs\src\prd.md` — **核心需求**，特别看 §3.1 / §3.2 / §3.3 / §3.4 节
2. `D:\Projects\Urban_Industry_Assistant\specs\arch\api.md` — 所有后端 API 的请求/响应格式
3. `D:\Projects\Urban_Industry_Assistant\outputs\handoffs\04_addendum_arch_decisions.md` — 决议 4（天地图 img_w 服务）、决议 6（离线瓦片兜底）、决议 7（WGS84 渲染）
4. 已实现的后端 API（你可以在编码时启动 `uvicorn src.main:app` 调试）

---

## 整体设计

### 单页应用骨架（左右分栏 + 顶部切换）

```
┌──────────────────────────────────────────────────────────────────┐
│  顶栏：项目名 + 端切换（政府端 / 企业端）+ 健康状态                │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│   左侧（70%）：地图面板                  │  右侧（30%）：交互面板  │
│   ┌─────────────────────────────────┐    │  ┌────────────────┐  │
│   │                                 │    │  │ Tab1 对话      │  │
│   │      天地图卫星图               │    │  │ Tab2 企业列表  │  │
│   │      + 渔网叠加（透明）         │    │  │ Tab3 自进化    │  │
│   │      + 鼠标九宫格悬停           │    │  │                │  │
│   │      + 框选 / 点选              │    │  │ （对应内容）   │  │
│   │      + 候选高亮                 │    │  │                │  │
│   └─────────────────────────────────┘    │  └────────────────┘  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 技术栈（全部 CDN 引入）

| 库 | 版本 | CDN |
|---|---|---|
| Leaflet | 1.9.4 | unpkg.com/leaflet@1.9.4 |
| leaflet-draw | 1.0.4 | 矩形框选 |
| Chart.js | 4.4.x | 雷达图 |
| 无 jQuery / Vue / React | — | 纯 vanilla JS |

---

## 本批次任务（5 个文件）

### 任务 1：`static/index.html`

**职责**：单页 HTML 骨架。

**必须包含**：
- HTML5 文档头，UTF-8，viewport meta
- CDN 引入：leaflet.css / leaflet.js / leaflet-draw.css / leaflet-draw.js / chart.umd.js
- 自身样式 `app.css` + 脚本 `app.js`（同目录）
- 主结构：
  ```html
  <header>
    <h1>Urban_Industry_Assistant — 城市产业空间智能助手</h1>
    <div class="role-switch">
      <button data-role="government" class="active">政府端</button>
      <button data-role="enterprise">企业端</button>
    </div>
    <span class="health-badge" id="health-badge">●  在线</span>
  </header>
  <main>
    <div id="map"></div>
    <aside id="panel">
      <nav class="tabs">
        <button data-tab="chat" class="active">对话</button>
        <button data-tab="enterprises">企业列表</button>
        <button data-tab="evolution">自进化</button>
      </nav>
      <section id="tab-chat" class="tab-content active">...</section>
      <section id="tab-enterprises" class="tab-content">...</section>
      <section id="tab-evolution" class="tab-content">...</section>
    </aside>
  </main>
  ```

### 任务 2：`static/app.css`

**职责**：全局样式 + 各组件样式。

**关键要求**：
- **暗色系科技风**（适配卫星图底图、显得专业）：
  - 背景 `#0d1117`、面板 `#161b22`、文字 `#e6edf3`、强调色 `#58a6ff`
- 顶栏 fixed 高度 50px
- 左 70% 右 30%，flex 布局
- 地图填满左侧
- 右侧面板可滚动
- 九宫格透显的样式：
  - `.nine-grid-center` —— 中心格 fillOpacity 0.45，stroke 较粗
  - `.nine-grid-outer` —— 外围格 fillOpacity 0.20，stroke 较细
- 渔网类型着色（CSS 变量预留 12 类，前端按 `land_type` 映射；**当 land_type 为 null 时统一渲染浅灰** `#6e7681`）
- 候选高亮：橙色描边 + 半透明填充
- 加载态：`.loading` 旋转图标
- 对话气泡：
  - 用户消息右对齐、`#58a6ff` 背景
  - Agent 消息左对齐、`#21262d` 背景
- 雷达图容器：固定 280×280

### 任务 3：`static/app.js`

**职责**：所有交互逻辑入口。

**模块拆分**（注释清晰，避免单文件过大）：

```javascript
// ===== 1. 全局配置 =====
const API_BASE = '';  // 与 FastAPI 同源
const TIANDITU_KEY = '__INJECT_FROM_BACKEND__';  // 通过后端 /api/config 拿
const TONGLU_BBOX = [119.16, 29.58, 119.80, 30.12];

// ===== 2. 状态管理 =====
const state = {
  role: 'government',
  currentBbox: null,
  selectedEnterpriseIds: [],
  candidateGrids: [],
  evolutionStats: null,
  chatHistory: [],
  gridLayer: null,
  nineGridLayer: null,
  candidateLayer: null,
};

// ===== 3. 地图初始化 =====
function initMap() { ... }
function loadTiandituBaseLayer() { ... }    // 在线 img_w + 兜底本地路径
function setupBboxLock() { ... }            // 拖动越界自动回弹

// ===== 4. 渔网交互 =====
function loadGridLight() { ... }            // 加载精简版 GeoJSON
function setupMouseHover() { ... }          // 九宫格透显
function setupBoxSelection() { ... }        // 矩形框选
function highlightCandidates(gridIds) { ... }

// ===== 5. 右侧面板 =====
function setupTabs() { ... }
function setupRoleSwitch() { ... }

// ===== 6. 对话面板 =====
function appendChatMessage(role, content) { ... }
function sendChat(message) { ... }
function renderAgentReply(reply) { ... }    // 结构化结果展示

// ===== 7. 企业列表 =====
function loadEnterprises(search = '') { ... }
function setupEnterpriseMultiSelect() { ... }
function triggerMatch() { ... }

// ===== 8. 自进化展示 =====
function loadEvolutionStats() { ... }
function renderRadarChart(values) { ... }   // Chart.js 雷达图
function renderProgressBar(percentage) { ... }

// ===== 9. 健康检查 =====
function pollHealth() { ... }               // 每 30s 调 /health 刷新顶栏

// ===== 10. 启动 =====
window.addEventListener('DOMContentLoaded', async () => {
  await loadConfig();      // 从后端拿天地图 key 等
  initMap();
  loadGridLight().catch(() => { /* 渔网未就绪，灰色降级 */ });
  setupTabs();
  setupRoleSwitch();
  loadEnterprises();
  loadEvolutionStats();
  pollHealth();
});
```

**关键实现要求**：

#### 3.1 地图初始化与天地图叠加

- 用 Leaflet 的 `L.tileLayer` 加载天地图 `img_w` 卫星图：
  ```javascript
  const TIANDITU_URL_TEMPLATE = `http://t{s}.tianditu.gov.cn/img_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=img&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&tk=${TIANDITU_KEY}`;
  const baseLayer = L.tileLayer(TIANDITU_URL_TEMPLATE, {
    subdomains: ['0','1','2','3','4','5','6','7'],
    minZoom: 10, maxZoom: 18,
    errorTileUrl: '/data/tiles/{z}/{x}/{y}.png',  // 离线兜底
  });
  ```
- 注记层：用 `cia_w` 同样模板，叠加在卫星层之上
- 桐庐边界约束：`map.setMaxBounds([[lat_min, lng_min], [lat_max, lng_max]])`
- 初始视野定位到桐庐中心 `(119.685, 29.795)`，zoom=11
- 缩放级别限制 10-18

#### 3.2 渔网精简加载与降级

- 启动后调 `GET /static/grid_light.geojson` 加载精简版（如果存在）
- **若不存在或为空**：
  - 控制台 console.warn
  - 不渲染渔网层
  - 顶栏健康徽章显示"●  渔网未就绪"
  - 其他功能（对话、企业列表、自进化）继续工作
- 渲染时按 `land_type` 着色，**land_type 为 null/缺失时统一浅灰**

#### 3.3 九宫格悬停

- 监听 `map.on('mousemove', handler)`
- handler 节流到 ≥ 80ms 一次（不要每次 mousemove 都触发后端调用）
- 调 `GET /api/map/ninegrid?lng=&lat=&role=` 拿 9 格数据
- 用 `L.featureGroup` 渲染：中心格 + 8 外围
- 鼠标离开 map 区域 → 清空九宫格图层
- **企业端不启用九宫格**

#### 3.4 矩形框选

- 用 leaflet-draw 提供 `L.Control.Draw`，仅启用 rectangle 模式
- 框选完成后：
  - 解构 bbox = `[ne, sw]` → `min_lng,min_lat,max_lng,max_lat`
  - 调 `GET /api/map/query?bbox=...&role=...`
  - 把返回的 `geojson` 渲染为高亮图层
  - 把统计信息（grid_count / total_area / land_types）填入对话面板顶部信息条
  - 自动切换到对话 tab，提示用户"已选择 XX 网格，请输入需求或直接询问产业建议"

#### 3.5 对话面板

- 上方消息列表，下方输入框 + 发送按钮
- 用户敲回车或点发送 → 调 `POST /api/agent/chat`
- 请求体：
  ```javascript
  {
    message: input.value,
    role: state.role,
    bbox: state.currentBbox,  // 若用户框选过
    context: state.chatHistory.slice(-10)  // 最近 10 条
  }
  ```
- 接到 AgentReply 后：
  - 在消息列表追加结构化展示：
    - 摘要 summary
    - 推荐 items 列表（rank/industry/score/reason）
    - 政策引用 policy_citations（折叠）
    - 风险 risks（红色提示）
  - 如果 `candidate_grids` 非空，调 `highlightCandidates(grid_ids)` 在地图上高亮

#### 3.6 企业列表

- 启动时调 `GET /api/enterprise/list` 加载全部
- 上方搜索框，输入触发 `loadEnterprises(search)`
- 每条企业带 checkbox（多选）
- 显示：`name` / `industry` / `annual_revenue` / `priority_tags`
- 底部"匹配选中企业"按钮：
  - 调 `POST /api/enterprise/match` `{enterprise_ids, role: 'government'}`
  - 接到 list[EnterpriseMatchResult] → 在对话面板渲染结果 + 地图高亮所有 candidate grids
  - 企业端隐藏此按钮（按钮显示但置灰，提示"仅政府端可用"）

#### 3.7 自进化展示

- Tab 切换到"自进化" → 调 `GET /api/evomap/status`
- 渲染：
  - 文案："本次评估已学习 N 次历史决策经验"
  - 进度条 "Agent 当前对桐庐县产业偏好的理解程度：XX%"
  - 文案 "已遗传/共享的评估方法论：X 条"
  - 文案 "已为集体智能贡献 Y 条经验"
  - **能力雷达图**（v1.0 必做）：
    - Chart.js radar，5 个维度：产业匹配 / 政策理解 / 空间分析 / 风险识别 / 企业匹配
    - 暗色主题，发光描边
    - 每 60 秒刷新一次（在 tab 激活时启动定时器，离开 tab 时停止）

#### 3.8 角色切换

- 顶栏两个按钮切换 `state.role`
- 切换时：
  - 重新 `loadEvolutionStats()`
  - 重新 `loadEnterprises()`
  - 清空当前 candidate 高亮
  - 政府端：九宫格悬停启用
  - 企业端：九宫格悬停禁用、单格点选禁用、匹配按钮置灰
  - 顶栏显示当前角色提示

#### 3.9 健康检查徽章

- 启动后立即调一次 `GET /health`
- 之后每 30 秒轮询一次
- 顶栏徽章三态：
  - `●  在线`（绿色）：HTTP 200 且 db=true
  - `●  EvoMap 离线`（黄色）：HTTP 200 但 evomap_online=false
  - `●  服务异常`（红色）：HTTP 非 200 或请求失败

---

### 任务 4：后端补充 `/api/config` 端点

**职责**：前端启动时拿到天地图 key 等公开配置。

**操作**：在 `src/main.py` 或新建 `src/api/config_routes.py` 中添加：

```python
from fastapi import APIRouter
from src import config

router = APIRouter(prefix="/api", tags=["config"])

@router.get("/config")
def get_public_config():
    """返回前端启动需要的公开配置（天地图 key、桐庐 bbox 等）"""
    return {
        "tianditu_key": config.TIANDITU_API_KEY or "",
        "tonglu_bbox": list(config.TONGLU_BBOX),
        "map_zoom_min": config.MAP_ZOOM_MIN,
        "map_zoom_max": config.MAP_ZOOM_MAX,
        "default_zoom": 11,
        "default_center": [29.795, 119.685],
    }
```

- **注意**：天地图 key 暴露给浏览器是必然的（前端调用的就是浏览器端 key），但 `DEEPSEEK_API_KEY` 绝不能暴露
- 挂载到 `main.py` 的 router 列表中
- 前端通过 `fetch('/api/config').then(r => r.json())` 拿到后注入到 `TIANDITU_KEY` 全局变量

---

### 任务 5：占位精简渔网 `static/grid_light.geojson`

**职责**：渔网真实数据未到位前的占位文件。

**操作**：创建一个**最小空 GeoJSON**：

```json
{
  "type": "FeatureCollection",
  "name": "grid_light_placeholder",
  "features": []
}
```

放在 `static/grid_light.geojson`。前端能正常加载，识别为空集合后走"渔网未就绪"降级路径，不报错。

---

## 关键约束（不可违反）

1. **Python 环境**：`D:\TOOLS\MiniConda\envs\agent_gpu_py311\python.exe`（仅用于启动 uvicorn 联调）
2. **前端纯 vanilla JS**，无 npm / webpack / TypeScript
3. **CDN 引入第三方库**，禁止任何打包工具
4. **不要硬编码 API key 到前端代码**——天地图 key 通过 `/api/config` 注入
5. **不要修改后端业务逻辑**，仅允许新增 `/api/config` 端点
6. **渔网空数据降级**：精简 GeoJSON 不存在或为空时，前端不能崩溃
7. **企业端 P3 简化策略**：列表/对话 tab 启用，匹配按钮置灰，suggest API 接入点保留，不做完整 UI

---

## 输出要求

- **交付物**：
  - `static/index.html`
  - `static/app.css`
  - `static/app.js`
  - `static/grid_light.geojson`（空集合占位）
  - `src/api/config_routes.py`（新增）
  - 修改 `src/main.py` 挂载 config_routes

- **质量底线**：
  - `python -m uvicorn src.main:app` 启动后，浏览器访问 `http://127.0.0.1:8000/static/index.html` 能完整加载
  - 浏览器 console 无报错（warn 可接受，特别是渔网未就绪的 warn）
  - 顶栏健康徽章显示状态
  - 地图能加载天地图卫星图（前提：`.env` 已配 TIANDITU_API_KEY）
  - 地图能被框选（即使没有渔网数据，也能调 API 拿到空结果不崩）
  - 对话框能发送消息并收到 LLM 响应（前提：`.env` 已配 DEEPSEEK_API_KEY）
  - 企业列表显示 12 家 seed 企业
  - 自进化 tab 显示文案 + 雷达图（基线 30 分）
  - 角色切换功能正常
  - 全文 grep `sk-ce4` / `48ad1b76` 无命中

---

## 汇报要求

完成后将汇报写入：`D:\Projects\Urban_Industry_Assistant\outputs\handoffs\05_report_impl_batchE.md`

汇报必须包含：
1. 5 份交付物完整路径与行数（HTML / CSS / JS / 占位 / config_routes）
2. 浏览器端自检结果（地图加载、对话、企业列表、雷达图、角色切换）
3. **渔网未就绪降级验证**：模拟空 GeoJSON 时前端的实际行为
4. **天地图 key 注入路径**：前端从 `/api/config` 拿到 key 的过程
5. 关键交互的实测体验（九宫格悬停延迟、框选响应、对话回执时间）
6. 风险或遗漏

汇报写完后，告知主人"批次 E 已完成，前端可以打开浏览器实测"。
