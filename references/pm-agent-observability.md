# PM 背景代理人觀察指南

本文件整合 PM（主線程）可用於觀察背景代理人狀態的所有工具，指引正確使用時機和安全邊界。

> **核心問題**：PM 派發背景代理人後，如何知道「代理人現在在做什麼？完成了嗎？留下了什麼？何時完成？」而不違反 PC-050 防護規則？

---

## 五工具分工總覽

| 工具 | 回答的問題 | 資料類型 | 更新時機 | 誰維護 |
|------|-----------|---------|---------|-------|
| `dispatch-active.json` | 我派發了幾個？Hook 認為哪些仍活躍？ | 持久化（JSON 檔案） | 派發時寫入、SubagentStop 時精準清理 | `dispatch-record-hook` + `subagent-stop-dispatch-cleanup-hook` |
| **TaskOutput** | 這個特定代理人現在還在執行嗎？ | 即時查詢（tool call） | 代理人生命週期內任意時刻 | CC runtime |
| `agent-commit-verification-hook` | 代理人留下了什麼 git 證據？ | 完成時觸發 | SubagentStop（代理人真正完成後） | Hook 自動 |
| **SubagentStop event** | 代理人真正停止了嗎？ | 事件驅動（Hook 觸發） | CC runtime 保證代理人停止時 | CC runtime + SubagentStop hooks |
| completion notification | 代理人何時完成？結果是什麼？ | 事件驅動（system-reminder） | 代理人完成瞬間 | CC runtime |

**設計原則**：五工具**互補非替代**。PM 應在不同場景選擇對應工具，禁止以單一工具推論全部資訊。

> **SubagentStop 是可信完成訊號**（CC runtime 保證代理人真正停止才觸發），取代先前 PostToolUse(Agent) 的不可靠完成推論（PC-050 模式 E 根因解法）。dispatch-active.json 的 [OK]/[WAIT] 廣播現由 SubagentStop handler 驅動，延遲 < 1s。

---

## 工具使用範本

### 1. dispatch-active.json（計數 Source of Truth）

**適用場景**：
- 派發後清點（確認派發數量正確）
- Checkpoint 1.85 代理人清點（禁止繼續條件）
- 完成確認 SOP 步驟 1
- 失敗判斷前置步驟 Step 0

**呼叫範本**：

```bash
cat .claude/dispatch-active.json | python3 -c "
import json, sys
d = json.load(sys.stdin)
if d:
    print('[WAIT] 仍有 {} 個代理人在執行：'.format(len(d)))
    for x in d:
        print('  - {}'.format(x.get('agent_description', '?')))
else:
    print('[OK] 所有代理人已完成。')
"
```

**限制**：
- 不能告訴你「某個特定代理人現在是否仍活著」（Hook 可能延遲清理或 race）
- 不能告訴你代理人進度（只有「有活躍派發」或「無活躍派發」二元狀態）

---

### 2. TaskOutput（即時狀態查詢）

> **注意**：TaskOutput 是 Claude Code **deferred tool**，新 session 首次使用前必須執行 `ToolSearch("select:TaskOutput")` 載入 schema，否則直接呼叫會得到 `InputValidationError`。deferred tools 概念和完整清單見 `.claude/skills/search-tools-guide/SKILL.md` 的「Claude Code Meta-Tools」章節。

**適用場景**：
- 懷疑某個背景代理人未完成但 task-notification 未到達
- 失敗判斷前置步驟 Step 0.5（見 pm-rules/agent-failure-sop.md）
- 多代理人派發時確認特定代理人是否仍在執行

**呼叫範本**：

```
# Step 1：首次使用前載入 schema（若本 session 已載入可跳過）
ToolSearch(query="select:TaskOutput")

# Step 2：呼叫（schema 載入後）
TaskOutput(
  task_id=<agentId>,      # Agent tool 返回的 agentId 即是 task_id
  block=false,            # 非阻塞，立即返回
  timeout=3000            # 3 秒超時
)
```

**返回值標籤解讀**：

| 標籤 | 允許讀取 | 用途 |
|------|---------|------|
| `<status>` | 允許 | `running` / `completed` / `error` — 唯一可信的狀態來源 |
| `<task_type>` | 允許 | 確認是 `local_agent`（非 bash / remote） |
| `<retrieval_status>` | 允許 | `not_ready` / `ready` — 指示 output 是否完整 |
| **`<output>` body** | **禁止推論** | 流式 JSONL transcript，可能數十 KB 污染 context；禁止從內容推論代理人狀態（PC-050 模式 D） |

**Context 污染警告**：

TaskOutput 返回值**包含截斷的 `<output>` body**（JSONL transcript）。即使標記 `<retrieval_status>not_ready</retrieval_status>`，transcript 仍會夾帶數十 KB 的工具呼叫歷史。

PM **必須紀律性只讀狀態標籤**，忽略 `<output>` 內容。若需深入檢視代理人工具呼叫，應等 `<task-notification>` 到達後做（完整摘要），而非從中間狀態推論。

**限制**：
- 無法回答「代理人做了什麼 git commit」（需 agent-commit-verification-hook）
- 無法回答「派發總數」（需 dispatch-active.json）
- `<output>` body 若被讀入會觸發 PC-050 模式 D 防護規則

---

### 3. agent-commit-verification-hook（完成時 git 證據）

**適用場景**：
- 代理人完成後，PM 需要知道「在哪個分支做了什麼變更」
- 判斷代理人是否跳過 commit（PC-024）
- 判斷 worktree / feature 分支是否有未合併 commit

**觸發時機**：PostToolUse（Agent），自動觸發，無需 PM 手動呼叫。

**輸出形式**：代理人完成後的 system-reminder，格式：

```
[Agent Commit 驗證警告]
代理人描述: <description>
未 commit 的檔案: <list>
建議動作: git add / commit / discard
```

**限制**：
- 只在代理人完成時觸發，無法查詢執行中狀態
- 只檢查 git 變更，不檢查工作內容品質

---

### 4. completion notification（事件驅動）

**適用場景**：
- 代理人完成的權威通知（唯一可信代表「代理人真正完成」）
- 觸發 Checkpoint 1.85 代理人清點和後續驗收

**形式**：system-reminder，下一次 PM 回合開始時送達：

```
<task-notification>
<task-id>xxx</task-id>
<output-file>/private/tmp/.../tasks/xxx.output</output-file>
<status>completed</status>
<summary>Agent "..." completed</summary>
<result>...完整結果摘要...</result>
</task-notification>
```

**PM 處理規則**：
- `<status>completed</status>` + `<result>` 才是權威結果
- 禁止從 `<output-file>` 路徑自行讀取推論（PC-050 模式 D）
- 禁止在 task-notification 到達前寫失敗分析

**限制**：
- 事件驅動，PM 無法主動觸發
- 若代理人永遠不結束（卡住），notification 不會到達

---

## 決策樹：我該用哪個工具？

```
我需要知道什麼？
├── 派發了幾個代理人？還有幾個活躍？
│   └── dispatch-active.json
│
├── 某個特定代理人現在還在執行嗎？
│   └── TaskOutput（只讀 <status>）
│
├── 代理人完成了嗎？結果是什麼？
│   └── 等 completion notification（不主動查）
│
├── 代理人留下了什麼 git 證據？
│   └── agent-commit-verification-hook（自動觸發，讀 system-reminder）
│
└── 代理人在執行什麼 tool call / 讀什麼檔案？
    └── 禁止查詢（PC-050 模式 D 防護）
```

---

## 常見錯誤模式對照

| 錯誤 | 違反 | 正確做法 |
|------|------|---------|
| 看主倉庫 `git status` 沒變更就判失敗 | PC-050 模式 A | 先檢查 worktree + feature 分支（pm-rules/agent-failure-sop.md 失敗判斷前置步驟） |
| 讀 `/private/tmp/.../tasks/xxx.output` 推論代理人是否卡住 | PC-050 模式 D | 呼叫 TaskOutput 只讀 `<status>` |
| 代理人未即時完成就自己寫產品程式碼 | PC-045 | 派發後切去做其他 Ticket 準備工作，等通知 |
| 完成通知到達立刻 commit 忘記其他代理人 | PC-050 模式 B | 查 dispatch-active.json 確認全部完成（Checkpoint 1.85） |
| 看到 Hook 廣播「所有代理人已完成」+ `git status` 空就判失敗 | PC-050 模式 E / PC-070 | Step 0.5 強制 TaskOutput `<status>` 查詢；生成 2+ 假設（A 失敗/B 仍在工作） |

---

## Hook 廣播訊號可靠度表（PC-050 模式 E / PC-070）

**核心結論**：Hook 廣播訊號與 CC runtime agent 真實完成狀態不同步；只有 `TaskOutput <status>` 為唯一直接可信證據。

| 訊號類型 | 性質 | 可靠度 | PM 允許的推論強度 |
|---------|------|--------|-----------------|
| `PostToolUse:Agent hook additional context` 廣播 | Hook 自行維護，邏輯可能誤觸 | 中 | 提示性，非結論性 |
| `dispatch-active.json` 空 | Hook 清除邏輯早於 agent 真實完成 | 中 | 配合其他訊號，不單獨使用 |
| 目標檔案 `git status` 無變更 | 代理人工作中段可能尚未落盤 | 低（無鑑別力） | 不具失敗判定鑑別力 |
| ticket Solution 區塊仍為模板 | 代理人通常尾段填寫 | 低（無鑑別力） | 不具失敗判定鑑別力 |
| **`TaskOutput <status>`** | CC runtime 直接查詢 | **高**（唯一直接證據） | 可作最終判定 |

**派發時間閾值規則**：

| 派發距今時間 | Hook 訊號可用於判失敗？ | 強制動作 |
|------------|---------------------|---------|
| < 2 分鐘 | **否** | Step 0.5 強制 TaskOutput status 查詢 |
| 2-5 分鐘 | 建議搭配 Step 0.5 | 推薦 TaskOutput 查詢 |
| > 5 分鐘 | 可作輔助 | 仍需完整失敗判斷前置步驟 |

> 完整防護規則和案例：`.claude/error-patterns/process-compliance/PC-050-premature-agent-completion-judgment.md` 模式 E，以及 `.claude/error-patterns/process-compliance/PC-070-pm-hook-signal-agent-failure-inference.md`（併入 PC-050 模式 E 的歷史紀錄）。

### CC 2.1.161 #18 修復標註：subagent 卡 running 顯示（已消解）

**修復原文**（CC 2.1.161 release notes）：

> Fixed completed subagents getting stuck showing as running when an error occurs while finalizing their result.

**Why**：PM 背景派發代理人後，偶會觀察到「TaskOutput 顯示 running，但無新 output 出現」的詭異狀態，導致無法判斷代理人是卡住還是快完成。根因之一是代理人已完成，但 finalize 過程中出錯，導致 TaskOutput 狀態未正確轉為 completed。此修復由 CC 2.1.161（2026-06 發布）消解。

**Consequence**：修復前，PM 遇到此狀況時無法確定是：(A) 代理人確實卡住（需介入），(B) 代理人已完成但狀態更新延遲（應等待）。必須依靠額外判斷線索（Hook 訊號、git status）側面推斷，增加歸因困難（PC-104 痛點）。修復後，「running 但無 output」的情況中，finalize 出錯這個根因已排除。

**Action**：升級至 CC 2.1.161 後，遇「TaskOutput 顯示 running 但無新進展」時可更有信心地假設代理人已完成，但仍應保持謹慎：

| 情境 | 修復前判斷困難 | 修復後簡化 | 注意 |
|------|-------------|----------|------|
| TaskOutput running + 無新 output >= 10s | 可能是 finalize 出錯或卡住 | 更可能是代理人已完成（finalize 出錯排除） | 仍有其他原因：網路中斷、代理人 OOM、系統崩潰 |
| TaskOutput running 但 dispatch-active.json 已清空 | 衝突訊號，歸因複雜 | 更可信：代理人已完成，finalize 出錯被修復 | 配合 SubagentStop event 最終確認 |

**仍需保持警惕的其他原因**：

- **網路中斷**：代理人完成但回傳結果時網路斷開，TaskOutput 仍卡 running
- **代理人 OOM / 系統資源耗盡**：代理人執行卡在 finalize 前置步驟，無法到達 finalize
- **環境罕見競態**：應用層與 runtime 層同步問題

**建議流程**：若遇此狀況，依序：

1. 查 `dispatch-active.json`（若空，代理人應已完成）
2. 查 SubagentStop event 日誌（若有，代理人已正式停止）
3. 強制 TaskOutput 查詢（確認最新狀態）
4. 若確實卡住，檢查機器網路和資源狀態

---

## 與現有規則的銜接

| 文件 | 引用本指南的情境 |
|------|----------------|
| `.claude/pm-rules/agent-failure-sop.md` 失敗判斷前置步驟 | Step 0.5 呼叫 TaskOutput 時引用本指南的安全範本 |
| `.claude/pm-rules/agent-failure-sop.md` 代理人完成確認 SOP | 補充驗證工具章節引用本指南的 TaskOutput 限制 |
| `.claude/error-patterns/process-compliance/PC-050-...md` | 「TaskOutput 安全使用範本」章節 = 本指南章節 2 的子集 |
| `.claude/pm-rules/completion-checkpoint-rules.md` Checkpoint 1.85 | 代理人清點使用 dispatch-active.json（本指南章節 1） |

---

## 代理人結束狀態協議（W17-010）

為讓 PM 從代理人 session 結束後能**可靠判斷結果**，代理人於 ticket body 中維護兩個結構化 section：

### NeedsContext Section（資料缺口回報）

代理人發現 context 不足時寫入 `## NeedsContext`，建議子項：

- **缺失項**：具體指出需要的 context 是什麼
- **觸發位置**：檔案:行號 或 決策點
- **影響**：缺料導致無法完成哪些 acceptance
- **建議補料**：PM 可採取的補充動作
- **重派成本**：若需重派所需 token/context 估算

寫入方式：

```bash
ticket track append-log <ticket-id> --section "NeedsContext" "$(cat <<'EOF'
- **缺失項**: 未找到 X 模組的介面定義
- **觸發位置**: src/foo.py:42
- **影響**: acceptance 第 2、3 項無法完成
- **建議補料**: 提供 X 模組 API 文件
- **重派成本**: 約 10K tokens
EOF
)"
```

寫入後 `needs-context-listener-hook.py`（PostToolUse:Bash）輸出 systemMessage 提示 PM 補料。

### Exit Status Section（結束狀態 schema）

代理人結束時以 YAML 區塊寫入 `## Exit Status`：

```yaml
status: needs_context    # success|needs_context|blocked|partial_success|failed
reason: "X 模組介面未定義"
confidence: 0.8
acceptance_met: [0, 1]
acceptance_unmet: [2, 3]
artifacts:
  - src/foo.py
context_dependencies:
  - X 模組 API 文件
estimated_recovery_effort: "10K tokens"
```

**Exit code 對應**：

| status | exit code | PM 處置 |
|--------|-----------|---------|
| success | 0 | Checkpoint 1 完成，進入 commit |
| partial_success | 0 | 驗收部分 AC，決定是否拆子任務 |
| needs_context | 2 | 讀 NeedsContext 補料後重派 |
| blocked | 2 | 釐清阻塞源後解鎖或升級 |
| failed | 1 | 走 agent-failure-sop.md 流程 |

### PM 讀取流程

```bash
ticket track full <ticket-id>
# 檢視 Exit Status YAML → 若為 needs_context → 檢視 NeedsContext → 補料 → 重派
```

---

## 附錄：外部觀察工具速查（補充，非取代既有五工具）

### `claude agents --json`（v2.1.145+）

Claude Code CLI 提供的外部觀察指令，列出當前機器上所有活躍 Claude Code sessions。

**Why 補充非取代**：粒度為 session 級（非 agent/dispatch 級），無法區分同一 session 內的多個 subagent。既有五工具（dispatch-active.json / TaskOutput / agent-commit-verification / SubagentStop / transcript_tail_reader）涵蓋 agent 級觀察，此指令僅作為 session 存活性外部驗證。

**輸出 schema**：

| 欄位 | 類型 | 說明 |
|------|------|------|
| `pid` | int | Process ID（可用於 OS 層存活性驗證） |
| `cwd` | string | Session 工作目錄 |
| `kind` | enum | `interactive` / `background` |
| `startedAt` | int (ms) | Session 啟動 timestamp |
| `sessionId` | UUID | Session 唯一識別 |
| `name` | string (optional) | Session 名稱（背景 session 常有） |
| `status` | string (optional) | 觀察值：`idle` / `busy` |

**適用情境**：

| 情境 | 用途 | 與五工具關係 |
|------|------|-------------|
| Session 存活性檢查 | `claude agents --json` + pid 比對，確認 session 還活著 | 補強 PC-070 的 hook 訊號可靠度 |
| Orphan dispatch 偵測 | 若 dispatch-active.json 有記錄但 `claude agents --json` 無對應 pid，視為 orphan 主動清理 | 補強 dispatch-active.json 的清理機制（未實作） |
| 跨 session 並行觀察 | 看是否有其他 session 在同一 cwd 工作 | 補強 PC-076 / PC-078 並行污染診斷 |

**不適用情境**：

| 情境 | 限制 | 替代工具 |
|------|------|---------|
| 判斷特定 subagent 是否完成 | 不列出 subagent | TaskOutput |
| 讀取 agent 最後訊息 | 無 transcript 內容 | transcript_tail_reader |
| 判斷 agent 是否 commit | 無 git 證據 | agent-commit-verification-hook |
| 取代既有五工具 | 粒度不匹配（session vs agent） | 仍使用五工具 |

> **未來升級重評觸發條件**：Claude Code 後續版本若擴充 subagent 級 JSON 輸出（含 agent_id / task / files），需重新評估是否整合進五工具體系（建 IMP ticket）。

---

**Last Updated**: 2026-06-03
**Version**: 1.4.0 - 新增「CC 2.1.161 #18 修復標註：subagent 卡 running 顯示（已消解）」段落，記錄 finalize 出錯卡 running 的平台修復及對 PM 狀態判讀的影響（0.19.1-W1-010 標註落地）

**Version**: 1.3.0 - 新增「附錄：外部觀察工具速查」段落，記錄 `claude agents --json` (v2.1.145+) schema 與適用 / 不適用情境（W3-027 ANA 方案 D 落地，W3-027.1）

**Version**: 1.2.0 - 新增「代理人結束狀態協議」（W17-010 三 IMP 合併：NeedsContext section + Exit Status YAML schema + needs-context-listener-hook）

**Version**: 1.1.0 - 新增 Hook 廣播訊號可靠度表 + 派發時間閾值規則（PC-050 模式 E / PC-070 防護）；常見錯誤模式新增 Hook 訊號誤判條目
**Source**: TaskOutput 對 local_agent 狀態查詢的實證結論 + agent-failure-sop.md 與 PC-050 的 TaskOutput 安全規則升級 + W10-059 ANA / W10-061 防護強化
