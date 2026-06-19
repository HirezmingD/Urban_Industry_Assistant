## 架构汇报

**任务**：阅读 PRD 和研究报告，输出 Urban_Industry_Assistant 系统架构与接口设计文档，七份交付物输出到 `specs/arch/` 目录。

**完成状态**：完成

**架构文档路径**：

| # | 文件 | 内容 |
|:--:|------|------|
| 1 | `specs/arch/architecture.md` | 四层架构总图 + 技术选型清单（12 项含理由）+ 政府端/企业端差异总表 |
| 2 | `specs/arch/modules.md` | 14 个模块的职责/依赖/函数签名 + 14 步实现顺序 + `requirements.txt` |
| 3 | `specs/arch/api.md` | 8 个 REST API 完整定义（路径+入参JSON+出参JSON+错误码+端权限） |
| 4 | `specs/arch/database.md` | 5 张表建表 SQL + R-tree 空间索引 + JSON 扩展字段方案 + 数据量估算 |
| 5 | `specs/arch/sequence.md` | 5 个核心场景时序图（Mermaid 文字版）+ 同步/异步/缓存分析 |
| 6 | `specs/arch/grid_preprocessing.md` | 渔网预处理 Python 伪代码 + 输出格式选择 + 耗时估算 + 降级回退方案 |
| 7 | `specs/arch/performance.md` | 3 个性能问题决策（并发/渔网查询/LLM 成本）+ PRD 指标对照表 |

---

**关键决策说明**：

1. **前端：纯 HTML+JS，无构建工具** — 20 小时开发窗口不允许任何 node_modules/webpack；Leaflet.js + Chart.js 全部 CDN 引入，零编译步骤
2. **SQLite 扩展字段：JSON 字段而非独立扩展表** — Demo 阶段边开发边补充，JSON `extras` 字段天然适合 `industry_score_*`/`policy_match`/`env_score` 的渐进式填充，不改表结构
3. **空间查询：SQLite 内建 R-tree，拒绝 SpatiaLite** — Windows 编译 spatialite.dll 是已知坑点；R-tree 两步法（粗筛 + shapely 精确过滤）< 30ms，完全够用
4. **LLM 串行化：asyncio.Semaphore(1) + 队列深度 10** — 保护单 API key 不被比赛现场的并发冲垮；企业匹配使用 asyncio.gather 并行（3 家独立评估压缩到 ~8s）
5. **九宫格悬停：策略 A 优先（前端本地缓存全量渔网索引）** — 183K × 5 字段 ≈ 5MB gzip，浏览器完全扛得住；零网络延迟 < 20ms；策略 B（API 查询）作为降级
6. **EvoMap 发布：评估完成后异步触发** — `asyncio.create_task(evo_client.publish(...))`，不阻塞用户等待评估结果
7. **地图瓦片离线兜底** — 前端检测在线加载失败 → 自动切换 `data/tiles/{z}/{x}/{y}.png` 本地路径，不依赖服务端判断
8. **政府端/企业端差异在 API 层做字段过滤** — `grid_service` 查全量字段，`api/map_routes` 按 `role` 过滤 `ownership`/`geometry` 字段，不在数据库层做行级权限
9. **渔网预处理耗时 45-75 秒（100m）** — shrink 到 30 秒（200m 降级），脚本独立于运行时，执行一次即可
10. **Python 3.11 硬约束遵守** — 所有代码路径在 `D:\TOOLS\MiniConda\envs\agent_gpu_py311\python.exe` 下执行

---

**模块实现顺序**：

```
config → schemas → database → system_prompt → grid_service → policy_service
→ eval_service → evo_service → ent_service → map_routes → agent_routes
→ evo_routes → ent_routes → main.py → static/index.html
```

14 步后端 + 1 步前端，预计编码 12 小时，不超出 20 小时窗口。

---

**风险提示**：

1. **渔网预处理依赖 DLTB_2020.xlsx 数据** — 若此数据未就绪，渔网不做空间连接，所有 `land_type` 为空，Agent 退化为纯文本对话。已在 `grid_preprocessing.md` 提供无数据降级方案
2. **EvoMap Hub 可用性不确定** — 已按研究报告建议做前端假数据兜底 + 录制备选。架构中 publish 为异步，不影响核心评估
3. **前端九宫格策略 A 的 183K 条缓存实测** — 若浏览器内存扛不住（概率低，5MB gzip 对现代浏览器不是问题），自动降级为策略 B（API 查询 + throttle 100ms）
4. **DeepSeek API 限速** — 已做 Semaphore(1) 串行化 + 队列深度 10 + 降级返回静态评估。建议和洲准备 1 个备选 API key（如硅基流动）作为双保险
5. **企业端未充分测试** — PRD 中有场景 D/E 较详细，但 Demo 优先级 P3（可砍）。架构已完整定义 API，实现 Agent 可正常编码；若时间不足直接砍掉

---

**待确认事项**：

1. **DeepSeek API key 是否已就绪**？架构假定使用 `DEEPSEEK_API_KEY` 环境变量
2. **DLTB_2020.xlsx 的字段映射**：土地利用分类代码到 `land_type` 文本的映射表，需要和洲确认 46 类用地的实际分类名
3. **XZQ.xlsx 14 个乡镇/街道的边界 GeoJSON** 是否已准备好？渔网预处理需要桐庐行政区划边界来做裁剪
4. **天地图 API Key**：架构使用了天地图卫星影像瓦片，需要和洲提供 API Key
5. **是否接受企业端作为 P3 可砍项**？若 20 小时不够，建议只演示政府端完整流程（框选 + 对话 + 企业面板 + EvoMap），企业端在 PPT 讲架构
6. **离线瓦片是否已下载**？建议 z12-z17 共 6 级，约 2 小时下载时间

---

**Skill 沉淀**：无。本次是首个架构任务，尚未有复用模式积累。待质检通过后，可将"县域产业评估 Agent 架构模板"沉淀为 Skill。

---

**完成度自检**：

| PRD 章节 | 功能 | 架构覆盖 |
|------|------|:--:|
| 3.1 地图面板 | 底图 / 渔网叠加 / 框选 / 点选 / 九宫格 / 匹配高亮 / 边界约束 | ✅ api/map_routes + grid_service + database |
| 3.2 对话面板 | 输入 / 回复结构 / 消息列表 / 对话上下文 | ✅ api/agent_routes + eval_service + prompts |
| 3.3 企业面板 | 列表 / 搜索 / 多选 / 批量匹配 | ✅ api/ent_routes + ent_service + enterprises 表 |
| 3.4 EvoMap 面板 | 进化经验 / 偏好理解度 / 雷达图 / Capsule 贡献 | ✅ api/evo_routes + evo_service + evomap_capsules 表 |
| 4.1 性能要求 | 框选<1s / 点选<500ms / LLM<15s / 匹配<20s | ✅ performance.md 全部对照 |
| 4.2 并发要求 | 数十人 + LLM 串行化 | ✅ 单 worker + Semaphore(1) |
| 4.4 安全性 | URL 参数区分角色 / 数据隔离 / EvoMap 密钥 | ✅ API 层按 role 过滤字段 |
| 5.1 数据需求 | 渔网 / 卫星瓦片 / 栅格 / 企业案例 | ✅ grid_preprocessing + database |

**无遗漏**。PRD 5 章所有功能需求在架构中均有明确的模块、API、数据库表对应。

---

**一句话总结**：实现 Agent 拿到这 7 份文档后，可以从 `config.py` 开始按 14 步顺序编码，每一步的输入输出依赖都是明确的，每一个 API 的入参出参 JSON 都可直接用于前端联调。
