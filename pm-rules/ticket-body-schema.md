# Ticket Body Schema（type-aware）

本文件定義不同 Ticket type 在 body 章節的**必填 / 選填 / 免填**對照，作為 PM 派發、代理人填寫、Hook 驗證的唯一依據。

> **來源**：W17-016.1 盤點結論（樣本 ANA × 4 + IMP × 1；DOC 樣本不足，現以保守建議落地）。完整樣本統計見該 ticket Solution 章節。
> **落地時機**：W17-016.2 寫入 template + SKILL.md；W17-016.3 上 Hook 驗證；3 個月後若完整率 < 50% 重啟盤點（樣本 40+）。

---

## Schema 對照表

> **type 正典**：4 型 IMP / ADJ / ANA / DOC（SSOT：`ticket_system/constants.py` 的 `TICKET_TYPES`，CLI 以 argparse choices 強制）。TST / RES / INV 為歷史化石（讀取容忍、寫入拒絕）。ADJ 未定義專屬章節要求，Hook 驗證回退通用檢查。

| Section | ANA | IMP | DOC |
|---------|-----|-----|-----|
| Task Summary | 必填 | 必填 | 必填 |
| Problem Analysis | 必填 | 選填 | 選填 |
| 重現實驗結果（三子節） | 必填（PC-063） | 免填 | 免填 |
| Solution | 必填 | 選填 | 免填 |
| Test Results | 選填（若有實驗） | 必填 | 免填 |
| Context Bundle | 選填（auto-extracted，非人工填寫） | 選填（auto-extracted，非人工填寫） | 選填（auto-extracted，非人工填寫） |
| NeedsContext | 選填（僅資料缺口時填寫） | 選填（僅資料缺口時填寫） | 選填（僅資料缺口時填寫） |
| Exit Status | 選填（W17-010 協議，代理人自報） | 選填（W17-010 協議，代理人自報） | 選填（W17-010 協議，代理人自報） |
| Spawn Requests | 選填（發現應開新 ticket 議題時填寫） | 選填（發現應開新 ticket 議題時填寫） | 選填（發現應開新 ticket 議題時填寫） |
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

#### 重現實驗結果章節：負面範圍聲明要求（PC-BAL-037 強制）

`實驗發現` 子節除既有「已驗證事實 vs 未驗證假設」二分外，必須追加一行「本實驗不涵蓋」負面範圍聲明——逐條列出本次實驗**未量測**的失效模式。

**Why**：實驗結論的自然摘要傾向以「模式安全」的粒度被記憶（如「flock 寫入 600 輪無損」在轉述中放大為「flock 寫入已驗證安全」），但實驗本身只驗證特定失效模式（如「並行寫入互相覆蓋」）不發生；缺少負面範圍聲明時，後續引用者須自行重建實驗邊界，而重建這一步沒有任何流程強制（PC-BAL-037 根因 3）。

**Consequence**：實驗結論被引為設計背書時，引用者容易只核對「結論是否為真」與「實驗標的是否同一段機制」，「失效模式清單是否覆蓋本設計暴露的失效模式清單」這一問從未被問——PC-BAL-037 實際案例：並行寫入實驗（600 輪無損）被引用背書 in-place 寫入模式，實驗從未量測的 crash 中途半截檔案、無鎖讀端 race 兩條失效路徑，直到多視角審查才被發現。

**Action**：`實驗發現` 子節補一行「本實驗不涵蓋：[逐條列出未測的失效模式]」，需具體列出失效模式，禁止「其餘情況未測試」等籠統帶過。引用實驗結論作設計依據前的三問檢查清單見 `.claude/references/experiment-evidence-citation-rules.md`。

#### Solution 章節：Spawn 落地確認（W17-167 強制）

ANA Solution 章節若含 IMP/DOC/ANA spawn 規劃表格，必須在 complete 前確認以下子節（被 acceptance-gate-hook Step 2.5.2 自動偵測）：

```markdown
### Spawn 落地確認

- [ ] 所有規劃項目已建 ticket（`spawned_tickets` 或 `children` 已記錄對應 ID）
- [ ] 或已登記 spawn request 並 resolve 為終態（`processed` 附 ticket ID／`dismissed` 附理由）
- [ ] 或在本章節逐項標註「無需建 ticket：[具體理由]」（一則宣告扣抵一項）
```

**Why**：acceptance 勾選「產出 spawned 清單」只檢文字產出，不檢 ticket 是否實際建立；Solution 寫了表格但未建 ticket = 無 trigger 延後決策（PC-093 模式）。停在 `pending` 的 spawn request 屬同一模式，故不計為落地。

**Consequence**：缺此 checklist，分析代理人 complete 時 frontmatter 為空也能放行，spawn 規劃靜默丟失（W17-167 元層級反例已證明）。

**Action**：落地是**執行者**於 complete 前的義務——complete 後強制層已無執行時機，PM 事後驗收屬冗餘檢查而非唯一保證。

| 情境 | 填寫方式 |
|------|---------|
| 全部已建 ticket | 勾選第一項，列出對應 ticket ID 清單 |
| 部分未建 | complete 前由執行者自行補建（`ticket create --source-ticket <本票 ID>`，或 `--parent <本票 ID>` 建 children） |
| 成票與否需 PM 裁決 | 勾選第二項：先 `add-spawn-request`，complete 前再 `resolve-spawn-request` 標為終態 |
| 評估後不需建 | 勾選第三項，**逐項**標註「無需建 ticket：[理由]」 |
| 工具清單不含 Bash 而無法呼叫 CLI | 停手上報 NeedsContext 由 PM 改派；此情形應在派發階段即避免 |

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

#### Solution 章節：逐筆清單落地（PC-BAL-054 強制）

ANA Solution 的判定對象若同時滿足以下三條件，逐筆清單必須落地為獨立檔案，不得只留統計表與逐類判定。三條件為 AND——任一不成立即不強制，多數 ANA 票不觸發本節。

| 條件 | 判準 |
|------|------|
| 1. 判定對象可枚舉且量大 | 對象是一組具體項目（檔案、行號、ticket、skill 配對等），且集合大小超出可在 Solution 內文合理列舉的規模（經驗閾值：> 15 筆，與抽樣複驗慣例對齊） |
| 2. 至少一張下游票逐筆依賴 | 下游票的處置是「對集合中每一筆分別判斷/處置」，而非「對整批做同質處置」（後者不需要清單） |
| 3. 量測結果具時間敏感性 | 對象所在的語料庫會因其他並行工作變動，重新量測可能得到不同結果 |

**Why**：ANA 的 Solution schema 要求的是結論——統計表、逐類判定、方案比較。逐筆清單在票的產出物模型裡從未被視為需落地的產出物，執行者依 schema 字面完成撰寫時票確實完整，但完整的是判定，不是判定所本的資料。判定完整的外觀正是缺口不會被攔下的原因：Solution 若明顯缺結論，驗收會直接卡住；有統計表有分類時，沒有人會去問「這些數字是從哪份清單算出來的，那份清單在哪」。

**Consequence**：缺口在分析票 complete 時不會暴露，要等下游票真的需要那份清單才浮現，此時已跨過驗收關卡，補救成本轉嫁給下游執行者。條件 3 使補救本身再失效一層——語料庫在多次量測之間變動時，同一定義重跑會得到不同數字，下游執行者無從判斷落差來自自己算錯、量測目標真的變了、還是原始分析有誤。PC-BAL-054 實際案例：一張分析票的三張下游票分別被迫重新掃描、加 blockedBy 待清單重建、移除 acceptance 條目改以事後複驗表為 ground truth。

**Action**：三條件成立時，Solution 撰寫流程新增一步——把逐筆清單寫入獨立檔案，最低限度三欄（來源檔案、行號、分類結果），路徑 `docs/work-logs/v{version}/tickets/artifacts/{ticket-id}-<slug>.tsv`，並在 Solution 內文附上該路徑與筆數供下游直接引用。下游需程式化讀取用 `.tsv` / `.csv` / `.json`，下游是人工核對用 `.md` 表格。

acceptance 須寫成可獨立驗證的兩條，禁止只寫「已保留逐筆清單」——該句無法被驗收者客觀檢查通過與否，驗收者既不知道要去哪裡找，也無從判斷「保留」到什麼程度算數：

```markdown
- [ ] 逐筆清單已落地至 `<明確路徑>`，檔案存在且非空
- [ ] 清單筆數與 Solution 內文宣稱的統計數字一致
```

前者驗收者可直接 `test -f` 或 `wc -l` 核對，後者可直接比對數字，兩者皆不需重新量測。

**與 Spawn 落地確認的邊界**：該節管的是「規劃項目有沒有變成 ticket」，本節管的是「判定所本的資料有沒有留存」。同一張 ANA 可同時觸發兩節，兩者無替代關係——spawn 全數落地不代表逐筆清單已留存。

**交叉引用**：`.claude/error-patterns/process-compliance/PC-BAL-054-analysis-ticket-judgment-without-itemized-list.md`（三條件的推導與下游受阻實例）

### Solution 章節：H3 子標題與表格使用慣例（W10-123 / W10-124 / W10-125 補強）

ANA / IMP Solution 章節支援 H3 子標題組織內容（如「### WRAP 完整分析」「### 修復策略」「### 變更總覽」），並支援 markdown 表格作為主要展示形式。Validator 層級規則：

| 元素 | 規則 |
|------|------|
| `### multi_view_status`（ANA 專用） | 不可作為 H3 子章節；必須以平鋪 `multi_view_status: <reviewed/skipped/n_a>` + `reason: ...` 寫入 Solution 文字內容（schema 來源：`.claude/config/ana-solution-schema.yaml`） |
| `### 自檢結果`（Layer 1） | 可作為 H3 子章節；hook 識別前綴匹配，可含中文括號補充說明（W10-124 修復後） |
| 表格 cell 中的 `N/A` / `TODO` / `TBD` | 屬合法「不適用 / 待辦 / 待定」標示，不視為 placeholder（W10-125 修復後；PC-138 / PC-144） |
| 章節整體只有 placeholder 字面（無表格） | 仍視為 placeholder，阻擋 complete |

**為何 multi_view_status 例外**：hook 用 regex 跨行掃描平鋪 YAML-like 結構，H3 子章節包裝會切斷掃描範圍（PC-117 / W17-111 設計）。

### Type-aware Quality Gate

`ticket-quality-gate-hook.py` 已刪除。C1 God Ticket / C3 Ambiguous Responsibility
判準移植至 `.claude/hooks/acceptance_checkers/`；C2 Incomplete Ticket 判準沿用既有的
`execution_log_checker.py`（非移植新增）。c2 與 c3 承接者的豁免機制並不相同，需分開看：

| 判準 | 現行承接者 | ANA | DOC | IMP | 缺 type frontmatter |
|------|-----------|-----|-----|-----|---------------------|
| c2 incomplete（execution log 填寫） | `execution_log_checker.check_execution_log_filled` | 未跳過，改加嚴：額外檢查「重現實驗結果」章節非空殼 | **無 type-based 跳過邏輯**：DOC schema 範本固定含「（免填：...）」placeholder 文字，regex 不會剝除該文字，實務上恆非空而不阻擋——非程式碼顯式豁免 | 檢查 Solution / Test Results 至少一項非空 | 同 IMP（空字串不在任何豁免集合） |
| c3 ambiguous responsibility（domain 分散度） | `responsibility_scope_checker.check_file_scope_diversity` | 顯式豁免（`_EXEMPT_TYPES = {"ANA", "DOC"}`） | 顯式豁免（同左） | domain 數 > 2 即違規 | 未豁免，套用同 IMP 邏輯 |

配置位置：兩檢查器的閾值與豁免清單為模組內常數（`_DOMAIN_COUNT_THRESHOLD`、
`_EXEMPT_TYPES`），非外部設定檔（原 `quality_config.yaml` 已隨舊 hook 一併刪除）。

**注意**：c2 對 DOC 的「不阻擋」是範本文字的副作用，非程式碼顯式排除——若 DOC
ticket 的 Solution / Test Results 章節被清空（不含「免填」placeholder 文字），仍會
被 `execution_log_checker` 判定為未填寫並阻擋 complete。

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

**Why**：1.2.0-W1-015 根因——既有 hook（l10n-sync / dart-style-guardian）對「應有設施缺席」失明，只在設施已存在時生效。升為 per-feature acceptance gate，不依賴 greenfield 是否 bootstrap。
**Consequence**：未補此維度的 UI IMP 可在無 i18n/theme 的專案通過驗收，硬編碼暢行至 1.0（v1.0 實證：app 21 文字 / 19 數字 / 18 顏色全程未攔）。
**Action**：IMP claim 後若觸發，acceptance 補列集中化條目；純後端/CLI（Go server log）依語言慣例可標註豁免理由。

**交叉引用**：

- `.claude/methodologies/acceptance-criteria-methodology.md`「強制驗收維度：集中化」章節

#### 防護類 hook ticket 額外 acceptance（必含項）

IMP ticket 的 `where.files` 觸及 hooks 目錄時，須補齊下表四項，查核對象不一致：前三項（本 session 實地觸發確認、liveness 驗證方式、失敗語意 fail-open/fail-closed）之語意須寫入 acceptance；第四項（產生路徑盤點結果）之正本須寫入 `how.strategy`（缺則 Solution），不在 acceptance 重複宣告。

**強制層現況**：四項皆已進入 `.claude/hooks/acceptance_checkers/hook_protection_acceptance_checker.py` 硬擋範圍（`acceptance-gate-hook.py` 於 complete 前呼叫）——前三項為 acceptance 語意關鍵詞硬擋；第四項（產生路徑盤點結果）為 `how.strategy` 正本解析硬擋，機制細節見下方第 4 項說明的「強制層現況」段落。

> **與下方「防護類 ticket：威脅事件寫 acceptance，攔截點寫 how.strategy」節的關係**：兩節對同一張 hooks 防護票同時生效，觸發方式與強制層級不同——本節由 `where.files` 機械判定並硬擋，下方節由 ticket 目的語意判定且純自律。本節四項屬**驗收手段與覆蓋範圍宣告**（防護是否在跑、擋住幾條路徑），不受下方節的攔截點約束；下方節管的是**防護攔截點**（防護攔在哪裡、覆蓋幾條路徑）。兩者職責正交，皆須滿足。

**觸發條件**（任一成立即須補強）：

- ticket `where.files` 含 `.claude/hooks/` 下任何路徑（頂層本體與 `tests/`、`acceptance_checkers/` 等子目錄皆算）
- ticket `where.files` 含任一 skill 私有 `.claude/skills/<skill>/hooks/` 下任何路徑（同屬防護面，見「hook 檔案落地監控」改造票的雙不管地帶教訓——只顧頂層會漏掉 skill hooks）

**必填四項**（觸發後皆須補齊；前三項須在 acceptance 中提及，語意關鍵詞檢查非逐字比對；第四項查核對象非 acceptance，見下表第 4 項）：

| # | 項目 | 說明 | 合格填法範例 |
|---|------|------|-------------|
| 1 | 本 session 實地觸發確認 | 本次寫入的 hook 是否已於本 session 實地觸發並確認落檔；未能確認時如何因應 | 「已於本 session 實地觸發並確認 hook-logs 落檔，可執行位已排除」或「本 wave 該防護不生效，改以人工紀律承擔」（部署期政策，用戶裁示的合格填法） |
| 2 | liveness 驗證方式 | 如何確認 hook 確實被 runtime 載入並執行 | 「以 liveness 日誌比對確認 hook 已被觸發」「實測 `git stash` 觸發後檢查對應 hook-logs 有新增紀錄」 |
| 3 | 失敗語意 | 異常時 fail-open 或 fail-closed | 「異常時 fail-closed，回傳 exit 2」「異常時 fail-open，僅記錄不阻擋」 |
| 4 | 產生路徑盤點表**存在於 `how.strategy`** | 本防護要擋的壞狀態有幾條產生路徑、現行攔截點覆蓋幾條、未覆蓋者在哪。**寫在 `how.strategy` 的盤點表，不在 acceptance 重複宣告數字** | 見下方 Action 第一步的表格格式 |

> **第 4 項的檢查對象是正本，不是宣告**。盤點表寫在 `how.strategy`（見下方 Action 第一步），checker 直接解析該表並於 complete 時輸出「本票盤點 N 條、覆蓋 M 條、未覆蓋 K 條」。撰寫者**不需**在 acceptance 重複宣告這些數字。
>
> **Why 檢查正本而非宣告**：acceptance 的數字宣告是副本，正本在 `how.strategy`。對副本設閘門而正本不設，與本模式根因（acceptance 被要求承載不該由它承載的東西）同構；且宣告的價值繫於有人對照，而 IMP 的 Phase 4 消費者為 warning 級的關鍵字存在性檢查，讀者實質缺席。改由機器讀正本同時消解兩者，並移除兩處數字須一致的維護負擔。
>
> **作用是使缺口可見，非防止缺口**。撰寫者仍可只列一條路徑草率過關，但盤點表逐條可見、計數由機器輸出，審查者與後續接手者可據以追問。
>
> **強制層現況**：checker 已改為直接解析 `how.strategy`（缺則 `Solution`）的盤點表正本，不再檢查 acceptance 數字宣告。行為三分：表格缺席阻擋 complete 並提示格式範例；表格存在且解析成功則放行，`logger.info` 輸出「本票盤點 N 條、覆蓋 M 條、未覆蓋 K 條」；表格存在但解析失敗則 fail-open，僅 `logger.warning` 記錄不阻擋。

**Why（前三項）**：這三項是機器檢查不到、只能落在 ticket 上的面向——單元測試全綠、settings.json 已註冊、實機 dogfooding 通過三項訊號都無法證明 hook 在「本次寫入的當下 session」已生效。零效力有兩條各自成立的成因：缺可執行位使 runtime 無從啟動它（與 runtime 版本無關，恆成立）、session 啟動時一次快照 hook 命令集（版本相依，2026-08-13 觀測的 runtime 上成立、2026-08-18 觀測的上不成立，見 PC-BAL-033「機制更正」節）。第 1 項要求的是「本 session 實地觸發是否落檔」而非「屬哪個 session 世代」——前者在兩種載入模型下都是有效證據，後者只在快照模型成立時才有意義。規則文字層級的預防措施已證明無法單靠文件落實，故用戶裁示強制層須為 acceptance 條目加 hook 硬擋。

**Why（產生路徑盤點結果）**：前三項驗證的是「防護有沒有在跑」，不涵蓋「防護擋住幾條路徑」。一個確實在跑、失敗語意明確、liveness 可驗證的防護，仍可能只覆蓋壞狀態的其中一條產生路徑。此項要求把覆蓋範圍以可數形式寫下，使該面向脫離撰寫者的隱性假設。

**Consequence**：未補前三項的防護類 hook ticket，撰寫者與 PM 皆會誤信防護已生效——2026-08-13 一次事故實證：一個新註冊的 guard hook 自建立起以 100644（無可執行位）存在，runtime 無法啟動它，事故當下該守衛全期零效力，全期僅一筆手動 dogfooding 日誌，此後零筆。

**Action**：IMP claim 後若 `where.files` 觸及 hooks 目錄，acceptance 補列表列各項語意（合格填法見上表，不要求逐字比對，語意到位即可）。`acceptance-gate-hook.py` 於 complete 前以 `check_hook_protection_acceptance` 對**前三項**硬擋，缺任一項 exit 非零並指出缺哪項；產生路徑盤點結果項的硬擋見上方強制層現況。

**參考**：

- `.claude/hooks/acceptance_checkers/hook_protection_acceptance_checker.py`
- `.claude/error-patterns/process-compliance/PC-BAL-035-acceptance-wording-locks-interception-point.md`（「硬擋形態的判準」節）

### DOC（Documentation）

**核心價值**：變更摘要 + 引用的檔案清單。

- `Completion Info` 必填，需附「變更摘要」（哪些文件 / 章節更新）。
- `Solution` / `Test Results` 免填（文件變更本身即為產出）。
- `Problem Analysis` 選填：若 DOC 起因於某缺陷或盤點結論，可記錄背景。

---

## Acceptance 欄位設計指引（L3-b 後）

### 語義基礎：Complete-Time Verification

ticket track claim 不再執行 AC verification（W3-046 L3-b 實作），所有驗收測試（包括 npm test）延遲到 complete 階段。Acceptance 欄位應以此為前提進行撰寫。

### 防護類 ticket：威脅事件寫 acceptance，攔截點寫 how.strategy

防護類 ticket（目的為阻止某個壞狀態出現，而非交付某個功能）的 acceptance 描述**威脅事件或最終狀態**，攔截點決策（用哪個工具、攔在哪個時機）寫在 `how.strategy` 或 Solution。兩者分屬不同欄位，不是二選一。

| 欄位 | 承載 | 範例 |
|------|------|------|
| `acceptance` | 威脅事件不再發生 | 缺可執行位的 hook 檔案不得在任何路徑下進入生效狀態而不被偵測 |
| `how.strategy` / Solution | 選定的攔截點、產生路徑盤點表與覆蓋結論 | 於設定檔寫入時檢查目標檔案模式；盤點表見下 |

**判準**：把 acceptance 唸一遍，問「若實作把攔截點換到別處但威脅事件同樣被擋住，這條還算通過嗎？」答「不算」表示攔截點已被寫進 acceptance，須把它移到 `how.strategy`，acceptance 改寫為威脅事件。

**Action（順序不可調換）**：

1. **先**列產生路徑盤點表，寫入 `how.strategy` 或 Solution（欄位如下，一條路徑一列）
2. 再依盤點結論撰寫 acceptance，以「不得 / 不應存在 / 任何路徑下」措辭寫威脅事件；涵蓋不足時以「所有路徑」措辭表達，不預先裁定攔截點
3. 對「動作發生時檢查」型防護，另加一條 acceptance 要求驗證操作順序調換後仍有效

| 產生路徑 | 是否覆蓋 | 未覆蓋原因 |
|---------|---------|-----------|
| 經工具正常寫入 | 是 | — |
| 先寫註冊後建檔（順序調換） | 否 | 檢查時目標尚不存在，走 fail-open |
| 經 VCS 合併寫入 | 否 | 未經該工具路徑 |

**Why**：acceptance 是測試設計、覆核重跑、gate 勾選三層驗證的共用真值來源。攔截點一旦寫進 acceptance，就從「什麼狀態算通過」退化為「照這個做法做」，三層驗證此後共用同一份條文，其覆蓋缺口對整條驗證鏈不可見。步驟 1 必須先於步驟 2，理由見下方參考文件的「時序不可調換」段。

**Consequence**：實作滿足條文、測試全綠、覆核一致，威脅事件仍可由未涵蓋路徑重現，要到 Phase 4 審查或事故復發才暴露。

**邊界（兩個方向）**：

- 對**上方**「防護類 hook ticket 額外 acceptance」：本節**不豁免**該節必含項的要求。該節各項（本 session 實地觸發確認、liveness 驗證方式、失敗語意、產生路徑盤點結果）屬**驗收手段與覆蓋範圍宣告**，照填；其中產生路徑盤點結果項與本節 Action 的第一步（列產生路徑盤點表）同源，盤點表寫 `how.strategy`，acceptance 只宣告其結果數字；本節管的是**防護攔截點**。一張 hooks 防護票同時受兩節約束。
- 對**下方**「撰寫原則」：其他 acceptance 條目（測試通過、產出清單）仍照撰寫原則寫具體指令與時機。前者說「什麼狀態算安全」，後者說「怎麼確認做完了」。

**參考**：完整論述、三列反模式對照表與判準依據見 `.claude/methodologies/acceptance-criteria-methodology.md`「防護類驗收條件：威脅事件測試」節與 `.claude/error-patterns/process-compliance/PC-BAL-035-acceptance-wording-locks-interception-point.md`。

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

## Frontmatter protocol_version 契約

自 W5-005.4 起，新建票 frontmatter 自動 emit `protocol_version` 欄位（值取自 `constants.py` 的 `PROTOCOL_VERSION_CURRENT`，當前 `"2.0"`）。

| 契約 | 說明 |
|------|------|
| 凍結豁免 | 歷史 2285 票不回填 `protocol_version`（缺欄位視為 `"1.0"` 隱含預設） |
| Lazy-migration | 工具讀取票時以 `frontmatter.get("protocol_version", PROTOCOL_VERSION_DEFAULT)` 取值；不主動寫回舊票 |
| 升版觸發 | `PROTOCOL_VERSION_CURRENT` 遞增時，新票自動拿新值；舊票凍結不動 |
| 消費者契約 | Hook/CLI 消費 protocol_version 時以 `PROTOCOL_VERSIONS_SUPPORTED` 白名單判斷是否支援 |

---

## 變更紀錄

| 版本 | 日期 | 變更 |
|------|------|------|
| 1.8.0 | 2026-08-20 | 改寫「Type-aware Quality Gate」節：`ticket-quality-gate-hook.py` 已刪除，改以現行承接者（`execution_log_checker.py` / `responsibility_scope_checker.py`）重寫 c2/c3 表格；c2 對 DOC 的行為改正為「範本 placeholder 副作用，非顯式豁免」（原表格誤植為「跳過」），c3 對 ANA/DOC 維持顯式豁免 |
| 1.5.0 | 2026-08-17 | IMP 區塊新增「防護類 hook ticket 額外 acceptance（三項必含）」段落：where.files 觸及 hooks 目錄（含頂層與 skill hooks）時強制三項語意（session 生效策略/liveness 驗證方式/失敗語意），對應 hook 硬擋於 acceptance-gate 新增 checker |
| 1.4.0 | 2026-07-05 | 新增「Frontmatter protocol_version 契約」段落：emit 機制 + 凍結豁免 + lazy-migration 契約（W5-005.4） |
| 1.3.0 | 2026-06-04 | IMP 區塊新增「src 字串輸出變更額外 acceptance」段落；反模式表補充 build-only 驗收反模式（W1-005.2 / W1-040） |
| 1.2.0 | 2026-05-13 | 新增「Solution 章節：H3 子標題與表格使用慣例」+「Type-aware Quality Gate」兩段（W10-123 / W10-124 / W10-125 規則收斂；W10-126 落地） |
| 1.1.0 | 2026-05-08 | ANA Solution 章節新增「Spawn 落地確認」子節 checklist（W17-167 L3 落地，配合 W17-168 hook + W17-169 quality-baseline / ticket-lifecycle 同步修訂） |
| 1.0.0 | 2026-04-20 | 初版（W17-016.2 落地 W17-016.1 盤點結論） |

**Last Updated**: 2026-08-23
**Version**: 1.10.0 — ANA 章節新增第三個強制子節「Solution 章節：逐筆清單落地（PC-BAL-054 強制）」：三條件 AND 判準（可枚舉且量大 / 下游逐筆依賴 / 量測具時間敏感性）成立時逐筆清單須落地為獨立檔案，附可驗證的 acceptance 兩條寫法與「已保留逐筆清單」不可用的理由，並劃出與 Spawn 落地確認的邊界（前者管規劃是否變成 ticket，後者管判定所本資料是否留存，無替代關係）。體例沿用同章節既有兩個強制子節。與 1.9.0 改的是不同子節，無覆蓋。
**Version**: 1.9.0 — 「Solution 章節：Spawn 落地確認」對齊規則 5 與強制層：checklist 補第二項（登記 spawn request 並 resolve 為終態），第三項改為逐項宣告；Action 段明示落地是執行者於 complete 前的義務，「部分未建」列的責任人由「PM 接手 ticket create 職責」改為執行者自行補建（原寫法與強制層實際擋的對象不符——gate 在 complete 前擋的是執行者，PM 無介入時機）；補「工具清單不含 Bash」的停手上報列。
**Version**: 1.8.0 — 「Type-aware Quality Gate」節改寫：已刪除的 `ticket-quality-gate-hook.py` 換成現行承接者說明。逐一查證兩個現行 checker 原始碼後發現舊表格對 DOC 的 c2 描述失準——`execution_log_checker.py` 對 DOC 無 type-based 跳過邏輯，DOC 之所以實務上不被阻擋，是因 schema 範本固定內嵌「（免填：...）」文字未被剝除規則移除，屬範本副作用而非程式碼顯式豁免；c3（`responsibility_scope_checker.py`）則確有 `_EXEMPT_TYPES = {"ANA", "DOC"}` 顯式豁免，與舊表格一致。同步移除已不存在的 `quality_config.yaml` 配置位置引用，改為模組內常數說明。
**Version**: 1.7.2 — 補改名漏網：「防護類 hook ticket 額外 acceptance」節與「邊界（兩個方向）」段的四項散文列舉仍寫舊 label「既有 session 生效策略」，與同節表格第 1 列的現行 label 不一致；依表格改為「本 session 實地觸發確認」。讀者依散文寫出的 acceptance 會落在舊措辭上，而 checker 的關鍵詞清單刻意保留舊用詞故不會擋，此不一致無自曝管道。要求本身與硬擋行為未變。
**Version**: 1.7.1（原記為 1.7.0，與先落地的方案 F 條目撞號，依落地順序改號） — 依 PC-BAL-033 機制收窄同步（2026-08-18）：必含項第 1 項由「既有 session 生效策略」改名為「本 session 實地觸發確認」（收窄後需驗的是本 session 實地觸發是否落檔，非屬哪個 session 世代），合格填法同步改寫；「Why（前三項）」段的機制句由單一快照模型斷言改為兩條成因並列（缺可執行位恆成立、註冊快照版本相依），並說明第 1 項為何選在兩種載入模型下都有效的證據。要求本身、觸發條件與硬擋行為皆未變。
**Version**: 1.7.0 — 依 0.2.1-W3-527 完整 WRAP 裁示改採方案 F（機器讀正本）：第 4 項的檢查對象由 acceptance 的數字宣告改為 `how.strategy` 的盤點表正本，撰寫者不再需要在 acceptance 重複宣告數字；補 Why（副本 vs 正本、消費者缺席）與強制層現況（改動待 0.2.1-W3-533 落地，該票完成前 checker 仍檢查 acceptance 宣告）。
**Version**: 1.6.2 — 依第二輪 Layer 2 審查更新：「維度型檢查」術語隨 PC-BAL-035 判準軸更換為「對外部事實可證偽」；補實作限制（判定須用 regex 不可用 substring，實測 18.0% 誤過率）。
**Version**: 1.6.1 — 依 Layer 2 審查修正 v1.6.0 的三項失準：強制層宣稱與實作不符（產生路徑盤點結果尚未進入 checker，已補「強制層現況」段明示該項在 0.2.1-W3-525 落地前為自律層）；Why／Consequence 原僅支撐前三項卻以全節語氣陳述，已拆為「Why（前三項）」與「Why（產生路徑盤點結果）」；節標題與內文改以角色命名（「必含項」）取代數量命名，位置序數引用改語意錨點。
**Version**: 1.6.0 — 「防護類 hook ticket 額外 acceptance」新增「產生路徑盤點結果」項（須含可數的路徑數與覆蓋數）；補該項的形態要求說明（維度型檢查，刻意不檢查 acceptance 措辭形態因其屬可空洞滿足的形式型）與作用邊界（使缺口可見而非防止缺口）；與下方攔截點分工節的雙向邊界說明同步更新。
**Version**: 1.5.0 — 新增「防護類 ticket：威脅事件寫 acceptance，攔截點寫 how.strategy」節（欄位分工表 + 判準問句 + 三步 Action 含產生路徑盤點表欄位與範例 + 雙向邊界）；「防護類 hook ticket 額外 acceptance（三項必含）」節補與該新節的關係說明（兩節對同一張 hooks 票同時生效，前者機械判定並硬擋且屬驗收手段，後者語意判定純自律且管攔截點，職責正交）。完整論述路由至 acceptance-criteria-methodology 與 PC-BAL-035，本檔不存副本。
**Version**: 1.4.0 — 新增 protocol_version 契約段落（emit + 凍結豁免 + lazy-migration，W5-005.4）
