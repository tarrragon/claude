---
id: IMP-BAL-013
title: sort/uniq 在預設 locale 下依 collation 合併相異 CJK 字串，靜默造成統計失準
category: implementation
severity: medium
created: 2026-08-24
---

# IMP-BAL-013: sort/uniq 在預設 locale 下依 collation 合併相異 CJK 字串，靜默造成統計失準

## 基本資訊

| 項目 | 內容 |
|------|------|
| 風險等級 | 中 |
| 首次發現 | 2026-08-24 |
| 來源版本 | v0.2.1 |
| 適用範圍 | 任何以 shell 管線（`sort` / `uniq` / `comm` / `join`，皆依 collation 比較）聚合中文或其他多位元組字串做統計的情境 |
| 偵測成本 | 低（`LC_ALL=C` 重跑同一管線比對輸出，或改用 `grep -cF` 逐一 byte-exact 計數） |

## 摘要

**`sort` 的排序鍵不是位元組序，而是目前 locale 的 collation 規則；`uniq -c` 的「相同」判斷沿用同一份 collation。** 系統預設 locale（如 `LANG=en_US.UTF-8`，`LC_ALL`/`LC_COLLATE` 皆未設）下，collation 對多位元組字元的排序權重與 byte-exact 比對不同，可能把兩個**位元組序列相異**的中文字串排到相鄰且判為相等，`uniq -c` 因而將其合併為一組，並以其中一方的名稱標示合併後的總和。

危害不在於輸出格式異常——三個訊號完全正常：命令無警告、無錯誤碼、總數守恆（分組前後筆數相加相符）。異常唯獨發生在分組本身：兩個不同的字串被算成同一類，且顯示的類別名稱只是被合併的其中一方，看不出另一方存在。不主動用其他方法（逐一比對、改變 locale 重跑）交叉驗證，此類統計錯誤不會被發現。

## 症狀

- 對中文（或其他 CJK／多位元組）字串跑 `sort | uniq -c` 做次數統計，結果類別數少於預期
- 加總各類別次數等於總筆數，數字表面自洽，看不出異常
- 改用 `LC_ALL=C sort | LC_ALL=C uniq -c` 重跑，類別數增加，原本的合併類別拆成兩筆或更多
- 環境變數 `LC_ALL`、`LC_COLLATE` 皆未設，僅有 `LANG=xx_XX.UTF-8`（多數互動式 shell 的預設狀態）

## 根因

| 環節 | 事實 | 後果 |
|------|------|------|
| `sort` 的排序鍵 | 依目前 locale 的 collation 規則排序，非位元組序 | 多位元組字元的排序位置與 byte-exact 排序不同 |
| `uniq -c` 的相等判斷 | 沿用同一份 collation 比較相鄰列 | collation 視為相等的兩個字串會被合併，即使位元組序列不同 |
| 輸出無任何錯誤訊號 | 命令執行成功、無 stderr、退出碼 0 | 使用者沒有「該懷疑」的訊號來源 |
| 總數守恆 | 合併後的計數仍是被合併雙方之和 | 唯一常見的交叉檢查（加總是否等於總筆數）通不過異常偵測 |
| 顯示名稱取自被合併的其中一方 | `uniq -c` 只印出它判定為代表的那一列內容 | 讀者只看到一個名稱，另一個字串完全從輸出中消失，無從得知曾經存在 |

**與一般統計誤用的差別**：一般統計誤用（如樣本偏誤、口徑不一致）通常在追問細節時會露出破綻；此問題連追問也追問不出來——`uniq -c` 印出的那一行，其名稱、計數、格式全部正確無誤，只是底下合併了另一個不存在於輸出中的字串。

## 最小重現

```bash
printf 'hook 可靠性與失敗語意\nhook 測試覆蓋\nhook 可靠性與失敗語意\n' > /tmp/t.txt

sort /tmp/t.txt | uniq -c
#   3 hook 測試覆蓋

LC_ALL=C sort /tmp/t.txt | LC_ALL=C uniq -c
#   2 hook 可靠性與失敗語意
#   1 hook 測試覆蓋
```

驗證環境：`LANG=en_US.UTF-8`，`LC_ALL` 與 `LC_COLLATE` 皆未設（`echo "LANG=$LANG LC_ALL=$LC_ALL LC_COLLATE=$LC_COLLATE"` 可確認）。第一次輸出把兩個不同字串合併為一行，且以「hook 測試覆蓋」（實際只出現 1 次）標示總數 3 次；改用 `LC_ALL=C` 後才拆出正確的「2」與「1」。

## 案例：統計中文 ticket 主題分佈得出 20 倍誤差（2026-08-24）

統計 ticket 主題分佈檔案時，以預設 locale 執行 `sort | uniq -c` 聚合中文主題字串，得出「某主題在存量範圍內有 64 張票」的結論。改用 `grep -cF` 對該主題字串逐一做 byte-exact 計數後，實際筆數為 3 張，相差超過 20 倍。若此數字未被察覺而直接沿用，會作為前提寫入另一張票的交接內容，成為下游執行者未經查證即採信的錯誤起點。

## 防護

| 時機 | 動作 |
|------|------|
| 以 `sort` / `uniq` / `comm` / `join` 聚合中文或多位元組字串統計前 | 在管線各命令前加 `LC_ALL=C`（如 `LC_ALL=C sort file \| LC_ALL=C uniq -c`），強制以位元組序比較，不受目前 locale collation 影響 |
| 已產出的聚合統計結果用於決策或寫入交接文件前 | 對關鍵類別另用 `grep -cF '<精確字串>' <來源檔>` 做 byte-exact 交叉驗證，兩者不一致時以 `grep -cF` 為準 |
| 不確定目前 shell 的 locale 設定 | `echo "LANG=$LANG LC_ALL=$LC_ALL LC_COLLATE=$LC_COLLATE"` 確認；未設 `LC_ALL`/`LC_COLLATE` 即可能受此影響 |
| 撰寫涉及 CJK 字串聚合的腳本或 Hook | 預設即加 `LC_ALL=C`，不依賴呼叫端的 shell locale 環境 |

## 相關

- `.claude/rules/core/bash-tool-usage-rules.md` 規則八（速查條目，路由至本檔與 `references/bash-tool-usage-details.md`）
- `.claude/rules/core/language-constraints.md` 規則 1（本框架強制繁體中文輸出，ticket 主題／error-pattern 分類／worklog 標題皆為中文字串，凡以 shell 管線聚合統計者皆在射程內）
- `.claude/rules/core/tool-output-trust-rules.md` 規則 3（關鍵事實用無法腦補的固定值交叉驗證）——本 pattern 補上「固定值本身可能因比較基準不一致而失真」的情形：`uniq -c` 的計數是整數固定值，但比較基準（collation）錯誤時，固定值本身就是錯的
- `IMP-BAL-009`（grep 位元組比對 vs 編碼不符造成 0 命中被誤讀為語意結論）——同屬「工具比較層級與人類預期不一致，且無錯誤訊號」家族，該例是編碼層級不符，本例是排序／相等判斷的 collation 層級不符
