# 資料層規格化方法論（Data Layer Contract）

**何時讀**：規劃資料層規格保護（schema 設計、資料契約文件、migration 決策）時；判斷契約文件或 migration 治理是否需要時；SQLite/sqflite 專案需補 CHECK 約束時。**解決什麼**：UI/UX 行為有 UC + E2E 測試保護，domain 邏輯有 spec + unit test 保護，但資料層（SQL schema 設計、欄位語意、約束決策）常缺乏對等的規格化機制，導致契約散落多處、演進無策略、測試對應不可審計。

> **核心理念**：業界常見的 migration / seed 腳本記錄「做了什麼變更」，不是「為何這樣設計、不變式是什麼」。資料層規格化的目標是把「設計意圖」與「執行腳本」分離，讓意圖可被審計。
> **n=1 標註**：本方法論的判準（尤其兩正交旗標邊界）基於單一驗證專案（flutter_balance）建立，第二個驗證專案校準前，判準邊界視為暫定。

---

## 1. 三層保護模型

資料層保護分三層，由確定性程度高到低排列：

| 層級 | 角色 | 承載內容 |
|------|------|---------|
| 第 1 層：schema 約束即規格 | DDL 本身 | CHECK / UNIQUE / FK / NOT NULL 應如 acceptance criteria 般被設計，不是寫程式時順手加的 |
| 第 2 層：資料契約文件 | 承載 DDL 表達不了的設計意圖 | 欄位語意、狀態責任分層、不變式陳述、交易邊界、錯誤語意契約、恢復模型（見 doc skill `data-contract-template.md`） |
| 第 3 層：契約對應整合測試 | 行為驗證 | 每條契約條目對應至少一個測試，覆蓋完整性可審計（見第 5 節） |

**判準：能寫成 CHECK 的不寫成文件。** DDL 是可執行、不會與程式碼漂移的規格；文件只承載 DDL 無法表達的意圖（為何、跨欄語意、遷移後仍成立的邏輯）。

**Why**：schema 是唯一與程式碼同步執行的規格層——CHECK 違反時資料庫直接拒絕寫入，不需要人記得檢查文件。文件會腐爛（改 schema 忘改文件），DDL 不會。
**Consequence**：把可寫成 CHECK 的不變式留在文件（例如「負債記正數」若能表為 `CHECK(type != 'liability' OR amount >= 0)` 卻只寫在 README），該不變式會在無人察覺下被繞過（測試漏跑、直接寫 DB 的腳本、未來重構遺漏檢查點）。
**Action**：每條候選不變式先問「能否表為 DDL 約束（CHECK/UNIQUE/FK/NOT NULL）」，能則寫成約束，文件只記錄「為何選這個約束、保證層歸屬理由」；不能才展開為文件條目。

---

## 2. 適用判準：兩個正交二元旗標

資料層規格化投入程度依兩個獨立旗標判定，不用線性分級（L1/L2/L3）。

| 旗標 | 判準：要 | 判準：不要 |
|------|---------|-----------|
| 契約文件 | 多人或 AI 代理協作、有交接需求 | 單人專案、無交接對象 |
| migration 治理 | 已上線有存量資料、schema 需演進 | 全新專案或 schema 已凍結不再變 |

**兩旗標皆否時**：僅維持 schema 約束 + DDL 註解即為合法終態——這不是「偷懶」，是有依據的豁免，讓小專案不需要為了「看起來完整」而製造不需要的文件。

**為何不用 L1/L2/L3 線性分級**（取代理由）：

1. **撞名**：`component-library-bidirectional-constraint-methodology.md` 已用 L1/L2/L3 表示承載層級記號，資料層若沿用同記號但語意不同，會造成跨方法論混淆。
2. **正交邊界案例無位置**：「單人小專案但已上線且有存量資料」這類情境在線性軸上無法歸類（契約文件旗標=否，但 migration 治理旗標=要）。兩正交旗標讓此類邊界案例可正確分類，線性分級做不到。

**判準基於 n=1 樣本（本專案）建立，邊界待第二個驗證專案校準**——尤其「多人或 AI 代理協作」與「單人專案」的邊界、「schema 需演進」的判定時機，皆待更多樣本驗證。

---

## 2.1 dormant 表豁免判準

**dormant 表** = schema 已建立、repository 寫入方法已實作，但無 production 觸達路徑（DI 未接線、或呼叫鏈終止於死路）的表。對 dormant 表撰寫第 2 層契約文件是負債：文件描述的是「寫入路徑的行為事實」，無 production 寫入路徑即無行為事實可承載，寫出的文件只能複述 DDL，並在首次真實接線時全文重審。本節定義何時可合法跳過契約撰寫（豁免），以及豁免必須滿足的條件。

### 豁免前置：三軸交叉驗證

**Why**：僅憑程式碼註解（「規劃中」「未來擴充」）或表面 grep 一次命中判定 dormant，會誤判仍有觸達路徑的表為 dormant（漏看間接呼叫鏈），或誤判已死的表為活躍（誤信過期註解）。兩種誤判都會造成契約文件缺口不被發現。
**Consequence**：未經三軸交叉驗證即豁免，會使真正需要契約保護的表被跳過，且此類遺漏不會被後續開發自然發現（dormant 表不觸發執行期錯誤）。
**Action**：豁免前必須依序完成三軸驗證，三軸皆須有可重放指令與命中結果佐證：

| 軸 | 驗證內容 | 完成判準 |
|---|---|---|
| 表名軸 | 表名關鍵字反查全部程式碼，逐一判定每個命中是「寫入」還是「型別引用/stub」 | 列出全部命中檔案並逐檔標註分類，不可只看命中數量 |
| 呼叫者軸 | repository 該表寫入方法（insert/update/delete）名稱反查全部呼叫者 | 每個寫入方法的呼叫者清單完整列出，含測試替身需標註排除 |
| 消費鏈軸 | 對每個呼叫者，逐層上溯實例化點與 DI/provider 消費者，直至 UI 進入點或死路 | 每條鏈的終點須明確判定為「觸達 UI」或「死路」，死路須附死路成因（如 provider 無 import 者、初始化流程從未呼叫） |

三軸缺一即不構成豁免依據——例如僅表名軸顯示低使用頻率，不足以判定 dormant，仍需消費鏈軸證明死路。

### 指令證據記錄

三軸驗證的每一步驟必須留下可重放指令與原始命中結果，寫入 Ticket 的重現實驗章節（依專案 Ticket 格式，可為「重現實驗結果」等章節），禁止以「已確認無使用」等結論轉述取代指令記錄。**Why**：口頭結論無法被後續開發者或另一 agent 重新驗證，指令記錄則可在懷疑豁免過期時直接重跑核對。

指令證據範例（依實際專案調整表名/方法名，非固定命令）：

```
grep -rln "<表名>" <程式碼根目錄> --include="*.<副檔名>"          # 表名軸
grep -rn "<insert方法>|<update方法>|<delete方法>" <程式碼根目錄>   # 呼叫者軸
grep -rn "<providerA>|<ServiceLocatorX>" <入口檔案>                # 消費鏈軸：入口是否觸發
```

### 重啟條件必須綁 ticket（decision-trigger-binding 狀態 b）

豁免不是終態，必須依 `.claude/rules/core/decision-trigger-binding.md` 規則 1 聲明何時失效，禁止「未來再評估」式的無 trigger 豁免。

| 情境 | 綁定方式 |
|---|---|
| 已有 pending ticket 涉及該表接線 | 直接綁定該 ticket ID，豁免記錄標註 `blockedBy` 或引用該 ID |
| 尚無任何 ticket（接線需求尚未發生） | 綁定「觸發事件描述」：聲明未來若有任何 ticket 使該表出現 production 寫入路徑，該 ticket acceptance 必須含「spawn 契約文件 ticket」動作；同時附機械可驗證的偵測條件（見下）作為判定重啟時機的客觀依據，取代主觀判斷 |

**機械偵測條件示例**：豁免記錄應附至少一則可重跑、結果非 0/1 即可判定重啟是否成立的指令，例如：

```
grep -rln "<provider或DI接線點>" <程式碼根目錄> --include="*.<副檔名>" | wc -l
# 由 0 變 >0 即重啟條件成立
```

機械偵測條件的價值在於把「是否該重啟」從記憶轉為可執行檢查——任何人（含未來 agent）可直接重跑指令得出是/否結論，不需回頭理解豁免時的完整脈絡。

---

## 3. CLI 化升級判準條款

契約文件的撰寫與更新目前不 CLI 化（人工撰寫 + hook 事後檢查）。是否升級為 CLI 子命令，依 `.claude/methodologies/structured-content-generation-methodology.md` 三條件判定：

| 條件 | 契約文件現況 |
|------|-------------|
| (1) 有確定性 schema | 有（模板固定章節結構） |
| (2) 多個寫入者 | 視專案而定 |
| (3) 格式錯誤有歷史 | 尚無（首次實例化） |

**現況**：僅滿足條件 (1)，不滿足 (2)(3)，故**不 CLI 化**（見 structured-content-generation 適用判準：三條件全滿足才應 CLI 化）。

**Action**：未來專案若同時命中三條件（多寫入者 + 已觀察格式錯誤），依 `structured-content-generation-methodology.md` 的模式 A（CLI 子命令）或模式 B（模板函式）自建提案，不在本方法論展開 CLI 設計細節（避免無實例化經驗的過度設計）。

---

## 4. sqflite migration 技術提示

SQLite/sqflite 專案在「補 CHECK 約束」決策上有三項本質限制，決策前必須知悉：

| 限制 | 內容 | 影響 |
|------|------|------|
| ALTER TABLE 不支援加 CHECK | SQLite 的 `ALTER TABLE` 無法對既有表新增 CHECK 約束 | 唯一路徑是官方 12 步驟表重建流程（建新表 → 複製資料 → 刪舊表 → 改名 → 重建索引/觸發器） |
| 表重建須暫停 FK 檢查 | 表重建過程中，`PRAGMA foreign_keys = ON` 會在中繼狀態擋下操作 | migration 執行前須 `PRAGMA foreign_keys = OFF`，完成後才恢復 `ON` |
| CHECK 違反無型別化例外 | sqflite 未提供 `isCheckConstraintError()` 等型別化錯誤判斷 API | CHECK 只能定位為 **defense-in-depth**（最後防線），應用層驗證仍是主要、可讀錯誤來源的手段，不可倒置依賴順序 |

**Why**：這三項限制共同指向「補 CHECK 的成本不只是加一行 DDL」——它必然牽動 migration 路徑設計與錯誤處理策略，不能孤立決策。
**Consequence**：忽略表重建路徑而直接假設「加 CHECK 只影響新裝置」，會造成新舊裝置 schema 隱性分裂（舊裝置永遠停在 `onCreate` 產生的舊 schema，除非有 `onUpgrade` 路徑）。
**Action**：任一條目決定補 CHECK → `onUpgrade` 表重建路徑與對應 migration 測試自動成為必要條件（不是可選項）；migration 測試必須證明「舊 schema DB 開啟後升級成功且既有資料通過新約束」，僅驗證全新 `onCreate` 路徑不算完成。

---

## 5. migration 治理流程判準（旗標=要時適用）

當第 2 節「migration 治理」旗標判定為「要」（已上線有存量資料、schema 需演進），適用以下流程判準。**本節僅引用概念，不複寫内容**——完整操作方式見用戶提供的資料庫設計文章集（`~/project/blog/content/backend/01-database/` 1.6 migration playbook、1.7 rollout evidence）。

| 判準 | 概念來源 | 一句話摘要 |
|------|---------|-----------|
| 狀態契約先行 | 文章集 1.6 | mapping table 等狀態契約必須先進 artifact，才能讓後續 validation 可判讀 |
| 分段可驗證 | 文章集 1.6 | migration 拆 expand / backfill / cutover / contract 四階段，每階段有明確完成訊號與停止條件 |
| rollback 隨階段遞減 | 文章集 1.7 | expand 階段可完全回退；contract 階段之後只剩資料修復手段，不再有結構回退 |
| validation 與 mapping 同源 | 文章集 1.6 | validation query 與狀態 mapping 共用同一語意來源，避免驗證邏輯與遷移邏輯各自表述而漂移 |

**單人小專案（旗標=否）不需本節**——evidence package / release gate 等完整流程對單人 app 過重，屬正當豁免範圍。

---

## 6. 契約 ↔ 測試對應

每條資料契約條目（第 2 層文件的每個不變式/欄位語意/邊界行為）必須對應至少一個測試，對應關係記錄於專案 `docs/traceability.yaml` 的第三軸 `data_contract_tests`（與既有 `mappings`、`domain_bundle_tests` 兩軸同檔，可交叉審計）。

**Why**：契約文件若不對應測試，只是「宣稱的規格」——無法驗證是否真的被執行檢查。第三軸讓「契約條目是否有測試覆蓋」可被 CI 或人工掃描直接查詢，而非散落在測試檔案的 group 命名裡（例如原本測試僅對應 AC 編號，看不出對應哪條資料契約）。
**Consequence**：缺此軸時，契約條目與測試的對應關係只存在維護者記憶中，新成員或 AI 代理無法審計覆蓋完整性，契約腐爛（改約束忘改測試）不會被自動發現。
**Action**：每次新增或修改契約條目時，同一 commit 內同步更新 `data_contract_tests` 軸的對應項；規劃波（version-bootstrap）在 Step 2.5 domain map 產出後、Step 5 測試設計前，檢查此軸是否已初始化。

### 6.1 條目 schema

`data_contract_tests` 每條條目採固定欄位，避免逐專案自創格式造成跨專案不可比對：

| 欄位 | 型別 | 必要性 | 說明 |
|------|------|--------|------|
| contract_ref | string | 必要 | 契約條目的唯一識別碼與來源文件（如 `INV-01` + 對應契約文件路徑），可拆為 `contract_id` + `spec` 兩欄實作 |
| description | string | 必要 | 不變式/欄位語意的一句話陳述，需可獨立閱讀，不需回查契約文件才能理解 |
| status | enum | 必要 | `covered`（有測試直接斷言）/ `partial`（僅部分承載層有測試）/ `gap`（無對應測試）三值之一 |
| tests | list[string] | 必要（可為空 list） | 「檔案路徑::group 或 test 名稱」格式引用，每筆引用須經 grep 實查，不可用文件轉述為據 |
| no_test_needed | bool | 選填 | `true` 表示此條目屬第 6.3 節合法分類，無需測試；出現時 `status` 免填，`tests` 固定為空 list |
| reason | string | `no_test_needed: true` 時必填 | 附程式碼座標佐證（檔案:行號），不可僅憑陳述無實證 |

`status` 為 `partial` 或 `gap` 時，建議額外附 `note` 欄說明缺口具體內容（如「僅驗證欄位映射，未驗證唯一性」），供後續補測試時直接定位範圍。

### 6.2 假覆蓋排除判準

判定 `status: covered` 前，須排除以下兩類假覆蓋——測試存在但未真正驗證該不變式：

| 假覆蓋類型 | 判準 | Why |
|-----------|------|-----|
| Mock 層測試不計入 DB 約束覆蓋 | 測試以 Mock/Fake repository 驗證的行為，只證明「服務層邏輯正確呼叫」，不證明 DB 層約束（UNIQUE/FK/CHECK）在真實寫入時生效 | Mock 層繞過真實資料庫，DB 約束是否真的擋下違反寫入完全未被測試觸及 |
| 僅斷言存在性不計入唯一性覆蓋 | 斷言「欄位有值」或「欄位映射正確」不等於斷言「唯一性成立」（如「同一分類至多一筆」） | 存在性斷言與唯一性斷言驗證的是不同陳述，測試通過不代表唯一性不變式被檢查 |

**豁免**：若不變式定義本身即為「服務層守門邏輯」（非 DB 層約束），Mock 測試可計入覆蓋——例如「建立前檢查是否已有活躍記錄」屬應用層守門，用 Mock repository 驗證守門邏輯正確觸發即成立，因守門本身就是該不變式的承載層，不需要繞過 Mock 驗證 DB。

**Action**：判定 `covered` 前先問「此測試斷言的對象，是否就是不變式陳述的對象本身？」若測試斷言的是替代物（Mock 呼叫記錄、部分欄位存在）而非不變式陳述本身（DB 拒絕違反寫入、唯一性恆成立），應判為 `gap` 或 `partial` 並在 `note` 註明。

### 6.3 no_test_needed 合法分類

`no_test_needed: true` 僅限以下兩類，且每筆必須附 `reason` 佐證，不可作為「懶得測」的出口：

| 分類 | 判準 | reason 最低要求 |
|------|------|-----------------|
| 型別系統承載 | 欄位型別本身即排除違反狀態成立的可能（如 non-nullable + required 建構子使 NULL 不可達） | 附程式碼座標（檔案:行號）證明型別約束確實存在 |
| 非可程式化驗證 | 不變式描述人工判斷或跨系統協議，無法表達為自動化斷言 | 說明為何此不變式無法被程式化檢查（而非「暫時沒空寫」） |

**判定流程**：標記前先問「若移除此設計約束（型別限制/建構子必要性），測試是否有機會偵測到違反？」——若移除約束後仍無法被任何合理測試偵測到（例如純語意層面的人工協議），才屬合法 `no_test_needed`；若移除約束後可被測試偵測但目前尚未寫測試，應判為 `gap`，不可歸入 `no_test_needed`。

---

## 檢查清單

規劃資料層規格化時確認：

- [ ] 候選不變式已逐條檢查「能否寫成 DDL CHECK」，能則優先寫約束不寫文件
- [ ] 兩正交旗標（契約文件 / migration 治理）已各自判定並記錄理由，非套用線性分級
- [ ] 兩旗標皆否時，已確認「僅 schema 約束 + DDL 註解」為合法終態，未強行補文件
- [ ] 契約文件撰寫尚未 CLI 化前，已依 structured-content-generation 三條件確認暫不需要
- [ ] 若決定補 CHECK，已規劃 `onUpgrade` 12 步表重建路徑 + `PRAGMA foreign_keys OFF/ON` + migration 測試（舊 schema 升級成功路徑，非僅 onCreate）
- [ ] migration 治理旗標=要 時，已確認狀態契約（mapping table）先行、分段可驗證、rollback 隨階段遞減三項判準
- [ ] 每條契約條目已對應 `traceability.yaml` 第三軸 `data_contract_tests`，覆蓋缺口已盤點
- [ ] 判定表為 dormant 前，三軸交叉驗證（表名/呼叫者/消費鏈）已完成且指令證據已記錄，重啟條件已綁 ticket 或機械偵測條件
- [ ] `data_contract_tests` 條目已排除假覆蓋（Mock 層測試不計 DB 約束覆蓋、存在性斷言不計唯一性覆蓋），`no_test_needed` 條目均附 `reason` 佐證

---

## Reference

- `.claude/skills/doc/templates/data-contract-template.md` — 資料契約文件模板（承載第 2 層內容的結構定義）
- `.claude/methodologies/structured-content-generation-methodology.md` — CLI 化三條件判準（第 3 節引用來源）
- `.claude/methodologies/domain-bundle-mapping-methodology.md` — domain 層 bundle 邊界判準（與資料層契約互補：domain-map 定義層與依賴方向，資料層契約定義該層資料的規格細節）
- `docs/proposals/PROP-002-data-layer-specification-framework.md` — 本方法論的來源提案（含替代方案否決理由、疏漏查核記錄）
- `.claude/rules/core/decision-trigger-binding.md` — 決策延後必須綁 trigger（第 2.1 節重啟條件引用來源）

---

**Last Updated**: 2026-07-26
**Version**: 1.1.0 — 新增 2.1 節「dormant 表豁免判準」（三軸交叉驗證 + 指令證據記錄 + 重啟條件綁 ticket + 機械偵測條件）；擴充第 6 節為 6.1 條目 schema、6.2 假覆蓋排除判準、6.3 no_test_needed 合法分類（0.2.1-W1-002，source: book_overview_app 0.38.1-W10-004/W10-005 臨場設計成文，去專案化）
**Version**: 1.0.0 — 初始建立（0.2.0-W2-002，source: PROP-002 In Scope 2）
