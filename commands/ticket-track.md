# Claude 指令：Ticket Track

CSV 式 Ticket 追蹤系統 - 輕量級的 Ticket 狀態追蹤和查詢工具。

## 使用方法

要追蹤 Ticket 進度，輸入：

```text
/ticket-track <command> [options]
```

## 系統指令

你是一名 **Ticket 追蹤管理員**，負責管理 CSV 式 Ticket 追蹤系統。

當用戶要求追蹤 Ticket 進度時，使用以下腳本：

```bash
uv run .claude/hooks/ticket-tracker.py <command> [options]
```

## 可用命令

### 初始化版本

開始新版本開發時，初始化版本資料夾：

```bash
uv run .claude/hooks/ticket-tracker.py init v0.15.15
```

### 新增 Ticket

規劃 Ticket 後，新增到 CSV：

```bash
uv run .claude/hooks/ticket-tracker.py add \
  --id T-001 \
  --log "v0.15.15-ticket-001.md" \
  --who "parsley-flutter-developer" \
  --what "實作 BookRepository" \
  --when "Phase 3 開始時" \
  --where "lib/infrastructure/" \
  --why "需要持久化書籍資料" \
  --how "SQLite 儲存"
```

### 接手 Ticket（代理人使用）

代理人開始執行任務前接手：

```bash
uv run .claude/hooks/ticket-tracker.py claim T-001
```

### 完成 Ticket（代理人使用）

代理人完成任務後標記：

```bash
uv run .claude/hooks/ticket-tracker.py complete T-001
```

### 記錄學習收穫（完成時強制）

> 理論依據：Will Guidara《Unreasonable Hospitality》- 經驗傳承

完成 Ticket 時，必須記錄學習收穫：

```bash
uv run .claude/hooks/ticket-tracker.py complete T-001 \
  --learning "發現了 API 的隱藏限制，已更新 error-patterns"
```

如果未提供 `--learning` 參數，系統會提示：

```text
⚠️ 請提供學習收穫記錄（--learning 參數）
提示問題：
  - 這個任務我們學到了什麼？
  - 有沒有可以改進流程的地方？
  - 這個經驗可以應用在哪裡？
  - 是否需要建立 error-pattern？
```

### 放棄 Ticket（代理人使用）

代理人無法繼續執行時放棄：

```bash
uv run .claude/hooks/ticket-tracker.py release T-001
```

### 查詢單一 Ticket

查看特定 Ticket 的詳細資訊：

```bash
uv run .claude/hooks/ticket-tracker.py query T-001
```

### 列出 Tickets

```bash
# 列出所有 Tickets
uv run .claude/hooks/ticket-tracker.py list

# 只顯示進行中的 Tickets
uv run .claude/hooks/ticket-tracker.py list --in-progress

# 只顯示未接手的 Tickets
uv run .claude/hooks/ticket-tracker.py list --pending

# 只顯示已完成的 Tickets
uv run .claude/hooks/ticket-tracker.py list --completed
```

### 快速摘要

獲取當前版本的 Ticket 進度摘要：

```bash
# 自動偵測當前版本
uv run .claude/hooks/ticket-tracker.py summary

# 指定版本
uv run .claude/hooks/ticket-tracker.py summary --version v0.15.15
```

## 輸出格式說明

**狀態圖示**：
- `⏸️` - 未接手 (`assigned=false`)
- `🔄` - 進行中 (`assigned=true`, `completed=false`)
- `✅` - 已完成 (`completed=true`)

**摘要範例**：
```text
📊 Ticket 摘要 v0.15.15 (2/3 完成)
T-001 | ✅ | parsley | 實作 BookRepository
T-002 | 🔄 | sage | 撰寫測試 (已 1h30m)
T-003 | ⏸️ | pepper | 整合測試規劃
```

## 最佳實踐

### 主線程

1. **不要詢問代理人進度** - 直接使用 `summary` 命令查詢
2. **規劃階段批量建立 Tickets** - 方便全局追蹤
3. **定期執行 `summary`** - 快速了解進度

### 代理人

1. **開始前執行 `claim`** - 記錄開始時間
2. **完成後執行 `complete`** - 標記完成狀態
3. **不要回報進度給主線程** - 直接更新 CSV

## 相關文件

- **方法論**: `.claude/methodologies/frontmatter-ticket-tracking-methodology.md`
- **CSV 範本**: `.claude/templates/tickets.csv.template`
- **腳本**: `.claude/hooks/ticket-tracker.py`

## 版本資料夾結構

```text
docs/work-logs/
├── v0.15.15/
│   ├── tickets.csv              # Ticket 狀態追蹤
│   ├── v0.15.15-ticket-001.md   # Ticket 詳細日誌
│   ├── v0.15.15-ticket-002.md
│   └── v0.15.15-main.md         # 主版本日誌
└── ...
```
