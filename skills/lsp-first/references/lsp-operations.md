# LSP 9 種操作詳解

---

## 1. goToDefinition - 跳轉定義

**用途**：找到符號的定義位置

**使用場景**：
- 追蹤函式來源
- 查看類別定義
- 理解變數宣告

**範例**：
```
LSP(operation="goToDefinition", filePath="lib/main.dart", line=15, character=10)
```

## 2. findReferences - 查找引用

**用途**：找出所有引用某符號的位置

**使用場景**：
- 重構前影響分析
- 變更影響評估
- 了解 API 使用情況

**範例**：
```
LSP(operation="findReferences", filePath="lib/domains/book/book.dart", line=26, character=6)
```

## 3. hover - 懸停資訊

**用途**：取得符號的型別資訊和文件

**使用場景**：
- 查看 API 文件
- 確認參數型別
- 理解返回值

**Dart MCP 替代**：
```
mcp__dart__hover(uri="file:///path/to/file.dart", line=10, column=5)
```

## 4. documentSymbol - 文件符號

**用途**：列出檔案中所有符號

**使用場景**：
- 快速理解檔案結構
- 找出類別中的方法
- 瀏覽模組 API

## 5. workspaceSymbol - 工作區搜尋

**用途**：跨檔案搜尋符號

**使用場景**：
- 找出類別定義
- 搜尋全域函式
- 模糊符號查詢

**Dart MCP 替代**：
```
mcp__dart__resolve_workspace_symbol(query="ClassName")
```

## 6. goToImplementation - 實作查找

**用途**：找出介面或抽象類別的所有實作

**使用場景**：
- 追蹤抽象類別實作
- 理解多態架構
- 驗證介面契約

## 7. prepareCallHierarchy - 呼叫層級準備

**用途**：準備呼叫層級分析

**使用場景**：
- 準備函式呼叫分析
- 取得呼叫層級項目

## 8. incomingCalls - 呼叫來源

**用途**：找出誰呼叫了這個函式

**使用場景**：
- 重構前影響分析
- 追蹤事件傳遞
- 了解依賴關係

## 9. outgoingCalls - 呼叫目標

**用途**：找出這個函式呼叫了誰

**使用場景**：
- 理解函式依賴
- 分析執行流程
- 追蹤呼叫鏈
