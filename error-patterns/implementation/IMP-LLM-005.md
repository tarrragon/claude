---
id: IMP-LLM-005
title: 以 glob 組測試檔清單時，zsh 對未命中的 glob 中止整段命令替換，清單變空，測試 runner 收到零個路徑而改跑整個套件
status: active
severity: 中
---

# IMP-LLM-005: 測試檔清單的 glob 未命中 → 清單變空 → runner 跑全套件

## 基本資訊

- **Pattern ID**: IMP-LLM-005
- **分類**: 實作 bug（implementation）
- **來源版本**: 3.2.0
- **發現日期**: 2026-11-11
- **風險等級**: 中
- **影響範圍**: Bash 工具在 zsh 下執行，以 `F=$(ls a*.py b*.py ...)` 或類似命令替換組出測試檔清單，再傳給 pytest／jest／flutter test 等「無路徑引數即跑全部」的 runner

---

## 問題描述

### 症狀

只想跑本票相關的測試檔，命令寫成：

```bash
F=$(cd $W && ls tests/test_handoff*.py tests/test_*dispatch*guard*.py 2>/dev/null | tr '\n' ' ')
python3 run-with-timeout.py 600 -- uv --directory $W run pytest -q ${=F}
```

其中一個 glob（`tests/test_*dispatch*guard*.py`）沒有任何檔案命中。zsh 在 glob 展開階段就報 `no matches found` 並中止 `ls`，`2>/dev/null` 攔不住（錯誤來自 shell 本身，不是 `ls`），`F` 變成空字串。pytest 收到零個路徑，退回 rootdir 收集全部測試，原本數秒的命令跑了兩分鐘仍未結束，被移到背景。

### 根因

1. zsh 預設 `NOMATCH`：未命中的 glob 是錯誤，整條簡單命令不執行；bash 預設則把未命中的 glob 原樣傳下去，`ls` 只對那一項報錯、其餘照列。同一行命令在兩種 shell 下行為不同。
2. 測試 runner 把「沒有路徑引數」解讀為「跑全部」。清單變空的失敗方向不是「少跑」，而是「多跑」，且外觀與正常執行相同，直到耗時異常才察覺。
3. 多跑的後果超出浪費時間：全套件繞過本機測試名額閘門（run-with-timeout 依命令判輕重，看到的是指定測試檔的意圖），與並行 session 的合併閘門搶資源。

與 IMP-GPD-023 同屬「zsh 下把檔案清單存進變數」，失敗方向相反：IMP-GPD-023 是整串被當成一個路徑而少掃（零命中），本 pattern 是清單變空而多跑。

---

## 解決方案

- 執行 runner 前確認清單非空，空就不跑：`[ ${#F} -gt 0 ] && pytest $F`（zsh 陣列）或 `[ -n "$F" ] && ...`。
- 組清單時對每個 glob 加 `(N)` 限定詞（zsh null_glob），未命中的 glob 展開為空而不中止整條命令：`ls tests/test_*guard*.py(N)`。
- 清單先寫入檔案並印出筆數，確認後再以陣列讀回傳給 runner。

已發生的處置：發現後立即以 TaskStop 停止背景任務，`pgrep` 確認無殘留 pytest 程序，改以明確清單（先寫檔、檢查筆數為 15）重跑。

---

## 預防措施

- 任何「無引數即全量」的命令（pytest、jest、`flutter test`、`rm` 搭配清單變數等），引數來自命令替換時，一律先檢查非空。
- 可考慮在 pre-test-hook 偵測「命令含 pytest 且路徑引數來自變數展開」時提示檢查空清單（該 hook 目前只提示「辨識不出測試呼叫」，未說明空清單會跑全套件）。

---

## 關聯

- 發現於 2026-11-11，一張 handoff 孤兒判準修正票的執行期（跑相關測試檔時）
- 相關：IMP-GPD-023（zsh 不拆分變數裡的檔案清單）
