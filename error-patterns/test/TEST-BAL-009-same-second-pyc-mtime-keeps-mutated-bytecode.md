---
id: TEST-BAL-009
title: mutation testing 的改回落在同一秒內，pyc 秒級 mtime 判準使還原後仍載入變異位元碼
severity: medium
related: [TEST-BAL-008]
---

# TEST-BAL-009: mutation testing 的改回落在同一秒內，pyc 秒級 mtime 判準使還原後仍載入變異位元碼

## 基本資訊

| 項目 | 值 |
|------|-----|
| 分類 | test |
| 風險等級 | 中 |
| 首次觀察 | 2026-08-20 |

## 症狀

為驗證新測試是否具鑑別力而做 mutation：改動一個常數或條件、跑測試確認轉紅、改回原值。
改回後重跑，測試**仍然紅**，且失敗項與 mutation 期間完全相同。

檢查原始碼，該處文字確實已是原值。於是懷疑實作有其他 bug，開始往錯誤方向查。

關鍵特徵：**檔案內容與程式行為矛盾**——`grep` 顯示常數為 3，執行期讀到 0。

## 根因：pyc 失效判準是秒級整數，整個 mutation 循環在同一秒內完成

CPython 預設以 source 檔的 mtime 判定 `__pycache__` 內的 `.pyc` 是否過期，比對的是
**秒級整數**（`.pyc` 標頭只存 4 bytes 的 source mtime）。

mutation 循環的三步——改值、跑測試、改回——在小型測試套件下可能全部落在同一秒內：

| 時點 | 事件 | mtime |
|------|------|-------|
| T+0.00 | 改為變異值 | 1787212775.35 |
| T+0.00 | 首次 import，寫入 pyc（記錄 source mtime 1787212775） | — |
| T+0.18 | 測試跑完（轉紅，符合預期） | — |
| T+0.24 | 改回原值 | 1787212775.59 |
| T+0.30 | 重新 import：取整後 mtime 仍是 1787212775，判定快取有效 | — |

於是載入的是變異版位元碼。原始碼已還原，行為卻沒有。

**失效方向具誤導性**：它看起來像「我的修正沒生效」或「實作另有 bug」，而不像快取問題——
因為 mutation 前測試是綠的，改回後應該回到綠，紅燈自然被歸因為程式碼。

## 鑑別方式

原始碼文字與執行期取值矛盾時，先確認載入來源而非邏輯：

```python
from mymodule import mything
print(mything.SOME_CONSTANT)      # 執行期實際值
print(mything.__file__)           # 載入的檔案路徑
import pathlib
p = pathlib.Path(mything.__file__)
print(p.stat().st_mtime)          # source mtime
print([(x.name, x.stat().st_mtime)
       for x in (p.parent / "__pycache__").glob(f"{p.stem}*.pyc")])
```

source mtime 與 pyc 記錄值的**整數部分相同**即命中本模式。

## 解決方案

清除快取後重跑：

```bash
find <專案根> -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
```

## 預防措施

| 時機 | 動作 |
|------|------|
| 執行 mutation testing | 還原步驟後一併清除 `__pycache__`，不依賴 mtime 判準 |
| 撰寫 mutation 腳本 | 改回原值後對檔案執行一次 `touch`（或寫入時附加當前時間戳），使 mtime 明確前進一秒以上 |
| 遇到「原始碼與行為矛盾」 | 先查 `__file__` 與 pyc mtime，再查邏輯——查邏輯的成本遠高且方向錯誤 |
| CI 環境 | 設 `PYTHONDONTWRITEBYTECODE=1` 使快取不生成，代價是每次載入重新編譯 |

**不建議**以「mutation 之間插入 sleep」規避：它讓每次驗證多付一秒，且掩蓋了問題本身——
還原後清快取是無條件正確的做法，不需依賴時序假設。

## 關聯 Ticket

- `0.2.1-W3-831`（首次觀察）：主題推導抽出為獨立模組後，以 mutation（門檻常數 3 改 0）
  驗證新增的 29 項單元測試是否具鑑別力。還原後 2 項測試仍紅，一度誤判為搬移改變了行為，
  實為本模式。清除 `__pycache__` 後 29 項全綠，且真實資料探針輸出與抽出前逐字相同。
