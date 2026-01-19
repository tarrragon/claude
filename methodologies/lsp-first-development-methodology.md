# LSP 優先開發策略方法論

## 核心原則

**LSP 能解決的問題必須優先使用 LSP**

### 為什麼優先使用 LSP

| 優勢 | 說明 | 效益 |
|------|------|------|
| **效能** | ~50ms vs ~45 秒 | 900x 加速 |
| **Token 效率** | 結構化資料輸出 | 降低 API 成本 |
| **語意精準** | 語言伺服器分析 | 非文字比對 |

---

## 工具選擇決策樹

```
需求分析：
├─ 需要呼叫層級分析？ → LSP (incomingCalls / outgoingCalls)
├─ 需要查找介面實作？ → LSP (goToImplementation)
├─ 需要符號定義？ → LSP (goToDefinition) / Dart MCP
├─ 需要引用追蹤？ → LSP (findReferences) / Serena
├─ 需要 Hover 資訊？ → Dart MCP (mcp__dart__hover)
├─ 需要工作區搜尋？ → Dart MCP (mcp__dart__resolve_workspace_symbol)
├─ 需要精準符號編輯？ → Serena (replace_symbol_body)
└─ LSP 不可用？ → Serena (備援方案)
```

### 工具優先順序

1. **優先**: LSP 工具 / 語言 MCP 工具
2. **次選**: Serena MCP（LSP 功能等效替代）
3. **備援**: 傳統 Grep/Glob 搜尋

---

## 9 種 LSP 操作

| 操作 | 用途 | 使用場景 |
|------|------|---------|
| **goToDefinition** | 跳轉定義 | 追蹤符號來源 |
| **findReferences** | 查找引用 | 重構影響分析 |
| **hover** | 懸停資訊 | 查看型別和文件 |
| **documentSymbol** | 文件符號 | 理解檔案結構 |
| **workspaceSymbol** | 工作區搜尋 | 跨檔案符號查詢 |
| **goToImplementation** | 實作查找 | 追蹤介面實作 |
| **callHierarchy** | 呼叫層級 | 呼叫分析 |
| **incomingCalls** | 呼叫來源 | 誰呼叫了這個函式 |
| **outgoingCalls** | 呼叫目標 | 這個函式呼叫了誰 |

---

## 當前可用工具對照

### Dart MCP 工具

| 工具 | 功能 | 對應 LSP |
|------|------|---------|
| `mcp__dart__hover` | 懸停資訊 | hover |
| `mcp__dart__resolve_workspace_symbol` | 工作區搜尋 | workspaceSymbol |
| `mcp__dart__signature_help` | 簽名提示 | signatureHelp |
| `mcp__dart__analyze_files` | 專案分析 | diagnostics |

### Serena MCP 工具（備援）

| 工具 | 功能 | 對應 LSP |
|------|------|---------|
| `mcp__serena__get_symbols_overview` | 符號概覽 | documentSymbol |
| `mcp__serena__find_symbol` | 符號查找 | goToDefinition |
| `mcp__serena__find_referencing_symbols` | 引用追蹤 | findReferences |

---

## 效能對比

| 操作 | LSP | 傳統方法 | 效能提升 |
|------|-----|---------|---------|
| 查找引用 | ~50ms | ~45 秒（grep） | 900x |
| 跳轉定義 | ~10ms | ~5 秒（搜尋） | 500x |
| 符號概覽 | ~20ms | ~10 秒（解析） | 500x |
| 呼叫層級 | ~100ms | 無法自動化 | - |

### Token 效率對比

| 工具 | 輸出類型 | 預估 Token |
|------|---------|-----------|
| **LSP findReferences** | 結構化位置列表 | ~100-500 |
| **Dart MCP hover** | 結構化資訊 | ~200-500 |
| Serena find_referencing_symbols | 完整上下文 | ~2000-5000 |
| Grep 搜尋 | 完整行內容 | ~3000-10000 |

---

## 快速檢查

開發時的 LSP 使用檢查：

- [ ] 符號定義追蹤用 LSP？
- [ ] 重構影響分析用 findReferences？
- [ ] 型別資訊用 hover？
- [ ] 呼叫層級分析用 callHierarchy？
- [ ] 避免使用 Grep 做符號搜尋？

---

## Reference

### 相關方法論
- [自然語言化撰寫方法論](./natural-language-programming-methodology.md) - 程式碼可讀性
- [錯誤修復和重構方法論](./error-fix-refactor-methodology.md) - 重構流程

### 詳細資料
- [LSP 優先策略 SKILL](../skills/lsp-first/SKILL.md) - 完整操作指南和故障排除
- [Hook 系統快速參考](../hook-system-reference.md) - LSP 環境檢查 Hook
