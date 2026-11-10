<!-- section: 待辦與來源（flutter-balance） owner: flutter-balance-77 -->
## 待辦與來源（flutter-balance）

本節只列與本 issue 直接相關的票。同主題（並行 session 協調）的完整待辦清單住在 `#77` 的「待辦與來源（flutter-balance）」，不在此重抄。

### 已落地的修復（三張，皆 completed，內容已在 canonical）

| 來源票 | 做什麼 | acceptance 條數 | 優先級 | 階段 | 狀態 |
|--------|--------|----------------|--------|------|------|
| `0.2.1-W3-1205` | SubagentStop 清理改為標記式，entry 保留並寫入 `turn_ended_at`；[WAIT]／[OK] 廣播改依 `still_running` 子集判斷（落地版本：v2.50.4，commit `33d622816`） | — | — | 本版 | 完成 |
| `0.2.1-W3-1214` | 改用 dispatch 時可得的 agent_handle 前綴比對，取代 `tool_response.agentId` 精準比對（落地版本：v2.50.6，commit `9e6a4b4f6`） | — | — | 本版 | 完成 |
| `0.2.1-W3-1154` | idle agent 回收 SOP 的觸發層與狀態列顯示語意（落地版本：v2.50.6 同批） | — | — | 本版 | 完成 |

### 待處理（收束時 pending，已 closed，知識住址為本 issue）

| 來源票 | 型別 | 做什麼 | acceptance 條數 | 優先級 | 階段 | 狀態 |
|--------|------|--------|----------------|--------|------|------|
| `0.2.1-W3-1242` | IMP | 派發記錄的釋放點設計。原票面為「complete／close 時清除條目」，前提部分證偽後須改以「保留期內 entry 的宣告 files 是否仍應鎖住路徑」為題，三個候選方向與代價見「問題與方案」 | 3 | P1 | 本版 | 待裁票 |
| `0.2.1-W3-1094` | ANA | 驗證 `SubagentStop` input 的欄位關聯性。前提已證偽（agent_handle 前綴比對已提供識別路徑），不再需要 | 1 | P2 | 本版 | 待裁票 |

取回原票的 acceptance 與 `where.files` 用 `ticket track query <closed-id>`，不重寫。`0.2.1-W3-1242` 的 `where.files` 宣告 `dispatch_tracker.py` 位於 ticket skill 的 lib 目錄，實際位於 `.claude/lib/`，重新裁票時須更正——該錯誤本身是 `#77`「當前結論」第四節所述路徑檢查盲區的第三個實例。

### 跨 consumer 待補

雙向驗證（代理人存活時 DENY 恢復、真正終止後記錄清除）尚無任何 consumer 完成，目前只有原始碼形態與現場 entry 分佈的靜態查證。任一 consumer 完成後應以 `update` 覆蓋「當前結論」記錄結果。

來源票對照：本 consumer 派發票 `0.2.1-W3-1267.7` 的 Test Results。
