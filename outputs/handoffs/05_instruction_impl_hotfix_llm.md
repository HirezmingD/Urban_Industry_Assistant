# 批次 E 热修复：LLM 对话报错

**指令编号**：05_hotfix  
**目标 Agent**：实现 Agent  
**优先级**：P0（阻断性 bug）  
**预估工作量**：5 分钟

---

## 背景

批次 E 完成后联调发现 `/api/agent/chat` 对话报 500 错误：

```
fastapi.exceptions.ResponseValidationError: 1 validation error:
{'type': 'model_attributes_type', 'loc': ('response', 'summary'), 
 'msg': 'Input should be a valid dictionary or object to extract fields from', 
 'input': '桐庐县当前无具体产业用地网格数据...'}
```

## 根因

`schemas.py` 中 `AgentReply.summary` 类型错误。三处代码不一致：

1. **System Prompt**（`system_prompt.py` 第 72 行）—— `summary` 是**字符串**（正确）
2. **LLM 实际返回** —— 返回的 JSON 中 `summary` 是字符串（正确）
3. **Pydantic 模型**（`schemas.py` 第 376 行）—— 定义 `summary: EvalSummary`（**嵌套对象**，与上两处矛盾）

LLM 返回的字符串被 FastAPI 尝试校验为 `EvalSummary` 对象，校验失败。

另外 `deepseek-chat` 模型名也需修正（`.env` 中 `deepseek-v4-pro` 不存在，已手动改为 `deepseek-chat`）。

---

## 修改清单（2 处文件）

### 1. `src/schemas.py` — 修复 `AgentReply.summary` 类型

**当前**（约第 376 行）：
```python
summary: EvalSummary = Field(default_factory=lambda: EvalSummary(grid_count=0, total_area_mu=0.0))
```

**改为**：
```python
summary: str = Field(default="", description="评估总体摘要")
```

同时将 `EvalSummary` 类标记为 `# 未使用（历史遗留，勿删）`，不改删除是避免 import 链断裂。

### 2. `src/services/eval_service.py` — 删除 `response_format`

**当前**（约第 244-245 行）：
```python
"temperature": 0.3,
"response_format": {"type": "json_object"},
```

**改为**：
```python
"temperature": 0.3,
```

原因：`deepseek-chat` 对该参数行为不确定（v4-pro 不支持时直接返回空字符串），且 System Prompt 已约束"严格按 JSON 格式返回"，Prompt 约束比 API 参数更可靠。

---

## 验证标准

| 项 | 标准 |
|------|------|
| `AgentReply.summary` | 类型为 `str`，默认 `""` |
| LLM 请求体 | 不含 `response_format` 字段 |
| `uvicorn` 启动正常 | 无 import 报错 |
| `POST /api/agent/chat` | 返回 200，`summary` 为字符串 |

---

## 完成后

将汇报写入 `D:\Projects\Urban_Industry_Assistant\outputs\handoffs\05_report_impl_hotfix_llm.md`。

汇报格式：
```
## 完成状态
✅ / ❌

## 修改清单
- [x] schemas.py AgentReply.summary → str
- [x] eval_service.py 删除 response_format

## uvicorn 启动验证
（贴启动最后 5 行）
```
