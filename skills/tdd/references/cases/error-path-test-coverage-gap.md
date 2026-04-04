# 異常路徑測試覆蓋缺口：180 個錯誤碼中 49% 生產路徑未測

> 來源：0.17.0-W4-013 回報（ErrorCodes.js 全域分析）
> 對應 Phase：Phase 2（測試設計）
> 對應 Decision Question：Q_new4（異常路徑覆蓋率）

---

## 問題概述

專案定義了 180 個錯誤碼（ErrorCodes），其中 49 個被 src/ 程式碼實際使用。但只有 25 個有對應的異常路徑測試，覆蓋率僅 51%。更嚴重的是，部分覆蓋率數字是虛假的 -- tests/ 引用 ErrorCodes 常數做比對，但並未真正觸發異常路徑。

---

## 覆蓋率分析

| 指標 | 數值 |
|------|------|
| 定義的錯誤碼總數 | 180 |
| 被 src/ 實際使用 | 49 |
| 有對應異常路徑測試 | 25 |
| 生產路徑覆蓋率 | 51%（25/49） |
| 未覆蓋的危險缺口 | 24 |

### 虛假覆蓋率的成因

測試檔案中 `import { ErrorCodes } from '...'` 並用於 `expect(result.code).toBe(ErrorCodes.SOME_ERROR)` -- 這看似覆蓋了錯誤碼，但實際上：

- 測試只驗證「回傳值包含正確的錯誤碼」
- 未驗證「觸發條件是否正確」
- 未驗證「錯誤訊息是否有用」
- 未驗證「錯誤恢復路徑是否正常」

---

## 最危險的 5 個缺口

### 1. OperationResult.fromJSON 的 PARSE_ERROR

null、空陣列、純字串輸入時應回傳 PARSE_ERROR，但三種輸入型別均無測試。

### 2. EventBus 初始化失敗

EVENTBUS_ERROR 和 EVENTBUS_REQUIRED 零覆蓋。EventBus 是事件驅動架構的核心，初始化失敗會導致所有模組間通訊靜默中斷。

### 3. BookValidationError 多條件分支

驗證錯誤根據輸入型別（Array / String / 其他）走不同分支，每個分支產生不同的錯誤訊息。只有 String 分支被測試。

### 4. CONFIG_ERROR 在 platform-switcher-service.js

3 處使用 CONFIG_ERROR 但零測試。平台切換配置錯誤會導致整個擴充功能在特定環境下無法啟動。

### 5. NetworkError 靜態工廠方法

`timeout()`、`connectionFailed()`、`rateLimited()` 三個工廠方法未驗證產出的錯誤物件是否包含正確的 code、message 和 retryable 屬性。

---

## 根因

1. **測試設計以成功路徑為主** -- Phase 2 設計測試案例時，異常路徑被視為「補充」而非「必要」
2. **錯誤碼引用 != 異常路徑測試** -- 測試中 import ErrorCodes 做斷言比對，被誤認為已覆蓋
3. **缺乏異常路徑覆蓋率指標** -- 沒有工具自動檢測「src/ 中使用的 ErrorCodes 是否都有觸發測試」

---

## Decision Question Q_new4 回答

> 「49 個生產異常路徑中只有 25 個有對應測試。最危險的 24 個缺口集中在初始化失敗、配置驗證、序列化異常。」

---

## 教訓

1. **異常路徑測試是必要的，不是補充的** -- Phase 2 測試設計必須為每個生產中使用的 ErrorCode 設計至少一個觸發測試
2. **區分「引用」和「測試」** -- 測試中 import 錯誤碼做比對不等於測試了異常路徑，必須驗證觸發條件
3. **初始化失敗和配置錯誤是最高風險** -- 這些錯誤發生在應用程式啟動階段，失敗時使用者完全無法使用功能

---

**Last Updated**: 2026-04-04
**Version**: 1.0.0 - 初始建立（0.17.0-W4-010）
