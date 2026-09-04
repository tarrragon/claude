# Bash 工具使用規則

Claude Code Bash 工具的使用規範，涵蓋工作目錄、輸出處理、git 串接、git 提交範圍四大核心問題。

> **持久狀態意識**：Bash 在同一 session 內共享 shell。`cd` 永久改變工作目錄；大輸出存為暫存檔。
> **各規則速查表、Why/Consequence、根因圖解、chpwd 深度說明、即時協議論證、規則六調和**：`.claude/references/bash-tool-usage-details.md`

---

## 八規則一行速查

| 規則 | 核心要求 | 來源 |
|------|---------|------|
| 一：禁裸 cd | git 操作用 `git -C path <cmd>`（首選不觸發 chpwd）；非 git 用子 shell `(cd path && cmd)`；uv 用 `uv -d path run ...`；污染後 `cd /project/root &&` 還原。裸 cd 觸發 chpwd ls 淹沒，是 confabulation 觸發鏈第 1 環 | IMP-008 / IMP-056 / PC-046 / PC-166 |
| 二：輸出機制辨識 | `run_in_background:true` → `TaskOutput(taskId)`；輸出含「Full output saved to」→ `Read(file_path)`；其餘直讀對話。預防大輸出：測試 `2>&1 \| tail -20`、一般 `\| head -100`、Grep `head_limit`、Read `offset`+`limit`。**輸出過濾方向**：`tail` 截斷、grep 白名單、`grep -v` 皆屬選擇性過濾，都更容易濾掉警告行——警告通常比正常輸出短且措辭不同，與輸出長度無關（實測：3 行輸出中 `tail -2`／`-3` 等常用值正好切掉第 1 行 `[Error]`；CLI 參數驗證錯誤如 argparse 的 error 前綴在頭、回吐內容在尾同屬此類）；不確定輸出結構時改用 `head` 或 `head`+`tail` 兩段皆取，grep 白名單須含 `WARNING\|Error\|Traceback` | IMP-009 |
| 三：禁串接 git 寫入 | `git add && git commit` 允許（實務簡化，非「唯讀命令併發安全」保證）；commit/merge/rebase/push 之間禁串接。每個寫入操作獨立一個 Bash 呼叫。index.lock 競爭不限寫入串接——唯讀命令（status/diff-tree/log）refresh index stat cache 時也會短暫觸發，遇到預設短暫重試，非逕判串接違規 | IMP-046 / issue-34（30 次併發 add 命中 1 次） |
| 四：CLI backtick 不用雙引號 | 雙引號內 backtick 被當 command substitution。改用 heredoc `cmd "$(cat <<'EOF'...EOF)"`、單引號包整參數、或 Edit 直改 ticket md。看到來源不明 `command not found` / `ModuleNotFoundError` 優先查 backtick | PC-079 |
| 五：長文字用 heredoc | append-log / commit msg / ANA 結論直接 heredoc 傳 CLI，禁繞 `/tmp`。ARG_MAX ≥ 1 MB（macOS）/ 2 MB（Linux），80 行 markdown 約 3-8 KB 遠低於上限。> 100 KB 才考慮改 Edit 直改 ticket md | PC-087 |
| 六：長背景任務即時可觀察 | 需即時觀察用 `PYTHONUNBUFFERED=1 pytest -v tests/ 2>&1 \| tee /tmp/task.log`（告知 `tail -f`）；只需最終結果保留規則二 `\| tail`。雙層緩衝（fully-buffered + `\| tail` 等 EOF）使輸出檔全程 0 行 | 背景任務緩衝 spike 實驗 |
| 七：禁 pathspec / `--only` / `-o` 提交丟棄 index，禁廣域 staging 收尾合併 | `git commit -- <path>` 與 `--only`（`-o`）語意相同：皆以 HEAD 建臨時 index、填入指定路徑的 **working tree 內容**、據此 commit，等同丟棄既有 index，會吸入該路徑上他人未 stage 的編輯；`--include`（`-i`）不丟棄 index，但把指定路徑併入現有 index 一併提交，會連同 index 中他人已 staged 的檔案一起送出。並行環境（共用 working tree）三者皆禁用。正確替代：`git add <exact-path>` 精確 stage → `git diff --cached --name-only` 確認 index 只含目標檔 → 裸 `git commit`（不帶 pathspec、不帶 `--only`/`-o`/`-a`）。**衝突合併的收尾提交同受本規則管轄**：`git merge` 產生衝突後以 `git add -A` / `git add .` / `git commit -a` 完成該合併，會把工作區內與本次合併無關的未暫存編輯一併寫進 merge commit；正確替代同上——精確 `git add <衝突檔>` → 核對 index → 裸 `git commit` | 並行 session 誤吸實測案例（以 `git apply --cached` 正確暫存後改用 pathspec 提交，誤吸另一並行 session 尚未 stage 的編輯，事後以回滾 commit 精準還原） |
| 八：CJK 聚合統計加 LC_ALL=C | `sort`/`uniq`（含 `comm`/`join`）依目前 locale collation 比較，非位元組序；系統預設 locale（僅 `LANG` 未設 `LC_ALL`/`LC_COLLATE`）下會把位元組相異的中文字串判為相等並合併計數，且無警告、總數仍守恆，唯獨分組錯誤、標籤取自被合併一方。管線各命令前加 `LC_ALL=C`，或改用 `grep -cF` 逐一 byte-exact 計數；關鍵統計結果寫入交接文件前應交叉驗證 | IMP-BAL-013（最小重現與案例見 references 詳細版） |

> **chpwd 與即時協議**：裸 cd 觸發 zsh chpwd hook 的 ls 淹沒工具結果。輸出可疑/被淹沒當下依四步即時協議——停手 → 重發乾淨原子命令（`git -C`／子 shell）→ 只信 raw stdout → 固定值（hash／二元 grep／整數計數）驗證。論證見 details.md 規則一詳細 + `tool-output-trust-rules` 規則 1-4。

> **規則七高衝突路徑加強做法（隔離索引 CAS）**：規則七「精確 add + 核對 + 裸 commit」三步驟間仍共用同一個 git index，並行環境下有 TOCTOU 窗口。高頻/高衝突路徑（同一檔案集合被多來源高頻觸發 commit）可改用 `GIT_INDEX_FILE` 指向獨立臨時 index，全程以 `read-tree`/`write-tree`/`commit-tree`/`update-ref`（CAS，帶舊值移動 HEAD）操作，完全不觸碰共用 index；不取代規則七，屬並列的加強選項。已驗證實作見 `ticket-md-auto-commit-hook.py`。完整配方與適用條件見 details.md「規則七詳細」。

> **規則七核對步驟的粒度邊界（檔案內夾帶）**：`git diff --cached --name-only` 只列檔名，核對粒度為檔案層級——`git add` 的最小單位即整個檔案，目標檔本身已含他人未 stage 的編輯時，該編輯隨精確 add 一併進入 index，核對必然通過，對此無鑑別力（機制與 PC-BAL-008「變體：檔案級共用」同源）。**不改變規則七既有禁止事項**，pathspec / `--only` / `-o` / `-i` 仍全數禁用。append-only 共用檔（如 `docs/work-logs/topic-assignments.txt`，每次 `ticket create` 皆追加一行，屬結構性熱點）建議：`git add --patch` 逐 hunk 挑選，或約定由單一方負責提交該檔。完整機制見 details.md「規則七詳細」。

> **規則七核對步驟的版本邊界（過期 index 快照）**：核對步驟驗證 index 含哪些檔案，不驗證這些 entry 有多新。`git add` 後 HEAD 若由其他路徑前進（他方以隔離索引 CAS 提交同一檔案、`merge` / `rebase` / `pull`），既有 index entry 相對新 HEAD 即成舊版本，檔名層級與最新內容無從區分——核對通過、裸 commit 回滾檔案內容、`git log` 外觀正常，全程無訊號。此路徑不需任何一方違反規則七（另一條路徑是 pathspec 提交後不寫回共用 index，殘留過期 entry）。**偵測**：`git show :<path>` 與 `git show HEAD:<path>` 比對，難判斷時加 `cat <path>` 構成三平面。**處置**：`git restore --staged <path>` 重設回 HEAD 後重新精確 add。**不改變規則七既有禁止事項**。完整機制與最小重現見 details.md「規則七詳細」。

---

## 統一檢查清單

執行 Bash 命令前：

- [ ] 命令含 `cd`？→ git 操作用 `git -C`；其餘用子 shell `()` 或 `uv -d`（規則一）
- [ ] 多步驟序列？→ 第一步加絕對路徑 `cd /project/root &&`
- [ ] 輸出可能很大？→ 提前加 `head` / `tail`（規則二）
- [ ] CLI 參數驗證失敗風險（argparse 等）／輸出經 `tail`、grep 白名單或 `grep -v` 過濾？→ 警告行常比正常輸出短且措辭不同，與長度無關（`tail -2`/`-3` 可能切掉唯一的 `[Error]` 行），改用 `head` 或 `head`+`tail` 兩段皆取，grep 白名單須含 `WARNING\|Error\|Traceback`（規則二）
- [ ] `run_in_background:true`？→ `TaskOutput(taskId)`；含「Full output saved to」？→ `Read(file_path)`
- [ ] 串接多個 git 寫入（commit/merge/rebase/push）？→ 拆成獨立呼叫（規則三）
- [ ] 看到 `index.lock` 錯誤？→ 短暫重試為預設（並行環境屬預期現象，唯讀命令亦會觸發）；反覆失敗才排查串接或殘留鎖檔（規則三）
- [ ] CLI 參數含 backtick？→ 改用 heredoc / 單引號 / Edit 工具（規則四）
- [ ] 看到 `command not found` / `ModuleNotFoundError` 來源不明？→ 檢查 backtick command substitution（PC-079）
- [ ] 準備 `Write /tmp/*.md` 作 CLI 中介？→ 改 heredoc 直傳（規則五）
- [ ] 長背景任務需即時觀察？→ `PYTHONUNBUFFERED=1 <cmd> 2>&1 | tee <logfile>`，告知 `tail -f`（規則六）
- [ ] 背景任務輸出檔全程 0 行？→ 確認是否 `-q | tail` 雙層緩衝（規則六觸發條件）
- [ ] 輸出可疑/被淹沒？→ 停手重發乾淨原子命令，只信 raw stdout（規則一即時協議）
- [ ] 準備 `git commit -- <path>` / `--only` / `-o` / `-i`？→ 改精確 `git add <exact-path>` + `git diff --cached --name-only` 核對 index 範圍 + 裸 `git commit`（規則七）
- [ ] 目標檔是 append-only 共用檔（如 `topic-assignments.txt`）且他人可能有未 stage 的行？→ 核對只驗檔名無法鑑別檔內夾帶，改用 `git add --patch` 挑 hunk 或約定單一方提交（規則七邊界）
- [ ] `git merge` 產生衝突，準備以 `git add -A` / `git add .` / `git commit -a` 收尾？→ 廣域 staging 會把工作區內與本次合併無關的未暫存編輯寫進 merge commit，改精確 `git add <衝突檔>` + 核對 index + 裸 `git commit`（規則七）
- [ ] `git add` 與裸 commit 之間 HEAD 可能已被他方前進（並行環境常態）？→ 核對只驗檔名無法鑑別 index entry 過期，commit 前比對 `git show :<path>` 與 `git show HEAD:<path>`，判定過期則 `git restore --staged <path>` 後重新 add（規則七邊界）
- [ ] 準備以 `sort` / `uniq` / `comm` / `join` 聚合中文（CJK）字串做統計？→ 管線各命令前加 `LC_ALL=C`，或改用 `grep -cF` byte-exact 計數；結果將寫入交接文件前交叉驗證（規則八）

---

## 相關文件

- `.claude/references/bash-tool-usage-details.md` — 各規則速查表、根因圖解、Why/Consequence、即時協議論證、規則六調和、規則七過期快照最小重現、規則八最小重現
- `.claude/hooks/bare-commit-guard-hook.py` — 規則七的 hook 強制層（防護標的為範圍過寬；過期快照屬範圍正確而內容過舊，不在其涵蓋內）
- `.claude/rules/core/tool-output-trust-rules.md` — confabulation 防護（規則一即時協議）
- `.claude/references/quality-python.md` — Python 執行規則
- `.claude/error-patterns/implementation/IMP-008-bash-working-directory-pollution.md`、`IMP-009-taskoutput-confusion.md`、`IMP-046-git-index-lock-race-condition.md`、`IMP-BAL-013-locale-sort-uniq-merges-distinct-cjk-strings.md`
- `.claude/error-patterns/process-compliance/PC-079-bash-backtick-command-substitution-in-cli-args.md`、`PC-087-pm-tmp-detour-for-ticket-content.md`、`PC-BAL-008-shared-git-index-sweeps-parallel-agent-staged-files.md`
- `.claude/pm-rules/parallel-dispatch.md` — 並行派發 git staging / commit 紀律（index.lock 與跨票吸收防護口徑一致）

---

**Last Updated**: 2026-09-04 | **Version**: 3.9.0 — 規則二「截斷方向」條款泛化為「輸出過濾方向」：`tail` 截斷只是選擇性過濾的一種，grep 白名單／`grep -v` 同樣更容易濾掉警告行，與輸出長度無關（實測第二、三實例：3 行輸出中 `tail -2` 正好切掉第 1 行 `[Error]`）；速查表與統一檢查清單同步改寫，grep 白名單須含 `WARNING\|Error\|Traceback`。完整第二、三實例最小重現見 details.md「規則二詳細」新增小節。
**Last Updated**: 2026-09-02 | **Version**: 3.8.0 — 規則二新增「截斷方向」條款：CLI 參數驗證錯誤（argparse 等）error 前綴在頭、回吐內容在尾，單取 `tail` 會截掉唯一判別依據使失敗與成功回音同形（最小重現：argparse `unrecognized arguments` 錯誤在 `tail -20` 下完全不可見）；不確定輸出屬性時改用 `head` 或 `head`+`tail` 兩段皆取。速查表與統一檢查清單同步新增。完整重現數據見 details.md「規則二詳細」新增小節。
**Last Updated**: 2026-08-28 | **Version**: 3.7.0 — 規則七涵蓋範圍擴充至衝突合併的收尾提交：`git merge` 衝突後以 `git add -A` / `git add .` / `git commit -a` 收尾會把工作區內與本次合併無關的未暫存編輯寫進 merge commit，既有四項 pathspec 禁令對此路徑全數無效（實測命中 merge commit `89c57a1c9`）。速查表第七列標題與條文同步擴充，統一檢查清單新增一列；正確替代與既有條文一致（精確 add + 核對 + 裸 commit）。完整實證、處置表與 `PC-BAL-008` 歸屬判定見 details.md「規則七詳細」新增小節。**不改變既有四項禁令**。
**Version**: 3.6.0 — 規則七後新增第三則邊界說明「版本邊界（過期 index 快照）」：核對步驟驗證 index 含哪些檔案、不驗證 entry 有多新，`git add` 後 HEAD 由他方前進（隔離索引 CAS 提交 / merge / rebase / pull）即使雙方皆未違反規則七也會產生過期 entry，裸 commit 回滾檔案內容且 `git log` 外觀正常；條文含偵測法（`git show :<path>` vs `git show HEAD:<path>`，難判斷時加 working tree 構成三平面）與處置（`git restore --staged` 後重新 add）。統一檢查清單同步新增一列，相關文件補 `bare-commit-guard-hook.py` 涵蓋邊界。完整機制與最小重現外移 details.md「規則七詳細」新增小節。
**Version**: 3.5.0 — 新增規則八「CJK 聚合統計加 LC_ALL=C」：`sort`/`uniq` 依 locale collation 比較，系統預設 locale 下會把位元組相異的中文字串靜默合併計數（無警告、總數守恆、唯分組錯誤），管線加 `LC_ALL=C` 或改用 `grep -cF` byte-exact 計數；完整最小重現與案例外移 `references/bash-tool-usage-details.md` 規則八詳細，並新增 `IMP-BAL-013` error-pattern。速查表更名為「八規則一行速查」，統一檢查清單同步新增一列。
**Version**: 3.4.0 — 規則七後新增一則邊界說明：核對步驟（`git diff --cached --name-only`）粒度為檔案層級，對同檔案內他人未 stage 的 hunk 無鑑別力（`git add` 最小單位即檔案），並給 append-only 共用檔（如 `topic-assignments.txt`）處置建議（`git add --patch` 或單一方提交）；不改變規則七既有禁止事項。統一檢查清單同步新增一列。完整機制路由至 details.md「規則七詳細」新增小節。
**Version**: 3.3.0 — 規則七後補一則「隔離索引 CAS」加強做法（GIT_INDEX_FILE + read-tree/write-tree/commit-tree/update-ref，並列選項非取代），供高頻/高衝突路徑使用；完整配方外移 details.md
**Version**: 3.2.0 — 新增規則七「禁 pathspec / `--only` / `-o` 提交丟棄 index」：`git commit -- <path>` 與 `--only`/`-o` 語意相同，皆以 working tree 全文取代既有 index 建 commit，並行環境下會吸入他人未 stage 的編輯；`--include`/`-i` 不丟棄 index 但會連同他人已 staged 內容一併送出。條文含正確替代（精確 `git add` + `git diff --cached --name-only` 核對 + 裸 `git commit`）；六規則速查表與檢查清單同步擴充為七規則。**Version**: 3.1.0 — 規則三因果修正：index.lock 競爭不限寫入串接，唯讀 git 命令 refresh index stat cache 時亦會短暫觸發（issue-34 實證：30 次併發 add 命中 1 次），移除「add 不觸發 Hook」的失準表述；checklist 遇 index.lock 改為預設短暫重試而非逕判串接違規。**Version**: 3.0.0 — token 收斂：六規則濃縮為一行速查表 + 統一檢查清單，各規則速查表 / Why / Consequence / 論證外移 `references/bash-tool-usage-details.md`。歷史 2.0–2.3 版見 git log。**Source**: IMP-008、IMP-009、IMP-046、index.lock 競爭、PC-087、PC-166、issue-34
