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

### 根因圖解（index.lock 競爭流程）

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

### 為何 `git add && git commit` 允許

| 操作 | 是否觸發 PostToolUse Hook 內的 git 競爭 |
|------|--------------------------------------|
| `git add` | 否（add 不改變 HEAD，Hook 內的 `git status`/`git log` 不衝突） |
| `git commit` | 是（commit 寫入 HEAD，Hook 同時讀取 HEAD 有輕微競爭但 commit 完成後 Hook 才跑） |

**關鍵**：commit 之後不可再串接 merge/push/rebase。add + commit 是唯一安全的組合（add 在 commit 之前完成，不與後續 Hook 競爭）。

### index.lock 錯誤的診斷

看到 `fatal: Unable to create index.lock` 錯誤時，依序檢查：

1. 是否有 git 操作串接？→ 拆成獨立 Bash 呼叫
2. 是否有殘留的 `.git/index.lock` 檔案？→ `git-index-lock-cleanup-hook.py` 會自動清理，若失敗可手動 `rm .git/index.lock`
3. 是否有其他 process 正在使用 git？→ 檢查 `ps aux | grep git`

---

## 規則五詳細：長文字傳遞預設使用 heredoc

### 心理障礙破除

PM 歷史上多次繞 `/tmp` 寫中介檔（PC-087），根因是**誤以為 heredoc 有容量限制**。實測：

- macOS ARG_MAX = 1,048,576 bytes（1 MB）
- Linux ARG_MAX 通常 ≥ 2 MB
- 單次 `ticket track append-log --content "$(cat <<'EOF' ... EOF)"` 可安全傳遞 800 KB+ 純文字
- 80 行密集中文 markdown 約 3-8 KB，完全在容量內

**為何 PM 仍繞 /tmp**：
1. LLM 訓練資料中 shell 「長字串用檔案」是常識模式，但那是針對傳統 shell 限制（512 KB 以下）
2. 沒有容量事實的錨定，直覺保守
3. `/tmp` 中介看似「更穩」，實際多兩次 IO + 遺留清理負擔

### 正確模式範例

```bash
ticket track append-log 0.18.0-W15-007 --section Solution --content "$(cat <<'EOF'
## Solution

實作摘要：
1. 主檔規則五新增（<30 行）
2. 規則四交叉引用補充
3. details.md 補心理障礙破除段
4. auto-memory 雙通道建立
EOF
)"
```

quoted delimiter (`'EOF'`) 禁用變數展開與 command substitution，內容原樣傳入，安全於 backtick 與 `$var`。

### 後退條件

若 3 個月內（2026-07-18 前）仍偵測到 PM 繞 `/tmp` 寫中介檔案的案例 ≥ 2 次，升級方案：

- 建立 pre-Write hook：Write 目標為 `/tmp/*.md` 且 content > 500 bytes 時警告「長文字應 heredoc 直傳，見 bash 規則五」
- 參考 W15-005 WRAP 方案 F（Hook 升級路徑）

### 觸發來源

- PC-087（PM 寫 /tmp 中介）直接觸發
- W15-005 WRAP 分析確認方案 E（規則 + memory + 交叉引用）為最低成本最大覆蓋方案
- W15-007 落地實作

---

## 相關文件

- `.claude/rules/core/bash-tool-usage-rules.md` — 規則骨架（auto-load）
- `.claude/references/quality-python.md` — Python 執行規則（類似規範）
- `.claude/error-patterns/implementation/IMP-008-bash-working-directory-pollution.md`
- `.claude/error-patterns/implementation/IMP-009-taskoutput-confusion.md`
- `.claude/error-patterns/implementation/IMP-056-chpwd-shell-hook-floods-agent-output.md`
- `.claude/error-patterns/process-compliance/PC-046-unnecessary-cd-for-global-cli.md`

---

**Last Updated**: 2026-04-18
**Version**: 1.1.0 — 新增規則五詳細（心理障礙破除 + 後退條件 + 觸發來源）（W15-007）
**Source**: IMP-008（cd 污染）、IMP-009（TaskOutput 混淆）、IMP-056（chpwd）、PC-046（高頻違規）、index.lock 競爭、PC-087（PM /tmp 中介）
