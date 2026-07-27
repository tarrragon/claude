# 知識捕獲三分流決策樹

本文件定義知識捕獲的分流決策流程。分流判斷在**寫入前**執行——「先記下來、事後再評估去向」的閉環經量化證明不執行（130 檔 feedback memory 標註率 4%），故決策時點前移到捕獲當下。

> **memory 不是目的地**：Claude Code 原生 memory 存於使用者 home 目錄的專案層級儲存（`~/.claude/projects/<project>/memory/`），不納入專案 git、不隨 `.claude/` sync 到其他專案，與「經驗須跨專案複用」的框架目標根本衝突。本框架因跨專案需求自建 `.claude/error-patterns/` 取代 memory 作為跨專案錯誤學習的載體；memory 機制本身不受影響，只是本決策樹不再把它列為候選目的地。

---

## 使用時機

| 時點 | 執行內容 |
|------|---------|
| 準備記錄經驗教訓時（**唯一路徑**） | 走 Q0 三分流，判定完當下即落筆到目的地或不記錄 |

`project_*.md` 類型的專案文件屬於專案內部 context 索引，不需執行本決策樹，但需檢查是否確實僅在本專案成立。

---

## 決策樹

```
記錄經驗教訓前（捕獲時）
    |
    v
Q0: 另一個專案的 session 讀到這段，能用嗎？
    |
    +-- 能用（框架相關） → 是否為錯誤學習類？
    |    |
    |    +-- 是 → 根因已過 Two-Phase Reflection（5+ 假設、2 層深因、WRAP 檢驗）？
    |    |    |
    |    |    +-- 是 → 直接 /error-pattern add（allocator 來源前綴編號，隨 sync 跨專案傳播）；流程結束
    |    |    |
    |    |    +-- 否 → 根因未熟（單一事件、假設未驗證），暫不記錄，續觀察同主題是否再現；
    |    |             明顯跨專案者可另以 framework-issue create --label candidate 建 inbox 錨點
    |    |
    |    +-- 否（非錯誤學習類） → Q1（選對應框架層目的地）
    |
    +-- 不能用，但本專案未來會用（專案相關） → 落 docs/ 或 CLAUDE.md；流程結束
    |
    +-- 兩者皆非（僅當前 session 成立） → 不記錄，ticket md 已承載執行脈絡；流程結束
```

> Q0「根因未熟不寫」的理由：表層根因經 sync 傳播到所有 consumer 後，已 pull 的舊版不會自動撤回——錯知識跨專案傳播的回收成本高於暫緩記錄。Two-Phase Reflection 見 `.claude/methodologies/three-phase-reflection-methodology.md`。

> 目的地拿不準時，先查 `.claude/methodologies/knowledge-carrier-allocation-methodology.md`（受眾 x 形態頂層地圖）。

**沒有第四個選項**：三個分支已窮盡所有情境，不存在「先記到某處、之後再決定」的中間態。

---

## Q1：框架相關內容的目的地分支

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
| 屬於某個 skill 的內部流程改進 | 「continuous-learning 捕獲時分流步驟」 |
| 需要在 skill 觸發時自動套用的指引 | 「ticket 命名規範」 |
| 屬於工具型操作而非品質規範 | 「sync-push 推送流程」 |

**目的地**：

- `skills/<skill>/SKILL.md` 主流程
- `skills/<skill>/references/<topic>.md` 詳細指引

---

## 模糊情境處理

### 情境 A：跨類別

若原則同時屬於多類（例如「PM 行為」也是「品質基線」），優先選擇**最具體**的目的地。例如「PM 寫產品程式碼禁止」屬於 PM 行為規範（rules/core/pm-role.md），而非通用品質基線。

### 情境 B：選定框架層後仍不確定具體位置

先落到較通用的位置（如 `rules/core/quality-baseline.md`），本次決策即告完成（狀態確定，非延後）。抽出獨立檔案屬「未來新原則出現」時的新決策，屆時依 `rules/README.md` 自動載入預算原則另行評估，與本次落地無未結事項。

### 情境 C：原則尚未成熟（僅限錯誤學習類）

若反饋來自單一事件、缺乏跨案例驗證（Q0 的「根因未熟」分支），暫不記錄，續觀察同主題是否再現；明顯跨專案者可另以 framework-issue `create --label candidate` 建 inbox 錨點。**不建立任何暫存記錄**——沒有暫存記錄就沒有積壓，同主題再現時憑印象或既有 ticket 紀錄重新評估即可。

---

## 關聯

- `.claude/pm-rules/pm-quality-baseline.md` 規則 7 — 知識捕獲時分流（分流判準權威來源）
- `.claude/error-patterns/process-compliance/PC-061-memory-upgrade-blindness.md` — Memory upgrade blindness 錯誤模式（memory 排除前的歷史問題記錄）
- `.claude/references/reference-stability-rules.md` 規則 8 — 框架文件禁止引用專案層級識別符

---

**Last Updated**: 2026-07-27
**Version**: 3.0.0 — 全檔改寫為三分流決策樹：Q0 由「錯誤學習跨專案適用性」擴充為「框架相關／專案相關／兩者皆非」三分流頂層判斷，memory 不再是任何分支的目的地；原 Q1（跨專案適用性）併入新 Q0；原 Q2 六類分支保留、改稱 Q1；「升級後處理」三步（含 MEMORY.md 索引移除）整章廢除——三分流下沒有「先寫暫存再升級」的中間態；情境 C 由「deferred frontmatter 標註」改為「不建立任何暫存記錄，續觀察」（0.2.1-W3-083，承接 0.2.1-W3-082 用戶裁示）
**Version**: 2.0.0 — 決策時點由「寫入後」前移為「捕獲時」：新增 Q0 分流（Two-Phase Reflection 成熟度門檻 + deferred 顯式標註 + framework-issue candidate 可選 inbox）；情境 C 改綁發版稽核收割（消除無 trigger 的「待回顧」積壓）；Q1/Q2 保留供 deferred 收割與積壓 promote
**Version**: 1.0.0 — 初始建立
