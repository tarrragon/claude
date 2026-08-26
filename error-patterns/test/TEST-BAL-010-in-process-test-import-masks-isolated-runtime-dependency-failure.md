---
id: TEST-BAL-010
title: 測試以 in-process import 載入模組，遮蔽隔離執行環境的依賴缺失
category: test
severity: high
status: active
created: 2026-08-26
related:
- PC-165
- TEST-BAL-007
- TEST-SCLK-001
---

# TEST-BAL-010: 測試以 in-process import 載入模組，遮蔽隔離執行環境的依賴缺失

被測模組在**測試環境**與**生產環境**跑在兩套不同的依賴宇宙，而測試只覆蓋前者。測試用 `importlib` 在 pytest 進程內載入模組，繼承了測試框架自身的依賴集合；生產則以隔離執行器（`uv run`、獨立 venv、容器、serverless runtime）啟動，只有該環境宣告的依賴可用。當模組新增一個 top-level import 指向測試環境有、生產環境沒有的套件時，測試全綠而生產靜默失效。

**Why**：測試的職責是驗證模組在**它實際被執行的環境**下正確。以 in-process import 載入，測試驗證的是「模組在 pytest 的依賴集合下可運作」——那不是生產環境的問題。兩套環境的依賴集合是不同的集合，覆蓋其一不蘊含覆蓋其二，而測試報告不呈現這個區別。

放大此缺陷的第二層機制是**偽造式的降級測試**。這類模組通常已有「依賴缺失時降級」的測試，做法是 monkeypatch `builtins.__import__` 強制拋 `ImportError`。該測試驗證的是**例外處理機制本身寫得對不對**，不是**真實隔離環境下 import 會不會成功**。兩者從未被同一條測試路徑覆蓋，於是「有降級測試」給出虛假的安全感。

**Consequence**：

| 層級 | 影響 |
|------|------|
| Runtime | 依賴缺失走進 fail-open 分支，功能永久失效且無錯誤訊號（fail-open 的設計目的正是不阻斷主流程） |
| 偵測 | 失效無紅燈、無告警、無日誌差異。發現途徑通常是無關的人恰好在無關的任務中讀到那段程式碼 |
| 存活期 | 因無訊號，失效可存活至下一次有人手動觸發並注意輸出為止，跨版本不受限 |
| 信任 | 「該模組有降級測試」成為誤導性證據，使審查者跳過該處 |

**Action**：

| 情境 | 做法 |
|------|------|
| 模組宣告零依賴（PEP 723 `dependencies = []`）或依賴集合小於測試環境 | 至少一條測試以**生產啟動方式**執行（`subprocess` 呼叫 `uv run <script>`），斷言真實輸出，不用 in-process import |
| 既有降級測試以 monkeypatch 偽造 `ImportError` | 保留（它驗例外處理），但**不得作為「隔離環境下可運作」的證據**；測試名稱與 docstring 需明示其驗證範圍 |
| 模組新增 top-level import | 檢查該套件是否在生產執行環境的依賴宣告內；不在則改 function-local（lazy）import |
| 判斷是否命中本模式 | 問「這個模組在生產是怎麼被啟動的」與「測試是怎麼載入它的」。兩者不同即命中，與程式碼品質無關 |

**識別訊號**：測試檔用 `importlib.util.spec_from_file_location` / `sys.path.insert` 載入被測模組；被測模組有自己的依賴宣告區塊（PEP 723 header、獨立 `pyproject.toml`、容器映像）；該宣告的依賴集合小於測試環境。

**邊界**：本模式針對**執行環境差異**造成的覆蓋落差，與 PC-165（斷言不覆蓋 runtime 路徑）不同——PC-165 的測試跑在對的環境但斷言問得不對，本模式的斷言問得對但跑在錯的環境。兩者可同時存在。

**實證來源**：doc skill 的 `uc_registry.py` 新增 top-level `import yaml` 與 `FileLocator`，使兩個 PEP 723 零依賴 hook（`uc-reference-validation-hook.py`、`uc-fingerprint-drift-check-hook.py`，皆宣告 `dependencies = []`）在生產的 `uv run --quiet` 隔離 venv 下載入失敗，靜默走 fail-open——UC 引用驗證會永久失效。該 hook 的既有測試以 in-process import 載入並繼承 pytest 環境的 pyyaml，全綠；其「fail-open」測試以 monkeypatch 偽造 `ImportError`，驗的是例外處理而非真實 import 結果。缺陷由實作者在同一次改動中自行察覺並改為 lazy import，非測試攔截。
