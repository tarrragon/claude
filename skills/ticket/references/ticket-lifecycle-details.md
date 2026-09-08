# Ticket 生命週期 - 詳細參考

> **何時讀**：查詢 Ticket 建立格式範本、驗收條件 4V 格式要求、驗收前置條件檢查流程、acceptance-gate-hook 技術細節、P0 緊急任務處理等生命週期細節時。**亦由此進入**：無（`grep -rn` 排除 `SKILL.md` 路由表本檔自身列後零命中，目前無其他檔案的步驟把讀者送到本檔）。
>
> **同目錄**：`track-command.md`（驗收條件操作對應的 CLI 指令）、`workflow-execute.md`（完成判斷決策樹）。
>
> **溯源**：本檔為 `.claude/pm-rules/ticket-lifecycle.md`（核心決策規則）的格式規範/訊息模板/Hook 技術細節詳版，於本專案匯入 commit `f375ae675` 時即已存在；本機 git log 對本檔僅見後續增補（如 hook 路徑漂移引用更正、章節 TOC 補齊），未見原始拆分點。

本檔章節：〈任務鏈後續步驟建議〉〈任務鏈 ID 格式〉〈Ticket 建立格式範本〉〈驗收條件 4V 格式要求〉〈Ticket 有效性驗證〉〈驗收前置條件檢查流程〉〈acceptance-gate-hook 技術細節〉〈驗收提示訊息模板〉〈P0 緊急任務處理〉〈簡化驗收檢查清單〉〈與其他流程的整合〉。

---

## 任務鏈後續步驟建議

當 Ticket 完成時，系統會自動分析任務鏈狀態並建議下一步。

### 分析優先級

| 優先級 | 情境 | 建議內容 |
|--------|------|---------|
| 1 | 有子 Ticket 可開始 | 「子 Ticket {id} 現在可以開始」 |
| 2 | 有被解除阻塞的 Ticket | 「{id} 的阻塞已解除」 |
| 3 | 有同層兄弟 Ticket | 「同層還有 {id} 待處理」 |
| 4 | 同 Wave 有其他 pending | 「同 Wave 還有 N 個待處理」 |
| 5 | 任務鏈全部完成 | 「任務鏈 {root} 全部完成」 |

### 輸出範例

```
============================================================
[任務鏈後續步驟建議]
============================================================

已完成: 1.0.0-W4-007.1
        [實作 track P0 功能]

任務鏈進度: 1/3 completed
   Root: 1.0.0-W4-007

建議下一步:
   1. 1.0.0-W4-007.2
      [實作 track P1 功能]
      原因: 阻塞已解除（blockedBy 1.0.0-W4-007.1 已完成）
      狀態: pending → 可認領
```

---

## 任務鏈 ID 格式

Ticket ID 格式（含子任務序號 `{根ID}.{n}[.{n}...]`）與正則定義見 `.claude/references/ticket-id-conventions.md`〈1. 標準 Ticket ID 格式（主要格式）〉。

### chain 欄位說明

| 欄位 | 類型 | 說明 |
|------|------|------|
| root | string | 任務鏈根 ID |
| parent | string/null | 直接父任務 ID |
| depth | number | 深度（根=0，0-based；與 `track depth` 命令輸出的基數不同，見下方注記） |
| sequence | array | 序號路徑陣列 |

> **與 `track depth` 命令的基數差異**：本欄位由 `calculate_chain_info`（`ticket_system/lib/id_parser.py`）依 ID 序號點數計算，寫入時即固定為建立當下的靜態快照，根任務 = 0（0-based）。`track-command.md`〈track deps / depth 子命令〉的 `ticket track depth <id>` 命令由 `ticket_system/lib/depth.py` 的 `compute_depth` 沿 `parent_id` 鏈即時計算，根任務 = 1（1-based），並用於 `MAX_TICKET_DEPTH=3` 與 `can_descend` 判定。兩者是同名不同來源的獨立量測值，不可互換代入——若把本欄位的 0-based 值直接拿去與 `MAX_TICKET_DEPTH` 比較，會使深度判斷少算一層。判斷是否可再往下派發（`can_descend`）一律以 `track depth` 命令輸出為準，不使用 frontmatter 的 `chain.depth`。

### 範例 chain 欄位

**根任務**（`1.0.0-W3-002`）：
```yaml
chain:
  root: "1.0.0-W3-002"
  parent: null
  depth: 0
  sequence: [2]
```

**子任務**（`1.0.0-W3-002.1.1`）：
```yaml
chain:
  root: "1.0.0-W3-002"
  parent: "1.0.0-W3-002.1"
  depth: 2
  sequence: [2, 1, 1]
```

---

## Ticket 建立格式範本

```markdown
---
id: {版本}-W{波次}-{序號}
title: {動詞} {目標}
type: IMP/ADJ/ANA/DOC
status: pending
priority: P0/P1/P2
who:
  current: pending
  history: {}
created: {日期}
---

# {Ticket ID}: {標題}

## 目標
{目標描述}

## 驗收條件
- [ ] {條件1}
- [ ] {條件2}
```

---

## 驗收條件 4V 格式要求

驗收條件必須符合 4V 原則：**可驗證、可量化、可追溯、可記錄**。

| 要求 | 對應 V | 說明 | 範例 |
|------|--------|------|------|
| 必須有編號 | 可記錄 | 每個驗收項目都有編號 | `1.`, `2.`, ... |
| 必須有來源 | 可追溯 | 引用設計文件或需求 | `SKILL.md〈子命令路由表〉` |
| 必須有確認方法 | 可驗證 | 定義如何驗證完成 | `執行命令驗證輸出` |
| 禁止模糊詞彙 | 可量化 | 不可用「完成」「正常」「適當」 | 用具體描述取代 |

> 四列與四 V 為一對一映射：編號使項目可被索引記錄（可記錄）；來源使項目可回溯依據（可追溯）；確認方法使項目可被驗證（可驗證）；禁模糊詞彙迫使描述量化（可量化）。

**標準格式（frontmatter `acceptance` 清單）**：全 skill CLI（`check-acceptance`／`set-acceptance`／`dispatch-validate` 規則 4／驗收記錄判定優先序 1，見〈驗收記錄的兩種成立形式〉）皆操作 frontmatter 的 `acceptance` 清單，非 body 表格：

```yaml
acceptance:
- '[ ] 具體驗收項目 1（含確認方法）'
- '[ ] 具體驗收項目 2（含確認方法）'
```

新增項目：`ticket track set-acceptance <id> --add "驗收項目文字"`；勾選：`ticket track check-acceptance <id> <index>`。

**報告格式（body，僅供人工呈現，CLI 不讀取）**：

```markdown
## Acceptance Criteria

| # | 項目 | 來源 | 確認方法 | 狀態 |
|---|------|------|---------|------|
| 1 | {項目描述} | {來源引用} | {確認方法} | [ ] |
| 2 | {項目描述} | {來源引用} | {確認方法} | [ ] |
```

> 兩者同時存在時以 frontmatter `acceptance` 清單為準。完整規範：@.claude/methodologies/acceptance-criteria-methodology.md

---

## Ticket 有效性驗證

### 有效 Ticket 定義

有效的 Ticket 必須滿足以下條件：

| 條件 | 說明 | 驗證方式 |
|------|------|---------|
| 決策樹欄位 | 包含 `decision_tree_path` 欄位 | YAML frontmatter 檢查 |
| 或決策樹區段 | 包含「## 決策樹路徑」Markdown 區段 | 內容檢查 |

### 驗證時機

| 時機 | 驗證者 | 動作 |
|------|-------|------|
| 建立 Ticket | /ticket create | 自動要求填寫決策樹欄位 |
| 派發任務 | agent-ticket-validation-hook | 阻止使用無效 Ticket |
| 認領 Ticket | /ticket track claim | 確認 Ticket 有效性 |

### 無效 Ticket 處理

無效 Ticket（缺少決策樹欄位）：
- 無法用於 Task 派發（被 Hook 阻止）
- 需要補充決策樹欄位才能使用
- 建議使用 /ticket create 重新建立

### 補充決策樹欄位

如果 Ticket 缺少決策樹欄位，可手動補充：

1. **YAML 格式**（在 frontmatter 中）：

```yaml
decision_tree_path:
  entry_point: "第X層"
  decision_nodes:
    - layer: "X"
      question: "決策問題"
      answer: "答案"
      next_action: "下一步"
  final_decision: "最終決策"
  rationale: "決策理由"
```

2. **Markdown 格式**（在內容中）：

```markdown
## 決策樹路徑

### 進入點
- **層級**: 第X層
- **觸發條件**: ...
```

---

## 驗收前置條件檢查流程

> **重要**：在執行驗收前，系統會先驗證 Ticket 狀態是否適合驗收。

```
觸發驗收流程
    |
    v
Step 1: 載入 Ticket
    |
    +-- 找不到 --> [Error] 錯誤訊息，exit 1
    |
    v
Step 2: 驗證狀態
    |
    +-- pending --> [Error] 阻止「尚未被接手」，exit 1
    +-- blocked --> [Error] 阻止「被阻塊」，exit 1
    +-- completed --> [Info] 已驗收完成，exit 0
    +-- in_progress --> 繼續檢查
    |
    v
Step 3: 驗收條件預檢查
    |
    +-- 有未完成項 --> [Warning] 提示執行者補齊，不阻止派發
    |
    v
Step 4: 檢查執行日誌
    |
    +-- 有未填寫區段 --> [Warning] 列出未填寫區段，建議執行者補充
    |
    v
[OK] 可以開始驗收，派發驗收代理人
```

### 驗收記錄的兩種成立形式

Step 4 之後、`/ticket track complete` 前，hook 依序判定「是否有驗收記錄」，滿足其一即成立：

| 優先序 | 判定依據 | 成立條件 |
|------|---------|---------|
| 1 | frontmatter `acceptance` 清單 | 全部項目 `[x]` 勾選 |
| 2（fallback） | body 關鍵字掃描 | 命中以下 7 個關鍵字之一：`驗收結果: 通過`、`Acceptance Audit Report`、`驗收通過`、`驗收者：`、`Auditor:`、`PM 直接驗收`、`acceptance-auditor` |

驗收本身由 `.claude/agents/acceptance-auditor.md` 以 Agent 派發執行（非 ticket 命令）；與 `.claude/pm-rules/ticket-lifecycle.md`〈驗收流程〉的 `check-acceptance` 步驟對齊——`check-acceptance` 負責勾選優先序 1 的 frontmatter 清單，acceptance-auditor 產出的驗收報告落在優先序 2 的關鍵字範圍內。

---

## acceptance-gate-hook 技術細節

**Hook 檔案**：`.claude/skills/ticket/hooks/acceptance-gate-hook.py`

**Hook 類型**：PreToolUse

**觸發時機**：`/ticket track complete` 命令執行前

**檢查邏輯**（PreToolUse，`generate_hook_output()` 輸出 JSON `hookSpecificOutput.permissionDecision`；阻止與允許皆由此欄位判定，非行程 exit code）：

| 情景 | 檢查項目 | 結果 | 行為 |
|------|---------|------|------|
| 任一層級 | children（子任務）是否全部 completed/closed？ | 否 | 阻止（`permissionDecision: deny`） |
| 防護類 hook ticket | acceptance 前三項＋Solution 盤點表等必含項目是否齊全？ | 否 | 阻止（deny） |
| ANA | Solution spawn 規劃 N 項 vs `spawned_tickets`+`children` 實際數 S+C：N>0 且 S+C=0？ | 是 | 阻止（deny） |
| ANA | `multi_view_status` 值是否合法（`reviewed`／`skipped`／`n_a`）？ | 否（值非法） | 阻止（deny），修正途徑 `ticket track fix-multi-view-status` |
| 任一層級 | 實驗器材是否已妥善處置？ | 否（殘留） | 阻止（deny） |
| 任一層級 | 驗收記錄是否存在（frontmatter `acceptance` 全勾選，或 fallback body 7 個關鍵字之一）？ | 否 | 警告（`permissionDecision: allow`）；`verify_acceptance_record`（`acceptance_checkers/acceptance_checker.py`）恆回 `should_block=False`，缺驗收記錄不阻擋 |
| ANA | 是否有後續 ticket（`spawned_tickets`／`children`）？ | 否 | 警告（allow） |

> 「父 complete 需子全部 completed/closed」原則見 `.claude/methodologies/atomic-ticket-methodology.md` 任務鏈核心哲學 + `.claude/methodologies/ticket-lifecycle-management-methodology.md` 父 complete 前置條件。舊版「根任務／子任務分列」「所有子任務是否驗收」判準與程式碼不符（無對應檢查函式），已依 `acceptance-gate-hook.py`（`check_acceptance_status`）與 `acceptance_checkers/acceptance_checker.py`（`verify_acceptance_record`）實作改寫。

**阻止場景**：實際訊息內容依觸發的 checker 模組決定，無統一固定文字（如 children 未完成訊息見 `children_checker.py`、防護類必含項目見 `hook_protection_acceptance_checker.py`、ANA spawn 規劃不一致見 `ana_spawn_consistency_checker.py`）；觸發情境見上表。

**驗收方式判準**（是否提醒派 acceptance-auditor，非阻擋）：`generate_hook_output()` 僅在下列條件全部成立時，於允許輸出附加 `AskUserQuestionReminders.COMPLETE_REMINDER` 提醒——priority 為 `P0`、type 不是 `DOC`／`ANA`、呼叫者非 subagent；其餘情況略過（記 log「自動簡化驗收」）。**呼叫者為 subagent 時，此提醒與其餘 AskUserQuestion 提醒一律略過**——subagent 無法自行派發 acceptance-auditor，驗收改由 PM 於 complete 後視情況補派。完整驗收流程見 `.claude/pm-rules/ticket-lifecycle.md`〈驗收流程〉。

**Hook 註冊**（`.claude/settings.json`，實際 schema：`hooks.PreToolUse` 陣列，`matcher` 為工具名而非本 hook 專屬鍵，同一 matcher 下多個 hook 依序註冊）：

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "uv run --quiet $CLAUDE_PROJECT_DIR/.claude/skills/ticket/hooks/acceptance-gate-hook.py"
          }
        ]
      }
    ]
  }
}
```

### 驗證結果對應表

以下為 `ticket track complete` CLI 本身（`ticket_system/commands/lifecycle.py` 的 `complete()`）的驗證結果，屬 CLI 層 exit code；與上方 acceptance-gate-hook 的 `permissionDecision`（PreToolUse 層，先於 CLI 執行）是不同機制——hook 先擋（deny 則 CLI 不執行），CLI 再驗（exit code 由 process 決定，非 JSON）。

| 情境 | 驗證結果 | 訊息類型 | Exit Code |
|------|---------|---------|-----------|
| Ticket 不存在 | 阻止 | Error | 1 |
| 狀態為 pending | 阻止 | Error（提示先 claim） | 2 |
| 狀態為 blocked | 阻止 | Error（提示先 release） | 2 |
| 狀態為 completed | 允許（友好提示，冪等） | Info | 0 |
| 驗收條件未全部完成（frontmatter `acceptance` 有未勾選項） | 阻止 | Error（列出未完成項） | 1 |
| 正常完成 | 允許 | OK | 0 |

> `pending`／`blocked` 經 `precondition.require_in_progress()` 判定，exit code 為 2（非 1）。

---

## 驗收提示訊息模板

實際訊息由 `generate_hook_output()`（`acceptance-gate-hook.py`）依下列分支決定，附加於允許輸出的 `additionalContext`（提醒，非阻擋文字）：

| 觸發條件 | 附加訊息 | 內容重點 |
|---------|---------|---------|
| priority 為 `P0` 且 type 不是 `DOC`／`ANA`，呼叫者非 subagent | `AskUserQuestionReminders.COMPLETE_REMINDER` | 提醒 PM 於 complete 前用 AskUserQuestion 選擇驗收方式（標準驗收／簡化驗收／先完成後補驗收），不阻擋 complete 本身 |
| priority 非 `P0`，或 type 為 `DOC`／`ANA` | 無（略過） | 記 log「自動簡化驗收」，視為已豁免 |
| 呼叫者為 subagent（任何 priority／type） | 無（略過） | subagent 無法自行使用 AskUserQuestion；驗收改由 PM 於 complete 後視情況補派，見 `.claude/pm-rules/ticket-lifecycle.md`〈驗收流程〉 |
| 無其他訊息且流程走到最後 | `AskUserQuestionReminders.COMPLETE_NEXT_STEP_REMINDER` | complete 後選擇下一步（繼續下個 Ticket／Wave 收尾／版本發布檢查／清空 Session），同樣僅提醒不阻擋，subagent 呼叫時略過 |

> 舊三段固定文字模板（暗示「驗收必須在 complete 之前完成」為前置關卡）與實作不符，已移除；`/ticket track complete` 本身是否阻擋見上方〈acceptance-gate-hook 技術細節〉檢查邏輯表（驗收記錄缺失僅警告，不阻擋）。

---

## P0 緊急任務處理

P0 緊急任務採「先完成後補驗收」的時間順序調整，驗收要求本身不因此被豁免。下述 24 小時為此流程的 SLA 政策值（PM 派發驗收的建議上限），非由量測資料推導；如需調整由 PM 於 pm-rules 修訂：

```
P0 緊急任務
    |
    v
執行者完成工作（優先響應）
    |
    v
標記「待補驗收」
    |
    v
[後續] PM 派發驗收（24 小時內）
    |
    v
驗收完成 → 正式完成
```

**P0 待補驗收記錄格式**：

```markdown
### P0 待補驗收
- **完成時間**: {時間}
- **補驗收期限**: {完成時間 + 24 小時}
- **狀態**: 待驗收 / 已驗收
```

---

## 簡化驗收檢查清單

acceptance-auditor 對 DOC 類型或簡單任務進行簡化驗收時，必須確認：

- [ ] Ticket 結構完整性（必填欄位齊全）
- [ ] 所有驗收條件已完成
- [ ] 執行日誌已填寫（非佔位符）
- [ ] 無遺漏項目

**簡化驗收記錄格式**：

```markdown
### 簡化驗收記錄
- **驗收者**: acceptance-auditor
- **驗收類型**: 簡化驗收
- **驗收時間**: {時間}
- **驗收結論**: 通過
```

---

## 與其他流程的整合

### 與 TDD 流程整合

Phase 0~4 Ticket 按順序執行：SA 審查 → 功能設計 → 測試設計 → 策略規劃 → 實作執行 → 重構優化

> 詳細流程：@.claude/pm-rules/tdd-flow.md

### 與事件回應流程整合

incident-responder 分析 → 建立錯誤修復 Ticket → 派發對應代理人

> 詳細流程：@.claude/pm-rules/incident-response.md

### 與技術債務流程整合

Phase 4 發現技術債務 → 記錄到工作日誌 → /tech-debt-capture → 建立技術債務 Ticket

> 詳細流程：@.claude/pm-rules/tech-debt.md

### 與建議追蹤流程整合

調查/分析報告產生建議 → 記錄到 Suggestion Tracking → 處理每個建議（採納/拒絕/延後） → 採納的建議轉為驗收條件

> 詳細規範：@.claude/methodologies/suggestion-tracking-methodology.md
