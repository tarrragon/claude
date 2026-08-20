---
id: TEST-BAL-007
title: 以繞道旗標讓測試變綠後歸因為「環境問題」，掩蓋套件依賴宣告缺漏
severity: high
related: [TEST-BAL-006, TEST-006, PC-165]
---

# TEST-BAL-007: 以繞道旗標讓測試變綠後歸因為「環境問題」，掩蓋套件依賴宣告缺漏

## 基本資訊

| 項目 | 值 |
|------|-----|
| 分類 | test |
| 風險等級 | 高 |
| 首次觀察 | 2026-08-20 |

## 症狀

測試執行遇到 collection 階段的 `ModuleNotFoundError`，執行者加上繞道旗標後套件轉綠，並在報告中把該檔記為「因環境問題略過，與本次變更無關」。

繞道形式包含（不限於）：

| 繞道形式 | 表面效果 |
|---------|---------|
| `pytest --ignore=<失敗檔>` | 該檔排除，其餘全綠 |
| `uv run --with <缺失套件> pytest ...` | 臨時環境補上依賴，全綠 |
| `pytest -k "not <失敗項>"` | 篩掉失敗項，全綠 |
| 改用 subprocess 呼叫取代直接 import | 迴避 import 期依賴，功能可用 |

關鍵特徵：**綠燈數字看起來合理**（如 209 passed / 249 passed），不像 0 collected 那樣刺眼，因此不觸發進一步查證。

## 根因：繞道動作本身是證據，卻被當成前置步驟丟棄

執行者的目標是「讓測試跑起來以驗證本次變更」，繞道是達成該目標的手段。手段成功後，注意力回到本次變更，繞道被歸檔為「與我無關的環境雜訊」。

但繞道之所以必要，正因為該套件的依賴宣告有缺漏。兩者是同一件事的兩面：

- 繞道前的失敗 = 正規路徑下的真實狀態
- 繞道後的綠燈 = 非正規環境下的狀態

歸因為「環境問題」等於宣稱正規環境有錯、非正規環境才對，方向相反。

**放大因子**：不同繞道形式掩蓋的失敗範圍不同，執行者容易低估。`--ignore` 讓人以為只有單檔受影響，實際不加 `--ignore` 時 pytest 回報的是 `Interrupted: N error during collection`——整個套件零收集。單檔略過與全套件中斷，前者可接受、後者不可接受，而繞道抹平了兩者的差別。

## 實證

同一 session 內兩個獨立主體（一位 subagent、一位 PM）對同一缺口產生同型歸因：

| 主體 | 繞道方式 | 得到的數字 | 下的結論 |
|------|---------|-----------|---------|
| subagent | `pytest --ignore=<檔>` | 209 passed | 「因環境缺 yaml 模組於 collection 階段失敗，與本票無關」 |
| PM | `uv run --with pyyaml python -m pytest <dir>` | 249 passed | 「它的環境缺 pyyaml，不是程式碼問題」 |

正規路徑實測（`uv run --directory <pkg> pytest tests/`）結果為 `Interrupted: 1 error during collection`，零測試執行。

兩列並置的證據價值在於：兩個獨立 context、不同繞道形式、各自獨立作業，卻收斂到同一句歸因。這排除了「個別執行者判斷力不足」的解釋——繞道的誘因內建在任務結構中（目標是驗證本次變更，繞道是達成該目標的最短路徑），任何人在該位置都會傾向繞。因此處置方向是為繞道動作加上留痕要求，不是要求執行者更謹慎。

根因為該套件 `pyproject.toml` 宣告 `dependencies = []`、dev group 僅含 pytest 與 pytest-cov，未含 pyyaml；而其測試間接匯入的模組於 import 期 eager-import yaml。同 repo 另一套件的 `pyproject.toml` 於 dependencies 與 dev group 皆宣告 pyyaml，可正常收集——兩者對照即為判準。

## 解決方案

發現需要繞道才能跑測試時，依序執行：

1. **確認該套件的正規測試命令**。依序查：專案測試說明文件、套件目錄的 `README`、`pyproject.toml` 的 `[tool.pytest.ini_options]`。三者皆無記載時，以「在套件目錄下、不帶額外旗標」為預設形式，並將此缺漏本身列為發現項。憑印象組的命令可能本身就是非正規形式。
2. **跑不帶任何繞道旗標的正規命令**，記錄完整輸出。判別失敗範圍是單檔略過（`N errors`，其餘照跑）還是全套件中斷（`Interrupted: ... during collection`）。
3. **檢查本套件測試的 import 鏈是否觸及未宣告的模組**。順著失敗訊息指名的模組往上追，確認其是否出現在該套件的 `dependencies` / `dependency-groups.dev` / PEP 723 header。未出現即為宣告缺漏，不是環境問題。與同 repo 其他套件的宣告對照可作為快速線索，但跨套件差異本身不構成判準——另一套件宣告該模組可能只是它自己需要。

## 預防措施

| 層級 | 措施 |
|------|------|
| 自律 | 報告測試結果時，若命令含 `--ignore` / `-k "not ..."` / `--with <套件>`，必須同時附上不帶該旗標的執行結果 |
| 自律 | 繞道結果僅供繼續當前工作，不作為結論依據——報告須同時載明繞道前的原始失敗與所用繞道形式 |
| 驗收 | 接收方見報告出現「環境問題」「與本次變更無關」等歸因、且命令含繞道旗標時，退回要求不帶旗標的執行輸出，不憑通過數採信 |
| 文件 | 專案測試執行方式須文件化到可直接複製的粒度，避免執行者自組非正規命令 |
| 工具 | CI 或 hook 以正規命令執行全套件，使繞道無法通過閘門 |
| 宣告 | 每個具 tests 目錄的套件，其依賴宣告須涵蓋測試 import 鏈上的全部第三方模組（含間接匯入） |

## 與相鄰模式的區別

| 模式 | 機制 | 差異 |
|------|------|------|
| TEST-BAL-006 | 顯式測試路徑覆蓋多筆 testpaths，收集母體縮小 | 依命令形態判別：帶**測試路徑參數**（如 `pytest tests/sub/`）→ 該模式；帶**繞道旗標**（`--ignore` / `-k "not ..."` / `--with`）→ 本模式（該模式屬命令形式的副作用，本模式的繞道為刻意動作，但意圖不在讀者的證物內，故以命令形態為主判準） |
| TEST-006 | pytest plugin fixture 未宣告，setup 階段 error | 兩者根因同為依賴宣告缺口，可同時成立：該模式診斷宣告缺口本身，本模式處理發現缺口後的繞道與歸因行為（宣告缺口是根因，繞道歸因是其上的行為層） |
| PC-165 | 測試綠燈不等於 runtime 正確 | 該模式的綠燈為真，只是覆蓋不足；本模式的綠燈是在非正規環境取得，正規環境根本沒有綠燈 |

各模式全文位置：

- `.claude/error-patterns/test/TEST-BAL-006-explicit-test-path-overrides-multi-entry-testpaths.md`
- `.claude/error-patterns/test/TEST-006-pytest-plugin-fixture-dependency-undeclared.md`
- `.claude/error-patterns/process-compliance/PC-165-false-positive-fix-chain.md`

本模式是 `.claude/rules/core/quality-baseline.md` 規則 1 邊界「測試綠燈不等於 Runtime 正確」的變體——該邊界處理綠燈為真但覆蓋不足，本模式處理綠燈取自非正規環境而正規環境無綠燈可言。
