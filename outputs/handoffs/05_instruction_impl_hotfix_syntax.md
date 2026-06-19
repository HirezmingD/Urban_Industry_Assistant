# 紧急修复：app.js 第 49 行语法错误导致黑屏

**指令编号**：05_hotfix_syntax  
**目标 Agent**：实现 Agent  
**优先级**：P0（页面完全不可用）  

---

## 根因

`static/app.js` 第 49 行：

```javascript
TIANDITU_KEY = *** || '';
```

`***` 不是合法 JavaScript，浏览器报 `Uncaught SyntaxError: Unexpected token '**'`，全部脚本中止执行，地图不渲染。

## 修复

改为从 API 返回的 `data` 中取天地图 key：

```javascript
TIANDITU_KEY = data.tianditu_key || '';
```

**文件**：`static/app.js`，第 49 行，1 处改动。

## 验证

刷新浏览器 `http://127.0.0.1:8000/static/index.html`，地图正常加载，Console 无红色报错。

## 完成后

汇报写入 `05_report_impl_hotfix_syntax.md`。
