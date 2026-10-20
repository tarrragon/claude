---
id: IMP-GPD-008
title: 守衛以正則或子字串比對 git 命令，git 與子命令之間的全域選項使比對落空
severity: 高
status: active
---

# IMP-GPD-008: 守衛以正則或子字串比對 git 命令，git 與子命令之間的全域選項使比對落空

## 基本資訊

- **Pattern ID**: IMP-GPD-008
- **分類**: 實作（implementation）
- **風險等級**: 高（守衛對框架自己規定的首選寫法恆不生效，失效方向為放行，且與「命令本來就不需檢查」同形）
- **來源版本**: 0.5.0
- **相關 Pattern**:
  - 解析 git branch 給人看的輸出取分支名的同類模式：該模式解析的是 git 的輸出，本模式解析的是 git 命令本身
  - 建議指令未經自家 parser 驗證的同類模式
  - 兩者皆為本地分域編號，尚未推上共用通道，依 `.claude/references/reference-stability-rules.md` 規則 8 以描述代替編號

---

## 問題描述

### 症狀

- hook 以 `"git push" in cmd` 或 `re.search(r"git\s+worktree\s+remove", cmd)` 判斷命令是否為目標操作
- `git -C <repo> push`、`git -c k=v merge`、`git -C <repo> worktree remove <path>` 在 `git` 與子命令之間多了全域選項，比對不命中
- 不命中的結果依守衛寫法而異：
  - 子字串判斷「是否需要檢查」：直接判為不需檢查，靜默通過
  - 正則擷取參數（如 remove 的路徑）：擷取到 0 個參數，落入「無法解析，放行」分支
- 反方向同時存在：子字串比對會把引號、echo、`--why "..."`、heredoc 內出現的字樣當成真的命令，誤觸發

### 根因

shell 命令的結構是「程式 + 全域選項 + 子命令 + 參數」，且可被語句分隔、包裹（`bash -c`、`eval`）、引號包住。正則與子字串只看字面序列，把「`git` 後緊接子命令」當成唯一形態。

框架規則要求 git 操作首選 `git -C <path>`（避免裸 cd 觸發 chpwd，見 `.claude/rules/core/bash-tool-usage-rules.md` 規則一），使得守衛最常遇到的正好是它不認得的形態。

### 缺陷為何長期未被發現

- 守衛失效的方向是放行，放行與「命令本來就不在檢查範圍」在輸出與結果上同形
- 測試多以無全域選項的命令字面當輸入（`git push origin main`），正向對照未涵蓋規範寫法
- 日誌只記「不需要檢查」或「無法解析，放行」，沒有人逐行讀這類 DEBUG／INFO 行

---

## 解決方案

改用共用的命令解析器辨識 git 呼叫，不在各守衛各寫一份正則：

- tokenize 後逐語句處理，跳過前綴包裹與環境變數賦值，遞迴進入 `bash -c`／`eval`
- 消耗全域選項（`-C`、`-c`、`--git-dir` 等）後才比對子命令，並展開 git 別名
- 剝離 heredoc 內文；引號內字樣不視為命令
- 解析失敗時回傳明確的「無法解析」值，由守衛決定 fail-open 或 fail-closed，並記日誌
- 汰換既有正則時，舊正則保留為「無法解析」時的退路：嚴格解析器對管線接 shell（`… | sh`）等結構回傳「無法解析」，舊正則對這類字面仍會命中。若直接 fail-open，覆蓋範圍會比汰換前倒退，而且倒退方向是放行。退路擷取到的對象照常送檢查，正則也沒命中時才 fail-open

本框架的實作在 `.claude/lib/git_command_parse.py`（`find_git_invocations`）。

---

## 預防措施

1. **寫守衛前先找共用解析器**：命令辨識屬共用邏輯，兩個以上守衛各自實作即違反單一定義（`.claude/skills/cognitive-load-assessment/references/file-split-by-contention.md`〈Python 程式碼〉節表格「共用邏輯進 lib」列）
2. **正向對照用規範寫法**：測試輸入至少含 `git -C <path> <子命令>`、`git -c <key>=<value> <子命令>`、`git --git-dir=<path> <子命令>` 三種全域選項形態，以及 `bash -c '<git 命令>'` 包裹形態；只用最短字面的測試對規範寫法無鑑別力（`.claude/rules/core/test-assertion-design-rules.md` E2）
3. **反向對照用引號與 echo**：同一字樣出現在引號、echo、heredoc 內時不應觸發
4. **讀「放行」類日誌**：守衛上線後，抽查日誌中「不需要檢查」「無法解析，放行」的行，確認它們對應的命令確實不在檢查範圍
5. **修一處時盤點同類**：`grep -rn -e '"git ' -e 'git\\s+' .claude/hooks .claude/skills/*/hooks` 找出同類比對點；`"git ` 涵蓋所有以字面 `"git <子命令>"` 做子字串比對的寫法（如 `"git push" in cmd`、`"git worktree remove" in cmd`），`git\\s+` 涵蓋正則寫法
