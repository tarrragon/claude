# 決策樹 — 執行 Domain

> 本文件從 decision-tree.md 按 DDD domain 邊界拆分。
> 路由入口：.claude/pm-rules/decision-tree.md
> 來源：決策樹按 DDD domain 邊界拆分

---

## 第三層半：執行中額外發現規則（技術債/問題/超範圍需求）

> 當 PM 或 Agent 在 Ticket 執行過程中發現任何需要追蹤的問題時，適用本規則。

**核心規則：發現即建立，不詢問確認**

- 發現了需要追蹤的問題嗎？→ 是 → **直接 /ticket create**
- 要不要處理、優先級高不高 → 這是後續 acceptance-auditor 審核的職責，不是此刻的決策點

### 子任務 vs 獨立 Ticket 判斷

| 判斷條件 | 建立方式 | 範例 |
|---------|---------|------|
| 因執行當前 Ticket 而產生（因果關係） | 子任務（`/ticket create --parent {current_id}`） | 實作中發現需要先重構某模組 |
| 與當前 Ticket 相同功能模組 | 子任務 | 同一個 feature 的額外驗收條件 |
| 獨立問題、不同模組 | 獨立 Ticket | 發現另一個模組的 bug |
| 跨版本的技術債 | 獨立 Ticket（歸入 todolist） | 長期架構改善 |

> 識別條件、強制處理流程、禁止行為清單：.claude/pm-rules/plan-to-ticket-flow.md（「執行中額外發現」章節）

### 效能問題發現後的代理人更新（強制）

> **來源**：多次效能問題修復（記憶體洩漏、狀態機終態、Widget 重建）後教訓未即時內化到代理人定義，導致同類問題可能重複發生。

當修復效能相關問題（記憶體洩漏、不必要的重建、資源未清理、狀態機問題等）時，除了建立 Ticket 追蹤外，**必須同時評估是否需要更新對應代理人的開發注意事項**。

| 效能問題類型 | 更新目標代理人 | 更新內容 |
|------------|--------------|---------|
| 記憶體洩漏（集合無上限、訂閱未清理） | 對應語言的開發代理人 | 資源管理章節 |
| Widget/Component 不必要重建 | UI 開發代理人 | 重建效能意識章節 |
| 狀態機設計問題 | 對應語言的開發代理人 | 狀態保護原則 |
| goroutine/async 洩漏 | 對應語言的開發代理人 | 並行資源管理 |

**執行時機**：效能修復 Ticket 完成後（Phase 4 或 complete 時），PM 檢查對應代理人是否已有相關注意事項，沒有則補充。

---

### 遇到問題的閉環流程（無法立刻決策時的合法路徑）

> **來源**：`.claude/rules/core/decision-trigger-binding.md` 規定決策只有兩種合法狀態（已決策含結論 / 綁 ticket trigger 延後），禁止無 trigger 延後。本節為規則層的流程層補充：當 PM 遇到問題不能立刻產出狀態 (a) 已決策時，必須走以下閉環產出狀態 (b)，最終回到 (a)。

**核心主張**：「不能立刻決策」不等於「延後」。延後是無 trigger 飄忽，閉環是有明確 ticket trigger 的執行路徑。

#### 5 step 閉環

| Step | 動作 | 具體執行 |
|------|------|---------|
| 1. 識別 | 認知這是「不能立刻產出結論」的問題 | 若可立即決策則寫狀態 (a) 結論，跳過閉環；否則進入 step 2 |
| 2. 建分析/規劃 ticket | 建 ANA（分析）或 DOC（規劃）ticket 承載問題 | `ticket create --type ANA --action "分析" --target "..."` 或 `--type DOC` |
| 3. Solution 規劃驗證/實驗子任務 | 在 step 2 ticket 的 Solution 章節列出需建立的 spawned IMP/DOC tickets | 每項需含：產出物、acceptance、預估成本；用 `--source-ticket` 建衍生 ticket |
| 4. 執行驗證/實驗 | 完成 spawned 子任務（依 Solution 方案逐項執行） | 標準 TDD 流程；每個子任務獨立 commit |
| 5. 釐清解決方案 + 結案 | 根據驗證結果，原 ANA/DOC ticket 寫明確結論並 complete | 結論為狀態 (a)：「採方案 X」「不採方案 Y 因為 Z」「需另建 follow-up 追蹤」 |

#### 結案的合法形式

| 結案內容 | 範例 |
|---------|------|
| 採某方案 | 「採方案 A，理由 B（baseline 數據 C）」 |
| 不採某方案 | 「方案 X 不可行，原因 Y（實驗結果 Z）」 |
| 衍生 follow-up | 「驗證指向新方向 X，已建衍生 ticket 追蹤；本 ticket 結論：原方向不採」 |
| 確認無需處理 | 「驗證後問題不存在/已自然消解，原因 Y」 |

**禁止結案內容**（屬無 trigger 延後反模式，違反 `decision-trigger-binding.md` 規則 1）：

| 反模式 | 原因 | 修正方向 |
|-------|------|---------|
| 「需要更多時間觀察」 | 無 trigger 飄忽 | 建監測 ticket 並設量化條件，以該 ticket 為 trigger |
| 「Phase 5 再決定」 | 違規無 trigger 延後 | 在當下 Phase 內決策，或建 follow-up ticket 明示綁定 |
| 「先放著看以後」 | 無結論等同無做 | 確認可立即下結論（狀態 a）或必須建 spawned ticket（狀態 b） |

#### 與 `decision-trigger-binding.md` 的對應

| 規則層 | 流程層（本章節） |
|---|---|
| 規則 1：決策只有兩種合法狀態 | 閉環是從狀態 (b) 回到狀態 (a) 的合法路徑 |
| 規則 2：trigger 限 ticket ID only | 閉環中所有等待點都是 spawned ticket 完成 |
| 規則 3：寫法替換對照表 | 「之後再評估」→「依 spawned ticket 驗證結果決策」 |
| 規則 4：違規偵測 | 結案文字若含反模式句型且無 ticket 引用即違規 |

任何 PM 工作中遇到「不能立刻決策」必走閉環，禁止用「以後再說」語句閃避。

---

## 第三層半-B：完成後發現（Post-Complete Discovery）

> **來源**：Ticket complete + commit 後 WRAP 分析發現與既有錯誤模式的矛盾，需要選擇性回退。完成後無正式修正流程，導致驗收條件與實際交付物不一致。

**觸發條件**：已 completed 的 Ticket 的交付物需要修正（WRAP 修正、error-pattern 衝突、外部回饋等）。

**與「執行中額外發現」的區別**：

| 面向 | 執行中發現（3.5 層） | 完成後發現（3.5-B 層） |
|------|-------------------|---------------------|
| Ticket 狀態 | in_progress | completed |
| 發現時機 | 實作過程中 | complete + commit 之後 |
| 修正對象 | 當前 Ticket 範圍外的新問題 | 當前 Ticket 交付物本身 |

### 修正規模判斷

```
已完成 Ticket 的交付物需要修正
    |
    v
修正是否改變原始 Ticket 的核心結論/方向?
    +-- 是（如：回退核心修改、方向完全改變）
    |       → 路徑 A：建立修正 Ticket
    +-- 否（如：補充文件、微調參數、更新驗收條件）
            → 路徑 B：就地修正
```

### 路徑 A：建立修正 Ticket

適用於修正規模大或方向改變的情況。

| 步驟 | 動作 | 說明 |
|------|------|------|
| 1 | `/ticket create --parent {original_id}` | 建立子 Ticket，標題含「修正」 |
| 2 | why 欄位記錄修正原因 | 引用 error-pattern 或 WRAP 決策 |
| 3 | 原始 Ticket 追加日誌 | `ticket track append-log` 記錄「發現需修正，見子 Ticket {id}」 |
| 4 | 正常 TDD/實作流程 | 修正 Ticket 走標準流程 |

### 路徑 B：就地修正

適用於修正規模小、不改變核心方向的情況。

| 步驟 | 動作 | 說明 |
|------|------|------|
| 1 | 原始 Ticket 追加日誌 | 記錄修正原因和內容 |
| 2 | 更新驗收條件 | 反映實際最終狀態（已做/未做/已知不做） |
| 3 | commit 引用原始 Ticket | commit message 含原始 Ticket ID |
| 4 | 不重新開啟 Ticket | completed 狀態不變（歷史完整性） |

### 驗收條件處理：凍結 + 補充

修正後，原始 AC **凍結不動**（保留歷史），新增 `amendment_acceptance` 和 `amendment_reason` 欄位：

```yaml
# 原始 AC（凍結，反映 complete 時的驗收狀態）
acceptance:
- '[x] 原始條件 A'
- '[x] 原始條件 B'

# 修正後 AC（反映實際最終狀態）
amendment_acceptance:
- '[x] 保留的改善項'
- '[ ] 已知不做項（附原因）'
amendment_reason: '修正原因簡述'
```

| 欄位 | 用途 | 可修改 |
|------|------|--------|
| `acceptance` | 原始驗收記錄（complete 時的狀態） | 凍結，不修改 |
| `amendment_acceptance` | 修正後的實際狀態 | 修正時填寫 |
| `amendment_reason` | 修正原因（引用 WRAP/error-pattern） | 修正時填寫 |

**為什麼凍結而非覆蓋**：原始 AC 記錄了「complete 時認為已完成的事項」。覆蓋後無法追溯「為什麼當時認為通過驗收」，失去審計價值。

**禁止行為**：

| 禁止 | 原因 |
|------|------|
| 修改原始 acceptance 欄位 | 破壞驗收歷史，無法審計 |
| 重新開啟已完成的 Ticket | 破壞完成歷史，狀態機不可逆 |
| 修正了交付物但只 commit 不記錄 | 原始 Ticket 失去追溯性 |
| 修正後不填 amendment_reason | 修正原因不可追溯 |

---

## 第四層：Ticket 執行流程

```
[Ticket 驗證通過]
    |
    v
是「繼續任務鏈」類請求? ─是→ [強制] 並行可行性分析 → 主動建議並行
    |
    └─否→ pending? → creation_accepted?
          |           ─否→ [強制] 並行審核（acceptance-auditor + system-analyst）
          |                → 通過後設定 creation_accepted: true
          |           ─是→ claim → 階段判斷
          in_progress? → 繼續執行
          completed? → [AskUserQuestion] 後續步驟選擇
          blocked? → 升級 PM
```

**建立後審核檢查（強制）**：pending Ticket 認領前必須 `creation_accepted: true`，否則強制並行派發 acceptance-auditor + system-analyst 審核。豁免：已審核父 Ticket 的子任務。

**Wave 邊界檢查（強制）**：當用戶指定「繼續 Wx」時，**必須**只處理該 Wave 的任務，禁止跨 Wave 執行。

**Handoff 方向選擇（AskUserQuestion）**：當 handoff 有多個可能方向時，**必須**使用 AskUserQuestion 讓使用者選擇。

> **Worktree 隔離**：派發會修改檔案的代理人（parsley, fennel, thyme-python, cinnamon, pepper, mint）必須使用 `Agent(isolation: "worktree")`。詳見 parallel-dispatch.md（Worktree 隔離章節）。

> Ticket 生命週期：.claude/pm-rules/ticket-lifecycle.md
> 並行派發規則：.claude/pm-rules/parallel-dispatch.md

---

**Last Updated**: 2026-04-09
**Version**: 1.0.1 - 版本日期更新（二元化拆分後多視角審查修正）
