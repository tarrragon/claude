---
name: lsp-first
description: "LSP 優先開發策略工具。Use for: (1) 查詢 LSP 操作指令, (2) 配置新語言 LSP 插件, (3) LSP vs MCP 工具選擇決策, (4) 自建 LSP 插件指南。Use when: 需要搜尋符號/定義/引用、想知道 LSP 和 MCP Serena 各自適合什麼場景、新增語言支援需要配置 LSP 時。"
---

# LSP 優先開發策略

---

## 核心原則

**LSP 能解決的問題必須優先使用 LSP**

| 優勢 | 說明 | 效益 |
|------|------|------|
| **效能** | ~50ms vs ~45 秒 | 900x 加速 |
| **Token 效率** | 結構化資料輸出 | 降低 API 成本 |
| **語意精準** | 語言伺服器分析 | 非文字比對 |

詳細效能資料：`references/performance-comparison.md`

---

## LSP 環境自動檢查

**Session 啟動時自動執行 LSP 環境檢查**

### 檢查項目

1. **基本 LSP**（所有專案必備）
   - marksman (Markdown)
   - yaml-language-server (YAML)

2. **語言特定 LSP**（根據專案類型）
   - Flutter/Dart: Dart SDK 內建 LSP
   - TypeScript/JavaScript: vtsls
   - Python: pyright
   - Go: gopls
   - Rust: rust-analyzer

### 相關檔案

- **檢查腳本**: `.claude/hooks/lsp-environment-check.py`
- **配置檔案**: `.claude/hooks/lsp-check-config.json`
- **整合位置**: `.claude/hooks/startup-check-hook.sh` (步驟 6.6)

---

## LSP 9 種操作速查

| 操作 | 用途 | 使用場景 |
|------|------|---------|
| goToDefinition | 跳轉符號定義 | 追蹤函式來源、查看類別定義 |
| findReferences | 查找所有引用 | 重構前影響分析、變更評估 |
| hover | 懸停型別資訊 | 查看 API 文件、確認參數型別 |
| documentSymbol | 列出檔案符號 | 快速理解檔案結構 |
| workspaceSymbol | 跨檔案搜尋 | 找出類別定義、模糊查詢 |
| goToImplementation | 實作查找 | 追蹤抽象類別實作 |
| prepareCallHierarchy | 呼叫層級準備 | 準備函式呼叫分析 |
| incomingCalls | 呼叫來源 | 找出誰呼叫了這個函式 |
| outgoingCalls | 呼叫目標 | 找出這個函式呼叫了誰 |

各操作詳解、範例和 Dart MCP 替代方案：`references/lsp-operations.md`

---

## 工具選擇

搜尋工具的完整選擇決策樹和場景對照表，詳見 `/search-tools-guide`。

以下為 LSP 專屬的選擇要點：

### LSP 獨佔能力（無法由其他工具替代）

| 能力 | LSP 操作 |
|------|---------|
| 呼叫層級分析 | incomingCalls / outgoingCalls |
| 介面實作查找 | goToImplementation |
| 精確型別推導 | hover（語意級別） |

### 工具優先順序

1. **優先**: LSP 工具（語意精準、效能最佳）
2. **次選**: Dart MCP / Serena MCP（LSP 功能等效替代）
3. **備援**: 傳統 Grep/Glob 搜尋

Dart MCP 和 Serena MCP 的工具列表與使用建議：`/search-tools-guide`

---

## LSP 伺服器配置

自建插件、官方插件市場、跨平台安裝、故障排除：`references/lsp-setup-guide.md`

---

## 相關資源

- `/search-tools-guide` - 搜尋工具選擇指南（含 Dart MCP、Serena、Grep 完整對照）
- `/startup-check` - Session 啟動檢查
- [boostvolt/claude-code-lsps](https://github.com/boostvolt/claude-code-lsps) - 官方 LSP 插件市場
- [Marksman](https://github.com/artempyanykh/marksman) - Markdown LSP
- [yaml-language-server](https://github.com/redhat-developer/yaml-language-server) - YAML LSP

---

**Last Updated**: 2026-03-02
**Version**: 1.0.0
