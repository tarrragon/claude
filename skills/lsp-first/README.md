# LSP 優先策略 - 快速參考

## 核心原則

**LSP 能解決的問題必須優先使用 LSP**

## 快速操作指南

### 符號查找
```
LSP(operation="goToDefinition", filePath="path/to/file", line=N, character=N)
```

### 引用追蹤
```
LSP(operation="findReferences", filePath="path/to/file", line=N, character=N)
```

### Hover 資訊
```
LSP(operation="hover", filePath="path/to/file", line=N, character=N)
```

### 文件符號
```
LSP(operation="documentSymbol", filePath="path/to/file", line=1, character=1)
```

### 呼叫層級（誰呼叫這個函式）
```
LSP(operation="prepareCallHierarchy", filePath="path/to/file", line=N, character=N)
LSP(operation="incomingCalls", ...)
```

### 介面實作
```
LSP(operation="goToImplementation", filePath="path/to/file", line=N, character=N)
```

## 工具優先順序

1. **LSP** - 符號查找、引用追蹤、呼叫層級
2. **語言 MCP** - 測試執行、Hot Reload
3. **Serena MCP** - 備援方案

## 安裝 LSP 插件

```bash
# 啟用 LSP
export ENABLE_LSP_TOOL=1

# 安裝插件市場
/plugin marketplace add boostvolt/claude-code-lsps

# 安裝語言插件
/plugin install dart-analyzer@claude-code-lsps
/plugin install pyright@claude-code-lsps
/plugin install vtsls@claude-code-lsps
```

## 注意事項

- LSP 使用 **1-based** 座標（line: 1, character: 1）
- 首次使用需等待索引完成
- 自建插件需確保 LSP 伺服器在 PATH 中
