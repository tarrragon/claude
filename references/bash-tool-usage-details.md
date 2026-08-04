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
- `.claude/error-patterns/process-compliance/PC-BAL-008-shared-git-index-sweeps-parallel-agent-staged-files.md`（並行 commit 掃入他人檔案；口徑與規則三情境二一致：lock/index 競爭屬並行環境預期現象）
- `.claude/error-patterns/process-compliance/PC-139-git-index-lock-source-misattribution-gui-app-fork.md`
- `.claude/pm-rules/parallel-dispatch.md` — 並行派發 git staging / commit 紀律
- 框架 issue 34（`tarrragon/claude`）— 規則三情境二實驗來源，consumer `screen_clock` ticket `1.4.0-W2-030`

---

**Last Updated**: 2026-08-04
**Version**: 1.3.0 — 規則三新增「情境二：唯讀 git 命令本身也會競爭 index.lock」（issue-34 實證：30 次併發 add 命中 1 次），修正「add 不觸發 Hook」的失準因果表述；index.lock 診斷改為「預設短暫重試」優先於「排查串接違規」；補與 PC-BAL-008 / parallel-dispatch.md 的口徑一致性說明（0.2.1-W3-262）
**Version**: 1.2.0 — 新增規則一即時協議（confabulation 防護四步）+ 規則六詳細（PYTHONUNBUFFERED + tee + 雙層緩衝根因 + 與規則二調和），自 bash-tool-usage-rules.md 主檔外移（1.0.0-W7-004.3 token 收斂）
**Version**: 1.1.0 — 新增規則五詳細（心理障礙破除 + 後退條件 + 觸發來源）（W15-007）
**Source**: IMP-008（cd 污染）、IMP-009（TaskOutput 混淆）、IMP-046（index.lock 競爭根因，含唯讀命令變體）、IMP-056（chpwd）、PC-046（高頻違規）、PC-087（PM /tmp 中介）、PC-139、PC-166（confabulation）、PC-BAL-008、W3-086（PYTHONUNBUFFERED spike）、issue-34
