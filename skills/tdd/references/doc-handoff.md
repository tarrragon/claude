# Doc 產出物銜接 TDD 流程指引

## 目的

定義 `/doc` skill 產出物（Proposal / Spec / UseCase 需求文件）如何作為 TDD 各階段（Phase 0 前置審查、Phase 1 功能設計、Phase 2 測試設計）的結構化輸入。銜接只做**格式映射 + 語意種子**，不重新設計——doc 端的設計決策已確認，TDD 端消費它。不經結構化銜接，Phase 1 設計者缺少 doc 端已確認的設計決策，重複推導或與 doc 結論矛盾。

**設計依據**：上游需求流程→doc 的銜接是「格式移交」（一對一映射），doc→TDD 的核心是「語意轉換」（系統做什麼→怎麼驗證做對了），轉換判斷由 TDD Phase 1 設計者執行，故銜接邏輯放 TDD 端。

---

## 觸發條件（條件式，有 doc 產出物才執行）

`/tdd start` 時，偵測以下路徑是否有對應文件：

| 路徑 | 偵測方式 |
|------|---------|
| `docs/spec/{domain}/` | 功能所屬 domain 有 spec 文件 |
| `docs/usecases/` | 有相關 UC 文件（spec 的 `related_usecases` 欄位） |
| `docs/proposals/` | 有來源 proposal（spec 的 `source_proposal` 欄位） |

- **有 doc 文件** → 執行本銜接流程，產出「TDD 輸入種子包」作為 Phase 0/1 的預填輸入
- **無 doc 文件** → 走現有 TDD Phase 0 流程（本銜接不是必要前置條件）

---

## 執行步驟

1. 偵測 doc 文件是否存在（§觸發條件）
2. 前置閘門檢查——三項全通過才繼續，不通過則中止銜接回 doc 端補齊（§前置閘門）
3. 執行映射（§映射表）+ UC 步驟→GWT 轉換（§UC 步驟→GWT 轉換規則）
4. 判斷整合測試 / 單元測試分工（§整合測試 vs 單元測試分工）
5. 產出種子包寫入 Ticket 的 Context Bundle（背景資料區）或 Problem Analysis（問題分析區）（§TDD 輸入種子包格式）
6. 執行檢查清單確認覆蓋完整（§檢查清單）

---

## 前置閘門

映射品質由輸入品質決定——FR（Functional Requirement，功能需求）空則 GWT（Given-When-Then）種子無操作可轉換、UC 空則無場景步驟可映射、無交叉引用則整合測試無法追溯 UC 場景。映射前確認 doc 產出物品質足夠：

| 檢查項 | 條件 | 不通過時動作 |
|--------|------|-------------|
| Spec FR 非空 | `docs/spec/{domain}/` 有至少 1 個 FR 定義 | 回 doc 補 spec（至少 1 個 FR） |
| UC 主成功場景非空 | UC 有至少 1 個完整場景步驟 | 回 doc 補 UC 場景步驟 |
| Spec ↔ UC 交叉引用存在 | Spec 的 `related_usecases` 有值 | 回 doc 建立 Spec↔UC 交叉引用 |
| 畫面狀態矩陣（涉及 UI 時） | spec 含畫面 × 狀態 × 操作 × 退出路徑矩陣 | 回 doc 補畫面狀態機 spec |

任一不通過 = doc 端設計不完整，不可硬生 TDD 輸入。閘門檢查輸入存在性；輸入品質由 doc 端的 Spec 驗證流程保證（見 `/spec validate`）。

---

## 映射表：doc 產出物 → TDD Phase 輸入

映射方向依 doc 產出物的語意層級對應 TDD 各 Phase 的輸入需求：Phase 0 需要需求邊界（Proposal 提供）、Phase 1 需要行為規格（Spec FR + UC 場景提供）、Phase 2 需要端到端路徑（UC 資訊鏈提供）。

### Phase 0 輸入映射

| doc 來源 | → Phase 0 審查項 | 映射方式 |
|---------|-----------------|---------|
| Proposal 驗收條件 | 需求文件完整性 → 驗收標準 | **直接使用**：Proposal「範圍界定 / 驗收條件」提供 Phase 0 需求完整性的判斷依據 |
| Spec domain 歸屬 | 系統一致性 → 架構層次 | **直接使用**：`domain` + `depends_on_domains` 欄位供 Phase 0 檢查架構層次和依賴方向 |
| Spec FR 清單 | 重複實作檢查 → 功能描述 | **直接使用**：逐一比對既有實作，確認無重複造輪子 |

### Phase 1 輸入映射（核心）

| doc 來源 | → Phase 1 產出種子 | 映射方式 |
|---------|-------------------|---------|
| Spec FR + NFR（Non-Functional Requirement） | 功能規格文件 | **格式映射**：FR 描述→功能規格、NFR→Phase 1 非功能性需求定義的預填 |
| Spec 介面規格 | API 介面定義 | **格式映射**：endpoint/參數/回應結構→函式簽名和資料結構定義 |
| Spec 資料模型 | 資料結構定義 | **格式映射**：DDL/schema→Phase 1 資料結構格式 |
| UC 主成功場景步驟 | **行為場景（GWT）種子** | **語意轉換**：見下方「UC 步驟→GWT 轉換規則」 |
| UC 替代/例外場景 | **邊界條件歸屬種子** | **語意轉換**：替代場景→對應行為單元的邊界條件 |
| UC 前置/後置條件 | 驗收標準清單 | **格式映射**：UC 的成功保證→可量化驗收標準 |

### Phase 2 輸入映射

| doc 來源 | → Phase 2 產出種子 | 映射方式 |
|---------|-------------------|---------|
| UC 資訊鏈整合測試 | 整合測試案例 | **直接使用**：UC 的「資訊鏈整合測試」定義直接作為 Phase 2 整合測試規格 |
| Phase 1 行為單元清單 | 單元測試案例 | Phase 1 的產出自然流入 Phase 2（非 doc 直接映射） |

---

## UC 步驟→GWT 轉換規則

這是 doc→TDD 銜接的核心語意轉換。GWT（Given-When-Then）是 TDD Phase 1 的標準行為描述格式，UC 步驟是使用者視角敘事，轉換為 GWT 使行為單元可直接對應測試案例。每個 UC 場景步驟轉換為 GWT 格式的行為場景種子。

### 轉換方法

| UC 元素 | → GWT 元素 | 規則 |
|---------|-----------|------|
| 場景前置條件 | Given | UC 的「前置條件」+ 該步驟的上下文 |
| 場景步驟動作 | When | 步驟中的使用者/系統操作 |
| 場景步驟預期結果 | Then | 步驟描述的預期回應/狀態變更 |

### 轉換注意事項

- **跨步驟狀態累積**：UC 步驟有序，後續步驟的 Given 必須包含前序步驟的累積狀態，不可假設各 GWT 場景獨立。例：步驟 3 的 Given 需涵蓋步驟 1-2 已建立的 session 和已送出的事件。
- **角色切換**：UC 可能在步驟間切換操作者（使用者操作 vs 系統自動行為）。When 欄位應標注操作者，避免角色資訊在轉換中丟失。

### 轉換範例

以下以一個查詢驗證場景步驟為例，展示 UC→GWT 的轉換方法：

**場景步驟：查詢驗證**
```
原始 UC 描述：
  - 開發者 GET /v1/events?limit=10
  - 回傳包含剛送出的 3 筆事件
  - 按 type 篩選 GET /v1/events?type=error 只回傳 error 事件
```

**轉換為 GWT 種子**：
```
場景 5a：查詢全部事件
  Given: collector 已接收 3 筆事件（event + error + lifecycle）
  When: GET /v1/events?limit=10
  Then: 回傳 3 筆事件，各事件包含完整 schema 欄位

場景 5b：按 type 篩選查詢
  Given: collector 已接收包含不同 type 的事件
  When: GET /v1/events?type=error
  Then: 只回傳 type=error 的事件
```

### GWT 種子與行為單元的分工邊界

GWT 種子產出後，由 Phase 1 設計者（非本銜接流程）判斷行為單元粒度。以下為 Phase 1 可能的拆解方向（示意，非本流程產出）：

```
場景 5a + 5b
  ├─ 行為單元：query API 回傳正確數量
  ├─ 行為單元：type 篩選只回傳對應類型
  ├─ 行為單元：limit 參數限制回傳筆數
  └─ 邊界條件（來源：UC 替代場景）：空結果 / 無效 type / limit=0
```

**分工邊界**：本銜接流程負責到「GWT 種子」，行為單元拆解是 Phase 1 的職責（見 `phase1/rules.md`「行為單元識別」章節）。

---

## 整合測試 vs 單元測試分工

doc 的 UC 已定義整合測試（資訊鏈），TDD 需決定哪些行為由整合測試覆蓋、哪些需拆為單元測試。

### 分工決策框架

| 行為特性 | 測試層級 | 原因 |
|---------|---------|------|
| 跨元件資料流（SDK→collector→storage→query） | **整合測試**（UC 資訊鏈） | 串接失敗只能在完整鏈路中暴露 |
| 單一元件內部邏輯（schema 驗證、欄位轉換） | **單元測試** | 商業規則可單獨測試，不需要完整鏈路 |
| 元件邊界行為（API 回傳格式、錯誤碼） | **單元測試** | 契約面由元件自身保證，不依賴上下游 |
| 多元件互動的特定路徑（error 事件的特殊處理流程） | **整合測試** | 特定路徑的互動需完整鏈路才能重現 |

### 判斷原則

> **UC 場景步驟中，每個步驟問「這個步驟的正確性是由自己決定，還是由串接決定？」**

- **自己決定** = 單元測試（例：schema 驗證邏輯、query 篩選邏輯）
- **串接決定** = 整合測試（例：SDK flush 後 collector 能收到、collector 存入後 query 能查到）
- **配置決定** = 參數化測試（例：不同 storage backend 的行為差異、不同 flush interval 的邊界）

> BDD→單元拆分的完整判準見 `references/bdd-behavior-testing.md`「BDD→單元拆分判準」章節。各層測試方法的詳細選擇見 `references/layered-test-strategy.md`。

### 與 UC 資訊鏈的關係

UC 的「資訊鏈整合測試」已定義 end-to-end 路徑。本框架補充的是：**每個路徑中的節點，需要哪些單元測試來保護節點內部邏輯**。

```
範例資訊鏈：SDK init → event/error 送出 → flush → collector 驗證 → 儲存 → query

整合測試覆蓋：[────────────────── 整條鏈 ──────────────────]

單元測試覆蓋：
  [SDK init]     → session 建立、lifecycle 事件格式
  [flush]        → batch 格式、retry 邏輯
  [collector 驗證] → schema 合規性、欄位必填檢查
  [儲存]         → SQLite 寫入、併發安全
  [query]        → 篩選邏輯、分頁、排序
```

---

## TDD 輸入種子包格式

銜接流程完成後，產出以下結構寫入 Ticket 的 Context Bundle（背景資料區）或 Problem Analysis（問題分析區），使 Phase 0/1 代理人快速定位 doc 中的對應段落並取得結構化輸入（GWT 種子為完整內容；功能規格種子為路標引用，代理人需回讀 Spec 對應章節取得細節）。未寫入種子包的銜接等於未執行。

```markdown
## TDD 輸入種子包

### 來源文件
- Proposal: {PROP-ID}
- Spec: {SPEC-ID} (domain: {domain})
- UseCase: {UC-ID}

### Phase 0 預填
- 需求完整性：Proposal 驗收條件 {N} 項（見 {PROP-ID}）
- 架構檢查：domain={domain}, depends_on={依賴 domain 列表}
- FR 清單：{N} 個 FR（見 {SPEC-ID}）

### Phase 1 GWT 種子（從 UC 步驟轉換）

| 場景 | Given | When | Then | 來源 UC 步驟 |
|------|-------|------|------|-------------|
| {編號} | {前置條件} | {操作} | {預期} | {UC-ID} 步驟 {N} |

### Phase 1 功能規格種子（從 Spec 映射）
- 輸入定義：見 {SPEC-ID} 介面規格
- 輸出定義：見 {SPEC-ID} 介面規格
- 資料結構定義：見 {SPEC-ID} 資料模型
- NFR 預填：見 {SPEC-ID} NFR 章節
- 邊界條件歸屬：{UC 替代/例外場景 → 對應 GWT 種子編號}
- 驗收標準：{UC 前置/後置條件 → 量化指標}

### 整合測試映射（直接使用 UC 資訊鏈）
- {UC-ID} 資訊鏈：{鏈路描述}

### 待 Phase 1 設計者判斷
- [ ] GWT 種子→行為單元拆解粒度
- [ ] 邊界條件歸屬
- [ ] 跨模組共用決策（Q1-Q2）
- [ ] 非功能性需求具體數值（Q5-Q6b）
```

---

## 新專案起手模式

doc 產出物完整時（多份 Spec + 多個 UC），可用「批量 BDD 設計」取代逐功能 Phase 0/1/2。

### 流程

```
doc 完整產出（Proposal + Spec + UC）
    │
    v
批量 BDD 測試設計 ANA（Phase 1+2 合併）
  → 全專案 UC→GWT→單元測試清單→測試檔案結構→Mock 策略
    │
    v
批量紅燈 ticket 建立（按模組群組拆分）
    │
    v
批量紅燈撰寫（並行派發）
    │
    v
實作讓綠（可按模組群組或一次性）
```

### Phase 0 豁免條件

當 doc 產出物已含以下資訊時，Phase 0（架構審查）可簡化或跳過：

| doc 已提供 | 對應 Phase 0 審查項 | 判定 |
|-----------|-------------------|------|
| Spec `domain` + `depends_on_domains` | 架構層次 + 依賴方向 | 已有 → 跳過 |
| Spec 介面規格 | 重複實作檢查 | 已有介面定義 → 跳過 |
| Proposal 驗收條件 | 需求完整性 | 已有 → 跳過 |

**三項全有 → Phase 0 可跳過**，直接從 Phase 1 開始。部分有則簡化 Phase 0（只補缺項）。

### 與逐功能模式的區別

| 面向 | 逐功能模式（增量開發） | 新專案起手模式 |
|------|---------------------|-------------|
| Phase 0 | 每功能一輪 | 跳過（doc 已涵蓋） |
| Phase 1+2 | 分開執行 | 合併為「BDD 測試設計 ANA」 |
| 粒度 | 行為單元 | 模組群組 |
| 紅燈 ticket | 每功能一個 | 按模組群組批量建立 |
| 實作 ticket | 1:1 對應測試 | N 測試 : 1 實作（按模組） |

---

## 檢查清單

銜接執行完成後確認：

- [ ] 前置閘門三項全通過？（不通過則中止銜接，回 doc 端補齊）
- [ ] Phase 0 預填已對應 Proposal 驗收條件 + Spec domain + FR 清單？
- [ ] 每個 Spec FR 都有對應的 GWT 種子或整合測試覆蓋？
- [ ] UC 主成功場景每個步驟都轉換為 GWT 種子？
- [ ] UC 替代/例外場景都歸屬為某個 GWT 種子的邊界條件？
- [ ] 整合測試 vs 單元測試分工已標註？
- [ ] 輸入種子包已寫入對應 Ticket？

---

## 追溯矩陣初始化

doc-handoff 銜接時，同步初始化 `docs/traceability.yaml` 的骨架：

1. 讀取各 UC 的場景（主成功 + 替代 + 例外）
2. 為每個場景建立 entry（integration_tests + unit_tests 空映射）
3. 填入 spec_frs 對應（從 UC 的 `related_specs` + Spec 的 FR 編號）
4. status 初始為 `gap`，測試撰寫後改為 `covered`

**邊界回補流程**：測試撰寫者發現 UC 未描述的邊界時，在 `boundaries:` 區加 gap entry，PM 檢視後建 DOC ticket 回補 UC/Spec。Phase 4 掃描所有 `status: gap` 確認無遺漏。

---

## 相關文件

- `.claude/skills/doc/SKILL.md` — doc 產出物結構定義
- `.claude/skills/doc/references/spec.md` — Spec 的「Spec → Ticket 轉換指引」
- `.claude/skills/doc/references/usecases.md` — UC 的「資訊鏈整合測試」定義
- `references/phase0/rules.md` — Phase 0 審查項目（需求完整性）
- `references/phase1/rules.md` — Phase 1 行為單元識別（GWT 種子的下游消費者）
- `references/phase2/rules.md` — Phase 2 測試設計（最終測試案例設計）
- `references/task-granularity-rules.md` — 粒度規則（UC→行為單元→測試→實作）
- `.claude/skills/saas-tech-selection/references/decision-record-template.md`「銜接 doc 系統」— 上游銜接範本

---

**Last Updated**: 2026-06-22
**Version**: 1.0.0 — 初始建立。補齊 doc→TDD 銜接缺口（WRAP 評估結論：銜接放 TDD 端）
**Source**: 上游需求銜接模式驗證
