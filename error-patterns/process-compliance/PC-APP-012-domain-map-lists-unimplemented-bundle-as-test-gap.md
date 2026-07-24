---
id: PC-APP-012
title: Domain map 將未實作概念列為已實作 bundle，衍生不可執行的測試 ticket
category: process-compliance
severity: medium
first_seen: "2026-07-23"
occurrences: 1
related_tickets:
  - 0.38.1-W8-002
  - 0.38.1-W6-002
  - 0.38.1-W5-002
---

# PC-APP-012: Domain map 將未實作概念列為已實作 bundle，衍生不可執行的測試 ticket

## 事件

W6-002 分析 domain-map vs 測試對齊度時，saffron 把 synchronization domain-map §3 列出的 `PassthroughMerge` 和 `TagTreeMerge` bundle 當作已實作的程式碼類別，據此建立 W8-002 IMP ticket 要求補寫 unit test。

Agent 執行時 `grep` 找不到目標類別——實際合併邏輯在 `SyncMergeService` 中，未拆為獨立策略類別。Ticket 無法執行，花費 97k tokens 後失敗回報。

## 根因

**domain-map 產出階段**（W5-002）：saffron 從 spec 概念描述反推 bundle 時，把「合併策略分類」概念（PassthroughMerge / TagTreeMerge）列為 §3 bundle，未用 `grep` 驗證對應類別在程式碼中存在。方法論 §3 底線「必須用實際 import 鏈驗證」聚焦依賴方向，未覆蓋「bundle 本身是否已實作」。

**分析消費階段**（W6-002）：直接消費 domain-map §3 的 bundle 清單比對測試目錄，未二次驗證 bundle 對應的程式碼類別存在性。domain-map 被當作 ground truth。

**建票階段**（PM）：從分析報告的 spawn 規劃建票時，未對 `where.files` 的目標類別做存在性確認。

## Why

domain-map §3 bundle 界定表有兩種語意：(a) 已實作的程式碼結構、(b) 規劃中的概念分層。兩者混在同一張表中，下游消費者（測試對齊分析、PM 建票）無法區分，預設全部為 (a)。

## Consequence

產出不可執行的 IMP ticket（W8-002），agent 花 97k tokens 嘗試後失敗。PM 需手動診斷根因、關閉 ticket、追溯錯誤鏈。

## Action

| 時機 | 動作 |
|------|------|
| domain-map 產出 | bundle 界定表每個 bundle 附程式碼路徑，`ls`/`grep` 驗證存在；概念性（未實作）bundle 在分類欄加「(規劃)」前綴 |
| domain-map 消費（測試對齊等） | 消費前 `grep` 驗證 bundle 對應類別存在，不存在者排除出缺口清單 |
| PM 建 IMP ticket | `where.files` 列出的目標檔案/類別 `test -f` 或 `grep` 確認存在 |

## 防護措施

- domain-map 模板 §3 加「實作狀態」欄（已實作/規劃中）——修改模板屬框架層變更，建 ticket 追蹤
- 測試對齊分析 prompt 加前置步驟：「驗證每個 bundle 的目標路徑存在」

## 與其他 pattern 的關係

- `ARCH-BAL-001`（dependency boundary declared without code verification）：同根因——宣告與現況漂移
- `PC-165`（false positive fix chain）：不同層級但同族——PC-165 是測試綠燈遮蔽 runtime 失效，PC-APP-012 是文件層 false positive 衍生不可執行工作
