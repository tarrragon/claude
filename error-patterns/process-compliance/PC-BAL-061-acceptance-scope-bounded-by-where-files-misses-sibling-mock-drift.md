---
id: PC-BAL-061
title: 驗收只跑 where.files 對應測試，同函式的其他測試檔在環境假失敗遮蔽下漏檢
status: active
severity: high
---

# PC-BAL-061: 驗收只跑 where.files 對應測試，同函式的其他測試檔在環境假失敗遮蔽下漏檢

## 基本資訊

- **類別**: process-compliance
- **風險等級**: high
- **發現日期**: 2026-09-03
- **來源版本**: 0.2.1
- **關聯案例**: 2026-09-02 至 03 的 ticket CLI worktree 修復波——「complete 自動提交 cwd 錨定」票引入回歸，「sibling worktree 序號掃描」票的執行者發現，另建修復票處理；遮蔽因子為同波次「worktree 內測試隔離分支繞過 mock」造成的 43 個環境假失敗

## 症狀

- 一張修改共用函式呼叫簽名的 IMP 票，代理人與 PM 驗收時只跑 `where.files` 列出的測試檔，全數綠燈後合併。
- 合併後 main 上另一個測試檔（未列入 where.files，但以 fake 函式 mock 同一個被呼叫端）以 `TypeError: unexpected keyword argument` 整檔紅燈。
- 紅燈由下一張票的執行者在跑全套件時首次發現，而非由引入者或 PM 驗收發現。
- 案例：cwd 錨定票為 `commit_files_isolated` 呼叫新增 `cwd` 關鍵字引數，驗收跑 `test_git_ops.py` 與 `test_complete_auto_commit.py` 共 28 通過；`tests/test_complete_auto_stage.py` 的 `fake_commit_files_isolated(paths, message)` 未同步，8 個測試失敗進入 main。

## 根因

三個因子共振，缺一不會漏檢：

1. **驗收範圍以 where.files 為界**：where.files 是「寫入意圖」宣告，不是「受影響測試」宣告。修改呼叫簽名的影響面是「所有 mock 或呼叫該函式的測試」，這個集合只能由 grep 被呼叫端名稱取得，不能由 where.files 推得。PC-BAL-040 處理的是 where.files 漏列承載檔；本模式是即使 where.files 正確，它也不承載「回歸測試範圍」這個語意。
2. **全套件被環境假失敗遮蔽**：當時 worktree 內全套件固定 43 個失敗（測試隔離分支在 linked worktree 內繞過 mock），派發 note 明確指示「回歸判定只跑 where.files 對應測試」。這是把全套件紅燈失去診斷價值的後果直接轉嫁到驗收範圍上，等於預先放棄了唯一能發現跨檔回歸的手段。
3. **mock 簽名是靜態契約卻無靜態檢查**：fake 函式以位置參數定義，被呼叫端新增關鍵字引數後，型別檢查與 lint 都不會警告，只有執行到才爆。

## 解決方案

- 修復票：fake 簽名補 `cwd=None` 並斷言其值；grep 全 skill 其餘 mock 位置逐一核對。
- 驗收層：PM 覆核重跑時，對「修改函式簽名 / 呼叫參數」類的票，以 `grep -rln "<被呼叫端名稱>" tests/ ticket_system/tests/` 取得受影響測試檔集合，全數執行，不以 where.files 為界。

## 預防措施

| 層級 | 動作 |
|------|------|
| 派發 note / 骨架 | 修改共用函式簽名或呼叫參數的票，acceptance 加一條「grep 被呼叫端名稱取得的所有測試檔全數通過」，不以 where.files 為界 |
| 全套件被遮蔽時 | 先修遮蔽因子再派會改共用函式的票；若順序不可調，驗收改以「修前修後失敗集合差集為空」判定，而非「只跑目標檔」 |
| 覆核重跑 | PM 覆核時對 diff 中每個被修改的函式呼叫，grep 其名稱在測試目錄的命中檔並全跑；命中檔數寫進驗收記錄 |
| 結構層 | fake / stub 函式改用 `*args, **kwargs` 轉發或以 `unittest.mock.create_autospec` 綁定真實簽名，讓簽名漂移在定義處而非執行處暴露 |

## 判別與邊界

- 與 PC-BAL-040 的分工：040 是 where.files 宣告不足（承載檔漏列）；061 是 where.files 即使正確，也不能當作回歸測試範圍。兩者可同時命中。
- 與 quality-baseline 規則 1 邊界「測試綠燈不等於 Runtime 正確」（PC-165）的分工：165 是綠燈遮蔽 runtime 失效；061 是綠燈的取樣範圍本身不足，紅燈根本沒被觀測到。
- 不適用：where.files 已涵蓋全部 mock 位置、或全套件可用且已執行的情況。

## 關聯 Ticket

見本專案 2026-09-03 的 ticket CLI worktree 修復波工作日誌（引入票、發現票、修復票三者的 ID 記錄於 `docs/work-logs/`，本檔依 reference-stability 規則 8 不引用專案層級 ID）。
