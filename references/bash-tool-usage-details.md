# Bash 工具使用詳細案例

本文件從 `.claude/rules/core/bash-tool-usage-rules.md` 拆出，為按需讀取的詳細案例集。遇到違規、debug 或需要理解「為什麼」時閱讀本文件。

> **使用時機**：
> - 被規則骨架提示但不理解原因
> - 違規後需診斷根因
> - 新進代理人需建立完整心智模型
> - 新增類似規則時參考既有深度說明

---

## 規則一詳細：禁止使用 cd 改變持久工作目錄

### 問題根源圖解

Claude Code 的 Bash 工具在同一 session 內共享一個持久 shell。

```
session 開始
    → shell 工作目錄：/project/root
    → cd .claude/skills/ticket
    → shell 工作目錄：/project/root/.claude/skills/ticket  ← 永久改變
    → 後續 ./scripts/sync-push.sh  ← 找不到！
```

### 三種安全做法的範例碼

**方法 1：子 shell（推薦，任何情況適用）**

```bash
# 括號建立子 shell，原工作目錄不受影響
(cd .claude/skills/ticket && uv run ticket track list)
```

子 shell 執行完畢後，父 shell 的工作目錄保持不變。這是最通用的方法，適用任何指令。

**方法 2：uv -d 參數（適用 uv 指令）**

```bash
# uv 支援 -d 指定目錄，不改變 shell 工作目錄
uv -d .claude/skills/ticket run ticket track list
```

uv 原生支援指定目錄參數，比子 shell 更精簡，但僅限 uv 指令。

**方法 3：絕對路徑還原**

```bash
# 若已污染，每次命令前加絕對路徑 cd
cd /your/project/root && ./scripts/sync-push.sh
```

這是補救做法，不是預防做法。若工作目錄已被污染，每次命令都必須先 cd 回根目錄。長期使用會累積技術債，應改用方法 1 或 2。

### chpwd Shell Hook 深度說明（IMP-056）

**此環境的 zsh 配置了 `chpwd` hook，切換目錄時會自動執行 `ls`。**

`chpwd` 是 zsh 的內建 hook 機制，每次工作目錄變更時都會觸發。本專案的 zsh 配置在 chpwd 時自動列出當前目錄內容（相當於自動執行 `ls`）。

**為什麼這會造成問題**：

1. 裸 `cd` 命令會觸發大量 `ls` 輸出
2. 輸出佔用工具結果空間（Claude 每次 Bash 呼叫的輸出有長度限制）
3. 後續命令的實際結果可能被 `ls` 輸出淹沒或截斷
4. 代理人收到的輸出可能被污染，導致判斷錯誤

**典型受害場景**：

```bash
# 錯誤示範：工具結果被 ls 輸出淹沒
cd /some/path && ls  # chpwd 先觸發一次 ls，再執行 ls，雙倍輸出
cd /deep/nested/dir && grep "x" file  # chpwd ls 可能大於 grep 結果
```

**安全替代**：

| 命令類型 | 錯誤做法 | 正確做法 |
|---------|---------|---------|
| 需要在其他目錄執行 | `cd /path && command` | `(cd /path && command)` — 子 shell 不觸發父 shell 的 chpwd |
| 讀取/編輯檔案 | `cd /path && cat file` | 使用 Read/Edit/Write 工具搭配絕對路徑 |
| uv 指令 | `cd /path && uv run ...` | `uv -d /path run ...` |

**為什麼子 shell 不觸發 chpwd**：子 shell 是獨立 process，即使有 chpwd 設定，其輸出不會污染父 shell 的工具結果空間（透過 `()` 包裹的命令結束後，子 shell 整體退出，chpwd 的 ls 輸出通常會被 shell 直接丟棄或只影響子 shell 內部）。

### 違規頻率警示（PC-046）

規則一是 50+ 次違規的高頻問題（PC-046）。常見違規模式：

1. **「我只用一次 cd 應該沒差」**：持久 shell 的概念不直觀，第一次違規後常以為是偶發
2. **慣性手勢**：從一般 Linux shell 遷移過來，習慣用 `cd && command`
3. **多步驟指令忘記子 shell**：只對第一個 `cd` 套子 shell，後續的 `cd` 又改回裸寫

---

## 規則二詳細：正確區分 TaskOutput vs 暫存輸出檔案

### 判斷流程圖解

```
工具執行完成
    |
    v
是否使用 run_in_background: true 啟動？
    |
    +-- 是 → TaskOutput(taskId: "xxx")
    |
    +-- 否 → 輸出是否顯示 "Full output saved to: /path/xxx.txt"？
        |
        +-- 是 → Read(file_path: "/path/xxx.txt")  ← 使用完整路徑
        +-- 否 → 直接讀取對話中的輸出
```

### 典型混淆案例

```
Bash 工具輸出：
"Output too large (279.4KB). Full output saved to: .../tool-results/b8refllkc.txt"

錯誤：TaskOutput(taskId: "b8refllkc")
   → 回傳：No task found with ID: b8refllkc
   → 原因：b8refllkc 是暫存檔案名，不是任務 ID

正確：Read(file_path: ".../tool-results/b8refllkc.txt")
   → 回傳：完整的輸出內容
```

### 兩種機制的本質差異

| 項目 | 背景任務 | 暫存輸出檔案 |
|------|---------|------------|
| 觸發條件 | 工具呼叫時明確設定 `run_in_background: true` | 同步呼叫但輸出超過 2KB（單次） |
| 生命週期 | 背景 process 持續執行直到完成 | 同步執行結束，只是輸出被暫存到檔案 |
| 識別字 | taskId（字串標識 running process） | 檔案路徑（指向已完成命令的輸出檔案） |
| 後續處理工具 | `TaskOutput` 讀取 process 當前輸出 | `Read` 讀取檔案內容 |
| 可否續作 | 可以持續 poll 到 process 結束 | 不適用（命令已完成） |

**核心辨識**：**訊息中是否出現 "Full output saved to:"**，有 → 用 Read；沒有且是背景任務 → TaskOutput。

---

## 規則三詳細：禁止串接多個 git 寫入操作

**前提修正（issue-34，0.2.1-W3-262）**：本節原表述隱含「唯讀 git 命令可安全併發，index.lock 只在寫入串接時才會發生」。此前提已被實驗推翻——見「情境二」。串接寫入操作仍應避免（機制見情境一），但 index.lock 本身不是「串接違規」的專屬訊號，遇到時的預設處置是短暫重試，見本節末「index.lock 錯誤的診斷」。

### 情境一：寫入串接觸發 Hook 競爭（根因圖解）

Claude Code 的 PostToolUse Hook 在每個 Bash 呼叫完成後觸發。Hook 內部會執行 git 命令（如 `git status`、`git log`）。

當多個 git 寫入操作用 `&&` 串接在同一個 Bash 呼叫中時：

```
git commit -m "msg" && git merge feat/xxx --no-edit
    |                      |
    v                      v
    commit 完成             merge 開始（同一 Bash 內，不等 Hook）
    |
    v
    Hook 觸發 → Hook 內的 git 命令
    |                      |
    v                      v
    git 競爭 index.lock ← git merge 也需要 index.lock
    → fatal: Unable to create index.lock
```

### 範例碼：正確分開呼叫

```bash
# 正確：分開呼叫
Bash: git add file.md && git commit -m "msg"     ← 第一個 Bash 呼叫
Bash: git merge feat/xxx --no-edit               ← 第二個 Bash 呼叫（等 Hook 完成後）
Bash: git push                                    ← 第三個 Bash 呼叫

# 錯誤：串接
Bash: git add file.md && git commit -m "msg" && git merge feat/xxx --no-edit && git push
```

### 情境二：唯讀 git 命令本身也會競爭 index.lock（issue-34 實證）

**Why**：git 唯讀子命令（`git status --porcelain`、`git diff-tree`、`git log -1` 等）在需要 refresh index stat cache 時，會透過標準 lockfile 機制短暫建立並釋放 `index.lock`——此行為與命令對使用者呈現的唯讀語意無關，純粹是 git 內部實作細節。

**實證**（框架 issue 34，consumer `screen_clock` ticket `1.4.0-W2-030`）：背景併發執行 `git status --porcelain` / `git diff-tree` / `git log -1` 時，前景 30 次獨立 `git add` 命中 1 次 index.lock 失敗；依原規則採 `add && commit` 串接則連續三次失敗，拆開後 `git add` 仍間歇性失敗需重試。此結果與原表述「add 不觸發 Hook」矛盾——真正發生競爭的不是「add 是否觸發 Hook」，而是「任一 git 命令（含唯讀命令）refresh stat cache 時是否恰好撞上另一 git 命令持有 lock 的瞬間」，屬本質上的機率性競爭，不是串接才會出現的行為。

**Consequence**：把 index.lock 錯誤逕自解讀為「一定是串接違規」會誤導排查方向——並行環境（背景任務、其他 subagent、外部 GUI app）中即使每個 git 呼叫都獨立、未串接，仍可能間歇命中 lock。IMP-046 已記錄此類 Hook 內 `git status` 與主線程 git 操作競爭的案例，本次 issue-34 補上「純唯讀命令互相競爭、與 Hook 或串接皆無關」的變體。

**Action**：遇 index.lock 錯誤，先依「index.lock 錯誤的診斷」表短暫重試，不預設為串接違規；`git add && git commit` 的允許性維持不變，但理由改為「實務簡化」而非「add 不觸發 Hook 故安全」。

### `git add && git commit` 為何仍維持允許（因果修正）

| 操作 | 原表述（已修正） | 修正後 |
|------|----------------|--------|
| `git add` | 「不改變 HEAD，Hook 內的 git status/log 不衝突」 | add 與其他 git 命令一樣，在 refresh index 時仍可能間歇命中 lock（情境二），並非因「不觸發 Hook」而免疫 |
| `git commit` | 「commit 完成後 Hook 才跑」 | 維持——commit 寫入 HEAD 後才觸發 PostToolUse Hook，情境一風險仍成立 |

**關鍵**：commit 之後不可再串接 merge/push/rebase（情境一風險，寫入間的 Hook 競爭仍真實存在）。add + commit 維持允許是實務簡化——兩者間本就無先後依賴的寫入衝突，即使間歇命中 lock 也屬情境二的一般性機率問題，非串接特有，短暫重試即可，不需因此禁止 add + commit 組合。

### index.lock 錯誤的診斷

看到 `fatal: Unable to create index.lock` 錯誤時，**預設處置是短暫等待後重試同一命令**（並行環境下屬預期現象，見情境二）。若重試後仍反覆失敗，再依序檢查：

1. 是否有 git 寫入操作串接（`&&` 連接 commit/merge/rebase/push）？→ 拆成獨立 Bash 呼叫（情境一）
2. 是否有殘留的 `.git/index.lock` 檔案（非本次操作造成）？→ `git-index-lock-cleanup-hook.py` 會自動清理超過 5 秒的殘留 lock，未清理可手動 `rm .git/index.lock`
3. 是否有其他 process 正在使用 git（含背景並行的唯讀命令、外部 GUI app）？→ 檢查 `ps aux | grep git`，另見 PC-139（外部 GUI app fork 誤判來源）

**與並行派發文件的口徑一致性**：`.claude/pm-rules/parallel-dispatch.md` 與 `PC-BAL-008`（同 repo 並行 agent 共用 git index）已採「lock 競爭屬預期現象、短暫等待重試為預設」的處置方向；本節修正後與其一致，皆不再要求把每次 index.lock 都當作違規追查。

---

## 規則五詳細：長文字傳遞預設使用 heredoc

### 心理障礙破除

PM 歷史上多次繞 `/tmp` 寫中介檔（PC-087），根因是**誤以為 heredoc 有容量限制**。實測：

- macOS ARG_MAX = 1,048,576 bytes（1 MB）
- Linux ARG_MAX 通常 ≥ 2 MB
- 單次 `ticket track append-log <id> "$(cat <<'EOF' ... EOF)" --section "..."` 可安全傳遞 800 KB+ 純文字
- 80 行密集中文 markdown 約 3-8 KB，完全在容量內

**為何 PM 仍繞 /tmp**：
1. LLM 訓練資料中 shell 「長字串用檔案」是常識模式，但那是針對傳統 shell 限制（512 KB 以下）
2. 沒有容量事實的錨定，直覺保守
3. `/tmp` 中介看似「更穩」，實際多兩次 IO + 遺留清理負擔

### 正確模式範例

```bash
ticket track append-log 0.18.0-W15-007 "$(cat <<'EOF'
## Solution

實作摘要：
1. 主檔規則五新增（<30 行）
2. 規則四交叉引用補充
3. details.md 補心理障礙破除段
4. auto-memory 雙通道建立
EOF
)" --section Solution
```

quoted delimiter (`'EOF'`) 禁用變數展開與 command substitution，內容原樣傳入，安全於 backtick 與 `$var`。

### 後退條件

若 3 個月內（2026-07-18 前）仍偵測到 PM 繞 `/tmp` 寫中介檔案的案例 ≥ 2 次，升級方案：

- 建立 pre-Write hook：Write 目標為 `/tmp/*.md` 且 content > 500 bytes 時警告「長文字應 heredoc 直傳，見 bash 規則五」（此即 WRAP 分析確認的 Hook 升級路徑）

### 觸發來源

- PC-087（PM 寫 /tmp 中介）直接觸發
- W15-005 WRAP 分析確認方案 E（規則 + memory + 交叉引用）為最低成本最大覆蓋方案
- W15-007 落地實作

---

## 規則一詳細：輸出可疑/被淹沒當下的即時協議（confabulation 防護）

工具輸出出現「無法定位本次命令真實 result」（chpwd ls 淹沒、輸出交錯、夾帶 markdown 旁白）時，依序執行四步協議：

| 步驟 | 動作 |
|------|------|
| 1 停手 | 不在同訊息續寫「預期輸出」（confabulation 點火動作，`tool-output-trust-rules` 規則 1） |
| 2 重發乾淨原子命令 | 用 `git -C`／子 shell 避免 chpwd，命令極簡單一目的 |
| 3 只信 raw stdout | 帶旁白／markdown 修飾的「輸出」視為自生雜訊（`tool-output-trust-rules` 規則 2） |
| 4 固定值驗證 | 關鍵事實用 hash／二元 grep／整數計數確認（`tool-output-trust-rules` 規則 3） |

**Why**：規則二教「事前」預防大輸出（加 head／tail），但 chpwd 淹沒是 shell hook 副作用，head／tail 無效（IMP-056 變體）。「淹沒已發生」的當下若無協議，預設行為退化成「用預期填補」（confabulation）。

**Consequence**：缺即時協議時，PM 在淹沒當下傾向把混入的 chpwd ls 當「正常但吵」接受並續寫，滑入 confabulation——把虛構輸出當事實推進，需外部介入才揭穿。

**Action**：核心是「停手重發」而非「帶疑推進」，依上表四步執行。

---

## 規則六詳細：長背景任務需即時可觀察時使用 PYTHONUNBUFFERED + tee

> **來源**：0.19.0-W3-086 ANA spike 實證（buffered 全程 0 行 vs PYTHONUNBUFFERED 逐行成長）。

**Why（雙層緩衝根因）**：Bash 子行程的 stdout 在非 TTY（管道/檔案）環境下預設為 fully-buffered（4-8 KB 才 flush）。加上 `| tail` 額外等 EOF 才吐出，雙層緩衝導致長任務輸出檔全程空白，用戶與 PM 無法即時觀察進度或早期偵測卡死/失敗。

**Consequence**：長任務黑箱化——用戶無法判斷任務是否存活，失敗需等全程結束才發現，信任度下降且無法早期介入。

**Action 場景對照**：

| 場景 | 錯誤做法 | 正確做法 |
|------|---------|---------|
| 長時間 pytest / build 需即時觀察 | `pytest -q tests/ 2>&1 \| tail -5`（run_in_background） | `PYTHONUNBUFFERED=1 pytest -v tests/ 2>&1 \| tee /tmp/task.log`，並告知用戶 `tail -f /tmp/task.log` |
| 長時間 Python 腳本需即時觀察 | `python script.py 2>&1 \| tail -20` | `PYTHONUNBUFFERED=1 python script.py 2>&1 \| tee /tmp/task.log` |
| 只需最終結果（無即時需求） | — | 保留規則二的 `\| tail` / `\| head` 防淹沒，不需 tee |

**三個慣例**：

| 慣例 | 說明 |
|------|------|
| `PYTHONUNBUFFERED=1` | 單一環境變數強制 Python stdout 逐行 flush；不需 stdbuf（macOS LD_PRELOAD 可靠性存疑） |
| `pytest -v`（非 `-q`） | `-q` 在非 TTY 環境不即時 flush；`-v` 逐測試輸出並保持 flush 行為 |
| `2>&1 \| tee <logfile>` | tee 將 stdout+stderr 同時寫入 logfile 並透傳；用戶可在另一個終端 `tail -f <logfile>` 即時觀察 |

**「大輸出防護」vs「即時可觀測性」的取捨（與規則二的調和）**：

| 需求 | 使用工具 | 說明 |
|------|---------|------|
| 只看最終結果，不需即時追蹤 | `\| tail` / `\| head`（規則二） | 防止大輸出淹沒，最終結果截取後讀取 |
| 需即時觀察進度（長任務存活性 / 失敗早現） | `PYTHONUNBUFFERED=1 ... \| tee <logfile>`（規則六） | logfile 逐行成長，`tail -f` 可即時追蹤 |

兩者不互斥：若既需即時觀察又防終端淹沒，用 tee 寫 logfile（即時），讀取時再 `tail -n 50 <logfile>`（限制行數）。

**識別特徵**：若長背景任務輸出檔全程 0 行、只在結束後一次性出現內容，確認是否使用了 `-q` + `| tail` 雙層緩衝（規則六的觸發條件）。

---

## 規則七詳細：隔離索引提交（GIT_INDEX_FILE CAS）

### 為何規則七的三步驟仍不夠——TOCTOU 窗口

規則七的正確替代（`git add <exact-path>` → `git diff --cached --name-only` 核對 → 裸 `git commit`）三個步驟間仍共用同一個 git index 檔案（`.git/index`）。核對通過後、裸 commit 執行前的窗口中，另一個並行 process（背景代理人、其他 subagent）仍可能 `git add` 進同一個共用 index，使裸 commit 連帶提交進去——先核對再 commit 仍存在 TOCTOU 窗口，並行環境下已有實測命中案例（PC-BAL-008）。

低頻手動 commit（規則七主文情境）用「核對 + 裸 commit」已足夠安全，成本也最低。但高頻/高衝突路徑（例如同一 ticket md 檔案每次操作都觸發一次 auto-commit）需要完全不共用 index 的做法，才能杜絕 TOCTOU 窗口。

### 隔離索引 CAS 配方

**Why**：把「建 tree → 建 commit → 移動 HEAD」全程操作獨立於共用 index 之外，commit 內容只由呼叫者傳入的精確檔案清單決定，不受任何並行寫入影響；最後以帶舊值的 `update-ref` 做 compare-and-swap，若 HEAD 於期間被移動則失敗而非覆蓋，不會遺失他人 commit。

**Consequence**：不採此法，高頻路徑的「核對 + 裸 commit」在並行環境下仍可能吸入他人 staged 內容，且發生時難以歸因——commit 已完成，只能事後比對 diff 才能發現範圍不對，錯誤已寫入歷史。

**Action（步驟）**：

```bash
# 1. 記下目前 HEAD（CAS 的舊值，也是 commit-tree 的 parent）
OLD_HEAD=$(git rev-parse HEAD)

# 2. 建立獨立臨時 index 路徑，GIT_INDEX_FILE 指向它
#    （檔案不先建立，read-tree 會依需要建立獨立 index）
TEMP_INDEX=$(mktemp -u)
export GIT_INDEX_FILE="$TEMP_INDEX"

# 3. 在臨時 index 中重建 HEAD 當下的樹狀態
git read-tree "$OLD_HEAD"

# 4. 只 stage 目標檔案（working tree 內容）；臨時 index 與共用 index 完全隔離
git add -- <exact-file-1> <exact-file-2>

# 5. 由臨時 index 產生 tree
TREE_SHA=$(git write-tree)

# 6. 以 plumbing 建立 commit（不經 git commit，不觸發 pre-commit/commit-msg hook）
COMMIT_SHA=$(git commit-tree "$TREE_SHA" -p "$OLD_HEAD" -m "訊息")

# 7. 自我驗證：新 commit 相對舊 HEAD 的變更範圍恰為預期檔案清單，不符即放棄（不執行步驟 8）
git diff --name-only "$OLD_HEAD" "$COMMIT_SHA"

# 8. CAS 移動 HEAD：帶舊值，若 HEAD 於期間被並行移動則失敗，不覆蓋
git update-ref HEAD "$COMMIT_SHA" "$OLD_HEAD"

# 9. 清理臨時 index
rm -f "$TEMP_INDEX"
unset GIT_INDEX_FILE
```

**適用條件**：

| 條件 | 說明 |
|------|------|
| 高頻自動化路徑 | 同一檔案集合被高頻率、多來源觸發 commit（如 ticket md 每次操作都 auto-commit） |
| 連續並行提交 | 短時間內連續對不同檔案做精確提交，人工核對速度跟不上並行寫入速度 |
| bare-commit-guard DENY 且確認範圍屬己 | 確認 staged 範圍屬於自己的派發範圍時，可用隔離索引 CAS 繞開共用 index 競爭本身，而非改用 pathspec（規則七禁止 pathspec 的理由不變，見規則七主文） |
| 一般低頻手動 commit | 不需要，規則七「精確 add + 核對 + 裸 commit」已足夠，不需引入 CAS 複雜度 |

**與規則七主文的關係**：不取代規則七的「精確 add + 核對 + 裸 commit」——後者仍是預設做法（成本低、無需額外 plumbing 知識）。隔離索引 CAS 是同一目標（避免吸入他人未 stage 編輯）在高衝突場景下的加強做法，兩者並列，依情境選擇。

**已驗證實作**：`.claude/skills/ticket/hooks/ticket-md-auto-commit-hook.py` 的 `auto_commit_ticket_md` 函式（現行實作，對應歷史 fix commit `bd849894a`）。因不經過 `git commit`，此路徑不會觸發 pre-commit/commit-msg hook（含 bare-commit-guard-hook）——這是 plumbing 命令的固有行為，不是刻意繞過；guard 存在的目的是攔截「範圍不明的裸 commit」，本配方以步驟 7 的自我驗證取代 guard 的把關角色，提交範圍由程式碼結構保證且提交後即時核驗，不削弱其防護意圖。

### 隔離索引提交的完整性三要件

上文配方容易被誤讀為「用了 `GIT_INDEX_FILE` 就已隔離」。實際上完整的隔離提交需同時滿足三個要件，任一項缺失即整體失效：

| 要件 | 內容 | 對應步驟 |
|------|------|---------|
| 1. 清單來源獨立於共用 index | 決定要提交哪些檔案的清單，必須取自呼叫端已知的精確來源（如 ticket `where.files` 宣告、或函式呼叫者作為引數傳入的檔案清單），禁止用 `git diff --cached --name-only` 或任何讀取共用 index 目前 staged 狀態的命令產生清單 | 步驟 4（`git add -- <exact-file-1> <exact-file-2>`）的引數來源 |
| 2. 寫入使用 GIT_INDEX_FILE | 全程操作（read-tree / add / write-tree）在獨立臨時 index 中進行，不觸及共用 index | 步驟 2-6 |
| 3. 提交前以 tree 層級自檢範圍 | 建立 commit 物件前後皆須核對變更範圍恰為預期清單。可在步驟 5 產生 `TREE_SHA` 後立即以 `git diff-tree --no-commit-id --name-only -r HEAD <TREE_SHA>` 自檢（早於建立 commit 物件，發現不符即可提前放棄，不需先耗費一次 commit-tree），或沿用步驟 7 既有的 `git diff --name-only <OLD_HEAD> <COMMIT_SHA>`（commit 建立後比對）；兩者比對邏輯等價，擇一即可但不可省略 | 步驟 5 之後（提前版）或步驟 7（既有版） |

**Why**：要件 1 與要件 2 保護的對象不同——要件 2（`GIT_INDEX_FILE`）只隔離「寫入端」，確保臨時 index 的內容不被其他並行程序寫入干擾；但若決定「寫入端該寫入什麼」的清單來源（要件 1）仍取自共用 index 的目前狀態，隔離在入口就已經漏掉——清單本身可能已摻入其他並行程序剛好也 staged 到共用 index 的檔案，後續全程獨立操作只是把「已經錯誤的清單」精確地提交進去。要件 3 是最後一道防線，防止清單變數被 shell 展開錯誤、路徑筆誤帶入非預期檔、或 read-tree 基底與 HEAD 不一致等清單以外的失誤流入最終 commit。

**Consequence**：不滿足要件 1 時，維護者複製本配方常會沿用規則七主文「先核對現有共用 index 內容」的核對習慣作清單來源——因為全程操作看似「隔離」，出錯時更難聯想到問題出在清單來源而非寫入端；且要件 1 失守時，要件 2、3 仍會「正確地」執行完畢（`GIT_INDEX_FILE` 隔離無誤、diff 自檢也會「通過」，因為自檢比對的正是同一份已經錯誤的清單），三個環節各自看起來都沒有問題，只有整體行為（提交範圍）是錯的。

**反例**（實證）：commit `a7caabf4f`（2026-08-21，目錄級 where.files 宣告攔截功能提交）示範要件 1 失守的具體樣態——清單來源改用 `git diff --cached --name-only` 讀取共用 index 目前 staged 狀態，即使後續仍以 `GIT_INDEX_FILE` 隔離寫入、產生 tree、建立 commit，仍把另一張並行進行中 ticket 的 metadata 檔案（未在本次任務清單內，當時恰好也 staged 在共用 index）一併提交進去。三個要件中只有第一項出錯，但因清單是整個配方的輸入起點，錯誤會沿全程配方精確複製到最終 commit——其餘兩項做得再確實，也無法補救清單本身已經錯誤。

### 規則七核對步驟的粒度邊界：檔案內夾帶

**現象**：規則七主文的正確替代（精確 `git add <exact-path>` → `git diff --cached --name-only` 核對 → 裸 `git commit`）以「核對 index 只含目標檔」為安全依據。此依據隱含一個未明示的前提——目標檔本身的內容是乾淨的。當目標檔本身就含有他人尚未 stage 的編輯時，前提不成立，核對步驟對此完全無鑑別力。

**Why**：`git diff --cached --name-only` 的輸出粒度是檔名，不是 hunk。`git add <path>` 的最小可定址單位是整個檔案的當下工作區內容——沒有「只 add 自己寫的那幾行」這種操作（`git add --patch` 除外，見下）。目標檔正是被夾帶的那個檔時，核對指令印出的檔名清單與「乾淨」情境完全相同，兩者在檔名層級無法區分。

**Consequence**：不理解此邊界時，容易誤以為規則七三步驟已提供完整防護，對「同檔案已有他人未 stage 編輯」的情境掉以輕心。實例（本專案 2026-08-24）：PM 於 `docs/work-logs/topic-assignments.txt` 追加一行後刻意不 stage，等在途代理人完成後再提交；代理人收尾時對同一檔案執行 `git add` 後裸 commit，核對步驟印出的檔名清單正確無誤，但 commit 內容同時含代理人自己的行與 PM 未 stage 的行。本例內容無害（兩行皆語意正確），但機制若發生在語意衝突或未完稿的編輯上，會直接把未完成的內容提交進歷史。

**Action**：

| 情境 | 處置 |
|------|------|
| 目標檔可能含他人未 stage 的獨立 hunk，且工具支援互動式 staging | `git add --patch <path>`，逐 hunk 確認後再 stage，取代整檔 `git add` |
| append-only 共用檔（如 `docs/work-logs/topic-assignments.txt`，每次 `ticket create` 皆追加一行，結構性熱點） | 約定由單一方（例如固定由 PM）負責提交該檔，其餘方只編輯不 commit；或改用 `git add --patch` |
| 無法確認目標檔是否乾淨 | commit 前先 `git diff <path>`（非 `--cached`）檢視工作區相對於 index 的差異，確認無非預期的既有未 stage 內容混入 working tree 版本 |

**與根因的關係**：本節與上方「變體：檔案級共用」章節（PC-BAL-008）同根因——`git add` 讀的是磁碟當下內容，無法區分「誰寫的哪一行」。PC-BAL-008 該章節處理的是兩張正式 ticket 的 `where.files` 重疊；本節額外指出**核對步驟本身**（而非僅 `git add` 動作）對此邊界無鑑別力，且將處置範圍擴及非 ticket 的 append-only 共用檔案。**邊界（不變）**：本節不改變規則七既有禁止事項——`git commit -- <path>` / `--only` / `-o` / `-i` 的禁令與其論證維持不變，本節是核對步驟侷限性的補充說明，非規則修訂。

---

## 規則八詳細：CJK 資料聚合統計加 LC_ALL=C（locale collation 陷阱）

### 問題根源

`sort` 的排序鍵與 `uniq -c` 的相等判斷都依目前 shell 的 locale collation 規則，不是位元組序。系統預設 locale（僅設 `LANG=xx_XX.UTF-8`，`LC_ALL`/`LC_COLLATE` 皆未設，多數互動式 shell 的常態）下，collation 對多位元組字元的排序權重可能把兩個**位元組序列相異**的字串判為相等，`uniq -c` 因而合併計數，且顯示名稱只取被合併中的其中一方。

### 最小重現（可自行執行驗證）

```bash
printf 'hook 可靠性與失敗語意\nhook 測試覆蓋\nhook 可靠性與失敗語意\n' > /tmp/t.txt

sort /tmp/t.txt | uniq -c
#   3 hook 測試覆蓋

LC_ALL=C sort /tmp/t.txt | LC_ALL=C uniq -c
#   2 hook 可靠性與失敗語意
#   1 hook 測試覆蓋
```

驗證環境：`LANG=en_US.UTF-8`，`LC_ALL` 與 `LC_COLLATE` 皆未設（`echo "LANG=$LANG LC_ALL=$LC_ALL LC_COLLATE=$LC_COLLATE"` 可確認）。第一次輸出把兩個不同字串合併為一行，並以實際只出現 1 次的字串標示總數 3；改用 `LC_ALL=C` 才拆出正確的「2」與「1」。

### 失效的形狀

- 輸出格式正常，無警告、無錯誤碼
- 總數守恆（3 = 2 + 1），加總對得起來，唯一常見的交叉檢查通不過異常偵測
- 唯獨分組錯誤，且顯示的類別名稱取自被合併的其中一方，另一方從輸出中完全消失

不比對其他來源（改變 locale 重跑、或逐一 byte-exact 計數）不會發現此問題——這不是「用錯工具」，是「正確用法在特定資料下靜默給錯答案」。

### 實際誤導案例（2026-08-24）

統計 ticket 主題分佈檔案時，以預設 locale 執行 `sort | uniq -c` 聚合中文主題字串，得出「某主題在存量範圍內有 64 張票」的結論；改用 `grep -cF` 逐一 byte-exact 比對後，實際筆數為 3 張，相差超過 20 倍。此數字若未被察覺即沿用，會作為前提寫入另一張票的交接內容，成為下游執行者未經查證即採信的錯誤起點。完整案例與防護表見 `.claude/error-patterns/implementation/IMP-BAL-013-locale-sort-uniq-merges-distinct-cjk-strings.md`。

### 影響面與替代寫法

本框架強制繁體中文輸出（`.claude/rules/core/language-constraints.md` 規則 1），ticket 主題、error-pattern 分類、worklog 標題皆為中文字串。凡以 shell 管線做聚合統計（`sort` / `uniq` / `comm` / `join`，皆依 collation 比較）者皆在射程內。

| 情境 | 替代寫法 |
|------|---------|
| 用 `sort \| uniq -c` 聚合中文字串統計次數 | 管線各命令前加 `LC_ALL=C`：`LC_ALL=C sort file \| LC_ALL=C uniq -c` |
| 只需驗證某一類別的精確筆數 | 改用 `grep -cF '<精確字串>' <來源檔>` 做 byte-exact 計數，不經排序/相等判斷 |
| 聚合結果將寫入 ticket 或交接文件成為他人前提 | 對關鍵類別另跑 `grep -cF` 交叉驗證，兩者不一致以 `grep -cF` 為準 |
| 撰寫涉及 CJK 聚合的腳本或 Hook | 預設即加 `LC_ALL=C`，不依賴呼叫端的 shell locale 環境 |

---

## 相關文件

- `.claude/rules/core/bash-tool-usage-rules.md` — 規則骨架（auto-load）
- `.claude/rules/core/tool-output-trust-rules.md` — confabulation 防護（規則一即時協議交叉引用）
- `.claude/references/quality-python.md` — Python 執行規則（類似規範）
- `.claude/error-patterns/implementation/IMP-008-bash-working-directory-pollution.md`
- `.claude/error-patterns/implementation/IMP-009-taskoutput-confusion.md`
- `.claude/error-patterns/implementation/IMP-046-git-index-lock-race-condition.md`（規則三情境一 + 情境二共同來源）
- `.claude/error-patterns/implementation/IMP-056-chpwd-shell-hook-floods-agent-output.md`
- `.claude/error-patterns/process-compliance/PC-046-unnecessary-cd-for-global-cli.md`
- `.claude/error-patterns/process-compliance/PC-079-bash-backtick-command-substitution-in-cli-args.md`
- `.claude/error-patterns/process-compliance/PC-087-pm-tmp-detour-for-ticket-content.md`
- `.claude/error-patterns/process-compliance/PC-BAL-008-shared-git-index-sweeps-parallel-agent-staged-files.md`（並行 commit 掃入他人檔案；口徑與規則三情境二一致：lock/index 競爭屬並行環境預期現象；規則七詳細「隔離索引 CAS」即此問題的加強解法；「變體：檔案級共用」與規則七詳細「核對步驟的粒度邊界」同根因）
- `.claude/skills/ticket/hooks/ticket-md-auto-commit-hook.py`（規則七詳細「隔離索引 CAS」的已驗證實作）
- `.claude/error-patterns/process-compliance/PC-139-git-index-lock-source-misattribution-gui-app-fork.md`
- `.claude/pm-rules/parallel-dispatch.md` — 並行派發 git staging / commit 紀律
- 框架 issue 34（`tarrragon/claude`）— 規則三情境二實驗來源，consumer `screen_clock` ticket `1.4.0-W2-030`
- `.claude/error-patterns/implementation/IMP-BAL-013-locale-sort-uniq-merges-distinct-cjk-strings.md`（規則八詳細的完整案例來源，含最小重現與防護表）
- `.claude/rules/core/language-constraints.md` 規則 1（規則八影響面：本框架強制繁體中文輸出，CJK 字串聚合統計皆在射程內）

---

**Last Updated**: 2026-08-24
**Version**: 1.7.0 — 新增「規則八詳細：CJK 資料聚合統計加 LC_ALL=C（locale collation 陷阱）」：`sort`/`uniq` 依 locale collation 而非位元組序比較，系統預設 locale 下會把相異 CJK 字串合併計數且無任何錯誤訊號；附最小重現、失效形狀、實際誤導案例（統計誤差 20 倍以上）、替代寫法對照表；主文速查條目見 `bash-tool-usage-rules.md` 規則八
**Version**: 1.6.0 — 規則七詳細新增「核對步驟的粒度邊界：檔案內夾帶」小節：`git diff --cached --name-only` 核對粒度為檔案層級，`git add` 最小單位即整個檔案，對同檔案內他人未 stage 的 hunk 無鑑別力；附 append-only 共用檔（`topic-assignments.txt`）處置建議表（`git add --patch` / 單一方提交 / commit 前 `git diff` 自查）；不改變規則七既有禁止事項，與 PC-BAL-008「變體：檔案級共用」同根因但聚焦核對步驟本身的侷限
**Version**: 1.5.0 — 新增「隔離索引提交的完整性三要件」小節：清單來源獨立於共用 index / GIT_INDEX_FILE 寫入隔離 / tree 層級提交前自檢，三要件缺一不可；補反例（commit `a7caabf4f`，清單改用 `git diff --cached --name-only` 掃入並行 ticket metadata，即使其餘兩要件正確執行仍整體失效）
**Version**: 1.4.0 — 新增「規則七詳細：隔離索引提交（GIT_INDEX_FILE CAS）」：TOCTOU 窗口說明 + read-tree/write-tree/commit-tree/update-ref 完整配方 + 適用條件表 + 與規則七主文關係；已驗證實作標註 `ticket-md-auto-commit-hook.py`（對應歷史 fix commit `bd849894a`）
**Version**: 1.3.0 — 規則三新增「情境二：唯讀 git 命令本身也會競爭 index.lock」（issue-34 實證：30 次併發 add 命中 1 次），修正「add 不觸發 Hook」的失準因果表述；index.lock 診斷改為「預設短暫重試」優先於「排查串接違規」；補與 PC-BAL-008 / parallel-dispatch.md 的口徑一致性說明（0.2.1-W3-262）
**Version**: 1.2.0 — 新增規則一即時協議（confabulation 防護四步）+ 規則六詳細（PYTHONUNBUFFERED + tee + 雙層緩衝根因 + 與規則二調和），自 bash-tool-usage-rules.md 主檔外移（1.0.0-W7-004.3 token 收斂）
**Version**: 1.1.0 — 新增規則五詳細（心理障礙破除 + 後退條件 + 觸發來源）（W15-007）
**Source**: IMP-008（cd 污染）、IMP-009（TaskOutput 混淆）、IMP-046（index.lock 競爭根因，含唯讀命令變體）、IMP-056（chpwd）、PC-046（高頻違規）、PC-087（PM /tmp 中介）、PC-139、PC-166（confabulation）、PC-BAL-008、W3-086（PYTHONUNBUFFERED spike）、issue-34
