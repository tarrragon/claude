# 可觀測性設計規則

本文件定義專案中所有元件的可觀測性要求，確保系統行為在開發和運行時可追蹤、可診斷。

> **核心理念**：每個生命週期階段必須有可觀測輸出，否則無法除錯。
>
> **來源**：WebSocket 連線排查時，因缺乏生命週期日誌，無法定位斷線階段的歷史教訓。

---

## 1. 生命週期階段日誌（強制）

每個長時間運行的元件（服務、連線、背景任務）必須在以下階段產出日誌：

| 階段 | 說明 | 範例 |
|------|------|------|
| 啟動 | 服務初始化完成、版本、監聽位址 | `ccsession-monitor starting on :8765` |
| 連線 | 建立/斷開外部連線 | `WebSocket client connected`, `client disconnected` |
| 處理 | 關鍵業務邏輯執行 | `new session detected: abc123`, `parsing JSONL file` |
| 錯誤 | 異常發生、錯誤恢復 | `parse error in session abc123: unexpected EOF` |
| 關閉 | 優雅停機、資源釋放 | `shutting down, closing 3 connections` |

**禁止行為**：

| 禁止 | 原因 |
|------|------|
| 啟動後無任何輸出 | 無法確認服務是否正常運行 |
| 連線建立/斷開無日誌 | 無法追蹤連線狀態變化 |
| catch/recover 區塊不記錄 | 異常被靜默吞掉 |

---

## 2. 異常雙通道輸出（強制）

> 延伸自 quality-baseline.md 規則 4（Hook 失敗必須可見）。

所有異常處理必須同時輸出到兩個通道：

| 通道 | 用途 | 實作方式 |
|------|------|---------|
| stderr / 即時輸出 | 開發者即時看到 | Go: `log.Printf` / `slog.Error`; Dart: `debugPrint` |
| 持久化日誌 | 事後分析 | Go: 結構化 JSON log; Dart: 日誌框架 |

**每個 catch/recover 區塊的最低要求**：

- 記錄錯誤訊息和上下文（哪個元件、哪個操作）
- 記錄堆疊追蹤（如可取得）
- 若只做 `return`/`continue` 不記錄：必須在註解中說明原因

---

## 2.5 統一日誌工具（強制）

使用專案統一的日誌工具，禁止散落的原生輸出。

| 要求 | 說明 |
|------|------|
| 統一入口 | 所有日誌透過專案指定的日誌工具輸出 |
| 禁止散落輸出 | 禁止直接使用 `debugPrint`、`print`、`console.log` 等原生方法 |
| 分級輸出 | 依嚴重程度使用 error / warning / info / debug 級別 |

> 本專案使用 `AppLogger`，詳見 CLAUDE.md 6.4 節。

---

## 2.6 全域錯誤處理完整性（強制）

應用程式必須建立完整的全域錯誤攔截，防止未處理異常導致無聲崩潰。

| 層級 | 覆蓋範圍 |
|------|---------|
| 框架層 | 框架內部錯誤（如 Flutter 的 Widget 建置錯誤） |
| 平台層 | 平台級未處理異常 |
| 非同步層 | 非同步操作中的未處理異常 |

**驗證方式**：確認三層皆已設定，缺少任一層即為不完整。

---

## 3. 長時間運行元件心跳（建議）

長時間運行的服務應定期輸出健康狀態，便於確認服務存活：

| 項目 | 建議 |
|------|------|
| 心跳間隔 | 30-60 秒 |
| 心跳內容 | 活躍連線數、監控中的 session 數、記憶體使用 |
| 觸發方式 | 定時器或事件驅動（如每 N 個請求） |

> 心跳為建議項目，非強制。但在除錯困難的場景（如 WebSocket 長連線）中強烈建議啟用。

---

## 4. 開發階段 Debug Log（強制）

開發階段必須提供足夠的 Debug 級別日誌，方便追蹤程式流程：

| 場景 | Debug Log 內容 |
|------|---------------|
| 檔案監控 | 偵測到的檔案變更路徑和類型 |
| 訊息解析 | 解析的 JSONL 行數、欄位摘要 |
| 狀態轉換 | session 狀態從 A 變為 B 的原因 |
| WebSocket 通訊 | 訊息類型和大小（不含完整內容） |

**Debug Log 規範**：

| 要求 | 說明 |
|------|------|
| 可開關 | 必須能透過配置或環境變數控制 Debug Log 開關 |
| 不含敏感資料 | 禁止記錄完整對話內容、API key 等 |
| 含上下文 | 每條 Debug Log 必須包含元件名稱或 layer 標識 |

---

## 4.5 CC 工具遙測：tool_parameters（可選增強，非強制）

> **定位**：本節與 1-4 節（產品程式碼可觀測性）不同層級——記錄的是 Claude Code session 的工具呼叫遙測，可作為 dispatch 行為分析的外部資料來源。**屬可選增強，非強制要求。**

CC v2.1.157 起，OpenTelemetry 的 `tool_decision` 事件可包含 `tool_parameters` 欄位（bash 指令字串、MCP / skill 名稱），需顯式設定環境變數 `OTEL_LOG_TOOL_DETAILS=1` 才記錄（預設關閉）。

| 項目 | 說明 |
|------|------|
| 啟用方式 | 環境變數 `OTEL_LOG_TOOL_DETAILS=1`（或 settings.json `env` 區段） |
| 記錄內容 | bash 指令、MCP server / skill 名稱 |
| 預設狀態 | 關閉（API key / 密碼自動濾除） |
| 潛在用途 | 與 `.claude/hooks/dispatch_stats.py` 等 dispatch 分析整合，量化工具使用分佈 |

**Why**：開啟後可獲得「PM 與 subagent 實際呼叫哪些指令」的遙測，有助 dispatch 行為審計與 hotpath 分析。

**Consequence（隱私成本，必須權衡）**：開啟後 bash 指令全文進遙測管道。若 OTEL collector 為外部端點，等同將指令內容外送，可能含路徑、檔名等專案資訊。**非剛需場景不應預設開啟。**

**Action**：僅在有明確 dispatch 可觀測性需求且 OTEL collector 為可信（本地或受控）端點時，才設 `OTEL_LOG_TOOL_DETAILS=1`；一般開發不需開啟。本節為能力備記，不要求任何元件強制啟用。

---

## 5. 可觀測性檢查清單

新增或修改功能時，確認：

- [ ] 啟動階段有日誌輸出（版本、配置、監聽位址）？
- [ ] 關鍵連線事件有日誌（建立、斷開、重連）？
- [ ] 異常處理同時輸出到 stderr 和日誌？
- [ ] catch/recover 區塊有記錄錯誤上下文？
- [ ] 日誌使用專案統一工具（非原生 `debugPrint`/`print`/`console.log`）？
- [ ] 全域錯誤處理三層皆已設定（框架層/平台層/非同步層）？
- [ ] 關鍵狀態變化有 Debug Log？
- [ ] 關閉/停機有日誌輸出？

---

## 相關規則

- .claude/rules/core/quality-baseline.md - 規則 4：Hook 失敗必須可見（異常雙通道）
- .claude/references/quality-go.md - Go 後端可觀測性要求
- .claude/references/quality-dart.md - Flutter 前端可觀測性要求

---

**Last Updated**: 2026-06-01
**Version**: 1.2.0 - 新增 4.5「CC 工具遙測：tool_parameters」可選增強章節（CC v2.1.157 / W4-028.3）。歷史 1.0–1.1 版見 git log。
