# 分層 i18n 管理方法論

> **完整程式碼範例（三層責任實作骨架 + 參數化訊息完整範例 + 四反模式正反程式碼對照）**：`.claude/references/business-layer-i18n-examples.md`（需照抄某一層的實作骨架、或需對照具體反模式程式碼理解違規時讀）

## 核心概念

i18n（國際化）訊息的管理遵循分層架構原則：**每層有明確的 i18n 責任，Domain 層不知道 UI 呈現方式**。

**關鍵原則**：
- 單一職責：每層只處理自己的 i18n 責任
- 關注點分離：Domain 層使用技術語言，ViewModel 層轉換為使用者語言
- 禁止硬編碼：所有使用者可見訊息必須來自合法來源

---

## 分層責任

> **各層完整程式碼範例（Domain/ViewModel/UI 實作骨架）**：見 `.claude/references/business-layer-i18n-examples.md`「三層責任完整程式碼範例」節（需照抄某一層實作骨架時讀）。

| 層級 | 職責 | 規則 |
|------|------|------|
| Domain/Service | 處理業務邏輯，回傳技術性結果或錯誤碼 | 使用 `ErrorCode` 枚舉或技術異常；禁止使用 i18n 或任何使用者訊息字串；回傳可被上層轉換的結構化資料 |
| ViewModel | 將 Domain 層結果轉換為 UI 可顯示的狀態，含使用者友善訊息 | 將 `ErrorCode` 轉換為 i18n 訊息；禁止硬編碼使用者訊息字串；使用三個合法訊息來源 |
| UI | 顯示 ViewModel 提供的狀態和訊息 | 直接使用 ViewModel 提供的訊息；禁止自行組裝或轉換訊息；禁止硬編碼使用者訊息字串 |

**ViewModel 層的三個合法訊息來源**：

| 來源 | 使用場景 | 範例 |
|------|---------|------|
| i18n 系統 | 靜態訊息，多語言支援 | `context.l10n!.invalidFileFormat` |
| ErrorHandler | 統一錯誤處理 | `ErrorHandler.getMessage(errorCode)` |
| Domain 回傳 | 動態訊息（伺服器回傳） | `apiResponse.message` |

---

## 錯誤訊息流程

```text
[Domain/Service 層]
        |
        | 回傳 ErrorCode 或技術異常
        v
[ViewModel 層]
        |
        | 使用 ErrorHandler 或 i18n 轉換為使用者訊息
        v
[UI 層]
        |
        | 直接顯示訊息
        v
[使用者看到友善訊息]
```

**完整流程範例**：

```text
1. Repository 捕獲 TimeoutException
2. Repository 回傳 Result.failure(BookErrorCode.networkTimeout)
3. ViewModel 接收 errorCode
4. ViewModel 呼叫 ErrorHandler.getMessage(errorCode)
5. ErrorHandler 查詢 i18n：l10n.networkTimeout -> "網路連線逾時，請稍後再試"
6. ViewModel 更新 state.errorMessage
7. UI 顯示 state.errorMessage
```

---

## 參數化訊息處理

當訊息需要動態參數時，在 ViewModel 層組裝（以 ARB 檔案定義 placeholder，在 ViewModel 呼叫帶參數的 l10n 方法）。

**禁止做法**：在 UI 層用字串插值組裝訊息（硬編碼違規）；在 Domain 層拋出含使用者訊息的 Exception（Domain 不應產生使用者訊息）。

> **參數化訊息完整範例（ARB 定義 + ViewModel 使用 + 禁止做法程式碼）**：見 `.claude/references/business-layer-i18n-examples.md`「參數化訊息完整範例」節（需對照 ARB placeholder 語法或禁止做法程式碼時讀）。

---

## 反模式

> **四反模式正反程式碼對照（完整錯誤程式碼）**：見 `.claude/references/business-layer-i18n-examples.md`「四反模式正反程式碼對照」節（需對照具體違規程式碼時讀）。

| 反模式 | 違規描述 | 為什麼是錯的 |
|--------|---------|-------------|
| 一：Domain 層包含使用者訊息 | Repository 回傳硬編碼中文錯誤字串 | 違反關注點分離；無法支援多語言；Domain 耦合到 UI 呈現 |
| 二：ViewModel 硬編碼訊息 | ViewModel switch 直接 copyWith 中文字串 | 無法支援多語言；訊息散落難以維護；違反 i18n 規範 |
| 三：UI 層自行組裝訊息 | Widget 依 errorCode 三元運算選訊息 | UI 應只負責呈現不負責邏輯；訊息邏輯應集中在 ViewModel；增加 UI 複雜度 |
| 四：跨層傳遞 Context | 將 BuildContext 傳入 Domain 層 | Domain 耦合到 Flutter 框架；難以測試；違反分層架構 |

---

## 執行步驟

1. **確認層級**：判斷目前程式碼屬於哪一層
2. **選擇訊息來源**：Domain 用 ErrorCode，ViewModel 用 i18n/ErrorHandler
3. **實作轉換**：在 ViewModel 層完成 ErrorCode 到訊息的轉換
4. **驗證 UI**：確認 UI 只顯示 ViewModel 提供的訊息

---

## 檢查清單

### Domain/Service 層

- [ ] 使用 ErrorCode 枚舉而非訊息字串
- [ ] 無 i18n 相關 import
- [ ] 無硬編碼使用者訊息
- [ ] 無 BuildContext 依賴

### ViewModel 層

- [ ] 所有使用者訊息來自三個合法來源
- [ ] 無硬編碼使用者訊息字串
- [ ] ErrorCode 轉換邏輯集中（ErrorHandler）
- [ ] 參數化訊息在此層組裝

### UI 層

- [ ] 直接使用 ViewModel 提供的訊息
- [ ] 無自行組裝訊息邏輯
- [ ] 無硬編碼使用者訊息字串
- [ ] 無 ErrorCode 判斷邏輯

### 整體架構

- [ ] i18n 訊息轉換只發生在 ViewModel 層
- [ ] Domain 層與 UI 呈現完全解耦
- [ ] ErrorHandler 集中管理錯誤訊息轉換

---

## Reference

### 衛星檔

- [分層 i18n 管理：完整程式碼範例](../references/business-layer-i18n-examples.md) - 三層責任實作骨架 + 參數化訊息完整範例 + 四反模式正反程式碼對照

### 專案規範

- 專案使用者訊息 / i18n 規範：見各專案 `CLAUDE.md`「專案特定規範」節（路由至該專案的訊息系統規範文件，如本 Chrome Extension 專案的 `docs/project-conventions.md` Messages 系統規範；Flutter 專案則為 ViewModel 層使用者訊息規範）- 業務層禁止事項和檢查清單
- [錯誤修復和重構方法論](./error-fix-refactor-methodology.md) - 錯誤處理原則

### 相關方法論

- [行為優先 TDD 方法論](./behavior-first-tdd-methodology.md) - 測試設計原則
- [程式碼自然語言化撰寫方法論](./natural-language-programming-methodology.md) - 命名規範
