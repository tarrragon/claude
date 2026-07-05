---
id: IMP-V1-006
title: 大小寫不敏感檔案系統上 Edit 工具寫入成功，但 git pathspec 以不同大小寫尋址失敗
category: implementation
severity: low
created: 2026-07-05
source_ticket: 1.5.0-W5-011.1
---

# IMP-V1-006: 大小寫不敏感檔案系統上 Edit 成功但 git pathspec 失敗

## 症狀

`git add <path>` 或 `git commit -- <path>` 回報 `error: pathspec '<path>' did not match any file(s) known to git`，但同一字面路徑的 Read / Edit / Write 全部成功，且檔案內容確實已被修改（`git status` 也列出該檔為 modified，只是大小寫不同）。

## 根因

兩層對「同一路徑」的判定標準不一致：

1. **檔案系統層**：macOS APFS 預設大小寫不敏感（case-insensitive, case-preserving）——以 `SKILL.md` 開啟實際名為 `skill.md` 的檔案會成功，工具層（Read/Edit/Write）完全無感。
2. **git 層**：pathspec 與 index 中記錄的實際檔名做大小寫敏感匹配——`SKILL.md` 對 index 內的 `skill.md` 不命中，直接報 pathspec 錯誤。

觸發條件通常是命名慣例混雜：目錄下多數檔案採一種大小寫慣例（如 skill 檔慣例 `SKILL.md`），個別歷史檔案實際為另一種（`skill.md`），操作者以慣例推斷檔名而未驗證。

## 偵測

pathspec 錯誤當下，以固定值命令確認實際大小寫（tool-output-trust 規則 3）：

```bash
git ls-files <目錄>   # index 中的權威檔名
ls <目錄>             # 檔案系統中的實際大小寫（case-preserving 會顯示原始命名）
```

## 解決方案

以 `git ls-files` 回報的實際檔名重下 git 命令。工具層先前的編輯不需重做（內容已正確落盤）。

## 防護措施

1. **git pathspec 以 `git ls-files` 實際檔名為準**：對 `.md` 等慣例命名檔案下 git 命令前，若曾以「慣例大小寫」而非「實測檔名」引用路徑，先 `git ls-files` 驗證。
2. **「Edit 成功」不保證 git 可以同字面路徑尋址**：大小寫不敏感檔案系統上兩者判定標準不同，工具層成功不可作為 git 層路徑正確的證據。
3. **命名慣例統一**：發現慣例外大小寫的歷史檔名時，依規則 5 建 ticket 追蹤重命名（`git mv` 需兩段式處理大小寫變更），不在當下任務內順手改。

## 關聯

- `.claude/rules/core/tool-output-trust-rules.md` 規則 3 — 固定值交叉驗證（本 pattern 的偵測手段）
- `.claude/rules/core/bash-tool-usage-rules.md` — Bash 命令前置檢查
