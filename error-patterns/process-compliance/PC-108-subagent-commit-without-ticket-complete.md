# PC-108: Subagent Commit 後未主動 Complete Ticket

**Category**: process-compliance
**Severity**: Medium
**Status**: Active
**Created**: 2026-04-21
**Source**: W17-022 分析 subagent 完成實作並 commit 後只回報 PM，未執行 `ticket track check-acceptance --all` 與 `ticket track complete`。

---

## 症狀

Subagent 完成實作、測試與 commit 後，回報內容停在「已提交 / 已完成變更」，但對應 Ticket 仍維持 `in_progress`。PM 需要額外執行：

```bash
ticket track check-acceptance --all <ticket-id>
ticket track complete <ticket-id>
```

典型訊號：

- commit 已存在，但 `ticket track query <id>` 仍顯示 `in_progress`
- Ticket body 的 Problem Analysis / Solution / Test Results 已填寫，acceptance 也可能已勾選，但 `completed_at` 仍為 `null`
- PM 在收尾時多做 2-3 個工具呼叫，只為補代理人本可完成的生命週期收尾
- 並行 session 中，其他排程工具因 Ticket 仍 `in_progress` 而誤判「有人正在做」

## 根因

歷史流程把 `ticket track complete` 視為 PM 專屬生命週期操作，而不是實作代理人的任務收尾責任。

| 層級 | 缺口 |
|------|------|
| Agent preload | Ticket 操作規範只強調 `query` / `append-log`，未明確要求完成後 check acceptance + complete |
| Agent definition standard | W17-016.5 已補「body 填寫責任」，但沒有延伸到 complete 本身 |
| Dispatch prompt | PM 有時會在 prompt 尾端提醒 complete，但不是穩定模板 |
| Hook 安全網 | acceptance-gate-hook 會在 complete 時驗證，但無法促使 agent 主動呼叫 complete |

本質上，代理人將「commit」誤當成任務終點；Ticket 系統的終點其實是「commit + 驗收狀態更新 + complete」。

## 觸發案例

### W17-020

Thyme agent 修復 `runqueue --context=resume` 空結果訊息並 commit。實作與測試已完成，但 Ticket 狀態未由 agent 主動 complete，PM 後續補執行 acceptance 勾選與 complete。

### W17-016.3

Thyme agent 擴充 complete hook type-aware body 驗證與佔位符偵測並 commit。代理人回報完成後，Ticket 生命週期仍需 PM 補完，呈現同一模式。

## 影響

- PM 收尾成本增加，且每次重複消耗注意力與工具呼叫
- `runqueue` / handoff / session-start 提醒依賴 Ticket 狀態時，會把已完成但未 complete 的工作誤判為進行中
- 父子任務或 spawned 任務鏈可能因子任務未 terminal 而阻塞後續 complete 或接手判斷
- 長期會弱化 agent 自律責任，讓 PM 變成 ticket lifecycle 補丁者

## 防護措施

### 1. Agent 自律收尾

W17-033 應將以下流程寫入 `AGENT_PRELOAD.md` 與 `agent-definition-standard.md`：

```bash
ticket track check-acceptance --all <ticket-id>
ticket track complete <ticket-id>
```

規則：

- 實作類 agent 完成 body 填寫、測試與 commit 後，應自行執行上述兩步
- 若 acceptance 無法全數通過，agent 應在 NeedsContext / Test Results 記錄缺口，不得假裝 complete
- 分析型 agent 若任務只要求回報分析，可由 PM 在派發 prompt 中明確豁免 complete

### 2. acceptance-gate-hook 作為安全網

Agent 自行呼叫 `ticket track complete` 時，acceptance-gate-hook 仍會檢查：

- acceptance 是否全數勾選
- type-aware body schema 是否完整
- 必填章節是否仍含 placeholder

因此 agent 主動 complete 不會繞過驗收；它只是把 PM 的手動收尾移回實作責任邊界。

### 3. PM 接收回報時抽查狀態

PM 收到 subagent「已 commit / 完成」回報後，應抽查：

```bash
ticket track query <ticket-id>
```

若 commit 已存在但 Ticket 仍 `in_progress`，先判定為本 pattern，要求 agent 補 complete，或由 PM 補完並將案例回饋到 W17-033 的規則。

### 4. Dispatch Prompt 明示終點

派發實作任務時，prompt 應把終點寫成：

> 完成實作、測試、commit 後，執行 `ticket track check-acceptance --all <id>` 與 `ticket track complete <id>`；若 complete 被 hook 擋下，將阻擋原因寫入 Ticket。

## 與其他 Pattern 關係

| Pattern | 關係 |
|---------|------|
| PC-104 | 同屬 agent 執行邊界誤判；PC-104 是「自稱不能寫回」，本 pattern 是「commit 後未完成 lifecycle」 |
| PC-105 feature integration | 若 agent complete 責任規則未寫入 preload / definition，會重演「功能存在但流程不知道」 |
| PC-075 | spawned / children terminal status 檢查會被本 pattern 放大，因為已完成工作仍非 terminal |

## 關鍵教訓

> 對 Ticket 系統而言，commit 不是完成。完成的最小閉環是：實作落地、測試驗證、commit、acceptance 對齊、`ticket track complete` 成功。

代理人若負責實作，也應負責把它推到 Ticket terminal state；PM 的角色是抽查與處理例外，不是每張 Ticket 的 lifecycle 補完者。
