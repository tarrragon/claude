---
id: IMP-079
title: 批次替換工具誤傷偵測目標字面 — regex/meta-test 內嵌待測字元被盲目轉換後語意塌縮
category: implementation
severity: medium
status: active
created: 2026-06-04
related:
- PC-158
- PC-165
---

# IMP-079: 批次替換工具誤傷偵測目標字面 — regex/meta-test 內嵌待測字元被盲目轉換後語意塌縮

批次替換工具（如 `scripts/remove-emoji.js`）對指定目錄全量執行轉換時，無法區分「被替換的目標字串」與「用於偵測目標的偵測字串」。測試檔案中的 regex pattern 或 meta-test 陣列常內嵌待測字元作為偵測目標；盲目轉換這些字面後，regex 字元類別語意錯誤或 pattern 整體過寬，測試仍能通過但偵測邏輯已失效。

**Why**：批次替換工具設計目標是「在業務程式碼中消除 X」，不具備語境感知能力——它無法辨別「字串中的 X 是要被清除的業務字面」還是「字串中的 X 是用於測試 X 存在與否的偵測目標」。兩者在檔案系統層面均為相同位元組，工具無從區分。

**Consequence**：偵測邏輯語意塌縮有兩種失效模式：(a) 映射內字元被替換為 `[KEYWORD]` 後，正則字元類別 `[...]` 中的 `K`/`E`/`Y` 等字母被當作字元匹配條件，導致誤匹配正常英文字母；(b) 映射外字元被直接移除後，regex pattern 塌縮過寬，無特徵匹配範圍擴大。兩種失效模式均可能讓 `npm test` 持續通過（因為 regex 仍是合法表達式），但偵測能力已靜默喪失——此即「工具操作成功，測試仍綠，但防護目標已失效」的 false positive 修復鏈前置條件（PC-165 機制）。

**Action**：工具設計必須支援排除清單；對 `tests/` 執行批次替換前必須 diff 審查含 regex 字面的檔案。

---

## 基本資訊

- **Pattern ID**: IMP-079
- **分類**: 實作（implementation）
- **來源版本**: v0.19.1
- **發現日期**: 2026-06-04（W1-005.3 執行期，ANA W1-007 固化）
- **風險等級**: 中
- **標籤**: `batch-replace` `regex` `meta-test` `detection-target` `false-positive` `tests-corruption` `remove-emoji`

---

## 與其他 error-pattern 的關係

| Error Pattern | 關聯性 | 說明 |
|--------------|--------|------|
| PC-158（emoji-in-visual-markers） | 弱相關（同屬 emoji 合規類）| PC-158 聚焦 agent 產出中的 emoji 違規（輸出層）；IMP-079 聚焦批次工具對測試檔 regex 字面的盲目轉換（工具操作層）。兩者根因領域不同：PC-158 是代理人規則意識問題，IMP-079 是工具設計無語境感知問題 |
| PC-165（false-positive-fix-chain） | 上位關係（IMP-079 是觸發路徑之一）| PC-165 描述「unit test 綠燈但 runtime/端到端邏輯失效」的三層共振機制（mock 替代 + 斷言不檢查字面 + 動態語言靜默忽略）。IMP-079 是更早一層的觸發——工具操作將 regex 字面盲目替換後，tests 本身仍 pass，但其偵測能力已靜默失效，為 PC-165 鏈提供一個新的「測試通過但行為已改變」前置條件 |

**分類說明**：歸 `implementation/`（IMP）而非 `process-compliance/`（PC），觸發點在工具設計層（`scripts/remove-emoji.js` 無排除機制），防護機制亦在工具設計層（排除清單 + diff 審查）。非流程協作層問題。

---

## 問題分析

### 症狀

- `npm test` 全套件通過，acceptance 勾選完成
- 批次替換工具（如 `node scripts/remove-emoji.js tests/`）執行後顯示 `modified: <file>` 正常輸出
- 事後 code review 或手動還原時發現 tests/ 某檔案中 regex pattern 語意已改變：
  - 失效模式 A：映射內字元（如 `[FAIL]` 映射）被替換後，regex 字元類別 `[F]` / `[FA]` / `[FAI]` / `[FAIL]` 中出現英文字母，誤匹配正常文字
  - 失效模式 B：映射外字元被直接移除，regex pattern 塌縮為過寬匹配（如 `/log\.(info|error|warn)\(['"` 後接空字串，匹配所有 log call）

### 根本原因（5 Why 分析）

1. 批次替換工具對 `tests/` 執行後，`background-local-dict.test.js` 中 antiPatterns 陣列的 regex 字面被修改
2. 為何 regex 字面被修改？— `scripts/remove-emoji.js` 的 `transformContent()` 對全檔案內容做字串 replace，無任何路徑、行號或語境排除機制
3. 為何需要排除機制？— 測試檔案中的 regex pattern 以「原始待測字元字面」作為偵測目標（即 regex 匹配條件本身包含應被偵測的 emoji 字元）；業務程式碼中同一字元是「被替換的對象」，語境完全相反
4. 為何工具不區分語境？— 工具設計目標是「對指定目錄所有 .js 檔執行相同轉換」，抽象層面是批次文字操作，不具備 regex AST 解析或測試語境感知能力
5. **根本原因**：批次替換工具在設計上缺乏「偵測目標字面」這一語境概念——工具不知道「regex pattern 內部的字元是偵測目標，不是被替換目標」，也未提供讓呼叫者宣告排除範圍的機制（排除清單、路徑過濾、行號標記均無）

---

## 動機案例

### W1-005.3（2026-06-03，v0.19.1）

`scripts/remove-emoji.js` 最初設計為對 `src/` 執行，W1-005.3 中為清理殘餘 emoji 擴大為對 `tests/` 執行。執行 `node scripts/remove-emoji.js tests/` 後，`tests/unit/background/background-local-dict.test.js` L508-518 的 antiPatterns 陣列被誤傷：

**受影響的 regex 結構（以 codepoint 描述，不使用 emoji 字元）**：

```javascript
// tests/unit/background/background-local-dict.test.js L508-518
// antiPatterns 陣列目的：驗證 src/background/background.js 中不再有
// log.X('emoji前綴...') 形式的殘留呼叫。
// 每個 regex 的 ['"` ] 後緊接「原始 emoji 字元字面」作為偵測目標。
const antiPatterns = [
  /log\.(info|error|warn)\(['"`]U+1F3C1/,  // 語意：以旗幟 emoji 開頭的 log call
  /log\.(info|error|warn)\(['"`]U+1F389/,  // 語意：以慶祝 emoji 開頭的 log call
  // ... 共 10 個 regex，每個均以 emoji 字元字面為匹配目標
]
```

**失效模式 A 範例**（以 codepoint 表示）：`U+274C`（❌，映射為 `[FAIL]`）被替換後，regex 變為：

```javascript
// 錯誤（替換後）：字元類別 [FAIL] 誤匹配 F/A/I/L 四個英文字母
/log\.(info|error|warn)\(['"`][FAIL]/
// 正確（替換前）：偵測 src/ 中以 U+274C 開頭的 log call
/log\.(info|error|warn)\(['"`]❌/
```

**失效模式 B 範例**（映射外字元）：`U+1F381`（🎁，純裝飾，直接移除）被移除後，regex 塌縮為過寬匹配，命中所有 log call 而非特定 emoji 前綴的 log call。

**既有警示註解**（`background-local-dict.test.js` L499-500，手動還原後加入）：

```javascript
// 此測試以「原始 emoji 字面」為偵測對象，驗證 dict 重構後 src 不再殘留 emoji 前綴
// log（應改用 log.X('MESSAGE_KEY') 形式）。emoji 字面為偵測目標，禁止經
// scripts/remove-emoji.js 轉換為 [KEYWORD]（會破壞 regex 語意，見 0.19.1-W1-005.3）。
```

**代價**：已手動還原並加警示註解。工具本身無防護，後續若再對 `tests/` 執行仍會重複觸發。

---

## 防護方向

### 防護一：工具支援排除清單（根本解，優先）

在 `scripts/remove-emoji.js` 中新增排除機制，讓呼叫者可宣告不轉換的檔案路徑或目錄：

```javascript
// 建議實作方向：--exclude 參數或 .remove-emoji-ignore 配置檔
// 範例呼叫形式
node scripts/remove-emoji.js tests/ --exclude tests/unit/background/background-local-dict.test.js
// 或
node scripts/remove-emoji.js src/ --exclude-pattern '**/background-local-dict.test.js'
```

呼叫者責任：凡 regex/meta-test 內嵌「原始待測字元」作為偵測目標的測試檔案，**必須**加入排除清單。

**Why**：排除清單使工具具備最小必要的語境感知——「這個檔案的字元是偵測目標，不是替換目標」——而無需工具理解完整語意。成本最低，副作用最小。

### 防護二：tests/ 批次替換前 diff 審查含 regex 字面的檔案

對 `tests/` 執行批次替換前，先用以下指令識別含 regex 字面的檔案，人工決定是否排除：

```bash
# 找出 tests/ 下含 regex 字元類別 [...] 且可能含偵測目標字元的檔案
# 重點掃描 antiPatterns、detector、validation 等關鍵字所在的測試檔案
grep -rln "antiPatterns\|detector\|[Dd]etect" tests/ --include="*.js"

# 執行後用 git diff 確認這些檔案的 regex 字面是否被修改
git diff tests/unit/background/background-local-dict.test.js
```

決策標準：diff 顯示 regex 字元類別 `[...]` 內容改變 → 立即還原該檔案並加入排除清單。

**Why**：即使工具尚未加入排除清單，人工 diff 審查可作為補救防護。成本低（只需確認 regex 字面部分），可在排除清單功能落地前作為過渡措施。

### 防護三：tests/ regex 偵測目標字面加警示註解（現有防護）

在含偵測目標字元字面的測試檔案中，於 regex 陣列上方加入警示註解，說明字元為偵測目標禁止被批次工具轉換：

```javascript
// 此測試以「原始字元字面」為偵測對象。
// 字元字面為偵測目標，禁止經 scripts/remove-emoji.js 或類似批次替換工具轉換。
// 轉換後 regex 語意塌縮（字元類別 [...] 誤匹配英文字母 / pattern 過寬），見 IMP-079。
const antiPatterns = [...]
```

`background-local-dict.test.js` L499-500 已有此警示（W1-005.3 手動還原後加入）。此為最低成本防護，但依賴工具使用者主動閱讀並配合，不如防護一可靠。

---

## 自查清單

執行批次替換工具前確認：

- [ ] 工具是否支援排除清單？若是，已確認需排除的 regex/meta-test 檔案已加入清單
- [ ] 目標目錄是否包含 `tests/`？若是，先執行 `grep -rln "antiPatterns\|detector" tests/` 確認潛在偵測目標檔案
- [ ] 執行後立即 `git diff tests/` — 確認 regex 字元類別 `[...]` 是否變動；如有變動立即還原並加入排除清單
- [ ] 若 diff 顯示 tests/ 任何 regex 字面被修改 → 停止、還原、建 IMP ticket 補加排除機制

---

## 抽象層級分析（必填）

| 欄位 | 內容 |
|------|------|
| 症狀層級 | 工具層（`scripts/remove-emoji.js` 執行輸出 `modified: <file>`，表面無異常）/ 實作層（regex 字元類別語意靜默改變）|
| 根因層級 | 工具層（批次替換工具設計缺乏排除機制，無法宣告「偵測目標字面」概念）|
| 跨層路徑 | N/A；症狀與根因同在工具層/實作層，無跨層 |
| 防護層級 | 工具層：防護一（工具排除清單）；實作層：防護二（diff 審查）+ 防護三（警示註解）|
| 跨層警示 | 禁止提升至認知層（「工具使用者不小心」）；根因是工具設計缺失，非個人失誤。若被引用於設計討論，應聚焦工具介面設計而非操作規範 |

---

## 相關資源

- `tests/unit/background/background-local-dict.test.js` L499-500 — 現有警示註解（W1-005.3 手動還原後加入）
- `scripts/remove-emoji.js` — 動機案例工具（全量替換，無排除機制，`walk()` 函式遞歸所有子目錄）
- `docs/work-logs/v0/v0.19/v0.19.1/tickets/0.19.1-W1-005.3.md` — 觸發案例（誤傷過程與手動還原記錄）
- `docs/work-logs/v0/v0.19/v0.19.1/tickets/0.19.1-W1-007.md` — ANA 固化來源（三流程教訓 retrospective）
- `.claude/error-patterns/process-compliance/PC-165-false-positive-fix-chain.md` — 上位 pattern（工具誤傷後 tests 仍通過的 false positive 修復鏈機制）
- `.claude/error-patterns/process-compliance/PC-158-mint-format-specialist-emoji-in-visual-markers.md` — 弱相關（emoji 合規，不同觸發層）

---

**Last Updated**: 2026-06-04
**Version**: 1.0.0 — 初始建立（W1-007 ANA 教訓 3 固化；W1-005.3 動機案例）
