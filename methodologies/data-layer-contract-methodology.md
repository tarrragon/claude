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

---

## Reference

- `.claude/skills/doc/templates/data-contract-template.md` — 資料契約文件模板（承載第 2 層內容的結構定義）
- `.claude/methodologies/structured-content-generation-methodology.md` — CLI 化三條件判準（第 3 節引用來源）
- `.claude/methodologies/domain-bundle-mapping-methodology.md` — domain 層 bundle 邊界判準（與資料層契約互補：domain-map 定義層與依賴方向，資料層契約定義該層資料的規格細節）
- `docs/proposals/PROP-002-data-layer-specification-framework.md` — 本方法論的來源提案（含替代方案否決理由、疏漏查核記錄）

---

**Last Updated**: 2026-07-25
**Version**: 1.0.0 — 初始建立（0.2.0-W2-002，source: PROP-002 In Scope 2）
