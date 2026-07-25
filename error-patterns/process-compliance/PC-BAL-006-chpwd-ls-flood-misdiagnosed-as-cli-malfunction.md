---
id: PC-BAL-006
title: 子 shell cd 的 chpwd ls 傾印疊在 CLI 輸出前，被誤診為 CLI 故障而繞道
severity: medium
category: process-compliance
related: [IMP-008, IMP-056, PC-166]
created: 2026-07-25
---

# PC-BAL-006: 子 shell cd 的 chpwd ls 傾印疊在 CLI 輸出前，被誤診為 CLI 故障而繞道

## 症狀

- 以合法子 shell 形式 `(cd <dir> && <cli> ...)` 執行命令時，工具結果開頭出現整頁目錄清單（zsh chpwd hook 的 ls 傾印），真正的 CLI 輸出被推到尾端
- Agent 判讀時把「輸出開頭是一堆檔名」歸因為「CLI 直接執行輸出異常」，改用其他調用方式（如 `uv run --directory`）繞道，並在報告中記載「PATH 上的 CLI 故障」
- 事後以相同命令重現：CLI 實際 exit 0、輸出完全正常——「故障」從未存在，只有雜訊前綴

## 根因

zsh chpwd hook 在每次 cd（含子 shell 內的 cd）觸發 ls。既有規則（bash-tool-usage-rules 規則一）將子 shell 列為裸 cd 的合法替代，理由是「不污染持久 cwd」——但子 shell 內的 cd 仍觸發 chpwd，ls 輸出照樣混入該次工具結果。「合法」只解決 cwd 持久化，不解決輸出雜訊。

Agent 缺「輸出前綴雜訊 ≠ 命令故障」的判讀錨點：診斷依據是輸出形態（開頭是否乾淨）而非固定值（exit code、關鍵輸出行是否存在），一眼看到雜訊即判故障，屬 tool-output-trust 規則 3 的反面——未用固定值交叉驗證就下結論。

## 解決方案

- 判讀層：看到輸出開頭為目錄清單時，先找 ls 段之後的實際輸出與 exit code；`echo "exit: $?"` 或 `| tail -N` 錨定關鍵行再判斷
- 繞道前先驗證：宣告「工具 X 故障」前，同命令重跑一次並檢查固定值（exit code / 預期輸出行 grep），兩次一致才成立（tool-output-trust 規則 3）
- 命令層降噪：對非 git 命令優先考慮免 cd 的等價形式（CLI 支援 `--directory` / 絕對路徑參數時直接用），子 shell cd 留作最後手段

## 預防措施

- 派發 prompt 涉及子 shell cd 時，附一句判讀提示：「輸出開頭的目錄清單是 shell hook 雜訊，以 exit code 與尾端輸出為準」
- 報告中出現「工具直接執行異常，已改用 Y 繞道」時，PM 驗收應重現一次原命令確認異常真實存在，再決定是否記錄工具缺陷——本模式即 PM 重現後發現「故障」不存在的實證

## 關聯

- IMP-008 / IMP-056：裸 cd 的 chpwd 污染與 ls 淹沒（本模式是其子 shell 變體：cwd 不污染但輸出仍淹沒）
- PC-166：confabulation 觸發鏈——輸出邊界模糊是誤判起點；本模式為「誤判方向相反」案例（把真實正常輸出判為故障，而非把虛構輸出判為真實）
- 實證：book_overview_app 0.38.1-W10-002（2026-07-25），`doc query SPEC-014` 被誤診為 shim 故障，PM 重現確認 exit 0 輸出正常
