---
id: PC-APP-008
title: 外部 API 測試使用虛構測資標籤導致錯誤結論
severity: high
category: process-compliance
first_seen: 2026-07-11
tags: [test-data, live-api, fixture, confabulation]
related_patterns: [PC-166]
---

# PC-APP-008：外部 API 測試使用虛構測資標籤導致錯誤結論

## 症狀

API 比較測試結論出現「API 回傳錯誤結果」「命中率高但全是誤命中」，但用戶實測結果相反。

## 根因

PM 從專案 test/lib 中 grep 出 ISBN 號碼後，**自行猜測書名標籤**（如 9789864793563 標為「原子習慣」），用虛構的 ISBN ↔ 書名對應關係跑 live API 比較測試。API 回傳的書名與虛構標籤不符，PM 得出「Primo API 80% 誤命中」的錯誤結論。

實際上 Primo 回傳的書名才是正確的——是標籤搞錯了。

**與 PC-166（confabulation）同構**：用預期填補未知事實，且結果自洽到察覺不到錯誤。差異在於 PC-166 是工具輸出虛構，本模式是測資標籤虛構。

## 影響

- 錯誤結論差點影響架構決策（放棄 Primo API 作為主要來源）
- 浪費分析時間（重新用已驗證測資跑一次才得到正確結論）

## 防護規則

### 內部 vs 外部測資二分法

| 測試類型 | 測資要求 | 理由 |
|---------|---------|------|
| 內部資料流（DB / Repository / Mock） | 可虛構 | 測的是程式碼邏輯，測資只需結構正確 |
| 外部 API 測試（live / 比較評估） | **必須已驗證真實性** | 測的是外部系統回傳，虛構預期值無法判定結果正確性 |

### 外部 API 測資使用三步驟（強制）

1. **來源標註**：每筆測資必須標註驗證來源（keyed 實測日期 / 官方資料庫查詢 / 用戶提供）
2. **預期值驗證**：預期值（書名、作者等）必須來自可靠來源，禁止猜測或推斷
3. **未驗證明示**：若無法驗證預期值，必須在測試中標註「預期值未驗證，僅測試 API 可達性」，斷言不得包含預期值比對

### 識別信號

| 信號 | 風險 |
|------|------|
| 測試中 `const _isbns = <String, String>{isbn: '書名'}` 且書名無來源註解 | 高：標籤可能虛構 |
| 結論含「API 回傳錯誤結果」但未交叉驗證預期值本身是否正確 | 高：可能是標籤錯誤 |
| 測資 ISBN 從 grep 撈出但未查證對應書籍 | 高：ISBN 是無語意數字，無法從號碼推斷書名 |

### 正確做法參考

```dart
/// fixture ISBN 選用依據（keyed 查詢實測，2026-07-10）：
/// - 9789574442515（傷心咖啡店之歌，台灣・九歌）——PM keyed 實測可得
/// - 9789571374864（遇見100%的女孩，台灣・時報）——PM keyed 實測可得
const _verifiedIsbns = <String, String>{
  '9789574442515': '傷心咖啡店之歌',
  '9789571374864': '遇見100%的女孩',
};
```

## 解決方案

1. 發現結論異常時，優先質疑測資而非 API
2. 使用既有已驗證 fixture（如 google_books_live_test.dart 檔頭的 keyed 實測備選池）
3. 無已驗證測資時，先用「僅測可達性」模式（不比對預期值），再請用戶提供已驗證對應

## 相關

- PC-166：confabulation（用預期填補未知事實）
- `test/integration/scanner/live_api/google_books_live_test.dart`：正確示範（檔頭 keyed 實測來源註解）
- `.claude/rules/core/test-assertion-design-rules.md`：測試斷言品質規則
