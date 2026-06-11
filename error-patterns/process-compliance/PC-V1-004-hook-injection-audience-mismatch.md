# PC-V1-004: Hook 注入訊息受眾錯配（PM-only 訊息注入 Subagent Context）

## 分類

- 類型：Process Compliance（hook 系統設計缺陷）
- 嚴重度：高（指令性訊息可誘導唯讀 subagent 越界執行寫入操作）
- 觸發頻率：中（任何 subagent 觸發 PostToolUse / Stop event 時皆可能）

## 症狀

- Subagent 回報訊息中混入「給 PM 的建議動作」（如「建議 git merge」「確認工作目錄」）
- 唯讀型 subagent（Explore / 審查委員）執行寫入操作（git merge / git checkout）
- Subagent final-message 被 Stop hook 訊息擠壓，報告本體遺失
- PM 需從 transcript 手動提取 subagent 報告

## 根因

Hook 輸出透過 additionalContext / systemMessage 注入 LLM context，但未區分受眾：

1. **PostToolUse hook 缺 subagent 偵測**：PM-only 訊息（commit 格式提醒、測試結果分析、ticket sync 提醒）注入 subagent context，subagent 將其視為自身任務指令。
2. **Stop hook systemMessage 在 subagent 觸發**：Stop event 在 subagent 結束時亦觸發，systemMessage 注入 subagent 最後 context 而非 PM。關鍵 hook 已修復加入偵測，但新 hook 可能重蹈覆轍。
3. **hook 輸出無受眾標記（audience marker）機制**：CC runtime 層不支援「此訊息僅限 PM」語義，所有 additionalContext 對觸發方的 LLM 一視同仁。

**Why**：hook 開發時的隱含假設是「觸發者 = PM 主線程」，但 PostToolUse / Stop event 對 subagent 同樣觸發，假設靜默失效。

**Consequence**：入口方向——指令性注入誘導唯讀 subagent 越界（破壞職責分離與 git 歸屬鏈）；出口方向——subagent final-message 被擠壓，PM 驗收依據遺失，需 transcript 手術提取。

## 案例

- 五委員審查輪 5/5 報告本體被 Stop hook 訊息擠掉（出口方向；1.0.0-W1-060 證據鏈）
- Explore 唯讀委員被注入「git merge」建議後實際執行 merge（入口方向；transcript WRITE-CMD 證據）

## 防護

**Action**（三層）：

| 層次 | 防護 | 狀態 |
|------|------|------|
| A. 短期（IMP） | 缺 subagent 偵測的 PostToolUse:Bash hook 加入 `is_subagent_environment()`（hook_utils/hook_io.py）早期跳過 | spawn IMP 追蹤 |
| B. 中期（DOC） | hook 開發 checklist 規則：任何輸出 additionalContext / systemMessage 的 hook 必須評估 subagent 受眾適切性，列入新 hook 審查強制項 | spawn DOC 追蹤 |
| C. 長期（ANA） | 評估受眾標記機制：AGENT_PRELOAD 教 subagent 忽略 PM-only 前綴，或 CC runtime 層級方案 | spawn ANA 追蹤 |

**識別訊號**：subagent 回報含「給 PM」「建議執行」等第三方視角指令；唯讀 agent 的 transcript 出現寫入命令；hook 原始碼有 additionalContext / systemMessage 輸出但 grep 不到 `is_subagent_environment`。

## 相關文件

- `.claude/hooks/hook_utils/hook_io.py` — `is_subagent_environment()` helper
- `.claude/rules/core/quality-baseline.md` 規則 4 — Hook 失敗可見性（互補：本 PC 處理「成功但受眾錯配」）
- `.claude/agents/AGENT_PRELOAD.md` — 長期防護 C 的落點候選

---

**Last Updated**: 2026-06-11
**Version**: 1.0.0 — 自 hook 注入雙向污染 ANA 結論建立（症狀/根因/案例/防護，含三層防護 spawn 對應）
