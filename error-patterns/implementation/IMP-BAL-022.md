---
id: IMP-BAL-022
title: 全樹格式化不是 lint 中性的：formatter 拆行會讓原本合法的單行寫法觸發新 lint，只看 analyze 總數時看不出退步
severity: low
status: active
category: implementation
tags: [formatter, lint, baseline, dart-format, curly-braces]
---

# IMP-BAL-022: 全樹格式化不是 lint 中性的：formatter 拆行會讓原本合法的單行寫法觸發新 lint，只看 analyze 總數時看不出退步

## 基本資訊

| 欄位 | 值 |
|------|-----|
| 類別 | implementation |
| 風險等級 | low |
| 來源版本 | 0.3.1 |
| 發現情境 | 對 lib 與 test 全樹執行 `dart format`（page_width 80）建立格式基線（2026-11-06）。代理人回報 analyze 有 37 個 info，沒有和格式化前比對；PM 對 main 與分支分別跑 analyze 並比對 diff，才發現其中 2 個是格式化新帶出來的 |

## 症狀

- 只做格式化、沒有任何語意改動，`flutter analyze` 的 issue 數卻增加。
- 新增的 issue 全是 `curly_braces_in_flow_control_structures`，位置都在原本寫成單行、沒有大括號的 `if (cond) continue;`。
- 執行者只回報 analyze 總數（例如「37 個 info，0 error」）時，讀者會把它當成既有的 lint 債，不會察覺其中有新增項目。

## 根因

| 層 | 行為 | 單獨看 | 疊加後 |
|----|------|--------|--------|
| lint 規則 | `curly_braces_in_flow_control_structures` 放過「整個 if 寫在同一行」的無大括號寫法，只在主體換行時報錯 | 允許簡短的 guard clause | lint 結果取決於排版，不只取決於語法結構 |
| formatter | 行長超過 page_width 時，把 `if (cond) stmt;` 拆成條件一行、主體一行 | 純排版、不改 AST | 把原本合法的單行寫法變成違規的兩行寫法 |
| 驗收方式 | 格式化票的驗證只要求「跑 analyze」，沒有附格式化前的基準數 | 已有 lint 債時，總數本來就不是 0 | 新增的 2 個混在既有的 35 個裡，總數 37 看起來像既有狀態 |

行尾註解會讓這個情況更容易發生：`if (x) continue; // 長註解` 原本靠註解撐長整行，格式化時會被拆開。

## 解決方案

1. 格式化之後，對格式化前與格式化後的 analyze 結果做 diff。先把行號正規化掉再排序比對（`sed -E 's/:[0-9]+:[0-9]+ / /' | LC_ALL=C sort`），只看新增的項目，不看總數。
2. 新增的項目另開一個 commit，把被拆開的 if 補成區塊形式 `if (cond) { stmt; }`，讓 analyze 回到格式化前的數量。格式化 commit 維持只有 formatter 產生的 diff，方便審查。
3. 補完之後再跑一次 formatter，確認沒有額外的 diff（區塊形式是 formatter 的穩定點）。

## 預防措施

- 派發格式化（或任何「預期輸出不變」的機械性改動）時，派發前先量好基準（analyze issue 清單），寫進 ticket，並要求執行者回報差值，而不是總數。這和 PC-GPD-043 同型：預期輸出不變的驗收條件，必須先備妥基準。
- 不要把 formatter 當成 lint 中性的工具。lint 規則只要對排版敏感（是否換行、是否同一行），全樹格式化就可能改變 lint 結果。
- 已知對排版敏感的 Dart lint：`curly_braces_in_flow_control_structures`。遇到其他規則時補進本條。

## 關聯

- 案例：consumer 專案的全樹 dart format 基線票，補修 commit 把 analyze 從 37 降回 35。
- 同型流程模式：PC-GPD-043（預期輸出不變的驗收派進 worktree，派發前未備妥基準）。
- 後續防護方向：在合併閘門加入 format 檢查，防止格式基線回退（consumer 專案已建 IMP 票追蹤）。
