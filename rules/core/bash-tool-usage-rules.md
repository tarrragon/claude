# Bash 工具使用規則

Claude Code Bash 工具的使用規範，涵蓋工作目錄、輸出處理、git 串接三大核心問題。

> **持久狀態意識**：Bash 在同一 session 內共享 shell。`cd` 會永久改變工作目錄；大輸出會存為暫存檔。
> **詳細案例、根因圖解、chpwd 深度說明**：`.claude/references/bash-tool-usage-details.md`

---

## 規則一：禁止使用 cd 改變持久工作目錄

| 場景 | 錯誤做法 | 正確做法 |
|------|---------|---------|
| 在特定目錄執行命令 | `cd .claude/skills/ticket && uv run ...` | `(cd .claude/skills/ticket && uv run ...)` |
| uv 指定目錄 | `cd .claude/skills/ticket && uv run ...` | `uv -d .claude/skills/ticket run ...` |
| 工作目錄已污染 | 無操作 | `cd /your/project/root && ...` |

**三種安全做法速查**：

| 方法 | 指令形式 | 適用情境 |
|------|---------|---------|
| 子 shell（推薦） | `(cd path && command)` | 任何命令，通用最廣 |
| uv -d 參數 | `uv -d path run ...` | 僅限 uv 指令 |
| 絕對路徑還原 | `cd /project/root && ...` | 污染後補救 |

> **chpwd 警告**：本環境 zsh 有 `chpwd` hook，裸 `cd` 觸發 `ls` 淹沒工具結果。必須用子 shell `()`。

---

## 規則二：正確區分 TaskOutput vs 暫存輸出檔案

| 機制 | 觸發條件 | 識別特徵 | 正確處理工具 |
|------|---------|---------|------------|
| 背景任務 | `run_in_background: true` | 訊息含「background task」 | `TaskOutput(taskId)` |
| 暫存輸出檔案 | 輸出 > 2KB | `Full output saved to: /path/...txt` | `Read(file_path)` |
| 一般同步輸出 | 小於 2KB 同步執行 | 無上述特徵 | 直接讀對話輸出 |

**主動預防大輸出**：

| 工具 | 大輸出防護 |
|------|----------|
| Bash（測試） | `flutter test 2>&1 \| tail -20` |
| Bash（一般） | `命令 \| head -100` 或 `\| wc -l` 確認大小 |
| Grep | 使用 `head_limit` 限制回傳行數 |
| Read | 使用 `offset` + `limit` 分頁讀取 |

---

## 規則三：禁止串接多個 git 寫入操作

| 組合 | 允許 | 原因 |
|------|------|------|
| `git add && git commit` | 允許 | add 不觸發 Hook，commit 是唯一寫入 |
| `git commit && git merge` | 禁止 | Hook 和 merge 競爭 index.lock |
| `git commit && git push` | 禁止 | push 可能觸發遠端 Hook |
| `git merge && git push` | 禁止 | 同上 |

**正確做法**：每個 git 寫入操作（commit/merge/rebase/push）獨立一個 Bash 呼叫。

---

## 規則四：CLI 參數含 backtick 禁止用雙引號直接傳入

> 來源：PC-079。雙引號字串內的 backtick 被 Bash 解析為 command substitution，字元在傳給 CLI 前已被替換。

| 場景 | 錯誤做法 | 正確做法 |
|------|---------|---------|
| Markdown 路徑參考 | `ticket track append-log ID --section "S" "檔案 \`src/x.py\` 說明"` | heredoc 或單引號或 Edit 直接編輯 ticket md |
| 程式碼片段傳入 | `python3 -c "print(\`cmd\`)"` | 用單引號 `python3 -c 'print(...)'` |
| Commit 訊息含 backtick | `git commit -m "修改 \`x.py\`"` | `git commit -m "$(cat <<'EOF'\n修改 \`x.py\`\nEOF\n)"` |

**三種安全做法速查**：

| 方法 | 指令形式 | 適用情境 |
|------|---------|---------|
| Heredoc with quoted delimiter（推薦） | `cmd "$(cat <<'EOF'\n...\nEOF\n)"` | 長文字、含特殊字元、commit 訊息（長文字傳遞見規則五） |
| 單引號包整參數 | `cmd '...含 backtick...'` | 參數內無單引號 |
| 改用 Edit 工具 | 直接 `Edit` ticket md 檔 | 長文字寫入 ticket 內容 |

**識別特徵**：若 Bash 執行後看到 `command not found` / `permission denied` / `ModuleNotFoundError` 等錯誤且來源不明，優先檢查是否 backtick 被 command substitution。

---

## 規則五：長文字傳遞預設使用 heredoc

> 來源：PC-087（PM 寫 /tmp 作 ticket 內容中介）+ W15-005 WRAP 方案 E。長文字（append-log 內容、commit msg、ANA 結論）直接用 heredoc 傳 CLI，禁止繞 `/tmp` 寫檔再讀回傳入。

**容量事實（打破心理障礙）**：

| 項目 | 容量 | 對照 |
|------|------|------|
| ARG_MAX（macOS） | ≥ 1 MB | 單一命令列總長度上限 |
| ARG_MAX（Linux） | ≥ 2 MB | 同上 |
| 80 行 markdown 長文字 | 約 3-8 KB | 遠低於 ARG_MAX |
| 典型 append-log Solution | 1-10 KB | 完全可行 |

**識別信號表**：

| 場景 | 錯誤做法 | 正確做法 |
|------|---------|---------|
| append-log 長 Solution | `Write /tmp/sol.md` → `Read` → `--content "$(cat /tmp/sol.md)"` | `ticket ... append-log ... --content "$(cat <<'EOF'\n...\nEOF\n)"` |
| Commit 訊息多段 | `echo > /tmp/msg` → `git commit -F /tmp/msg` | `git commit -m "$(cat <<'EOF'\n...\nEOF\n)"` |
| ANA 結論傳 CLI | 中介 /tmp 檔 | heredoc 直傳 |

**例外**：文字 > 100 KB（極少見）才考慮檔案中介；此時應優先改用 `Edit` 工具直接改 ticket md。

---

## 統一檢查清單

執行 Bash 命令前：

- [ ] 命令含 `cd`？→ 改用子 shell `()` 或 `uv -d`
- [ ] 多步驟序列？→ 第一步加絕對路徑 `cd /project/root &&`
- [ ] 輸出可能很大？→ 提前加 `head` / `tail`
- [ ] `run_in_background: true`？→ 用 `TaskOutput(taskId)`
- [ ] 輸出含「Full output saved to」？→ 用 `Read(file_path)`
- [ ] 串接多個 git 寫入（commit/merge/rebase/push）？→ 拆成獨立呼叫
- [ ] 看到 `index.lock` 錯誤？→ 確認是否有 git 串接
- [ ] CLI 參數含 backtick？→ 改用 heredoc / 單引號 / Edit 工具（規則四）
- [ ] 看到 `command not found` / `ModuleNotFoundError` 來源不明？→ 檢查 backtick command substitution（PC-079）
- [ ] 準備 `Write /tmp/*.md` 作 CLI 中介？→ 改 heredoc 直傳（規則五，容量絕對夠）

---

## 相關文件

- `.claude/references/bash-tool-usage-details.md` — 詳細案例、根因圖解、chpwd 深度說明
- `.claude/references/quality-python.md` — Python 執行規則
- `.claude/error-patterns/implementation/IMP-008-bash-working-directory-pollution.md`、`IMP-009-taskoutput-confusion.md`
- `.claude/error-patterns/process-compliance/PC-079-bash-backtick-command-substitution-in-cli-args.md` — 規則四的完整案例與根因
- `.claude/error-patterns/process-compliance/PC-087-pm-tmp-detour-for-long-text.md` — 規則五的觸發案例
- CLAUDE.md — 專案開發規範

---

**Last Updated**: 2026-04-18 | **Version**: 2.1.0 — 新增規則五 heredoc 長文字傳遞預設（W15-007 / W15-005 WRAP 方案 E） | **Source**: IMP-008、IMP-009、index.lock 競爭、PC-087
