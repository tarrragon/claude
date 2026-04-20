# ARCH-019: Hook Event 時機錯位（啟動 vs 完成職責分掛同一 event）

## 錯誤症狀

Hook 將「啟動時邏輯」與「完成時邏輯」掛在**同一 event** 上，而該 event 的觸發時機與「完成」語意不符。後果：

- 完成邏輯在錯誤時機觸發（例如代理人才剛啟動就被當完成處理）
- 修補三輪皆繞道，無法解決根本時機錯位（只能加 guard 跳過）
- 殘留狀態無法清理（如 `dispatch-active.json` 累積未清記錄）

典型表現（本專案實例）：

- Hook 掛 `PostToolUse(Agent)` 期望在「Agent 完成後」觸發
- 但 `run_in_background: true` 派發時，`PostToolUse(Agent)` 在**代理人啟動時**就觸發
- Hook 邏輯（清理派發記錄、驗證 commit、廣播完成）全部時機錯位

## 根因分析

### 根因 1：event 名稱的語意陷阱

`PostToolUse(Agent)` 字面看像「Agent 結束後」，但語意實為「Agent 工具呼叫的外層 wrapper 結束後」。對於前台同步派發兩者重合；對於 `run_in_background: true`，外層 wrapper 在派發指令送出後立即返回，與代理人實際完成無關。

設計者望文生義選擇 event，未實測驗證觸發時機。

### 根因 2：CC runtime 提供了專用 event 但被忽略

CC runtime 官方支援 `SubagentStop` event，input 含 `agent_id` / `agent_type` / `agent_transcript_path` / `last_assistant_message`，是「代理人真完成」的正確訊號源。

但本專案 75+ hooks 中至少 7 個服務「代理人完成」語意（active-dispatch-tracker、agent-commit-verification、agent-completion-broadcast 等）皆掛 `PostToolUse(Agent)`，未使用 `SubagentStop`。

根因：`hook-architect-technical-reference.md` 將 `SubagentStop` 用途錯標為「防止對話過早停止」，誤導所有 Hook 設計者。

### 根因 3：啟動職責與完成職責混掛同一 event

Hook 同時承擔兩種職責：

- 啟動時邏輯：註冊派發、驗證 prompt、檢查 ticket reference
- 完成時邏輯：清理記錄、驗證 commit、廣播完成

掛在 `PostToolUse(Agent)` 時，啟動邏輯時機正確（前台與背景皆觸發），但完成邏輯在背景模式失效。混掛的 Hook 必須加 `if background_mode: skip` 之類的 guard，這是繞道而非修復。

正確設計應將兩種職責分掛兩個 event：

- 啟動時 → `PreToolUse(Agent)`
- 完成時 → `SubagentStop`（含 `agent_id` 可精準匹配對應派發）

## 防護措施

### 設計層：選 event 前實測觸發時機

新增 Hook 前，必須完成以下檢查：

| 檢查項 | 動作 |
|------|------|
| 字面語意是否符合預期 | 不憑名稱推論，查 hook-spec 確認觸發時機 |
| `run_in_background: true` 行為 | 實測或查文件確認 background 模式下的觸發時機 |
| Hook 職責是否單一時機 | 啟動 vs 完成不可混掛 |

### 規則層：「代理人完成」相關 Hook 必須掛 SubagentStop

新增涉及「代理人完成」語意的 Hook（清理派發、驗證 commit、廣播狀態、handoff 提醒等），**強制使用 `SubagentStop`**。理由：

- 唯一在代理人真完成時觸發的 event
- input 含 `agent_id` 為 source of truth（可精準匹配派發記錄，取代易碰撞的 `agent_description` 字串）
- 同時涵蓋前台與背景派發

### 流程層：Hook 設計審查 checklist

basil-hook-architect 設計審查時必須回答：

- Hook 服務的是「啟動時邏輯」還是「完成時邏輯」還是兩者？
- 若兩者，是否該拆成兩個 Hook 分掛兩個 event？
- 選用 event 在 background 模式的觸發時機是否符合語意需求？

### 檢測手段：殘留狀態即訊號

執行期 Hook 失效的表徵之一：「應被清理的狀態未被清理」（如 `dispatch-active.json` 累積過時記錄）。發現此類殘留時，應質疑：

- 清理邏輯掛的 event 是否在「真完成」時觸發？
- 是否需要遷移到 `SubagentStop`？

## 實戰案例

### 2026-04-14 ~ 2026-04-15：active-dispatch-tracker-hook 三輪繞道

**症狀演進**：

1. **W10-024**：active-dispatch-tracker-hook 在 background 派發時提示誤導（PostToolUse 啟動時就清理派發記錄，但代理人仍在執行）。修補：訊息加三態（背景/前台/未知）區分。
2. **W10-060**：盤點所有 PostToolUse(Agent) 類 Hook（共 7 個），發現相同問題普遍存在。修補：所有 Hook 套用「background 模式跳過邏輯」guard。
3. **W10-061**：PM 代理人狀態查詢防護強化時，發現修補本身仍是繞道——根因是 event 選擇錯誤，PostToolUse(Agent) 從未是「代理人完成」訊號。

**證據**：

- `.claude/hooks/active-dispatch-tracker-hook.py:66` 註解：「背景代理人：PostToolUse 在啟動時即觸發，代理人仍在執行。」
- 當前 session `.claude/dispatch-active.json` 殘留 7 筆未清記錄（agent_description 重複、ticket_id 空），證明清理邏輯失效

**正確解法**：W10-066/067 將 active-dispatch-tracker-hook 和 agent-commit-verification-hook 改掛 `SubagentStop`，依 `agent_id` 精準清理。從根因層消除 PC-050 模式 E（Hook 訊號誤判）。

**教訓**：三輪修補耗費三個 Wave，根因僅是「選錯 event」。若初始設計即知 `SubagentStop` 為代理人完成訊號源，可避免全部繞道。

## 相關規則

- `.claude/error-patterns/process-compliance/PC-050-premature-agent-completion-judgment.md` — 模式 E（Hook 訊號誤判，本 pattern 是其架構根因）
- `.claude/hook-specs/claude-code-hooks-official-standards.md` — CC runtime 9 種 Hook events 規範
- `.claude/methodologies/hook-system-methodology.md` — Hook 設計方法論（待 W10-069 補 Event 選擇與識別碼章節）

---

**Last Updated**: 2026-04-15
**Version**: 1.0.0 — 初始建立
