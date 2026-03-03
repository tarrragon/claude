# 技術債務提醒 Hook - 快速參考卡片

## 一句話概述

在 Session 啟動時自動檢查當前版本是否有待處理的技術債務，並顯示警告訊息。

## 檔案位置

```
.claude/hooks/tech-debt-reminder.py        ← Hook 腳本 (13 KB, 484 行)
.claude/references/hooks/TECH-DEBT-REMINDER-USAGE.md  ← 完整使用指南 (5 頁)
.claude/hook-logs/tech-debt-reminder/      ← 日誌和報告目錄
```

## 工作流程

```
Session 啟動
    ↓
讀取 pubspec.yaml 版本號 (e.g. 0.20.5)
    ↓
解析版本系列 (e.g. v0.20.x)
    ↓
定位 docs/work-logs/v0.20.0/tickets/
    ↓
掃描所有 .md 檔案，找出 TD Tickets
    ↓
過濾 status: pending 的項目
    ↓
若有 pending TD → 顯示警告訊息
否則 → 靜默執行，無輸出
```

## 輸出範例

### 有待處理 TD

```
⚠️ 技術債務提醒

當前版本 v0.20.x 有 4 個待處理技術債務：

  1. 0.20.0-TD-001: `book_tags.book_id` 缺少資料庫索引 (風險等級: low)
  2. 0.20.0-TD-002: `loadInitial` 和 `loadMore` 錯誤處理邏輯可 (風險等級: low)
  3. 0.20.0-TD-003: 8 個 info 級別 linter 警告 (風險等級: critical)
  4. 0.20.0-TD-004: `BackgroundProcessingService` 尚未到 Repository (風險等級: medium)

建議：
  1. 在開始新功能開發前處理這些技術債務
  2. 或使用 /ticket track 將目標版本延後
  3. 查看詳細 Ticket: docs/work-logs/v*/tickets/
```

### 無待處理 TD

```
(無輸出，靜默執行)
```

## 技術規格

| 項目 | 值 |
|------|-----|
| **Hook 類型** | SessionStart |
| **語言** | Python 3.10+ |
| **依賴** | pyyaml >= 6.0 |
| **執行模式** | PEP 723 UV Single-File |
| **Timeout** | 30s |
| **執行時間** | 100-150ms |
| **記憶體** | < 5MB |

## 配置

在 `.claude/settings.local.json` 中自動配置：

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/tech-debt-reminder.py",
            "timeout": 30000
          }
        ]
      }
    ]
  }
}
```

## 快速命令

### 查看執行日誌
```bash
tail -f .claude/hook-logs/tech-debt-reminder/tech-debt-reminder.log
```

### 手動測試
```bash
# 基本測試
echo '{"session_id":"test"}' | uv run .claude/hooks/tech-debt-reminder.py

# 啟用詳細日誌
HOOK_DEBUG=true echo '{}' | uv run .claude/hooks/tech-debt-reminder.py
```

### 檢視文件
```bash
# 完整使用指南
cat .claude/references/hooks/TECH-DEBT-REMINDER-USAGE.md

# 測試報告
cat .claude/hook-logs/tech-debt-reminder/TEST-REPORT.md

# 部署總結
cat .claude/references/hooks/README-TECH-DEBT-REMINDER.md
```

## Ticket Frontmatter 格式

Hook 會掃描符合以下條件的 Markdown 檔案：

```yaml
---
ticket_id: 0.20.0-TD-001
ticket_type: "tech-debt"         # ← 必須
status: pending                  # ← 必須
risk_level: low|medium|high|critical
target: "描述"
version: 0.21.0
---
```

**掃描位置**: `docs/work-logs/v{major}.{minor}.0/tickets/`

## 常見問題

### Q1: 如何禁用此 Hook？
編輯 `.claude/settings.local.json`，移除 SessionStart 配置即可。

### Q2: 為什麼有些版本沒有顯示？
該版本的 `v{major}.{minor}.0/tickets/` 目錄不存在，或無 pending TD。

### Q3: 如何只針對特定版本檢查？
目前 Hook 自動基於當前版本檢查。可編輯 Hook 腳本來自訂邏輯。

### Q4: 性能是否會影響 Session 啟動？
執行時間 < 150ms，完全不影響（Session 啟動通常花費秒級時間）。

### Q5: 如何除錯 Hook 執行？
設定環境變數: `HOOK_DEBUG=true` 並檢視日誌。

## 測試結果

**評分**: ⭐⭐⭐⭐⭐ (5/5)

- ✅ 功能測試 (4/4 通過)
- ✅ 邊界條件 (3/3 通過)
- ✅ 語法檢查 (通過)
- ✅ 配置驗證 (通過)
- ✅ 效能測試 (通過)

## 相關資源

- **完整指南**: [TECH-DEBT-REMINDER-USAGE.md](./TECH-DEBT-REMINDER-USAGE.md)
- **部署總結**: [README-TECH-DEBT-REMINDER.md](./README-TECH-DEBT-REMINDER.md)
- **測試報告**: [TEST-REPORT.md](./../hook-logs/tech-debt-reminder/TEST-REPORT.md)

## 狀態

✅ 已部署
✅ 即時可用
✅ 無需額外配置

---

建立日期: 2026-01-07
版本: v1.0
