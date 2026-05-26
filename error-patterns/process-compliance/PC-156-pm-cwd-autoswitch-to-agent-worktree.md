# PC-156: PM cwd auto-switch 到 agent worktree

> **錯誤類別**：流程合規（cc runtime 行為認知缺口）
> **嚴重度**：中（不阻擋但易造成 commit/merge 落點錯誤、與預期不符）
> **發現案例**：0.19.0-W1-048.5.1 thyme isolation:worktree 派發後

---

## 症狀

PM 派發 `isolation: "worktree"` agent 後（特別是 task-notification 到達時），cc runtime 將 PM 的 cwd 自動切到 agent worktree（`.claude/worktrees/agent-XXXXXXXX`）。PM 後續所有 git 操作（commit / merge / status）以及 file 操作（Read / Write）全部發生在 agent worktree branch（`worktree-agent-XXXXXXXX`）內。

但這個切換對 PM 不透明：
- task-notification 訊息不告知 cwd 已變
- pwd 不會主動執行，PM 預設假設仍在主 repo
- 直到 hook 提示「待合併 commit」才會察覺切換已發生

## 根因

cc runtime 為了讓 PM 接續處理 agent 結果（例如 merge worktree、commit 補強），設計可能會自動切 PM cwd 進 agent worktree。但這個設計沒有顯式告知 PM，且現行 hook（branch-status-reminder / SessionStart）只在 session 啟動時提示，不會在每次 cwd 切換時提示。

## 案例：W1-048.5.1 thyme 派發

| 時序 | 動作 | cwd / branch |
|------|------|-------------|
| T+0 | PM 派發 thyme（isolation:worktree, background） | `/Users/.../book_overview_v1` / main |
| T+1958s | task-notification 到達（thyme token 耗盡中斷） | 自動切到 `.../.claude/worktrees/agent-a4473995e44001eef` / `worktree-agent-a4473995e44001eef` |
| T+1959s | PM 執行 `git log` 確認狀態 | 看到 d0d8b965 / 598d99a4 stash refs，誤判仍在 main |
| T+2000s | PM 執行 `npm test`、`git diff`、`git status` | 全在 agent worktree 內 |
| T+2050s | PM `git commit` 建 W1-057 ticket | commit 落到 `worktree-agent-a4473995e44001eef` branch |
| T+2100s | hook 提示「待合併 commit」 | PM 才察覺 cwd 早已切換 |

## 防護要點

### 規則層（自律）

| 動作時機 | 強制查詢 |
|---------|---------|
| 派發 isolation:worktree agent 後 | `git branch --show-current` + `pwd` |
| 接到 task-notification 後 | 第一個動作必查 cwd 與 branch |
| commit 前 | 確認 branch 名稱不是 `worktree-agent-*` |
| 看到「待合併 commit」hook 提示 | 表示 commit 落 agent worktree，需手動 merge 回 main |

### Hook 層（強制，建議實作）

- 在 task-notification 觸發後，若偵測 cwd 為 `.claude/worktrees/agent-*`，hook 立即輸出 warning 告知 PM 已切換
- 在每次 `git commit` 前的 PreToolUse hook 偵測：若 branch 為 `worktree-agent-*` 且 commit 訊息含「main」字眼或 ticket 標題，警示「commit 不會進 main」

## 修復建議

短期（自律）：PM 在派發 isolation:worktree agent 之後，每次接 task-notification 都執行 `git branch --show-current && pwd` 確認位置。

中期（hook）：
1. 建 hook 在 task-notification PostUser hook 偵測 cwd 與 branch 並 emit warning
2. 建 hook 在 commit PreBash hook 偵測 branch 名稱 + 跨參考檢查

長期（cc runtime）：希望 cc runtime 改為「PM cwd 切換時主動 emit notification」，或 PM 工具集提供 `current-context` 查詢，讓 cwd 切換明確化。

## 相關規則

- `.claude/rules/core/pm-role.md` — PM 角色行為準則（含 session-start 全量清點，但未涵蓋派發後 cwd 切換）
- `.claude/skills/worktree/SKILL.md` — Agent isolation worktree 章節（提到殭屍清理，但未提 PM cwd 切換）
- `feedback_pm_cwd_autoswitch_agent_worktree`（memory）

## 追蹤

- W1-048.5.1 派發案例（2026-05-23）— 首次發現
- 建議：建立 follow-up DOC ticket 補完防護機制（hook 層 + 規則層）

---

**Last Updated**: 2026-05-23
**Version**: 1.0.0
**Status**: Discovered (需後續 hook 層落地)
