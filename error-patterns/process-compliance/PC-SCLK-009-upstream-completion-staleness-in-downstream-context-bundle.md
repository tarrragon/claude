---
id: PC-SCLK-009
title: 上游 ticket 完成使下游 Context Bundle 失效，派發前未重新校準
category: process-compliance
severity: medium
status: active
created: 2026-08-05
related:
- PC-040
- PC-162
- PC-100
---

# PC-SCLK-009: 上游 ticket 完成使下游 Context Bundle 失效，派發前未重新校準

## 基本資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-SCLK-009 |
| 類別 | process-compliance |
| 風險等級 | 中 |
| 發現時間 | 2026-08-05 |
| 來源版本 | 1.4.0 |
| 相關 ticket | SCLK 專案同批次的四張票：上游的欄位解析 helper 票、下游的 JSON 鍵常數化票、上游的定位器拆分票、下游的定位器引用票 |

## 問題描述

PM 依 PC-040 於派發前把 context 寫入 ticket 的 Context Bundle。該內容是撰寫當下的程式碼快照——行號、識別符名稱、出現次數、結構描述。

當同一批次中的上游 ticket 先完成並改動了下游 ticket 所依據的程式碼，下游的 Context Bundle 隨即失效，但沒有任何機制標示它已過期。

**過期的 Context Bundle 比沒有 Context Bundle 更危險**：PC-040 的設計目的正是讓執行者信任它、不必重新探索，執行者因此會照著失效內容動手，而不是去看程式碼現況。

## 觸發案例

2026-08-05，SCLK 專案的一個版本，同一 session 內兩次獨立命中，機制相同。

### 案例 A：問題描述被推翻（數量與性質皆變）

| 時序 | 事件 |
|------|------|
| 建票時 | 下游的 JSON 鍵常數化票記「cursorLocator 三個 JSON 鍵在 fromJson 與 toJson 各以裸字面出現一次共六處」 |
| 上游執行 | 上游的欄位解析 helper 票完成，引入 `_resolveField(欄位名, raw, parsed, fallback)`，12 個純量欄位改走此 helper |
| 失效後果 | 每欄位的鍵字面由 2 處變 3 處（參數 1 日誌欄位名 / 參數 2 `json[key]` / 參數 3 解析器再取一次），加 toJson 實測約 49 處 |

不只數量變化，問題性質也變了：參數 1 與參數 2/3 必須指涉同一欄位但簽名不強制同源，新增了「日誌欄位名與 JSON 鍵脫鉤」的風險，且該風險的後果（觀測性設施報錯欄位名）比原描述的「鍵打錯字靜默落回預設」更難察覺。

### 案例 B：識別符被重命名

| 時序 | 事件 |
|------|------|
| 派發前 | PM 為下游的定位器引用票寫 Context Bundle，表格列出 `AppCursorLocator.defaultEnabled` 等 4 處引用 |
| 上游執行 | 上游的定位器拆分票完成，`AppCursorLocator` 拆為 `AppCursorLocatorChannel` / `AppCursorLocatorHotkey` / `AppCursorLocatorSettings` 三類 |
| 失效後果 | Context Bundle 內 4 處識別符指向已不存在的類別，正確名稱為 `AppCursorLocatorSettings.defaultEnabled` |

兩次都在 PM 準備派發下游時人工發現，無任何自動機制攔截。

## 根因

1. **Context Bundle 是快照不是引用**。它複製程式碼的當下狀態，但與被引用的程式碼之間沒有連結，程式碼變動時快照不會跟著動，也不會標示自己已過期。
2. **失效來源是已知且有序的**。這是與 PC-162 問題 A 的關鍵差異——此處的上游 ticket 是 PM 自己剛派發、剛驗收、剛 merge 的，資訊完全在手，不是遺忘的歷史變動。資訊不缺，缺的是把資訊接到下游的動作。
3. **生命週期缺 checkpoint**。ticket 流程在「上游 complete」與「下游派發」之間沒有任何步驟要求檢視下游的 Context Bundle。規則層與 hook 層皆無覆蓋，完全依賴 PM 記憶。

## 與既有 pattern 的邊界

| pattern | 失效來源 | 時序 | 防護方向 |
|---------|---------|------|---------|
| PC-162 問題 A | 建票時基於舊記憶或舊文件，環境早已變動 | 環境先變 → ticket 後建 | 建票時驗證環境現況 |
| **本 pattern** | 建票時正確，被自己剛執行的上游 ticket 作廢 | ticket 先建（正確）→ 上游執行 → 失效 | 上游 complete 後校準下游 |

兩者根因與防護時機皆不同，故獨立記錄而非併入 PC-162。

## 解決方案

上游 ticket complete 並 merge 後、派發任何 `blockedBy` 該票的下游 ticket 前，執行校準：

1. 取得下游清單（`blockedBy` 指向剛完成的票）
2. 對每張下游 ticket，grep 其 Context Bundle 中的識別符、行號、數量描述
3. 對照上游 Solution 記錄的新舊對應（若上游依規範記錄，可直接引用不需重新推導）
4. 有落差則以 `append-log` 補正

補正時**新增章節明確標示取代關係**，例如「### 前置更新：<上游 ticket ID> 已完成，本節取代上方表格的類別名」，而非原地改寫——保留漂移軌跡，讓執行者知道哪些內容曾經是什麼、為何改變。

## 預防措施

| 層級 | 措施 |
|------|------|
| 工具層 | ticket CLI 於 `complete` 時掃描 `blockedBy` 指向本票的下游 ticket，若其 body 含本票 `where.files` 的檔案路徑或本票 Solution 提及的識別符，輸出提示（不阻擋） |
| 規範層 | 上游 ticket 的 Solution 應明列重命名或搬移的新舊對應。案例 B 的上游定位器拆分票有做，使下游校準從「重新查證」降為「照表替換」 |
| 撰寫層 | Context Bundle 引用識別符時標註出處與查證時間，讓讀者能判斷新鮮度 |

## 關聯

- **PC-040**（context 寫入 ticket 而非 prompt）：本 pattern 是該實踐的副作用。PC-040 越落實、Context Bundle 越詳盡，過期時的誤導性越強
- **PC-162**（ticket 描述含過時環境狀態）：機制不同，見上方邊界表
- **PC-100**（派發前 context 準備）：同屬派發前準備家族
- framework issue `tarrragon/claude#55`（ticket CLI 契約缺口叢集）：工具層預防措施的落點
