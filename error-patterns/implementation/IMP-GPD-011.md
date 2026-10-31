---
id: IMP-GPD-011
title: 回饋排在會讓觸發者卸載的 await 之後，mounted 守衛把回饋靜默吞掉
severity: 中
status: active
---

# IMP-GPD-011: 回饋排在會讓觸發者卸載的 await 之後，mounted 守衛把回饋靜默吞掉

## 基本資訊

- **Pattern ID**: IMP-GPD-011
- **分類**: 實作（implementation）
- **風險等級**: 中（回饋整個消失，使用者不知道某件事失敗；功能本身照常運作，所以不會被當成錯誤回報）
- **來源版本**: 0.5.0
- **相關 Pattern**: IMP-GPD-006（判定依據與被判定對象脫鉤；本模式是「回饋時機」與「回饋載體的存活期」脫鉤）

---

## 問題描述

### 症狀

- UI 事件處理函式先 `await` 一個會改變畫面狀態的流程，例如「選定工作區 → 畫面狀態轉為載入中」。這個狀態轉換讓觸發按鈕所在的 widget 從樹上移除
- 處理函式在 await 之後才寫 `if (!context.mounted) return;`，再顯示 SnackBar 或其他回饋
- await 返回時 context 必定已卸載，回饋分支一次都不會執行
- `mounted` 守衛本身是正確寫法，靜態分析與 lint 都不會報；沒有走到這條分支的測試時，全綠

### 根因

回饋的時序綁在「流程完成之後」，但流程本身就是讓觸發者消失的那件事：

| 步驟 | 觸發 widget 狀態 | 結果 |
|------|----------------|------|
| 點按，進入處理函式 | 已掛載 | 可以顯示回饋 |
| `await` 流程（流程中狀態轉換、widget 被替換） | 已卸載 | — |
| await 返回，檢查 `context.mounted` | 已卸載 | 守衛返回，回饋被丟棄 |

`mounted` 守衛把「這個 context 不能用」轉成「什麼都不做」，失敗沒有任何訊號。

### 缺陷為何不易被發現

- 功能主路徑（流程本身）正常，只有附帶的回饋消失
- 測試常只斷言「流程被呼叫」（替身計次），對回饋是否出現沒有鑑別力
- 被吞掉的多半是次要提示（例：「已選定，但偏好設定未能寫入」），手動測試很難觸發該條件

---

## 解決方案

依回饋與流程結果的關係擇一：

1. **回饋與流程結果無關**（例：偏好設定寫入失敗的提示，在流程開始前就已知道）：在 `await` 之前顯示
2. **回饋必須等流程結果**：在 `await` 之前取得不依附觸發 widget 的載體，例如 `ScaffoldMessenger.of(context)`，或上層注入的回饋服務；await 後用該載體顯示，不再讀觸發 widget 的 context

```dart
// 錯誤：await 讓觸發 widget 卸載後才顯示，必定被守衛擋下
await selectWorkspace(ref, state);
if (!context.mounted) return;
showNotice(context, message);

// 正確（結果無關的提示）：先顯示，再 await
showNotice(context, message);
await selectWorkspace(ref, state);
```

---

### 變體：共用流程拿呼叫端的 WidgetRef，在 await 之後繼續使用

同一根因的另一種失敗形態，例外取代了靜默：

- 共用流程的簽名為 `Future<void> f(WidgetRef ref, ...)`，內部先 await 會讓呼叫端卸載的步驟，之後再 `ref.read(...)` 寫其他狀態
- 呼叫端卸載後，Riverpod 丟出 `Bad state: Cannot use "ref" after the widget was disposed`，後段副作用（例：寫入最近清單）不執行
- 由不會卸載的呼叫端（例：常駐浮層）觸發時一切正常，所以先抽出共用流程、只接一個呼叫端時不會暴露；接上第二個會卸載的呼叫端才出現

修法：副作用改由 app 層的 Notifier 執行（它的 `ref` 隨 ProviderContainer 存活）。對外的函式可保留 `WidgetRef` 參數作為薄包裝，但只在第一個 await 之前用它取得 notifier。

## 預防措施

- 審查 UI 事件處理函式時，凡是 `await` 之後接 `context.mounted` 再顯示回饋的寫法，逐一問：被 await 的流程會不會讓這個 widget 卸載？會的話，該回饋分支就是死碼
- 測試讓該分支走完整流程，並斷言回饋確實出現；只斷言流程被呼叫的測試不算覆蓋
- 規格寫互動反應時，回饋的觸發時刻（流程前或流程後）要明寫，實作照時刻落點

## 實例

一個桌面 App 的「選擇資料夾」按鈕位在「未選專案」畫面。選定成功但偏好設定寫入失敗時，程式先 await 共用的選定流程（流程把畫面狀態轉為載入中，未選專案畫面被替換），再檢查 mounted、顯示「未能記住」提示。結果提示從未出現。該分支沒有測試。PM 驗收讀 diff 時發現，退回實作者改為先顯示再 await，並補一則斷言提示出現的測試。
