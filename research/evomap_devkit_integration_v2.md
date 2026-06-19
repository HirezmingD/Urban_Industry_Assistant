# EvoMap 开发者套件集成研究报告（修订版）

> **日期**：2026-06-19  
> **指令**：02_instruction_research_evomap_devkit_v2  
> **修订原因**：evomap_developer 源码到位后发现全新 OAuth2 接入模式

---

## 1. 接入方案选型（A2A vs OAuth2 开发者平台）

### 1.1 两个方案的关系

**结论：不是替代关系，而是两条独立的接入路径，服务不同场景。** 

| 维度 | A2A 协议 | OAuth2 开发者平台 |
|:---|:---|:---|
| **定位** | Agent 注册为 EvoMap 网络的**平等节点**，发布自己的进化产物 | 第三方应用**代表用户**读取 EvoMap 价值网络，或发布 recipe |
| **身份** | Agent 自身（`node_id`） | 人类用户（通过 OAuth2 委托） |
| **数据流** | 发布 Gene/Capsule → EvoMap 网络 | 检索已有 recipe/gene → 增强自身应用 |
| **目标用户** | 想要"输出进化能力"的 AI Agent | 想要"消费集体智能"的应用开发者 |
| **典型场景** | Agent 自我进化、贡献经验到公共池 | 提示词增强器、用 EvoMap 登录、调用价值网络的 AI agent |
| **API 前缀** | `/a2a/` | `/developer/oauth/` |
| **认证** | `node_secret` (Bearer) | OAuth2 `access_token` (Bearer) |
| **端点签名** | GEP-A2A envelope（`protocol/message_type/sender_id`） | 标准 REST（无 envelope） |

证据来源：
- A2A 协议：「你的 Agent 注册为一个节点，发布经过验证的解决方案（叫 Capsule）」— `03-for-ai-agents.md`
- OAuth2 平台：「这里是**在它之上构建应用的开发者主页**：读取 gene 与 recipe、代表用户创建并发布 recipe」— `README.zh-CN.md`
- HACKATHON.md 项目点子第一项：「**提示词增强器** — 用户说需求 → 检索可复用的 recipe/gene → 拼进增强后的 prompt」— 这正是我们的 use case

### 1.2 A2A 协议是否已过时？

**A2A 协议并未过时，但 Urban_Industry_Assistant 的路演场景更适合 OAuth2 平台。**

HACKATHON.md 推荐 OAuth2 平台用于黑客松的原因是：

> 「提示词增强器」— 用户说需求 → 检索可复用的 recipe/gene → 拼进增强后的 prompt

这与我们"评估前从 EvoMap 检索经验 → 注入 LLM prompt → 输出更精准建议"的模式完全吻合。

A2A 协议的合适场景是：当我们的 Agent 经过大量评估积累了已验证的评估方法论后，作为"贡献者"发布 Gene/Capsule 到 EvoMap 网络。但路演 Demo 中，我们更多是"消费者"——从集体智能中检索经验来增强评估质量。

### 1.3 三个 scope 能否覆盖需求？

**完全覆盖路演 Demo 的检索需求。**

| Scope | 功能 | 我们的使用 | 是否必需 |
|:---|:---|:---|:---:|
| `recipe:read` | 读 recipe — 列表/搜索/详情 | 全文搜 recipe（`?q=user_message`）获取可复用工作流 | ✅ |
| `gene:read` | 读 gene — 列表/搜索/详情 | 补充通用能力（热门 gene，无文本搜，按 type 排行） | ✅ |
| `reuse:query` | 查复用/关联图谱 | 深入了解 recipe 的关联资产，可暂不启用 | ⚠️ 可选 |

这三个 scope 全部**自助通过，无需审核**（`README.zh-CN.md` Scopes 表格：`gene:read`、`recipe:read`、`reuse:query` 均为"自助"）。

### 1.4 是否需要申请开发者资格发布 recipe？

- **发布 recipe** 需要 `recipe:publish` scope，需要[在门户申请](https://evomap.ai/dev/portal)开发者资格
- **创建草稿** 仅需 `recipe:write` scope，自助通过
- **测试模式**下，即使 `recipe:publish` 也**自助可用**（test mode 整个流程零真实副作用）

因此：**路演 Demo 阶段使用 test mode app，`recipe:publish` 无需申请。赛后如需发布到真实价值池再申请 live 资格。**

### 1.5 最终选型结论

```
┌─────────────────────────────────────────────────────────────┐
│                    最终选型结论                              │
│                                                             │
│  主方案：OAuth2 开发者平台（提示词增强器模式）                │
│  ─────────────────────────────────────────                  │
│  · 评估前：调用 /developer/oauth/recipes?q= 检索集体经验    │
│  · 注入增强 prompt → LLM 产出更精准的产业评估               │
│  · 三步 scope 自助获取，test mode 零风险                    │
│                                                             │
│  保留方案：A2A 协议（贡献者模式）                            │
│  ─────────────────────────────────                          │
│  · 评估后：高质量的评估方法论发布为 Gene+Capsule             │
│  · 现有 evo_client.py 代码保留，作为贡献通道                │
│  · 路演中"已贡献 N 条经验"的叙事素材                        │
│                                                             │
│  分工原则：OAuth2 = 消费集体智能，A2A = 贡献自身经验          │
└─────────────────────────────────────────────────────────────┘
```

**两个方案分工明确**：
- **OAuth2（新增）**：`新文件 oauth_client.py`，评估前检索 → 注入 prompt → 增强评估质量
- **A2A（保留）**：`现有 evo_client.py`，评估后发布高质量 Capsule → 贡献回网络

---

## 2. 提示词增强器集成设计（eval_service.py 改造方案）

### 2.1 检索插入位置

**文件**：`D:\Projects\Urban_Industry_Assistant\src\services\eval_service.py`  
**函数**：`async def evaluate_grids()`  
**插入位置**：Step 4（构建 prompt）和 Step 5（LLM API 调用）之间

```
现有流程：
Step 1: grid_service.get_grid_stats(grid_ids)
Step 2: 推断主导产业类型
Step 3: 政策上下文（policy_service）
Step 4: 构建 prompt（system_prompt + user_prompt）  ← 在此之后
  ↓
  ★ 新增 Step 4.5：EvoMap 检索增强
  4.5.1: 调用 oauth_client.search_recipes(user_message)
  4.5.2: 调用 oauth_client.get_top_genes(limit=3)
  4.5.3: 将检索结果注入 user_prompt
  ★ 降级：EvoMap 不可用时跳过，不影响现有流程
  ↓
Step 5: LLM API 调用（现有不变）
Step 6: 解析结果（现有不变）
Step 7: 存储评估记录（现有不变）
```

### 2.2 检索策略

**策略 1（主要）：全文搜 recipe**

```python
# 在 eval_service.py 的 evaluate_grids() 函数内，# Step 4.5
# 调用位置：第 133 行（messages 构造完成后，httpx.AsyncClient 调用前）

# --- Step 4.5: EvoMap 检索增强（可降级）---
evo_context = ""
try:
    recipes = await oauth_client.search_recipes(user_message, limit=5)
    if recipes:
        recipe_lines = []
        for r in recipes[:5]:
            title = r.get("title", "")
            desc = (r.get("description") or "")[:150]
            recipe_lines.append(f"- 《{title}》：{desc}")
        evo_context = (
            "## 🌍 EvoMap 集体智能（优先参考，避免重造）\n"
            "以下是从 EvoMap 价值网络中检索到的已验证经验：\n"
            + "\n".join(recipe_lines)
            + "\n\n请基于以上经验，结合桐庐本地政策和数据，给出评估建议。\n"
        )
except Exception as e:
    logger.info("EvoMap recipe 检索不可用（降级）: %s", e)
    evo_context = ""

# --- Step 4.6（可选）：补充热门 gene ---
try:
    genes = await oauth_client.get_top_genes(limit=3)
    if genes:
        gene_lines = []
        for g in genes[:3]:
            name = g.get("name", g.get("title", ""))
            summary = (g.get("summary") or g.get("description") or "")[:120]
            gene_lines.append(f"- {name}：{summary}")
        evo_context += (
            "\n## 🧬 通用能力参考（网络里好用的方法论）\n"
            + "\n".join(gene_lines)
            + "\n"
        )
except Exception:
    pass  # gene 检索是可选的，失败静默
```

关键约束 — 检索原语对比（来自 HACKATHON.md）：

| 检索方式 | 端点 | 参数 | 说明 |
|:---|:---|:---|:---|
| recipe 全文搜 | `/developer/oauth/recipes?q=` | 自然语言查询 | 最适合提示词增强器，输入 `user_message` |
| gene 排行 | `/developer/oauth/genes?limit=` | 无 `q`，按 type 排行 feed | 通用能力补充，非文本搜索 |
| reuse 图谱 | `/developer/oauth/reuse?recipe_id=` | 需要已知 recipe_id | 深度探索时使用，非初始检索 |

### 2.3 检索结果注入格式

检索到的 recipe/gene 注入到 `messages` 的 User Message **尾部**（而非 System Prompt），理由：
- System Prompt 是角色定义，不随每次评估变化
- User Message 天然携带当次上下文
- 符合 HACKATHON.md 的 `enhancePrompt()` 格式

**注入后消息结构**：

```python
messages: list[dict[str, str]] = [
    {"role": "system", "content": system_prompt},
]
if context:
    messages.extend(context)
# user_prompt 末尾追加 evo_context
messages.append({
    "role": "user",
    "content": user_prompt + "\n\n" + evo_context if evo_context else user_prompt
})
```

**注入内容的格式**（紧接在 user_prompt 后）：

```
## 🌍 EvoMap 集体智能（优先参考，避免重造）
以下是从 EvoMap 价值网络中检索到的已验证经验：
- 《产业用地评估方法论》：基于多维栅格数据和政策匹配的产业化评估工作流
- 《县域产业规划指南》：县市级产业规划的完整参考流程
...

## 🧬 通用能力参考（网络里好用的方法论）
- 产业匹配：基于用地类型和产业政策的自动适配
...
```

### 2.4 降级策略

**设计原则：EvoMap 检索是增强，不是依赖。**

| 降级场景 | 处理方式 | 用户体验 |
|:---|:---|:---|
| OAuth token 未配置/过期 | 跳过检索，日志记录 | 评估正常进行（无增强） |
| EvoMap API 超时（>5s） | 跳过检索，日志 warning | 同上 |
| 返回空结果 | `evo_context = ""`，日志 info | 同上 |
| API 返回错误（4xx/5xx） | 跳过检索，日志 warning | 同上 |
| A2A 发布失败 | 跳过，写入失败记录 | 不影响评估 |

**关键代码段（在 eval_service.py 中）**：

```python
# oauth_client 可能为 None（未初始化），优雅处理
_oauth = oauth_client  # 模块级懒加载实例

if _oauth is None or not _oauth.access_token:
    evo_context = ""
else:
    try:
        # 设置较短超时（5s），避免拖慢评估主流程
        async with asyncio.timeout(5):
            recipes = await _oauth.search_recipes(user_message, limit=5)
            if recipes:
                evo_context = _build_evo_context(recipes)
    except (asyncio.TimeoutError, Exception):
        logger.info("EvoMap 检索超时或不可用，跳过增强")
        evo_context = ""
```

---

## 3. Python OAuth2 PKCE 实现方案

### 3.1 核心组件设计

基于 quickstart `index.js` 的 Node.js 实现（`D:\TOOLS\Evomap_wiki\evomap_developer\developers\examples\quickstart\index.js`），给出 Python 等价实现。

**新增文件：`src/services/oauth_client.py`**

```python
"""
EvoMap OAuth2 开发者平台客户端。

基于 OAuth2 + PKCE (S256) 协议，提供：
- 授权 URL 构造（/oauth/authorize）
- code → token 交换（/oauth/token）
- token 刷新
- recipe / gene / reuse 检索 API

所有网络异常均降级返回 None/[]，不抛异常。
"""

import asyncio
import base64
import hashlib
import logging
import os
import secrets
from typing import Any

import httpx

from src.config import EVOMAP_HUB_URL

logger = logging.getLogger(__name__)

# ============================================================
# PKCE 工具函数
# ============================================================

def _base64url(data: bytes) -> str:
    """Base64url 编码（无 padding）。"""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def generate_pkce_pair() -> tuple[str, str]:
    """生成 PKCE code_verifier 和 code_challenge (S256)。

    Returns:
        (code_verifier, code_challenge)
    """
    verifier = _base64url(secrets.token_bytes(32))  # 32 bytes = 256 bits
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = _base64url(digest)
    return verifier, challenge


# ============================================================
# OAuth2 客户端
# ============================================================

class EvoMapOAuthClient:
    """EvoMap OAuth2 开发者平台客户端。

    设计为启动时一次性授权（适合路演 Demo），
    access_token 存储在内存中，支持自动刷新。
    """

    def __init__(self) -> None:
        self.client_id: str = os.getenv("EVOMAP_OAUTH_CLIENT_ID", "")
        self.client_secret: str = os.getenv("EVOMAP_OAUTH_CLIENT_SECRET", "")
        self.base_url: str = EVOMAP_HUB_URL.rstrip("/")
        self.redirect_uri: str = os.getenv(
            "EVOMAP_OAUTH_REDIRECT_URI",
            "http://localhost:8000/api/evomap/callback"
        )
        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self._code_verifier: str | None = None
        self._state: str | None = None
        self._is_test_mode: bool = self.client_id.startswith("evm_client_test_")

    # ---------- Step 1: 授权 URL ----------

    def build_authorize_url(self, scopes: str = "recipe:read gene:read reuse:query") -> str:
        """构造授权 URL（PKCE S256 流）。

        Args:
            scopes: 空格分隔的 scope 列表。

        Returns:
            str: 完整的 authorize URL。
        """
        verifier, challenge = generate_pkce_pair()
        state = secrets.token_hex(16)

        # 存储 verifier 和 state 用于 callback 校验
        self._code_verifier = verifier
        self._state = state

        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": scopes,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.base_url}/oauth/authorize?{query}"

    # ---------- Step 2: code → token ----------

    async def exchange_code(self, code: str, state: str) -> dict[str, Any]:
        """用 authorization code 交换 access token。

        Args:
            code: 授权回调返回的 code。
            state: 回调 state（用于防 CSRF）。

        Returns:
            dict: token 响应（含 access_token / refresh_token / expires_in）。
        """
        # CSRF 校验
        if state != self._state:
            raise ValueError("OAuth state mismatch — CSRF detected")

        if not self._code_verifier:
            raise ValueError("code_verifier not found — 请先调用 build_authorize_url()")

        body = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "code_verifier": self._code_verifier,
        }
        if self.client_secret:
            body["client_secret"] = self.client_secret

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{self.base_url}/oauth/token",
                    data=body,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.warning("EvoMap token exchange 失败: %s", e)
            raise

        self.access_token = data.get("access_token")
        self.refresh_token = data.get("refresh_token")
        logger.info("EvoMap OAuth: token 获取成功, test_mode=%s", self._is_test_mode)
        return data

    # ---------- Step 3: Token 刷新 ----------

    async def refresh_access_token(self) -> bool:
        """使用 refresh_token 刷新 access token。

        Returns:
            bool: 是否刷新成功。
        """
        if not self.refresh_token:
            return False

        body = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
        }
        if self.client_secret:
            body["client_secret"] = self.client_secret

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{self.base_url}/oauth/token",
                    data=body,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.warning("EvoMap token 刷新失败: %s", e)
            return False

        self.access_token = data.get("access_token")
        self.refresh_token = data.get("refresh_token", self.refresh_token)
        logger.info("EvoMap OAuth: token 刷新成功")
        return True

    # ---------- API 调用 ----------

    @property
    def is_available(self) -> bool:
        """是否可调用 API。"""
        return bool(self.access_token)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"}

    async def search_recipes(self, query: str, limit: int = 5) -> list[dict]:
        """全文搜 recipe（提示词增强模式核心 API）。

        Args:
            query: 自然语言查询（例如 user_message）。
            limit: 返回数量上限。

        Returns:
            list[dict]: recipe 列表，每条含 title/description 等。
        """
        if not self.access_token:
            return []
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    f"{self.base_url}/developer/oauth/recipes",
                    params={"q": query, "limit": limit},
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("recipes", [])
        except Exception as e:
            logger.warning("EvoMap recipe search 失败: %s", e)
            return []

    async def get_top_genes(self, limit: int = 3) -> list[dict]:
        """获取排行靠前的 gene（通用能力补充）。

        Args:
            limit: 返回数量。

        Returns:
            list[dict]: gene 列表。
        """
        if not self.access_token:
            return []
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    f"{self.base_url}/developer/oauth/genes",
                    params={"limit": limit},
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("genes", [])
        except Exception as e:
            logger.warning("EvoMap gene fetch 失败: %s", e)
            return []

    async def query_reuse(self, recipe_id: str) -> dict | None:
        """查询复用/关联图谱。

        Args:
            recipe_id: recipe 的 ID。

        Returns:
            dict | None: reuse 数据或 None。
        """
        if not self.access_token:
            return None
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    f"{self.base_url}/developer/oauth/reuse",
                    params={"recipe_id": recipe_id},
                    headers=self._headers(),
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.warning("EvoMap reuse query 失败: %s", e)
            return None


# ============================================================
# 模块级实例
# ============================================================

oauth_client = EvoMapOAuthClient()
"""全局 EvoMap OAuth 客户端实例。

注意事项：
- 启动时需完成一次性 OAuth 授权（手动操作一次浏览器授权）
- 否则 access_token 为空，所有 API 调用静默跳过
"""
```

### 3.2 授权路由

**新增路由**：`src/api/evo_routes.py` 追加（或新建 `src/api/oauth_routes.py`）

```python
# 追加到 evo_routes.py 或新文件 oauth_routes.py

@router.get("/evomap/authorize")
async def evomap_authorize():
    """获取 EvoMap OAuth 授权 URL，用户浏览器访问后完成授权。"""
    url = oauth_client.build_authorize_url()
    return {"authorize_url": url}

@router.get("/evomap/callback")
async def evomap_callback(code: str, state: str):
    """OAuth 回调：用 code 换 token。"""
    try:
        data = await oauth_client.exchange_code(code, state)
        return {
            "status": "authorized",
            "test_mode": oauth_client._is_test_mode,
            "scopes": data.get("scope", ""),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
```

### 3.3 Token 存储与刷新策略

| 场景 | 策略 | 理由 |
|:---|:---|:---|
| **路演 Demo** | 内存存储（`self.access_token`） | 一次性授权后会话内有效，重启后重新授权 |
| **Token 过期** | 每次 API 调用前检查，401 时尝试 refresh | quickstart 模式，避免刷太频繁 |
| **启动时** | 手动访问 `/api/evomap/authorize` 完成授权 | 比赛现场操作一次即可 |
| **生产环境** | 持久化 refresh_token，启动时尝试恢复 | 长期运行需要 |

**启动授权流程（路演用）**：

```
1. 启动服务器 → 访问 http://localhost:8000/api/evomap/authorize
2. 复制 authorize_url → 浏览器打开 → "Connect with EvoMap"
3. EvoMap 回跳到 http://localhost:8000/api/evomap/callback?code=...&state=...
4. 后端自动用 code 换 token → oauth_client.access_token 就位
5. 完成！后续评估自动检索 EvoMap
```

### 3.4 需要一个 `/api/evomap/auth` 路由吗？

**需要，但设计为"启动时一次性授权"而非"每次请求都授权"。**

理由：
- OAuth2 PKCE 涉及浏览器跳转，不是纯 API 调用
- 路演中只需要授权一次，token 在服务端内存中持续有效
- 只需两个端点：`/api/evomap/authorize`（获取授权 URL）和 `/api/evomap/callback`（处理回调）

---

## 4. 路演叙事设计（集体智能版自进化）

### 4.1 5 分钟路演时序

```
┌──────────────────────────────────────────────────────────────────┐
│              路演叙事：从"本地评估"到"集体智能增强"               │
└──────────────────────────────────────────────────────────────────┘

Step 0: 开场（30秒）
───────
"桐庐有 ~18.3 万块网格化的产业用地，每块地适合做什么产业？
三个 Agent 帮助我们回答这个问题。"

Step 1: 基线评估 — EvoMap 检索关闭（90秒）
───────
· 操作：在界面上关闭 EvoMap 检索开关（或首次评估时 oauth token 未就位）
· 政府端框选城东某区域（~20 个渔网单元）
· 提问："这块地适合发展什么产业？"
· Agent 返回：
  - 摘要：共 20 个渔网单元，45.8 亩
  - 评分：精密制造 7.5/10，数字经济 6.5/10
  - 依据：土地利用类型 + 产业政策知识库
· 旁白："这是 Agent 基于本地数据和政策的基线评估，它只看到了桐庐的数据。"

Step 2: 开启 EvoMap 检索 — 同一问题（120秒）
───────
· 操作：开启 EvoMap 检索（一键开关，其实是 oauth token 就位）
· 再次提问同一问题
· Agent 返回（底部标注"🌍 EvoMap 集体智能增强"）：
  - 摘要：共 20 个渔网单元，45.8 亩
  - 评分：精密制造 8.5/10，大健康 7.8/10 ← 变化！
  - 依据：土地利用 + 政策 + **"已检索到 N 条 EvoMap 社区验证经验"**
  - 新增推荐产业：智能装备 7.5/10（来自 EvoMap 同类案例）
· 旁白："开启 EvoMap 后，Agent 从全球价值网络中检索到了 5 条已验证的产业评估经验。
  它借鉴了其他城市产业用地的成功案例，评估更精准、推荐更全面。
  这就像 consulting 了几百位专家的意见，而不只是自己埋头苦算。"

Step 3: 自进化面板展示（90秒）
───────
· 切换到"自进化面板"
· 展示内容：
  ┌───────────────────────────────────┐
  │ 🌱 进化经验积累：已学习 12 次决策经验  │
  │ 📊 偏好理解度：78%                  │
  │ 🧬 遗传方法论：3 条（可展开查看）     │
  │ 📈 能力雷达图：五维能力变化           │
  │   · 产业匹配：65→85（+20）★         │
  │   · 政策理解：70→82（+12）           │
  │   · 空间分析：55→72（+17）           │
  │   · 风险识别：45→68（+23）★         │
  │   · 企业匹配：50→65（+15）           │
  │ 🎁 Capsule 贡献：已为集体智能贡献 3 条经验│
  └───────────────────────────────────┘
· 旁白："Agent 的'自进化'体现在三个层面：
  ① 本地学习 — 每次评估反馈让 Agent 更理解桐庐
  ② 网络学习 — EvoMap 检索让 Agent 获取全球经验
  ③ 贡献回馈 — Agent 的高质量评估发布回 EvoMap，帮助其他 Agent"

总结（30秒）
───────
"Urban_Industry_Assistant 让每一块地的决策都有数据支撑，
每一次评估都比上一次更聪明，
而且这个聪明会通过网络持续进化。"
```

### 4.2 叙事关键点

| 要素 | 旧叙事（A2A only） | 新叙事（OAuth2 + A2A） |
|:---|:---|:---|
| **核心概念** | 本地积累 → 发布 Capsule → 本地变聪明 | 搜索集体智能 → 检索他人经验 → **借助网络给出更优建议** |
| **用户感知** | "Agent 在自我学习" | "Agent 在调用全球专家的经验" |
| **Demo 亮点** | 自进化面板的数字在增长 | **同一问题两次评估的对比**（关闭 vs 开启 EvoMap） |
| **技术锚点** | A2A publish 成功 | OAuth2 recipe search 返回实际结果 |

---

## 5. Test Mode 使用建议

### 5.1 路演是否可用 Test Mode？

**强烈推荐。Test mode 是专门为 Demo/黑客松设计的。**

来自 HACKATHON.md：

> ✅ **建议勾「test mode」** — 拿到 `evm_client_test_…` 的 client id，整个流程（含发布）都在沙箱里跑，**不碰真实数据**

Test mode 的关键特性：

| 特性 | 说明 |
|:---|:---|
| **隔离** | 所有操作在独立沙箱中，不触碰线上目录/排名/配额/价值池 |
| **逼真响应** | 发布流程跑真实的校验 + 审核 gate，返回逼真结果 |
| **可读回** | Test publish 的结果可用 test token 读回（TTL ~24h） |
| **零成本** | 无积分消耗，无真实副作用 |
| **代码一致** | 切换到 live 模式只需换 `client_id`，代码完全不变 |
| **`livemode` 字段** | API 响应中 `livemode: false` 标识 test mode |

来源：`README.zh-CN.md`「测试模式」节 + OpenAPI `x-pricing` 节

### 5.2 是否需要准备 Live Mode 备选？

**建议准备但不依赖。** 策略：

| 方案 | 准备内容 | 何时使用 |
|:---|:---|:---|
| **Plan A（主）** | Test mode app (`evm_client_test_…`)，会前注册好并完成一次授权 | 路演全程 |
| **Plan B（备选）** | 降级：EvoMap 检索功能关闭，仅展示本地评估 | Test mode 不可用时 |
| **Plan C（备选）** | Live mode app (`evm_client_live_…`)，只读 scope | Live 可用但 test 不可用时 |

**Plan A 的准备工作清单**：

1. [ ] 赛前：在 [evomap.ai/dev/portal](https://evomap.ai/dev/portal) 注册 test mode app
   - 回调地址：`http://localhost:8000/api/evomap/callback`
   - scope：`recipe:read gene:read reuse:query`
   - 勾选 test mode
2. [ ] 将 `CLIENT_ID` / `CLIENT_SECRET` 写入 `.env`
3. [ ] 赛前启动服务器，访问 `/api/evomap/authorize` 完成一次授权
4. [ ] 用 `GET /developer/oauth/recipes?q=产业用地&limit=3` 验证 token 有效
5. [ ] 保持服务器运行，token 在内存中

### 5.3 Test Mode 下 Publish Recipe 的行为

> Test 发布会跑真实的校验 + 审核 gate 并返回逼真响应，但**绝不触碰**线上目录/排名/配额/价值池，只能用 test token 读回。

具体行为：
- ✅ 执行完整的校验和审核流程
- ✅ 返回逼真的成功/失败响应（含评分反馈）
- ❌ 不写入真实价值池、目录、排名
- ❌ 不触发真实 webhook
- ✅ Test 发布的 recipe 以 `recipe_test_…` 前缀标识
- ✅ 可通过 test token 读回，TTL ~24h
- ⚠️ `genes` 和 `reuse` 端点返回空

**对路演的影响**：Test mode 下只适合演示"检索"环节（Step 2），不适合演示"发布贡献"（Step 3 中的 Capsule 贡献展示需要 A2A 协议的 `publish` 来完成，而非 OAuth2 `recipe:publish`）。

---

## 6. 实施优先级清单

### P0 — 路演必须（赛前完成）

| # | 任务 | 说明 | 预估 |
|:--:|:---|:---|:--:|
| 1 | 注册 Test Mode App | 在 evomap.ai/dev/portal 注册，获取 client_id/secret | 5 min |
| 2 | 实现 `oauth_client.py` | 按第 3 节设计，实现 OAuth2 PKCE + API 调用 | 1 h |
| 3 | 改造 `eval_service.py` | 在 evaluate_grids() 中插入 Step 4.5 EvoMap 检索 | 30 min |
| 4 | 追加 OAuth 路由 | `/api/evomap/authorize` + `/api/evomap/callback` | 20 min |
| 5 | 前端 EvoMap 开关 | 对话面板添加"🌍 EvoMap 增强"开关按钮 | 15 min |
| 6 | 路演联调 | 关闭/开启 EvoMap 各做一次评估，对比结果 | 30 min |

**P0 总计：~2h 40min**

### P1 — 路演建议（赛前尽量完成）

| # | 任务 | 说明 | 预估 |
|:--:|:---|:---|:--:|
| 7 | 自进化面板 UI | 对比展示"无 EvoMap vs 有 EvoMap"的能力雷达图 | 1 h |
| 8 | A2A publish 触发 | 高质量评估（confidence > 0.8）自动发布 Gene+Capsule | 30 min |
| 9 | 降级逻辑完善 | 所有 EvoMap 调用异常 → 前端提示"经验检索暂时不可用" | 20 min |

### P2 — 赛后完善

| # | 任务 | 说明 | 预估 |
|:--:|:---|:---|:--:|
| 10 | Token 持久化 | 加密存储 refresh_token，重启后自动恢复 | 1 h |
| 11 | reuse 图谱深度集成 | 为推荐产业提供关联 recipe 的关联图谱 | 2 h |
| 12 | Live Mode 迁移 | 申请 `recipe:publish` 资格，切换到 live | 1 h |

### P3 — 生产环境

| # | 任务 | 说明 | 预估 |
|:--:|:---|:---|:--:|
| 13 | Webhook 接收 | 监听 recipe.published 事件，自动更新本地经验库 | 1 h |
| 14 | 多用户授权 | 支持不同用户各自的 OAuth 授权（非共享 token） | 2 h |

---

## 附录 A：关键差异速查

### A.1 A2A vs OAuth2 API 端点对比

| 目的 | A2A 端点 | OAuth2 端点 | 我们使用 |
|:---|:---|:---|:---|
| 注册/认证 | `POST /a2a/hello` → `node_secret` | OAuth2 PKCE → `access_token` | OAuth2 ✅ |
| 检索经验 | `POST /a2a/fetch` (按信号) | `GET /developer/oauth/recipes?q=` | OAuth2 ✅ |
| 发布成果 | `POST /a2a/publish` (Gene+Capsule) | `POST /developer/oauth/recipe[/publish]` | A2A ✅ (已有) |
| 心跳保活 | `POST /a2a/heartbeat` | 无（token 自动过期/刷新） | A2A ✅ (已有) |

### A.2 两条路径共存策略

```
                ┌──────────────────────┐
                │   eval_service.py    │
                │   evaluate_grids()   │
                └──────┬───────┬───────┘
                       │       │
         ┌─────────────┘       └─────────────┐
         ▼                                    ▼
  评估前：OAuth2 检索                  评估后：A2A 发布
  ┌───────────────────┐               ┌───────────────────┐
  │ oauth_client.py   │               │ evo_client.py     │
  │ (新增)             │               │ (保留，已有的)     │
  │                   │               │                   │
  │ search_recipes()  │               │ publish()          │
  │ get_top_genes()   │               │ hello / heartbeat  │
  │ query_reuse()     │               │ status()           │
  └───────┬───────────┘               └───────┬───────────┘
          │                                   │
          ▼                                   ▼
   EvoMap API:                        EvoMap API:
   /developer/oauth/*                 /a2a/*
   (OAuth2 bearer token)             (node_secret bearer)
```

---

## 附录 B：环境变量清单

```bash
# .env 新增的 EvoMap OAuth2 配置

# === OAuth2 开发者平台（新） ===
EVOMAP_OAUTH_CLIENT_ID=evm_client_test_xxxxxxxxxx
EVOMAP_OAUTH_CLIENT_SECRET=your_secret_here
EVOMAP_OAUTH_REDIRECT_URI=http://localhost:8000/api/evomap/callback

# === A2A 协议（保留，已有） ===
EVOMAP_NODE_ID=node_urban_industry_assistant
EVOMAP_NODE_SECRET=xxx
```

### 注册 App 后填入 `EVOMAP_OAUTH_CLIENT_ID`

- **Test mode** → `evm_client_test_…` 前缀
- **Live mode** → `evm_client_live_…` 前缀
- 代码中 `_is_test_mode` 自动根据前缀检测
