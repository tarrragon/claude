# Domain Bundle Mapping 方法論

**何時讀**：規劃波在 spec FR 填完後、測試設計前（version-bootstrap Step 2.5）要產出 domain map 時。**解決什麼**：只有 UC（使用者行為）與 spec（feature 分組）時，domain 切層沒有依據、退化為「哪個檔案太大就拆」；本方法論給「從 spec FR 反推 domain bundle 邊界」的判準——bundle 分類、依賴方向 DAG、層→測試對應。配合 doc skill `domain-map-template.md`（結構載體）與 version-bootstrap Step 2.5（流程觸發點）。

> **核心理念**：domain map 是**水平視角**（按業務知識切聚合邊界），正交於 UC（垂直的使用者行為劇本）與 spec 目錄分組（feature grouping）。本文的 aggregate / kernel / read-model 是**本框架切層用語**（kernel 指跨 read-model 共享的核心計算，非 DDD shared-kernel bounded context；read-model 指衍生計算 bundle，非 CQRS 讀模型），完整分類判準見 §2。

---

## 1. 從 FR 反推 bundle（三步）

| 步驟 | 動作 | 產出 |
|------|------|------|
| 1. 分層歸屬 | 逐一問每個 FR：系統**計算**什麼（domain）／使用者**看**什麼（presentation）／存取什麼外部資源（data）| FR → 層 初分 |
| 2. domain FR 聚類 | 把 domain 層 FR 按**業務概念**聚類（淨值、槓桿、流動性…），非按畫面 | 候選 read-model bundle |
| 3. 抽共享 kernel | 找被 2+ 個 candidate 消費的核心計算（估值、聚合），抽為獨立 kernel | aggregate / kernel / read-model 分層 |

**判準：按概念不按畫面**。同一概念被多畫面使用時，按畫面切會重複並使 domain 反向耦合 presentation（違反依賴方向）。畫面層級的聚合放 presentation。

**同一概念的可操作啟發式**（Step 2 聚類判準）：兩個 FR 共享同一 aggregate 欄位集、且輸出型別同族 → 同 bundle；否則分開。避免只憑「感覺同一概念」拿捏粒度。

**多 aggregate 延伸**（Step 2）：多 aggregate 時先識別**交易一致性邊界**——同一 transaction 內必須原子修改的實體集合 = 一個 aggregate。不同 aggregate 間用 by-id 參照，跨 aggregate 一致性透過 domain events 達成。

**command-side 延伸**（Step 3）：若有跨 aggregate 協調邏輯（某 FR 依賴 2+ aggregate 的資料或命令），判定為以下三類之一：無狀態協調 → domain service；事件驅動反應 → policy / event handler；有狀態長期協調 + 補償 → saga / process manager。判準見 §2 分類表。

> **適用邊界**：本方法論覆蓋 **read-heavy**（單 aggregate + 衍生計算為主）與 **command-side**（多 aggregate + 協調邏輯）兩大形態。**event sourcing / CQRS** 模式的專屬延伸（event store、projection、分離讀寫模型）未覆蓋，遇此類形態時標為「未覆蓋」並上報。

---

## 2. Bundle 分類判準

| 分類 | 判準 | 依賴 |
|------|------|------|
| aggregate root | 需持久化的核心實體；持有核心不變式；是其他 bundle 的資料源。多 aggregate 專案有多個，各自持有獨立不變式和一致性邊界 | 被依賴（最底層 domain）；aggregate 間僅允許 by-id 參照（VO 持有 ID），禁直接嵌入——嵌入會違反交易一致性邊界 |
| kernel（共享） | 被 2+ read-model 消費的核心計算（估值/聚合）；不屬任何單一 read-model | 依賴 aggregate + supporting VO |
| read-model | 衍生計算（趨勢/比率/配置）；從 kernel/aggregate 讀取後轉換 | 依賴 kernel/aggregate；可依賴其他 read-model 但**不成環**；多 aggregate 時可跨 aggregate 聚合資料（透過 repository），但不修改 aggregate |
| supporting VO | 自足值物件 + 純函式（折舊/換算演算法）；有自己的不變式 | 零依賴或被單向依賴 |
| domain service | 無狀態跨 aggregate 協調；邏輯不自然屬於任一 aggregate | 依賴 2+ aggregate 的 repository 介面（透過 DI），不持有狀態 |
| policy / event handler | 訂閱 aggregate A 的 domain event，觸發 aggregate B 的命令；無自身持久化 | 間接依賴：事件發布者 + 命令接收者（透過 event bus），不直接 import aggregate |
| saga / process manager | 有狀態跨 aggregate 長期協調 + 補償邏輯；自身需持久化（進行中狀態） | 自身持久化 + 依賴多 aggregate 的 repository |
| 非 domain：cross-cutting | 顯示層關注（i18n/主題/格式化/單位換算）→ presentation；或跨切面**基礎設施**關注（稽核日誌/通知/排程，非顯示）→ infra 層 | presentation 或 data/infra |
| 非 domain：infrastructure | 有狀態 + I/O（外部服務/持久化/匯入匯出）| data |

> 非 domain 兩類列入 domain map 僅為**覆蓋完整性**（FR→bundle 全覆蓋），與真 domain 視覺區隔。

**command-side 與現有分類的邊界判準**（避免誤歸類）：

| 對照 | 現有分類 | command-side 分類 | 區別判準 |
|------|---------|-------------------|---------|
| kernel vs domain service | kernel 產出衍生值被 read-model 消費 | domain service 協調命令不產出衍生值 | 「產出被消費」vs「協調命令」 |
| read-model vs policy | read-model 從 aggregate 讀取並轉換 | policy 訂閱事件並觸發命令 | 「讀取轉換」vs「事件驅動命令」 |
| aggregate vs saga | aggregate 是業務實體 | saga 是協調流程狀態 | 「業務不變式」vs「流程狀態機」 |

---

## 3. 依賴方向 DAG 規則

- domain 不得 import data / presentation / UI 框架 / 外部服務——違反則喪失純函式可測性。
- read-model 依賴 kernel + aggregate；read-model 間**只禁成環、不禁無環邊**（A→B 合法，A→B→A 禁）。**不要**為單一消費者的衍生計算硬造假 kernel——kernel 判準是「被 2+ read-model 消費」，只有一個下游時保留為被依賴的 read-model 即可。
- **aggregate 間**：禁直接 import / 嵌入；僅允許 by-id 參照（VO 持有另一 aggregate 的 ID）。by-id 參照是 aggregate 一致性邊界的必然結果——同一 aggregate 內原子一致，跨 aggregate 最終一致（透過 domain events）。
- **domain service**：可依賴多 aggregate 的 repository 介面（透過 DI），不持有狀態。
- **policy / event handler**：透過 event bus 間接依賴，不直接 import aggregate。
- **saga / process manager**：自身持久化（狀態機）；透過 repository 介面協調多 aggregate。
- **底線必須用實際 import 鏈驗證，不可憑心智模型宣告**：宣告「A 只依賴 B」前用 grep/codegraph 查 A 的實際 import 集合；共享工具被 2+ 模組消費即為 kernel，須獨立分層（防 `ARCH-BAL-001`：底線與現況漂移）。
- 描述目標邊界（尚未接線的計畫依賴）時明文標註「目標邊界，非現況」，與現況區隔。

---

## 4. 層 → 測試對應

| 層 | 測試類型 | 說明 |
|----|---------|------|
| domain（aggregate/kernel/read-model/VO）| 純函式 unit test | 餵真實 domain 物件斷言數值，無 mock/widget/DB |
| domain 不變式（per-bundle）| unit test 系統列舉 | 每 bundle 的業務規則/邊界/狀態轉換前置條件逐條列舉（各專案自己的 domain 不變式），不靠「剛好出現於 UC 場景」被動覆蓋 |
| domain service | unit test + integration test | mock repository 驗證協調邏輯；integration test 驗證跨 aggregate 行為 |
| policy / event handler | unit test | 餵 domain event 斷言觸發正確命令 |
| saga / process manager | unit test（狀態機）+ integration test | 狀態轉換測試 + 補償路徑測試 |
| data | repository test | in-memory DB + schema 約束 |
| presentation | widget test | provider override + 渲染斷言 |

> 分層測試決策樹（Clean Architecture 層級 → 測試手段）見 `.claude/methodologies/hybrid-testing-strategy-methodology.md`；domain 不變式軸與 traceability 的對應見 version-bootstrap Step 5 / Step 2.5 domain map 不變式節。
>
> **不變式 vs 計算測試的界線**（避免雙重計數或遺漏）：不變式 = 跨所有輸入成立的性質 / 跨欄約束（property test，如「占比恆加總=1」「淨額 = Σ資產−Σ負債」）；計算測試 = 特定輸入的值斷言（example test）。read-model 的「不變式」易坍縮成「計算正確」——判別用「這條斷言換一組輸入還成立嗎」：成立則屬不變式軸，只對特定值成立則屬計算測試。

---

## 檢查清單

界定 domain map 時確認：

- [ ] 每個 spec FR 有層歸屬（domain / presentation / data），FR→bundle 覆蓋表無遺漏
- [ ] domain FR 按業務概念聚類（非按畫面）
- [ ] 被多 read-model 共享的核心計算已抽 kernel
- [ ] 依賴方向底線經 import 鏈驗證（非憑心智模型）
- [ ] read-model 彼此不成環（DAG）
- [ ] 多 aggregate 時：aggregate 間僅 by-id 參照、無直接 import
- [ ] command-side 邏輯已分類（domain service / policy / saga）且不混入 read-model
- [ ] 每 bundle 標測試層；domain 不變式逐條列舉
- [ ] 非 domain（cross-cutting/infrastructure）與真 domain 視覺區隔

---

**Last Updated**: 2026-07-23 | **Version**: 2.0.0 — 延伸支援多 aggregate（by-id 互參、交易一致性邊界）+ command-side 形態（domain service / policy / saga），0.1.0-W2-021（source: W2-018 ANA）。**Source**: 0.1.0-W2-016.4（v1.0.0 初建）。動機案例：flutter_balance W2-014 domain map；W2-016 Round 3 steelman S1/S3 findings。
