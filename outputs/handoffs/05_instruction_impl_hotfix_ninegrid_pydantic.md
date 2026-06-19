# 九宫格 Pydantic 校验报错——紧急修复

**指令编号**：05_hotfix_ninegrid_pydantic  
**目标 Agent**：实现 Agent  
**优先级**：P0（九宫格完全不可用）  

---

## 根因

`map_routes.py` 第 162 行：

```python
@router.get("/ninegrid", response_model=list[GridFeature])
```

`GridFeature` 要求 `land_type` 必填。但九宫格响应已精简到 6 字段（无 `land_type`），Pydantic 校验失败 → 500。

## 修复

**文件**：`src/api/map_routes.py`，第 162 行

```python
# 改前
@router.get("/ninegrid", response_model=list[GridFeature])

# 改后
@router.get("/ninegrid")
```

去掉 `response_model`，让原始 dict 直接返回，不经过 Pydantic 校验。

## 验证

重启 uvicorn，鼠标移过地图 → 九宫格出现。cmd 无红色报错。

## 完成后

汇报写入 `05_report_impl_hotfix_ninegrid_pydantic.md`。
