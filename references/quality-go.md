# Go 品質規則

本文件為 Go 語言的品質規則補充。通用規則見 quality-common.md。

> **適用代理人**：fennel-go-developer
>
> **適用版本**：Go 1.21+（使用 `log/slog` 標準庫）

---

## 1. 命名慣例（Effective Go）

| 類型 | 規則 | 正確 | 錯誤 |
|------|------|------|------|
| 套件名稱 | 小寫單詞，不用下劃線 | `parser`, `watcher` | `jsonlParser`, `file_watcher` |
| 導出名稱 | MixedCaps | `SessionEvent`, `ParseLine` | `session_event`, `parse_line` |
| 未導出名稱 | mixedCaps | `sessionID`, `parseRawLine` | `session_id`, `parse_raw_line` |
| 方法 | 不加 Get 前綴 | `Owner()` | `GetOwner()` |
| 介面（單方法） | 方法名 + `-er` | `Reader`, `Parser` | `IParser`, `ParserInterface` |
| 接收者 | 1-2 字母縮寫 | `(p *Parser)` | `(this *Parser)` |
| 錯誤變數 | `err` 或 `ErrXxx` | `ErrSessionNotFound` | `sessionError` |

**禁止**：蛇形命名、冗餘包名重複、縮寫（`usrMgr`）、模糊詞（`data`, `info`）

---

## 2. 常數集中管理（強制）

每個 package 必須有 `constants.go` 集中定義所有常數，**程式碼中禁止硬編碼數值或字串**。

```go
// constants.go
type SessionStatus int

const (
    SessionStatusActive SessionStatus = iota
    SessionStatusIdle
    SessionStatusCompleted
)

const (
    DefaultPort            = 8765
    ActiveThresholdSeconds = 120
    MaxHistoryLines        = 1000
    HeartbeatIntervalSecs  = 30
)
```

**禁止行為**：

| 禁止 | 正確做法 |
|------|---------|
| `port := 8765` | `port := DefaultPort` |
| `time.Sleep(30 * time.Second)` | `time.Sleep(HeartbeatIntervalSecs * time.Second)` |
| `if count > 1000` | `if count > MaxHistoryLines` |

---

## 3. 字串集中管理與多語系（強制）

所有字串統一在 `messages/` 目錄管理，**程式碼中禁止硬編碼任何字串**。

```
server/messages/
├── log_messages.go    # 開發者 log 訊息（英文常數）
├── api_messages.go    # API 錯誤碼（Client 可見）
├── cli_messages.go    # CLI 提示訊息
└── i18n/              # 使用者可見文字（多語系）
    ├── en.json
    └── zh-TW.json
```

正確做法（使用常數）：

```go
logger.Info(messages.LogNewSessionFile, "sessionID", id)
return WSResponse{Error: messages.ErrCodeSessionNotFound}
```

錯誤做法（硬編碼字串）：

```go
logger.Info("new session detected", "id", id)
return WSResponse{Error: "session not found"}
```

Client 可見的錯誤使用**錯誤碼**（如 `"SESSION_NOT_FOUND"`），由 Client 側負責本地化顯示。

---

## 4. 結構化日誌（log/slog，強制）

```go
// 初始化（main.go）
logger := slog.New(slog.NewJSONHandler(os.Stderr, &slog.HandlerOptions{
    Level: slog.LevelDebug,
}))

// 每條 log 必須包含 "layer" 欄位（UC-011 格式變動偵測）
logger.Warn(messages.LogUnknownField,
    "layer", "jsonl_parser",
    "field", unknownKey,
    "hint", messages.LogFormatChangeHint)
```

---

## 5. 錯誤處理

```go
// Sentinel error（可比較）
var ErrSessionNotFound = errors.New("session not found")

// 自訂錯誤類型（含上下文）
type ParseError struct {
    SessionID string
    Cause     error
}
func (e *ParseError) Error() string { return fmt.Sprintf("parse session %s: %v", e.SessionID, e.Cause) }
func (e *ParseError) Unwrap() error { return e.Cause }

// 保留上下文
return fmt.Errorf("read file %s: %w", path, err)

// 錯誤：丟棄上下文
return errors.New("read failed")
```

**禁止 `_ = err` 丟棄錯誤**，必須處理或明確在註解說明理由。

---

## 6. 執行方式

所有 Go 指令必須在 `server/` 子目錄下執行，使用子 shell 避免 cd 污染：

```bash
(cd server && go test ./...)
(cd server && go vet ./...)
(cd server && go build ./...)
```

禁止直接 `cd server`（污染 shell 工作目錄）。

> 詳細規則：.claude/rules/core/bash-tool-usage-rules.md

---

## 7. Go 品質檢查清單

（在通用清單基礎上追加）

- [ ] 命名符合 Effective Go 規範（無蛇形、無 Get 前綴、接收者縮寫）
- [ ] 每個 package 有 `constants.go`，無硬編碼數值
- [ ] 所有字串集中在 `messages/` 目錄，無硬編碼字串
- [ ] 每條 log 含 "layer" 欄位
- [ ] 錯誤處理保留上下文，無 `_ = err`
- [ ] 所有 Go 指令透過子 shell 執行

---

## 8. 可觀測性要求（Go 後端）

> **來源**：.claude/references/observability-rules.md — 通用可觀測性規則的 Go 特化要求。

### 8.1 啟動日誌（強制）

服務啟動時必須輸出版本和監聽位址，便於確認服務正常運行：

```go
log.Printf("ccsession-monitor %s starting on :%d", Version, DefaultPort)
log.Printf("scanning existing JSONL files in %s", watchDir)
```

### 8.2 運行心跳（建議）

長時間運行的服務應定期輸出統計資訊：

```go
// 每 HeartbeatIntervalSecs 輸出一次
slog.Info(messages.LogHeartbeat,
    "layer", "server",
    "active_sessions", len(sessions),
    "ws_connections", connCount,
)
```

### 8.3 異常告警（強制）

錯誤處理必須同時輸出到 stderr（透過 slog）和結構化日誌，保留完整上下文：

```go
// 正確：含 layer、操作、錯誤上下文
slog.Error(messages.LogParseError,
    "layer", "jsonl_parser",
    "sessionID", id,
    "error", err,
)

// 錯誤：只記錄錯誤訊息，缺少上下文
log.Println(err)
```

### 8.4 Go 可觀測性檢查清單

- [ ] `main()` 啟動時輸出版本和監聽位址
- [ ] 每個 `if err != nil` 區塊有含 layer 的結構化 log
- [ ] WebSocket 連線建立/斷開有日誌
- [ ] 檔案監控事件（新增/變更/刪除）有 Debug log

---

## 相關文件

- .claude/rules/core/quality-common.md - 通用品質基線
- .claude/rules/core/bash-tool-usage-rules.md - Bash 工具使用規則
- .claude/references/observability-rules.md - 通用可觀測性規則

---

**Last Updated**: 2026-03-27
**Version**: 1.1.0 - 新增可觀測性要求章節（0.2.1-W1-003）
