# V1.1：EvoMap 节点注册 + 心跳验证

**指令编号**：05_op_evomap  
**目标 Agent**：实现 Agent  
**优先级**：P0（赛道"自进化"必须有 EvoMap 对接）  
**预估耗时**：15 分钟  

---

## 背景

V1.0 demo 可演示，但 EvoMap 节点尚未注册。赛道 The Pearl 要求自进化叙事，心跳跑起来是评分关键。本项目约定走**通用协议接入**（HTTP REST 直调 evomap.ai），不用 Evolver 插件。

---

## 任务

### 步骤 1：检查凭证是否存在

```bash
ls -la ~/.evomap/
```

如 `node_id` 和 `node_secret` 已存在，跳过步骤 2，直接进入步骤 3 心跳测试。

### 步骤 2：注册节点（如凭证不存在）

调用 EvoMap Hello 接口注册节点：

```
POST https://evomap.ai/a2a/hello
Content-Type: application/json

{
  "protocol": "a2a/1.0",
  "message_type": "hello",
  "sender_id": "urban-industry-assistant-tonglu",
  "payload": {
    "capabilities": ["land_evaluation", "industry_matching", "policy_reasoning"],
    "env_fingerprint": "python311-fastapi-leaflet-tianditu-deepseek-chat"
  }
}
```

预期返回：
```json
{
  "your_node_id": "...",
  "node_secret": "...",
  "claim_url": "...",
  "credit_balance": 100
}
```

### 步骤 3：保存凭证

将返回的 `node_id` 和 `node_secret` 写入：

```bash
mkdir -p ~/.evomap
echo "<node_id>" > ~/.evomap/node_id
echo "<node_secret>" > ~/.evomap/node_secret
```

### 步骤 4：验证心跳

**curl 测试**：

```bash
curl -X POST https://evomap.ai/a2a/heartbeat \
  -H "Authorization: Bearer $(cat ~/.evomap/node_secret)" \
  -H "Content-Type: application/json" \
  -d "{\"node_id\": \"$(cat ~/.evomap/node_id)\"}"
```

预期：HTTP 200，响应含 online 状态。

### 步骤 5：验证后端读取凭证正常

重启 uvicorn，确认 startup 日志显示 EvoMap 心跳后台任务已启动（不再提示"凭证未就绪"）。

---

## 注意事项

- sender_id 建议用 `urban-industry-assistant-tonglu`（全局唯一，含项目名+地域）
- 如果 Hello 接口返回 claim_url，记录下来（用户可能需要浏览器访问确认）
- 如果接口返回错误，抓完整响应体写入汇报，不要编造

---

## 验证标准

| 项 | 标准 |
|------|------|
| `~/.evomap/node_id` | 非空文件 |
| `~/.evomap/node_secret` | 非空文件 |
| Heartbeat curl | HTTP 200 |
| uvicorn startup 日志 | 不再提示"EvoMap 凭证未就绪" |
| 凭证无硬编码 | node_id/secret 仅存文件，不写进 .py 或 .env |

---

## 完成后

汇报写入 `D:\Projects\Urban_Industry_Assistant\outputs\handoffs\05_report_impl_op_evomap.md`。

汇报格式：
```
## 执行结果
✅ / ❌

## 注册响应
（贴 /a2a/hello 返回的完整 JSON，不含 node_secret）

## Heartbeat 验证
（贴 curl 结果）

## uvicorn 启动
（贴 startup 最后 5 行）
```
