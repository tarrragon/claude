# codebase-memory-mcp (cbm) 工具參考

> **定位**：cbm 是三 MCP 之一，定位為「跨檔案概念 / 語義搜尋入口」，搭配 BM25 + 向量索引提供 11-signal 排序。本檔記錄 CLI 用法、實機限制與 workaround，供 `search-tools-guide` 主檔 lazy-load。
>
> **何時讀本檔**：(1) 派發前需要選擇 cbm vs codegraph vs serena；(2) 對 `.claude/` 範圍做搜尋發現 cbm 結果為空；(3) 需要 cbm CLI 模式（PM 前台離線驗證）語法。

---

## 1. 工具呼叫方式（MCP deferred tools 已曝光）

**現況（2026-06-24 W1-006 驗證）**：`mcp__codebase-memory-mcp__*` 系列工具已正常曝光於 ToolSearch deferred tools，可直接呼叫。`ToolSearch(query="select:mcp__codebase-memory-mcp__list_projects")` 載入 schema 後呼叫成功（回傳已索引 project）。**MCP deferred tools 為首選呼叫路徑**，CLI 模式（§下方）保留為 PM 前台離線驗證的替代手段。

> **歷史**：W6-001.4（2026-05-25）實證當時 namespace 未曝光，需走 CLI workaround；W1-006 觀測 trigger（namespace 曝光）已於 2026-06-24 達成，缺口解除。

**CLI 統一格式**（PM 前台離線驗證 / MCP 不可用時 fallback）：

```bash
codebase-memory-mcp cli <tool_name> '<json_args>'
```

### 必備工具速查

| Tool | 用途 | 必填參數 | 典型呼叫 |
|------|------|---------|---------|
| `list_projects` | 列出已索引的 project | — | `codebase-memory-mcp cli list_projects '{}'` |
| `index_repository` | 建立 / 更新索引 | `repo_path` | `codebase-memory-mcp cli index_repository '{"repo_path":"/abs/path","mode":"moderate"}'` |
| `search_code` | BM25 文字搜尋（含 regex） | `project`, `pattern` | `codebase-memory-mcp cli search_code '{"project":"<id>","pattern":"BookValidationError"}'` |
| `search_graph` | 向量 + BM25 混合搜尋（11-signal） | `project`, `query` | `codebase-memory-mcp cli search_graph '{"project":"<id>","query":"error handling patterns"}'` |
| `detect_changes` | 增量更新偵測 | `project` | `codebase-memory-mcp cli detect_changes '{"project":"<id>"}'` |
| `delete_project` | 刪除索引（clean reindex 前用） | `project` | `codebase-memory-mcp cli delete_project '{"project":"<id>"}'` |

### project ID 命名規則

cbm 將 `repo_path` 轉成 project ID：去除前置 `/`，路徑分隔符 `/` 轉為 `-`。例：

```
/Users/tarragon/Projects/book_overview_v1
  → Users-tarragon-Projects-book_overview_v1
```

`list_projects` 回傳結果可直接複製當作其他工具的 `project` 參數。

### index_repository 進階參數

| 參數 | 預設 | 何時調整 |
|------|------|---------|
| `mode` | `moderate` | `fast`（粗略 BM25 only）/ `deep`（深層向量分析） |
| `include_globs` | repo 預設 | 限縮範圍時用 `["src/**/*.js","docs/**/*.md"]` |
| `exclude_globs` | `[]` | 排除 `node_modules`、`build/` |
| `include_hidden` | `false` | 索引 `.codex/`、`.github/` 等 hidden dir |
| `force_reindex` | `false` | 強制全量重建（搭配 `delete_project` 更乾淨） |

---

## 2. 實機限制：cbm 對 `.claude/` 不索引（v0.6.1 確認）

### 觀察事實

W6-001.4 PM 前台執行的 6 步驗證實驗：

| 步驟 | 操作 | 結果 |
|------|------|------|
| 1 | `list_projects '{}'` | `{"projects":[],"hint":"No projects indexed."}` |
| 2 | `index_repository '{"repo_path":"/Users/tarragon/Projects/book_overview_v1","include_globs":[".claude/**/*.md",".claude/**/*.py","docs/**/*.md"]}'` | indexed nodes=63155 edges=90919 elapsed_ms=3283 |
| 3 | `search_code '{"project":"...","pattern":"AGENT_PRELOAD"}'` | 10 results，**全部 `docs/`，零 `.claude/`** |
| 4 | 對照 `grep -rl "mcp__serena__find_symbol" .claude/` | 11 個 `.claude/` 檔案命中（含 `.claude/agents/AGENT_PRELOAD.md`） |
| 5 | 重 index 加 `include_hidden:true` + `force_reindex:true` + 空 `exclude_globs:[]` | 仍無 `.claude/` 結果 |
| 6 | `delete_project` 後 clean reindex 同條件 | 依舊不索引 `.claude/` |

### 結論

cbm v0.6.1 對 `.claude/` 目錄存在 **hardcoded skip**：

- 非統一 hidden dir blacklist：相同條件下 `.codex/` 可索引（前置實驗 search "lsp-first" 命中 `.codex/skill-trigger-map.md`）
- `include_globs` / `include_hidden` / `force_reindex` 皆無法覆寫
- 屬上游 cbm 行為，**不是設計缺陷**，本檔僅文件化

### 影響範圍

| 想搜尋的目標 | cbm 可用？ | 替代方案 |
|------------|-----------|---------|
| `src/` 程式碼 | 是 | cbm + codegraph |
| `docs/` 文件 | 是 | cbm |
| `.codex/` skill triggers | 是 | cbm |
| `.claude/agents/`、`.claude/rules/`、`.claude/skills/`、`.claude/hooks/` | **否** | rg / Grep + serena |
| `.claude/error-patterns/`、`.claude/methodologies/`、`.claude/references/` | **否** | rg / Grep |

---

## 3. cbm vs codegraph vs serena 分工

> 完整九維度對照、三刀流決策樹見 `../SKILL.md` 三 MCP 章節。本節為「按範圍」的速判版。

### 按搜尋範圍分工

| 範圍 | 主力工具 | 補強工具 | Why |
|------|---------|---------|-----|
| `src/`（程式碼） | cbm（概念）+ codegraph（caller / impact） | serena（精確符號定位） | 程式碼有結構，三 MCP 互補 |
| `src/` 重構前 blast radius | codegraph `impact` + serena `find_referencing_symbols` | — | 兩者皆語意級，雙保險 |
| `docs/` | cbm（語義） | rg（精確字串） | docs 重 concept matching |
| `.claude/` 全範圍 | rg（強制 fallback） | serena（.py 符號操作） | cbm 不索引；rg 是唯一通用入口 |
| `.claude/hooks/*.py` 符號層 | serena | rg | LSP-backed Python 操作 |
| 型別密集（TS / Dart / Python typed） | serena | LSP 直呼 | 型別感知不可替代 |

### 按任務性質分工

| 任務 | 工具 | 命令範例 |
|------|------|---------|
| 「找到處理 X 概念的所有檔案」 | cbm `search_graph` | `search_graph '{"project":"<id>","query":"book extraction pipeline"}'` |
| 「找符號 X 的定義 + 引用」 | serena `find_symbol` + `find_referencing_symbols` | （見 search-tools-guide §三 MCP 命令速查） |
| 「找誰呼叫了 X」 | codegraph `callers` | （見 search-tools-guide §三 MCP 命令速查） |
| 「修改 X 會影響什麼」 | codegraph `impact` + serena `find_referencing_symbols` | 雙重驗證 |
| 「在 `.claude/` 找含字面 Y 的檔案」 | rg | `rg -l "Y" .claude/` |
| 「在 `.claude/hooks/*.py` 重構 X 符號」 | serena `rename_symbol` | — |

---

## 4. Workaround 速查

| 情境 | Workaround |
|------|-----------|
| MCP deferred tools 不可用（fresh subprocess / headless） | 改用 CLI 模式 `codebase-memory-mcp cli <tool> '<json>'`（CC runtime session 內 `mcp__codebase-memory-mcp__*` 已可直接呼叫） |
| 想對 `.claude/` 做概念搜尋 | 改用 `rg -i "<keyword>" .claude/` + 必要時 serena 補符號級 |
| cbm 索引後仍找不到結果 | (1) 確認 project ID 拼寫；(2) `delete_project` + clean reindex；(3) 改 `mode:"deep"` |
| codegraph 索引耗時長 | 首次冷啟動需 embedding model 載入（BGE-Small-EN-v1.5，約 30-60s）；後續走快取 |
| serena MCP 子進程獨立呼叫失敗 | serena 預期由 CC runtime host 管理 stdin/stdout；直接 subprocess 呼叫需手動 jsonrpc framing |

---

## 5. 三 MCP 實證紀錄（W6-001.4）

### cbm CLI 模式（PM 前台驗證）

見本檔 §2「實機限制」六步實驗。

### serena 符號查詢實證（agent 補完）

呼叫 `find_symbol(name_path_pattern="BookValidationError")` 回傳：

```json
[
  {"name_path":"BookValidationError","kind":"Constant","relative_path":"src/background/domains/data-management/services/data-validation-service.js","body_location":{"start_line":34,"end_line":34}},
  {"name_path":"book_overview_v1/src/core/errors/BookValidationError","kind":"File","relative_path":"src/core/errors/BookValidationError.js","body_location":{"start_line":0,"end_line":83}},
  {"name_path":"BookValidationError[0]","kind":"Class","relative_path":"src/core/errors/BookValidationError.js","body_location":{"start_line":9,"end_line":74}},
  ...
]
```

**證據強度**：serena 同時返回 Class（核心定義 src/core/errors/）+ Constant（消費端 import 點）+ File 節點，展示 LSP 級型別感知。對比 cbm `search_code` 同 pattern 只能返回字面命中行。

### codegraph 連線驗證

`codegraph: ✓ Connected`（`claude mcp list` 輸出）；初始化握手回傳 `{"serverInfo":{"name":"codegraph","version":"0.16.6"}}`；workspace 索引啟動：

```
[INFO] codegraph_server::mcp::server: Indexing workspace: ["/Users/tarragon/Projects/book_overview_v1"]
[INFO] codegraph_memory::embedding::fastembed_embed: Loading embedding model: BGE-Small-EN-v1.5 (384d, 512-tok context)
```

**冷啟動約束**：fresh subprocess 首次索引需 30-60s（embedding model 下載 + tree-sitter parse）；CC runtime 內已暖機的 codegraph 即時可用。**Action**：派發 agent 時優先用 CC runtime 內的 `mcp__codegraph__*` deferred tools；CLI 模式僅作為 PM 前台離線驗證。

---

## 6. 與其他規則的關係

| 規則 / Skill | 關係 |
|-------------|------|
| `.claude/skills/search-tools-guide/SKILL.md` | 本檔的 parent；主檔含三 MCP 章節 + 命令速查 |
| `.claude/skills/lsp-first/SKILL.md` | 補強三 MCP 路由；LSP 為精度錨點，cbm/codegraph 為查詢入口 |
| `.claude/rules/core/tool-discovery.md` | ToolSearch 五問檢查；cbm MCP namespace 缺口（已於 W1-006 解除）曾為「規則 1 問題 5」的反例案例 |

---

**Last Updated**: 2026-06-24
**Version**: 1.1.0 — W1-006 落地：cbm MCP namespace 已曝光於 ToolSearch deferred tools，§1 改為 MCP deferred tools 首選 / CLI 為 fallback；`.claude/` 不索引限制（§2，v0.6.1）維持待 W1-005 上游修復
**Version**: 1.0.0 — 從 W6-001.4 落地：cbm CLI 用法 + `.claude/` 不索引限制 + 三 MCP 分工
