# 技術債務 Ticket 範本

> 技術債務 Ticket 遵循 ticket Skill 的標準格式，額外包含技術債務特有欄位。
> 通用 Ticket 格式規範請見：`.claude/skills/ticket/references/create-command.md`

---

## Ticket ID 格式

```
{TargetVersion}-TD-{Seq:03d}
```

**範例**:

- `0.20.0-TD-001` - v0.20.0 的第一個技術債務
- `0.20.0-TD-004` - v0.20.0 的第四個技術債務

## Frontmatter 結構

技術債務 Ticket 包含特殊欄位 `ticket_type: "tech-debt"`:

```yaml
---
# === Identification ===
ticket_id: "0.20.0-TD-001"
ticket_type: "tech-debt"
version: "0.20.0"

# === Technical Debt Specific ===
source_version: "0.19.8"
source_uc: "UC-08"
risk_level: "low"  # high, medium, low, critical
original_id: "TD-001"

# === Single Responsibility ===
action: "Add"
target: "database index on book_tags.book_id"

# === Execution ===
agent: "parsley-flutter-developer"

# === 5W1H Design ===
who: "parsley-flutter-developer (執行者) | rosemary-project-manager (分派者)"
what: "在 book_tags 表格的 book_id 欄位新增資料庫索引"
when: "v0.20.x 開發期間"
where: "lib/infrastructure/database/migrations/"
why: "改善大量資料查詢效能"
how: "[Task Type: Implementation] 建立 SQLite 遷移腳本 -> 執行測試 -> 驗證索引生效"

# === Acceptance Criteria ===
acceptance:
  - 資料庫索引成功建立
  - 相關測試通過
  - 查詢效能改善驗證

# === Related Files ===
files:
  - lib/infrastructure/database/sqlite_book_repository.dart
  - test/integration/database_index_test.dart

# === Dependencies ===
dependencies: []

# === Status Tracking ===
status: "pending"
assigned: false
started_at: null
completed_at: null
---

# Execution Log

## Task Summary

在 book_tags 表格的 book_id 欄位新增資料庫索引

## Problem Analysis

<!-- To be filled by executing agent -->

## Solution

<!-- To be filled by executing agent -->

## Test Results

<!-- To be filled by executing agent -->

## Completion Info

**Completion Time**: (pending)
**Executing Agent**: parsley-flutter-developer
**Review Status**: pending
```

## 儲存位置

```
docs/work-logs/v{TargetVersion}/tickets/
```

**範例**:

```
docs/work-logs/v0.20.0/tickets/0.20.0-TD-001.md
docs/work-logs/v0.20.0/tickets/0.20.0-TD-002.md
```
