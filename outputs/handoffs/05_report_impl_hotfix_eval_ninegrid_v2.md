## 完成状态
✅ 完成

## 任务 1：get_grid_stats 支持聚合表

- 根据 grid_id 前缀（`_L{level}_`）自动选择对应聚合表
- 聚合表直接取 `area_sqm` + `land_type_top3` JSON 解析分布
- L0 保持不变（GROUP BY 逐格统计）

**验证**：
```
grid_L2_2065_8333 → grid_count=1, area=2,210,000 m² (3,315 亩) ✅
grid_1            → grid_count=1, area=10,000 m² (15 亩) ✅
```

## 任务 2：诊断（后端等效验证）

| 诊断项 | 结果 |
|--------|------|
| A: grid_layer API | zoom=12 → 943 features, zoom=13 → 3,558 features ✅ |
| B: gridIndex 样本 | grid_id 格式正确 (`grid_L2_xxx_xxx`) ✅ |
| C: mousemove | 修复后 findGridAt null 时穿透 HTTP fallback ✅ |
| D: ninegrid API | zoom=14 政府端 → 9 cells, `True True 6` ✅ |

## 九宫格问题根因判断

预加载层 `interactive: false` 已加（hotfix_batchH），mousemove 回退已修复（本次），不再阻断 HTTP ninegrid。两个修复联合解决了九宫格无效果问题。
