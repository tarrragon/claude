# 測試斷言設計規則

> **定位路由**：跨專案通用概念框架（9 類型斷言問題、斷言品質三問、判斷決策表）位於 `.claude/skills/test-assertion-design/SKILL.md`。本檔為**本專案（Chrome Extension / JS / Jest）專屬規則**，規範具體精度數字（`numDigits <= 2`）、測試目錄規定（`tests/perf/`）與實證案例引用（W1-017、W1-018）。兩者分層互補：skill 提供判斷概念，本檔提供專案落地約束。

本文件定義所有 JavaScript 測試（Jest / Puppeteer）中斷言設計的品質底線，防止計時依賴與高精度浮點斷言在 CI 或全套件負載下造成 flaky。

> **設計前提**：效能差是設計問題，不是功能問題。測試的職責是驗證功能正確性，不是量測執行速度。
> **與 quality-baseline 的邊界**：`quality-baseline.md` 規則 1 要求「測試通過率 100%」。本規則是實現規則 1 的前置條件——若斷言設計依賴環境計時，100% 通過率在 CI 負載下無法保證。兩者互補：規則 1 是通過率目標，本規則是斷言設計約束。
> **觸發案例**：W1-017（event-system 與 UC07 計時硬門檻修復）、W1-018（全專案計時斷言盤點）。

---

## 規則 1：npm test 主套件禁止絕對計時門檻當 pass-fail 斷言

> 本規則處理**絕對計時門檻**（`toBeLessThan(N)`，直接比較單次計時值）。**相對計時比較**（`timeA < timeB * N`，比較兩次執行差距）屬快取驗證反模式，見規則 4。

**禁止在 `tests/unit/` 和 `tests/integration/`（即 `npm test` 掃描範圍）使用 `toBeLessThan(Nms)` 等計時硬門檻作為 pass-fail 驗收條件。**

**Why**：Jest 在 jsdom 環境下大量使用 mock，計時值受全套件機器負載、GC 觸發、JIT 暖機影響，是非確定性數值。在開發機單獨執行時通過，在 CI 或完整 `npm test`（195 suites 並行）下容易超過門檻失敗。W1-017 實證：`avgSuggestionTime < 2ms` 單獨執行連續 23/23 通過，完整 `npm test` 下實測 2.48ms 失敗。

**Consequence**：計時斷言在完整套件下 intermittent flaky，違反 `quality-baseline.md` 規則 1（測試通過率 100%）。每次失敗需人工判斷是真實回歸還是環境噪音，增加診斷成本；積累多個計時斷言後 npm test 變成不可信指標。

**Action**：

| 既有計時斷言類型 | 對應處理 |
|----------------|---------|
| `expect(time).toBeLessThan(N)` 純計時 | 移除計時斷言，保留功能正確性驗證 |
| 含計時且無其他功能驗證的 test case | 整個 test case 移至 `tests/perf/`（見規則 2） |
| 計時門檻混在功能測試檔 | 只移除計時行，該檔其他功能斷言保留原位 |

**允許的例外**：
- **mock 固定回傳的計時值**：斷言對象是 mock 回傳的固定數字（例如 `expect(mockDuration).toBeLessThan(1000)`），而非由 `performance.now()` / `Date.now()` 差值計算的真實計時——mock 控制值不受環境影響。可保留，但應加註解標明非效能 SLA（例如 `// mock 固定回傳值，非真實計時量測`）
- `tests/perf/` 目錄下的計時斷言（經 `npm run test:perf` 獨立執行，已明確定位為大幅退化防護）

**識別非豁免情境**：看到 `Date.now()` 差值、`performance.now()` 差值、`getTimestamp()` 差值作為斷言對象，即為真實計時，不適用 mock 豁免。

---

## 規則 2：效能測試放 tests/perf/，透過 npm run test:perf 獨立執行

**計時斷言必須集中在 `tests/perf/` 目錄，透過 `npm run test:perf` 獨立執行，禁止殘留於 npm test 主套件。**

**Why**：效能量測需要隔離環境（低負載、預熱後）才有意義。Jest jsdom 非有效效能量測環境，與功能測試混跑時 JIT 暖機狀態、記憶體壓力都不一致，量測結果無可重現性基準。W1-017 採方案 A 物理拆檔，將兩個純效能 describe 移至 `tests/perf/` 後，`npm test` 達穩定 100%，`npm run test:perf` 提供獨立可控的效能基準。

**Consequence**：效能測試殘留 `tests/integration/` 或 `tests/unit/` 會導致：（a）環境依賴使 npm test 不穩定；（b）效能基準資料在全套件負載下失真，無法作為有效回歸偵測依據。

**Action**：

| 測試類型 | 放置位置 | 執行方式 |
|---------|---------|---------|
| 功能正確性（輸出值、狀態、結構） | `tests/unit/` 或 `tests/integration/` | `npm test` |
| 穩定性（零崩潰、零記憶體洩漏） | `tests/integration/` | `npm test` |
| 計時門檻（大幅退化防護） | `tests/perf/` | `npm run test:perf` |
| 效能基準報告（benchmark output） | `tests/perf/` | `npm run test:perf` |

`npm test` 解析為 `jest tests/unit tests/integration`，路徑正則不覆蓋 `tests/perf/`，自動排除，無需額外 exclusion 配置。

**tests/perf/ 檔頭標準**：每個效能測試檔開頭應有以下標注（W1-017 實作範本）：

```javascript
/**
 * 效能測試：[模組名稱]
 *
 * 注意：此測試在 Jest jsdom 環境下執行，使用 mock 模擬，非有效效能量測環境。
 * 計時斷言定位為「大幅退化防護」而非效能 SLA，門檻寬鬆（如 <10000ms）。
 * 執行方式：npm run test:perf（獨立於 npm test 主套件）
 */
```

---

## 規則 3：toBeCloseTo 精度不超過 2 位（除非驗證確定性整數計算）

**`toBeCloseTo(value, numDigits)` 的 `numDigits` 參數不得超過 2，例外情況需附加說明。**

**Why**：`toBeCloseTo(v, 5)` 表示精度到小數點後 5 位（±0.000005）。浮點平均值、信賴度計算等結果在 IEEE 754 下因 JIT 編譯路徑、運算順序不同，5 位精度可能因環境差異產生不同的末位數字。W1-017 實證：`expect(avgProgress).toBeCloseTo(scenario.averageProgress, 5)` 在完整 `npm test` 首次執行失敗（intermittent），單獨執行 13/13 通過，確認為高精度 × 跨 suite 負載的共振問題。

**Consequence**：高精度浮點斷言 intermittent flaky，在 CI 中零星失敗，難以與真實回歸區分。盤點（W1-018）發現三處 `numDigits=5` 斷言分布於兩個檔案，屬系統性問題而非個案。

**Action**：

| 場景 | 建議精度 | 理由 |
|------|---------|------|
| 浮點平均值 | 1-2 位 | 四捨五入到小數點後 2 位的差異已足以偵測業務邏輯回歸 |
| 信賴度、比率計算（0 到 1 之間） | 1-2 位 | 同上 |
| 確定性整數計算轉浮點（如 `5/5 = 1.0`） | 允許更高 | 結果確定性高，需附加說明 `// 確定性整數計算，精度 N 位合理` |
| 物理量測值 | 1-2 位 | 感測器精度通常不超過 2 位有效數字 |

**例外豁免**：驗證確定性整數計算（如除法結果整除、固定比率）可使用高精度，但必須在同行附加說明：

```javascript
// 正確：確定性整數計算，精度 5 位合理
expect(result).toBeCloseTo(1.0, 5); // 5/5 = 1.0，非浮點累積誤差

// 錯誤：浮點平均值高精度（intermittent flaky）
expect(avgProgress).toBeCloseTo(scenario.averageProgress, 5);
```

---

## 規則 4：快取加速驗證用命中率而非計時比較

**驗證快取加速效果時，禁止用 `secondRunTime < firstRunTime * N` 的計時比較斷言；改用快取命中率 `getCacheHitRate()` 或等效的快取狀態查詢。**

**Why**：`secondRunTime < firstRunTime * 0.8`（「第二次快 20%」）是相對計時比較，同樣受 GC、JIT 暖機影響。在 mock 環境下兩次呼叫的時間差可能在雜訊範圍內（sub-millisecond），使相對比較失去意義。W1-018 盤點發現 `readmoo-data-validator.test.js:641` 使用此模式，屬設計不良需重新設計。

**Consequence**：相對計時比較無法區分「快取確實有效」與「第二次 JIT 已暖機」，測試既不能正確驗證快取功能，又因環境依賴有 flaky 風險。此斷言同時具備「功能驗證失效」和「環境依賴 flaky」兩個問題，是最不值得保留的計時斷言類型。

**Action**：

```javascript
// 錯誤：計時比較，受 GC/JIT 影響 flaky，且在 mock 環境下無效能量測意義
expect(secondRunTime).toBeLessThan(firstRunTime * 0.8);

// 正確選項 A：驗證快取命中率大於 0（有使用快取）
expect(cache.getHitRate()).toBeGreaterThan(0);

// 正確選項 B：驗證快取已有項目（快取確實被填充）
expect(cache.size).toBeGreaterThan(0);

// 正確選項 C：驗證第二次呼叫返回相同物件參考（toBe，非 toEqual）
const firstResult = service.getMapping();
const secondResult = service.getMapping();
expect(secondResult).toBe(firstResult); // Object.freeze 單例，快取不重建
```

選項 C（`toBe` 參考比較）是最強的快取驗證：若快取失效重建物件，`toBe` 必然失敗，與計時完全無關。W1-017 中 UC07 的 `toEqual → toBe` 修改即採此原則。

---

## 適用範圍

| 規則 | 適用 | 不適用 |
|------|------|--------|
| 規則 1（禁止計時硬門檻） | `tests/unit/`、`tests/integration/` | `tests/perf/`（已隔離，允許計時斷言） |
| 規則 2（效能測試放 perf） | 所有計時為主要驗收的 describe | 功能測試、穩定性測試（零崩潰類） |
| 規則 3（toBeCloseTo 精度 ≤2） | 所有 Jest 測試檔 | 確定性整數計算（需附加說明豁免） |
| 規則 4（快取命中率取代計時比較） | 所有驗證快取效能的 test case | 非快取相關的計時測試 |

---

## 延伸路由：測試綠燈不等於 Runtime 正確

本規則處理「斷言設計品質」（計時 / 精度 / 快取驗證方式），但測試綠燈本身不保證 runtime 行為正確。修復「訊息系統 / 日誌系統 / 跨模組整合」類 bug 時，unit test pass 是必要條件不是充分條件，acceptance 必須含 runtime 層級驗證（chrome-devtools-mcp 實機 / integration 斷言訊息文字）。

**Why**：mock 取代真實依賴 + 斷言只檢查結構 + 動態語言靜默忽略多餘參數 → 三層共振可讓修復鏈中每步綠燈但端到端 runtime 失效。

**Consequence**：false positive 修復被視為「修復已生效」，後續 ticket 基於此假設推進，將表層補救移除後暴露根本未生效的修復；連鎖回溯成本高。

**Action**：修復類 + 訊息 / 日誌 / 跨模組整合三標籤聯集的 IMP ticket，acceptance 必含至少 1 項 runtime 驗證項。詳見 `.claude/error-patterns/process-compliance/PC-165-false-positive-fix-chain.md`（含 W1-105 / W1-106 / W1-108 事件鏈 + 三層共振機制 + 三層防護設計）。

---

## 延伸路由：src 字串輸出變更 acceptance 設計

本規則處理「斷言品質」（計時 / 精度 / 快取），但斷言期待值與 src 字串的同步問題是 acceptance 設計責任，見 `ticket-body-schema.md`「src 字串輸出變更額外 acceptance」章節。

**Why**：`src/` 字串字面（log 前綴、錯誤訊息、UI 文案）修改後，`tests/` 斷言期待值（`toHaveBeenCalledWith` / `toContain`）若未同步更新，兩者靜默不一致。`npm run build:dev` 只驗編譯，不驗斷言期待值，build 綠燈不能代表 test 綠燈。

**Consequence**：修改 src 字面只驗 build 的 IMP 一旦 complete，後續 `npm test` 執行時爆發跨 ticket 隱性回歸，回溯根因和補修成本均遠高於同步驗證（W1-005.2 → W1-005.3：12 檔 48+ 處斷言補修）。

**Action**：IMP ticket 修改 `src/` 字串字面時，acceptance 必須包含「complete 時驗收：`npm test` exit 0」，不可只驗 `npm run build:dev`。

**參考**：`.claude/pm-rules/ticket-body-schema.md`「IMP > src 字串輸出變更額外 acceptance」、觸發案例 `0.19.1-W1-005.2`

---

## 與 quality-baseline 的交叉引用

| quality-baseline 規則 | 本規則的對應關係 |
|----------------------|----------------|
| 規則 1（測試通過率 100%） | 本規則是達成規則 1 的設計前提；計時斷言 flaky 是規則 1 最常見的違反路徑之一 |
| 規則 3（設計問題立即修正） | 發現計時斷言違規時，不可延後處理（W1-018 已完整盤點，W1-019 跟進修復） |
| 規則 5（所有發現必須追蹤） | 盤點中發現的每個違規斷言必須有對應 ticket（W1-018 → W1-019 + W1-020） |

---

## 檢查清單

撰寫或審查測試時確認：

- [ ] 新增斷言是否包含 `toBeLessThan`（計時類）？若是，確認放在 `tests/perf/` 而非主套件
- [ ] `toBeCloseTo` 的 `numDigits` 是否 ≤ 2？若 > 2，是否有確定性計算的說明
- [ ] 快取驗證是否使用命中率或參考比較（而非計時比較）
- [ ] 效能測試是否已建立 `tests/perf/` 檔頭標注

---

## 相關文件

- `.claude/rules/core/quality-baseline.md` — 規則 1（測試通過率 100%）、規則 3（設計問題立即修正）
- `.claude/error-patterns/process-compliance/PC-165-false-positive-fix-chain.md` — 測試綠燈不等於 runtime 正確（修復鏈 acceptance 含 runtime 驗證）
- `.claude/pm-rules/ticket-body-schema.md` — IMP 「src 字串輸出變更額外 acceptance」章節（src 字面修改必含 npm test）
- `docs/work-logs/v0/v0.19/v0.19.0/tickets/0.19.0-W1-017.md` — 計時斷言修復案例（event-system + UC07）
- `docs/work-logs/v0/v0.19/v0.19.0/tickets/0.19.0-W1-018.md` — 全專案盤點分析（7 檔 21 個斷言的分類判斷）
- `tests/perf/` — 效能測試目錄（`npm run test:perf`）

---

**Last Updated**: 2026-06-04
**Version**: 1.3.0 — 新增「延伸路由：src 字串輸出變更 acceptance 設計」章節（W1-005.2 教訓固化，交叉引用 ticket-body-schema.md / 0.19.1-W1-040）。歷史 1.0–1.2 版見 git log。
