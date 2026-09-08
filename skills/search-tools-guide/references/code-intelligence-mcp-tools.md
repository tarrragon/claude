# Code Intelligence MCP 三刀流

> **定位**：本檔為 `search-tools-guide` 主檔「Code Intelligence MCP 三刀流」節的完整版，收錄三個 Code Intelligence MCP server（codebase-memory-mcp / codegraph / serena）的九維度設計對照表、選擇決策樹，以及 JS Chrome Extension 開發情境下的工具組合範例。
>
> **何時讀本檔**：已確定要在 cbm / codegraph / serena 三者之間選擇，需要完整對照表或決策樹依據時。日常搜尋只需主檔「Code Intelligence MCP 三刀流」節的摘要即可判斷方向，不需要本檔的九維度細節。
>
> **同目錄**：`codebase-memory-tool.md`（cbm 專屬 CLI 用法、`.claude/` 不索引限制與 workaround）。
>
> 溯源：v5.2.0 拆分自 `SKILL.md`「Code Intelligence MCP 三刀流」節（體量收斂：全檔 6,723 tokens 超出 5,000 門檻 1.34 倍）。

---

## 三 MCP 設計對照表

| 維度 | codebase-memory-mcp (cbm) | CodeGraph | Serena / LSP |
|------|---------------------------|-----------|-------------|
| **後端架構** | 語言無關向量+BM25 混合索引 | TypeScript/JavaScript AST（sqlite WAL） | LSP 協定（language server） |
| **語言覆蓋** | 所有語言（向量向度） | JS/TS/Python/YAML/JSON（AST 支援度） | 編輯器已配置 LSP 的語言（Dart/JS/TS/Python 優先） |
| **持久化** | `~/.cache/codebase-memory-mcp/` | `.codegraph/` (local per-developer) | LSP server 進程內（session 級） |
| **Sync 機制** | 自動增量索引（watch mode） | 首次 init 後自動增量（2-5s lag） | LSP server 即時響應（file change event） |
| **Type Resolution** | 無型別感知 | AST 級型別資訊（TS/JS 完整、Python partial） | 語言伺服器提供完整型別資訊 |
| **跨 Service 查詢** | 單 repo 索引；支援多 project 管理 | 單 repo 初始化；可在外部 worktree 重複索引 | 單 LSP server 綁定，跨檔無額外能力 |
| **概念搜尋** | 向量語意搜尋（「找相似概念」）| 精確 AST 符號定位（無模糊搜尋） | 精確符號查詢（定義/引用） |
| **Symbol 編輯** | 無編輯能力 | `safe_delete_symbol`、其他編輯工具不支援 | `rename_symbol`、`replace_symbol_body`、`insert_before/after_symbol` |
| **Diagnostics** | 無 | 無 | LSP `analyze_files` 靜態檢查（Dart 優先） |

**特色對位**：cbm 的「語言無關 + 概念搜尋」是 codegraph/serena 都無法提供的；codegraph 在「自動增量 + 跨檔 caller 追蹤」獨佔；serena 在「型別感知 + symbol edit + diagnostics」領先。

## 三刀流工作流決策樹

選擇工具時按以下決策樹進行。各情境的工具推薦經實測驗證：

```
搜尋 / 分析需求
    |
    +-- 找概念相似的程式碼 / 模糊搜尋
    |   → codebase-memory-mcp (cbm) [推薦]
    |   例：「找所有處理錯誤的地方」「找 state 相關邏輯」
    |   理由：向量語意搜尋，callstack/control flow 無法表達但 cbm 可召回
    |
    +-- 精確找某函式的所有 caller
    |   → CodeGraph + Serena（兩者都行；cgraph 更快）
    |   例：「deleteBook 被誰呼叫」「fetchBooks 的 callers」
    |   理由：AST caller/callee 追蹤，比正則搜尋精確
    |
    +-- 分析修改影響範圍 (blast radius)
    |   → Serena（最安全）或 CodeGraph（最快）
    |   例：「改 API 回傳型別會影響多少地方」
    |   理由：Serena type-aware；CodeGraph 自動 sync caller 資訊
    |
    +-- 重命名符號 / 安全重構
    |   → Serena [唯一支援]
    |   例：`BookRepository` → `BookStore`；重命名後自動更新 100+ 引用
    |   理由：LSP rename 包含檔案儲存；其他工具不支援
    |
    +-- 跨 Repo / 跨服務符號查詢（本專案單 repo 不常見）
    |   → codebase-memory-mcp [推薦]
    |   例：「這個概念在其他專案實作過嗎」
    |   理由：cbm 支援多 project 管理，向量搜尋跨 repo
```

## JS Chrome Extension 場景：三刀流最佳組合

本專案（Chrome Extension + JS 前端 + Python hook 混合）的典型工作流：

| 工作 | 首選工具 | 理由 | 備選 |
|------|---------|------|------|
| 探索新需求 / 理解架構邊界 | cbm semantic search | 模糊找「event」「dispatch」「listener」等概念 | Serena find_symbol（但需精確名稱） |
| 追蹤事件流（event → listener → handler） | CodeGraph call graph | 自動追蹤完整呼叫鏈（特別是 async callback） | rg + Serena（手動多步） |
| 確認改動影響（改 message schema 會卡誰） | CodeGraph impact + Serena rename | cbm 找相關檔，Serena 確認精確引用 | rg 逐個驗證 |
| 重構回呼函式名 / API 簽章 | Serena rename + replace_symbol_body | rename 改所有引用；replace_symbol_body 改實作 | 手動 sed + rg |
| 查詢 Chrome API 使用方式 | Serena hover（JS LSP）| 顯示 TypeScript 型別簽章（chrome.runtime.sendMessage 參數） | 網路搜尋 + WebSearch |

**實踐建議**：cbm 為「初期探索」甜蜜點（可模糊記得概念名但不清楚確切函式名），codegraph 為「精確追蹤」甜蜜點（給定起點快速展開 caller/callee），serena 為「安全編輯」甜蜜點（批量重構無誤）。三者絕非同時用，而是按需求切換。
