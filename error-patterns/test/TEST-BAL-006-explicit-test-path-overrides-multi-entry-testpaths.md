---
id: TEST-BAL-006
title: 顯式指定測試路徑覆蓋多筆 testpaths，收集母體縮小而輸出仍是 passed
severity: high
related: [PC-135, TEST-BAL-001, PC-BAL-048]
---

# TEST-BAL-006: 顯式指定測試路徑覆蓋多筆 testpaths，收集母體縮小而輸出仍是 passed

## 基本資訊

| 項目 | 值 |
|------|-----|
| 分類 | test |
| 風險等級 | 高 |
| 首次觀察 | 2026-08-20 |

## 症狀

執行者回報測試全數通過，通過數卻與既有基線相差甚遠（本案為 1192 對 3363，缺 2171）。兩次執行的差異只在命令列是否顯式帶入測試目錄路徑：

```bash
# 專案設定的完整母體
uv run --directory <pkg> pytest -q          # 3365 passed

# 顯式指定其中一個測試目錄
uv --project <pkg> run pytest <pkg>/tests/ -q   # 1192 passed
```

兩者皆 exit 0、皆顯示 passed、皆無任何警告指出母體不同。

## 根因

**pytest 的 `testpaths` 只在命令列未給出路徑參數時生效**。專案設定多個入口時：

```toml
[tool.pytest.ini_options]
testpaths = ["tests", "ticket_system/tests"]
```

命令列一旦帶入任一路徑，該設定整條被忽略，只收集所指定的路徑。本案 `tests/` 與 `ticket_system/tests/` 兩者的測試數約為 2:1，指定後者即靜默丟棄前者的全部測試。

**縮小後的母體仍是合法的測試執行**，沒有任何機制會指出「你少跑了一半」。pytest 不知道使用者的意圖是全跑還是選跑，故不警告。

**通過數是唯一的訊號，而它不會自己顯眼**。1192 與 3363 都是四位數以內的數字，不對照基線就看不出問題；而執行者若是首次接觸該套件，根本沒有基線可對照。

## 判別

| 觀察 | 判別 |
|------|------|
| 通過數與基線差距大於新增測試數 | 高度可疑，先查收集母體再查測試本身 |
| 兩種執行方式的 exit code 都是 0 | 不構成排除依據——縮小的母體同樣會全過 |
| 命令列含測試目錄路徑或檔名 | `testpaths` 已被覆蓋，母體由該路徑決定 |

確認方式為比對收集數，不需實際執行：

```bash
pytest --collect-only -q | tail -1        # 完整母體
pytest <path>/ --collect-only -q | tail -1   # 指定路徑後的母體
```

## 解決方案

**執行側**：跑完整套件時不帶任何路徑參數，讓 `testpaths` 生效。需要只跑局部時，明示這是局部執行並註明未涵蓋範圍，不以該次結果宣稱全套件通過。

**回報側**：測試結果須附通過數與其對照基線（「3365 passed，基線 3363，新增 2 與本次新增測試數吻合」）。只寫「全數通過」不足以讓驗收方判斷母體是否完整。

**驗收側**：接收測試回報時比對通過數與基線的差值。差值不等於本次新增的測試數即停手查證——多出來或少掉的都要有解釋。

## 預防措施

**基線在票面留存**。ticket 的 Test Results 記錄通過數時一併寫入當時基線，使下一張票的驗收方有對照點，不需自行考古。

**`testpaths` 多筆時於 pyproject 加註**。設定處以註解說明「命令列帶路徑會覆蓋本設定」，讓修改者在該處即看到後果。此為 opinionated-default 的最小形式——無法改變 pytest 行為，至少讓資訊出現在會被讀到的位置。

**不以 exit code 作為母體完整性的證據**。exit 0 只保證跑到的測試全過，不保證跑到了該跑的測試。此判準與 `PC-BAL-048`「量測宇宙與結論宇宙必須一致」同源：篩選了什麼，結論就只能宣稱什麼。

**工具層：conftest 外掛在執行當下提示**。上述三項都是文字預防，依賴執行者讀到並記得；同日兩次再現證明文字預防不足（見下）。預防改由工具承擔：外掛 `.claude/hooks/testpaths_coverage_warning.py` 在 pytest 執行當下偵測「命令列帶路徑而 `testpaths` 有多筆」並輸出警告；警告與 pytest 輸出同屏出現，執行者必然看到，不再依賴事前閱讀。派發範本的〈全套件回報規格〉（`.claude/references/agent-dispatch-template.md`）與外掛互補：外掛負責當場警告，範本負責讓事後回報可用全量數對帳。

**同日兩次再現**（去識別化敘述）：

| 案例 | 執行方式 | 結果 |
|------|---------|------|
| (a) hooks 包 | 驗收時傳入包內某個測試路徑，未走無路徑指令 | 收進 archived 的失敗測試被一併跑到，同時漏掉 lib 的測試，兩個方向的母體誤差並存 |
| (b) ticket 包 | 只跑 `tests/`，漏掉 `ticket_system/tests` | 後者的回歸未被執行，隨提交進入 main |

**轉折**：本模式已有文字層預防（基線留存、pyproject 註解、exit code 判準）後，同日仍再現兩次。結論是此類預防不能只靠被讀到的文字，須由工具在執行當下介入；事後驗收則改依可對帳的回報規格。

## 相關

- `.claude/error-patterns/process-compliance/PC-135-subagent-pytest-pass-but-hook-subprocess-fail.md` — 同屬「測試通過但涵蓋不成立」家族，該模式的落差在執行環境（pytest 對 hook subprocess），本模式的落差在收集母體
- `.claude/error-patterns/process-compliance/PC-BAL-048-adhoc-script-fallback-branch-output-read-as-result.md` — 預防措施「量測宇宙與結論宇宙必須一致」在測試母體上的實例
- `.claude/error-patterns/test/TEST-BAL-001-idealized-fixture-format-masks-validator-false-pass.md` — 同為「綠燈不等於覆蓋」，該模式的失效點在 fixture 內容，本模式在檔案收集
- `.claude/rules/core/quality-baseline.md` 規則 1 — 測試通過率 100% 的邊界：100% 是對「跑到的測試」而言

---

**Last Updated**: 2026-10-02
**Version**: 1.1.0 — 預防措施補工具層（conftest 外掛在執行當下提示）與同日兩次再現（去識別化），記錄文字預防失效、改由工具承擔的轉折。
