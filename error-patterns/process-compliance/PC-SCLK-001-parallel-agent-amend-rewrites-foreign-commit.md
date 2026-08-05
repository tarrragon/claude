---
id: PC-SCLK-001
title: 並行 agent 的 git commit --amend 改寫其他執行體的 commit
severity: high
---

# PC-SCLK-001: 並行 agent 的 git commit --amend 改寫其他執行體的 commit

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-SCLK-001 |
| 類別 | process-compliance |
| 風險等級 | 高 |
| 首發時間 | 2026-07-29（1.4.0-W1-011 amend 改寫 1.4.0-W1-003 commit） |
| 姊妹模式 | PC-078（並行 session ticket 狀態誤判，讀取面）、PC-076（前 session 未 commit 遺留）、ARCH-015（worktree 隔離） |

---

## 症狀

多個 agent 在同一工作樹並行執行時，某 agent 執行 `git commit --amend` 補充自己剛才的 commit，實際改寫的卻是另一個 agent 在這段期間新建的 commit。表現為：

1. 該 agent 的變更被折疊進他人的 commit，兩者內容混在同一個 commit
2. 他人 commit 的 hash 改變，其代理人（或 PM）記錄的 hash 失效
3. `git log` 表面正常，無錯誤訊息，需逐 commit 比對 `--stat` 才會發現
4. 若已推送，他人需 force-pull 才能同步；未推送則僅本地歷史受影響

與 PC-078 的區別：PC-078 是**讀取面**誤判（把他人活動誤認為遺留而錯誤處置），本模式是**寫入面**破壞（直接改寫他人已完成的工作記錄）。

---

## 實例（2026-07-29，1.4.0-W1-011 與 1.4.0-W1-003）

事件序列：

| 時刻 | 執行體 | 動作 | HEAD |
|------|-------|------|------|
| T1 | W1-011 agent | `git commit` 自己的分析產出 | `835ccaa` |
| T2 | W1-003 agent | `git commit` 自己的 tracking 遷移 | `939c9bd` |
| T3 | W1-011 agent | `git commit --amend` 補 19 行自檢章節 | `939c9bd` 被改寫 |

T3 的 `--amend` 作用於當下 HEAD，而 HEAD 已在 T2 被另一個 agent 推進。W1-011 的意圖是修改自己在 T1 的 commit，實際改寫了 W1-003 在 T2 的 commit，把 19 行折疊進去。

修復（由發現問題的 agent 自行完成）：`b8bdb09` 還原 W1-003 commit 為其原始 2 檔內容，`8f119e9` 將自己的 19 行獨立成 commit。事後驗證 `git diff 939c9bd b8bdb09` 僅剩 W1-003 自身的 `status: completed` 與 `completed_at` 兩處差異，核心產出（`proposals-tracking.yaml` 114 行變更）逐字一致，無資料遺失。

未推送（`origin/main` 停在事件前的舊 commit）是此次未擴大的關鍵——已推送則需協調 force-push 與他人 reset。

---

## 根因

`git commit --amend` 的作用對象是**執行當下的 HEAD**，不是「我上次建立的那個 commit」。單一執行體的心智模型中兩者等價，因為沒有其他人會推進 HEAD；並行執行體共用工作樹時此等價關係破裂。

三個條件同時成立即觸發：

1. 多個 agent 共用同一工作樹（非 worktree 隔離）
2. 其中一個 agent 在自己 commit 後、amend 前，另一個 agent 完成了 commit
3. amend 方未在執行前重新確認 HEAD 是否仍是自己的 commit

第 3 點是可控環節。前兩點是並行派發的常態，不是異常。

延伸：同源風險存在於所有「以 HEAD 為隱含參數」的 git 操作——`git reset --soft HEAD~1`、`git rebase -i HEAD~N`、`git commit --fixup HEAD`。amend 只是最常用的一個。

---

## 解決方案

### 事後修復（已發生時）

1. 確認範圍：`git show --stat <被改寫的 hash>` 對照 `git reflog` 找出原始內容
2. 拆分：以 `git reset --soft` 退回改寫前狀態，重新建立兩個獨立 commit
3. 驗證：`git diff <原始 hash> <修復後 hash>` 確認他人產出逐字一致
4. 告知：他人記錄的 hash 已失效，須通知其更新引用

### 事前預防（agent 側）

amend 前必須確認 HEAD 仍是自己的 commit：

```bash
# 建立 commit 後記錄自己的 hash
MY_COMMIT=$(git rev-parse HEAD)

# amend 前驗證 HEAD 未被推進
[ "$(git rev-parse HEAD)" = "$MY_COMMIT" ] && git commit --amend || echo "HEAD 已被其他執行體推進，改用新 commit"
```

更簡單且無條件安全的做法：**並行情境下不使用 `--amend`，改為新增一個 commit**。碎 commit 對 ticket 收尾類變更完全可接受，且天然免疫此問題。

### 事前預防（PM 側）

| 情境 | 措施 |
|------|------|
| 派發涉及 git 寫入的並行 agent | Context Bundle 明載「禁用 `--amend` / `reset` / `rebase`，補充內容一律新增 commit」 |
| 檔案修改型並行派發 | 優先採 worktree 隔離（ARCH-015），從根本消除共用 HEAD |
| 收到 agent 回報 commit hash | 以 `git cat-file -t <hash>` 驗證存在性，並在後續引用前重新確認未被改寫 |

---

## 預防措施

| 層級 | 措施 | 狀態 |
|------|------|------|
| Agent 自律 | Context Bundle 加入「並行安全約束」章節，明列禁用 HEAD 隱含參數的 git 操作 | 可立即施行 |
| PM 派發 | 檔案修改型並行任務優先 worktree 隔離 | 既有 ARCH-015 規範 |
| Hook 強制 | PreToolUse 偵測 `git commit --amend` / `git reset` 且當前有 2+ 進行中 ticket 時警告 | 待評估 |

Hook 層可行性備註：判定「是否有其他 agent 並行」可查 `ticket track list --status in_progress` 的筆數，或檢查 subagent 目錄活躍度。此為 WARNING 級即可，不需硬擋（單一執行體的 amend 是合法且常用的操作）。

---

## 相關規則

- `.claude/rules/core/bash-tool-usage-rules.md` 規則三 — 禁止串接 git 寫入操作（同源的 git 並發問題，但聚焦 index.lock 競爭而非 HEAD 漂移）
- `.claude/rules/core/tool-output-trust-rules.md` 規則 5 — 記錄平面不是 ground truth，重大狀態以世界平面為準（本模式的驗證方法論依據）
- `.claude/error-patterns/process-compliance/PC-078-parallel-session-ticket-state-misjudgment.md` — 並行的讀取面失效
- `.claude/pm-rules/parallel-dispatch.md` — 並行派發規範

---

## 關聯 Ticket

- `1.4.0-W1-011`（事件發生與自行修復的 ticket）
- `1.4.0-W1-003`（commit 被改寫的受害方）
