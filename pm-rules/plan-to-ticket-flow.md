# Plan-to-Ticket 轉換流程

Plan Mode 產出到 Atomic Ticket 的轉換流程。

---

## 8 步驟流程

1. **解析 Plan 檔案** - 提取功能名稱、步驟、修改檔案
2. **識別任務項目** - 原子性檢查、分類（IMP/ADJ/ANA/DOC）
3. **評估複雜度** - 認知負擔指數，決定是否拆分
4. **映射 TDD 階段** - 新功能→完整 TDD，小修改→簡化，純文件→DOC
5. **識別依賴關係** - 資料、架構、TDD 依賴，標記 blockedBy
6. **並行分組** - 無依賴同階段任務分組到同一 Wave
7. **產生 Tickets** - `/ticket create` 建立符合格式的 Atomic Ticket
8. **驗證輸出** - 確認所有 Ticket 符合規範

---

## 觸發條件

| 條件 | 強制性 |
|------|--------|
| `.claude/plans/` 下有已核准 Plan | 必須 |
| 用戶已確認（Plan Mode 退出） | 必須 |
| 目標版本和 Wave 已確定 | 必須 |

**不觸發**：Plan 未核准、純研究型 Plan、已有對應 Ticket

---

## 執行中額外發現（強制流程）

> **核心原則**：執行 Ticket 過程中發現任何需要追蹤的問題（技術債/bug/回歸/超範圍需求），必須立即建立 Ticket，**不需要詢問用戶確認**，不可忽視，不可中斷主線。

### 什麼算「額外發現」

| 情況 | 是否觸發 |
|------|---------|
| 執行中發現技術債務 | 是 |
| 執行中發現 bug 或回歸 | 是 |
| 執行 Ticket 時發現相關模組需同步更新 | 是 |
| Agent 分析時識別出計畫未涵蓋的需求 | 是 |
| 實作中發現設計缺口（規則/流程/文件） | 是 |
| 超出當前 Ticket scope 的延伸工作 | 是 |
| 計畫內的子步驟細分 | 否 |
| 已在原計畫 Ticket 驗收條件中的工作 | 否 |

### 強制處理流程

```
執行中發現技術債/問題/超範圍需求
    |
    v
[強制] 立即執行 /ticket create 建立 pending Ticket
（不需要詢問用戶是否要建立）
    |
    v
新 Ticket 歸入當前版本（Wave 依複雜度決定）
    |
    v
繼續執行當前計畫主線（不中斷）
    |
    v
當前 Ticket 完成後 → 處理新建的 pending Ticket
```

**子任務 vs 獨立 Ticket 判斷**：

```
發現額外需求
    |
    v
因執行當前 Ticket 而產生? ─是→ /ticket create --parent {current_id}
    |
    └─否→ /ticket create（獨立 Ticket）
```

判斷依據：「如果當前 Ticket 不存在，這個問題還會被發現嗎？」
- 不會 → 子任務（因果關係）
- 會 → 獨立 Ticket（獨立問題）

### 禁止行為

| 禁止 | 說明 |
|------|------|
| 詢問用戶「要不要建 Ticket？」 | 發現是確定性事件，建立是強制動作 |
| 忽視不建立 Ticket | 額外發現必須立即追蹤 |
| 中斷主線去處理額外發現 | 先建 Ticket，完成當前任務後再執行 |
| 僅口頭回報不建 Ticket | 必須有可追蹤的 Ticket 記錄 |
| 等計畫完成後再補建 Ticket | 必須**立即**建立 |

---

## 前置閘門：載體選擇（PC-BAL-003）

> **順序**：本閘門在「創建位置決策樹」之前。位置決策樹回答「ticket 之間的關係」，前提是已確定該建 ticket；本閘門回答「這件事該不該是 ticket」。

規劃系統的載體有明確的承諾語意分工，選錯載體會使承諾層級與實際狀態不符：

| 載體 | 語意 | 承諾程度 | 適用 |
|------|------|---------|------|
| todolist `proposals` / 提案 | 安全停放區——記錄想法，不代表要做 | 無承諾 | 未啟動版本的工作、輸入未到手的需求 |
| ticket（pending） | 承諾清單——已決定要做，排入排程 | 已承諾 | 範圍與驗收已由規劃確定的工作 |

### 三問閘門（建 ticket 前必答）

| 問題 | 答案為否時的載體 |
|------|-----------------|
| 目標版本已啟動（active）？ | 否 → todolist `proposals` 或提案 |
| 工作的輸入已到手（非等待用戶或他方提供）？ | 否 → 提案，主體留白並記錄啟動條件 |
| 範圍與驗收條件由已完成的規劃決定，非由我推測？ | 否 → 提案，待規劃波展開 |

三問皆為是才建 ticket。任一為否即改用提案或 todolist。

**Why**：框架的規劃流程是單向 pipeline——todolist `proposals` →（版本啟動時）`version-bootstrap` 展開 → spec → UC → ticket。ticket 是 pipeline 的**產出**而非輸入。未啟動版本的工作，其範圍、優先級、驗收條件尚未由該版本的規劃波確定，此時寫下的 acceptance 是對規劃結果的猜測。

**Consequence**：越層建票同時繞過六步流程中的跨提案依賴檢查、spec 骨架建立、UI 類提案的 design token 與元件庫前置檢查；且該票的 acceptance 與規劃波實際產出不一致時，需事後對帳或撤銷。

**Action**：未啟動版本的工作寫入 todolist 的 `proposals` 欄位並建立對應提案（`doc create proposal`），啟動時執行 `version-bootstrap --version <ver>` 展開為票。

### 工具阻擋的解讀順序

`ticket create` 對未啟動版本的阻擋（`版本狀態為 planned（非 active）`）是本閘門的強制層，非技術限制。

| 訊號 | 判定 | 動作 |
|------|------|------|
| 阻擋訊息描述狀態前提（版本未啟動、依賴未完成、前置未通過） | 流程守衛 | 補足前提，或改用不需該前提的載體 |
| 阻擋訊息描述格式或參數錯誤 | 輸入問題 | 修正輸入 |
| 已找到繞過路徑且驗證「不會壞事」 | 不構成繞過的正當性 | 繞過前仍須回答守衛的保護目標 |

**禁止**：修改版本狀態、利用解析順序、加旗標等方式使阻擋失效，以達成越層建票。「驗證繞過不會破壞現況」與「繞過是正確的」是兩個獨立命題，前者為真不蘊含後者；附上誠實的技術註記說明「做了什麼」，不回答「該不該做」，故不豁免本禁令。

---

## Ticket 創建位置決策樹（W17-008.15）

> **背景**：W17-004 / W17-008 系列暴露的問題 — ANA 結論的多項修復條目散落為兄弟 ticket 失去層次感。決策樹協助 PM 在「兄弟」「子任務」「衍生」三種關係間快速定位。
>
> **2026-06-13 W8-025 Option A 修正**：本決策樹原編碼舊 PC-073 模型（ANA 落地走 spawned、「ANA 自身的 child = PC-073 衝突」），在 PC-091 升格（2026-05-03，ANA 落地唯一權威＝children）時未同步，造成與 PC-091/ticket-lifecycle 矛盾。下方已對齊 PC-091：**ANA 落地 = children of ANA（`--parent <ANA-id>`）**，spawned 僅給「執行中意外發現、與當前 ticket 無因果」的工作。

```
新發現需要建立 ticket
    │
    ▼
是 ANA 結論的落地/修復條目？──是──▶ children of ANA（--parent {ANA_id}）
    │                              防護性 ANA 保持 in_progress 直到 children 完成
    │                              （落地條目極多需中間層時：group 為 ANA 的 child，
    │                               落地為 group 的 child；勿建為 ANA 的兄弟）
    │                              盤點/規劃型 ANA 的清理落地亦走此路（清理＝落地，非衍生副產品）
    │
    └─否──▶ 是當前 in_progress ticket 執行中發現？
                │
                是──▶ 因果關係（不執行此 ticket 不會發現）？
                │       │
                │       是──▶ --parent {current_ticket_id}（子任務）
                │       │
                │       否──▶ --source-ticket {current_ticket_id}（衍生 / spawned）
                │              （執行中意外發現的獨立工作，如 W8-013 審查中發現 W8-015/016）
                │
                否──▶ 獨立 ticket（不帶 --parent / --source-ticket）
```

### 三種關係速查

| 關係 | CLI 旗標 | 適用情境 | 違反成本 |
|------|---------|---------|---------|
| 子任務（children） | `--parent {id}` | **ANA 落地（含盤點/規劃型清理）**、因果衍生、需阻擋父 complete | 漏層次 → 看不出延伸鏈；建為兄弟 → PC-091 血緣斷裂 |
| 衍生（spawned） | `--source-ticket {id}` | 執行中**意外發現**、與當前 ticket 無因果的獨立工作（非 ANA 落地） | 漏掛 → 失去追溯；**錯用於 ANA 落地 → 牴觸 PC-091/L115 children 終局** |
| 兄弟（siblings） | 不帶 flag | 完全獨立的問題 | 應屬子卻建兄弟 → 失層次；ARCH-017 兄弟應無依賴 |

### 創建後輔助提示

- `ticket create` 不帶 `--parent` 時若偵測到當前 wave 內 in_progress group，會自動印出提示行（W17-008.15 第 3 項）
- `ticket track stuck-anas` 列出「in_progress 但 spawned 全 completed」的 ANA，協助識別卡住情境（W17-008.15 第 1 項）
- IMP complete 後若 source ANA 的 spawned 全 completed，會自動印出 complete 建議（W17-008.15 第 2 項）

### 禁止項

| 禁止 | 替代 |
|------|------|
| 建為已知 group ticket 的「父任務的兄弟」（破壞層次感） | `--parent {group_id}` |
| ANA 落地用 `--source-ticket`/spawned 或無關聯兄弟編號（PC-091 血緣斷裂 + L115 children 終局） | `--parent {ANA_id}`（ANA 落地一律 children） |
| 把盤點/規劃型 ANA 的清理誤當衍生副產品用 spawned（W8-025 Option A） | `--parent {ANA_id}`（清理＝落地，走 children；ANA 維持 in_progress 至清理完成） |
| 用 `--parent` 串接無因果的 ticket | 改用 `blockedBy` 或保持兄弟 |

---

## 相關文件

- .claude/references/plan-to-ticket-mapping-details.md - 映射規則、依賴分析、並行分組
- .claude/references/plan-to-ticket-details.md - 驗證清單、報告格式
- .claude/pm-rules/ticket-lifecycle.md - Ticket 生命週期
- .claude/pm-rules/tdd-flow.md - TDD 流程
- .claude/rules/core/cognitive-load.md - 認知負擔評估

---

**Last Updated**: 2026-04-28
**Version**: 3.4.0 — 新增「Ticket 創建位置決策樹」（W17-008.15 方案 D）：三種關係（children / spawned / siblings）速查、CLI 輔助提示、禁止項
**Version**: 3.3.0 - 執行中額外發現流程新增子任務 vs 獨立 Ticket 判斷標準
