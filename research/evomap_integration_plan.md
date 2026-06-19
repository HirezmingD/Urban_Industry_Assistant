# EvoMap 最小可行接入方案

> **研究对象**：Urban_Industry_Assistant（县域产业用地智能评估 Agent）
> **场景**：48 小时黑客松 Demo（The Pearl · 自进化赛道）
> **编写日期**：2026-06-18
> **依据文档**：`03-for-ai-agents.md`、`05-a2a-protocol.md`、`35-evolver-configuration.md`、`开发流程_内部方案.md`

---

## 一、核心发现摘要

**⚠️ 关键结论：新注册节点头 2 天无法达到自动推广门槛，Demo 阶段应聚焦"注册+发布+前端展示"，PPT 中说明自进化机制即可。**

| 指标 | 自动推广最低要求 | 新节点实际情况 | 能否满足 |
|------|:-------------:|:----------:|:------:|
| GDI 评分（保守下界） | >= 25 | 0（首次发布） | ❌ |
| GDI 内在质量分 | >= 0.4 | 取决于 Capsule 质量 | ⚠️ 可构造 |
| confidence | >= 0.5 | 取决于 self-report | ✅ 可自评 |
| 来源节点声誉 | >= 30 | 0（新节点） | ❌ 硬伤 |
| 验证共识 | 未过半失败 | 无验证者 | ✅ 无人反对 |

**致命瓶颈**：来源节点声誉要求 >= 30，但新注册节点初始声誉为 0。即使 GDI 和 confidence 达标，在两天内也不可能积累到 30 分声誉。这意味着"自动推广"在 Demo 阶段不可行。

---

## 二、注册节点（POST /a2a/hello）

### 最小参数

```json
{
  "protocol": "gep-a2a",
  "protocol_version": "1.0.0",
  "message_type": "hello",
  "message_id": "msg_{timestamp}_{random_hex}",
  "sender_id": "node_urban_industry_assistant",
  "timestamp": "2026-06-19T04:00:00.000Z",
  "payload": {
    "capabilities": {
      "land_evaluation": "县域产业用地智能评估",
      "gis_analysis": "多源用地数据 + 卫星图叠加分析",
      "industry_matching": "产业适配度评分与推荐"
    },
    "model": "deepseek-v4-pro",
    "gene_count": 0,
    "capsule_count": 0,
    "env_fingerprint": {
      "node_version": "v24.14.1",
      "platform": "win32",
      "arch": "x64"
    },
    "identity_doc": "Urban_Industry_Assistant 是一个面向县域政府的产业用地智能评估 Agent，基于开放下载的城市存量数据、既有数据、历史积累数据，融合多维栅格数据和十五五产业政策知识库，为地块提供产业适配评分与发展建议。",
    "constitution": "1. 评估结论必须基于数据，不可凭空推测。\n2. 产业发展建议必须对标当地政策规划。\n3. 风险提示优先于乐观推荐。"
  }
}
```

### 返回关键字段

| 字段 | 说明 | Demo 阶段用途 |
|------|------|-------------|
| `status: "acknowledged"` | 注册成功 | ✅ 前端展示"已注册" |
| `your_node_id` | 节点 ID | ✅ 存入配置，后续 API 调用 |
| `node_secret` | 64 位 hex 密钥 | ⚠️ 存入环境变量，**不要**写入 git |
| `claim_code` + `claim_url` | 认领链接 | ⚠️ Demo 中展示但不要求评委操作 |
| `credit_balance: 100` | 启动积分 100 | ✅ 前端展示积分余额 |
| `survival_status: "alive"` | 节点存活 | ✅ 前端展示 |
| `starter_gene_pack` | 先验基因包 | ⚠️ 可展示，但 Demo 不做 fetch |
| `recommended_tasks` | 匹配的悬赏任务 | ℹ️ 可忽略 |
| `network_manifest` | 网络信息 | ℹ️ 可忽略 |

### 注册执行计划

- **负责人**：和洲（见开发流程 0.7）
- **时机**：19 号中午环境就绪后立即注册
- **存储**：`node_id` + `node_secret` 存入服务器 `.env`，不提交 git

---

## 三、心跳保活（POST /a2a/heartbeat）

### 核心参数

| 项目 | 值 |
|------|-----|
| 推荐频率 | 每 5 分钟（`heartbeat_interval_ms: 300000`） |
| 超时阈值 | 15 分钟无心跳 → 标记离线 |
| 鉴权方式 | `Authorization: Bearer <node_secret>` |
| Payload | `{ "node_id": "node_xxx" }` |

### Demo 阶段建议

- **必须实现**：心跳保活（让节点在 EvoMap 上显示 `alive` 状态）
- **实现方式**：FastAPI 后台定时任务（`asyncio.create_task`），每 5 分钟发送一次
- **前端展示**：状态面板实时显示"在线"状态和最近心跳时间

---

## 四、发布 Capsule（POST /a2a/publish）

### Gene + Capsule 捆绑包最小结构

Gene 和 Capsule **必须**作为捆绑包一起发布（`payload.assets` 数组）。单独发送会被拒绝。

#### Gene（策略基因）最小结构

```json
{
  "type": "Gene",
  "schema_version": "1.5.0",
  "category": "innovate",
  "signals_match": [
    "land-use-evaluation",
    "industry-suitability",
    "county-planning"
  ],
  "summary": "多维度产业用地适配评估方法：综合用地性质、面积、交通可达性、环境约束和产业政策偏好，通过加权评分模型输出地块的产业适配度排名",
  "model_name": "deepseek-v4-pro",
  "domain": "data_analysis",
  "asset_id": "sha256:<gene_hex>"
}
```

**`asset_id` 计算规则**：对 asset 对象排除 `asset_id` 字段、按 key 排序后的 canonical JSON 做 SHA-256。

#### Capsule（验证结果）最小结构

```json
{
  "type": "Capsule",
  "schema_version": "1.5.0",
  "trigger": [
    "land-use-evaluation",
    "industry-suitability"
  ],
  "gene": "sha256:<gene_hex>",
  "summary": "对桐庐县城东30亩工业用地的评估：推荐精密制造（评分8.2）、大健康（评分7.5）、快递物流装备（评分6.8），风险点-周边交通配套待完善",
  "confidence": 0.85,
  "blast_radius": {
    "files": 3,
    "lines": 150
  },
  "outcome": {
    "status": "success",
    "score": 0.85
  },
  "env_fingerprint": {
    "platform": "win32",
    "arch": "x64"
  },
  "success_streak": 1,
  "model_name": "deepseek-v4-pro",
  "domain": "data_analysis",
  "asset_id": "sha256:<capsule_hex>"
}
```

### 捆绑包发布请求

```json
{
  "protocol": "gep-a2a",
  "protocol_version": "1.0.0",
  "message_type": "publish",
  "message_id": "msg_{timestamp}_{hex}",
  "sender_id": "node_urban_industry_assistant",
  "timestamp": "2026-06-20T08:00:00.000Z",
  "payload": {
    "assets": [geneObject, capsuleObject]
  }
}
```

HTTP 请求头：`Authorization: Bearer <node_secret>`

### 发布门槛与 Demo 对策

| 条件 | 最低要求 | Demo 实际 | 对策 |
|------|:------:|:------:|------|
| GDI 评分 | >= 25 | 未知 | ✅ self-report confidence 0.8+ 可提高 GDI 内在分 |
| GDI 内在质量分 | >= 0.4 | 取决于内容 | ✅ 构造高质量 Gene + Capsule，内容详实 |
| confidence | >= 0.5 | 自评 | ✅ 自评 >= 0.8 没问题 |
| 来源节点声誉 | >= 30 | **0** | ❌ **硬伤，两天内不可能达到** |
| 验证共识 | 未过半失败 | 无验证者 | ✅ 无人反对即通过 |

**对策方案**：
1. **能做多少**：注册节点 + 心跳保活 + 构造并发送 publish 请求（资产会进入 `candidate` 状态）
2. **不能做什么**：自动推广到 `promoted`（需要声誉 >= 30，新节点不可能）
3. **PPT 怎么说**：展示 publish 请求已发送、资产在 EvoMap 上可见（candidate 状态），说明正式运营后声誉积累即可自动推广

---

## 五、两天内的最小可行接入步骤

### 必须跑通的（3 步）

| 步骤 | 操作 | 预计耗时 | 依赖 |
|:--:|------|:------:|------|
| 1 | **注册节点** — POST /a2a/hello，获取 node_id + node_secret | 10 min | 服务器网络通 |
| 2 | **心跳保活** — 后台每 5 分钟发 /a2a/heartbeat | 20 min（写代码） | 步骤 1 完成 |
| 3 | **构造并发布 1 个 Gene+Capsule** — 把一次评估结果打包发布到 EvoMap | 1h | 有至少一次完整评估 |

### PPT 里讲就行的（3 步）

| 步骤 | 操作 | 为什么不做 |
|:--:|------|------|
| 4 | **自进化闭环** — memory/recall → 优化评估 → 重新发布 | 需要多轮积累，时间不够 |
| 5 | **Capability Chain** — 多个 Capsule 串联 | 需要多次发布，且 asset 需先 promoted |
| 6 | **验证者/任务** — 认领悬赏任务 | 偏离 Demo 核心价值 |

### 自进化演示剧本（备选录屏）

如果实时调不通 EvoMap API，用录屏替代：

```
第一轮：评估城东30亩 → 推荐"轻工业" → 用户反馈"服装业饱和"
第二轮：memory/recall 调取上次反馈 → 跳过服装 → 推荐"精密制造"
第三轮：切换到"企业B" → 继承基因 → 直接排除饱和产业
```

---

## 六、EvoMap 集成的技术实现要点

### 在 FastAPI 中的代码骨架

```python
# config.py
EVOMAP_HUB = "https://evomap.ai"
NODE_ID = os.getenv("EVOMAP_NODE_ID")
NODE_SECRET = os.getenv("EVOMAP_NODE_SECRET")

# evomap_client.py
import httpx
import asyncio
import hashlib
import json
import time

class EvomapClient:
    def __init__(self):
        self.node_id = NODE_ID
        self.secret = NODE_SECRET
        self.base_url = f"{EVOMAP_HUB}/a2a"
    
    def _headers(self):
        return {"Authorization": f"Bearer {self.secret}", "Content-Type": "application/json"}
    
    async def heartbeat(self):
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{self.base_url}/heartbeat", 
                json={"node_id": self.node_id}, headers=self._headers())
        return r.json()
    
    async def start_heartbeat_loop(self, interval=300):
        """每 5 分钟心跳"""
        while True:
            try:
                resp = await self.heartbeat()
                print(f"[EvoMap] heartbeat: {resp.get('status')}")
            except Exception as e:
                print(f"[EvoMap] heartbeat fail: {e}")
            await asyncio.sleep(interval)
    
    @staticmethod
    def compute_asset_id(asset):
        """计算 SHA-256 asset_id"""
        clean = {k: v for k, v in asset.items() if k != "asset_id"}
        sorted_str = json.dumps(clean, sort_keys=True, ensure_ascii=False)
        return "sha256:" + hashlib.sha256(sorted_str.encode()).hexdigest()
    
    async def publish(self, gene: dict, capsule: dict):
        gene["asset_id"] = self.compute_asset_id(gene)
        capsule["gene"] = gene["asset_id"]
        capsule["asset_id"] = self.compute_asset_id(capsule)
        
        envelope = {
            "protocol": "gep-a2a",
            "protocol_version": "1.0.0",
            "message_type": "publish",
            "message_id": f"msg_{int(time.time()*1000)}_{os.urandom(4).hex()}",
            "sender_id": self.node_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "payload": {"assets": [gene, capsule]}
        }
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{self.base_url}/publish", 
                json=envelope, headers=self._headers())
        return r.json()
```

### 风险提示

| 风险 | 概率 | 预案 |
|------|:--:|------|
| EvoMap Hub 不通/限速 | 中 | 前端做假数据展示，嘴上讲架构，不现场调 API（开发流程已列入预案） |
| node_secret 泄露到 git | 中 | `.env` 不入库，`.gitignore` 检查 |
| publish 返回 `content_safety_flag` | 低 | 检查 Gene summary 中无敏感词 |
| publish 返回 `duplicate_content_structure` | 低 | 确保每次发布内容有实质差异 |

---

## 七、结论与建议

1. **注册+心跳+发布这三步必须跑通**，这是 EvoMap 集成的"最小闭环"
2. **不要追求自动推广**（`promoted` 状态），新节点声誉瓶颈无法突破
3. **发布 1-2 个候选资产即可**，证明 Agent 能输出 Gene+Capsule 就足够
4. **前端状态面板**展示节点状态、心跳时间、已发布 Capsule 列表、积分余额，让评委"看到"自进化
5. **备选录屏**覆盖 EvoMap API 不通的场景

> **一句话**：能做到"注册上线、心跳保活、发布候选资产"，剩下的在 PPT 和录屏里讲自进化故事。

---

*信息缺口：EvoMap 是否允许未认领节点在 candidate 状态展示资产 ID 和详情页，需实测确认。如不展示，则需要认领节点（人类用户访问 claim_url 绑定）。*
