# 測試斷言設計規則（速查 stub）

> **完整論證與實證**：`.claude/references/test-assertion-design-details.md`（按需讀取，含各規則 Why/Consequence 全文、W1-017 / W1-018 實證數字、`tests/perf/` 檔頭範本、適用範圍表、兩個延伸路由章與 quality-baseline 交叉引用）。
> **概念框架**：跨專案通用斷言判斷框架（9 類型斷言問題、斷言品質三問、判斷決策表）→ `.claude/skills/test-assertion-design/SKILL.md`。

本文件定義測試斷言設計的品質底線，防止斷言結果依賴程式以外因素（機器負載、網路、時區等）導致 flaky。**設計前提**：效能差是設計問題，測試的職責是驗證功能正確性，不是量測執行速度。

---

## 不可靠斷言判準

**不可靠斷言 = 斷言結果依賴程式以外的可變因素，使紅燈不一定反映程式缺陷。**

| 因素類型 | 識別方法 | Dart/Flutter 典型樣態 |
|---------|---------|----------------------|
| 機器負載 | `Stopwatch` + `lessThan(N)` 作 pass-fail；同一斷言跨環境 GREEN/RED 擺盪 | `expect(stopwatch.elapsedMilliseconds, lessThan(500))` |
| 網路與外部服務 | 測試發出真實 HTTP 請求，無 mock/stub 介入 | `@Tags(['live'])`、`HttpClient` 直連外部 API |
| 檔案系統時序 | 斷言依賴 File I/O 完成速度或暫存檔時間戳 | `File(...).lastModified()` 比較 |
| 隨機數 | 斷言結果受 `Random()` 種子影響 | 未固定 seed 的隨機輸入 |
| 時區 / 時鐘 | `DateTime.now()` 直接進入斷言比較 | `expect(x.isBefore(DateTime.now().add(...)))` |
| 測試並行順序 | 共享可變靜態狀態使結果依賴執行順序 | `static var` 在 `setUpAll` 初始化但跨 group 共用 |

**判定流程**：對每個 `expect` / `assert`，問「若程式碼不變但環境改變（換機器 / 換時段 / 網路斷開），此斷言是否可能翻轉？」答案為「是」即命中。

---

## JS/Jest 落地規則（四規則速查）

| 規則 | 核心約束 | 豁免 |
|------|---------|------|
| 1 主套件禁絕對計時門檻 | `tests/unit/` `tests/integration/` 禁用 `toBeLessThan(Nms)` 作 pass-fail 斷言 | mock 固定回傳值（需加註解標明非效能 SLA）；`tests/perf/` 內 |
| 2 計時斷言集中 perf | 計時斷言全數放 `tests/perf/`，走 `npm run test:perf` 獨立執行 | — |
| 3 toBeCloseTo 精度 ≤ 2 | `toBeCloseTo(v, numDigits)` 的 `numDigits` 不得 > 2 | 確定性整數計算（如 `5/5=1.0`，需同行附加說明） |
| 4 快取驗證禁計時比較 | 禁 `secondRunTime < firstRunTime * N`；改用命中率 `getHitRate()` 或 `toBe` 參考比較 | — |

> 識別真實計時（不適用 mock 豁免）：斷言對象為 `Date.now()` / `performance.now()` / `getTimestamp()` 差值。

---

## Dart/Flutter 落地規則

### 規則 D1：主套件禁絕對計時門檻

`test/unit/`、`test/widget/`、`test/integration/`、`test/events/`、`test/regression/`、`test/domains/` 禁止以 `Stopwatch.elapsed*` + `lessThan(N)` / `greaterThan(N)` 作 pass-fail 斷言。

| 合法位置 | 說明 |
|---------|------|
| `test/performance/` | 效能基準測試，獨立於主套件執行 |
| mock 固定回傳值 | `Stopwatch` 測的是 mock delay 而非真實效能（需加 `// 非效能 SLA：測的是 mock 回傳值` 註解） |

**識別真實計時**：斷言對象為 `stopwatch.elapsedMilliseconds`、`stopwatch.elapsedMicroseconds`、`averageTimeMicros`、`averageTime`、`Duration.inMilliseconds` 差值。mock 延遲（如 `Future.delayed` 後量測 >= N）視為行為驗證，不受本規則限制（但上界斷言 `<= N` 仍受限，因環境抖動可能突破上界）。

### 規則 D2：外部服務測試必須隔離

直接發出真實 HTTP/Socket 請求的測試必須：
1. 標記 `@Tags(['live'])`
2. 在 `dart_test.yaml` 以 `skip: '需要網路和外部服務'` 從預設執行中排除
3. 由專用指令 `flutter test -t live` 顯式觸發

**Why**：外部服務可用性非程式缺陷，混入主套件會使紅燈失去診斷價值——紅燈時無法分辨是程式壞了還是外部服務抖動，團隊因此學會忽略紅燈。

### 規則 D3：`DateTime.now()` 不進入斷言比較

測試中需要時間戳時，使用固定值（`DateTime(2024, 1, 1)`）或注入式 `Clock`，禁止 `DateTime.now()` 直接參與 `expect` 比較。

**豁免**：`isBefore(DateTime.now().add(Duration(seconds: 1)))` 形式的「寬鬆範圍檢查」（容忍 1 秒以上）視為低風險，但建議改用固定時間。

### 規則 D4：隨機輸入必須固定 seed 或窮舉

測試使用 `Random` 產生輸入時，必須使用固定 seed（`Random(42)`）或改用窮舉邊界值。未固定 seed 的隨機測試紅燈不可重現。

---

## 延伸路由

| 主題 | 路由 |
|------|------|
| 各規則 Why/Consequence 全文 + 實證 + perf 檔頭範本 + 適用範圍表 | `.claude/references/test-assertion-design-details.md` |
| 測試綠燈不等於 Runtime 正確（修復鏈 acceptance 含 runtime 驗證） | `.claude/error-patterns/process-compliance/PC-165-false-positive-fix-chain.md` |
| 不可靠斷言跨環境擺盪實證 | IMP-APP-003「附帶發現：計時斷言污染紅燈判讀」章節（同一計時斷言跨環境 GREEN/RED 擺盪的對照實驗數據） |

---

## 規則 D5：外部 API 測資禁止虛構預期值

外部 API 測試（live test / 比較評估）的測資預期值（書名、作者等）必須來自已驗證來源，禁止猜測或推斷。

| 測試類型 | 測資要求 |
|---------|---------|
| 內部資料流（DB / Mock） | 可虛構（測程式碼邏輯） |
| 外部 API（live / 比較） | 必須已驗證（測外部系統回傳） |

**Why**：虛構的預期值與 API 真實回傳不符時，會得出「API 回傳錯誤」的假結論，可能影響架構決策（PC-APP-008 實證：差點因此放棄 Primo API）。

**Action**：每筆外部 API 測資必須標註驗證來源（keyed 實測日期 / 用戶提供）。無法驗證時標註「僅測可達性」，斷言不比對預期值。

## 檢查清單

撰寫或審查測試時確認：

- [ ] 新增斷言是否包含 `lessThan` + `elapsed*`（計時類）？若是，確認放在 `test/performance/` 而非主套件（D1）
- [ ] 測試是否發出真實 HTTP 請求？若是，確認標記 `@Tags(['live'])` 且從預設執行排除（D2）
- [ ] 斷言是否使用 `DateTime.now()`？若是，改用固定時間或注入式 Clock（D3）
- [ ] 測試是否使用 `Random()` 且未固定 seed？若是，改用固定 seed 或窮舉（D4）
- [ ] 外部 API 測資的預期值是否有驗證來源標註？若無，改為僅測可達性或補驗證（D5）
- [ ] 快取驗證是否使用計時比較？改用命中率或參考比較
- [ ] 效能測試是否已放在 `test/performance/` 並獨立執行

---

**Last Updated**: 2026-07-11
**Version**: 3.1.0 — 新增規則 D5：外部 API 測資禁止虛構預期值（PC-APP-008 實證，ISBN 標籤虛構致錯誤結論）。歷史 3.0 版見 git log。
