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

## 變體：改 hook 輸出字面，同一支 hook 的測試跨套件分散

**症狀**：修改 hook 的提示或建議字面後，代理人與 PM 只跑 skill 目錄下的同名測試，結果全綠。另一個套件（如 `.claude/hooks/tests/`）裡有一份同名的測試檔，同樣測這支 hook，仍斷言舊字面，要到合併閘門跑全套件時才轉紅。兩份測試的函式名沒有交集，但覆蓋同一行為，因此改完後一份斷言新字面、另一份斷言舊字面，彼此矛盾。

**根因**：「相關測試」憑目錄或檔名挑選。檔名完全相同，讓人誤以為那份測試已經改過了。

**做法**：以被測 hook 的檔名在所有套件的測試目錄取集合，例如 `grep -rl <hook 檔名> .claude/hooks/tests .claude/skills/*/tests`，全數執行，並把命中檔數寫進驗收記錄。hook 檔名含連字號，測試只能以路徑載入，所以檔名必定出現在測試檔內，這個 grep 可以取到全集。已知盲區是經 dispatcher 或 registry 間接執行的整合測試，這類測試不會寫出檔名，仍由合併閘門的全套件兜底。被測對象是一般 Python 模組、且模組名是常見字（如 `lease` 會命中 `please`）時，裸名 grep 會混入大量無關檔，改以 import 語句形式取集合，例如 `grep -rlE "lib\.lease|import lease|from \.?lease"`。

## 變體：改動 import，全域的架構守衛測試不在相關測試內

**症狀**：代理人新增或改動 import 後，只跑被改畫面的測試，結果全綠。專案另有一支全域的架構守衛測試，掃描整個原始碼目錄，檢查分層的 import 方向（例如畫面之間不得互相 import、應用層不得 import 畫面層）。這支測試要到合併閘門跑全套件時才轉紅。

**根因**：守衛測試不以檔名或目錄對應任何一個被改的檔案，它的輸入是整個原始碼樹。因此以「被改檔案的同名或同目錄測試」挑選相關測試時，守衛必定落在範圍之外。上一個變體的 grep 取集合法在這裡也取不到，因為守衛測試裡不會出現被改檔案的名稱。

**做法**：改動 import 或新增檔案時，本機驗收要加跑專案全部的 import 方向守衛，不靠相關性挑選。守衛不一定集中在一個架構目錄，也可能分散在各層自己的測試目錄，甚至寫在一般測試檔的某個 group 裡。所以要依內容取得全集：在測試目錄 grep import 樣式的比對（例如 import 字串的正規表示式、禁止清單函式），不要只跑一個目錄。派發 prompt 要列出這份清單，因為代理人無法從 where.files 推得。修正放錯層的 import 前，先找專案既有的跨層慣例（例如把跨畫面共用的目標狀態下沉到應用層），比照該慣例修正。選定新落點前，要讀目標層自己的反向守衛（該層不得 import 什麼），而不只讀上層的分層規則：程式碼搬進較低的層後，可能因為仍需讀取上層的型別而違反該層守衛，這時要把職責拆開，各自放到守衛允許的層。

## 判別與邊界

- 與 PC-BAL-040 的分工：040 是 where.files 宣告不足（承載檔漏列）；061 是 where.files 即使正確，也不能當作回歸測試範圍。兩者可同時命中。
- 與 quality-baseline 規則 1 邊界「測試綠燈不等於 Runtime 正確」（PC-165）的分工：165 是綠燈遮蔽 runtime 失效；061 是綠燈的取樣範圍本身不足，紅燈根本沒被觀測到。
- 不適用：where.files 已涵蓋全部 mock 位置、或全套件可用且已執行的情況。

## 關聯 Ticket

見本專案 2026-09-03 的 ticket CLI worktree 修復波工作日誌（引入票、發現票、修復票三者的 ID 記錄於 `docs/work-logs/`，本檔依 reference-stability 規則 8 不引用專案層級 ID）。
