---
id: PC-GPD-077
title: 改 skill 內容時沒有同步升版號，發佈前才發現本地與發佈庫版號相同而內容不同
category: process-compliance
severity: low
status: active
created: 2026-11-03
related: []
---

# PC-GPD-077：skill 內容改了，版號沒動

## 基本資訊

| 項目 | 內容 |
|------|------|
| Pattern ID | PC-GPD-077 |
| 分類 | process-compliance（框架資產的版本紀錄） |
| 風險等級 | 低（發佈前會被狀態報告攔下，不會錯誤發佈） |
| 來源版本 | 0.6.0 |
| 首次觀測 | 2026-11-03 |

## 摘要

**改 skill 的 SKILL.md、references 或程式時，如果不在同一張票裡升版號、寫 CHANGELOG，版號就會一直停在上次發佈的值。** 等到要推送時，狀態報告會把它列為「本地較新」，但本地和發佈庫的版號相同，必須先補升版才能推，否則會用舊版號發佈新內容。

## 症狀

- skill-sync 狀態報告的 SHOULD PUSH 清單裡，有 skill 寫著 `local(X) vs remote(X)`，兩個版號相同。
- 首例同時有 4 個 skill 處於這個狀態，變更分散在多張票，包括新增 CLI 子命令、hook 檢查、schema 邊與規則文字。

## 根因

- 修改 skill 的票是功能票或修正票，驗收條件只看功能本身，沒有「版號與 CHANGELOG 同步」這一條。
- 同一個 skill 會被好幾張票接連修改，每張票都覺得「下一張再升」，最後沒有任何一張升。
- 升版要等到發佈時才有人需要，平時沒有工具檢查。

## 防護

| 情境 | 做法 |
|------|------|
| 一張票會改到 `.claude/skills/<name>/` 下的內容 | 在同一張票升該 skill 的版號（SKILL.md frontmatter）並寫 CHANGELOG，驗收條件列出這一條 |
| 同一個 skill 被多張並行的票修改 | 每張票各自升 patch；合併時版號衝突就讓號，與 SPEC 的做法相同 |
| 發佈前盤點 | 先跑 skill-sync 狀態報告，`local(X) vs remote(X)` 版號相同的項目先補升版，再推送；不要用 `--force` 跳過 |

## 檢查問句

commit 改到某個 skill 的檔案之前問：這次改動有沒有升這個 skill 的版號、寫 CHANGELOG？
