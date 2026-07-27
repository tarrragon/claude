---
id: PC-BAL-009
title: 測試 fixture 用相對路徑觸及專案根資產，同一套件在不同 cwd 給出不同顏色，兩方結果不符但皆屬實
severity: high
category: process-compliance
source_ticket: 0.2.1-W3-029
related:
 - PC-165
 - PC-V1-010
 - TEST-BAL-001
created: 2026-07-27
---

# PC-BAL-009: 測試套件的顏色隨執行 cwd 翻轉，使兩方驗收結論互相矛盾且雙方都沒說謊

## 症狀

- 執行方（agent）與驗收方（PM）各自跑同一套測試，得到不同的 pass/fail 分佈，但兩人都能重現自己那一組結果
- 兩組結果的 **pass + fail 總數相同**，只是幾個 case 在一方是綠、另一方是紅
- 驗收方傾向以「我跑的才是準的」為前提，直接判定執行方回報失實，並把該判定寫入 worklog / ticket
- 真正的差異來源是執行 cwd 不同：測試 fixture 以相對路徑觸及專案根資產（`docs/work-logs/...`、`.claude/...`），路徑在專案根解析得到真實 repo，在 `pyproject.toml` 的 canonical `testpaths` 位置解析不到，斷言因此翻轉

## 觸發案例（0.2.1-W3-022 驗收，2026-07-26）

| 執行方 | 執行 cwd | 結果 | 總數 |
|--------|---------|------|------|
| agent | 專案根 | 3182 passed / 1 failed | 3183 |
| PM | `.claude/hooks/`（`pyproject.toml` 的 `testpaths = ["tests"]` 所指 canonical 位置） | 3180 passed / 3 failed | 3183 |

PM 據此一度判定「agent 回報失實」並寫入 worklog；靠 pass+fail 總數相同這一點回頭對帳才更正——總數相同代表兩邊蒐集到的是同一批 case，差異只可能來自執行環境，不可能來自回報造假。相關 fixture 已於 0.2.1-W3-027 改為 cwd 無關（`conftest.py` 的 `hook_project_env`，以 `Path(__file__).resolve().parents[n]` 推導而非依賴 cwd）。

## 根因

**Why**：測試的斷言結果被允許依賴一個「不在測試宣告內」的隱性輸入——執行時的 cwd。fixture 寫相對路徑時，路徑語意由執行位置決定，而執行位置沒有任何一方視為需要對齊的契約：agent 習慣在專案根跑（其他工具都在那裡跑），PM 依 `pyproject.toml` 在 canonical 位置跑，兩者都自認在跑「同一套測試」。

**Consequence**：

| 層級 | 影響 |
|------|------|
| 驗收 | 驗收結論不可傳遞——A 的綠燈在 B 手上是紅燈，acceptance 失去仲裁能力 |
| 信任 | 差異被誤歸因為「回報失實」，對正確完成工作的一方發出錯誤指控，且該誤判會被寫入 worklog 成為後續票的既定事實 |
| 診斷 | 真正的缺陷（本例另有兩個真實紅燈）被「誰在說謊」的爭議掩蓋，修復被延後 |

## 鑑別手段：先做算術對帳，再談歸因

收到「兩方測試結果不符」時，比對 pass、fail、skip 與其總數，可機械區分三種成因，不需人工逐案審視：

| 觀察 | 成因 | 下一步 |
|------|------|--------|
| 總數相同、分佈不同 | 執行環境差異（cwd / 環境變數 / 平台），**非回報問題** | 兩方互報執行 cwd 與指令，在對方位置重跑一次 |
| 總數不同 | 蒐集範圍差異（`testpaths` / `-k` 篩選 / 目錄層級不同） | 對齊指令與工作目錄後重跑，不比較舊數字 |
| 總數相同、分佈相同，但與回報數字不符 | 回報失實或回報的是過期的一次執行 | 要求附上原始輸出，此時才進入歸因討論 |

**Action**：在完成算術對帳之前，禁止寫出「對方回報失實」這類歸因結論，也禁止把該歸因寫入 worklog 或 ticket。

## 防護（回報方與驗收方兩側）

### 回報方（執行測試的一方）

1. 回報測試結果時必附**執行 cwd 與完整指令**，格式如 `cwd=.claude/hooks, uv run pytest tests/ → 3180 passed / 3 failed`。只給數字的回報視為不完整，驗收方可要求補齊而不進入歸因。
2. 若執行位置不是專案設定檔（`pyproject.toml` / `dart_test.yaml`）指定的 canonical 位置，回報中明示「非 canonical 位置」，並在該位置補跑一次。

### 驗收方（PM）

3. 跑測試前先讀專案設定檔確認 canonical 執行位置（`grep -n "testpaths\|rootdir" .claude/hooks/pyproject.toml`），在該位置執行，並在驗收紀錄寫下自己的 cwd。
4. 結果與回報不符時，依上節對帳表判定成因；總數相同即歸類為環境差異，直接進入「兩方互報 cwd」流程，不寫歸因結論。

### 程式碼層（根治）

5. 測試 fixture 一律以 `Path(__file__).resolve().parents[n]` 或 conftest 共用 fixture 推導路徑，禁止相對路徑觸及專案根資產；需要專案根結構的測試改用 tmp_path 建假專案根（實作參考 `.claude/hooks/tests/conftest.py` 的 `hook_project_env`）。
6. 新增此類測試時，驗收條件加一條「在專案根與 canonical 位置各跑一次，結果一致」，把 cwd 無關性變成被斷言的性質而非默契。

## 與 PC-165 的邊界

| | PC-165 | 本模式 |
|---|--------|--------|
| 測試顏色 | 穩定綠燈 | 隨執行環境在綠與紅之間翻轉 |
| 落差所在 | 測試斷言與 runtime 行為之間（綠燈遮蔽真實失效） | 同一套測試的兩次執行之間（顏色本身不唯一） |
| 錯誤結論 | 「已修好」（實際未生效） | 「對方回報失實」（實際雙方都屬實） |
| 對策 | acceptance 補 runtime 層級驗證 | 對齊執行位置 + 算術對帳 + fixture 路徑 cwd 無關化 |

兩者可疊加：cwd 翻轉使某些 case 在 canonical 位置永遠不執行到真實路徑，即退化為 PC-165 的遮蔽情形。判別順序為先確認顏色是否穩定（本模式），再確認綠燈是否覆蓋 runtime（PC-165）。

## 關聯

- PC-165：測試綠燈不等於 runtime 正確（顏色穩定但無效；本模式為顏色不穩定）
- PC-V1-010：subagent 在完成摘要混淆 total 與 passed（本模式的對帳手段依賴 total 被正確回報）
- TEST-BAL-001：理想化 fixture 使 validator 假通過（同屬 fixture 與真實環境落差，該案為恆真、本案為隨環境翻轉）
- 實證：flutter_balance 0.2.1-W3-022 驗收（2026-07-26），fixture cwd 無關化修復於 0.2.1-W3-027
