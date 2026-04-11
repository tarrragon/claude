---
id: IMP-056
title: chpwd Shell Hook 大量 ls 輸出淹沒代理人工具結果
category: implementation
severity: medium
first_seen: 2026-04-11
ticket: 0.17.4-W1-001
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

## 正確做法

```bash
# 錯誤：裸 cd 會觸發 chpwd
cd /path/to/worktree && git status

# 正確：子 shell 隔離
(cd /path/to/worktree && git status)
```

## 相關

- IMP-008: Bash 工作目錄污染（cd 持久化問題）
- .claude/rules/core/bash-tool-usage-rules.md 規則一

---

**Last Updated**: 2026-04-11
