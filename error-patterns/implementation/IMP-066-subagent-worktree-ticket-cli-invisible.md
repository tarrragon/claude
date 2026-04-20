---
id: IMP-066
title: subagent 在 isolation:worktree 下透過 ticket CLI 看不到主 repo 新建 ticket
category: implementation
severity: medium
status: active
created: 2026-04-18
related:
- ARCH-015
- PC-019
---

# IMP-066: subagent 在 isolation:worktree 下透過 ticket CLI 看不到主 repo 新建 ticket

## 問題描述

PM 主線程新建 ticket → `git commit` 到主 repo main → 派發 subagent 帶 `isolation: "worktree"` → subagent 執行 `ticket track full <new-id>` 回報 `找不到 Ticket`。

本事件觸發場景：PM 在同一 session 先 commit 新 ticket 再派發 subagent，subagent 看不到新 ticket。

## 根本原因

CC isolation:worktree 建立的 subagent worktree 並非從當前 HEAD checkout：

1. CC runtime 為 subagent 建立獨立 worktree（路徑形如 `.claude/worktrees/agent-<hash>/`）
2. 該 worktree 的 HEAD 停在某較早的 commit（實測 `2e1ae8db`，落後 main 數個 commits）
3. subagent 的 ticket CLI 從 worktree 的 docs/ 讀取 ticket 檔案
4. 新 ticket 的 .md 檔案在那個較早的 commit 中不存在
5. ticket CLI 因此回報 `找不到 Ticket`

## 受影響行為

- `ticket track full <id>`：找不到新建的 ticket
- `ticket track list`：列表少了新 ticket
- `ticket track append-log <id> ...`：無法記錄到新 ticket
- `ticket track complete <id>`：失敗

**Read 主 repo 絕對路徑不受影響**：subagent 可 Read 主 repo 任何路徑（見 ARCH-015 更新後的 Read 行為）。

## 正確做法

### 派發 prompt 規則

派發含「需存取新 ticket」的 subagent 時，**禁止 prompt 使用 ticket CLI 讀取新 ticket**。改用：

1. **Read 絕對路徑讀 ticket md**：
   ```
   Read /Users/tarragon/Projects/book_overview_v1/docs/work-logs/v0/v0.18/v0.18.0/tickets/{ticket-id}.md
   ```

2. **結構化結果由 subagent 回傳 PM**（不派 ticket CLI 寫入）：
   subagent 在最終 response 以結構化文字返回結果；PM 收到後從主 repo 執行 `ticket track append-log` 寫入。

### Prompt 最小範本

```
Ticket: {ticket-id}

Read `{absolute-path-to-ticket.md}` 取得 Context Bundle，執行步驟並將結果以結構化文字返回 PM（不呼叫 ticket CLI，不 git commit）。
```

## 為何 isolation:worktree 不同步主 repo

推測原因（未證實，需 Anthropic 確認）：
- isolation:worktree 的設計意圖是提供固定 baseline 避免並行 agent 互相干擾
- 若每次都以最新 HEAD 為 base，並行 agents 會在不同 HEAD 下工作，違反 isolation 初衷
- 因此 CC 可能選擇以 session 啟動時或某 checkpoint 為 base 建立 worktree

**實用結論**：不要假設 subagent worktree 與 main 同步。Commit 後派發的 ticket 需改用絕對路徑 Read。

## 相關 Pattern

- ARCH-015: subagent .claude/ 寫入 hardcoded 保護（2026-04-18 修正為「target 是否在主 repo 樹內」）
- PC-019: worktree-merge-state-loss（派發前必須 commit 主 repo 變更）
- IMP-047: worktree-subagent-read-only-exhaustion

## 觸發案例

2026-04-18（W5-047.4.1/.2/.3 首輪派發事件）：

PM 新建 W5-050 umbrella + W5-050.1/.2/.3 子任務 → commit c35da16b → 派發 3 個 thyme subagent with `isolation: worktree` → 3 agents 全部回報「Ticket 0.18.0-W5-050.X does not exist」。agent 實測 worktree HEAD 為 `2e1ae8db`（落後 c35da16b 至少 4 commits）。

修復：PM 改派發 prompt 為 Read 絕對路徑 + 結構化結果返回，第二輪派發全部成功。

---

**Last Updated**: 2026-04-18
