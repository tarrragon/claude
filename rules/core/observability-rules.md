# 可觀測性規則

本文件定義所有程式碼的可觀測性最低要求。詳細規則和語言專屬實作見 references。

> **核心理念**：異常不可靜默消失，關鍵流程必須有跡可循。

---

## 規則 1：catch 區塊必須有日誌

每個 catch 區塊必須滿足以下至少一項，否則需附註說明原因：

| catch 行為 | 要求 |
|-----------|------|
| catch 後 return 預設值 | 必須記錄 warning 日誌（含錯誤訊息和元件名稱） |
| catch 後 rethrow | 加日誌或直接移除 try-catch（禁止無意義 catch-rethrow） |
| catch 後拋出自訂 Exception | 必須記錄原始錯誤再拋出 |
| 空 catch `catch (_) {}` | 禁止，必須加日誌或在註解中說明靜默原因 |

**日誌內容最低要求**：錯誤訊息 + 發生位置（元件/函式名稱）。

> 延伸自 quality-baseline.md 規則 4（異常可觀測性）。

---

## 規則 2：統一日誌工具

使用專案統一的日誌工具，禁止散落的原生輸出。

| 要求 | 說明 |
|------|------|
| 統一入口 | 所有日誌透過專案指定的日誌工具輸出 |
| 禁止散落輸出 | 禁止直接使用 `debugPrint`、`print`、`console.log` 等原生方法 |
| 分級輸出 | 依嚴重程度使用 error / warning / info / debug 級別 |

> 本專案使用 `dart:developer` 的 `developer.log`，搭配 `name: _tag` 標籤分級（level 900 = error）。

---

## 規則 3：全域錯誤處理完整性

應用程式必須建立完整的全域錯誤攔截，防止未處理異常導致無聲崩潰。

| 層級 | 覆蓋範圍 |
|------|---------|
| 框架層 | 框架內部錯誤（如 Flutter 的 Widget 建置錯誤） |
| 平台層 | 平台級未處理異常 |
| 非同步層 | 非同步操作中的未處理異常 |

**驗證方式**：確認三層皆已設定，缺少任一層即為不完整。

---

## 規則 4：關鍵流程三階段日誌

長時間運行的元件和關鍵業務流程，必須在以下階段產出日誌：

| 階段 | 說明 |
|------|------|
| 啟動 | 初始化完成、版本、配置摘要 |
| 錯誤 | 異常發生、錯誤恢復、降級處理 |
| 關閉 | 優雅停機、資源釋放 |

連線型元件額外要求：連線建立和斷開事件必須有日誌。

> 完整生命週期階段定義（含心跳、Debug Log 規範）見 `.claude/references/observability-rules.md`。

---

## 規則 5：平台互動程式碼必須自帶日誌

**寫平台互動程式碼時，日誌與功能同步寫入，禁止事後補。** mock 測試環境不走真實平台 API，日誌缺失在測試階段不會被發現，實機才暴露盲區。

**適用範圍**：程式碼直接或間接呼叫平台 API（權限、相機、GPS、藍牙、NFC、檔案系統、生命週期回調）的所有位置。

| 互動類別 | 必須記錄的日誌點 | 日誌級別 |
|---------|----------------|---------|
| 權限檢查 | check 入口 + 結果（granted/denied/restricted/permanentlyDenied） | info |
| 權限請求 | request 入口 + 結果 | info |
| 平台 API 初始化 | controller create/start 入口 + 成功/失敗 | info |
| 平台 API 銷毀 | controller stop/dispose 入口 | debug |
| 生命週期回調 | didChangeAppLifecycleState 中涉及平台資源操作（暫停/恢復相機等） | debug |
| 平台異常 | PlatformException / MissingPluginException 的 code + message | warning |

**日誌內容最低要求**：操作名稱 + 元件標籤 + 結果或錯誤訊息。範例：`developer.log('Camera permission status: $status', name: _tag);`

**與規則 4 邊界**：規則 4 覆蓋「長時間運行元件的生命週期」；規則 5 覆蓋「平台 API 互動的每個決策點」。兩者可重疊（如相機 controller 同時是長時間元件也是平台 API），重疊時兩條規則皆適用。

> 完整條款（含 Phase 3b 驗收檢查清單、實證事件鏈、日誌範本）見 `.claude/references/observability-rules.md` 第 6 節。

---

## 檢查清單

- [ ] catch 區塊有日誌或有靜默原因註解？
- [ ] 日誌使用專案統一工具（非原生 print）？
- [ ] 全域錯誤處理三層皆已設定？
- [ ] 關鍵流程有啟動/錯誤/關閉日誌？
- [ ] 平台互動程式碼自帶日誌（權限 check/request、平台 API init/dispose、生命週期回調）？

---

## 相關文件

- .claude/references/observability-rules.md - 詳細可觀測性規則（生命週期、心跳、Debug Log、平台互動）
- CLAUDE.md §6 技術選型 - 專案日誌工具為 `dart:developer developer.log`
- .claude/rules/core/quality-baseline.md - 規則 4：異常可觀測性
- .claude/rules/core/quality-common.md - 通用品質基線

---

**Last Updated**: 2026-07-13
**Version**: 1.1.0 - 新增規則 5「平台互動程式碼必須自帶日誌」（0.38.1-W1-037，W1-030/033/035 三輪盲飛教訓）
