# PRD 修订 v1.1 补丁：ownership 字段规格修正

**发出方**：Orchestrator  
**接收方**：内容 Agent  
**指令编号**：01_revise_prd_v1.1_patch  
**时间**：2026-06-19  

---

## 背景

PRD v1.1（`specs/src/prd_v1.1.md`）第 100 行，聚合网格字段表中 `ownership` 原定为 `"混合（N 单位）"`（简化文本）。

经和洲确认，改为 **JSON 精确比例对象**，存储各单位面积占比。

## 修改

**文件**：`specs/src/prd_v1.1.md`  
**位置**：§2.3 聚合网格字段定义表，`ownership` 行

**原文**：
```
| `ownership` | TEXT | "混合（N 单位）" | 简化权属表示，N=被合并网格的权属单位数 |
```

**改为**：
```
| `ownership` | TEXT (JSON) | `{"大源村":0.45,"芦茨村":0.35,"国有":0.20}` | 精确存储各单位（村/国有/集体）面积占比的 JSON 对象 |
```

## 影响范围

- PRD v1.1 §2.3 字段定义表
- 架构文档 `lod_pyramid_design.md` 已同步（ownership 计算函数输出 JSON 对象）
- 不影响 v1.0 原始表（`land_grid_L0` 的 ownership 仍为单一文本）

## 验收

- PRD v1.1 第 100 行 ownership 字段描述与架构文档一致
- 版本修订记录中追加此行变更

---

## 完成后

无需单独汇报。直接在 `specs/src/prd_v1.1.md` 版本修订记录表中追加一行：

```
| v1.1-patch1 | 2026-06-19 | ownership 字段从"混合（N 单位）"改为 JSON 精确比例对象 | 和洲 → Orchestrator → 内容 Agent |
```
