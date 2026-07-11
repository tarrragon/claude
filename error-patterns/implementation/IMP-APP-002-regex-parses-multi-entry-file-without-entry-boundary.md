---
id: IMP-APP-002
title: regex 解析多條目結構化檔案未以條目邊界為先（跨條目誤配 + 格式漂移靜默失效）
category: implementation
severity: high
created: 2026-07-08
related:
 - 0.38.0-W1-001
 - 0.38.0-W1-002
 - IMP-021
---

# IMP-APP-002: regex 解析多條目結構化檔案未以條目邊界為先

## 症狀

同一根因族的兩種表現（2026-07-08 同日在兩張票各自實證）：

1. **跨條目誤配**（0.38.0-W1-001）：`activate_next_planned_version` 用單一橫跨全檔的 lazy DOTALL regex 從 todolist 找「version 條目 + status」。當第一個條目狀態不符時，regex 跳過該條目自身欄位、匹配到檔案中「下一個」符合的狀態值並寫入，但訊息標籤仍印最早條目的版本號——寫入位置與標籤不一致，造成 1.0.0 被誤推進 active。
2. **格式漂移靜默失效**（0.38.0-W1-002）：`parse_proposals` 的 `PROPOSAL_ID_PATTERN` 只認 `  PROP-001:` 鍵值格式，但 `docs/proposals-tracking.yaml` 實際是 `- id: PROP-016` 清單項格式。解析對真實檔案恆回傳空字典，依賴它的漂移 6 偵測自建立以來從未生效——且因「空結果 = 無警告」語意合法，無任何失效訊號。

## 根因

以 regex 解析多條目結構化檔案（YAML / markdown 清單）時的兩個結構性弱點：

- **條目邊界缺失**：pattern 直接匹配「欄位 A ... 欄位 B」而未先切出單一條目範圍，DOTALL/lazy 量詞使匹配自由跨越條目邊界，取到 A 條目的鍵配 B 條目的值。
- **格式假設無驗證**：pattern 寫成當下對檔案格式的想像，檔案格式演進（或一開始就不符）後解析靜默回空，消費端把「空」當「無問題」，防護機制變成永不觸發的死代碼。

## 解決方案

1. **先定位條目邊界、再在邊界內找欄位**：兩段式解析——第一段切條目區塊（如 `_scan_todolist_planned_candidates` 以條目起始 pattern + 下一條目/區塊起始為界），第二段只在單一區塊內匹配欄位。W1-002 的 `SECTION_BOUNDARY_PATTERN` 同理（防最後一個條目吞噬後續區塊）。
2. **解析結果空集合時的自證檢查**：對「理應非空」的來源（檔案存在且非空但解析出 0 條目），輸出 WARNING 而非靜默回空，讓格式漂移第一時間可見。
3. **用真實 repo 資料做端到端驗證**：fixture 測試全綠不代表 pattern 符合真實檔案格式（W1-002 漂移 6 的 fixture 恰好用了 pattern 想像中的格式）；上線前至少跑一次真實資料。

## 預防措施

- 寫「regex 解析多條目檔案」的程式碼時，檢查是否兩段式（條目邊界 → 欄位）；單一跨檔 DOTALL pattern 即為警訊。
- 結構化檔案優先用標準 parser（yaml.safe_load）；選擇 regex 時在註解記錄「為何不用 parser」與所假設的格式樣本。
- 消費「解析結果」的防護/偵測邏輯，測試須含「真實檔案格式」案例，不能只用自造 fixture。

## 與 IMP-021 的邊界

IMP-021（手動文字解析結構化格式）的主張是「優先用標準 parser」；本模式處理其未覆蓋的兩個維度：(1) 不得不用 regex 時的**條目邊界紀律**（兩段式：先切條目、再匹配欄位），(2) **解析恆空的靜默失效偵測**（格式漂移使防護變死代碼且無訊號）。先讀 IMP-021 判斷可否改用標準 parser；確定用 regex 才適用本模式。

## 關聯 Ticket

- 0.38.0-W1-001（跨條目誤配修復：a491f23c）
- 0.38.0-W1-002（格式漂移修復：0c4d006e）
- 0.38.0-W1-007（同日第三起：`_sync_tracking_yaml` 假設 dict 結構、真實檔案為 list，`doc update confirmed` 從未真正同步 tracking.yaml——非 regex 但同屬「格式假設無真實資料驗證」維度，適用解決方案 2、3）
- 0.38.0-W1-009（同日第四起：寫入欄位名 `confirmed` 與真實 schema `confirmed_at` 不符，sync 產生從未被讀取的欄位、真欄位不同步——欄位命名維度，W1-007 依預防措施 3 用真實資料驗證才揪出，證明該措施有效）
- 0.38.0-W1-011（同日第五起：sync 寫入真實 schema 不存在的頂層 `last_updated` 鍵——同一 `_sync_tracking_yaml` 函式連續三起（結構/欄位名/頂層鍵），單點函式的格式假設應一次全面對照真實 schema 盤點，而非逐次修補）
- 0.38.0-W3-010（第六起，維度擴展至 spec 文件層：spec §14.2 指定 tag_management_page 為 Divider 遷移試點頁，但 grep 實證該頁無任何 Divider（7 處實分佈於 library/search/version_management/sync）——「格式假設無真實資料驗證」不限程式碼 pattern，spec 撰寫時引用的程式碼現況同樣需 grep 實證，否則下游 ticket acceptance 直接繼承不可執行條件；W3-001 驗收時攔截）
