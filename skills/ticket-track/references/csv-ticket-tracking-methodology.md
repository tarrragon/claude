# CSV 式 Ticket 追蹤方法論

## 方法論概述

本方法論定義基於 CSV 檔案的輕量級 Ticket 狀態追蹤系統，解決主線程與代理人之間的進度追蹤效率問題。

**核心目標**：
- 減少 context 佔用：透過檔案儲存狀態，避免代理人回報佔用主線程 context
- 獨立操作：主線程和代理人可以獨立查詢和更新狀態
- 簡潔輸出：提供精簡的狀態摘要，快速了解進度

**方法論版本**：v2.0.0（精簡版 - 職責分離）

**與其他方法論的關係**：
- 本方法論是「[Ticket 設計派工方法論](./ticket-design-dispatch-methodology.md)」的補充
- 專注於**狀態追蹤**機制，不儲存 5W1H 設計資訊
- 5W1H 資訊存放在 YAML 定義檔（參考「[Atomic Ticket 方法論](./atomic-ticket-methodology.md)」）

**職責分離原則（v2.0 核心變更）**：

| 文件類型 | 職責 | 唯一事實源 |
|---------|------|-----------|
| **tickets.csv** | 狀態追蹤 | ✅ 狀態唯一來源 |
| **{ticket_id}.yaml** | 設計規格 | ✅ 5W1H 唯一來源 |
| **{ticket_id}.md** | 執行日誌 | ✅ 執行過程唯一來源 |

> **⚠️ 重要變更**：v2.0 版本精簡 CSV 欄位，移除 5W1H 資訊，只保留狀態追蹤必要欄位。5W1H 資訊遷移到 YAML 定義檔。

---

## 第一章：設計理念

### 1.1 問題分析

**現有問題**：

1. **追蹤成本高**
   - 主線程需要詢問代理人才能得知進度
   - 每次詢問都需要等待回應，增加延遲

2. **Context 佔用**
   - 代理人回報進度會輸出大量文字
   - 佔用主線程有限的 context 空間
   - 降低主線程處理其他任務的能力

3. **資訊分散**
   - 進度資訊散落在對話記錄中
   - 難以快速獲得全局視圖
   - 歷史記錄難以追溯

### 1.2 解決方案

**CSV 作為狀態儲存**：

```text
主線程                    CSV 檔案                   代理人
   │                         │                         │
   │  查詢進度               │                         │
   ├────────────────────────►│                         │
   │◄────────────────────────┤                         │
   │  （直接讀取，無需詢問）    │                         │
   │                         │                         │
   │                         │  更新狀態               │
   │                         │◄────────────────────────┤
   │                         │  （直接寫入，無需回報）   │
```

**核心原則**：

1. **檔案即狀態**：CSV 檔案是唯一的狀態來源
2. **獨立操作**：查詢和更新不需要雙向溝通
3. **精簡輸出**：腳本輸出最小化，節省 context

### 1.3 與傳統追蹤方式的比較

| 維度 | 傳統方式（詢問代理人） | CSV 追蹤方式 |
|------|----------------------|-------------|
| **查詢成本** | 高（需要等待回應） | 低（直接讀取檔案） |
| **Context 佔用** | 高（代理人輸出詳細報告） | 低（腳本輸出精簡摘要） |
| **即時性** | 依賴代理人回應時間 | 即時（檔案隨時可讀） |
| **歷史追溯** | 需要搜尋對話記錄 | 檔案記錄完整歷史 |
| **多版本管理** | 困難 | 每個版本獨立資料夾 |

---

## 第二章：資料結構設計

### 2.1 檔案位置和命名

**目錄結構**：

```text
docs/work-logs/
├── v0.15.15/                    # 版本資料夾
│   ├── tickets.csv              # Ticket 狀態追蹤
│   ├── v0.15.15-ticket-001.md   # Ticket 詳細日誌
│   ├── v0.15.15-ticket-002.md
│   └── v0.15.15-main.md         # 主版本日誌
├── v0.15.16/
│   ├── tickets.csv
│   └── ...
└── ... (舊版本扁平結構保持不變)
```

**命名規則**：

- 版本資料夾：`vX.Y.Z`（與版本號一致）
- CSV 檔案：`tickets.csv`（每個版本固定名稱）
- Ticket 日誌：`vX.Y.Z-ticket-NNN.md`（三位數編號）

### 2.2 CSV 欄位定義

**完整欄位列表**：

| 欄位 | 類型 | 必填 | 說明 | 範例 |
|------|------|------|------|------|
| `ticket_id` | string | 是 | 票號 | `T-001` |
| `log_path` | string | 是 | LOG 檔案相對路徑 | `v0.15.15-ticket-001.md` |
| `who` | string | 是 | 執行者/分派者 | `parsley-flutter-developer` |
| `what` | string | 是 | 任務內容 | `實作 BookRepository` |
| `when` | string | 是 | 觸發時機 | `Phase 3 開始時` |
| `where` | string | 是 | 執行位置 | `lib/infrastructure/` |
| `why` | string | 是 | 需求依據 | `需要持久化書籍資料` |
| `how` | string | 是 | 實作策略 | `SQLite 儲存` |
| `assigned` | bool | 是 | 是否有人接手 | `true` / `false` |
| `started_at` | timestamp | 否 | 開始時間（ISO 8601） | `2025-12-25T00:30:00` |
| `completed` | bool | 是 | 是否完成 | `true` / `false` |

### 2.3 欄位詳細說明

#### ticket_id（票號）

**格式**：`T-NNN`（T 開頭，三位數編號）

**範例**：
- `T-001` - 第一個 Ticket
- `T-002` - 第二個 Ticket
- `T-100` - 第一百個 Ticket

**規則**：
- 同一版本內唯一
- 按建立順序遞增
- 不重複使用（即使 Ticket 被取消）

#### log_path（LOG 檔案路徑）

**格式**：相對於版本資料夾的路徑

**範例**：
- `v0.15.15-ticket-001.md`

**規則**：
- 與 ticket_id 對應
- 檔案可能尚未建立（草稿階段）

#### 5W1H 欄位

**Who（誰）**：
- 格式：`{執行代理人}` 或 `{執行代理人} | {分派者}`
- 範例：`parsley-flutter-developer`、`sage-test-architect | rosemary-project-manager`

**What（什麼）**：
- 格式：簡短描述任務內容（< 50 字）
- 範例：`實作 BookRepository`、`撰寫 BookService 測試`

**When（何時）**：
- 格式：觸發時機或前置條件
- 範例：`Phase 3 開始時`、`T-001 完成後`

**Where（何地）**：
- 格式：檔案路徑或模組位置
- 範例：`lib/infrastructure/`、`test/domains/`

**Why（為什麼）**：
- 格式：需求依據或問題描述
- 範例：`需要持久化書籍資料`、`確保邏輯正確性`

**How（如何）**：
- 格式：實作策略或方法
- 範例：`SQLite 儲存`、`使用 Mockito Mock`

#### 狀態欄位

**assigned（是否接手）**：
- `false`：尚未有人接手
- `true`：已有代理人接手執行

**started_at（開始時間）**：
- 格式：ISO 8601（`YYYY-MM-DDTHH:MM:SS`）
- 空值：尚未開始
- 範例：`2025-12-25T00:30:00`

**completed（是否完成）**：
- `false`：尚未完成
- `true`：已完成

### 2.4 CSV 範例

```csv
ticket_id,log_path,who,what,when,where,why,how,assigned,started_at,completed
T-001,v0.15.15-ticket-001.md,parsley-flutter-developer,實作 BookRepository,Phase 3 開始時,lib/infrastructure/,需要持久化書籍資料,SQLite 儲存,true,2025-12-25T00:30:00,true
T-002,v0.15.15-ticket-002.md,sage-test-architect,撰寫 BookRepository 測試,T-001 完成後,test/infrastructure/,確保邏輯正確性,Mockito Mock,true,2025-12-25T02:00:00,false
T-003,v0.15.15-ticket-003.md,pepper-test-implementer,整合測試規劃,Phase 2 完成後,docs/,驗證模組整合,TDD 流程,false,,false
```

---

## 第三章：操作流程

### 3.1 版本初始化

**時機**：開始新版本開發時

**操作**：
```bash
uv run .claude/hooks/ticket-tracker.py init v0.15.15
```

**結果**：
- 建立 `docs/work-logs/v0.15.15/` 資料夾
- 建立空的 `tickets.csv`（只有標題行）

### 3.2 新增 Ticket

**時機**：PM 規劃 Ticket 後

**操作**：
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

**結果**：
- CSV 新增一行記錄
- `assigned=false`、`completed=false`

### 3.3 接手 Ticket（代理人）

**時機**：代理人開始執行 Ticket

**操作**：
```bash
uv run .claude/hooks/ticket-tracker.py claim T-001
```

**結果**：
- `assigned=true`
- `started_at=當前時間`

### 3.4 完成 Ticket（代理人）

**時機**：代理人完成 Ticket

**操作**：
```bash
uv run .claude/hooks/ticket-tracker.py complete T-001
```

**結果**：
- `completed=true`

### 3.5 查詢進度（主線程）

**單一 Ticket**：
```bash
uv run .claude/hooks/ticket-tracker.py query T-001
```

**列出所有**：
```bash
# 進行中的 Tickets
uv run .claude/hooks/ticket-tracker.py list --in-progress

# 未接手的 Tickets
uv run .claude/hooks/ticket-tracker.py list --pending

# 已完成的 Tickets
uv run .claude/hooks/ticket-tracker.py list --completed
```

**快速摘要**：
```bash
uv run .claude/hooks/ticket-tracker.py summary
```

**輸出範例**：
```text
📊 Ticket 摘要 v0.15.15 (2/3 完成)
T-001 | ✅ 已完成 | parsley | 實作 BookRepository
T-002 | 🔄 進行中 | sage | 撰寫測試 (已 1h30m)
T-003 | ⏸️ 未接手 | pepper | 整合測試規劃
```

### 3.6 放棄 Ticket（代理人）

**時機**：代理人無法繼續執行

**操作**：
```bash
uv run .claude/hooks/ticket-tracker.py release T-001
```

**結果**：
- `assigned=false`
- `started_at=清空`

---

## 第四章：與現有機制的整合

### 4.1 與 Ticket 設計派工方法論的關係

**互補定位**：

| 方法論 | 職責 |
|--------|------|
| Ticket 設計派工方法論 | 定義 Ticket 的設計標準、生命週期、Review 機制 |
| CSV Ticket 追蹤方法論 | 提供輕量級的狀態追蹤和查詢機制 |

**整合點**：

1. **Ticket 建立**
   - 按照「Ticket 設計派工方法論」設計 Ticket
   - 使用本方法論的腳本記錄到 CSV

2. **生命週期狀態對應**

   | Ticket 生命週期 | CSV 狀態 |
   |----------------|---------|
   | Draft | 未記錄（尚未正式建立） |
   | Ready | `assigned=false`, `completed=false` |
   | In Progress | `assigned=true`, `completed=false` |
   | Review | `assigned=true`, `completed=false`（日誌標記 Review） |
   | Closed | `completed=true` |
   | Blocked | `assigned=true`（日誌標記 Blocked） |
   | Cancelled | 從 CSV 刪除或標記（保留歷史） |

3. **文件同步**
   - CSV 記錄狀態變更
   - Ticket 日誌（.md）記錄詳細過程

### 4.2 與 5W1H 框架的整合

**CSV 欄位完整涵蓋 5W1H**：

- Who → `who` 欄位
- What → `what` 欄位
- When → `when` 欄位
- Where → `where` 欄位
- Why → `why` 欄位
- How → `how` 欄位

**填寫時機**：
- Ticket 建立時填寫完整 5W1H
- 確保每個 Ticket 都經過 5W1H 思考

### 4.3 與三重文件原則的整合

**三重文件 + CSV 的關係**：

```text
CHANGELOG.md         ← 版本發布時提取功能變動
    ↑
todolist.md          ← 任務狀態追蹤（粗粒度）
    ↑
tickets.csv          ← Ticket 狀態追蹤（細粒度）★ 本方法論
    ↑
work-log/*.md        ← 詳細實作記錄
```

**職責分工**：

| 文件 | 粒度 | 職責 |
|------|------|------|
| CHANGELOG | 版本 | 面向用戶的功能描述 |
| todolist | 任務 | 開發任務全景圖 |
| tickets.csv | Ticket | 細粒度狀態追蹤 |
| work-log | 詳細 | 完整技術記錄 |

---

## 第五章：最佳實踐

### 5.1 主線程最佳實踐

**定期檢查進度**：
```bash
# 每次需要了解進度時執行
uv run .claude/hooks/ticket-tracker.py summary
```

**不要詢問代理人進度**：
- ❌ 錯誤：「代理人，T-001 完成了嗎？」
- ✅ 正確：直接查詢 CSV

**批量建立 Ticket**：
- 規劃階段一次建立所有 Ticket
- 方便了解全局進度

### 5.2 代理人最佳實踐

**開始前接手**：
```bash
# 開始執行任務前先接手
uv run .claude/hooks/ticket-tracker.py claim T-001
```

**完成後標記**：
```bash
# 完成後立即標記
uv run .claude/hooks/ticket-tracker.py complete T-001
```

**不要回報進度給主線程**：
- ❌ 錯誤：「我已經完成 T-001，以下是詳細報告...」
- ✅ 正確：標記完成，詳細記錄到 Ticket 日誌

### 5.3 版本管理最佳實踐

**每個版本獨立資料夾**：
- 便於歷史追溯
- 避免跨版本混淆

**保持 CSV 簡潔**：
- 5W1H 欄位簡短描述
- 詳細內容放在 Ticket 日誌

**定期歸檔**：
- 版本完成後保留 CSV 作為歷史記錄

---

## 第六章：工具參考

### 6.1 腳本命令速查

| 命令 | 用途 | 使用者 |
|------|------|-------|
| `init <version>` | 初始化版本資料夾 | 主線程 |
| `add --id ... --who ...` | 新增 Ticket | 主線程 |
| `claim <ticket_id>` | 接手 Ticket | 代理人 |
| `complete <ticket_id>` | 標記完成 | 代理人 |
| `release <ticket_id>` | 放棄 Ticket | 代理人 |
| `query <ticket_id>` | 查詢單一 Ticket | 主線程 |
| `list [--in-progress\|--pending\|--completed]` | 列出 Tickets | 主線程 |
| `summary [--version <version>]` | 快速摘要 | 主線程 |

### 6.2 狀態圖示說明

| 圖示 | 狀態 | 說明 |
|------|------|------|
| ⏸️ | 未接手 | `assigned=false` |
| 🔄 | 進行中 | `assigned=true`, `completed=false` |
| ✅ | 已完成 | `completed=true` |

### 6.3 相關檔案

| 檔案 | 用途 |
|------|------|
| `.claude/hooks/ticket-tracker.py` | 主要腳本 |
| `.claude/templates/tickets.csv.template` | CSV 範本 |
| `.claude/commands/ticket-track.md` | Skill 定義 |

---

## 方法論總結

### 核心價值

本方法論透過 CSV 式追蹤解決以下問題：

1. **減少 Context 佔用** - 腳本輸出精簡，不佔用對話空間
2. **提升追蹤效率** - 直接讀取檔案，無需等待回應
3. **獨立操作** - 主線程和代理人可以獨立查詢和更新
4. **完整歷史** - CSV 檔案保留完整狀態變更記錄

### 適用場景

- 多代理人並行執行任務
- 需要頻繁追蹤進度的版本開發
- 主線程需要專注於統籌而非追蹤

### 限制說明

- CSV 不支援複雜的依賴關係管理（需配合 Ticket 日誌）
- 單一 CSV 不適合超過 100 個 Tickets（建議拆分版本）

---

**文件結束**
