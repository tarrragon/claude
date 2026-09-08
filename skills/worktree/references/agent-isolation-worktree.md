# Agent Isolation Worktree（cc 自動建 worktree-agent-*）

> 何時讀：遇到 cc runtime 自動建立的 agent worktree 相關議題時——worktree base 落後 main、dart MCP 寫入洩漏到主 repo、ticket 狀態該寫進哪個倉庫、殭屍 worktree 累積、或 EnterWorktree mid-session 切換後的查核。`SKILL.md`〈Agent isolation worktree〉速查表逐項路由到本檔對應節。
>
> 同目錄：子命令（create/status）參數與範例在 `subcommands.md`；核心功能、快速開始、使用場景、Hook 整合、常見問題留在 `SKILL.md`。
>
> 溯源：自 `SKILL.md` 的〈Agent isolation worktree〉節搬移（v1.4.0）。移出理由是該節原佔全檔 50.6% tokens（2,882/5,690），多數讀者只在遇到特定議題時才需要對應細節，不需要每次觸發都載入全部。

本檔說明 Claude Code runtime 自動建立的 agent worktree（與本 SKILL 的人工 `/worktree create` 為不同來源），重點在殭屍累積的成因與專案 GC 對策。

## 機制

Claude Code 的 Agent tool 設定 `isolation: "worktree"` 派發 subagent 時，cc runtime 會自動執行下列動作：

- 在 `.claude/worktrees/agent-XXXXXXXX` 建立隔離 worktree（XXXXXXXX 為隨機 hash）
- 對應分支命名為 `worktree-agent-XXXXXXXX`
- 同時對該 worktree 加 git lock，lock reason 內含 cc CLI process 的 PID，目的是阻止 git 自動 GC 在 agent 執行期間誤清

**Why**：worktree 隔離讓 subagent 的檔案改動與主 repo 解耦，避免並行派發時互相覆蓋；lock + PID 是 cc 對 git GC 的防護，確保長時間 agent 執行不被 `git worktree prune` 中斷。

<!-- rule8-exempt: relocation:自 .claude/skills/worktree/SKILL.md 逐字位置搬移 -->
## Base ref 與隔離邊界（W3-007 / W3-008）

| 議題 | 事實 | 對策 |
|------|------|------|
| worktree base 取自哪裡 | cc runtime 以 `origin/main`（remote-tracking ref）為 base，**非** local main HEAD。local main 領先 origin/main 時 worktree 建在 stale 基底（W3-007 實證） | 派發前先 `git push origin main`；`worktree-commit-before-dispatch-hook.py` 在 origin/main 落後時 stderr 警告 <!-- rule8-exempt: relocation:自 .claude/skills/worktree/SKILL.md 逐字位置搬移 --> |
| daemon-rooted 寫入工具洩漏 | dart MCP（dart fix / dart format）daemon 的 analysis root 在 session 啟動時綁定主 repo，worktree 派發只改 shell cwd，無法切換 daemon root，寫入會洩漏到主 repo（W3-008 根因 2） | worktree 實作 agent **禁用 dart MCP 寫入工具，改用 Bash `dart fix` / `dart format`（尊重 agent cwd）或 Edit** <!-- rule8-exempt: relocation:自 .claude/skills/worktree/SKILL.md 逐字位置搬移 --> |
| ticket CLI auto-commit 洩漏（W3-008 當時） | `paths.py:get_project_root()` 原優先讀 `CLAUDE_PROJECT_DIR`（恆指向主 repo），使 ticket md 寫入與 auto-commit 落在主 repo（W3-008 根因 1） | 當時已修：`get_project_root()` 加 worktree 感知，git root != CLAUDE_PROJECT_DIR 時優先用 git root。**此對策已被下方〈ticket 狀態統一寫入主倉庫〉取代，見該節說明** <!-- rule8-exempt: relocation:自 .claude/skills/worktree/SKILL.md 逐字位置搬移 --> |

**Why**：worktree 隔離只改變 agent 的 shell cwd，對「session 啟動時靜態綁定主 repo 根目錄」的寫入工具（dart MCP daemon）不生效，這類工具的寫入會繞過隔離邊界洩漏到主 repo。

## ticket 狀態統一寫入主倉庫（2026-09-02 起，刻意設計，非洩漏）

上表「ticket CLI auto-commit 洩漏」列記錄的是 W3-008 當時的問題與當時對策：讓 `get_project_root()` 具 worktree 感知，使 ticket CLI 的寫入跟隨 agent 所在 worktree。**該對策已被後續的架構決策取代**——`paths.py:get_ticket_state_root()`（2026-09-02 新增）現為 ticket 狀態操作（`ticket track claim` / `append-log` / `check-acceptance` 等讀寫 ticket md 與其 auto-commit）的唯一根目錄解析入口，其行為與 `get_project_root()` 相反：偵測到呼叫端位於 linked worktree 時，**反向回推主倉庫根目錄**，使 ticket 狀態一律寫入主倉庫，不進 worktree 分支。<!-- rule8-exempt: relocation:自 .claude/skills/worktree/SKILL.md 逐字位置搬移 -->

**Why**：若 ticket 狀態沿用 worktree 感知，多個隔離 agent 各自把票面寫入自己的 worktree 分支，PM 在主倉庫看不到最新狀態（觀察性失效），且 body 內容不會隨 worktree 分支合併帶回主倉庫——受控實驗實測並行派發的 worktree agent 全數出現票面分裂。統一寫入主倉庫消除此分裂，ticket 狀態單一事實來源恆為主倉庫。

**與程式碼提交的分離**：本節僅涵蓋 ticket 狀態（md 讀寫 + auto-commit）。`ticket track commit`（程式碼提交）維持 `resolve_project_cwd` 的原 worktree 感知邏輯不變，程式碼隔離不受影響——worktree agent 的產品碼變更仍 commit 進該 worktree 對應分支，由 PM 之後 `git merge` 帶回主倉庫。也就是說：**程式碼提交走 worktree 分支，ticket 狀態寫入主倉庫**，兩者是不同的 root 解析路徑，不會互相影響。**`--worktree` 旗標為必帶**：`resolve_project_cwd()` 依呼叫當下 process cwd 判斷 repo root，非依檔案實際位置；agent 的 Bash 呼叫依 harness 慣例每次重設回主倉庫 cwd，未帶 `--worktree <該 worktree 絕對路徑>` 時會誤綁主 repo（新檔案無法 add、已修改檔案誤判空 tree 短路），見 ticket skill〈track commit 子命令〉〈`--worktree` 條件〉。

**Consequence（agent 誤讀為缺陷時）**：worktree 內執行 `ticket track full` 讀到的內容與主倉庫一致（非該 worktree 自身分支上的 ticket md 版本），這是設計行為，不是 bug；`ticket track append-log` 等寫入的 commit 會出現在主倉庫的 git log，而非該 worktree 對應分支。誤判為缺陷並嘗試「修復」會反轉此設計，重新引入票面分裂風險。

**Action**：worktree 內需要讀取「該 worktree 自身分支上的 ticket md 版本」時（例如驗證某次寫入是否落在預期分支），改用 `git show <branch>:<path>` 或直接 `cat` 該 worktree working tree 內的檔案，不依賴 `ticket track full` 的輸出——後者恆讀主倉庫。完整理由見 `.claude/skills/ticket/ticket_system/lib/paths.py` 的 `get_ticket_state_root()` docstring；ticket 狀態與程式碼提交分離的說明另見 `.claude/skills/ticket/SKILL.md`「Ticket 狀態與程式碼提交的 root 分離」節。

## 殭屍問題

cc runtime 在 agent 結束或 process 異常死亡時**不會自動 remove** agent worktree。後果：

- 殘留目錄不會自動消失（cc 只 unlock，不 remove，見下方 Lock 行為表）
- `.claude/worktrees/` 下殘留 worktree 目錄，累積佔用磁碟空間
- `git worktree list` 與 statusline 顯示大量無用 entries，干擾人工判讀

**Lock 行為（CC v2.1.157 起的變化）**：

| agent 結束方式 | lock 狀態 | 清理路徑 |
|---------------|----------|---------|
| 正常結束（v2.1.157+） | 自動 unlock | 可直接 `git worktree remove` / `git worktree prune`，免 unlock 前置 |
| process 異常死亡 | 可能殘留「殭屍 lock」（git 看 lock 不看 PID） | 仍需 `git worktree unlock` 前置（見下方〈手動清理指令〉路徑 2） |

**Why**：v2.1.157 起 cc 在 agent 正常結束時主動 unlock worktree（release note：「Worktrees managed by Claude are now left unlocked when the agent finishes」），使 `git worktree remove`/`prune` 能直接清理；但異常死亡（process 被 kill / crash）來不及 unlock，仍會殘留 lock，故 unlock 前置步驟對該情境保留。

**Consequence**：未清理的殭屍 worktree 會無上限累積，每次 cc session 派發 isolation:worktree subagent 都新增一個，數天內可達數十個，污染 git 視圖並佔用 GB 級空間。

**Action**：依賴下方〈專案對策〉自動 GC，或在察覺累積時執行〈手動清理指令〉。

<!-- rule8-exempt: relocation:自 .claude/skills/worktree/SKILL.md 逐字位置搬移 -->
## 專案對策（W17-119.1 SessionStart hook GC）

本專案在 `.claude/skills/worktree/hooks/worktree-zombie-cleanup-hook.py` 實作 SessionStart 觸發的自動 GC，邏輯如下：

| 步驟 | 動作 |
|------|------|
| 1 | 列舉 `.claude/worktrees/agent-*` 下所有 worktree |
| 2 | 解析每個 worktree 的 lock reason，提取 PID |
| 3 | 對 PID 執行死活檢測（`ps -p <pid>`） |
| 4 | PID 已死 → `git worktree unlock` + `git worktree remove --force` |

**安全防護**：

- worktree 內 dirty 檔案數 != 0 時僅輸出警告，不自動清，避免誤刪未保存改動
- 排除建立時間 < 30 分鐘的 worktree，避免清掉剛啟動還沒來得及註冊的 agent
- 透過環境變數開關，可在偵錯時暫時關閉

**Why**：SessionStart 是 cc session 入口，每次新 session 都做一次清理可保證殭屍上限不超過上一 session 累積量。

## 手動清理指令

當自動 GC 失效或要主動清理時，使用以下指令：

```bash
# 列出殭屍（PID 已死的 agent worktree lock）
git worktree list --porcelain | grep "^locked" | grep -oE "pid [0-9]+" | awk '{print $2}' | while read p; do
  ps -p $p > /dev/null 2>&1 || echo "$p dead"
done

# 路徑 1（v2.1.157+ 首選）：清理已 unlock 的殘留（正常結束的 agent worktree）
# agent 正常結束已自動 unlock，prune 可直接回收，無需 unlock 前置
git worktree prune

# 路徑 2（異常死亡殘留 lock 時）：強制清所有 agent worktree（謹慎使用：不檢查 dirty）
git worktree list --porcelain | grep "^worktree .*\.claude/worktrees/agent-" | awk '{print $2}' | while read wt; do
  git worktree unlock "$wt" 2>/dev/null
  git worktree remove --force "$wt"
done
```

**Action**：第一段指令僅列舉，可安全執行確認殭屍數量；**路徑 1（`git worktree prune`）為 v2.1.157+ 首選**，清理正常結束（已 unlock）的殘留，安全且免 unlock 前置；路徑 2 為強制清理（含 unlock），用於異常死亡殘留 lock 的情境，執行前請先用 `git worktree list` 人工確認沒有正在進行中的 agent。

> **絆腳索**：若 `git worktree prune` 實測仍因 lock 無法清理某 worktree，表示該 worktree 屬異常死亡殘留 lock，改走路徑 2（unlock + remove --force）。

## 與人工 /worktree create 的區別

兩者表面都是 git worktree，但來源、生命週期、清理機制完全不同。混淆會導致誤清正在工作的 worktree。

| 維度 | cc Agent isolation:worktree | 人工 /worktree create |
|------|----------------------------|----------------------|
| 觸發者 | cc runtime（Agent tool 自動） | 使用者（本 SKILL） |
| 路徑 | `.claude/worktrees/agent-XXXXXXXX` | `../ccsession-<ticket-id>` |
| 分支命名 | `worktree-agent-XXXXXXXX` | `feat/<ticket-id>` |
| Lock | 自動加 lock（含 PID） | 不加 lock |
| 預期生命週期 | 單次 agent 執行（分鐘級） | 整個 ticket 開發（小時至天級） |
| 清理機制 | cc 不清，依 W17-119.1 hook GC | 使用者手動 `git worktree remove` <!-- rule8-exempt: relocation:自 .claude/skills/worktree/SKILL.md 逐字位置搬移 --> |
| 殭屍風險 | 高（無自動清） | 低（使用者主動管理） |

**Action**：判斷某個 worktree 屬哪一類，看路徑前綴即可（`.claude/worktrees/agent-` vs `../ccsession-`）；自動 GC hook 僅處理前者，後者請使用本 SKILL 的人工流程管理。

## EnterWorktree mid-session 切換（CC v2.1.157）

CC v2.1.157 起 `EnterWorktree` 工具支援**在 session 中途切換** Claude-managed worktree（不必重啟 session），前一個 worktree 的工作狀態保留。

**Why**：可在同一 session 於多個工作目錄間切換（例如特性開發中途切到緊急 bugfix worktree），免去重啟成本。

**Consequence（查核必要性反而上升）**：mid-session 切換使 cwd 落點更易在無感知下改變。若不確認當前所在 worktree 就 commit / merge，變更可能落到非預期分支（與既有「PM cwd 被 runtime 自動切進 agent worktree」風險同源）。

**Action**：

| 時機 | 強制查核 |
|------|---------|
| 派發 isolation:worktree agent 後 | `git branch --show-current` + `pwd` 確認 cwd 落點 |
| 接收 agent task-notification 後 | 同上，確認 commit/merge 目標分支 |
| 主動 EnterWorktree 切換後 | 同上，切換完成立即確認新 worktree 身份 |

切換後 commit/merge 前未查核 → 變更落點不可信，須先 `git branch --show-current` + `pwd` 對齊預期再操作。
