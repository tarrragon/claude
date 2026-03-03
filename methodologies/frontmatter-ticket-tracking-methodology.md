# Frontmatter 式 Ticket 追蹤方法論

## 方法論概述

本方法論定義基於 Markdown + YAML Frontmatter 的 Ticket 狀態追蹤系統，解決主線程與代理人之間的進度追蹤效率問題。

**核心目標**：

- 減少 context 佔用：透過直接讀取 frontmatter 取得狀態，避免代理人回報佔用主線程 context
- 單一文件架構：每個 Ticket 的設計、執行日誌、狀態追蹤都在同一個檔案中
- 獨立操作：主線程和代理人可以獨立查詢和更新狀態

**方法論版本**：v3.0.0（Frontmatter 版 - 單一文件架構）

**與其他方法論的關係**：

- 本方法論是「[Ticket 設計派工方法論](./ticket-design-dispatch-methodology.md)」的補充
- 取代舊版「[CSV 式 Ticket 追蹤方法論](./csv-ticket-tracking-methodology.md)」（v2.0.0）
- 與「[Atomic Ticket 方法論](./atomic-ticket-methodology.md)」配合使用

---

## 第一章：設計理念

### 1.1 單一文件架構的優勢

**從 CSV 到 Frontmatter 的演進**：

| 版本     | 架構                       | 問題                     |
| -------- | -------------------------- | ------------------------ |
| v1.0     | 獨立 YAML + 獨立 MD        | 檔案過多，維護困難       |
| v2.0     | CSV 追蹤 + MD 日誌         | 狀態分散在兩處，同步困難 |
| **v3.0** | **Markdown + Frontmatter** | **單一文件，一致性保證** |

**v3.0 的核心改進**：

```text
舊架構 (v2.0)：
├── tickets.csv          # 狀態追蹤
├── ticket-001.yaml      # 5W1H 設計
└── ticket-001.md        # 執行日誌

新架構 (v3.0)：
└── 0.16.0-W1-001.md     # 包含 frontmatter（設計+狀態）+ body（執行日誌）
```

**優勢**：

1. **一致性保證**：狀態和內容在同一檔案，不會不同步
2. **減少檔案數量**：每個 Ticket 只有一個檔案
3. **簡化工具鏈**：只需 frontmatter 解析器，無需 CSV 處理
4. **Git 友好**：每個 Ticket 的變更清楚可追蹤

### 1.2 架構圖

```text
主線程                    Ticket Frontmatter              代理人
   │                              │                          │
   │  查詢進度                    │                          │
   ├─────────────────────────────►│                          │
   │◄─────────────────────────────┤                          │
   │  （直接讀取 frontmatter）      │                          │
   │                              │                          │
   │                              │  更新狀態                 │
   │                              │◄─────────────────────────┤
   │                              │  （直接更新 frontmatter）  │
```

**核心原則**：

1. **Frontmatter 即狀態**：frontmatter 是唯一的狀態來源
2. **獨立操作**：查詢和更新不需要雙向溝通
3. **精簡輸出**：腳本輸出最小化，節省 context

---

## 第二章：資料結構設計

### 2.1 檔案位置和命名

**目錄結構**：

```text
docs/work-logs/
├── v0.16.0/                        # 版本資料夾
│   ├── tickets/                    # Ticket 檔案目錄
│   │   ├── 0.16.0-W1-001.md       # Ticket 檔案
│   │   ├── 0.16.0-W1-002.md
│   │   └── 0.16.0-W2-001.md
│   └── v0.16.0-main.md            # 主版本日誌
├── v0.15.16/                       # 舊版本（CSV 格式，唯讀）
│   ├── tickets.csv
│   └── ...
```

**命名規則**：

- 版本資料夾：`vX.Y.Z`
- Tickets 目錄：`tickets/`
- Ticket 檔案：`{VERSION}-W{WAVE}-{SEQ}.md`（例如：`0.16.0-W1-001.md`）

### 2.2 Frontmatter 欄位定義

**完整欄位列表**：

```yaml
---
# === 識別資訊 ===
ticket_id: "0.16.0-W1-001"
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
  - 0.16.0-W1-001

# === 狀態追蹤 ===
status: "pending"
assigned: false
started_at: null
completed_at: null
---
```

### 2.3 欄位分類說明

#### 識別欄位

| 欄位        | 類型   | 必填 | 說明                                    |
| ----------- | ------ | ---- | --------------------------------------- |
| `ticket_id` | string | 是   | 票號（格式：`{VERSION}-W{WAVE}-{SEQ}`） |
| `version`   | string | 是   | 版本號（例如：`0.16.0`）                |
| `wave`      | int    | 是   | Wave 編號（1, 2, 3...）                 |

#### 單一職責欄位

| 欄位     | 類型   | 必填 | 說明                                                  |
| -------- | ------ | ---- | ----------------------------------------------------- |
| `action` | string | 是   | 動詞（Implement, Fix, Add, Refactor, Remove, Update） |
| `target` | string | 是   | 單一目標（方法、類別、測試、檔案等）                  |

#### 執行資訊

| 欄位    | 類型   | 必填 | 說明                                            |
| ------- | ------ | ---- | ----------------------------------------------- |
| `agent` | string | 是   | 執行代理人（例如：`parsley-flutter-developer`） |

#### 5W1H 設計

| 欄位    | 類型   | 必填 | 說明     |
| ------- | ------ | ---- | -------- |
| `who`   | string | 是   | 執行者   |
| `what`  | string | 是   | 任務內容 |
| `when`  | string | 是   | 觸發時機 |
| `where` | string | 是   | 執行位置 |
| `why`   | string | 是   | 需求依據 |
| `how`   | string | 是   | 實作策略 |

#### 驗收與依賴

| 欄位           | 類型 | 必填 | 說明                  |
| -------------- | ---- | ---- | --------------------- |
| `acceptance`   | list | 否   | 驗收條件清單          |
| `files`        | list | 否   | 相關檔案清單          |
| `dependencies` | list | 否   | 依賴的 Ticket ID 清單 |

#### 狀態追蹤

| 欄位           | 類型     | 必填 | 說明                                    |
| -------------- | -------- | ---- | --------------------------------------- |
| `status`       | string   | 是   | 狀態（pending, in_progress, completed） |
| `assigned`     | boolean  | 是   | 是否有人接手                            |
| `started_at`   | datetime | 否   | 開始時間（ISO 8601）                    |
| `completed_at` | datetime | 否   | 完成時間（ISO 8601）                    |

---

## 第三章：操作流程

### 3.1 建立 Ticket

**時機**：PM 規劃 Ticket 後

**使用腳本**：

```bash
uv run ticket create \
  --version "0.16.0" \
  --wave 1 \
  --action "Implement" \
  --target "startScan() method" \
  --who "parsley-flutter-developer"
```

**結果**：

- 建立 `docs/work-logs/v0.16.0/tickets/0.16.0-W1-001.md`
- frontmatter 包含 5W1H 設計和初始狀態
- body 包含執行日誌模板

### 3.2 接手 Ticket（代理人）

**時機**：代理人開始執行 Ticket

**使用腳本**：

```bash
uv run ticket track claim 0.16.0-W1-001
```

**Frontmatter 更新**：

- `assigned: true`
- `started_at: [當前時間]`
- `status: "in_progress"`

### 3.3 完成 Ticket（代理人）

**時機**：代理人完成 Ticket

**使用腳本**：

```bash
uv run ticket track complete 0.16.0-W1-001
```

**Frontmatter 更新**：

- `status: "completed"`
- `completed_at: [當前時間]`

### 3.4 放棄 Ticket（代理人）

**時機**：代理人無法繼續執行

**使用腳本**：

```bash
uv run ticket track release 0.16.0-W1-001
```

**Frontmatter 更新**：

- `assigned: false`
- `started_at: null`
- `status: "pending"`

### 3.5 查詢進度（主線程）

**單一 Ticket**：

```bash
uv run ticket track query 0.16.0-W1-001
```

**列出所有**：

```bash
# 進行中的 Tickets
uv run ticket track list --in-progress

# 未接手的 Tickets
uv run ticket track list --pending

# 已完成的 Tickets
uv run ticket track list --completed
```

**快速摘要**：

```bash
uv run ticket track summary
```

**輸出範例**：

```text
📊 Ticket 摘要 v0.16.0 (2/5 完成) [markdown]
----------------------------------------------------------------------------------------------------
0.16.0-W1-001 | ✅ | parsley         | Implement startScan() method
0.16.0-W1-002 | 🔄 | parsley         | Implement stopScan() method (已 1h30m)
0.16.0-W1-003 | ⏸️ | parsley         | Implement scan result handling
0.16.0-W2-001 | ⏸️ | sage            | Add ScannerService unit tests
0.16.0-W2-002 | ⏸️ | thyme           | Update scanner documentation
```

---

## 第四章：向後相容性

### 4.1 舊版本 CSV 格式支援（唯讀）

**自動偵測機制**：

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

**唯讀模式限制**：

| 操作       | v0.16.0+ (Markdown) | v0.15.x (CSV) |
| ---------- | ------------------- | ------------- |
| `summary`  | ✅ 完整支援         | ✅ 唯讀       |
| `list`     | ✅ 完整支援         | ✅ 唯讀       |
| `query`    | ✅ 完整支援         | ⚠️ 有限       |
| `claim`    | ✅ 完整支援         | ❌ 不支援     |
| `complete` | ✅ 完整支援         | ❌ 不支援     |
| `release`  | ✅ 完整支援         | ❌ 不支援     |

### 4.2 舊版本查詢範例

```bash
uv run ticket track summary --version v0.15.16
```

**輸出**：

```text
⚠️  v0.15.16 使用舊版 CSV 格式（唯讀模式）
   狀態更新命令（claim/complete/release）在 v0.15.x 版本不支援
   請升級到 v0.16.0+ 以使用新的 Markdown Ticket 系統

📊 Ticket 摘要 v0.15.16 (15/34 完成) [csv]
----------------------------------------------------------------------------------------------------
...
```

---

## 第五章：與現有機制的整合

### 5.1 與三重文件原則的整合

**三重文件 + Frontmatter 的關係**：

```text
CHANGELOG.md         ← 版本發布時提取功能變動
    ↑
todolist.yaml          ← 任務狀態追蹤（粗粒度）
    ↑
tickets/*.md         ← Ticket 狀態追蹤（細粒度） ★ 本方法論
    ↑
work-log/*.md        ← 詳細實作記錄
```

### 5.2 與 5W1H 框架的整合

**Frontmatter 完整涵蓋 5W1H**：

```yaml
who: "parsley-flutter-developer" # 誰執行
what: "Implement startScan() method" # 做什麼
when: "Phase 3 start" # 什麼時候
where: "lib/infrastructure/" # 在哪裡
why: "Enable barcode scanning" # 為什麼
how: "Use mobile_scanner package" # 怎麼做
```

### 5.3 生命週期狀態對應

| Ticket 生命週期 | Frontmatter 狀態                            |
| --------------- | ------------------------------------------- |
| Draft           | 未建立檔案                                  |
| Ready           | `status: "pending"`, `assigned: false`      |
| In Progress     | `status: "in_progress"`, `assigned: true`   |
| Review          | `status: "in_progress"`（日誌標記 Review）  |
| Closed          | `status: "completed"`                       |
| Blocked         | `status: "in_progress"`（日誌標記 Blocked） |

---

## 第六章：最佳實踐

### 6.1 主線程最佳實踐

**定期檢查進度**：

```bash
# 每次需要了解進度時執行
uv run ticket track summary
```

**不要詢問代理人進度**：

- ❌ 錯誤：「代理人，0.16.0-W1-001 完成了嗎？」
- ✅ 正確：直接執行 `summary` 或 `query` 命令

### 6.2 代理人最佳實踐

**開始前接手**：

```bash
# 開始執行任務前先接手
uv run ticket track claim 0.16.0-W1-001
```

**完成後標記**：

```bash
# 完成後立即標記
uv run ticket track complete 0.16.0-W1-001
```

**不要回報進度給主線程**：

- ❌ 錯誤：「我已經完成 0.16.0-W1-001，以下是詳細報告...」
- ✅ 正確：標記完成，詳細記錄到 Ticket 的執行日誌區段

### 6.3 執行日誌撰寫

**每個 Ticket 的 body 區段用於記錄**：

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

## 第七章：工具參考

### 7.1 腳本命令速查

| 命令                   | 用途                 | 使用者 |
| ---------------------- | -------------------- | ------ |
| `create`               | 建立新 Ticket        | 主線程 |
| `list`                 | 列出所有 Tickets     | 主線程 |
| `show`                 | 顯示 Ticket 詳細資訊 | 主線程 |
| `claim <ticket_id>`    | 接手 Ticket          | 代理人 |
| `complete <ticket_id>` | 標記完成             | 代理人 |
| `release <ticket_id>`  | 放棄 Ticket          | 代理人 |
| `query <ticket_id>`    | 查詢單一 Ticket      | 主線程 |
| `summary`              | 快速摘要             | 主線程 |

### 7.2 狀態圖示說明

| 圖示 | 狀態        | 說明                    |
| ---- | ----------- | ----------------------- |
| ⏸️   | Pending     | `status: "pending"`     |
| 🔄   | In Progress | `status: "in_progress"` |
| ✅   | Completed   | `status: "completed"`   |

### 7.3 相關檔案

| 檔案                                    | 用途                 |
| --------------------------------------- | -------------------- |
| `.claude/hooks/ticket-creator.py`       | Ticket 建立腳本      |
| `.claude/hooks/ticket tracker.py`       | 狀態追蹤腳本         |
| `.claude/hooks/frontmatter_parser.py`   | Frontmatter 解析模組 |
| `.claude/templates/ticket.md.template`  | Ticket 檔案模板      |
| `.claude/skills/ticket create/SKILL.md` | Skill 定義           |
| `.claude/skills/ticket track/SKILL.md`  | Skill 定義           |

---

## 方法論總結

### 核心價值

本方法論透過 Frontmatter 式追蹤解決以下問題：

1. **單一文件架構** - 設計、狀態、日誌都在同一檔案
2. **減少 Context 佔用** - 腳本輸出精簡，不佔用對話空間
3. **提升追蹤效率** - 直接讀取 frontmatter，無需等待回應
4. **獨立操作** - 主線程和代理人可以獨立查詢和更新
5. **向後相容** - 可唯讀查詢舊版本 CSV 格式

### 適用場景

- 多代理人並行執行任務
- 需要頻繁追蹤進度的版本開發
- 主線程需要專注於統籌而非追蹤
- 需要完整保留 Ticket 設計和執行歷史

### 版本演進

| 版本     | 架構                       | 狀態                     |
| -------- | -------------------------- | ------------------------ |
| v1.0     | YAML + MD 分離             | 已棄用                   |
| v2.0     | CSV + MD 分離              | 已棄用（v0.15.x）        |
| **v3.0** | **Markdown + Frontmatter** | **當前版本（v0.16.0+）** |

---

**文件結束**
