## 完成状态
✅ 完成

## 修改清单
- [x] `src/schemas.py` — `AgentReply.summary` 类型从 `EvalSummary` 改为 `str`（默认 `""`）
- [x] `src/schemas.py` — `EvalSummary` 标记"未使用，历史遗留，勿删"
- [x] `src/services/eval_service.py` — 删除 `"response_format": {"type": "json_object"}`

## uvicorn 启动验证
```
[startup] EvoMap 凭证未就绪，跳过心跳后台任务
uvicorn startup OK
Routes: 17
```

## 验证结果
- `AgentReply.summary` → `str` ✅
- LLM 请求体不再含 `response_format` ✅
- import 无报错 ✅
- uvicorn 启动正常 ✅
