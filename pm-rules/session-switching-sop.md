# 工作階段切換 SOP

> **核心理念**：PM 管理的是整個專案的流動，不是單一 Ticket 的完成。切換工作階段時必須重新掌握全局進度。

---

## 切換前：確認背景任務狀態

每次切換工作焦點（包括 `/clear` 清除 session）前，執行進度快照：

```bash
# 一條命令掌握全局（含版本進度、in_progress、pending、git status）
ticket track snapshot
```

---

## 切換時：記錄當前進度到 worklog

在 worklog 記錄：
- 目前正在進行的 Ticket 和進度
- 背景代理人各自在處理哪個 Ticket
- 下一步預期動作（等代理人回來做什麼）

---

## /clear 前的強制確認

`/clear` 會清除 session context。執行前必須確認：

| 確認項 | 原因 |
|-------|------|
| 背景代理人是否還在運行 | 完成通知會到新 session，但 context 已丟失 |
| 未提交的變更是否已 commit | /clear 不影響檔案，但記憶會丟失 |
| 當前 Ticket 進度是否已寫入 worklog | 新 session 靠 worklog 恢復 context |
| 待驗收的代理人結果是否已處理 | 避免結果被遺忘 |
| Session 中產生的原則 / 洞察是否已持久化 | Context 中的決策經驗不會自動記錄，/clear 後永久消失 |

**禁止行為**：

| 禁止 | 原因 |
|------|------|
| 未確認經驗持久化就主動建議 /clear | Session 中的隱性知識（決策理由、流程洞察、踩坑紀錄）一旦清除即永久消失 |
| 以「context 太多」為由先建議 /clear 再補文件 | 應反過來：先持久化（memory / ticket / worklog），確認完整後才考慮 /clear |
| Session 中有待後續審查的工作時 /clear | Context 本身是審查的重要輸入；審查必須在當前 session 執行 |

---

## Worklog 交接與 CLI handoff 同步（雙軌強制一致）

> **Why**: worklog 「下個 Session 接手 Context」段落是人類可讀的交接（長敘述、背景、決策脈絡），`ticket handoff` CLI 產出 `.claude/handoff/pending/*.json` 是機器可讀的交接（新 session scheduler runqueue 讀取來源）。兩者職責不同，必須同步——只寫 worklog 不執行 CLI，下 session `ticket resume --list` / `runqueue --context=resume` 會找不到任何候選，接手者被迫手動指定 ticket（本事件根因）。
>
> **Consequence**: 缺 CLI handoff 時，session-start-scheduler-hint-hook 的 runqueue 輸出是「（無 resume 候選）」，用戶看不到前 session 明確指定的下個任務，PM 必須靠用戶手動輸入 ticket ID 或從 worklog 重讀尋找——浪費 token 且容易跳過前 session 決策脈絡。
>
> **Action**: session 收尾若在 worklog 寫了「下個 Session 接手 Context」或同義段落（「下 session 優先建議」、「接手指引」等），**強制**同時執行 `ticket handoff <ticket_id>` CLI 產生 pending JSON。若交接對象是多個 ticket，為每個都執行一次。

### 觸發條件

當前 session 準備 commit 或 /clear 前，worklog 或 session summary 中出現以下任一樣態：

| 樣態 | 範例關鍵字 |
|------|-----------|
| 明確指定下個 ticket | 「下 session 優先建議：W17-079」、「接手 W17-080」 |
| 列出未完成 spawned 推進清單 | Spawned 推進清單章節含 pending/in_progress 項 |
| 列出 in_progress 待續 ticket | 「本 session 結束時 W17-079 仍 in_progress」 |

任一樣態成立即觸發。

### 雙軌同步規則

| 軌道 | 產出 | 讀者 | 工具 |
|------|------|------|------|
| Worklog 軌道 | `docs/work-logs/.../vX-main.md` 的「下個 Session 接手 Context」段落 | 人類接手者、審查者 | Edit / Write markdown |
| CLI handoff 軌道 | `.claude/handoff/pending/<ticket_id>.json` | scheduler / runqueue --context=resume | `ticket handoff <ticket_id>` |

**強制一致性**：兩軌道的 ticket ID 清單必須一致。只用一條軌道（尤其只寫 worklog）視為缺口，下 session 接手會卡 scheduler 層。

### 禁止行為

| 禁止 | 原因 |
|------|------|
| 只寫 worklog 不執行 `ticket handoff` CLI | 下 session scheduler 看不到候選 |
| 用 `ticket handoff` 但未在 worklog 補背景脈絡 | 接手者只看到 JSON 無法理解決策脈絡 |
| 用「下 session 再說」或口頭約定取代雙軌產出 | 無持久化紀錄 |

### 豁免條款

| 情境 | 處理 |
|------|------|
| 本 session 所有 ticket 皆 complete 且無下個明確建議 | 豁免，不需 CLI handoff；worklog 可寫「本版本階段性收尾，無 pending handoff」 |
| 交接對象為「觀察期 / 延後追蹤」型 ticket（非立即執行） | 豁免 CLI handoff，僅 worklog 記錄即可；可於 ticket 內用 `blockedBy` 表達依賴 |

### 來源

2026-04-24 session 事件：前 session commit `6d0a8fc2` 在 v0.18.0-main.md 寫「下 session 優先建議：W17-079」，但未執行 `ticket handoff`，本 session /ticket 裸命令 runqueue 回「無 resume 候選」，用戶被迫手動指定 W17-079。雙軌不同步為根因。

---

## Spawned 推進清單（ANA complete 後 handoff 強制欄位）

> **Why**: ANA complete 與 spawned IMP 推進常跨 session（session A 結 ANA，session B 推 spawned），若 handoff 記錄無強制欄位列出 spawned 清單，接手者須重新 `ticket track deps` 查詢並容易遺忘；此機制確保「ANA 結論落地進度」在 handoff 時顯式可見。

### 觸發條件

當前 Ticket 為 ANA 類且 complete 後要進入 handoff / `/clear`；該 Ticket 的 `spawned_tickets` 欄位存在 `pending` 或 `in_progress` 項目時，**強制**在 handoff 記錄（worklog 或 handoff 文件）列出「Spawned 推進清單」欄位。

### 欄位格式

| 欄位 | 說明 |
|------|------|
| Source ANA ID | 衍生這些 IMP 的 ANA Ticket ID |
| Spawned Ticket ID | 各未完成 spawned ticket（pending / in_progress） |
| Priority | 該 spawned ticket 的 priority（依 `ticket-lifecycle.md` 繼承規則） |
| 狀態 | pending / in_progress |
| 預期責任人 | 下次推進建議派給誰（PM 前台 / 代理人類型） |

### 強制性

| 狀態 | 處理 |
|------|------|
| 所有 spawned 皆 completed / closed | 豁免，handoff 無需列出本章節 |
| 任一 spawned 為 pending / in_progress | **強制**列出清單 |
| 僅 P2 以下 spawned 未完成（且 P1 全 completed） | 可於 Wave 結尾集中清點，不強制每次 handoff 都列；但 worklog 需至少一行備註 |

### 查詢 CLI

```bash
ticket track deps <ana-ticket-id>        # 衍生關係（spawned_tickets + source_ticket）與狀態
ticket track query <spawned-id>          # 單一 spawned 詳情（標題、priority、where、acceptance）
```

### 範例

```markdown
### Spawned 推進清單

| Source ANA | Spawned Ticket | Priority | 狀態 | 預期責任人 |
|------------|----------------|----------|------|------------|
| 0.18.0-W17-036 | 0.18.0-W17-039 | P1 | in_progress | rosemary（PM 前台） |
| 0.18.0-W17-036 | 0.18.0-W17-040 | P1 | pending | rosemary（PM 前台） |
| 0.18.0-W17-036 | 0.18.0-W17-041 | P2 | pending | basil-hook-architect |
```

### 來源

W17-036 軸 D 缺口分析：跨 session 遺忘 spawned 推進。詳見 `docs/work-logs/v0/v0.18/v0.18.0/tickets/0.18.0-W17-036.md` Solution 章節軸 D（Handoff 觸發條件補強）。

---

## 新 session 開始時：重建全局視野

```bash
# 快速掌握全局進度（含版本進度、in_progress、pending、git status）
ticket track snapshot

# 查看「接下來該做什麼」（scheduler / Linux runqueue 類比）
ticket track runqueue --context=resume --top 3     # 與 handoff/pending 交集
ticket track runqueue --wave N --format=list       # 當前 wave 可執行清單（priority 排序）
ticket track runqueue --wave N --format=dag        # 完整依賴 DAG + 關鍵路徑
```

**自動引導**：`session-start-scheduler-hint-hook.py` 在 SessionStart 時自動呼叫 `runqueue --context=resume`，結果顯示於 hook additionalContext。用戶無需手動呼叫即可看到排程建議；若需更多資訊（如 DAG 或其他 wave）再手動執行。

然後根據 worklog + runqueue 提示決定從哪個 Ticket 繼續。

**Context 隔離**：一個 session 只做一件事，做完 commit → handoff。

---

## 相關文件

- .claude/rules/core/pm-role.md — 核心禁令與情境路由
- .claude/pm-rules/decision-tree.md — Re-center Protocol 詳細步驟
- .claude/skills/strategic-compact/ — 策略性 Context 壓縮工具

---

**Last Updated**: 2026-04-24
**Version**: 1.1.0 — 新增「Worklog 交接與 CLI handoff 同步（雙軌強制一致）」章節，修復 2026-04-24 session 事件根因（worklog 寫了 handoff 但未執行 CLI，scheduler 無候選）
**Version**: 1.0.0 — 從 rules/core/pm-role.md 拆出（W10-076.2 拆分；原檔 v3.7.0 L109-L160）
