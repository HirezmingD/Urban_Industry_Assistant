# 批次 E 运维：离线瓦片下载

**指令编号**：05_op_tiles  
**目标 Agent**：实现 Agent  
**优先级**：P0（演示必需）  
**预估耗时**：10-30 分钟（取决于天地图限速）

---

## 任务

执行桐庐县域离线天地图卫星瓦片下载。

## 环境

- Python：`D:\TOOLS\MiniConda\envs\agent_gpu_py311\python.exe`
- 工作目录：`D:\Projects\Urban_Industry_Assistant`
- API key 从 `.env` 自动读取（已配置）

## 执行命令

```bash
cd /d/Projects/Urban_Industry_Assistant && D:/TOOLS/MiniConda/envs/agent_gpu_py311/python.exe scripts/download_tiles.py --zoom-min 12 --zoom-max 15
```

## 预期

| zoom | 瓦片数 |
|------|--------|
| 12 | 72 |
| 13 | 240 |
| 14 | 870 |
| 15 | 3,422 |
| **合计** | **~4,600** |

输出目录：`data/tiles/{z}/{x}/{y}.png`

## 注意事项

- 脚本已处理重复下载（已有则跳过）
- 失败瓦片记录到 `failed_tiles.txt`
- 不要改脚本，直接跑
- 跑完后统计成功/失败数和总大小

---

## 验证标准

| 项 | 标准 |
|------|------|
| 命令正常退出 | exit code = 0 |
| `data/tiles/` 下有 4 级目录 | z12/ z13/ z14/ z15/ |
| 成功数 ≥ 90% | 少量边界外瓦片 404 正常 |
| 总大小约 50-200 MB | 视瓦片内容 |
| 失败清单 `failed_tiles.txt` | 如存在，失败 < 5% |

---

## 完成后

汇报写入 `D:\Projects\Urban_Industry_Assistant\outputs\handoffs\05_report_impl_op_tiles.md`。

汇报格式：
```
## 执行结果
✅ / ❌

## 统计
| zoom | 成功 | 失败 | 总大小 |
|------|------|------|--------|
| 12   |      |      |        |
| 13   |      |      |        |
| 14   |      |      |        |
| 15   |      |      |        |

## 总耗时
（贴末尾输出）
```
