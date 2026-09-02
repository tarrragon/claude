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

### 截斷方向：`head` 還是 `tail`（CLI 參數驗證錯誤場景）

**Why**：`tail -N` 假設「有用資訊在尾部」，對一般執行日誌（進度往下滾動、結論在最後）成立；但 argparse 等 CLI 參數驗證錯誤的訊息結構相反——`usage:` 與 `error:` 前綴固定印在最前面，若被拒的參數本身是多行內容（如 heredoc 傳入的 ticket 內文），argparse 會把該內容原文回吐在 error 訊息之後。此時「error 前綴」在頭、「回吐內容」在尾，`tail` 只取尾段等於只留下回吐內容，畫面與呼叫成功時的內容回音逐字相同。

**Consequence（最小重現，2026-09-02）**：以 argparse 模擬「unrecognized arguments」錯誤，被拒的 25 行 heredoc 內容隨錯誤訊息回吐：

```
$ python3 argp_test3.py ticket-1 --section Notes "$(cat <<'EOF'
line1
...
line25
EOF
)" 2>&1 | tail -20
line6
line7
...
line25
```

`tail -20` 的輸出完全看不到 `usage:` / `error: unrecognized arguments:` 這兩行判別依據，只剩內容本體——與呼叫成功時 stdout 回音內容的視覺形態相同。改用 `head -5` 則兩行前綴清楚可見：

```
$ ... | head -5
usage: argp_test3.py [-h] --section SECTION id
argp_test3.py: error: unrecognized arguments: line1
line2
line3
line4
```

實測後果（框架資產移交案例）：ticket CLI 的 append-log 兩次因參數誤用靜默失敗，PM 端僅看到 `tail` 截斷後的內容回音，誤判為成功；complete 閘門的 execution log 檢查同樣只掃字串存在與否，未能攔截。

**Action**：預防大輸出時，若命令屬於「CLI 參數/子命令呼叫」（非測試套件、非長 log），不確定其錯誤訊息的前綴位置時：
1. 優先改用 `head -40`（覆蓋 usage/error 前綴與多數短錯誤）；
2. 或兩段皆取：`2>&1 | head -20 && echo '...' && <same-cmd> 2>&1 | tail -20`（成本稍高，適合高風險呼叫如 ticket CLI 寫入）；
3. 已知該命令穩定產出「結論在尾部」的日誌（如 `pytest`、長編譯輸出）時，`tail` 仍是預設正確選擇，不需一律改 `head`。

**適用邊界**：本條款只影響「不確定輸出結構」時的截斷方向選擇，不改變規則二既有的 TaskOutput / Read 判斷流程圖。

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
| 1. 清單來源獨立於共用 index | 決定要提交哪些檔案的清單，必須取自呼叫端已知的精確來源（如 ticket `where.files` 宣告、或函式呼叫者作為引數傳入的檔案清單），禁止用 `git diff --cached --name-only` 或任何讀取共用 index 目前 staged 狀態的命令產生清單。此要件有第二維：`git status --porcelain` 反映整個工作區，多 PM session 並行時必然摻入他 session 尚在撰寫的檔案，清單來源同時須具備 session 歸屬過濾（見下方「工作區維度」小節） | 步驟 4（`git add -- <exact-file-1> <exact-file-2>`）的引數來源 |
| 2. 寫入使用 GIT_INDEX_FILE | 全程操作（read-tree / add / write-tree）在獨立臨時 index 中進行，不觸及共用 index | 步驟 2-6 |
| 3. 提交前以 tree 層級自檢範圍 | 建立 commit 物件前後皆須核對變更範圍恰為預期清單。可在步驟 5 產生 `TREE_SHA` 後立即以 `git diff-tree --no-commit-id --name-only -r HEAD <TREE_SHA>` 自檢（早於建立 commit 物件，發現不符即可提前放棄，不需先耗費一次 commit-tree），或沿用步驟 7 既有的 `git diff --name-only <OLD_HEAD> <COMMIT_SHA>`（commit 建立後比對）；兩者比對邏輯等價，擇一即可但不可省略 | 步驟 5 之後（提前版）或步驟 7（既有版） |

**Why**：要件 1 與要件 2 保護的對象不同——要件 2（`GIT_INDEX_FILE`）只隔離「寫入端」，確保臨時 index 的內容不被其他並行程序寫入干擾；但若決定「寫入端該寫入什麼」的清單來源（要件 1）仍取自共用 index 的目前狀態，隔離在入口就已經漏掉——清單本身可能已摻入其他並行程序剛好也 staged 到共用 index 的檔案，後續全程獨立操作只是把「已經錯誤的清單」精確地提交進去。要件 3 是最後一道防線，防止清單變數被 shell 展開錯誤、路徑筆誤帶入非預期檔、或 read-tree 基底與 HEAD 不一致等清單以外的失誤流入最終 commit。

**Consequence**：不滿足要件 1 時，維護者複製本配方常會沿用規則七主文「先核對現有共用 index 內容」的核對習慣作清單來源——因為全程操作看似「隔離」，出錯時更難聯想到問題出在清單來源而非寫入端；且要件 1 失守時，要件 2、3 仍會「正確地」執行完畢（`GIT_INDEX_FILE` 隔離無誤、diff 自檢也會「通過」，因為自檢比對的正是同一份已經錯誤的清單），三個環節各自看起來都沒有問題，只有整體行為（提交範圍）是錯的。

**反例**（實證）：commit `a7caabf4f`（2026-08-21，目錄級 where.files 宣告攔截功能提交）示範要件 1 失守的具體樣態——清單來源改用 `git diff --cached --name-only` 讀取共用 index 目前 staged 狀態，即使後續仍以 `GIT_INDEX_FILE` 隔離寫入、產生 tree、建立 commit，仍把另一張並行進行中 ticket 的 metadata 檔案（未在本次任務清單內，當時恰好也 staged 在共用 index）一併提交進去。三個要件中只有第一項出錯，但因清單是整個配方的輸入起點，錯誤會沿全程配方精確複製到最終 commit——其餘兩項做得再確實，也無法補救清單本身已經錯誤。

**要件 1 的工作區維度**：清單來源即使不讀共用 index（例如改讀 `git status --porcelain`），仍可能摻入非本次提交對象的檔案——多 PM session 並行的環境下，`git status --porcelain` 反映的是整個工作區，必然包含他 session 尚在撰寫、未完成的檔案。`has_active_background_agents()` 這類「有無活躍背景代理人」的整批跳過判準只擋「本 session 自己派發、追蹤中的代理人」這一種情境，無法涵蓋「他 session 直接 CLI 操作、未經派發追蹤」或「他 session 已完成派發但尚未輪到自身 turn-end」的情形。完整清單來源獨立性因此需要同時滿足兩維：獨立於共用 index（防夾帶他人已 staged 內容）**且**獨立於工作區其他 session（防誤提交他 session 在途工作）。已驗證實作見 `ticket-md-auto-commit-hook.py` 的 `get_session_claimed_ticket_ids`（以 `.claude/lib/pm_registry.py` 的 session 認領清單為正歸屬判準，歸屬無法判定時保守排除）。

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

### 規則七核對步驟的版本邊界：過期 index 快照

**現象**：核對步驟（`git diff --cached --name-only`）驗證的是 index 中有哪些檔案，不是這些檔案的內容有多新。index entry 是 `git add` 當下的內容快照，HEAD 之後若被其他路徑前進，該 entry 相對於新 HEAD 就成了舊版本，但在檔名層級與「剛 add 的最新內容」完全無從區分。核對通過、裸 commit 執行，檔案內容被回滾至舊版本，全程無警告。

**Why**：index 與 HEAD 是兩個獨立前進的平面。`git add` 只寫 index，不讀 HEAD；HEAD 前進（他方 commit、`merge`、`rebase`、`pull`）也不改寫既有 index entry。兩者失去同步時，index 相對新 HEAD 呈現為「staged 的舊內容」，而 `--name-only` 的輸出粒度是檔名，看不到版本維度。

**產生路徑**（兩條，後者不需任何一方違反規則七）：

| 路徑 | 機制 | 需違反規則七？ |
|------|------|--------------|
| A：pathspec 提交後 index 未寫回 | `git commit -- <path>` / `--only` / `-o` 以 HEAD 建臨時 index 提交，提交後不寫回共用 index，先前 `git add` 的 entry 原封留著，相對新 HEAD 已是舊內容 | 是（但非並行期間 `bare-commit-guard-hook.py` 僅 WARN 不阻擋，該路徑實際可被執行） |
| B：HEAD 由他方前進 | 己方 `git add <path>` 後，另一 session 以隔離索引 CAS 提交同一檔案的新版本（或發生 `merge` / `rebase` / `pull`），HEAD 前進而共用 index entry 未動 | 否——雙方各自都遵守規則，屬並行環境的結構性現象 |

路徑 B 是本節的主要理由。隔離索引 CAS 普及後（見上方「隔離索引提交」小節），HEAD 在他方 `git add` 與裸 commit 之間前進的機會隨之增加。

**Consequence**：檔案內容退回舊版本並寫入歷史。ticket md 的情形是狀態欄位被回滾（`in_progress` 變回 `pending`）；程式碼檔則是整份退版。歷史外觀完全正常——被覆寫的那個 commit 仍在 `git log` 中，只有比對檔案內容才看得出回滾，無任何異常訊號可供事後歸因。

**最小重現**（可自行執行驗證，`$D` 為任一臨時 repo）：

```bash
printf 'v1\n' > "$D/a.txt"; git -C "$D" add a.txt; git -C "$D" commit -q -m base
printf 'v2\n' > "$D/a.txt"; git -C "$D" add a.txt     # 共用 index = v2
printf 'v3\n' > "$D/a.txt"                            # working tree = v3

# 他方以隔離索引 CAS 提交 v3（完全不碰共用 index），HEAD 前進
OLD=$(git -C "$D" rev-parse HEAD)
GIT_INDEX_FILE=$(mktemp -u) sh -c "
  git -C '$D' read-tree $OLD
  git -C '$D' update-index --add a.txt
  T=\$(git -C '$D' write-tree)
  N=\$(git -C '$D' commit-tree \$T -p $OLD -m 'peer commits v3')
  git -C '$D' update-ref \$(git -C '$D' symbolic-ref HEAD) \$N $OLD"

git -C "$D" diff --cached --name-only    # a.txt —— 核對通過，index 確實只含目標檔
git -C "$D" show HEAD:a.txt              # v3
git -C "$D" show :a.txt                  # v2 —— index entry 相對新 HEAD 已過期
git -C "$D" commit -q -m "bare commit after passing the name-only check"
git -C "$D" show HEAD:a.txt              # v2 —— 內容被回滾，git log 三個 commit 外觀正常
```

**Action**：

| 情境 | 處置 |
|------|------|
| 通過核對步驟後、裸 commit 之前（並行環境常態） | 加一道版本比對：`git show :<path>` 與 `git show HEAD:<path>` 內容不同時，確認差異是自己這次的編輯，而非 index 停留在舊版本 |
| 無法判斷 index entry 是過期快照還是刻意暫存的中間版本 | 三平面比對——`git show HEAD:<path>`（HEAD）、`git show :<path>`（index）、`cat <path>`（working tree）。index 內容既非 HEAD 亦非 working tree，且無從說明為何是那個版本時，視為過期 |
| 已判定為過期快照 | `git restore --staged <path>` 將 index 重設回 HEAD，再重新精確 `git add <path>` 取當下 working tree 內容 |
| 高頻/高衝突路徑 | 改用上方「隔離索引 CAS 配方」——以 `read-tree` 從當下 HEAD 重建臨時 index，內容不取自共用 index，本邊界自然不適用 |

**與既有兩則邊界的關係**：三則邊界的失效維度互不重疊——「隔離索引 CAS」處理三步驟間的**時序窗口**，「檔案內夾帶」處理同一檔案內的 **hunk 粒度**，本節處理 index entry 相對 HEAD 的**版本新舊**。**邊界（不變）**：本節同樣不改變規則七既有禁止事項，`git commit -- <path>` / `--only` / `-o` / `-i` 的禁令與其論證維持不變。

**與既有防護層的關係**：`.claude/hooks/bare-commit-guard-hook.py` 以「裸 commit 可用 staged 快照驗證安全性」為放行前提（見該檔 docstring）。過期快照使該前提在內容維度失效：檔名範圍驗證仍通過，內容卻是舊版。該 hook 的防護標的是**範圍過寬**（吸入他人檔案），本節的失效形態是**範圍正確而內容過舊**，兩者不互相涵蓋。

### 規則七的涵蓋擴充：衝突合併收尾的廣域 staging

**現象**：`git merge` 產生衝突後，以 `git add -A` / `git add .` / `git commit -a` 完成該合併，工作區內與本次合併無關的未暫存編輯一併寫進 merge commit。commit 成功、退出碼 0、內容正確、訊息正常——與規則七既有四項禁令一樣屬零訊號的靜默污染。

**Why**：`git add -A` 的定址範圍是整個工作區，不是「本次合併涉及的檔案」。衝突狀態特別容易誘導廣域 staging——`git status` 在衝突期間列出的 unmerged 檔案讓人以為 staging 範圍已被合併狀態限定，實際上 `-A` 照樣掃過工作區的每一個修改。merge commit 的多 parent 結構又使事後歸因困難：diff 相對於哪個 parent 計算會給出不同答案，「這個變更是合併帶進來的還是被捲進來的」不容易一眼判定。

**Consequence**：輕則 provenance 污染——merge commit 的 diff 含其標題所述範圍外的變更，後續考古把 A 的工作歸因到這次合併。重則提交半成品（捲入的編輯尚未完稿）或造成覆蓋（兩方同時編輯同檔）。與規則七既有禁令的差別在於，本路徑不需要任何 pathspec 形式，單純 `git add -A` 即觸發，故四項禁令對它全數無效。

**實證**（本專案 2026-08-26，merge commit `89c57a1c9`）：並行 session 合併 worktree 分支時產生衝突，收尾提交把本 session 代理人尚未提交的 `.claude/pm-rules/parallel-dispatch.md` 編輯捲入。判定「內容來自工作區」用三方行數比對：

| 觀測 | 值 |
|------|-----|
| parent 1 該檔行數 | 1020 |
| parent 2 該檔行數 | 1020 |
| merge 結果該檔行數 | 926 |
| 該檔是否在 incoming 變更範圍（`git diff --name-only <p1>...<p2>`） | 否 |

合併結果含有兩個 parent 皆不存在的內容，且該檔不在合併的變更範圍內，唯一來源即工作區。**本次是代理人 `ticket track commit` 的檔數自我驗證（預期兩檔實得一檔）才暴露**——一般提交流程沒有這道自我驗證，捲入不會產生任何訊號。

**Action**：

| 情境 | 處置 |
|------|------|
| 衝突解決完畢，準備收尾提交 | 精確 `git add <衝突檔>` → `git diff --cached --name-only` 核對 index 僅含衝突檔與本次合併應有的變更 → 裸 `git commit`（`git merge --continue` 亦讀 index，同樣受此核對保護） |
| 合併前工作區已有未暫存的無關編輯 | 合併前先處置（提交或 `git stash`），不留在工作區等合併結束——`-A` 之外，衝突期間的多次 `git add` 也容易誤觸 |
| 已發生捲入 | 依規則七既有條文：**不得** `revert` / `reset --soft` / `commit --amend` / 反向套用。被捲入的內容與他方同窗口的合法寫入在 diff 上不可區分，任一還原動作都會連帶撤銷後者。記錄 commit SHA 與檔案清單於 ticket，上報 PM |

**與既有防護層的關係**：派發骨架（`agent-dispatch-template.md` / `track_dispatch.py` 的 `SKELETON_TEMPLATE_NORMAL`）的 Forbidden 行已同時禁 `git add . / git add -A` 與 `git commit -a`，涵蓋本節兩種載體；缺口原本只在規則七主文——規則七列的是四種 pathspec 形式，未把廣域 staging 納入自身射程，本節補此涵蓋。`bare-commit-guard-hook.py` 與 `dispatch-staging-phrase-guard-hook.py` 皆不涵蓋 merge 收尾（前者攔 pathspec commit，後者檢查派發 prompt 的片語完整性），強制層是否加碼屬另一議題，不在本節範圍。

**與 PC-BAL-008 的歸屬判定**：本機制**應併入 `PC-BAL-008` 作為新變體**，不另立 error-pattern。判定依據三項——(1) 該 PC 的根因抽象層是「commit 範圍大於意圖且無訊號」，本節是同一抽象下的另一載體，該 PC 已用「變體：檔案級共用」章節容納過一次相同性質的擴充；(2) 讀者遇到「commit 含非預期檔案」時只需查一份文件，另立新 PC 會迫使讀者在兩份相似文件間先判定載體差異，而該判定正是事發當下最難做的；(3) 該 PC 的預防措施（隔離索引、commit 後驗證錨定 SHA 而非 `HEAD`）對本節同樣適用，另立會整段重複。**併入的代價**：該 PC 標題含 `parallel-agent`，而本機制在單 session 自行合併時亦會發生，併入時需於變體章節明示此差異。

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
- `.claude/hooks/bare-commit-guard-hook.py`（規則七的 hook 強制層；其放行裸 commit 的前提「staged 快照可驗證安全性」在過期快照下於內容維度失效，見規則七詳細「版本邊界」）
- `.claude/error-patterns/process-compliance/PC-139-git-index-lock-source-misattribution-gui-app-fork.md`
- `.claude/pm-rules/parallel-dispatch.md` — 並行派發 git staging / commit 紀律
- 框架 issue 34（`tarrragon/claude`）— 規則三情境二實驗來源，consumer `screen_clock` ticket `1.4.0-W2-030`
- `.claude/error-patterns/implementation/IMP-BAL-013-locale-sort-uniq-merges-distinct-cjk-strings.md`（規則八詳細的完整案例來源，含最小重現與防護表）
- `.claude/rules/core/language-constraints.md` 規則 1（規則八影響面：本框架強制繁體中文輸出，CJK 字串聚合統計皆在射程內）

---

**Last Updated**: 2026-09-02
**Version**: 1.11.0 — 規則二詳細新增「截斷方向：`head` 還是 `tail`（CLI 參數驗證錯誤場景）」小節：argparse 等 CLI 驗證錯誤的 `usage:`/`error:` 前綴固定在頭、被拒的多行參數內容回吐在尾，單取 `tail` 會截掉唯一判別依據使失敗與成功回音同形；附可執行最小重現（`tail -20` 完全看不到前綴 vs `head -5` 前綴清楚可見）、實測後果（ticket CLI append-log 靜默失敗案例）與 Action（不確定輸出結構時改 `head` 或 `head`+`tail` 兩段皆取，穩定尾部結論日誌維持 `tail`）；主文速查條目與統一檢查清單見 `bash-tool-usage-rules.md` 規則二
**Version**: 1.10.0 — 規則七詳細新增「涵蓋擴充：衝突合併收尾的廣域 staging」小節：`git merge` 衝突後以 `git add -A` / `git add .` / `git commit -a` 收尾會把工作區無關的未暫存編輯寫進 merge commit，四項既有禁令對此路徑全數無效；附實證（merge commit `89c57a1c9`，兩 parent 皆 1020 行 / merge 926 行 / 該檔不在 incoming 變更範圍，三方比對判定內容源自工作區）、正確替代與已發生時的處置表；並記錄與派發骨架 Forbidden 行的涵蓋落差（骨架已擋、規則主文未擋），以及本機制應併入 `PC-BAL-008` 作為新變體的判定與三項依據
**Version**: 1.9.0 — 規則七詳細新增「核對步驟的版本邊界：過期 index 快照」小節：核對步驟驗證 index 含哪些檔案、不驗證 entry 相對 HEAD 有多新；列兩條產生路徑（A pathspec 提交後不寫回共用 index；B 他方以隔離索引 CAS 提交 / merge / rebase / pull 使 HEAD 前進，雙方皆未違規），附可執行最小重現（核對通過 → 裸 commit → 內容回滾至舊版本，`git log` 外觀正常）、三平面比對偵測法與 `git restore --staged` 處置表；並明示三則邊界失效維度互不重疊（時序窗口 / hunk 粒度 / 版本新舊）、與 `bare-commit-guard-hook.py` 防護標的的差異（範圍過寬 vs 範圍正確而內容過舊）；不改變規則七既有禁止事項
**Version**: 1.8.0 — 「隔離索引提交的完整性三要件」要件 1 補工作區維度：`git status --porcelain` 反映整個工作區，多 PM session 並行時必然摻入他 session 在途工作，清單來源需同時獨立於共用 index 與其他 session；已驗證實作見 `ticket-md-auto-commit-hook.py` 的 `get_session_claimed_ticket_ids`（以 pm-registry 認領清單為正歸屬判準，歸屬無法判定時保守排除）
**Version**: 1.7.0 — 新增「規則八詳細：CJK 資料聚合統計加 LC_ALL=C（locale collation 陷阱）」：`sort`/`uniq` 依 locale collation 而非位元組序比較，系統預設 locale 下會把相異 CJK 字串合併計數且無任何錯誤訊號；附最小重現、失效形狀、實際誤導案例（統計誤差 20 倍以上）、替代寫法對照表；主文速查條目見 `bash-tool-usage-rules.md` 規則八
**Version**: 1.6.0 — 規則七詳細新增「核對步驟的粒度邊界：檔案內夾帶」小節：`git diff --cached --name-only` 核對粒度為檔案層級，`git add` 最小單位即整個檔案，對同檔案內他人未 stage 的 hunk 無鑑別力；附 append-only 共用檔（`topic-assignments.txt`）處置建議表（`git add --patch` / 單一方提交 / commit 前 `git diff` 自查）；不改變規則七既有禁止事項，與 PC-BAL-008「變體：檔案級共用」同根因但聚焦核對步驟本身的侷限
**Version**: 1.5.0 — 新增「隔離索引提交的完整性三要件」小節：清單來源獨立於共用 index / GIT_INDEX_FILE 寫入隔離 / tree 層級提交前自檢，三要件缺一不可；補反例（commit `a7caabf4f`，清單改用 `git diff --cached --name-only` 掃入並行 ticket metadata，即使其餘兩要件正確執行仍整體失效）
**Version**: 1.4.0 — 新增「規則七詳細：隔離索引提交（GIT_INDEX_FILE CAS）」：TOCTOU 窗口說明 + read-tree/write-tree/commit-tree/update-ref 完整配方 + 適用條件表 + 與規則七主文關係；已驗證實作標註 `ticket-md-auto-commit-hook.py`（對應歷史 fix commit `bd849894a`）
**Version**: 1.3.0 — 規則三新增「情境二：唯讀 git 命令本身也會競爭 index.lock」（issue-34 實證：30 次併發 add 命中 1 次），修正「add 不觸發 Hook」的失準因果表述；index.lock 診斷改為「預設短暫重試」優先於「排查串接違規」；補與 PC-BAL-008 / parallel-dispatch.md 的口徑一致性說明（0.2.1-W3-262）
**Version**: 1.2.0 — 新增規則一即時協議（confabulation 防護四步）+ 規則六詳細（PYTHONUNBUFFERED + tee + 雙層緩衝根因 + 與規則二調和），自 bash-tool-usage-rules.md 主檔外移（1.0.0-W7-004.3 token 收斂）
**Version**: 1.1.0 — 新增規則五詳細（心理障礙破除 + 後退條件 + 觸發來源）（W15-007）
**Source**: IMP-008（cd 污染）、IMP-009（TaskOutput 混淆）、IMP-046（index.lock 競爭根因，含唯讀命令變體）、IMP-056（chpwd）、PC-046（高頻違規）、PC-087（PM /tmp 中介）、PC-139、PC-166（confabulation）、PC-BAL-008、W3-086（PYTHONUNBUFFERED spike）、issue-34
