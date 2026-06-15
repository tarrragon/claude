# Frontmatter 式 Ticket 追蹤：操作參考

> **用途**：本檔為 `.claude/methodologies/frontmatter-ticket-tracking-methodology.md` 的衛星參考檔，存放逐字 bash 命令範例、frontmatter 完整 YAML 範例、執行日誌完整範本、工具速查表，以及 v0.15.x 舊版 CSV 格式的向後相容處理。需要複製可執行命令、查詢舊版 CSV 格式、或對照完整範本時按需讀取。
>
> **核心方法論（單一文件架構 + 欄位定義 + 操作流程概念 + 整合 + 最佳實踐）**：`.claude/methodologies/frontmatter-ticket-tracking-methodology.md`（需回顧設計理念、frontmatter 欄位 schema 或生命週期狀態對應時讀）

---

## Frontmatter 完整範例

完整欄位列表（含分組註解），對照主檔第二章欄位定義表使用：

```yaml
---
# === 識別資訊 ===
ticket_id: "{version}-W{n}-001"
version: "0.16.0"
wave: 1

# === 單一職責定義 ===
action: "Implement"
target: "startScan() method"

# === 執行資訊 ===
agent: "parsley-flutter-developer"

# === 5W1H 設計 ===
who: "parsley-flutter-developer"
what: "Implement startScan() method"
when: "Phase 3 start"
where: "lib/infrastructure/"
why: "Enable barcode scanning"
how: "Use mobile_scanner package"

# === 驗收條件 ===
acceptance:
  - Task implementation complete
  - Related tests pass
  - No code quality warnings

# === 相關檔案 ===
files:
  - lib/infrastructure/scanner_service.dart

# === 依賴 ===
dependencies:
  - {version}-W{n}-001

# === 狀態追蹤 ===
status: "pending"
assigned: false
started_at: null
completed_at: null
---
```

---

## 命令範例

對照主檔第三章操作流程表使用，本節提供逐字 bash 命令與輸出範例。

### 建立 Ticket（主線程）

```bash
uv run ticket create \
  --version "0.16.0" \
  --wave 1 \
  --action "Implement" \
  --target "startScan() method" \
  --who "parsley-flutter-developer"
```

結果：

- 建立 `docs/work-logs/v{major}/v{major}.{minor}/v{version}/tickets/{version}-W{n}-001.md`（例：`docs/work-logs/v0/v0.16/v0.16.0/tickets/0.16.0-W{n}-001.md`）
- frontmatter 包含 5W1H 設計和初始狀態
- body 包含執行日誌模板

### 接手 Ticket（代理人）

```bash
uv run ticket track claim {version}-W{n}-001
```

Frontmatter 更新：`assigned: true`、`started_at: [當前時間]`、`status: "in_progress"`

### 完成 Ticket（代理人）

```bash
uv run ticket track complete {version}-W{n}-001
```

Frontmatter 更新：`status: "completed"`、`completed_at: [當前時間]`

### 放棄 Ticket（代理人）

```bash
uv run ticket track release {version}-W{n}-001
```

Frontmatter 更新：`assigned: false`、`started_at: null`、`status: "pending"`

### 查詢進度（主線程）

```bash
# 單一 Ticket
uv run ticket track query {version}-W{n}-001

# 列出篩選清單
uv run ticket track list --in-progress
uv run ticket track list --pending
uv run ticket track list --completed

# 版本層快速摘要
uv run ticket track summary
```

`summary` 輸出範例：

```text
Ticket 摘要 v0.16.0 (2/5 完成) [markdown]
----------------------------------------------------------------------------------------------------
{version}-W{n}-001 | [Completed]   | parsley | Implement startScan() method
{version}-W{n}-002 | [In Progress] | parsley | Implement stopScan() method (已 1h30m)
{version}-W{n}-003 | [Pending]     | parsley | Implement scan result handling
{version}-W{n+1}-001 | [Pending]   | sage    | Add ScannerService unit tests
{version}-W{n+1}-002 | [Pending]   | thyme   | Update scanner documentation
```

---

## 執行日誌完整範本

對照主檔第五章 5.3 節使用，每個 Ticket 的 body 區段按以下五面向結構撰寫：

```markdown
# 執行日誌

## 任務摘要

Implement startScan() method for barcode scanning feature.

---

## 問題分析

1. 需要整合 mobile_scanner 套件
2. 需要處理相機權限請求
3. 需要處理掃描結果回調

---

## 解決方案

1. 使用 MobileScanner widget 包裝掃描功能
2. 在 AndroidManifest.xml 和 Info.plist 添加相機權限
3. 實作 onDetect callback 處理掃描結果

---

## 測試結果

- [x] Unit tests passed
- [x] Integration tests passed
- [x] Manual testing on Android device

---

## 完成資訊

**完成時間**: 2025-12-27T12:30:00
**執行代理人**: parsley-flutter-developer
**Review 狀態**: Approved
```

---

## 向後相容性：v0.15.x 舊版 CSV 格式

### 自動偵測機制

舊版本 `v0.15.x` 使用 CSV 格式（唯讀），系統依以下流程自動偵測格式：

```text
查詢版本
    │
    ▼
是否存在 tickets/ 目錄且包含 .md 檔案？
    │
    ├── 是 → 使用 Markdown 格式（完整功能）
    │
    └── 否 → 是否存在 tickets.csv？
              │
              ├── 是 → 使用 CSV 格式（唯讀模式）
              │
              └── 否 → 無 Tickets
```

### 唯讀模式限制

| 操作 | v0.16.0+ (Markdown) | v0.15.x (CSV) |
| ---- | ------------------- | ------------- |
| `summary` | 完整支援 | 唯讀 |
| `list` | 完整支援 | 唯讀 |
| `query` | 完整支援 | 有限 |
| `claim` | 完整支援 | 不支援 |
| `complete` | 完整支援 | 不支援 |
| `release` | 完整支援 | 不支援 |

### 舊版本查詢範例

```bash
uv run ticket track summary --version v0.15.16
```

輸出：

```text
[WARNING] v0.15.16 使用舊版 CSV 格式（唯讀模式）
   狀態更新命令（claim/complete/release）在 v0.15.x 版本不支援
   請升級到 v0.16.0+ 以使用新的 Markdown Ticket 系統

Ticket 摘要 v0.15.16 (15/34 完成) [csv]
----------------------------------------------------------------------------------------------------
...
```

---

## 工具參考

### 腳本命令速查

| 命令 | 用途 | 使用者 |
| ---- | ---- | ------ |
| `create` | 建立新 Ticket | 主線程 |
| `list` | 列出所有 Tickets | 主線程 |
| `show` | 顯示 Ticket 詳細資訊 | 主線程 |
| `claim <ticket_id>` | 接手 Ticket | 代理人 |
| `complete <ticket_id>` | 標記完成 | 代理人 |
| `release <ticket_id>` | 放棄 Ticket | 代理人 |
| `query <ticket_id>` | 查詢單一 Ticket | 主線程 |
| `summary` | 快速摘要 | 主線程 |

### 狀態標記說明

| 標記 | 狀態 | frontmatter 值 |
| ---- | ---- | -------------- |
| `[Pending]` | Pending | `status: "pending"` |
| `[In Progress]` | In Progress | `status: "in_progress"` |
| `[Completed]` | Completed | `status: "completed"` |

### 相關檔案

| 檔案 | 用途 |
| ---- | ---- |
| `.claude/skills/ticket/SKILL.md` | Ticket 系統 Skill 入口（create / track / handoff / resume / migrate / generate） |
| `.claude/skills/ticket/ticket_system/` | live CLI Python 套件（透過 `uv tool install` 安裝為 `ticket` 命令） |
| `.claude/skills/ticket/ticket_system/lib/ticket_builder.py` | Ticket body 與 frontmatter code-gen（不讀 `.template` 檔） |

---

**文件結束**
