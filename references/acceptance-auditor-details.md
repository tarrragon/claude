# Acceptance Auditor 詳細驗收步驟

本文件包含 acceptance-auditor 代理人的詳細驗收檢查步驟、判定規則和報告格式範例。

> 主要定義：.claude/agents/acceptance-auditor.md

---

## Step 2：結構完整性檢查

### YAML Frontmatter 必填欄位

| 欄位 | 檢查規則 | 失敗判定 |
|------|---------|---------|
| `id` | 非空且符合 Ticket ID 格式 | 空值或格式錯誤 |
| `title` | 非空 | 空值 |
| `type` | 為有效類型（IMP/TST/ADJ/RES/ANA/INV/DOC） | 無效值 |
| `status` | 為 in_progress（驗收時應為此狀態） | 非 in_progress |
| `version` | 非空且符合版本格式 | 空值 |
| `wave` | 非空 | 空值 |
| `priority` | 為有效值（P0/P1/P2） | 無效值 |
| `who.current` | 非空 | 空值（無人認領） |
| `what` | 非空 | 空值 |
| `why` | 非空 | 空值 |
| `acceptance` | 為非空陣列 | 空陣列或缺失 |
| `assigned` | 為 true | 為 false（未認領） |
| `started_at` | 非空 | 空值 |

### 可選但建議填寫的欄位

| 欄位 | 說明 |
|------|------|
| `when` | 觸發時機 |
| `where` | 執行位置 |
| `how` | 實作策略 |
| `decision_tree_path` | 決策樹路徑 |

---

## Step 3：子任務完成狀態檢查

### 檢查規則

```
Ticket 有 children 欄位?
    |
    +-- 否（children 為空陣列）--> 跳過此步驟
    |
    +-- 是（children 非空）
        |
        v
    逐一載入每個子任務
        |
        v
    每個子任務的 status 是否為 completed?
        |
        +-- 全部 completed --> 通過
        +-- 有非 completed --> 失敗，列出未完成的子任務
```

### 檢查項目

| 檢查項 | 規則 | 失敗判定 |
|-------|------|---------|
| children 存在性 | 載入每個 child Ticket 檔案 | 檔案不存在 |
| children 狀態 | 每個 child 的 status 為 completed | 任一 child 非 completed |
| 遞迴檢查 | 子任務若也有 children，同樣需要全部 completed | 任一孫任務非 completed |

### 失敗報告格式

```markdown
[FAIL] 子任務完成狀態檢查

未完成的子任務：
| ID | 標題 | 狀態 |
|----|------|------|
| 0.31.0-W4-052.2 | 實作 acceptance-gate-hook | pending |
| 0.31.0-W4-052.3 | 更新 ticket-lifecycle 規則 | pending |

結論：父任務 0.31.0-W4-052 有 2 個子任務未完成，不允許通過驗收。
```

---

## Step 4：執行日誌完整性檢查

### 檢查規則

在 Ticket 的 body 部分（`---` 分隔符之後），檢查 Execution Log 區段。

| 區段 | 檢查規則 | 失敗判定 |
|------|---------|---------|
| `## Problem Analysis` | 存在且有實際內容 | 不存在、為空、或包含佔位符 |
| `## Solution` | 存在且有實際內容 | 不存在、為空、或包含佔位符 |
| `## Test Results` | 存在且有實際內容 | 不存在、為空、或包含佔位符 |

### 佔位符識別

以下模式視為「未填寫」：

| 佔位符模式 | 說明 |
|-----------|------|
| `<!-- To be filled by executing agent -->` | 預設佔位符 |
| `<!-- .* -->` | 任何 HTML 註解形式 |
| `(pending)` | 待填寫標記 |
| `TBD` / `TODO` / `N/A` | 常見佔位符 |
| 空白或僅有換行 | 實質上未填寫 |

### 失敗報告格式

```markdown
[FAIL] 執行日誌完整性檢查

未填寫的區段：
- Problem Analysis：包含佔位符 `<!-- To be filled by executing agent -->`
- Test Results：區段為空

結論：執行日誌有 2 個區段未填寫。
建議：使用 `ticket track append-log <id> --section "Problem Analysis" "內容"` 補填。
```

---

## Step 5：測試執行驗證

> **核心原則**：「測試通過」不能只看 Ticket 上的勾選，必須親自執行驗證。

### 觸發條件

```
Ticket 類型判斷
    |
    +-- IMP / ADJ / TST --> 執行測試驗證
    |
    +-- DOC / ANA / RES / INV --> 跳過（SKIP）
```

### 檢查流程

```
[Step 5] 測試執行驗證
    |
    v
1. 執行 dart analyze（靜態分析）
    |
    +-- 有 error --> FAIL
    +-- 有 warning --> WARN（記錄但不阻止）
    +-- 無問題 --> 繼續
    |
    v
2. 從 Ticket 的 where.files 或驗收條件識別相關測試檔案
    |
    v
3. 執行 flutter test（相關測試或全部測試）
    |
    +-- 有失敗 --> FAIL（列出失敗的測試）
    +-- 全部通過 --> PASS
```

### Bash 使用規則

| 允許的命令 | 用途 | 範例 |
|-----------|------|------|
| `dart analyze` | 靜態分析，偵測語法錯誤和類型問題 | `dart analyze lib/` |
| `flutter test` | 執行測試套件 | `flutter test test/unit/` |
| `flutter test --reporter compact` | 精簡輸出格式 | 大量測試時使用 |

| 禁止的命令 | 原因 |
|-----------|------|
| 任何修改檔案的命令 | 驗收代理人只讀 |
| `git` 操作 | 不在職責範圍 |
| `flutter build` | 不需要建置 |
| 安裝/移除套件 | 不在職責範圍 |

### 報告格式範例

**失敗（靜態分析有錯誤）**：
```markdown
[FAIL] 測試執行驗證

靜態分析結果：
- dart analyze: 2 error(s), 1 warning(s)
- error 1: lib/domain/plan_parser.dart:270 - Expected ';' after this.
- error 2: lib/domain/plan_parser.dart:275 - Undefined name 'result'.

測試執行結果：
- flutter test: 無法執行（靜態分析有 error）

結論：程式碼存在語法錯誤，測試無法通過。
```

**失敗（測試未通過）**：
```markdown
[FAIL] 測試執行驗證

靜態分析結果：
- dart analyze: 0 error(s), 0 warning(s)

測試執行結果：
- flutter test: 3 tests failed out of 47
- FAILED: test/unit/plan_parser_test.dart - 'parse empty input returns empty list'
- FAILED: test/unit/plan_parser_test.dart - 'parse valid plan extracts steps'
- FAILED: test/unit/plan_parser_test.dart - 'parse nested steps maintains hierarchy'

結論：3 個測試未通過，驗收失敗。
```

**通過**：
```markdown
[PASS] 測試執行驗證

靜態分析結果：
- dart analyze: 0 error(s), 0 warning(s)

測試執行結果：
- flutter test: All 47 tests passed

結論：所有測試通過，靜態分析無問題。
```

---

## Step 6：驗收條件一致性檢查

### 檢查規則

| 檢查項 | 規則 | 失敗判定 |
|-------|------|---------|
| 驗收條件數量 | acceptance 陣列至少 1 項 | 空陣列 |
| 條件合理性 | 每項驗收條件都是具體可驗證的描述 | 含模糊詞（「完成」「正常」「適當」） |
| 與執行日誌一致 | 驗收條件描述的內容在 Solution/Test Results 中有對應記錄 | 驗收條件提到的功能/修改在日誌中找不到對應 |

### 一致性判斷方法

**關鍵字比對**：從驗收條件提取關鍵概念，在執行日誌中搜尋對應記錄。

範例：
- 驗收條件：「validate_execution_log() 偵測佔位符」
- 搜尋日誌中是否提到 `validate_execution_log` 或「佔位符偵測」
- 找到 --> 一致；找不到 --> 標記為「無法確認一致性」

**注意**：一致性檢查是「合理性判斷」而非「精確匹配」。當無法確認時，標記為「建議人工確認」而非直接判定失敗。

### 報告格式

```markdown
[WARNING] 驗收條件一致性檢查

無法確認一致性的項目：
| # | 驗收條件 | 日誌中對應記錄 | 判定 |
|---|---------|-------------|------|
| 3 | Hook 阻擋行為已驗證 | 未在日誌中找到測試記錄 | 建議人工確認 |

結論：1 項驗收條件無法自動確認一致性，建議 PM 人工確認。
```

---

## Step 7：後續任務銜接檢查

### 核心原則

> 設計類任務必須有後續實作任務；分析類任務必須有後續處理任務。
> 任務不應該「懸空」-- 完成後無人接手、無後續行動。

### 檢查規則

```
Ticket 類型判斷
    |
    v
屬於「應有後續」的類型?
    |
    +-- 否（IMP 實作 / DOC 文件）--> 跳過此步驟
    |
    +-- 是（設計 / 分析 / 調查 / 研究）
        |
        v
    檢查是否存在後續任務
        |
        +-- 有 children 且包含實作類子任務 --> 通過
        +-- 有 spawned_tickets 指向後續任務 --> 通過
        +-- 同任務鏈中有後續 Ticket --> 通過
        +-- 以上皆無 --> 失敗：缺少後續任務
```

### 「應有後續」的任務類型

| Ticket type | 期望後續 | 說明 |
|-------------|---------|------|
| RES（研究） | 實作或決策 Ticket | 研究結論應轉化為行動 |
| ANA（分析） | 修正或改善 Ticket | 分析結果應有對應處理 |
| INV（調查） | 修正 Ticket | 調查根因後應修復 |
| Phase 1（功能設計） | Phase 2 Ticket | 設計完成後應接測試設計 |
| Phase 2（測試設計） | Phase 3a Ticket | 測試設計後應接策略規劃 |
| Phase 3a（策略規劃） | Phase 3b Ticket | 策略規劃後應接實作 |

### 不需要後續的任務類型

| Ticket type | 說明 |
|-------------|------|
| IMP（實作） | 實作本身就是終端任務（除非需要 Phase 4） |
| ADJ（調整） | 調整本身就是修正 |
| DOC（文件） | 文件更新通常是獨立的 |
| Phase 3b（實作執行） | 後續是 Phase 4，但 Phase 4 由流程自動觸發 |
| Phase 4（重構優化） | TDD 流程的最後階段 |

### 後續任務識別方法

按優先級檢查以下來源：

1. **children 欄位**：子任務中是否有 IMP/ADJ 類型
2. **spawned_tickets 欄位**：衍生任務中是否有後續行動
3. **同任務鏈搜尋**：同 root 下是否有序號更大的 Ticket
4. **Ticket body 中的明確聲明**：如「後續任務已在 {id} 中規劃」

### 豁免條件

| 豁免情境 | 識別方式 | 說明 |
|---------|---------|------|
| Ticket body 明確聲明不需後續 | 包含「不需後續」「無需後續行動」等文字 | 已經過有意識的判斷 |
| 任務鏈的最後一個任務 | 同 root 下最大序號 | 任務鏈自然結束 |
| 結論為「不建議」的分析 | ANA 類型且結論為拒絕 | 分析結果不需要行動 |

### 報告格式

```markdown
[FAIL] 後續任務銜接檢查

Ticket 類型: RES（研究）
期望後續: 應有實作或決策 Ticket

檢查結果:
- children: 無子任務
- spawned_tickets: 無衍生任務
- 同任務鏈: 無後續 Ticket

結論: 研究任務完成但無後續行動 Ticket，成果可能懸空。
建議: 建立後續 Ticket 記錄研究結論的處理計畫，或在 Ticket body 中說明不需後續的理由。
```

---

## 驗收報告格式

```markdown
# Acceptance Audit Report

## 基本資訊
- **Ticket ID**: {id}
- **Ticket 標題**: {title}
- **驗收時間**: {timestamp}
- **驗收者**: acceptance-auditor

## 檢查結果摘要

| 檢查步驟 | 結果 | 說明 |
|---------|------|------|
| 結構完整性 | PASS/FAIL | {說明} |
| 子任務完成 | PASS/FAIL/SKIP | {說明} |
| 執行日誌完整 | PASS/FAIL | {說明} |
| 測試執行驗證 | PASS/FAIL/SKIP | {說明} |
| 驗收條件一致 | PASS/WARN | {說明} |
| 後續任務銜接 | PASS/FAIL/SKIP | {說明} |

## 結論
- **驗收結果**: 通過 / 未通過
- **未通過原因**: {如有}
- **改善建議**: {如有}

## 詳細檢查記錄
{各步驟的詳細檢查結果}
```

---

## 驗收結果判定規則

| 情境 | 判定 | 說明 |
|------|------|------|
| 全部 PASS | 通過 | 可執行 complete |
| 任一 FAIL | 未通過 | 不可執行 complete，需修正 |
| 有 WARN 無 FAIL | 通過（附建議） | 可執行 complete，但建議 PM 確認 WARN 項 |

---

**Last Updated**: 2026-03-02
**Version**: 1.0.0 - 從 acceptance-auditor.md 提取（Progressive Disclosure）
