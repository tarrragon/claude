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
| **main 是否有未提交變更** | **強制 commit**（見下方差別對待規則） |
| worktree 是否有未提交變更 | 提示但不強制（避免干擾其他 terminal） |
| 當前 Ticket 進度是否已寫入 worklog | 新 session 靠 worklog 恢復 context |
| 待驗收的代理人結果是否已處理 | 避免結果被遺忘 |
| Session 中產生的原則 / 洞察是否已持久化 | Context 中的決策經驗不會自動記錄，/clear 後永久消失 |

### main vs worktree 差別對待（強制）

> **Why**：main 與 worktree 對 /clear 的資訊遺失風險不同。main 通常是 PM 主線程紀錄決策、規則調整、跨 ticket 的中介改動；這些變更若隨 /clear 丟失 context 後沒有 commit 留底，後人僅能看檔案不知為何如此改動。worktree 則由代理人持有，可能正在進行中且有平行 terminal 操作；強制 commit 反而會干擾並行工作。
>
> **Consequence**：對 main 不強制會讓 PM 在 context 沉重時為了「快點 /clear」跳過 commit，導致決策脈絡永久遺失（記憶在 context、檔案在 disk，兩者斷鏈）。對 worktree 強制會搶用其他 terminal 正在編輯的檔案，造成跨 session 衝突。
>
> **Action**：依當前分支位置分流處理（下表）。

| 當前位置 | 有未提交變更時 | 動作 |
|---------|--------------|------|
| 主倉庫 main | 是 | **強制**：先 `git add` + `git commit` 才能進入 /clear；commit message 至少含「為何改」（決策理由），不只「改了什麼」 |
| 主倉庫 main | 否 | 通過 |
| Worktree（feature 分支） | 是 | **提示**：列出未提交檔案，告知用戶可選 commit 或留待 worktree owner 處理；**不阻擋** /clear |
| Worktree（feature 分支） | 否 | 通過 |

**判別當前位置**：

```bash
git rev-parse --show-toplevel        # 確認當前是主倉庫還是 worktree
git rev-parse --abbrev-ref HEAD      # 確認當前分支
git status --short                   # 列出未提交變更
```

**主倉庫 + main 分支** = 強制 commit；其他組合 = 提示不強制。

### 禁止行為

| 禁止 | 原因 |
|------|------|
| 未確認經驗持久化就主動建議 /clear | Session 中的隱性知識（決策理由、流程洞察、踩坑紀錄）一旦清除即永久消失 |
| 以「context 太多」為由先建議 /clear 再補文件 | 應反過來：先持久化（memory / ticket / worklog），確認完整後才考慮 /clear |
| Session 中有待後續審查的工作時 /clear | Context 本身是審查的重要輸入；審查必須在當前 session 執行 |
| main 有未提交變更時直接詢問 /clear | 違反差別對待規則；必須先 commit 才呈現 #11 Handoff 選項 |

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

### 自動化落地（W17-083）

紀律規則的自動防護由以下三層機制提供：

| 層 | 機制 | 觸發 | 行為 |
|---|------|------|------|
| 偵測 | `.claude/hooks/stop-worklog-handoff-sync-check-hook.py` | session 結束（Stop event） | 掃描 worklog 最新交接段，比對 `.claude/handoff/pending/`；缺失 / 孤立時於 additionalContext 輸出警告 + 建議 CLI |
| 落地 | `ticket handoff --from-worklog` | PM 顯性執行（被警告後） | 解析 worklog 交接段提取 ticket ID，逐項執行 `ticket handoff` 補建 pending JSON |
| 共用 | `.claude/skills/ticket/ticket_system/lib/worklog_parser.py` | 上述兩者皆 import | 6 公開 API：HANDOFF_KEYWORDS / detect_handoff_keywords / extract_ticket_ids / extract_recent_content / extract_handoff_section / find_worklog_path |

**ARCH-020 同構防漂移**：Stop hook 因 PEP 723 隔離 env 不可 import lib，採 SOT-mirror 策略（HANDOFF_KEYWORDS + ticket ID regex 在 hook 與 lib 同步雙寫，docstring 互相引用 SOT）。修改任一處須同步另一處。

**禁用情境**：CI / batch 環境無 Stop event，自動偵測失效，仍須以紀律規則為準（本章節「禁止行為」「豁免條款」）。

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

> **bg session resume 場景**：Claude Code v2.1.144+ 支援 `/resume` 恢復 background session。bg session resume 不是「新 session 開始」而是「既有 session 恢復」，事件觸發行為與前台新 session 不同，詳見下節「/resume bg session 場景」。

---

## /resume bg session 場景（v2.1.144+）

> **Why**：Claude Code v2.1.144 引入 `/resume` 對 background session 的支援（subagent 結束後 session 仍可被 resume 為前台 interactive session）。既有 handoff 機制設計時假設 session 為前台模式（subagent 結束即 session 終止），bg session resume 屬新增的 session 生命週期模式。雖然 W3-028 ANA 結論顯示**直接衝擊低**（handoff JSON 是 session-agnostic 檔案系統持久化），但 SOP 仍需顯式涵蓋此場景，避免 PM 在 resume bg session 後因預期行為落差而誤判 hook / scheduler 狀態。
>
> **Consequence**：SOP 未涵蓋此場景會讓 PM resume bg session 後遇到「自動 runqueue 提示未出現」「commit-handoff-hook 是否觸發不確定」等情境時無對應指引，被迫即時推理或誤以為機制故障，浪費 token 也容易跳過 handoff 流程。
>
> **Action**：依下方對比表確認當前 session 類型，並依「行為差異說明」採取對應動作。

### 前台 session vs bg session resume 行為對比

| 機制 | 新 session（前台） | /resume 前台 session | /resume bg session |
|------|-------------------|---------------------|-------------------|
| commit-handoff-hook 觸發 | 是 | 是 | 是（resume 後變前台，subagent guard 自動解除） |
| SessionStart hook 觸發 | 是（source=startup） | 是（推論 source=resume，未實證但同 runtime） | 是（source=resume，繼承 bg UUID；W3-028.2 實證） |
| Stop hook 觸發 | 是 | 是 | 是 |
| handoff JSON 可讀 | 是 | 是 | 是（檔案系統層，session-agnostic） |
| ticket resume CLI 可用 | 是 | 是 | 是 |
| 自動 runqueue 提示出現 | 是（透過 session-start-scheduler-hint-hook） | 是 | 是（W3-028.2 實證確認） |

### SessionStart event source 對照表（v2.1.150 實證）

> **來源**：W3-028.2 實機驗證（2026-05-26）

| 進入路徑 | source 值 | session_id 行為 |
|---------|----------|---------------|
| `claude` cold start | `startup` | 新 UUID |
| `claude --background "..."` 建立 bg | `startup` | 新 UUID |
| `/clear` 在現有 session | `clear` | 維持原 UUID |
| `claude attach <bg-id>` | `clear` | 新子 UUID（不繼承 bg UUID） |
| `/resume <running-bg-id>` 全 UUID | runtime 拒絕（無 event；訊息：still running） | N/A |
| `/resume <stopped-bg-id>` 全 UUID | `resume` | 繼承原 bg UUID |
| `/resume` 短 ID（任何狀態） | runtime 拒絕（無 event；訊息：not found） | N/A |

**核心結論**：所有實際可進入 session 的路徑（startup / clear / resume），SessionStart hooks 均觸發。runqueue hint 在所有可行接手場景均出現，無補救必要。

### attach vs /resume 進入路徑差異

| 維度 | `claude attach` | `/resume` |
|------|----------------|-----------|
| 適用 bg 狀態 | running | stopped（runtime 拒絕 running） |
| source 值 | `clear` | `resume` |
| session_id | 新生 child UUID | 繼承原 bg UUID |
| 語義 | 「進來看看」（不繼承狀態） | 「接管原狀態」 |
| 短 ID 支援 | 是 | 否（須全 UUID） |

**選擇建議**：

- **bg session 還在 running**：用 `claude attach <short-id>`，最快接管，新 session_id 不污染原 bg 狀態
- **bg session 已 stopped 但想恢復**：用 `claude` → `/resume <full-uuid>`，繼承原 session UUID
- **/resume 對 running bg 必失敗**：runtime 強制避免並發 owner，必須先 `claude stop`

### bg session resume 後的 handoff 流程

| 步驟 | 動作 | 與前台 session 差異 |
|------|------|-------------------|
| 1. 確認 session 類型 | 觀察 prompt 提示是否含 「resumed from background」標記 | 前台新 session 無此標記 |
| 2. 重建全局視野 | 自動執行 `ticket track snapshot`（W3-028.2 實證：SessionStart 在 /resume 觸發 source=resume，hint hook 跑） | 與前台 session 一致；無需手動干預 |
| 3. 查 runqueue 接手建議 | `session-start-scheduler-hint-hook` 自動觸發；hint 在 additionalContext 顯示 | 與前台 session 一致 |
| 4. 後續執行流程（commit / handoff） | 與前台 session 一致（commit-handoff-hook 在 resume 後變前台後正常觸發） | 無差異 |

### 禁止行為

| 禁止 | 原因 |
|------|------|
| 假設 `/resume` 對 running bg session 可用 | runtime 拒絕：須先 `claude stop <bg-id>`。若僅需查看狀態用 `claude attach <bg-id>` |
| 假設 `claude attach` 與 `/resume` 等價 | 兩者 source 值不同（attach=clear / resume=resume）、session_id 處理不同（attach 新生 child / resume 繼承）。語義不同，依需求選擇 |
| 假設 `/resume` 短 ID 可用 | 必須全 UUID。短 ID 一律 `Session not found` |
| 假設 bg session resume 後 commit-handoff-hook 不觸發 | resume 後 session 變前台，subagent guard 自動解除，hook 正常運作 |
| 把 bg session resume 視為「subagent 內」處理 | resume 後已非 subagent 環境；不可套用 subagent 內的 hook 跳過邏輯 |

### 豁免條款

| 情境 | 處理 |
|------|------|
| Claude Code 版本 < v2.1.144 | 本章節不適用（無 /resume bg session 功能） |
| 未來 Claude Code 升級改變 source 值定義 | 重新執行 W3-028.2 diagnostic hook 實驗，更新本節 source 對照表 |

### 來源

- **W3-028 ANA**（`docs/work-logs/v0/v0.19/v0.19.0/tickets/0.19.0-W3-028.md`）：bg session 與既有 handoff 機制互動矩陣表、風險點識別
- **W3-028.2 已落地**（`docs/work-logs/v0/v0.19/v0.19.0/tickets/0.19.0-W3-028.2.md`）：實機驗證 SessionStart event 在 /resume bg session 的觸發行為，本節 source 對照表與 attach vs resume 差異說明依此驗證結果建立
- **Diagnostic hook**（`.claude/hooks/session-source-diagnostic-hook.py`）：保留作為長期觀察資產，未來版本升級重驗證可直接複用

---

## 相關文件

- .claude/rules/core/pm-role.md — 核心禁令與情境路由
- .claude/pm-rules/decision-tree.md — Re-center Protocol 詳細步驟
- .claude/skills/strategic-compact/ — 策略性 Context 壓縮工具

---

**Last Updated**: 2026-05-26
**Version**: 1.5.0 — W3-028.2 實機驗證落地：新增「SessionStart event source 對照表」與「attach vs /resume 進入路徑差異」兩節；對比表「待驗證」標記更新為 v2.1.150 實證確定狀態（SessionStart 在 /resume bg 觸發 source=resume、繼承 bg UUID）；handoff 流程從「手動執行 snapshot/runqueue」更新為「依賴 SessionStart hook 自動觸發」；禁止行為新增三條（running bg /resume 拒絕、attach ≠ /resume、短 ID 無效）；豁免條款移除 W3-028.2 追蹤、新增版本升級重驗證 trigger
**Version**: 1.4.0 — 新增「/resume bg session 場景（v2.1.144+）」章節：前台 vs bg session resume 行為對比表、bg session resume 後 handoff 流程、SessionStart 觸發行為待驗證標記。對齊 ANA 結論（bg session 直接衝擊低、handoff JSON session-agnostic、SessionStart 待實機驗證）
**Version**: 1.3.0 — 「Worklog 交接與 CLI handoff 同步」章節新增「自動化落地」小節：紀律規則由 stop-worklog-handoff-sync-check-hook + handoff --from-worklog CLI + worklog_parser lib 三層自動防護（W17-083 全鏈完成）；含 ARCH-020 SOT-mirror 設計與 CI/batch 失效豁免說明
**Version**: 1.2.0 — 新增「main vs worktree 差別對待」強制條款（W10-014）：main 未提交變更強制 commit 才能 /clear；worktree 僅提示不強制，避免干擾並行 terminal
**Version**: 1.1.0 — 新增「Worklog 交接與 CLI handoff 同步（雙軌強制一致）」章節，修復 2026-04-24 session 事件根因（worklog 寫了 handoff 但未執行 CLI，scheduler 無候選）
**Version**: 1.0.0 — 從 rules/core/pm-role.md 拆出（W10-076.2 拆分；原檔 v3.7.0 L109-L160）
