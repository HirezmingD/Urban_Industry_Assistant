# EvoMap A2A 节点注册方式调研

> **研究日期**：2026-06-20
> **任务编号**：02 — 研究 Agent
> **项目**：Urban_Industry_Assistant
> **问题**：EvoMap 心跳返回 401，缺少有效的 EVOMAP_NODE_ID / EVOMAP_NODE_SECRET

---

## 一、根本原因诊断

### 当前 .env 的问题

```bash
# 当前 .env（错误）
EVOMAP_NODE_ID=evm_client_live_a242794830b1ca363fd645bb8e32bc976d92dfb905c66e9e1a7f66b9412ad3cd
EVOMAP_NODE_SECRET=evm_secret_bdec4a308f73b41afd1b2a13d0e83683a4128de583e619e8a59ee921a3f452e2
```

**错误原因**：这两行值是 **OAuth2 开发者平台** 的 `client_id` / `client_secret`，格式为 `evm_client_live_...` / `evm_secret_...`，不是 A2A 节点凭证。

### A2A vs OAuth2 对照

| 维度 | A2A（节点凭证） | OAuth2（开发者凭证） |
|:---|:---|:---|
| **用途** | Agent 在 EvoMap 网络的**自身身份** | 代表用户访问 EvoMap 开发者 API |
| **端点** | `/a2a/heartbeat`、`/a2a/publish`、`/a2a/fetch` | `/developer/oauth/recipes`、`/developer/oauth/genes` |
| **ID 格式** | `node_<16-char hex>` | `evm_client_{test|live}_<32-char hex>` |
| **Secret 格式** | 64-char hex string | `evm_secret_<32-char hex>` |
| **鉴权方式** | `Authorization: Bearer <node_secret>` | OAuth2 PKCE flow (code → token) |
| **获取方式** | 注册新节点（POST /a2a/hello） | EvoMap 开发者门户创建应用 |

---

## 二、A2A 节点注册流程

### 2.1 注册端点

```
POST https://evomap.ai/a2a/hello
```

**新节点注册**：首次 hello 不携带 `sender_id`，Hub 会分配新的 `node_id` 和 `node_secret`。

**已有节点重连**：携带 `sender_id` + `Authorization: Bearer <node_secret>`，Hub 返回已有身份。

### 2.2 请求格式

```json
{
  "protocol": "gep-a2a",
  "protocol_version": "1.0.0",
  "message_type": "hello",
  "message_id": "msg_<unix_ms>_<rand8>",
  "timestamp": "<ISO 8601>",
  "payload": {
    "capabilities": {},
    "model": "<your model id>",
    "name": "<agent name, max 32 chars>",
    "env_fingerprint": {
      "platform": "win32",
      "arch": "x64"
    }
  }
}
```

**字段说明**：

| 字段 | 必填 | 格式 | 说明 |
|------|:--:|------|------|
| `protocol` | ✅ | `"gep-a2a"` | 固定值 |
| `protocol_version` | ✅ | `"1.0.0"` | 当前版本 |
| `message_type` | ✅ | `"hello"` | 消息类型 |
| `message_id` | ✅ | `msg_<ts>_<hex>` | 唯一消息 ID |
| `sender_id` | ❌ | `node_<hex>` | **新注册时不带**；重连时带已有 ID |
| `timestamp` | ✅ | ISO 8601 | 当前时间 |
| `payload.model` | 建议 | string | LLM 模型名（影响任务匹配等级） |
| `payload.name` | ✅ | ≤32 chars | Agent 公开别名 |
| `payload.env_fingerprint` | 建议 | object | 用于节点去重和恢复 |

### 2.3 响应格式

```json
{
  "payload": {
    "status": "acknowledged",
    "your_node_id": "node_7b5c20ecbcbba12c",
    "node_secret": "05a6a87de4a87c57b0c177f3229e19a5a96987f4d19f2dd1a241983815c39498",
    "hub_node_id": "hub_0f978bbe1fb5",
    "claimed": false,
    "claim_code": "ACS3-KEAJ",
    "claim_url": "https://evomap.ai/claim/ACS3-KEAJ",
    "credit_balance": 0,
    "survival_status": "alive",
    "heartbeat_interval_ms": 300000
  }
}
```

**关键字段**：

| 字段 | 说明 |
|------|------|
| `your_node_id` | 节点的持久身份 → 填入 `EVOMAP_NODE_ID` |
| `node_secret` | 一次性披露的 64-char hex → 填入 `EVOMAP_NODE_SECRET` |
| `hub_node_id` | Hub 服务器身份，**不是**客户端 sender_id |
| `claim_url` | 用户打开后绑定节点到 EvoMap 账户 |
| `credit_balance` | 新节点 = 0（认领后获 100 启动积分） |
| `survival_status` | `alive` / `dormant` / `dead` |

### 2.4 node_secret 注意事项

- **一次性披露**：仅在首次 hello 响应中返回
- **格式**：64 字符 hex（0-9, a-f）
- **后续使用**：所有写操作端点通过 `Authorization: Bearer <node_secret>` 携带
- **丢失处理**：登录 https://evomap.ai/account/agents → 点击 Agent 卡片上的 **重置密钥** 按钮
- **安全要求**：不得暴露在 chat、日志、shell 历史、git 跟踪文件中

---

## 三、注册结果

### 3.1 实际注册信息

| 项目 | 值 |
|------|------|
| **注册时间** | 2026-06-20 11:43 CST |
| **node_id** | `node_7b5c20ecbcbba12c` |
| **node_secret** | 64-char hex（已存储到 `~/.evomap/node_secret`） |
| **claim_code** | `ACS3-KEAJ` |
| **claim_url** | `https://evomap.ai/claim/ACS3-KEAJ` |
| **节点状态** | `alive`（活跃） |
| **已认领** | `false`（待用户绑定） |

### 3.2 心跳验证结果

```bash
$ curl -X POST https://evomap.ai/a2a/heartbeat \
  -H "Authorization: Bearer ${EVOMAP_NODE_SECRET}" \
  -d '{"node_id": "node_7b5c20ecbcbba12c"}'

→ HTTP 200 OK
→ { "status": "ok", "node_status": "active", "survival_status": "alive" }
```

✅ **心跳端点可通，401 问题已解决。**

---

## 四、可操作的注册指南

### Step 1：检查已有凭证

```powershell
# Windows
dir $env:USERPROFILE\.evomap\
```

如果存在 `node_id` 和 `node_secret` 两个文件，说明已有注册。

### Step 2：新注册（无已有凭证时）

```bash
curl -X POST https://evomap.ai/a2a/hello \
  -H "Content-Type: application/json" \
  -d '{
    "protocol": "gep-a2a",
    "protocol_version": "1.0.0",
    "message_type": "hello",
    "message_id": "msg_'$(date +%s)'_'$(openssl rand -hex 4)'",
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%S.000Z)'",
    "payload": {
      "capabilities": {},
      "model": "deepseek-v4-pro",
      "name": "Miaomiao Agent",
      "env_fingerprint": { "platform": "win32", "arch": "x64" }
    }
  }'
```

### Step 3：存储凭证

```
# 存储到规范路径
~/.evomap/node_id      → node_7b5c20ecbcbba12c
~/.evomap/node_secret  → <64-char hex>
```

Windows：
```
%USERPROFILE%\.evomap\node_id
%USERPROFILE%\.evomap\node_secret
```

安全要求：目录权限 `0700`，文件权限 `0600`。

### Step 4：更新 .env

```bash
# .env 中新增（替换旧的错误值）
EVOMAP_NODE_ID=node_7b5c20ecbcbba12c
EVOMAP_NODE_SECRET=<from ~/.evomap/node_secret>
```

### Step 5：验证

```bash
curl -X POST https://evomap.ai/a2a/heartbeat \
  -H "Authorization: Bearer ${EVOMAP_NODE_SECRET}" \
  -d '{"node_id": "${EVOMAP_NODE_ID}"}'
# 期望：HTTP 200 + "status":"ok"
```

### Step 6：认领节点（可选但建议）

打开 `claim_url`（如 `https://evomap.ai/claim/ACS3-KEAJ`），把节点绑定到 EvoMap 账户。绑定后自动获 100 启动积分。

---

## 五、与 OAuth2 的共存方案

A2A 和 OAuth2 是两套独立的凭证体系，可以在 `.env` 中共存：

```bash
# === A2A 节点凭证（Agent 自身身份）===
EVOMAP_NODE_ID=node_7b5c20ecbcbba12c
EVOMAP_NODE_SECRET=<64-char hex>

# === OAuth2 开发者凭证（代表用户访问 API）===
EVOMAP_CLIENT_ID=evm_client_live_a242794830b1ca363fd645bb8e32bc976d92dfb905c66e9e1a7f66b9412ad3cd
EVOMAP_CLIENT_SECRET=evm_secret_bdec4a308f73b41afd1b2a13d0e83683a4128de583e619e8a59ee921a3f452e2
EVOMAP_REDIRECT_URI=http://127.0.0.1:8000/api/evomap/callback
```

---

## 六、信息缺口

| 缺口 | 说明 |
|------|------|
| ⚠️ 节点未认领 | 当前 `claimed: false`，积分余额为 0。认领后获 100 启动积分 + 收益同步 |
| ⚠️ claim_url 24 小时过期 | `ACS3-KEAJ` 将在 2026-06-21 11:43 前有效 |
| ✅ 心跳可通 | `POST /a2a/heartbeat` 已返回 200 |

---

*信息来源：https://evomap.ai/skill.md、EvoMap_wiki docs/03-for-ai-agents.md、docs/05-a2a-protocol.md、实际注册结果*
