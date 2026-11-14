---
id: IMP-BAL-018
title: module 層級常數在 import 當下定型，早於測試隔離 fixture 生效，副作用寫進 production 位置而測試全綠
severity: medium
---

# IMP-BAL-018: module 層級常數在 import 當下定型，早於測試隔離 fixture 生效

## 基本資訊

| 項目 | 值 |
|------|-----|
| 分類 | implementation |
| 來源版本 | 0.2.1 |
| 風險等級 | 中 |
| 首次觀察 | 2026-08-28 |

## 症狀

測試套件全數通過，但執行測試會在 production 位置留下副作用（日誌行、狀態檔寫入、快取項）。測試本身不斷言這些副作用的位置，故無任何紅燈；污染只在有人事後翻閱 production 檔案時才被發現。

前置條件是專案已有測試隔離機制，且該機制以「改寫被測模組的 `__file__` 或等價路徑錨點」實作——這是隔離 hook / CLI 這類以自身檔案位置推導專案根的程式碼時的常見做法。

## 根因

**求值時機早於隔離時機**。把路徑寫成 module 層級常數時：

```python
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent   # import 當下即求值定型
```

Python 在 import 該模組的當下執行 module 層級語句。測試 fixture 改寫 `__file__` 發生在 import 之後，此時常數已經定型為改寫前的值。隔離機制看似生效（`__file__` 確實被改了），實際被繞過（沒有人再讀它）。

寫成函式則求值時機推遲到呼叫時，落在 fixture 生效之後：

```python
def _get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent        # 每次呼叫才求值
```

**測試的斷言範圍不涵蓋副作用位置**。測試斷言的是行為正確性（回傳值、狀態轉換），不是「這次執行寫到哪個檔案」。位置錯誤因此落在斷言的盲區內，套件維持全綠。

## 偵測方式

副作用位置無法由斷言涵蓋時，用外部計數對照：跑測試前後各取一次 production 檔案的命中數，數字增長即為污染。

```bash
grep -c "<測試 fixture 專用的識別字串>" <production 檔案>   # 測試前
# 執行測試
grep -c "<測試 fixture 專用的識別字串>" <production 檔案>   # 測試後，應與前者相同
```

實證（2026-08-28）：一次 hook 的 root 對齊修改，第一版把 root 寫成 module 層級常數，測試 fixture 名（`agent-xyz`）出現在 production 日誌，命中數由 0 增為 2。改為呼叫時求值後命中數不再增長，確認修正生效。該次修改的測試套件在兩個版本下皆為 4536 passed / 0 failed——綠燈對此缺陷完全沒有鑑別力。

## 解決方案

| 情境 | 做法 |
|------|------|
| 路徑錨點（`__file__` 導向的 root、log 目錄、狀態檔位置） | 一律寫成函式，不寫成 module 層級常數 |
| 已存在的 module 層級路徑常數 | 改為函式；呼叫端改為呼叫，不快取回傳值到另一個 module 層級名稱 |
| 確實需要快取（求值成本高） | 快取在函式內以 lazy 方式初始化，並提供測試可重置的入口 |

已寫進 production 位置的污染，若該檔案是 gitignored 的共用熱檔（日誌、快取），可留置不清——行級編輯共用熱檔的風險高於污染本身的成本；於 ticket 或 worklog 記錄即可。若污染進入版控或影響正確性，則必須清除。

## 預防措施

| 層級 | 措施 |
|------|------|
| 撰寫 | 路徑錨點寫成函式是預設做法，寫成常數需在該行註解說明何以不受測試隔離影響 |
| 審查 | 見到 `X = Path(__file__)...` 形式的 module 層級賦值，即檢查該專案的測試隔離機制是否依賴改寫 `__file__` |
| 驗證 | 新增涉及路徑解析的測試時，以 production 檔案的命中數前後對照確認隔離生效，不以套件綠燈為證 |

## 變體：測試端的 fixture scope 早於隔離 fixture

**主張**：production 端寫法正確（路徑在呼叫時求值）時，同樣的時序缺陷仍會從測試端發生。測試以 module 級（或更高 scope）fixture 載入「import 時就有副作用」的模組，例如以 `exec_module` 載入 hook，而載入過程呼叫了日誌初始化。conftest 的隔離若是 function 級 autouse，就來不及攔截，因為 pytest 一律先建立較高 scope 的 fixture。

**Why**：pytest 依 scope 由高到低建立 fixture，與 conftest 和測試檔的宣告位置無關。function 級隔離只保護 function 級之後發生的事；module 級 fixture 內的副作用落在它之前，求值時讀到的是未隔離的環境。

**Consequence**：副作用寫進真實位置，測試照樣全綠。若 fixture 另啟子行程且沒有明確傳入 env，子行程只繼承啟動當下的環境，同樣繞過隔離；在 linked worktree 內執行時，worktree 偵測優先於環境變數，問題更隱蔽。

**Action**：
- 載入有 import 副作用模組的 fixture，scope 若高於 function，該 fixture 自己就要建立隔離。做法是在同一 scope 用 `pytest.MonkeyPatch.context()` 或 module 級 autouse fixture 設定隔離環境變數。
- 呼叫子行程時明確傳入 `env=`。
- 偵測不靠套件綠燈：以前後快照比對真實輸出位置，有新增即判紅。

**實證（2026-11-12）**：測試洩漏哨兵改為前後快照比對後，第一次合併閘門在 ticket 套件判紅，訊息為 `hook-logs/<hook 名>` 被建在真實根。套件內 5157 個測試全數 passed，結束碼由哨兵設為 1。改用 module 級隔離加上子行程明確傳 env 後，該套件整套結束碼為 0。

## 與既有模式的邊界

| 模式 | 差異 |
|------|------|
| `IMP-064` | 該模式是函式體 local re-import **晚於** mock 生效而取到真實符號；本模式是 module 層級常數 **早於** fixture 生效而取到未改寫的值。同屬綁定時機家族，方向相反 |
| `PC-BAL-009` | 該模式的變因是執行 cwd 不同使測試結果翻轉（有紅燈、只是兩方顏色不同）；本模式無紅燈，兩個版本都全綠 |
| `PC-165` | 該模式主張測試綠燈不等於 runtime 正確；本模式是其一個具體實例，機制為求值時機與隔離時機的先後 |

## 觀察來源

2026-08-28 一次 hook 日誌 root 對齊的實作，執行代理人於自我驗證階段抓到並修正，未進入交付版本。
