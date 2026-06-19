## 研究汇报
**任务**：EvoMap OAuth2 开发者平台集成方案研究（v2修订版），回答5个核心问题
**完成状态**：完成
**关键发现**：
1. **选型结论**：A2A 协议和 OAuth2 平台是互补而非替代——OAuth2 用于"消费集体智能"（评估前检索 recipe 注入 prompt），A2A 用于"贡献自身经验"（评估后发布 Capsule）。路演 Demo 核心为 OAuth2 提示词增强器模式，现有 evo_client.py 保留作为贡献通道（来源：HACKATHON.md Demo + README.zh-CN.md Scopes 表 + index.js）
2. **eval_service.py 改造**：在 `evaluate_grids()` 函数 Step 4（构建 prompt）和 Step 5（LLM 调用）之间插入 EvoMap 检索，用 `user_message` 做 `/developer/oauth/recipes?q=` 全文搜 + `/developer/oauth/genes?limit=3` 补充通用能力，检索结果注入 user_prompt 尾部。降级策略：5s 超时 + 所有异常静默跳过，保证评估主流程不受影响。
3. **Python OAuth2 PKCE**：基于 quickstart index.js 给出完整 Python 实现（`oauth_client.py`），含 PKCE S256 生成、授权 URL 构造、code→token 交换、token 刷新、recipe/gene/reuse API。路演用"启动时一次性授权"策略，内存存 token，无需持久化。
4. **路演叙事**：设计三步 Demo——Step 1 关闭 EvoMap 做基线评估 → Step 2 开启 EvoMap 同问题对比"检索到 N 条经验，评估更精准" → Step 3 自进化面板展示进化前后五维雷达图变化。核心叙事从"本地自进化"转为"借助集体智能的网络自进化"。
5. **Test Mode**：强烈推荐路演使用 test mode app（`evm_client_test_…`），沙箱隔离、逼真响应、零真实副作用、可读回。需赛前完成注册+一次授权。Test mode 下 genes/reuse 返回空——路演"检索"环节只需 recipes 端点。

**交付物**：`research/evomap_devkit_integration_v2.md`（~24KB，含6章+2附录）
**信息缺口**：无
**实施优先级**：P0（路演必须）6项共~2.7h，P1（建议）3项，P2（赛后）3项
