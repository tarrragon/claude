---
id: PC-SCLK-005
title: 共享 working tree 下無 pathspec 的 git commit 會夾帶他人已 staged 的檔案
severity: medium
---

# PC-SCLK-005: 共享 working tree 下無 pathspec 的 git commit 會夾帶他人已 staged 的檔案

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-SCLK-005 |
| 類別 | process-compliance |
| 風險等級 | 中（範圍面：本次未造成損害，執行代理人在 commit 前自行發現並改用精準 pathspec 攔截；互斥面：命令直接失敗未觸及 index，本質安全，僅需正確復原程序） |
| 首發時間 | 2026-07-31（範圍面：1.4.0-W2-016 修正 CursorLocatorBridge 時發現；互斥面：同日 PM 在 1.4.0-W3-002 追蹤票 commit 時撞見） |
| 姊妹模式 | PC-SCLK-001（並行 agent 的 `--amend` 改寫他人 commit，同屬「共享 HEAD/index 心智模型失效」家族，但 001 是寫入面直接破壞、本模式是暫存面夾帶）、PC-019（worktree 派發前的未 commit 變更防護，見下方適用條件）、PC-BAL-008（跨 consumer 同家族：flutter_balance 專案獨立捕獲，本模式聚焦路徑級隔離「commit 帶精準 pathspec」；PC-BAL-008「變體：檔案級共用」章節實證此防護在兩票 `where.files` 指向同一實體檔案時失效，見下方「解決方案」章節補述） |

---

## 症狀

多個 agent 在同一 working tree（非 worktree 隔離）並行作業時，各自對自己負責的檔案執行 `git add <path>`。此步驟本身安全——`git add` 只把指定路徑的變更加入 index，不影響其他路徑。真正的風險點在**下一步的 commit**：若此時執行不帶 pathspec 的 `git commit -m "..."`，git 會提交 index 當下的**全部**內容，包含其他 agent 早於自己 add、且尚未 commit 完成的檔案——即使自己從未對那些檔案下過任何指令。

危險點在於：index 是整個 working tree 唯一共享的暫存區，不是每個 agent 各自的私有暫存區。`git add` 的路徑範圍限制只保護「加入」這一步，不保護「提交」這一步；commit 若省略 pathspec，範圍預設是整個 index，而非「我這次 add 的東西」。

---

## 實例（2026-07-31，1.4.0-W2-016）

事件序列：

| 步驟 | 動作 | 觀察到的結果 |
|------|------|------|
| 1 | 執行 `git add macos/Runner/MainFlutterWindow.swift`（僅此一個路徑） | 命令本身成功，只操作了指定路徑 |
| 2 | 執行 `git status --porcelain` 確認 add 結果 | 除了預期的 `M macos/Runner/MainFlutterWindow.swift`，同時看到 `M  lib/app_constants.dart`、`M  lib/main.dart`、`A  lib/platform/cursor_locator_hotkey_controller.dart`、`M  test/fullscreen_clock_visibility_test.dart`、`A  test/platform/cursor_locator_hotkey_controller_test.dart`、`M  test/widget_test.dart` 六個檔案的 staged 標記——這些檔案我從未 add 過，是另一個並行 agent（負責 W2-005 hotkey 相關 ticket）先前已 stage、尚未 commit 完成的工作 |
| 3 | 意識到若直接 `git commit -m "..."`（不帶 pathspec）會把上述 6 個他人檔案一併提交，改用 `git commit -m "..." -- macos/Runner/MainFlutterWindow.swift` | commit 只包含 1 個檔案、99 行變更；`git status --porcelain` 確認其餘 6 個檔案維持原 staged 狀態未被觸碰 |

發現方式：commit 前對照 `git status --porcelain` 的檔案清單與自己實際修改的範圍是否一致，而非信任「我只 add 了一個檔案，commit 應該也只有一個檔案」的直覺推論。

未造成損害的關鍵：commit 前檢查這一步是可控環節，且本次是在 add 之後、commit 之前多做了一次 `git status` 核對才發現落差；若省略核對直接 `git commit -m`，他人 6 個檔案（含 2 個尚在編輯中的新檔案）會被夾帶進與己無關的 commit，造成他人半成品被提前定格、commit 訊息與實際內容不符、且該 agent 後續 commit 時會因這些檔案已不在 unstaged 狀態而混亂。

---

## 根因

「`git add` 範圍限定 = commit 範圍限定」是單一執行體心智模型下的合理直覺，因為沒有其他人會在自己 add 和 commit 之間插入 stage 動作。並行執行體共用同一 index 時此等價關係破裂：

三個條件同時成立即觸發：

1. 多個 agent 共用同一 working tree（非 worktree 隔離）
2. 其中一個 agent 已 `git add` 了自己的檔案、尚未 commit
3. 另一個 agent 在此期間執行 `git commit -m "..."` 時未加 pathspec

第 3 點是可控環節——commit 命令本身有明確語法差異（帶 `-- <path>` vs 不帶），不需猜測他人狀態即可規避。第 1、2 點是並行派發的常態，不是異常，也不該要求所有 agent「不要提前 add」（那只是把風險延後到 commit 當下才 add，仍會撞上同一問題）。

延伸：同源風險存在於所有「以當前 index 為隱含範圍」的 git 操作——`git commit`（無 pathspec）、`git stash`（無 `--` 限定路徑時預設打包整個 working tree）、`git diff --cached`（用於檢視而非寫入，風險較低但同樣會顯示他人內容造成誤讀）。

---

## 姊妹面向：`.git/index.lock` 互斥（失敗響亮 vs 夾帶靜默）

範圍問題（上述）與鎖問題（本節）是同一份共享資源（index）在並行寫入下暴露的兩種不同性質的風險，機制不同、後果性質相反：

| 面向 | 共享的是什麼 | 觸發後果 | 有效防護 |
|------|------|------|------|
| 範圍（上述章節） | index 的**內容**：多個 agent 的 staged 檔案共存於同一份 index | 靜默夾帶——commit 成功執行，混入他人內容，事後才發現（或發現不了） | `git commit -m "..." -- <path>` |
| 互斥（本節） | `.git/index.lock`：git 寫入 index 前建立的排他鎖，同時只允許一個寫入程序持有 | 命令當場失敗（`fatal: Unable to create '.git/index.lock': File exists.`），exit 128，什麼都沒發生 | 間隔後重試，**絕不手動刪除 lock 檔** |

**實例**（2026-07-31，PM 在 1.4.0-W3-002 追蹤票 commit 時觸發）：與另一個並行 agent 的 commit 撞期，取得 `.git/index.lock` 失敗，git 回報：

```
fatal: Unable to create '.git/index.lock': File exists.
Another git process seems to be running in this repository, e.g.
an editor opened by 'git commit'. Please make sure all processes
are terminated then try again. If it still fails, a git process
may have crashed in this repository earlier: remove the file
manually to continue.
```

### 為何「會失敗」反而是危險程度較低的那一種

兩者的危險程度直覺上容易顛倒——鎖衝突會直接報錯，看起來像「壞事發生了」；範圍夾帶不報任何錯，commit 顯示成功，看起來像「一切正常」。但實際的危險排序相反：

- 鎖衝突的失敗**無法被忽略**——命令回傳非零、stderr 有明確 `fatal` 字樣，agent 或 PM 一定會注意到，且此時 index 尚未被寫入，狀態未被破壞，重試即可恢復。
- 範圍夾帶的成功**可以被完全忽略**——commit 正常返回、`git log` 表面正常，若沒有像本模式「解決方案」章節那樣主動核對 `git status`，混入的他人內容會一路留在歷史裡，直到事後被發現（甚至永遠不被發現）。

這是本模式判定「pathspec 紀律遠比鎖處理更重要」的核心理由：鎖問題會自己攔住你，範圍問題不會，攔不住的風險才是需要主動防禦的風險。

### 危險：`fatal` 訊息本身在共享 tree 下具誤導性

git 官方錯誤訊息建議「若確認沒有其他 git 程序在跑，手動刪除 lock 檔即可繼續」——這在單人本機環境下是正確且常見的復原建議（例如編輯器崩潰後殘留 lock 檔）。但在多 agent 共享同一 working tree 的情境下，**這條建議的前提假設（沒有其他 git 程序在跑）通常不成立**：lock 檔存在的當下極可能正是另一個 agent 的 commit 真正進行中。此時依訊息字面建議手動刪除 lock 檔，會在對方寫入 index 的過程中把鎖拆掉，可能造成對方 index 損毀或 commit 內容不完整——這是「正確的工具訊息在錯誤的環境假設下變成有害建議」的具體案例：訊息本身沒有寫錯，錯的是套用訊息建議的環境前提。

**正確處置**：撞到 `index.lock` 衝突時，一律視為「有其他 agent 正在寫入」，間隔數秒後重試 commit 即可（多數情況一次重試即成功，因為對方的寫入通常在數秒內完成）；共享 tree 下**任何情況都不手動刪除 `.git/index.lock`**，即使訊息字面上建議這麼做。

---

## 解決方案

### 有效防護：commit 一律帶精準 pathspec

```bash
# 危險：省略 pathspec，提交 index 當下全部內容
git commit -m "..."

# 安全：無論 index 當下還有什麼其他人的暫存內容，只提交指定路徑的變更
git commit -m "..." -- macos/Runner/MainFlutterWindow.swift
```

這比「約定不要用 `git add -A` / `git add .`」更根本，因為它不依賴每個 agent 自律避免寬範圍 add——即使自己全程只 `git add <path>`，只要 commit 時漏了 pathspec，仍會被他人已 stage 的內容拖下水。`git commit -- <path>` 從 commit 這一步本身就繞過已 staged 的 index 內容，不管 index 裡還有什麼。

**邊界：pathspec 是路徑級隔離，非檔案級隔離**——上述防護只確保「其他路徑」不會被夾帶進 commit，前提是兩個並行任務各自負責的路徑互斥。若兩票的 `where.files` 指向**同一實體檔案**，該檔案在共享 working tree 中會被雙方的 Edit 依序疊寫，此時任一方對這個路徑執行精準 pathspec commit，add 進 index 的仍是「當下磁碟上已疊寫兩方內容」的版本——pathspec 對此無效，因為問題不在 index 累積範圍之外的檔案，而在目標檔案本身已是共筆。**Why/Consequence**：誤把「commit 帶 pathspec」當充分防護，會在檔案級共用情境下重蹈本模式、卻找不到根因（明明已遵守本文件建議）。**Action**：派發前先做 `where.files` 交集檢查，兩票指向同一檔案時改序列派發或拆分檔案落點，不可僅靠 commit 端的 pathspec 補救。完整變體案例、根因與解決方案見 `PC-BAL-008-shared-git-index-sweeps-parallel-agent-staged-files.md`「變體：檔案級共用」章節。

### 事前預防（agent 側）

| 情境 | 措施 |
|------|------|
| commit 前 | 一律 `git commit -m "..." -- <自己負責的路徑>`，不依賴「我只 add 了自己的東西」的假設 |
| add 後、commit 前 | 執行 `git status --porcelain` 核對 staged 清單是否只有自己預期的檔案；出現非預期項目時，優先假設是他人並行工作，不隨意 `git reset` 清空 |
| commit 後 | 再次 `git status --porcelain` 確認自己 commit 前看到的「他人 staged 檔案」仍維持原狀未被觸碰，驗證 commit 範圍未外溢 |

### 事前預防（PM 側）

| 情境 | 措施 |
|------|------|
| 派發涉及 git commit 的並行 agent | Context Bundle 明載「commit 一律帶 `-- <path>` pathspec，不可依賴僅 add 自己檔案即安全」 |
| 檔案修改型並行派發 | 優先採 worktree 隔離（ARCH-015），從根本消除共用 index；但注意下方「適用條件」的互斥限制 |

---

## 預防措施

| 層級 | 措施 | 狀態 |
|------|------|------|
| Agent 自律 | Context Bundle 加入「commit 一律 `-- <path>` pathspec」的並行安全約束 | 可立即施行 |
| PM 派發 | 檔案修改型並行任務優先 worktree 隔離 | 既有 ARCH-015 規範，但受下方適用條件限制 |
| Hook 強制 | PreToolUse 偵測共用 working tree 下 `git commit -m` 未帶 `--` pathspec 且當前有 2+ 進行中 ticket 時警告 | 待評估（WARNING 級即可，單一執行體省略 pathspec 是合法且常見的操作，不應硬擋） |
| Agent 自律（互斥面） | 撞到 `index.lock` 衝突一律間隔重試，禁止依 git 訊息字面建議手動刪除 lock 檔 | 可立即施行 |

---

## 適用條件（與 worktree 隔離互斥）

Worktree 隔離可從根本避免本模式——每個 agent 各自的 index 天生互不干擾。但當共享 working tree 上已有其他 agent 進行中、尚未 commit 的變更時，`worktree-commit-before-dispatch-hook`（`.claude/skills/worktree/hooks/worktree-commit-before-dispatch-hook.py`）會依 PC-019 的防護邏輯**阻擋**新的 worktree 派發（未 commit 的 tracked 變更可能在 worktree 操作的 stash/checkout 中丟失）。

換言之：兩種並行隔離手段在同一時間窗口互斥——

- 共享 tree 上有他人未 commit 的進行中變更時 → 無法派發新的 worktree agent（PC-019 擋）→ 只能繼續在共享 tree 上派發 → 承擔本模式（PC-SCLK-005）的暫存夾帶風險
- 想用 worktree 隔離消除本模式的風險 → 前提是共享 tree 先清乾淨（全部 commit）→ 但這正是本模式描述的、最容易在多 agent 並行時做不到的狀態

**結論**：本模式的防護不能指望「改用 worktree 就不用管」，因為觸發本模式的時間窗口（他人有未 commit 變更）恰好是 worktree 派發被 PC-019 擋住的同一時間窗口。共享 tree 情境下的 commit pathspec 紀律是**必要**防線，不是 worktree 隔離普及前的過渡措施。

---

## 相關規則

- `.claude/rules/core/bash-tool-usage-rules.md` 規則三 — 禁止串接 git 寫入操作（同源於 `index.lock` 競爭，但聚焦「單一 agent 一次 Bash 呼叫內串接多個寫入指令」；本模式的互斥面聚焦「兩個獨立 agent 各自正常執行、時間點恰好重疊」，觸發條件不同但復原原則一致：重試、不手動介入鎖）
- `.claude/error-patterns/process-compliance/PC-SCLK-001-parallel-agent-amend-rewrites-foreign-commit.md` — 姊妹模式：共享 HEAD 心智模型在並行下失效的另一種表現（寫入面直接改寫 vs 本模式的暫存面夾帶）
- `.claude/error-patterns/process-compliance/PC-BAL-008-shared-git-index-sweeps-parallel-agent-staged-files.md` — 跨 consumer 姊妹模式：flutter_balance 專案獨立捕獲同家族的路徑級夾帶，其「變體：檔案級共用」章節補述本模式 pathspec 防護在檔案級共用場景失效的邊界
- `.claude/error-patterns/process-compliance/PC-019-worktree-merge-state-loss.md` — worktree 隔離的前置條件與本模式的互斥關係
- `.claude/skills/worktree/hooks/worktree-commit-before-dispatch-hook.py` — PC-019 的 Hook 強制層，決定本模式的適用時間窗口
- `.claude/pm-rules/parallel-dispatch.md` — 並行派發規範

---

## 關聯 Ticket

- `1.4.0-W2-016`（發現範圍面並自行以 `git commit -- <path>` 攔截的 ticket）
- `1.4.0-W3-002`（PM 追蹤票 commit 時撞見互斥面 `index.lock` 衝突）
