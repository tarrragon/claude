# Memory 升級評估決策樹（捕獲時分流）

本文件定義知識捕獲的分流決策流程。分流判斷在**寫入前**執行（Q0）；Q1/Q2 用於 deferred 收割與既有積壓 promote。「寫入後補評估」的事後閉環經量化證明不執行（130 檔 feedback memory 標註率 4%），故決策時點前移。

---

## 使用時機

| 時點 | 執行內容 |
|------|---------|
| 準備記錄經驗教訓時（**主路徑**） | 先走 Q0 捕獲時分流，再落筆 |
| deferred 項收割（根因後續成熟、發版稽核點名、promote 積壓清理） | 走 Q1/Q2 判目的地 |

`project_*.md` 類型的 memory 屬於專案內部 context 索引，不需執行升級評估，但需檢查命名前綴是否正確。

---

## 決策樹

```
記錄經驗教訓前（捕獲時）
    |
    v
Q0: 錯誤學習類且跨專案適用嗎？
    |
    +-- 是 → 根因已過 Two-Phase Reflection（5+ 假設、2 層深因、WRAP 檢驗）？
    |    |
    |    +-- 是 → 直接 /error-pattern add（allocator 來源前綴編號，隨 sync 跨專案傳播）；
    |    |        memory 至多留一行 pointer；流程結束
    |    |
    |    +-- 否 → feedback memory + frontmatter 標註 upgrade: deferred 與理由；
    |             明顯跨專案者可另以 framework-issue create --label candidate 建 inbox 錨點；
    |             deferred 積壓由發版稽核收割，收割時走 Q1
    |
    +-- 否 → Q1
         |
         v
Q1: 此原則對其他專案也適用嗎？
    |
    +-- 否 → 加 project_ 前綴，保留為專案特定 context；流程結束
    |
    +-- 是 → Q2（必須升級）
         |
         v
         Q2: 屬於哪類原則？升級到對應目的地
              |
              +-- 通用品質基線        → rules/core/quality-baseline.md 或新 rules/core/*.md
              +-- PM 行為規範         → rules/core/pm-role.md 或 pm-rules/
              +-- 單一代理人身份/偏好 → agents/<name>.md（邊界見 knowledge-carrier-allocation 代理人定義內容規範）
              +-- 語言/工具品質       → references/quality-<lang>.md
              +-- 錯誤學習           → error-patterns/{category}/
              +-- 流程方法論         → methodologies/
              +-- Skill 引導         → skills/<skill>/
```

> Q0 的「根因未熟直寫 canonical」防護理由：表層根因經 sync 傳播到所有 consumer 後，已 pull 的舊版不會自動撤回——錯知識跨專案傳播的回收成本高於對知識暫留本地。Two-Phase Reflection 見 `.claude/methodologies/three-phase-reflection-methodology.md`。

> 目的地拿不準時，先查 `.claude/methodologies/knowledge-carrier-allocation-methodology.md`（受眾 x 形態頂層地圖）。

---

## Q1：跨專案適用性判斷

### 判斷標準

| 提問 | 若答「是」 |
|------|-----------|
| 此原則是否與當前專案的特定技術選型綁定？ | 否，加 `project_` 前綴 |
| 換到 Flutter / Python / Go 等其他專案，這個原則還會成立嗎？ | 是，必須升級 |
| 是否屬於 PM 行為、文件規範、品質基線等跨語言通用議題？ | 是，必須升級 |
| 是否來自 PM 或代理人協作流程的反饋？ | 是，多半必須升級 |

### 專案特定的典型範例

- 「本專案的 ESLint 規則設定」
- 「目標站點 DOM 選擇器多層 fallback 策略」
- 「特定平台 API 限制（例如 Manifest V3、iOS 沙箱）」

### 跨專案通用的典型範例

- 「PM 派發後立刻切換工作而非空等」
- 「框架文件禁止引用專案 ticket ID」
- 「破壞性操作預設保留而非刪除」

---

## Q2：六類目的地分支

### 分支 1：通用品質基線 → `rules/core/`

**判斷條件**：

| 特徵 | 範例 |
|------|------|
| 屬於跨語言、跨角色都需遵守的品質底線 | 「測試通過率必須維持 100%」 |
| 影響所有開發流程的決策原則 | 「Phase 4 重構評估不可跳過」 |
| 屬於 commit/版本/文件等基礎規範 | 「錯誤學習知識捕獲時分流」 |

**目的地**：

- 既有規則延伸 → `rules/core/quality-baseline.md` 新增規則條目
- 全新主題 → `rules/core/<topic>.md`（如 `observability-rules.md`、`cognitive-load.md`）

### 分支 2：PM 行為規範 → `rules/core/pm-role.md` 或 `pm-rules/`

**判斷條件**：

| 特徵 | 範例 |
|------|------|
| 主線程角色行為準則 | 「PM 不寫產品程式碼」 |
| PM 流程操作 SOP | 「代理人完成確認 SOP」 |
| Ticket / 派發 / 驗收等 PM 專屬流程 | 「並行派發前置檢查」 |

**目的地**：

- 簡短行為原則 → `rules/core/pm-role.md`
- 複雜流程 SOP → `pm-rules/<topic>.md`

### 分支 3：語言/工具品質 → `references/quality-<lang>.md`

**判斷條件**：

| 特徵 | 範例 |
|------|------|
| 與特定語言或框架的最佳實踐綁定 | 「Dart async/await 錯誤處理模式」 |
| 工具使用規範（git、bash、特定 CLI） | 「git index.lock 防範」 |
| 語言專屬的可觀測性實作 | 「Python logging 配置慣例」 |

**目的地**：

- 語言品質 → `references/quality-{dart,python,go,js,...}.md`
- 工具規範 → `rules/core/<tool>-usage-rules.md`（如 `bash-tool-usage-rules.md`）

### 分支 4：錯誤學習 → `error-patterns/{category}/`

**判斷條件**：

| 特徵 | 範例 |
|------|------|
| 來自實際失敗或回歸的反饋 | 「修復函式假設欄位格式錯誤」 |
| 可被歸類為流程、實作、架構或測試的反模式 | 「premature agent completion judgment」 |
| 需要提供具體防護措施的教訓 | 「Hook 靜默失敗的雙通道修復」 |

**目的地**：

- 流程合規 → `error-patterns/process-compliance/PC-XXX-*.md`
- 實作 bug → `error-patterns/implementation/IMP-XXX-*.md`
- 架構問題 → `error-patterns/architecture/ARCH-XXX-*.md`
- 測試問題 → `error-patterns/testing/TEST-XXX-*.md`

### 分支 5：流程方法論 → `methodologies/`

**判斷條件**：

| 特徵 | 範例 |
|------|------|
| 系統化的工作流程或思考框架 | 「Atomic Ticket 拆分方法論」 |
| 可重複套用的決策框架 | 「WRAP 決策框架」 |
| 跨多個 Ticket 都會用到的方法論 | 「註解撰寫方法論」 |

**目的地**：

- `methodologies/<topic>-methodology.md`

### 分支 6：Skill 引導 → `skills/<skill>/`

**判斷條件**：

| 特徵 | 範例 |
|------|------|
| 屬於某個 skill 的內部流程改進 | 「continuous-learning 升級評估步驟」 |
| 需要在 skill 觸發時自動套用的指引 | 「ticket 命名規範」 |
| 屬於工具型操作而非品質規範 | 「sync-push 推送流程」 |

**目的地**：

- `skills/<skill>/SKILL.md` 主流程
- `skills/<skill>/references/<topic>.md` 詳細指引

---

## 升級後處理

完成升級後，對原 memory 檔案執行以下三步：

### 步驟 1：在原 memory 檔案頂部加註「已升級」標註

```markdown
> **Status**: Upgraded — 已升級至框架共用層
> **Upgraded To**: `.claude/rules/core/quality-baseline.md` 規則 X
> **Upgraded Date**: YYYY-MM-DD
```

### 步驟 2：列出升級目的地路徑

完整路徑（從 `.claude/` 開始），方便日後追溯。若同一原則升級到多個位置，全部列出。

### 步驟 3：自 MEMORY.md 索引移除該條目

MEMORY.md 每 session 自動載入，升級後保留索引行即雙重儲存（升級即搬家，非複製）。memory 單檔可保留供考古（記錄此原則在本專案的觸發歷史），但索引必須移除；對照關係記於升級 commit 或 ticket。與 `pm-quality-baseline.md` 規則 7「升級後處理」一致。

---

## 模糊情境處理

### 情境 A：跨類別

若原則同時屬於多類（例如「PM 行為」也是「品質基線」），優先選擇**最具體**的目的地。例如「PM 寫產品程式碼禁止」屬於 PM 行為規範（rules/core/pm-role.md），而非通用品質基線。

### 情境 B：升級後仍不確定具體位置

先升級到較通用的位置（如 `rules/core/quality-baseline.md`），本次決策即告完成（狀態確定，非延後）。抽出獨立檔案屬「未來新原則出現」時的新決策，屆時依 `rules/README.md` 自動載入預算原則另行評估，與本次升級無未結事項。

### 情境 C：原則尚未成熟

若反饋來自單一事件、缺乏跨案例驗證（即 Q0 的「根因未熟」分支），保留為 `feedback_*.md` 並於 frontmatter 標註 `upgrade: deferred` 與理由；明顯跨專案者可另以 framework-issue `create --label candidate` 建 inbox 錨點。deferred 項由發版稽核（version-release 稽核項）點名收割，禁止無標註裸寫（無 trigger 的「待累積案例後升級」即不可觀測積壓的來源）。

---

## 關聯

- `.claude/pm-rules/pm-quality-baseline.md` 規則 7 — 錯誤學習知識捕獲時分流（分流判準權威來源）
- `.claude/error-patterns/process-compliance/PC-061-memory-upgrade-blindness.md` — Memory upgrade blindness 錯誤模式
- `.claude/references/reference-stability-rules.md` 規則 8 — 框架文件禁止引用專案層級識別符
- `references/memory-capture-guide.md` — Memory Capture 標準結構與品質檢查

---

**Last Updated**: 2026-07-05
**Version**: 2.0.0 — 決策時點由「寫入後」前移為「捕獲時」：新增 Q0 分流（Two-Phase Reflection 成熟度門檻 + deferred 顯式標註 + framework-issue candidate 可選 inbox）；情境 C 改綁發版稽核收割（消除無 trigger 的「待回顧」積壓）；Q1/Q2 保留供 deferred 收割與積壓 promote
**Version**: 1.0.0 — 初始建立
