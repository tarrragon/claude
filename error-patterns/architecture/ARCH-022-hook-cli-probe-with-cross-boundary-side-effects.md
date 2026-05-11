# ARCH-022: Hook 用 CLI 探測產生跨界隱性副作用

## 核心原則

Framework hook 不該對 user-scope 設定產生隱性副作用。Hook 透過 spawn 子 CLI 探測狀態時，子 CLI 內部可能對遠端服務、個人設定、隱私資料發起請求；此副作用對 hook 設計者隱形，對用戶不可見。

**Why**：framework hook 在每個 session 啟動時自動執行，使用者無法即時審視其行為。若 hook 透過 CLI 間接觸發 user-scope 動作（HTTP 請求、token 讀取、檔案存取），等同 framework 在用戶背後做事。

**Consequence**：（1）每 session 啟動隱性付出網路 / 計算成本；（2）對遠端服務發送的請求可能洩漏使用模式；（3）副作用累加跨專案 sync 後放大；（4）hook timeout 看似邊緣案例，實際是「每次都接近 timeout」的設計問題被誤判為「偶爾失敗」。

**Action**：hook 探測狀態時優先讀取本地檔案（settings JSON / 註冊表 / lock file），避免 spawn 子 CLI；必須 spawn 時，明確限定子 CLI 的範圍（如 `--scope user` 而非全範圍探測），並驗證子 CLI 內部不會發起遠端請求。

---

## 錯誤症狀

Framework hook 透過 spawn 子 CLI 探測狀態，子 CLI 內部執行範圍超過探測目的，造成下列問題：

- **執行時間遠超預期**：spawn 子 CLI 可能觸發其內部完整初始化或健康檢查流程，hook 從預期的 < 100ms 拖到 8-10s
- **隱性網路請求**：子 CLI 對 user 註冊的所有遠端服務發送 HTTP / RPC 請求，完成 hook 探測目的不需要的副作用
- **跨專案 sync 後放大**：framework 共享後，每個專案 session 啟動都付出此成本
- **Timeout 訊號被誤判**：「偶爾 timeout」表面看是邊緣案例，實際是「每次都拖到接近 timeout 閾值」的設計問題

典型表現（zhtw-mcp 整合案例）：

| 探測目的 | 實際副作用 |
|---------|----------|
| 確認 zhtw-mcp 是否註冊到 Claude Code | spawn `claude mcp list` |
| `claude mcp list` 內部行為 | 對所有 MCP server（Gmail / Google Drive / Linear / Greptile / Calendar）做健康檢查 |
| 完成探測平均耗時 | 8.9s（vs 直讀 settings JSON < 50ms） |
| 副作用 | 每 session 啟動，對所有遠端 MCP server 發 HTTP 請求 |

---

## 根因分析

### 根因 1：探測目的與探測機制範圍不對稱

設計者採用「最直觀」的官方 CLI 介面探測，但官方 CLI 的範圍遠大於探測需求。例：探測「某個 MCP 是否已註冊」（local file check 即可），卻用「列出所有 MCP 並健康檢查」的 CLI 命令。

**Why 容易發生**：官方 CLI 是公開介面，設計者直覺認為「用公開介面比讀檔穩定」，忽略了 CLI 副作用範圍。

**Action**：設計 hook 探測前，先以一句話寫下「我想知道什麼」與「子 CLI 內部會做什麼」，比對兩者範圍是否對齊。範圍不對齊即進入選項 A 或 B。

### 根因 2：子 CLI 副作用對設計者透明

設計者在自己的環境驗證 hook 時，可能誤以為「8s 是初始 cache miss 後就會穩定」或「一次性成本可接受」。實際上：

- 跨 session 不會 cache（每 session 啟動 hook）
- 跨專案 sync 後成本累加（N 專案 × M session/day）
- 子 CLI 對遠端服務的請求被視為「正常 health check」，不會觸發告警

**Action**：設計階段在乾淨環境（新 session / 多專案模擬）跑 hook 至少一輪，量測平均耗時，並用 `lsof -p <pid>` 觀察是否有預期外的網路連線；耗時 > 1s 或出現外部 socket 即觸發機制範圍重新評估。

### 根因 3：Timeout 訊號被視為瑕疵而非警訊

當 hook 偶爾 timeout 時，設計者第一反應是「調高 timeout」或「視為軟性瑕疵」。但 timeout 接近閾值本身就是訊號：探測機制與探測目的範圍不對稱。

「偶爾 timeout」應觸發 WRAP 重新審視，而非單純調整參數。

**Action**：Timeout 接近閾值時，先用 `time` / `timeit` 量測平均耗時，再對照「探測目的」與「子 CLI 內部執行範圍」；若兩者不對齊，依根因 1 的 Action 重新設計探測機制。

---

## 建議做法

### 選項 A：File-based 探測取代 CLI-based 探測（推薦）

直接讀取設定檔（如 `~/.claude.json`、`.mcp.json`、`settings.local.json`）判斷狀態，無需 spawn CLI。

| 對照 | CLI-based | File-based |
|------|-----------|-----------|
| 耗時 | 8-10s | < 50ms |
| 副作用 | 對遠端服務發 HTTP | 無 |
| 失敗 | timeout 時 hook 顯示 unavailable | 讀檔失敗時可 fallback |
| 跨平台 | 統一 | 路徑可能變動（需 fallback） |

**讀檔失敗時的 fallback 設計**：先試 file-based，失敗時再 spawn CLI（保底）。當設定檔路徑屬工具公開合約（如 `~/.claude.json` 為 Claude Code 公開設定路徑）時，file-based 為主、CLI fallback 為輔的組合在穩定性與副作用上優於純 CLI。若設定檔路徑非公開合約且可能隨版本變動，fallback 機制可降低破壞風險。

### 選項 B：限定子 CLI 範圍

無法避免 spawn 子 CLI 時，傳入 scope 參數限定範圍：

| 不限定 | 限定 |
|--------|------|
| `claude mcp list`（檢查所有 server） | `claude mcp get <name>`（單一 server） |
| `kubectl get all`（所有資源） | `kubectl get pod <name>`（單一 pod） |
| `git status`（整 repo） | `git status -- <path>`（單一路徑） |

成本：scope 參數每個 CLI 不同，需逐個學習。回報：副作用降低幅度視 CLI 設計而定（本案例由 8.9s 降至 < 50ms，約 178 倍）。

### 選項 C：Hook 設計時加入「子 CLI 副作用評估」步驟

在 framework 規則層加入 hook 設計清單：spawn 子 CLI 前，先列出子 CLI 內部執行的所有動作（含網路請求）。若副作用範圍超過探測目的，改用選項 A 或 B。

---

## 判斷準則：哪些情境適用本 pattern

| 情境特徵 | 是否適用 ARCH-022 |
|---------|-----------------|
| Framework hook spawn 子 CLI 探測本地狀態 | 是（核心場景） |
| 子 CLI 內部對遠端服務發 HTTP / RPC | 是 |
| Hook 平均執行時間 > 1s | 是（觸發訊號） |
| 子 CLI 範圍小於 hook 探測範圍（如同 CLI 但限定 scope） | 不適用 |
| 一次性執行的腳本（非常駐 hook） | 部分適用（副作用較小但仍應評估） |

---

## 與其他 error pattern 的關係

| Pattern | 關聯 |
|---------|------|
| ARCH-018（hook-blanket-requirement-vs-nested-rule-conflict） | 同屬 hook 設計類；ARCH-018 處理規則衝突，本 pattern 處理副作用範圍 |
| ARCH-020（duplicate-validation-logic） | 同屬「邏輯應該在哪」類；ARCH-020 是「分散」問題，本 pattern 是「探測範圍超範圍」問題 |

## 相關事件與 Ticket

| 事件 | 日期 | 說明 |
|------|------|------|
| W17-139 | 2026-05-05 | zhtw-mcp 整合，hook 採用 `claude mcp list` 探測 |
| W17-139 hook 驗證 | 2026-05-05 | 發現 hook 平均耗 8.9s，「偶爾 timeout」 |
| WRAP 分析 | 2026-05-05 | 揭露 timeout 訊號為設計副作用而非軟性瑕疵 |
| W17-143 | 2026-05-05 | IMP ticket 修復 hook 改用 file-based 三層 scope 探測 |

## 相關文件

- `.claude/hooks/zhtw-mcp-availability-check-hook.py` — 本 pattern 的觸發案例
- `.claude/skills/wrap-decision/SKILL.md` — WRAP 框架揭露 timeout 訊號的方法
- `.claude/rules/core/quality-baseline.md` 規則 4（Hook 失敗必須可見）+ 規則 6（失敗案例學習）
- `.claude/rules/core/observability-rules.md` — Hook 可觀測性規範

---

**Last Updated**: 2026-05-05
**Version**: 1.0.0 — 初版；source W17-143 WRAP 分析（zhtw-mcp hook 探測機制設計副作用揭露）
