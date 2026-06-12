# Bash 工具使用規則

Claude Code Bash 工具的使用規範，涵蓋工作目錄、輸出處理、git 串接三大核心問題。

> **持久狀態意識**：Bash 在同一 session 內共享 shell。`cd` 永久改變工作目錄；大輸出存為暫存檔。
> **各規則速查表、Why/Consequence、根因圖解、chpwd 深度說明、即時協議論證、規則六調和**：`.claude/references/bash-tool-usage-details.md`

---

## 六規則一行速查

| 規則 | 核心要求 | 來源 |
|------|---------|------|
| 一：禁裸 cd | git 操作用 `git -C path <cmd>`（首選不觸發 chpwd）；非 git 用子 shell `(cd path && cmd)`；uv 用 `uv -d path run ...`；污染後 `cd /project/root &&` 還原。裸 cd 觸發 chpwd ls 淹沒，是 confabulation 觸發鏈第 1 環 | IMP-008 / IMP-056 / PC-046 / PC-166 |
| 二：輸出機制辨識 | `run_in_background:true` → `TaskOutput(taskId)`；輸出含「Full output saved to」→ `Read(file_path)`；其餘直讀對話。預防大輸出：測試 `2>&1 \| tail -20`、一般 `\| head -100`、Grep `head_limit`、Read `offset`+`limit` | IMP-009 |
| 三：禁串接 git 寫入 | `git add && git commit` 允許（add 不觸發 Hook）；commit/merge/rebase/push 之間禁串接（競爭 index.lock）。每個寫入操作獨立一個 Bash 呼叫 | index.lock 競爭 |
| 四：CLI backtick 不用雙引號 | 雙引號內 backtick 被當 command substitution。改用 heredoc `cmd "$(cat <<'EOF'...EOF)"`、單引號包整參數、或 Edit 直改 ticket md。看到來源不明 `command not found` / `ModuleNotFoundError` 優先查 backtick | PC-079 |
| 五：長文字用 heredoc | append-log / commit msg / ANA 結論直接 heredoc 傳 CLI，禁繞 `/tmp`。ARG_MAX ≥ 1 MB（macOS）/ 2 MB（Linux），80 行 markdown 約 3-8 KB 遠低於上限。> 100 KB 才考慮改 Edit 直改 ticket md | PC-087 / W15-005 |
| 六：長背景任務即時可觀察 | 需即時觀察用 `PYTHONUNBUFFERED=1 pytest -v tests/ 2>&1 \| tee /tmp/task.log`（告知 `tail -f`）；只需最終結果保留規則二 `\| tail`。雙層緩衝（fully-buffered + `\| tail` 等 EOF）使輸出檔全程 0 行 | W3-086 spike |

> **chpwd 與即時協議**：裸 cd 觸發 zsh chpwd hook 的 ls 淹沒工具結果。輸出可疑/被淹沒當下依四步即時協議——停手 → 重發乾淨原子命令（`git -C`／子 shell）→ 只信 raw stdout → 固定值（hash／二元 grep／整數計數）驗證。論證見 details.md 規則一詳細 + `tool-output-trust-rules` 規則 1-4。

---

## 統一檢查清單

執行 Bash 命令前：

- [ ] 命令含 `cd`？→ git 操作用 `git -C`；其餘用子 shell `()` 或 `uv -d`（規則一）
- [ ] 多步驟序列？→ 第一步加絕對路徑 `cd /project/root &&`
- [ ] 輸出可能很大？→ 提前加 `head` / `tail`（規則二）
- [ ] `run_in_background:true`？→ `TaskOutput(taskId)`；含「Full output saved to」？→ `Read(file_path)`
- [ ] 串接多個 git 寫入（commit/merge/rebase/push）？→ 拆成獨立呼叫（規則三）
- [ ] 看到 `index.lock` 錯誤？→ 確認是否有 git 串接
- [ ] CLI 參數含 backtick？→ 改用 heredoc / 單引號 / Edit 工具（規則四）
- [ ] 看到 `command not found` / `ModuleNotFoundError` 來源不明？→ 檢查 backtick command substitution（PC-079）
- [ ] 準備 `Write /tmp/*.md` 作 CLI 中介？→ 改 heredoc 直傳（規則五）
- [ ] 長背景任務需即時觀察？→ `PYTHONUNBUFFERED=1 <cmd> 2>&1 | tee <logfile>`，告知 `tail -f`（規則六）
- [ ] 背景任務輸出檔全程 0 行？→ 確認是否 `-q | tail` 雙層緩衝（規則六觸發條件）
- [ ] 輸出可疑/被淹沒？→ 停手重發乾淨原子命令，只信 raw stdout（規則一即時協議）

---

## 相關文件

- `.claude/references/bash-tool-usage-details.md` — 各規則速查表、根因圖解、Why/Consequence、即時協議論證、規則六調和
- `.claude/rules/core/tool-output-trust-rules.md` — confabulation 防護（規則一即時協議）
- `.claude/references/quality-python.md` — Python 執行規則
- `.claude/error-patterns/implementation/IMP-008-bash-working-directory-pollution.md`、`IMP-009-taskoutput-confusion.md`
- `.claude/error-patterns/process-compliance/PC-079-bash-backtick-command-substitution-in-cli-args.md`、`PC-087-pm-tmp-detour-for-long-text.md`

---

**Last Updated**: 2026-06-12 | **Version**: 3.0.0 — token 收斂：六規則濃縮為一行速查表 + 統一檢查清單，各規則速查表 / Why / Consequence / 論證外移 `references/bash-tool-usage-details.md`（1.0.0-W7-004.3）。歷史 2.0–2.3 版見 git log。**Source**: IMP-008、IMP-009、index.lock 競爭、PC-087、W3-086、PC-166
