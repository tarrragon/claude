# Frontmatter 式 Ticket 追蹤方法論

> **30 秒核心**：每個 Ticket 用單一 Markdown 檔（frontmatter 存設計 + 狀態，body 存執行日誌），frontmatter 即唯一狀態來源；主線程與代理人各自直接讀寫 frontmatter，無需雙向回報。
>
> **完整命令範例 / 執行日誌範本 / 工具速查 / 舊版 CSV 相容（衛星檔）**：`.claude/references/frontmatter-ticket-tracking-operations.md`（需要逐字 bash 命令、執行日誌完整範本、命令速查表、或查詢 v0.15.x 舊版 CSV 格式時讀）

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

### 1.1 單一文件架構的演進與優勢

| 版本 | 架構 | 問題 |
| ---- | ---- | ---- |
| v1.0 | 獨立 YAML + 獨立 MD | 檔案過多，維護困難 |
| v2.0 | CSV 追蹤 + MD 日誌 | 狀態分散在兩處，同步困難 |
| **v3.0** | **Markdown + Frontmatter** | **單一文件，一致性保證** |

v3.0 將「狀態追蹤 + 5W1H 設計 + 執行日誌」三者合併到單一 `{version}-W{n}-001.md` 檔（frontmatter 存設計與狀態，body 存執行日誌），帶來四項改進：

1. **一致性保證**：狀態和內容在同一檔案，不會不同步
2. **減少檔案數量**：每個 Ticket 只有一個檔案
3. **簡化工具鏈**：只需 frontmatter 解析器，無需 CSV 處理
4. **Git 友好**：每個 Ticket 的變更清楚可追蹤

### 1.2 三條核心原則

主線程與代理人對同一 Ticket frontmatter 進行單向讀寫（主線程查詢、代理人更新），不需雙向溝通，由此導出三條原則：

1. **Frontmatter 即狀態**：frontmatter 是唯一的狀態來源
2. **獨立操作**：查詢和更新不需要雙向溝通
3. **精簡輸出**：腳本輸出最小化，節省 context

---

## 第二章：資料結構設計

### 2.1 檔案位置和命名

Ticket 檔案依三層版本結構存放（`major / minor / patch`），命名規則固定為 `{VERSION}-W{WAVE}-{SEQ}.md`：

```text
docs/work-logs/
└── v0/                              # major 版本 group
    └── v0.18/                       # minor 版本 group
        └── v0.18.0/                 # patch 版本資料夾
            ├── tickets/             # Ticket 檔案目錄
            │   └── 0.18.0-W17-001.md
            └── v0.18.0-main.md      # 主版本日誌
```

- 版本資料夾：`vX.Y.Z`
- Tickets 目錄：`tickets/`
- Ticket 檔案：`{VERSION}-W{WAVE}-{SEQ}.md`（例：`0.18.0-W17-001.md`）
- 舊版本 `v0.15.x` 為 CSV 格式（唯讀，未轉三層結構），相容處理見衛星檔

### 2.2 Frontmatter 欄位定義

frontmatter 是 Ticket 的設計與狀態 schema，分為識別、職責、5W1H、驗收依賴、狀態追蹤五組。各欄位的型別與必填要求：

#### 識別欄位

| 欄位 | 類型 | 必填 | 說明 |
| ---- | ---- | ---- | ---- |
| `ticket_id` | string | 是 | 票號（格式：`{VERSION}-W{WAVE}-{SEQ}`） |
| `version` | string | 是 | 版本號（例如：`0.16.0`） |
| `wave` | int | 是 | Wave 編號（1, 2, 3...） |

#### 單一職責欄位

| 欄位 | 類型 | 必填 | 說明 |
| ---- | ---- | ---- | ---- |
| `action` | string | 是 | 動詞（Implement, Fix, Add, Refactor, Remove, Update） |
| `target` | string | 是 | 單一目標（方法、類別、測試、檔案等） |

#### 執行資訊

| 欄位 | 類型 | 必填 | 說明 |
| ---- | ---- | ---- | ---- |
| `agent` | string | 是 | 執行代理人（例如：`parsley-flutter-developer`） |

#### 5W1H 設計

| 欄位 | 類型 | 必填 | 說明 |
| ---- | ---- | ---- | ---- |
| `who` | string | 是 | 執行者 |
| `what` | string | 是 | 任務內容 |
| `when` | string | 是 | 觸發時機 |
| `where` | string | 是 | 執行位置 |
| `why` | string | 是 | 需求依據 |
| `how` | string | 是 | 實作策略 |

#### 驗收與依賴

| 欄位 | 類型 | 必填 | 說明 |
| ---- | ---- | ---- | ---- |
| `acceptance` | list | 否 | 驗收條件清單 |
| `files` | list | 否 | 相關檔案清單 |
| `dependencies` | list | 否 | 依賴的 Ticket ID 清單 |

#### 狀態追蹤

| 欄位 | 類型 | 必填 | 說明 |
| ---- | ---- | ---- | ---- |
| `status` | string | 是 | 狀態（pending, in_progress, completed） |
| `assigned` | boolean | 是 | 是否有人接手 |
| `started_at` | datetime | 否 | 開始時間（ISO 8601） |
| `completed_at` | datetime | 否 | 完成時間（ISO 8601） |

> 完整 frontmatter YAML 範例（含分組註解）見衛星檔「Frontmatter 完整範例」節。

---

## 第三章：操作流程

Ticket 生命週期的五個動作各對應一個 `ticket track` 子命令；主線程負責建立與查詢，代理人負責接手、完成、放棄。下表為各步驟的概念與 frontmatter 變更，逐字 bash 命令與輸出範例見衛星檔「命令範例」節。

| 步驟 | 使用者 | 命令 | 時機 | Frontmatter 變更 |
| ---- | ------ | ---- | ---- | ---- |
| 建立 Ticket | 主線程 | `create` | PM 規劃 Ticket 後 | 寫入 5W1H 設計 + 初始狀態 + 執行日誌模板 |
| 接手 Ticket | 代理人 | `claim` | 代理人開始執行 | `assigned: true`、`started_at`、`status: in_progress` |
| 完成 Ticket | 代理人 | `complete` | 代理人完成 | `status: completed`、`completed_at` |
| 放棄 Ticket | 代理人 | `release` | 代理人無法繼續 | `assigned: false`、`started_at: null`、`status: pending` |
| 查詢進度 | 主線程 | `query` / `list` / `summary` | 需要了解進度時 | 唯讀 |

**查詢三層粒度**：`query` 查單一 Ticket、`list`（搭配 `--pending` / `--in-progress` / `--completed`）列出篩選清單、`summary` 取版本層快速摘要。

---

## 第四章：與現有機制的整合

### 4.1 與三重文件原則的整合

本方法論的 `tickets/*.md` 位於三重文件階層的細粒度層，向上提供 todolist 與 CHANGELOG 的狀態來源：

```text
CHANGELOG.md       ← 版本發布時提取功能變動
    ↑
todolist.yaml      ← 任務狀態追蹤（粗粒度）
    ↑
tickets/*.md       ← Ticket 狀態追蹤（細粒度） <- 本方法論
    ↑
work-log/*.md      ← 詳細實作記錄
```

### 4.2 與 5W1H 框架的整合

frontmatter 的 `who / what / when / where / why / how` 六欄完整涵蓋 5W1H 框架，使 Ticket 自帶完整設計脈絡。

### 4.3 生命週期狀態對應

| Ticket 生命週期 | Frontmatter 狀態 |
| --------------- | ---------------- |
| Draft | 未建立檔案 |
| Ready | `status: "pending"`, `assigned: false` |
| In Progress | `status: "in_progress"`, `assigned: true` |
| Review | `status: "in_progress"`（日誌標記 Review） |
| Closed | `status: "completed"` |
| Blocked | `status: "in_progress"`（日誌標記 Blocked） |

---

## 第五章：最佳實踐

### 5.1 主線程最佳實踐

主線程需要進度時直接執行 `summary` 或 `query` 命令讀取 frontmatter，不向代理人詢問進度。

- 反模式：「代理人，`{version}-W{n}-001` 完成了嗎？」
- 正確：直接執行 `summary` 或 `query` 命令

### 5.2 代理人最佳實踐

代理人開始前用 `claim` 接手、完成後立即 `complete` 標記，詳細結果寫入 Ticket body 的執行日誌而非回報主線程。

- 反模式：「我已經完成 `{version}-W{n}-001`，以下是詳細報告...」
- 正確：標記完成，詳細記錄到 Ticket 的執行日誌區段

### 5.3 執行日誌撰寫

每個 Ticket 的 body 區段記錄任務摘要、問題分析、解決方案、測試結果、完成資訊五個面向。完整執行日誌範本見衛星檔「執行日誌完整範本」節。

---

## 方法論總結

### 核心價值

本方法論透過 Frontmatter 式追蹤解決以下問題：

1. **單一文件架構** - 設計、狀態、日誌都在同一檔案
2. **減少 Context 佔用** - 腳本輸出精簡，不佔用對話空間
3. **提升追蹤效率** - 直接讀取 frontmatter，無需等待回應
4. **獨立操作** - 主線程和代理人可以獨立查詢和更新
5. **向後相容** - 可唯讀查詢舊版本 CSV 格式（見衛星檔）

### 適用場景

- 多代理人並行執行任務
- 需要頻繁追蹤進度的版本開發
- 主線程需要專注於統籌而非追蹤
- 需要完整保留 Ticket 設計和執行歷史

### 版本演進

| 版本 | 架構 | 狀態 |
| ---- | ---- | ---- |
| v1.0 | YAML + MD 分離 | 已棄用 |
| v2.0 | CSV + MD 分離 | 已棄用（v0.15.x） |
| **v3.0** | **Markdown + Frontmatter** | **當前版本（v0.16.0+）** |

---

**文件結束**
