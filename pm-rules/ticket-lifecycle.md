# Ticket 生命週期流程

> 操作指南：.claude/skills/ticket/SKILL.md
> AskUserQuestion 規則：.claude/pm-rules/askuserquestion-rules.md

---

## 狀態定義

```
pending → claim → in_progress → complete → completed
                                    ↑ release → blocked → 升級 PM
```

| 狀態 | 允許操作 |
|------|---------|
| pending | claim |
| in_progress | complete, release |
| completed | 就地修正（不變更狀態）或建立修正子 Ticket |
| blocked | claim（重新認領） |

> **completed 修正規則**：completed 狀態不可回退為 in_progress（歷史完整性）。
> 修正走「完成後發現」流程：`.claude/pm-rules/execution-discovery-rules.md` 3.5-B 層。

---

## 階段-標準流程總覽

| 階段 | 強制規則 | AskUserQuestion |
|------|---------|----------------|
| **建立** | 必須用 `/ticket create`，禁止直接寫 .md | 任務拆分確認（認知 > 10） |
| **建立後** | 強制並行審核：acceptance-auditor（品質）+ system-analyst（設計）→ creation_accepted: true | - |
| **認領** | 阻塞依賴檢查 + **5W1H 待定義欄位補全（強制）** + **簡化 WRAP 三問（W/A/P，強制）** | - |
| **執行** | 錯誤強制派發 incident-responder；日誌必填 | - |
| **驗收** | **主動勾選驗收條件**（`check-acceptance`）→ acceptance-gate-hook 事後驗證 | **驗收方式確認**（標準/簡化/先完成後補） |
| **完成** | 所有驗收條件已勾選後執行 `/ticket track complete`；complete 後處理 #17（錯誤學習） | **後續步驟選擇** |
| **收尾** | PM 主動告知變更狀態 + 查詢待處理 | **Wave 收尾確認** |

> 各階段詳細規則：.claude/references/ticket-lifecycle-phases.md

---

## Ticket 建立強制規則

| 規則 | 說明 |
|------|------|
| 必須使用命令 | `/ticket create` |
| 唯一存放路徑 | `docs/work-logs/v{version}/tickets/` |
| 子任務建立 | `/ticket create --parent {parent_id}` |
| 任務層級判斷 | 因執行現有 Ticket 產生 → 子任務；獨立問題 → 新任務鏈 |
| **ANA 衍生 Ticket 溯源驗證** | **AC 必須 1:1 對應來源 ANA Solution 修改項（PC-041）** |
| **骨架/references 雙向檢查** | where.files 必須同時列骨架索引路徑與 references 實質路徑（詳見 `.claude/methodologies/atomic-ticket-methodology.md` §「where.files 撰寫指引：拆分檔案配對」） |

### ANA 衍生 Ticket 溯源驗證（強制）

> **來源**：PC-041 — 分析 Ticket 結論的落地執行不完整，PM 只執行部分項目就標記完成。

從 ANA Ticket 衍生執行 Ticket 時，建立階段必須執行溯源驗證：

| 步驟 | 動作 | 說明 |
|------|------|------|
| 1 | 列出 ANA Solution 所有修改項 | 逐項列出，不遺漏 |
| 2 | 合併背景代理人分析結果 | 等待通知或查閱 output |
| 3 | 建立執行 Ticket 的 AC | 每個修改項對應一條 AC |
| 4 | 交叉驗證覆蓋率 | AC 合集覆蓋 Solution 所有項 = 100% |

**禁止行為**：

| 禁止 | 原因 |
|------|------|
| 依記憶建立 AC，不逐項對照 Solution | 容易遺漏（PC-041 根因） |
| 背景代理人未完成就建立執行 Ticket | 延遲分析結果被跳過 |
| 執行 Ticket AC 比 ANA Solution 少 | 修改不完整，驗收失效 |

---

## 建立後強制審核流程

Ticket 建立後、認領前，強制並行派發多代理人審核。

### 觸發條件

- Ticket 建立完成（`/ticket create` 執行成功）
- `creation_accepted` 為 false（預設）

### 審核內容

| 審核者 | 面向 | 檢查項目 |
|--------|------|---------|
| acceptance-auditor | 品質 | 驗收條件 4V 合規、where.files 完整性（含骨架/references 配對完整性）、數字正確性 |
| system-analyst | 設計 | 設計合理性、重複實作檢查、範圍適當性 |

### 審核流程

```
/ticket create → creation_accepted: false
    |
    v
[強制] 並行派發 acceptance-auditor + system-analyst
    |
    v
彙整結果 → 通過（無高/中缺陷）→ creation_accepted: true → 可認領
         → 未通過 → 修正 → 重新審核
```

### 判定標準

| 缺陷等級 | 判定 | 處理 |
|---------|------|------|
| 無/僅低缺陷 | 通過 | creation_accepted: true |
| 中缺陷 | 不通過 | PM 修正後重新審核或確認 |
| 高缺陷 | 不通過 | 必須修正後重新審核 |

### 豁免條件

| 條件 | 說明 |
|------|------|
| 已審核父 Ticket 的子任務 | 範圍已確認，可跳過 |

> 來源：PC-002 錯誤模式 — Ticket 建立後未經審核直接派發

---

## 驗收流程

| 任務類型 | 驗收深度 |
|---------|---------|
| IMP/ADJ/TDD Phase/複雜/安全 | 完整驗收（acceptance-auditor） |
| DOC/簡單（任務範圍單純） | 簡化驗收 |

### Complete 前主動勾選驗收條件（強制）

> **來源**：用戶反饋 — 每次 complete 都被 CLI 擋回才補勾驗收條件，浪費 context 和耐心。

PM 執行 `ticket track complete` **前**，必須先主動勾選所有驗收條件。禁止依賴 CLI 的錯誤提示才補勾。

**強制步驟順序**：

```
任務執行完成
    |
    v
Step 1: 逐條確認驗收條件已滿足
    |
    v
Step 1.5: [IMP/ADJ] error-pattern 衝突檢查（PC-052 預防）
    |       列出修改的核心函式/模組 → /error-pattern query <函式名>
    |       有衝突 → 暫停，評估是否需調整方案
    |       無衝突 → 繼續
    |
    v
Step 2: 執行 ticket track check-acceptance <id>
    |
    v
Step 3: 執行 ticket track complete <id>
    |
    v
acceptance-gate-hook 事後驗證（最後防線）
```

### Complete 前 error-pattern 衝突檢查（IMP/ADJ 強制）

> **來源**：PC-052 — 修改核心函式完成後，才發現 IMP-049 已記錄相同修改失敗 2 次。如果 complete 前查詢 error-pattern，問題在驗收階段就能攔截。

**觸發條件**：IMP 或 ADJ 類型 Ticket 執行 complete 前。

**執行方式**：

| 步驟 | 動作 | 範例 |
|------|------|------|
| 1 | 列出 Ticket 修改的核心函式/模組 | `run_hook_safely`, `sys.exit` |
| 2 | 用每個名稱查詢 error-pattern | `/error-pattern query run_hook_safely` |
| 3 | 檢查是否有衝突 | 找到 IMP-049 警告不要修改 |
| 4a | 有衝突 → 暫停 complete，評估方案 | WRAP 決策或調整修改 |
| 4b | 無衝突 → 繼續正常 complete | — |

**與認領時查詢的差異**：

| 時機 | 查詢重點 | 目的 |
|------|---------|------|
| 認領時 | 問題描述關鍵字 | 了解歷史上類似問題的處理方式 |
| complete 前 | 修改的核心函式名 | 確認修改不與已知失敗經驗衝突 |

**豁免條件**：DOC/ANA/REF 類型 Ticket（不涉及程式碼修改）。

**禁止行為**：

| 禁止 | 說明 |
|------|------|
| 直接執行 complete 不先 check-acceptance | 會被 CLI 擋回，浪費 context |
| 被擋回後才補勾 | 應主動確認，不依賴被動提醒 |

---

## AC 漂移偵測（claim 階段強制）

> **來源**：PC-055 — Ticket AC 與實況漂移未被系統偵測。PROP-010 Phase 1 MVP 透過兩項自動機制防護。
>
> **觸發時機**：每次執行 `ticket track claim <id>` 時，CLI 自動觸發 AC 驗證 + stale 警告。

### 機制總覽

| 機制 | 實作位置 | 觸發條件 | 來源 Ticket |
|------|---------|---------|------------|
| AC 自動驗證 | `lifecycle.py` / `claim_verification.py` | claim 前解析 AC 並執行可機器驗證項 | W11-001.1 |
| Stale 年齡警告 | `lib/staleness.py` | Ticket 建立距今 >= 7/14/30 天 | W11-001.2 |

### Claim 時三決策路徑

claim 命令整合上述兩機制後，PM 面對的決策空間為：

| 情境（驗證結果 + 年齡） | CLI 行為 | PM 三選一決策 |
|-----------------------|---------|--------------|
| S1: AC 全未達成 + fresh (<7d) | 通過，直接進入 in_progress | 無需決策 |
| S2: AC 部分未達成（N/A 或跳過） | 輸出結果，問 y/n | **繼續 claim** / **取消** |
| S3: AC 部分已達成（外溢） | 輸出已達成明細，問 y/n | **繼續 claim（重做）** / **取消後轉 complete** |
| S4: AC 全部已達成（S4） | **拒絕 claim**，提示改用 complete 記錄外溢 | **轉 complete** / **取消** |
| 任一 + stale WARNING (>14d) | claim 前輸出 WARNING，續接上述 y/n | 同上 + 考慮重新規劃 |
| 任一 + stale CRITICAL (>30d) | claim 前強烈警告「標記 stale 或重新規劃」 | 同上 + 建議拆分/關閉 |

**三選一決策總綱**：

| 決策 | 適用情境 | 後續動作 |
|------|---------|---------|
| 繼續 claim（y） | AC 未達成或部分達成屬預期 | 正常進入 in_progress |
| 取消（n） | 疑似外溢或規格需重評估 | 暫緩 claim，重新評估 Ticket |
| 轉 complete | AC 已全部或多數被上游 Ticket 外溢達成 | `check-acceptance --all` → `complete` 並 append-log 記錄外溢來源 |

### 實例範例

**範例 A：Ticket 已達成（外溢）**

```
# 情境：W5-020 pending 18 天，PC-055 觸發案例。
# 上游 W5-015 的重構已順帶修復 AC[0]「測試全綠」和 AC[1]「lint 0 warning」。

$ ticket track claim 0.18.0-W5-020
[WARNING] Ticket 建立已 18 天，超過 14 天警告閾值
[AC 驗證] 解析 4 條 AC，執行 2 條可機器驗證：
  [x] AC[0] 測試全綠（npm test 0 failure）— 已達成（外溢）
  [x] AC[1] lint 0 warning — 已達成（外溢）
  [-] AC[2] 補 worklog — 無法自動驗證
  [-] AC[3] 文件更新 — 無法自動驗證
[S3] 部分 AC 已達成。繼續 claim (y) / 取消 (n)? n

# PM 選擇 n → 改用 complete：
$ ticket track append-log 0.18.0-W5-020 "AC[0-1] 由 W5-015 外溢達成，AC[2-3] 手動確認"
$ ticket track check-acceptance 0.18.0-W5-020 --all
$ ticket track complete 0.18.0-W5-020
```

**範例 B：Ticket 尚未達成（正常 claim）**

```
# 情境：W10-042 昨天建立，AC 要求實作新功能。

$ ticket track claim 0.18.0-W10-042
[AC 驗證] 解析 3 條 AC，執行 1 條可機器驗證：
  [ ] AC[0] 新指令 `track snapshot` 可執行 — 未達成
  [-] AC[1] 整合測試通過 — 待實作後驗證
  [-] AC[2] 文件更新 — 無法自動驗證
[S2] AC 未達成。繼續 claim (y) / 取消 (n)? y
[OK] claim 成功，進入 in_progress
```

### PM 行為規範

| 行為 | 強制性 |
|------|-------|
| 不可跳過 claim 時的 AC 驗證輸出 | 強制閱讀 |
| S3/S4 情境不可直接 y 重做 | 強制評估是否為外溢 |
| CRITICAL 級 stale 警告不可忽略 | 強制決定「繼續 / 拆分 / 關閉」 |
| 轉 complete 時必須 `append-log` 記錄外溢來源 | 強制，保留追溯 |

### 豁免條件

| 條件 | 處理 |
|------|------|
| `--skip-verify` 旗標 | 跳過 AC 驗證（CI/緊急情境用，stderr 輸出 WARNING 紀錄） |
| `--yes` 旗標 | 自動選 y，但 S4 仍拒絕（S4 拒絕優先於 --yes） |
| 無可機器驗證 AC 的 Ticket | CLI 僅輸出「無可驗證項」，不阻擋 claim |

> AC 驗證實作細節：`.claude/skills/ticket/ticket_system/commands/claim_verification.py`
> Stale 閾值常數：`.claude/skills/ticket/ticket_system/lib/staleness.py`（7/14/30 天）
> PC-055 完整症狀與根因：`.claude/error-patterns/process-compliance/PC-055-ticket-ac-drift-undetected.md`

---

## 完成階段錯誤學習驗證

`ticket track complete` 執行前，acceptance-gate-hook 會自動檢查是否有新增 error-pattern，並輸出場景 #17 提醒。

**強制時序**：先執行 complete，後處理 #17（避免死鎖）。

| 條件 | 處理 |
|------|------|
| 有新增 error-pattern | complete 後執行 AskUserQuestion #17 |
| 無新增 error-pattern | 跳過 #17，正常完成 |

> 執行時序詳細說明和死鎖防護：.claude/references/ticket-lifecycle-phases.md（完成階段錯誤學習驗證章節）
> 場景定義：.claude/pm-rules/askuserquestion-rules.md（場景 #17）

---

## 父 Ticket complete 前置檢查（強制）

> **來源**：`.claude/methodologies/atomic-ticket-methodology.md` 「任務鏈核心哲學 — 父子責任傳遞」+ `.claude/methodologies/ticket-lifecycle-management-methodology.md` 「父 complete 前置條件」。

**核心原則**：父文件完成 ≠ 父責任履行。父 complete 需滿足「所有子 Ticket 已 completed 或 closed」。

### 強制規則表

| 場景 | 父 Ticket 狀態 | PM 行為 |
|------|--------------|--------|
| 子 Ticket 全 completed/closed | 可 complete | 執行 `ticket track complete <父ID>` |
| 任一子 Ticket pending/in_progress/blocked | **禁止 complete** | 繼續處理子 Ticket，父保持 in_progress |
| 父需抽離 context（未準備 complete） | 保持 in_progress | 用 `ticket handoff <父ID>` 而非 `complete` |
| 父 AC 全勾但有子未完成 | **禁止 complete** | AC 勾選是文件完成，非責任履行 |

### 禁止行為

| 禁止 | 原因 |
|------|------|
| 子未完成時強制 complete 父 | 父責任尚未由子履行，違反任務鏈哲學 |
| 將父回退為 pending 等待子 | completed 不可回退（lifecycle 規則）；但父未 complete 時保持 in_progress 本身就是等待 |
| 以「只是個 ANA 分析完成了就 complete」為由越過 | ANA 父的責任是「分析結論被解決」，不是「分析報告寫完」 |

### CLI 層強制

acceptance-gate-hook 將於 0.18.0-W10-036.2 實作根任務 complete 前的遞迴子狀態檢查（exit 2 block）。在該 Hook 落地前，本規則由 PM 自律 + 方法論文件約束。

---

## ANA Ticket 落地下游血緣選擇（強制）

> **來源**：PC-091 — PM 將 ANA Solution 的「落地行動」建立為兄弟 Ticket（同 Wave 獨立編號），導致血緣斷裂、`tree`/`chain` 看不到延伸鏈。

ANA Ticket 的下游 Ticket **必須以 children 表達**（用 `--parent <ANA-id>`），不可建立為兄弟。

| 場景 | 血緣選擇 | 命令 |
|------|---------|------|
| ANA 結論的執行延伸（IMP/DOC 落地） | **children** | `--parent <ANA-id>`（自動子序號） |
| 執行 Ticket 過程中發現獨立 bug/技術債 | **spawned_tickets** | 建立後手動填入欄位 |
| 完全獨立的新需求（非任何上游觸發） | **sibling** | 不指定 `--parent` |

**判別問題**（PM 建立下游 Ticket 前自問）：

> 這個 Ticket 的存在是因為「上游 Ticket 的結論要求」嗎？
> - 是 → children
> - 否，但發現於上游執行中 → spawned_tickets
> - 否，獨立發現/規劃 → sibling

**禁止行為**：
- 把「執行獨立性」（可獨立執行）誤當「血緣獨立性」（與上游無關）→ 仍應為 children
- 用 `spawned_tickets` 代替 `parent_id` 表達血緣（spawned 是衍生副產品語意，非直系後代）

> **CLI 對照**：`--parent` vs `--source-ticket` 的副作用、欄位寫入、阻擋規則完整對比表，見 `.claude/skills/ticket/references/create-command.md`「--parent vs --source-ticket 對比表」章節。建立衍生 Ticket 時使用 `--source-ticket <SOURCE-ID>`，CLI 會自動追加新 Ticket ID 至 source 的 `spawned_tickets`，無需人工編輯。

---

## ANA 衍生 Ticket Priority 繼承（強制）

> **來源**：PC-075 下游傳播路徑軸 B — 無 priority 繼承規則時，P1 ANA 衍生 P2 IMP 造成「P1 分析結論的落地執行卻被排在其他 P1 後面」的語意矛盾。

**預設繼承規則**：

| ANA 類型 | 衍生 Ticket（children 或 spawned）預設 priority |
|---------|----------------------------------------|
| 防護性 ANA（結論需要 IMP 落地才算解決） | **繼承 source ANA 的 priority** |
| 純研究性 ANA（結論是知識產出，無需落地） | 衍生 Ticket 視實際需求獨立指定 |

**Why**：防護性 ANA 的衍生 Ticket 承載「分析結論的落地責任」，若 priority 降級，runqueue 排序會將結論落地推遲至其他同 priority 任務之後，違反「分析急迫性 → 落地急迫性」的邏輯延續。

**降級條件**：

衍生 Ticket 僅在以下情境可降級 priority：

| 降級情境 | 範例 | 必要條件 |
|---------|------|---------|
| 非阻塞性優化 | 補強性 hook、增量提示、nice-to-have 功能 | ticket body 明示「降級理由」段落 |
| 已有替代防護 | 其他 spawned Ticket 已覆蓋主要風險，本項為補強 | 引用替代防護的 Ticket ID |
| 跨版本延後 | 本版本 scope 外，但保留追蹤 | 明示目標版本 |

**降級明示要求**：

降級 priority 的衍生 Ticket 必須在 ticket body（Problem Analysis 章節或建立備註）明示降級理由。禁止：

- 無理由降級（PM 預設 P2 而非繼承）
- 以「看起來不急」為由降級
- 未引用替代防護就降級「非阻塞性」類別

**檢查清單**（PM 建立 ANA 衍生 Ticket 時）：

- [ ] source ANA 是否為防護性 ANA？（結論需 IMP 落地才算解決）
- [ ] 若是，衍生 Ticket priority 是否預設繼承 source？
- [ ] 若降級，ticket body 是否含明示降級理由段落？
- [ ] 降級理由是否屬上表三種情境之一？

> **CLI 行為**：`ticket create --source-ticket <ID>` 目前不自動繼承 priority（PM 需手動指定 `--priority`）。未來 CLI 可能實作自動繼承 + 降級需 `--priority-override-reason` 強制，屆時本規則作為實作依據。

---

## ANA Ticket 完成階段衍生 Ticket 檢查（強制）

> **來源**：ANA Ticket 完成時未強制確認分析結論是否需要建立衍生 Ticket，導致建議被遺忘需事後人工補建。

`ticket track complete` 對 ANA 類型 Ticket 執行前，acceptance-gate-hook 自動檢查 `spawned_tickets` 和 `children` 欄位。

| 情況 | 處理方式 |
|------|---------|
| spawned_tickets/children 不為空 **且全 completed/closed** | 通過，可 complete |
| spawned_tickets/children 不為空 **但有未完成** | **阻止 complete**（適用父 complete 前置規則） |
| 兩者皆為空 | 輸出 WARNING，提醒 PM 確認是否需要建立衍生 Ticket |

**PM 在看到 WARNING 後必須二選一**：

| 選擇 | 動作 |
|------|------|
| 需要衍生 Ticket | 先建立 Ticket 並**等待其 completed/closed**後才 complete 父（非「建立後即可 complete」） |
| 不需要 | 在 Ticket 執行日誌中記錄理由（如「分析結論為維持現狀，無需修改」）|

> **重要澄清**：「建立衍生 Ticket」不等於「父責任已履行」。衍生 Ticket 須 completed/closed，父才可 complete。見本文件上方「父 Ticket complete 前置檢查」章節。

> acceptance-gate-hook 實作：步驟 2.5（check_ana_has_spawned_tickets），獨立於步驟 2 驗收記錄檢查。

---

## Close 條件規則

> **來源**：W15-024 ANA — W15-015 決策中 PM 提議「閘門未觸發時 close ticket」，被用戶指正：ticket 只能「做任務」或「收狀（completed/closed）」，不可有「留待之後判斷」。本章節固化 close 合法條件，防止推延性 close 反模式重犯。

---

### C1. close 合法理由（frontmatter 必填 close_reason）

執行 `ticket track close <id>` 時，`close_reason` 必填，且必須為以下 6 枚舉之一：

| close_reason | 語意 | 使用要求 |
|-------------|------|---------|
| `goal_achieved` | 目標已達成 | 正常完成路徑（一般用 `complete` 取代） |
| `requirement_vanished` | 需求消失（環境變更使 ticket 無意義） | 需在執行日誌說明外部變更事由 |
| `superseded_by` | 被上游 ticket 取代 | 必須附 ticket ID（如 `superseded_by: 0.18.0-W15-020`） |
| `not_executable_knowledge_captured` | 無法執行且知識已轉移至 error-pattern | 必須附 error-pattern 檔案路徑 |
| `duplicate` | 與既有 ticket 重複 | 必須附重複 ticket ID |
| `cancelled_by_user` | 用戶明示取消 | 必須在執行日誌附理由（一句即可） |

**回溯 close（retrospective）**：既有 closed ticket 若無 close_reason，允許補填 `unknown`，但需標記 `retrospective: true` 供 audit 使用。

---

### C2. 禁止的假 close（推延性 close 反模式）

以下動機**不構成合法 close 理由**，違反者視為推延性 close 反模式（PC-090）：

| 禁止說法 | 真實動機 | 正確處理 |
|---------|---------|---------|
| 「等 data / 等觀察再說」 | 決策疲勞 / 成本迴避 | migrate 至下版本，或 rescope 條件 |
| 「暫緩 / 之後再說」 | 成本迴避 | migrate 或拆 ANA 改設計 |
| 「算了不重要了」 | 決策疲勞 | close `cancelled_by_user` 並在日誌記錄決策依據 |
| 「閘門未達，先 close」 | 閘門混淆（把 ANA 成本閘門當目標達成） | 評估條件型 ticket 三後果（見 C3） |
| 「follow-up 已建立，原 ticket 收掉」 | 責任轉移錯誤 | follow-up completed 後父才可 close/complete |

**識別信號**：close 理由描述含「等」「暫」「之後」「再觀察」「不急」時，必須重新評估是否符合 C1 枚舉。

---

### C3. 條件型 Ticket 建立時預定義三後果

條件觸發型 ticket（例：「E3 > 0.3 才投入 E2 實驗」「指標達標才執行 X」）**建立時必須在 how.strategy 預定義三後果**：

```markdown
how:
  strategy: |
    條件：[描述觸發條件，如「E3 > 0.3」]
    - 觸發 → [執行動作，如「實作 E2 實驗」]
    - 未觸發 → close `not_executable_knowledge_captured`，error-pattern 位置：[路徑 TBD]
    - 未觸發但條件仍有價值 → rescope 條件或 migrate 至下版本
```

**為何強制預定義**：

| 問題 | 後果 |
|------|------|
| 未預定義 → 條件未觸發時 PM 不知道如何處置 | 推延性 close（或假 close）風險極高 |
| 未預定義 → 沒有 error-pattern 落地路徑 | 知識損失 |
| 建立時預定義 → PM 執行時有明確路徑 | 防止 W15-015 類型重犯 |

---

### C4. CLI 驗證規範

> **實作 Ticket**：W15-027（ticket CLI close command 加 `--reason` 必填枚舉驗證）

`ticket track close` 指令的驗證行為（W15-027 落地後生效）：

| 驗證項目 | CLI 行為 |
|---------|---------|
| `--reason` 未填 | 拒絕執行，列出 6 枚舉提示 |
| `--reason` 不在枚舉內 | 拒絕執行，提示最近似枚舉 |
| `superseded_by` 未附 ticket ID | 拒絕執行，提示補填 `--ref <ticket_id>` |
| `not_executable_knowledge_captured` 未附 error-pattern 路徑 | 拒絕執行，提示補填 `--ref <file_path>` |
| `duplicate` 未附 ticket ID | 拒絕執行，提示補填 `--ref <ticket_id>` |
| `unknown`（retrospective） | 允許，自動加 `retrospective: true` 標記 |

**W15-027 落地前過渡期**：PM 自律補填 `close_reason` 至 frontmatter，CLI 不阻擋但 acceptance-gate-hook 輸出 WARNING。

---

## 相關文件

- .claude/references/ticket-lifecycle-phases.md - 各階段詳細規則
- .claude/skills/ticket/references/ticket-lifecycle-details.md - 格式和 Hook 技術細節
- .claude/pm-rules/decision-tree.md - 主線程決策樹
- .claude/pm-rules/incident-response.md - 事件回應流程
- .claude/error-patterns/process-compliance/PC-090（建立中）- 推延性 close 反模式

---

**Last Updated**: 2026-04-21
**Version**: 6.1.0 — 新增「ANA 衍生 Ticket Priority 繼承」章節（預設繼承 + 三種降級情境 + 降級明示要求 + 檢查清單），來源 PC-075 下游傳播路徑軸 B

**Version**: 6.0.0 - 新增「Close 條件規則」章節（C1 close_reason 6 枚舉、C2 禁止假 close 案例、C3 條件型 ticket 三後果模板、C4 CLI 驗證規範），來源 W15-024 ANA + W15-025
