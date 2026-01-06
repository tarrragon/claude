---
name: tech-debt-capture
description: "Automated Phase 4 technical debt capture and Ticket creation. Parses work-log evaluation reports, extracts TD (Technical Debt) items, and creates Atomic Tickets using Single Responsibility Principle. Use: Extract technical debts from Phase 4 evaluation → Auto-map to target versions → Create tickets → Update todolist."
---

# Tech Debt Capture

Automated technical debt capture from Phase 4 evaluation reports and conversion to Atomic Tickets.

## 核心功能

**目的**: 將 Phase 4 重構評估識別的技術債務自動轉換為可執行的 Ticket

**工作流程**:
1. 解析工作日誌中的技術債務表格
2. 根據風險等級決定目標版本
3. 建立 Atomic Ticket 檔案
4. 更新 todolist.md 技術債務追蹤區塊

## 技術債務定義

**來源**: Phase 4 最終重構評估報告
**格式**: Markdown 表格

```markdown
| ID | 描述 | 風險等級 | 建議處理時機 |
|----|------|---------|------------|
| TD-001 | 描述 | 低 | 處理時機 |
```

**風險等級分類**:
- **高 (High)**: 可能影響使用者體驗或效能的重大問題
- **中 (Medium)**: 影響維護成本但不嚴重的問題
- **低 (Low)**: 程式碼品質或架構改進
- **極低 (Critical)**: 非功能性風格問題

## 版本對應規則

本 Skill 遵循 **UC-Oriented 開發** 原則，決定技術債務的目標版本：

### 版本推進規則 (UC-Oriented)

| 風險等級 | 版本規則 | 範例 |
|---------|--------|------|
| **高** | 當前 UC 完成後的版本 | UC-08 v0.19.8 的高風險 TD → v0.20.0 (UC-09) |
| **中** | 當前 UC 完成後的版本 | UC-08 v0.19.8 的中風險 TD → v0.20.0 (UC-09) |
| **低** | 當前 UC 版本系列的後續小版本 | UC-08 的低風險 TD → v0.20.x 或更後 |
| **極低** | 可選改進，不強制排期 | TD-003 可選清理 |

**決策邏輯**:

```
1. 判斷技術債務來自哪個 UC 版本系列
   Example: v0.19.8 = UC-08

2. 根據風險等級選擇目標版本
   ├─ 高/中 → 下一個 UC (v0.20.x)
   └─ 低/極低 → 當前 UC 版本系列或後續版本

3. 如果未指定 --target-version，自動推導
```

### 實際案例

**v0.19.8 Phase 4 技術債務**:

| 原始 ID | 描述 | 風險 | 當前 UC | 目標版本 | 新 Ticket ID |
|--------|------|------|--------|---------|------------|
| TD-001 | book_tags 索引缺失 | 低 | UC-08 (v0.19) | v0.20.x | 0.20.0-TD-001 |
| TD-002 | 錯誤處理邏輯重複 | 低 | UC-08 (v0.19) | 可選 | 0.20.0-TD-002 |
| TD-003 | Linter 警告 | 極低 | UC-08 (v0.19) | 可選 | 0.20.0-TD-003 |
| TD-004 | Service 整合缺失 | 中 | UC-08 (v0.19) | v0.20.0 | 0.20.0-TD-004 |

## Ticket 建立規則

### Ticket ID 格式

```
{TargetVersion}-TD-{Seq:03d}
```

**範例**:
- `0.20.0-TD-001` - v0.20.0 的第一個技術債務
- `0.20.0-TD-004` - v0.20.0 的第四個技術債務

### Frontmatter 結構

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
how: "[Task Type: Implementation] 建立 SQLite 遷移腳本 → 執行測試 → 驗證索引生效"

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

### 儲存位置

```
docs/work-logs/v{TargetVersion}/tickets/
```

**範例**:
```
docs/work-logs/v0.20.0/tickets/0.20.0-TD-001.md
docs/work-logs/v0.20.0/tickets/0.20.0-TD-002.md
docs/work-logs/v0.20.0/tickets/0.20.0-TD-003.md
docs/work-logs/v0.20.0/tickets/0.20.0-TD-004.md
```

## TodoList 更新規則

在 `docs/todolist.md` 末尾新增或更新技術債務追蹤區塊：

```markdown
## 技術債務追蹤

| Ticket ID | 描述 | 來源版本 | 目標版本 | 風險 | 狀態 |
|-----------|------|---------|--------|------|------|
| 0.20.0-TD-001 | 新增 book_tags.book_id 索引 | v0.19.8 | v0.20.0 | 低 | pending |
| 0.20.0-TD-002 | 抽取共用錯誤處理邏輯 | v0.19.8 | v0.20.0 | 低 | pending |
| 0.20.0-TD-003 | 清理 linter 警告 | v0.19.8 | 可選 | 極低 | pending |
| 0.20.0-TD-004 | 整合 BackgroundProcessingService | v0.19.8 | v0.20.0 | 中 | pending |
```

## 使用方式

### 互動模式（推薦）

```bash
/tech-debt-capture
```

引導式交互，逐步收集資訊：
1. 選擇要解析的工作日誌檔案
2. 確認技術債務清單
3. 確認目標版本對應
4. 建立 Ticket 並更新 todolist

### 批量模式

```bash
uv run .claude/skills/tech-debt-capture/scripts/tech_debt_capturer.py capture \
    docs/work-logs/v0.19.8-phase4-final-evaluation.md
```

**輸出**:
```
📋 解析工作日誌
  ✅ 找到 4 個技術債務項目

📊 版本對應決策
  TD-001 (低) → 0.20.0
  TD-002 (低) → 0.20.0
  TD-003 (極低) → 0.20.0 (可選)
  TD-004 (中) → 0.20.0

📝 建立 Ticket 檔案
  ✅ docs/work-logs/v0.20.0/tickets/0.20.0-TD-001.md
  ✅ docs/work-logs/v0.20.0/tickets/0.20.0-TD-002.md
  ✅ docs/work-logs/v0.20.0/tickets/0.20.0-TD-003.md
  ✅ docs/work-logs/v0.20.0/tickets/0.20.0-TD-004.md

📝 更新 todolist.md
  ✅ 技術債務追蹤區塊已更新

✅ 完成！共建立 4 個技術債務 Ticket
```

### 指定目標版本

```bash
uv run .claude/skills/tech-debt-capture/scripts/tech_debt_capturer.py capture \
    docs/work-logs/v0.19.8-phase4-final-evaluation.md \
    --target-version 0.20.0
```

### 預覽模式

```bash
uv run .claude/skills/tech-debt-capture/scripts/tech_debt_capturer.py capture \
    docs/work-logs/v0.19.8-phase4-final-evaluation.md \
    --dry-run
```

預覽所有將建立的 Ticket，但不實際建立檔案：

```
📋 預覽模式 - 不會建立實際檔案

📝 將建立以下 Ticket:
  1. 0.20.0-TD-001 - 新增 book_tags.book_id 索引 (低)
  2. 0.20.0-TD-002 - 抽取共用錯誤處理邏輯 (低)
  3. 0.20.0-TD-003 - 清理 linter 警告 (極低)
  4. 0.20.0-TD-004 - 整合 BackgroundProcessingService (中)

✅ 預覽完成。執行不含 --dry-run 參數建立 Ticket
```

### 初始化版本目錄

```bash
uv run .claude/skills/tech-debt-capture/scripts/tech_debt_capturer.py init 0.20.0
```

建立版本目錄和 tickets 子目錄：

```
docs/work-logs/v0.20.0/
├── tickets/
├── v0.20.0-phase1-design.md
├── v0.20.0-phase2-test-design.md
├── v0.20.0-phase3a-strategy.md
└── (其他 Phase 工作日誌)
```

### 列出技術債務

```bash
uv run .claude/skills/tech-debt-capture/scripts/tech_debt_capturer.py list \
    --version 0.20.0
```

列出版本中的所有技術債務 Ticket：

```
📋 v0.20.0 技術債務清單

Ticket ID         | 描述                      | 風險  | 來源版本 | 狀態
------------------|-------------------------|-------|---------|-------
0.20.0-TD-001     | 新增 book_tags 索引 | 低   | v0.19.8 | pending
0.20.0-TD-002     | 抽取錯誤處理邏輯        | 低   | v0.19.8 | pending
0.20.0-TD-003     | 清理 linter 警告       | 極低 | v0.19.8 | pending
0.20.0-TD-004     | 整合 Service           | 中   | v0.19.8 | pending
```

## 功能特性

### 1. 智慧解析

- **Markdown 表格辨識**: 自動解析 Phase 4 工作日誌中的技術債務表格
- **欄位提取**: 智慧判斷 ID、描述、風險等級、建議處理時機
- **錯誤容忍**: 處理不完全或格式變化的表格

### 2. 版本決策引擎

- **UC-Oriented 版本推導**: 自動判斷來源 UC 版本
- **風險等級對應**: 高/中→當前 UC 下一版本，低→當前版本系列
- **手動覆蓋**: 支援 `--target-version` 明確指定版本

### 3. Atomic Ticket 產生

- **單一職責設計**: 每個技術債務自動轉換為一個 Atomic Ticket
- **完整 5W1H**: 自動填充基本的 5W1H 資訊
- **Frontmatter 格式**: 遵循 v3.0 Ticket 格式規範

### 4. 文件更新

- **todolist.md 整合**: 自動新增或更新技術債務追蹤區塊
- **目錄建立**: 自動建立版本目錄和 tickets 子目錄
- **驗證檢查**: 確保檔案位置正確且無重複

## 錯誤處理

### 常見問題

| 問題 | 原因 | 解決方式 |
|------|------|---------|
| 找不到工作日誌檔案 | 檔案路徑錯誤 | 確認檔案路徑和名稱 |
| 表格格式不符 | 日誌編輯後格式變化 | 檢查表格欄位名稱 |
| 版本目錄已存在 | 多次執行 | 使用 --force-overwrite 覆蓋 |
| Ticket 檔案衝突 | 已有相同 ID 的 Ticket | 查看現有 Ticket 或變更版本 |

### 修復指引

**問題**: `FileNotFoundError: docs/work-logs/v0.19.8-phase4.md`

```bash
# 1. 確認工作日誌檔案路徑
ls docs/work-logs/v0.19.8*

# 2. 使用正確的檔案名稱
uv run .claude/skills/tech-debt-capture/scripts/tech_debt_capturer.py capture \
    docs/work-logs/v0.19.8-phase4-final-evaluation.md
```

**問題**: `ValueError: 無法解析技術債務表格`

```bash
# 1. 檢查表格格式（應包含 ID, 描述, 風險等級, 建議處理時機 欄位）
# 2. 若表格名稱不同，檢查工作日誌內容
# 3. 使用 --dry-run 預覽解析結果
```

## 相關工具和指令

### 前置條件

- `python3.10+`
- `pyyaml` 套件（UV 自動安裝）
- 完成 Phase 4 重構評估報告

### 相關 Skills

- `/ticket-create` - 手動建立 Atomic Ticket
- `/ticket-track` - 追蹤和更新 Ticket 狀態

### 相關文件

- `docs/todolist.md` - 整體開發計畫和技術債務追蹤
- `.claude/methodologies/atomic-ticket-methodology.md` - 單一職責原則
- `.claude/methodologies/frontmatter-ticket-tracking-methodology.md` - Ticket 狀態追蹤
- 具體工作日誌範例: `docs/work-logs/v0.19.8-phase4-final-evaluation.md`

## Skill 開發參考

**版本**: v1.0
**建立日期**: 2026-01-06
**執行引擎**: Python 3.10+ with PEP 723 UV Single-File
**適用場景**: Phase 4 重構評估完成後的技術債務建立
**維護責任**: basil-hook-architect
