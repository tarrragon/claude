# Ticket Body Schema（type-aware）

本文件定義不同 Ticket type 在 body 章節的**必填 / 選填 / 免填**對照，作為 PM 派發、代理人填寫、Hook 驗證的唯一依據。

> **來源**：W17-016.1 盤點結論（樣本 ANA × 4 + IMP × 1；DOC 樣本不足，現以保守建議落地）。完整樣本統計見該 ticket Solution 章節。
> **落地時機**：W17-016.2 寫入 template + SKILL.md；W17-016.3 上 Hook 驗證；3 個月後若完整率 < 50% 重啟盤點（樣本 40+）。

---

## Schema 對照表

| Section | ANA | IMP | DOC |
|---------|-----|-----|-----|
| Task Summary | 必填 | 必填 | 必填 |
| Problem Analysis | 必填 | 選填 | 選填 |
| 重現實驗結果（三子節） | 必填（PC-063） | 免填 | 免填 |
| Solution | 必填 | 選填 | 免填 |
| Test Results | 選填（若有實驗） | 必填 | 免填 |
| Completion Info | 必填 | 必填 | 必填（附變更摘要） |

**狀態定義**：

| 狀態 | 語義 | 填寫要求 |
|------|------|---------|
| 必填 | 章節存在且內容非 placeholder | claim/complete 時 Hook 應驗證 |
| 選填 | 章節存在，內容可為 placeholder 或省略 | 有助於後人查閱時填寫 |
| 免填 | 章節可省略或保留空結構 | 不強制檢查，template 可省 |

---

## 各 type 重點說明

### ANA（Analysis）

**核心價值**：根因 / WRAP / ROI 表 / 實驗結果的持久參考價值。

- `Problem Analysis` + `重現實驗結果` + `Solution` 為三大必填，構成「問題→實驗→結論」完整鏈路。
- `Test Results` 僅在有實驗輸出時填寫；樣本顯示 ANA 普遍無獨立測試輸出（4/4 missing），故列選填。

#### Solution 章節：Spawn 落地確認（W17-167 強制）

ANA Solution 章節若含 IMP/DOC/ANA spawn 規劃表格，必須在 complete 前確認以下子節（被 acceptance-gate-hook Step 2.5.2 自動偵測）：

```markdown
### Spawn 落地確認

- [ ] 所有規劃項目已建 ticket（`spawned_tickets` 或 `children` 已記錄對應 ID）
- [ ] 或在本章節顯性標註「無需建 ticket：[具體理由]」
```

**Why**：acceptance 勾選「產出 spawned 清單」只檢文字產出，不檢 ticket 是否實際建立；Solution 寫了表格但未建 ticket = 無 trigger 延後決策（PC-093 模式）。

**Consequence**：缺此 checklist，分析代理人 complete 時 frontmatter 為空也能放行，spawn 規劃靜默丟失（W17-167 元層級反例已證明）。

**Action**：

| 情境 | 填寫方式 |
|------|---------|
| 全部已建 ticket | 勾選第一項，列出對應 ticket ID 清單 |
| 部分未建 | complete 前先補建（PM 接手 ticket create 職責） |
| 評估後不需建 | 勾選第二項，標註「無需建 ticket：[理由]」 |

**Spawn 規劃表建議格式**（W1-004 擴充）：

```markdown
| 項目 | 形態 | 優先級 | Source FR | 說明 |
|------|------|--------|-----------|------|
| 骨架實作 | IMP | P0 | FR-01, FR-06 | 六個公開 API + Timestamp |
| Buffer+Flush | IMP | P0 | FR-02 | 攢批送出 |
```

`Source FR` 欄追溯每個 spawn 項目對應的 spec FR，使覆蓋盲區在拆分階段即可識別。無 spec 來源時可省略此欄。

**交叉引用**：

- 規則層：`.claude/rules/core/quality-baseline.md` 規則 5「ANA Solution 內 spawn 規劃」
- Lifecycle 層：`.claude/pm-rules/ticket-lifecycle.md`「ANA 衍生 Ticket 溯源驗證」Step 0（FR↔Ticket 覆蓋矩陣）
- Lifecycle 層：`.claude/pm-rules/ticket-lifecycle.md`「ANA Solution Spawn 規劃落地（強制）」
- 強制層：acceptance-gate-hook Step 2.5.2（W17-168 落地）

### Solution 章節：H3 子標題與表格使用慣例（W10-123 / W10-124 / W10-125 補強）

ANA / IMP Solution 章節支援 H3 子標題組織內容（如「### WRAP 完整分析」「### 修復策略」「### 變更總覽」），並支援 markdown 表格作為主要展示形式。Validator 層級規則：

| 元素 | 規則 |
|------|------|
| `### multi_view_status`（ANA 專用） | 不可作為 H3 子章節；必須以平鋪 `multi_view_status: <reviewed/skipped/n_a>` + `reason: ...` 寫入 Solution 文字內容（schema 來源：`.claude/config/ana-solution-schema.yaml`） |
| `### 自檢結果`（Layer 1） | 可作為 H3 子章節；hook 識別前綴匹配，可含中文括號補充說明（W10-124 修復後） |
| 表格 cell 中的 `N/A` / `TODO` / `TBD` | 屬合法「不適用 / 待辦 / 待定」標示，不視為 placeholder（W10-125 修復後；PC-138 / PC-144） |
| 章節整體只有 placeholder 字面（無表格） | 仍視為 placeholder，阻擋 complete |

**為何 multi_view_status 例外**：hook 用 regex 跨行掃描平鋪 YAML-like 結構，H3 子章節包裝會切斷掃描範圍（PC-117 / W17-111 設計）。

### Type-aware Quality Gate（W10-123 補強）

`ticket-quality-gate-hook` 對不同 ticket type 套用不同檢查：

| Type | c2 incomplete check | c3 ambiguous responsibility check |
|------|-------------------|--------------------------------|
| ANA | 跳過（不適用實作測試路徑要求） | 跳過（不適用 Layer 1-5 分層） |
| DOC | 跳過 | 跳過 |
| IMP | 觸發 | 觸發 |
| 缺 type frontmatter | 觸發（向後相容） | 觸發 |

配置位置：`.claude/hooks/quality_config.yaml` 的 `trigger_conditions.type_excludes`（預設 `["ANA", "DOC"]`）。

### IMP（Implementation）

**核心價值**：commit SHA + 測試輸出 + 實機驗證作為 proof。

- `Test Results` 必填：至少記錄執行指令與通過數（或 commit SHA）。
- `Problem Analysis` / `Solution` 選填：小型 IMP 以 frontmatter how/acceptance 已足；大型 IMP 建議補充決策理由。

#### 安裝指令 IMP 額外 acceptance（PC-159 防護）

IMP ticket 含安裝指令時，acceptance 必須補上 fresh shell 驗證條件，避免 PM / agent 既有環境通過驗證但 fresh shell 失敗的系統性風險（PC-159 / W3-050 codegraph placeholder package、W3-051 sys.path hack 案例）。

**觸發條件**（任一成立即須補強）：

- ticket `what` / `how` 含安裝動詞：`npm install` / `pip install` / `brew install` / `uv tool install` / `cargo install`
- ticket `where.files` 含 `docs/development-setup.md` / `docs/environment-recovery-guide.md` / 等價的環境安裝指南檔案

**必填 acceptance**（觸發後至少一項勾選）：

| # | 驗證條件 | 適用情境 |
|---|---------|---------|
| 1 | 安裝指令在 fresh shell（新 terminal、無 `.bashrc` / `.zshrc` 以外環境變數）執行通過 | 任何安裝指令均適用 |
| 2 | package name 為完整 scoped name（`@scope/pkg-name`）或完整 registry URL，無短名 placeholder squat 風險 | npm / PyPI 公開 registry |
| 3 | 附 package registry 驗證輸出（`npm info <pkg>` / `pip show <pkg>` / `cargo search <pkg>`） | 已知 squat 風險或內部 mirror |

表格三項為 OR 關係，任一勾選即滿足 PC-159 acceptance 閘門；多項並列僅為冗餘保護，無加分效果。

**Why**：規則 5（所有發現必須追蹤）+ PC-159 三層防護（規則層 / Hook 層 / 文件層）的 Acceptance Schema 層落地。Hook 層（W3-052.1 `install-guide-edit-reminder-hook`）僅提供 reminder，acceptance schema 層提供 complete-time 強制驗證閘門。

**Consequence**：未補強 acceptance 的 IMP 可在 PM / agent 既有環境通過 complete，但其他用戶 fresh shell 安裝即失敗（PC-159 重現模式：W3-050 codegraph placeholder package、W3-051 sys.path hack 在 uv tool install 後失效）；此時責任歸屬不清，需事後重新復現。

**Action**：IMP claim 後若觸發條件成立，依上方表格至少勾選一項並在 ticket Test Results 附驗證輸出；若三項皆不適用（如離線環境、自訂 registry），於 acceptance 增列豁免條件並明示理由（避免規則 1.5 無 trigger 延後）。

**參考**：

- `.claude/error-patterns/process-compliance/PC-159-install-command-not-verified-in-fresh-shell.md`
- 設計來源：`docs/work-logs/v0/v0.19/v0.19.0/tickets/0.19.0-W3-052.md` Solution 方案 (b)

#### src 字串輸出變更額外 acceptance（W1-005.2 / W1-040 防護）

IMP ticket 修改 `src/` 字串輸出字面時，acceptance 必須補上 `npm test`（或對應測試套件）驗證，不可只驗 `npm run build:dev`。

**觸發條件**（任一成立即須補強）：

- ticket `what` / `how` 含 log 前綴變更、錯誤訊息改寫、UI 文案替換等字串字面修改
- ticket `where.files` 含 `src/` 下任何輸出字串（`console.log` / `console.warn` / `console.error` 前綴、`throw new Error(...)` 訊息、UI label 等）的修改

**必填 acceptance**（觸發後必須勾選）：

| # | 驗證條件 | 說明 |
|---|---------|------|
| 1 | complete 時驗收：`npm test` exit 0，0 failed tests | 確認 tests/ 斷言期待值與 src 新字串字面一致 |

**Why**：`tests/` 斷言（`toHaveBeenCalledWith` / `toContain` / `toEqual`）與 `src/` 字串輸出同源。`npm run build:dev` 只驗編譯可通過，不驗斷言期待值是否與新字串一致。修改 src 字面後 tests/ 若未同步更新，兩者靜默不一致，build 綠燈掩蓋隱性回歸。

**Consequence**：未補強的 IMP 可通過 build 驗收，但 tests/ 斷言期待值仍含舊字串字面，進入 in_progress 的其他 ticket 執行 `npm test` 時爆發——回溯根因成本遠高於修改時同步驗證（W1-005.2 → W1-005.3 案例：12 檔 48+ 處斷言需補修）。

**Action**：IMP claim 後若觸發條件成立，在 acceptance 補列「complete 時驗收：`npm test` exit 0」；若同時修改 tests/ 斷言（正確做法），在 Test Results 附執行輸出；若未修改 tests/ 但 `npm test` 仍通過，說明無斷言依賴（可加注）。

**觸發案例**：

- `docs/work-logs/v0/v0.19/v0.19.1/tickets/0.19.1-W1-005.2.md`（acceptance 僅驗 build:dev，致 12 檔 48+ 處隱性回歸，W1-005.3 補修）

**交叉引用**：

- `.claude/rules/core/test-assertion-design-rules.md`「延伸路由：src 字串輸出變更 acceptance 設計」章節

#### 含 UI 的 IMP 額外 acceptance：集中化（1.2.0-W1-015 防護）

含 UI 產出的 IMP ticket，acceptance 必須補上集中化驗收條目。

**觸發條件**（任一成立即須補強）：

- ticket `what` / `how` 含新增/修改畫面、widget、樣式、user-facing 文字
- ticket `where.files` 含 UI 層檔案（screen / widget / theme / renderer 等）

**必填 acceptance**（觸發後必須勾選）：

| # | 驗證條件 | 說明 |
|---|---------|------|
| 1 | 本功能 user-facing 文字→i18n key、顏色→theme token、魔術數字→具名常數，無新增裸 `Color()` / 字面字串 / 字面尺寸 | grep 變更碼確認 |

**Why**：1.2.0-W1-015 根因——既有 hook（l10n-sync / style-guardian）對「應有設施缺席」失明，只在設施已存在時生效。升為 per-feature acceptance gate，不依賴 greenfield 是否 bootstrap。
**Consequence**：未補此維度的 UI IMP 可在無 i18n/theme 的專案通過驗收，硬編碼暢行至 1.0（v1.0 實證：app 21 文字 / 19 數字 / 18 顏色全程未攔）。
**Action**：IMP claim 後若觸發，acceptance 補列集中化條目；純後端/CLI（Go server log）依語言慣例可標註豁免理由。

**交叉引用**：

- `.claude/methodologies/acceptance-criteria-methodology.md`「強制驗收維度：集中化」章節

### DOC（Documentation）

**核心價值**：變更摘要 + 引用的檔案清單。

- `Completion Info` 必填，需附「變更摘要」（哪些文件 / 章節更新）。
- `Solution` / `Test Results` 免填（文件變更本身即為產出）。
- `Problem Analysis` 選填：若 DOC 起因於某缺陷或盤點結論，可記錄背景。

---

## Acceptance 欄位設計指引（L3-b 後）

### 語義基礎：Complete-Time Verification

ticket track claim 不再執行 AC verification（W3-046 L3-b 實作），所有驗收測試（包括 npm test）延遲到 complete 階段。Acceptance 欄位應以此為前提進行撰寫。

### 撰寫原則

| 原則 | 為何 | 示例 |
|------|------|------|
| 包含測試 acceptance → 明示驗收時機 | L3-b 後 claim 不跑測試，未明示時機讀者無法判定何時驗收 | `complete 時驗收：npm test 100% 通過` |
| 包含工作產出 acceptance → 明示產出清單 | 文件 / 規範類產出無「測試」概念，需有可數產出對應 | `3 個 .md 文件已更新（見 Solution 章節）` |
| 明示驗收範圍 → 避免假設全套件 | 全套件驗收與並行 claim 衝突（PC-078 根因） | `相關檔案測試 (src/utils/*.test.js) 通過` |
| 避免歧義標記 → 禁止「npm test」單獨出現 | 單獨出現的 `npm test` 無法區分 claim/complete 時機 | 改為「complete 時驗收 npm test exit 0」|

### 反模式與修正（單一權威源）

> 本表為全專案 acceptance 反模式的單一權威源；`.claude/pm-rules/ticket-lifecycle.md` 反向引用本表，避免雙處維護漂移（W3-057 整併）

| 反模式 | 問題 | 修正 |
|-------|------|------|
| `npm test 100% 通過` | 驗收時機不明（claim vs complete） | 改為「complete 時驗收：npm test 100% 通過」 |
| `npm test 不引入新失敗` | 同上 | 改為「complete 時驗收：npm test 不引入新失敗」 |
| `全套件測試通過` / `全套件測試無回歸` | 並行 claim 會衝突（PC-078 根因）+ 時機不明 | 改為「相關檔案測試（X 個檔案）通過」或「complete 時驗收 npm test 0 failed」 |
| `測試通過率 100%` | 過於抽象 + 驗收時機不明 | 改為「complete 時驗收：npm test exit 0 無 failed tests」 |
| `lint 0 warning` / `npm run lint 無問題` | 缺少具體指標（error vs warning） | 改為「complete 時驗收：npm run lint 0 errors / 0 warnings」 |
| 修改 src/ 字串字面只驗 `npm run build:dev` | build 不覆蓋 tests/ 斷言期待值一致性（W1-005.2 隱性回歸） | 改為「complete 時驗收：`npm test` exit 0」（IMP 修改 src/ 字串字面類必填） |

### 有效 Acceptance 範例

**IMP Ticket（功能實作）**：
```yaml
acceptance:
- '[x] 修復後檔案無 linter error'
- '[x] complete 時驗收：npm test --testPathPattern=modified-file 全通過'
- '[x] 相關功能測試（5 個 test.js）無回歸'
```

**DOC Ticket（文件更新）**：
```yaml
acceptance:
- '[x] 3 個 markdown 檔案已更新（見 Solution 變更摘要）'
- '[x] 交叉連結驗證（所有引用路徑有效）'
- '[x] 內容一致性檢查（相同概念同義表述）'
```

**ANA Ticket（分析任務）**：
```yaml
acceptance:
- '[x] 三層方案定位與優先序已明確'
- '[x] 包含至少 3 個歷史案例驗證'
- '[x] Spawn 規劃表已落地為實際 ticket'
```

---

## 與既有規則的關係

| 規則 | 關係 |
|------|------|
| `.claude/pm-rules/ticket-lifecycle.md` | 本 schema 是 lifecycle 各階段填寫粒度的細化 |
| `.claude/error-patterns/process-compliance/PC-063` | ANA「重現實驗結果」強制章節來源，schema 保留此強制 |
| `.claude/rules/core/quality-baseline.md` 規則 5 | 本 schema 不改追蹤原則，只規範 body 顆粒度 |

---

## 歷史豁免

已完成（status=completed）的 ticket 不回頭補章節。schema 只對新建 + in_progress 的 ticket 生效。Hook 驗證（W17-016.3）應以 `status != completed` 為前置條件。

---

## 變更紀錄

| 版本 | 日期 | 變更 |
|------|------|------|
| 1.3.0 | 2026-06-04 | IMP 區塊新增「src 字串輸出變更額外 acceptance」段落；反模式表補充 build-only 驗收反模式（W1-005.2 / W1-040） |
| 1.2.0 | 2026-05-13 | 新增「Solution 章節：H3 子標題與表格使用慣例」+「Type-aware Quality Gate」兩段（W10-123 / W10-124 / W10-125 規則收斂；W10-126 落地） |
| 1.1.0 | 2026-05-08 | ANA Solution 章節新增「Spawn 落地確認」子節 checklist（W17-167 L3 落地，配合 W17-168 hook + W17-169 quality-baseline / ticket-lifecycle 同步修訂） |
| 1.0.0 | 2026-04-20 | 初版（W17-016.2 落地 W17-016.1 盤點結論） |

**Last Updated**: 2026-06-04
**Version**: 1.3.0 — IMP 新增 src 字串輸出變更 acceptance 規則（必含 npm test，禁止只驗 build:dev）+ 反模式表補充（W1-005.2 / 0.19.1-W1-040）
