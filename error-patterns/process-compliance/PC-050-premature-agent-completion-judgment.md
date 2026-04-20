# PC-050: PM 在代理人仍在工作時誤判（完成或失敗）

## 錯誤症狀

**變體 X — 誤判完成**（原始觸發案例）：
- PM 收到一個代理人的完成通知後，立刻開始驗收和 commit
- 實際上還有其他代理人在背景執行中
- 導致代理人工作結果被覆蓋、衝突、或遺漏

**變體 Y — 誤判失敗（新增 2026-04-12）**：
- PM 主動讀取背景代理人的 transcript output 檔案
- 看到 transcript 停留在某個「我即將做 X」的 text 宣告或中間狀態
- 誤判「代理人過早 stop 了/沒執行/失敗」
- 立刻啟動補救措施（建 handoff 準備重派、寫失敗分析）
- 實際上代理人仍在背景執行，稍後才完成並產出完整結果
- 後果：補救 Ticket/handoff/失敗記錄全部要回退或更正，浪費 PM 工作

**變體 Z — 信任 Hook 廣播推論失敗（新增 2026-04-15，收編自 PC-070）**：
- PM 收到 `PostToolUse:Agent hook additional context` 廣播「所有代理人已完成」
- 搭配 `dispatch-active.json` 為空、`git status` 無變更、ticket Solution 仍為模板
- PM 推論「代理人完成但失敗」，啟動失敗 SOP（根因分析、重試策略、縮小 scope）
- 實際上代理人仍在 running，Hook 廣播時機與 CC runtime agent 真實完成狀態不同步
- 與變體 Y 的對照：變體 Y 信任**錯誤資訊源**（transcript body），變體 Z 跳過**正確資訊源**（TaskOutput status）

## 根因分析

PM 缺乏「代理人完成確認」的系統性流程。具體表現：

**模式 A — 未檢查分支就判定失敗**：
1. PM 派發代理人（背景）
2. 代理人在 feature 分支上 commit
3. PM 在 main 上看 `git status`，沒有變更
4. PM 誤判「代理人沒做事」，重新派發
5. 浪費一次代理人執行

**模式 B — 多代理人只看一個就行動**：
1. PM 派發代理人 A（回合耗盡，未完成）
2. PM 重新派發代理人 B（簡化版）
3. 代理人 B 完成，PM 立刻 commit
4. 代理人 A 仍在背景執行（或已完成但 PM 未確認）
5. 兩個代理人可能在同一個分支上產生衝突

**模式 C — 共用分支**：
1. PM 建了一個 feature 分支
2. 並行派發兩個代理人
3. 兩個代理人都在同一個分支上工作
4. 失去分支隔離的意義

**模式 D — 看 transcript 中間狀態就判失敗**（2026-04-12 新增）：
1. PM 派發代理人（背景）
2. PM 主動讀取 `/private/tmp/claude-501/.../tasks/{agentId}.output`
3. transcript 是 JSONL，記錄 agent 每個 tool call，但**尚未到完成時刻**
4. PM 看到最後一行是 agent 的 text（如「I have sufficient context. Now I'll write...」）以為 agent stop
5. 實際上 agent 只是在 tool call 之間的 text response，後續還有 append-log 等工具執行
6. PM 誤判後開始補救流程（在 Ticket 寫失敗分析、建 handoff、準備重派）
7. task-notification 到達時發現 agent 早就完成且產出可用
8. PM 花時間撤回補救措施（刪 handoff、改 append-log 為更正記錄）

**根本原因**：transcript output 是流式寫入，讀取時可能只是代理人執行過程的快照，不是最終狀態。**只有 `<task-notification>` tag 才代表 agent 真正完成或失敗**。

**模式 E — 信任 Hook 廣播推論失敗**（2026-04-15 新增，收編自 PC-070）：
1. PM 派發代理人（background）
2. 短時間內收到 `PostToolUse:Agent` 廣播「所有代理人已完成」+ dispatch-active.json 清空
3. PM 查 ticket：Solution 空、目標檔案無變更、無新 commit
4. PM 推論「代理人完成但沒做事」，進入失敗 SOP（根因分析、scope 縮小、重派）
5. 用戶打斷指正或稍後 task-notification 到達，TaskOutput `<status>` 顯示 `running`
6. 差點造成重派衝突；PM context 浪費在錯誤根因分析

**根本原因**：Hook 廣播訊號（`PostToolUse:Agent hook additional context`、dispatch-active.json 清空）是 Hook 自行維護的計數檔，清除時機與 CC runtime agent 真實完成狀態**不同步**。`git status` 無變更、ticket Solution 空這類「間接訊號」**無鑑別力**——代理人工作中段本來就不落盤、填 Solution 也在尾段。**唯一可靠的狀態來源是 `TaskOutput <status>` 標籤**。

**與模式 D 的對照**：

| 維度 | 模式 D | 模式 E |
|------|-------|-------|
| 誤判類型 | 信任**錯誤**資訊源（transcript body） | 跳過**正確**資訊源（TaskOutput status） |
| 工具焦點 | transcript JSONL 檔案 | Hook 廣播 + dispatch-active.json |
| 症狀關鍵字 | 讀到「我即將做 X」 | 看到「完成訊號組合」 |
| 防護方向 | 禁止讀 body | 強制用 status 查詢 |

兩者為同一家族（代理人狀態誤判），互補防護：前者切斷錯誤資訊通道，後者強化正確資訊通道。

## 防護措施

### PM 代理人完成確認 SOP（強制，已整合到決策樹）

**派發後**（dispatch-gate.md「派發後清點」）：
```bash
cat .claude/dispatch-active.json  # 確認派發數量正確
```

**收到完成通知時**（pm-rules/agent-failure-sop.md「代理人完成確認 SOP」）：
```bash
cat .claude/dispatch-active.json  # 確認剩餘活躍派發
```

**只有 dispatch-active.json 為空時，才能開始驗收和 commit。**

**針對模式 D（誤判失敗）的強制規則（2026-04-13 修訂）**：

| 禁止行為 | 原因 | 替代做法 |
|---------|------|---------|
| 主動讀取 agent transcript output 檔的 **`<output>` body** 推論 agent 是否失敗 | output body 是流式 JSONL 快照，非最終狀態 | 呼叫 TaskOutput 只讀 `<status>` 標籤（見下節）；或等 `<task-notification>` 到達 |
| 看到 agent 在 transcript 中只做了少量 tool call 就判定「過早 stop」 | agent 可能仍在執行，transcript 只是當下狀態 | Hook 顯示「所有代理人已完成」不等於「這個代理人已完成」，必須等 task-notification |
| 在 task-notification 未到達前寫「失敗分析」到 Ticket | 事實未定，可能誤導 | 有疑慮時呼叫 TaskOutput 確認 `<status>`，或用 SendMessage 確認 |

**唯一授權讀取 transcript body 的情境**：`<task-notification>` 已到達但 result 摘要不清楚，需深入檢視 agent 實際 tool calls 時。即便如此也禁止從中間狀態推論「仍在執行 vs 失敗」。

**針對模式 E（信任 Hook 廣播推論失敗）的強制規則（2026-04-15 新增）**：

| 訊號類型 | 性質 | 可靠度 | PM 處理 |
|---------|------|--------|--------|
| `SubagentStop` [OK]/[WAIT] 廣播 | CC runtime 保證代理人停止才觸發 | **高** | 可信完成訊號（長期解法，取代 PostToolUse 廣播） |
| `PostToolUse:Agent` 廣播 | Hook 自行維護，background 啟動時誤觸 | **低** | 已不再廣播 [OK]/[WAIT]（僅 housekeeping） |
| `dispatch-active.json` 空 | SubagentStop 精準清理 + FIFO fallback | 中-高 | 計數 Source of Truth，清理由 SubagentStop 驅動 |
| `git status` 無變更 | 代理人工作中段本來就可能無落盤 | **低**（無鑑別力） | 禁止作為失敗判定依據 |
| `ticket Solution` 空 | 代理人填 Solution 通常在尾段 | **低**（無鑑別力） | 禁止作為失敗判定依據 |
| **`TaskOutput <status>` 標籤** | CC runtime 直接查詢 | **高**（唯一直接證據） | 必須查，才能定論 |

| 禁止行為 | 原因 | 替代做法 |
|---------|------|---------|
| 收到 Hook 廣播「所有代理人已完成」就判定失敗 | Hook 清除時機與 runtime 不同步 | 執行 Step 0.5：`TaskOutput(task_id, block=false, timeout=3000)` 查 `<status>` |
| 用「Hook 完成 + git status 無變更 + Solution 空」組合直接定錨失敗 | 組合中每個訊號鑑別力都低 | 生成 2+ 替代假設（仍在工作／長單步執行／產出位置不符預期），TaskOutput 排除後才決策 |
| 把 `dispatch-active.json` 空當狀態證據 | 這是**結果**訊號（派發清點），非**狀態**查詢 | 狀態判定唯一靠 TaskOutput `<status>` |

**替代假設生成要求**：收到「完成訊號組合」時，禁止立即定錨「失敗」。至少列出：
- 假設 A：代理人完成但失敗（最常見誤判）
- 假設 B：代理人仍在工作（Hook 訊號不可靠）
- 假設 C：代理人在「長單步」中（例如連續 Edit）
- 假設 D：代理人已完成但產出不在預期位置

四假設之一被 TaskOutput status 排除之前，不做重試/重派決策。

### TaskOutput 安全使用範本（2026-04-13 新增）

PM 可用 TaskOutput 工具對 `local_agent` 任務做**非侵入性狀態查詢**，補模式 D 的根因盲點（缺乏主動查詢代理人存活的工具）：

```
TaskOutput(
  task_id=<agentId>,      # Agent tool 返回的 agentId 即是 task_id
  block=false,            # 非阻塞，立即返回
  timeout=3000            # 3 秒超時
)
```

**解讀返回值**：

| 標籤 | 允許讀取 | 用途 |
|------|---------|------|
| `<status>` | 允許 | `running` / `completed` / `error` — 唯一可信的狀態來源 |
| `<task_type>` | 允許 | 確認是 `local_agent`（非 bash/remote） |
| `<retrieval_status>` | 允許 | `not_ready` / `ready` — 指示 output 是否完整 |
| **`<output>` body** | **禁止推論** | 流式 JSONL transcript，可能數十 KB 污染 context；禁止從內容推論代理人狀態 |

**Context 污染警告**：TaskOutput 返回值包含截斷的 `<output>` body（JSONL transcript）。PM **必須紀律性只讀狀態標籤，忽略 `<output>` 內容**。若需深入檢視代理人工具呼叫，等 `<task-notification>` 到達後做，而非從中間狀態推論。

**適用場景**：
- 懷疑某個背景代理人未完成但 task-notification 未到達 → 查 `<status>` 確認
- 失敗判斷前置步驟 Step 0.5（見 pm-rules/agent-failure-sop.md）
- 派發多個代理人後，確認某個特定代理人仍在執行中（非從 dispatch-active.json 推論）

**不適用場景**：
- 代理人計數 → 用 dispatch-active.json（Source of Truth）
- 代理人完成時間 → 等 completion notification（事件驅動）
- git commit 證據 → 靠 agent-commit-verification-hook

**完成 Checkpoint 中**（completion-checkpoint-rules.md「Checkpoint 1.85」）：
- 1.85 代理人清點：dispatch-active.json 非空 → 阻塞，禁止繼續

**判斷代理人失敗前**（pm-rules/agent-failure-sop.md「失敗判斷前置步驟」）：
1. `cat .claude/dispatch-active.json` — 代理人可能還在活躍派發中
2. `git branch | grep feat/` + `git worktree list` — 變更可能在其他分支
3. 只有 dispatch-active.json 為空且所有分支都無 commit 後，才判定失敗

### 並行派發分支隔離（強制，已整合到 dispatch-gate.md）

- 每個代理人使用獨立 feature 分支（N 個代理人 = N 個分支）
- 派發前切回 main 建新分支
- 或使用 `isolation: "worktree"` 自動隔離
- 禁止共用分支

## 實際案例（觸發次數統計）

| 日期 | 誤判類型 | 後果 |
|------|---------|------|
| 2026-04-09 | 模式 A | 不必要的重新派發 |
| 2026-04-10 | 模式 A | 不必要的重新派發 |
| 2026-04-10 | 模式 C | 共用分支失去隔離 |
| 2026-04-10 | 模式 B | 代理人仍在執行時 commit |
| 2026-04-12 | 模式 D | 寫失敗分析/建 handoff，task-notification 到達後全部回退更正 |
| 2026-04-15 | 模式 E | Phase 4b 重構派發後信任 Hook 廣播+dispatch 清空+無 commit，準備走失敗 SOP，用戶打斷指正代理人實為 running（觸發 W10-059 ANA） |

> 具體案例細節保留在各專案 worklog，此表僅記錄發生頻率和誤判分布。

## 關聯

- **相關模式**: PC-039（worktree 未合併不可見）
- **收編的歷史紀錄**: PC-070（模式 E 獨立文件，保留為歷史案例）
- **PM 規則**: .claude/pm-rules/agent-failure-sop.md（代理人失敗判斷前置步驟 Step 0.5）
- **觀察工具**: .claude/references/pm-agent-observability.md（四工具分工：Agent 派發、TaskOutput 狀態、SendMessage 通訊、TaskList 清點）

---

**Created**: 2026-04-10
**Last Updated**: 2026-04-15
**Category**: process-compliance
**Severity**: P1（導致重複工作、潛在衝突、判斷錯誤）
**Key Lesson**:
- 派發時記錄數量，收到通知時比對，全部完成才行動（模式 A-C）
- TaskOutput `<status>` 標籤提供安全的 runtime 狀態查詢（模式 D-E）
- Hook 廣播 / dispatch-active.json / git status / ticket Solution 都是**輔助提示**，唯有 TaskOutput `<status>` 是**直接證據**（模式 E）
