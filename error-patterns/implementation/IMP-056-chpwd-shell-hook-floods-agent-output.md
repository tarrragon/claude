---
id: IMP-056
title: chpwd Shell Hook 大量 ls 輸出淹沒代理人工具結果
category: implementation
severity: medium
first_seen: 2026-04-11
---

# IMP-056: chpwd Shell Hook 大量 ls 輸出淹沒代理人工具結果

## 症狀

代理人派發到 worktree 後，回報完成但 worktree 無任何變更或 commit。代理人看似正常執行但實際上未完成任何修改。

## 根因

用戶的 zsh 配置中有 `chpwd` hook（切換目錄時自動執行 `ls`）。當代理人使用 `cd` 切換到 worktree 目錄時：

1. `chpwd` hook 自動執行 `ls`，輸出整個目錄的檔案列表（80+ 行）
2. 大量噪音輸出佔用代理人的 tool call 結果空間
3. 代理人的實際 git/test 命令結果被噪音淹沒
4. 代理人無法正確判斷命令執行結果，導致後續操作偏離

## 觸發條件

- 代理人使用 Bash 工具執行包含 `cd` 的命令
- 用戶 shell 配置了 `chpwd`、`precmd` 或類似的目錄切換 hook
- worktree 目錄或主專案目錄檔案數量多

## 防護措施

### 派發代理人時（PM 職責）

1. **明確告知代理人不要使用 `cd`**
2. **指導使用替代方案**：
   - 讀取/編輯/建立檔案：使用 Read/Edit/Write 工具搭配**絕對路徑**
   - 執行命令：使用子 shell `(cd /path && command)` — 子 shell 的 cd 不觸發 chpwd
   - uv 指令：使用 `uv -d /path run ...`

### Prompt 模板

在派發 prompt 中加入：

```
Shell 環境警告：此 shell 的 chpwd hook 會在 cd 時自動輸出 ls。
絕對不要使用裸 cd 命令。改用：
- Read/Edit/Write 工具搭配絕對路徑
- 子 shell: (cd /path && command)
```

### 主線程 PM 自身同樣適用（受眾擴展）

本 pattern 防護易被讀成「PM 提醒 subagent 不要 cd」，但**主線程 PM 自己裸 cd 同樣觸發 chpwd 淹沒**——PM 不在「安全位置提醒別人」，而是同等暴露。

**chpwd 淹沒發生後的正確反應**：停手重發乾淨命令（`git -C`／子 shell），**不是**把淹沒的輸出當「正常但吵」接受、更不是用預期填補續寫。後者是 confabulation 觸發鏈（輸出淹沒 → result 邊界模糊 → 同訊息腦補），見 PC-166 + `tool-output-trust-rules` 規則 1/4。

## 正確做法

```bash
# 錯誤：裸 cd 會觸發 chpwd
cd /path/to/worktree && git status

# 正確：子 shell 隔離
(cd /path/to/worktree && git status)

# 更佳（git 專用）：用 -C 完全不換目錄、不觸發 chpwd
git -C /path/to/worktree status
```

## 變體：chpwd 輸出被捕獲進 redirect 致下游處理拿到假資料（W1-018 near-miss）

**症狀**：`(cd "$DIR" && cmd | sort) > file.txt` 後，`file.txt` 開頭混入該目錄的 `ls` 列表（chpwd 在 cd 當下印出），使檔案**非完全排序**；後續 `comm -23 file.txt other.txt` 因 comm 要求輸入嚴格排序而產生大量假差異。

**根因**：即使用子 shell `()` 隔離工作目錄，chpwd hook 仍在子 shell 內的 cd 當下執行 `ls`，其 stdout 與後續命令的 stdout 一起被 `>` 重導向**捕獲進檔案**。子 shell 只隔離 cwd 變更，不抑制 chpwd 的副作用輸出。

**Consequence（為何嚴重）**：這不是「輸出變吵」而是「資料被靜默污染」。W1-018 實證：孤兒比對 `comm` 得到假的 2610 筆（實為 751），PM 差點據此向用戶誤報「sync-push --clean 會災難性刪除 2610 檔」。被污染的中介檔讓錯誤結論看似有憑據。

**Action（防護）**：

| 情境 | 錯誤 | 正確 |
|------|------|------|
| 需在某目錄跑 git 並捕獲輸出 | `(cd "$D" && git ls-files \| sort) > f` | `git -C "$D" ls-files \| sort > f`（不 cd，不觸發 chpwd） |
| 必須 cd 且要捕獲 | 直接 `>` 捕獲 | 先確認輸出無 chpwd 污染（`head` 檢視），或在子 shell 內 `unfunction chpwd` |
| 用 comm 前 | 假設「sort 過就排序正確」 | 確認排序檔無前置雜訊；用 `sort -c f` 驗證已排序 |

**識別信號**：comm/diff 結果數量遠超預期（near-100% 差異）、排序檔開頭出現不屬於命令輸出的目錄列表 → 優先懷疑 chpwd 污染。

## 相關

- IMP-008: Bash 工作目錄污染（cd 持久化問題）
- .claude/rules/core/bash-tool-usage-rules.md 規則一

---

**Last Updated**: 2026-06-10 — 禁用詞修正：變體標題與本 footer 共 2 處用詞改為「假資料」+ 自稱「本 PC」→「本 pattern」（IMP 類非 PC 類）（W1-032 文件交叉引用稽核）。

**Last Updated**: 2026-06-07 — 新增「變體：chpwd 輸出被捕獲進 redirect 致 comm 假資料」（W1-018 near-miss：假 2610 孤兒差點誤報災難性刪除，實為 751）+ `git -C` 正確做法。
