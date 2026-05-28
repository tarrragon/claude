---
id: PC-164
title: MCP binary 名稱假設未實證 — `.mcp.json` 與 detector 同源誤判
category: process-compliance
severity: medium
status: active
created: 2026-05-27
related:
- PC-068
- PC-143
- PC-131
- ARCH-015
---

# PC-164: MCP binary 名稱假設未實證

當 MCP server 配置（`.mcp.json` 的 `command` 欄位）與 detector 程式碼（如 `mcp_detector.py` 的 `_detect_binary` 呼叫）同時引用某個 binary 名稱，但設計者未實證該 binary 在實際 npm/pip 套件中對外暴露的名稱時，雙端會同步誤判：MCP server 無法啟動 + detector 報告 MISSING + session-start 完全沒有可見錯誤。用戶看到的只是「codegraph_* tools 不存在」這種高層症狀，根因被多層遮蔽。

**Why**：MCP 配置與 detector 是同源邏輯的兩個落點，常由同一份設計文件（規格或心智模型）派生。若設計者只用「直覺命名」（例如「這是 MCP server，binary 名稱應該是 X-mcp」）而沒 `which X` 或讀套件 `package.json` 的 `bin` 欄位實證，兩個落點會同步寫入錯誤名稱。

**Consequence**：雙端誤判形成「自洽錯誤」——detector 報告 MISSING 看似合理（用戶以為是真的沒裝），用戶嘗試重裝後仍 MISSING（因為 detector 找錯名）。錯誤永久存活，直到有人從第三方角度（如本案例：用戶手動 `which codegraph` 發現實際 binary 名）才能識破。本 PC 觸發案例中，W6-001.2 已 completed 9 個月仍未被察覺，直到用戶在 W1-101 .mcp.json 修正後主動檢討。

**Action**：新增 MCP server 配置或 detector 邏輯前，**必須** `which <suspected-binary-name>` 實證；若 binary 不存在於 PATH，需查套件 source（`npm view <package> bin` 或 `package.json` 的 `bin` 欄位）確認真實名稱再寫入配置。

## 觸發案例

### W6-001.2 + W1-101 同源誤判（2026-05-27 揭露）

**時序**：

1. 2026-04-XX：W6-001.2 設計 `project-init` MCP detector 擴充，`mcp_detector.py` 寫入 `_detect_binary("codegraph-mcp")` + 註解「對於不支援 --version 的 binary（如 codegraph-mcp），可傳 ['--info']」。設計者假設 binary 名稱 `codegraph-mcp`，未實證。
2. 同期：`.mcp.json` codegraph section 寫入 `"command": "codegraph-mcp"`，同樣未實證。
3. 2026-04-XX：W6-001.2 完成（acceptance 全勾，pytest 通過——測試 mock 也用 `codegraph-mcp` 字面，自洽通過）。
4. 用戶安裝 `@colbymchenry/codegraph` 0.9.4（npm package），實際暴露 binary 名為 `codegraph`（無 `-mcp` 後綴）。
5. 每次 session 啟動：
   - MCP server 無法啟動（`codegraph-mcp` not found），`codegraph_*` tools 全部未註冊
   - `project-init check` 對 codegraph section 報告 MISSING（但因為 `project-init` 套件本身 OUTDATED 未 reinstall，連 MCP section 都沒顯示，雙重遮蔽）
   - 用戶完全沒可見錯誤訊息
6. 2026-05-27：用戶在不相干情境中發現「codegraph_* tools 不能用」，PM 調查鏈：W1-101 修 `.mcp.json` → 用戶檢討「為何 session-start 沒抓到」→ 發現 W6-001.2 設計層同源誤判 → W1-102 修 `mcp_detector.py` → W1-104 立此 PC。

**雙重遮蔽機制**：

| 層級 | 應該偵測 | 為何沒偵測 |
|------|---------|-----------|
| MCP server runtime | server 啟動失敗應警示 | Claude Code 對 MCP server 啟動失敗無 user-facing 訊息（已知設計） |
| `project-init` MCP detector | detector 報告 MISSING | detector 找錯名（自證錯誤）；且 `project-init` 套件 OUTDATED 連 section 都未生成 |
| User 觀察 | 應該注意到 codegraph_* tools 缺失 | tools 缺失症狀分散在多個工具呼叫上，無中心警示 |

## 根本原因

### 表層原因

| 原因 | 說明 |
|------|------|
| 設計時用直覺命名 | 「MCP server」+「codegraph」→ 設計者直覺認為 binary 是 `codegraph-mcp` |
| 雙端共用錯誤假設 | `.mcp.json` + `mcp_detector.py` 同期撰寫，誤用同一假設值 |
| 測試 mock 自洽 | pytest mock 用 `codegraph-mcp` 字面測試，永遠通過，無法揭露假設錯誤 |

### 深層原因

| 維度 | 說明 |
|------|------|
| 「實證」不在 detector 新增 SOP | 新增 MCP detector 前無「`which` 驗證 binary」的明文規範 |
| 設計文件未要求 source-of-truth | W6-001.2 設計文件假設 binary 名為 detector design 的權威，未引用套件 `package.json` 或 npm registry |
| 觀察工具自驗證機制弱 | `project-init check` 對偵測對象的 source-of-truth 漂移無自警示 |

## 與 PC-068 / PC-143 / PC-131 的關係

| PC | 領域 | 與本 PC 共通機制 |
|----|------|----------------|
| PC-068 | ANA spawn IMP 前 grep 既有資產 | 都屬「假設前實證」家族；PC-068 防重複造輪子，本 PC 防誤命名 |
| PC-143 | lavender Phase 1 spec 描述既有 CLI flag 用未驗證值 | 同源——設計時假設值，未 grep source 驗證；可視為 PC-143 在 MCP 領域的延伸 |
| PC-131 | 採用外部工具前必須精度實證 | 共通核心：對外部依賴的假設必須有實證程序 |

**整合 advice**：未來修訂 PC-068 時，可考慮將本 PC 與 PC-143 整併為「假設前實證原則」上位 PC，下分 ANA spawn / lavender spec / MCP detector 三個觸發領域。

## 正確做法

### Approach A：新增 MCP server 配置前 `which` 實證（推薦）

| 動作 | 何時 |
|------|------|
| 新增 `.mcp.json` server 條目前，`which <command-name>` 確認 binary 存在 | 配置撰寫時 |
| 不存在則查套件 `npm view <package> bin` / `package.json` 的 `bin` 欄位 | binary 不存在時 |
| 將實證輸出（command 路徑 + version）記錄於對應 commit message | commit 時 |

**Why**：MCP server 配置是用戶不可見的 runtime 依賴，配置錯誤無 user-facing 訊息，必須在撰寫期驗證。

**Consequence**：每次新增 MCP server 多 1 個 Bash 步驟，可忽略不計。

**Action**：將本流程加入 MCP 配置 onboarding doc / `.mcp.json` 註解。

### Approach B：MCP detector 設計時 `which` 實證

| 動作 | 何時 |
|------|------|
| `mcp_detector.py` 新增 detector function 前，PM 或 agent 必須 `which <binary>` 確認 | detector 撰寫時 |
| pytest 加入「true binary lookup」測試（非 mock）作 sanity check | pytest 設計時 |

**Why**：mock 測試永遠自洽，無法揭露 binary 名稱錯誤；需 real-binary sanity test 作補強。

**Consequence**：sanity test 對 missing binary 會 skip 或 fail，需設計 conditional skip。

**Action**：補強 detector pytest 模板含真實 `which` 呼叫（已隔離為 sanity layer）。

### Approach C：session-start 跨來源一致性驗證（長期）

| 動作 | 何時 |
|------|------|
| session-start hook 比對 `.mcp.json` 的 command 名與系統 PATH 真實 binary | 每次 session 啟動 |
| 不一致時警示 + 提供修復指令 | session 啟動 |

**Why**：自動防護優於人工自律；session-start 是最早可發現此類錯誤的時機。

**Consequence**：需修改 hook 並加跨來源驗證邏輯，工作量中等。

**Action**：列為 follow-up ticket（屬於 W1-103 強化 stale CLI 提醒的進階版）。

## 防護措施

### 第一層：撰寫期 SOP（短期）

**適用條件**：適用於所有新增 MCP server 配置或 detector function 的場合。零工程成本，依賴撰寫者自律。

撰寫者新增 binary 引用前 `which <command>` 實證，輸出貼到 commit message 作審計軌跡。

### 第二層：pytest sanity layer（中期）

**適用條件**：適用於有 detector 程式碼的場合（非 .mcp.json 純配置）。中等工程成本，但事後驗證強度高。

detector pytest 加入「real binary lookup, skip if missing」測試層，避免 mock 自洽通過遮蔽問題。

### 第三層：session-start 跨來源驗證 hook（長期）

**適用條件**：跨整個專案的 MCP 配置一致性檢查，需獨立 ANA ticket 評估成本效益（W1-103 的進階延伸）。

session-start hook 比對 `.mcp.json` command 名 vs PATH 真實 binary，不一致即警示。

## 邊界與例外

| 情境 | 適用 |
|------|------|
| 新增 MCP server（npm / pip / cargo 安裝的 CLI） | 適用 |
| 已存在 server 維護（如版本升級不換 binary 名） | 不適用 |
| binary 名與套件名一致（如 `ripgrep` 套件提供 `rg` ... 不，`rg`！這就是反例） | 仍適用——binary 名永遠需 `which` 實證 |
| 純 stdio MCP server（無對外 binary） | 不適用 |

**邊界判定原則**：本 PC 觸發前提是「文件 / 程式碼引用一個 binary 名稱」。任何此類引用都必須有 `which` 實證背書。引用 binary 名稱的位置包含 `.mcp.json` / detector 程式碼 / SKILL.md / agent prompt / hook script 等。

## 相關

| 參考 | 關聯 |
|------|------|
| PC-068 | ANA spawn IMP 前 grep 既有資產（假設前實證家族） |
| PC-143 | lavender spec 描述既有 CLI flag 用未驗證值（同源延伸至 MCP 領域） |
| PC-131 | 外部工具採用前精度實證（同核心原則） |
| ARCH-015 | `.claude/` 派發位置決策（dispatch-position） |
| W1-101 | `.mcp.json` 修正觸發案例 |
| W1-102 | `mcp_detector.py` 修正觸發案例 |
| W6-001.2 | 同源誤判設計源頭（已 completed 但實質失效） |

---

**Last Updated**: 2026-05-27
**Version**: 1.0.0 — 初始建立，源 W1-101 + W1-102 + W6-001.2 三案例證據鏈
