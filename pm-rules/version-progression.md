# 版本推進決策規則

> **核心原則**：版本 scope 開放時，開發過程中發現的問題優先在本版本內處理；scope 凍結後不再無條件收入，依問題性質分流（見〈版本生命週期〉）。

---

## 版本層級語義

| 層級 | 語義 | 核心問題 |
|------|------|---------|
| **Wave** | 執行批次 | 同一個目標，分幾批做？ |
| **Patch** | 獨立可交付 | 完成後能獨立發布嗎？ |
| **Minor** | 功能里程碑 | 用戶能感知到新功能嗎？ |
| **Major** | 架構里程碑 | 系統基本能力改變了嗎？ |

---

## Q1-Q4 語義判斷

> 本流程圖假設版本 scope 已開放。scope 凍結時不進入此流程，改依〈版本生命週期〉的凍結分流處理。

```
[Q1] 和當前版本主題相同? → 是 → 新增 Wave
                          → 否 ↓
[Q2] 完成後能獨立發布? → 是 → 推進 Patch
                        → 否 ↓
[Q3] 需當前版本完成後才能開始? → 是 → 等待後推進 Patch
                                → 否 → 可並行開發，推進 Patch
[Q4] Patch 系列達成功能里程碑? → 是 → 推進 Minor
```

---

## 快速判斷檢查清單

1. [ ] 版本 scope 已凍結？ YES → 依〈版本生命週期〉凍結分流（品質→patch+1／能力→minor+1／框架→canonical issue）STOP
2. [ ] （scope 開放）是開發衍生問題？ YES → **本版本處理** STOP
3. [ ] [Q1] 和當前版本主題相同？ YES → **新 Wave** STOP
4. [ ] [Q2] 完成後能獨立發布？ YES → **新 Patch** STOP
5. [ ] [Q4] 達成功能里程碑？ YES → **新 Minor**

---

## 強制規則

| 規則 | 說明 |
|------|------|
| scope 開放時衍生問題進當前版本 | 流程缺口/技術債務/Bug/工具改善（含 .claude 規則/Hook/Skill 修正）在 scope 開放的 active 版本內以 Wave 或 Patch 處理，無需 Q1-Q4 |
| scope 凍結後依問題性質分流 | 品質改善（bug/技術債）→ 下一個 patch（x.y.z+1）；新能力 → 下一個 minor（x.y+1.0）；框架問題（根源在 `.claude/` 通用資產、抽象後仍可攜）→ canonical issue，不進本地版本判斷（見 `framework-issue` skill〈決策入口〉） |
| 版本推進需語義理由 | 必須通過 Q1-Q4 判斷（僅 scope 開放時適用） |
| 活躍版本由 todolist.yaml 決定 | `status: active` 為 Source of Truth |
| 版本邊界以 active 為準 | 版本邊界時（舊版剛完成/新版剛啟動），todolist.yaml active 版本即為「當前版本」，無需推斷 |

**Why**：舊制一律無條件收入 active 版本、免除版本判斷，未區分「版本現在還收不收票」這一軸，實測（0.1.0）造成 pending 池膨脹至遠超必要交付範圍的規模——衍生問題與框架問題無差別流入同一 active 版本，必要與非必要工作無法分辨。**Consequence**：不分流會使版本收尾遙遙無期，且框架問題原地滯留在無法收件的本地池中，不會被推向能實際處理它的 canonical issue。**Action**：建票前先查 `docs/todolist.yaml` 對應版本的 `scope` 欄位；`scope: frozen` 時依上表分流，不再無條件視為本版本工作。

---

## 版本生命週期

版本從建立到完成，在三個互相獨立的軸上前進：**版本歸屬**（票屬於哪個版本號）、**收件資格**（版本現在能否收新根票）、**執行資格**（該版本下的既有票能否被 claim/執行）。三軸混為一談是舊制的根因——舊制把 `status` 欄位當成三種語意共用的單一開關，`planned` 版本因此被誤判為「不能執行」；經查證 `lifecycle.py` 對版本狀態零檢查，**claim 不查版本狀態**：任何版本（含 `planned`）下已存在的票，今天就能被 claim 並執行，執行早已與版本狀態解耦。

| 階段 | status / scope | 收件資格 | 執行資格 |
|------|----------------|---------|---------|
| 規劃中 | `status: planned` | 可建票（須以 `--version` 明示指定） | 可執行（claim 不查版本狀態） |
| 開發中，scope 開放 | `status: active`，`scope` 欄位缺席或非 `frozen` | 可建票（含根票，跟隨版本推進正常流程） | 可執行 |
| 開發中，scope 凍結 | `status: active`，`scope: frozen` | 僅收帶 `--scope-blocker <理由>` 的根票（理由持久化為 ticket frontmatter `scope_blocker` 欄位，供發版側查詢）；`--parent` 子票不受影響 | 可執行（既有票不受收件閘門限制） |
| 已完成 | `status: completed` | 不可建根票（依情境回報 `VERSION_NOT_ACTIVE` 或 `VERSION_NOT_REGISTERED`） | 不適用（無待執行票） |

**凍結動作含兩步，不只標記版本條目**：凍結 = (1) `docs/todolist.yaml` 標 `scope: frozen`；(2) 對凍結前已存在、且屬版本契約必要的 `pending` 票逐張執行 `ticket track set-scope-blocker <id> --reason <對應契約項>`。**Why**：發版檢查（見 `.claude/skills/version-release/SKILL.md`）以 `scope_blocker` 欄位區分阻擋與前移，只覆蓋凍結後才建立的根票（`--scope-blocker` 建票時寫入）；凍結前既有的必要票沒有這個建立時機，若不回溯標記，發版檢查會把它們誤判為可前移，必要工作因此被搬到下一版本。**規劃頁面（`docs/plans/` 等）不是 CLI 的資料來源**——「這張票是必要的」只寫在規劃文件不會被發版檢查讀到，必要性須進票面 `scope_blocker` 欄位才算數。

**scope 凍結後的分流去向**（對應上方強制規則表）：

| 問題性質 | 去向 | 說明 |
|---------|------|------|
| 品質改善（bug、技術債） | 下一個 patch（x.y.z+1） | 登記規則見 `docs/todolist.yaml` 檔頭〈patch 版本登記規則〉 |
| 新能力 | 下一個 minor（x.y+1.0） | 需先於 `docs/todolist.yaml` 登記為 `planned` 或 `active` |
| 框架問題（抽象可攜 + 根源在 `.claude/` 通用資產，兩條件皆成立） | canonical framework issue | 不落地為本地版本票；該問題在本 consumer 的落地實作票才回頭建本地票，並掛 `--dedup-checked <issue 號>`（見 `.claude/skills/ticket/references/create-command.md`〈可攜問題分流硬閘門〉） |

---

## Ticket 版本歸屬規則

| 規則 | 說明 |
|------|------|
| 新 Ticket 版本號預設對齊 active 版本 | 建立 Ticket 時，版本號預設跟隨當前 active 版本，除非有明確跨版本要求；scope 凍結時另受〈版本生命週期〉收件資格規則約束 |
| 版本號不主動調整 | Ticket 版本號建立後不主動變更；只有 wave 可根據任務鏈位置調整 |
| 版本目標改變時同步處理 | 版本開發目標改變時，必須同步執行：(1) 更新版本目標設定，(2) 遷移受影響 Ticket，(3) 重新規劃 wave |

---

## Wave 獨立性原則

Wave 是相互隔離的執行單位。禁止跨 Wave 依賴和並行派發。

> 詳細 Wave 規則和 Ticket 歸屬判斷：.claude/references/version-progression-details.md

---

## 版本收尾技術債整理流程

> **觸發時機**：決策樹第八層情境 C2（版本內所有 Ticket 已完成，無任何待處理任務）
>
> **來源**：W49 實踐 — Wave 收尾多視角審查 + 版本收尾技術債批量建 Ticket 模式

版本完成後、執行 `/version-release check` 之前，**必須**整理未追蹤的技術債。

### 流程

```
情境 C2：版本無任何待處理任務
    |
    v
[強制] 檢查 todolist.yaml
    → 篩選與當前版本相關的未排程項目
    → 識別需要帶入下一版本的技術債
    |
    v
有需要建立的技術債 Ticket?
    |
    +── 是 → /ticket batch-create 批量建立（歸入下一版本）
    |         → 建立後不影響當前版本完成狀態
    |
    +── 否 → 繼續
    |
    v
[強制] /version-release check
    → AskUserQuestion #13（版本推進確認）
```

### 技術債篩選標準

| 來源 | 判斷 | 處理 |
|------|------|------|
| todolist.yaml 已記錄但未排程 | 是否與下一版本目標相關？ | 相關 → 建立 Ticket；不相關 → 保留在 todolist |
| Phase 4 `/tech-debt-capture` 產出 | 已建立 Ticket？ | 已建 → 確認版本歸屬；未建 → 補建 |
| Wave 審查發現但未處理 | 是否阻塞版本發布？ | 阻塞 → 本版本處理；不阻塞 → 歸入下一版本 |

### 禁止行為

| 禁止 | 說明 |
|------|------|
| 跳過 todolist 檢查直接發布 | 可能遺漏已知技術債 |
| 將技術債 Ticket 建在當前版本 | 版本已完成，應歸入下一版本 |
| 只口頭記錄不建 Ticket | 必須有可追蹤的 Ticket |

---

## 權限需求變更檢查

若專案有面向使用者的權限宣告（如 Chrome Extension、行動 APP），版本發布或推進時須檢查權限是否較上一發布版本變更。**Why**：權限有變更而未同步更新權限說明文件，會導致應用程式商店審核因宣告與實際不符而卡關。**Action**：依專案類型同步更新對應的權限說明文件與上架頁；後端服務等無使用者端權限宣告的專案類型不適用。

各專案類型的權限宣告位置、同步更新對象與完整檢查步驟，見 `version-release` skill 的「權限需求變更檢查」章節；本規則僅在版本推進階段提醒，不重複定義步驟。

---

## 相關文件

- .claude/pm-rules/monorepo-version-strategy.md - Monorepo 三層版本定義和同步規則（L1/L2/L3）
- .claude/references/version-progression-details.md - Wave 獨立性、Ticket 歸屬、二元決策流程
- .claude/references/version-decision-case-studies.md - 案例分析
- .claude/pm-rules/ticket-lifecycle.md - Ticket 生命週期

---

## 跨版本 Ticket 遷移決策

當 Ticket 需要從一個版本遷移到另一個版本時：

| 情境 | 決策 |
|------|------|
| 當前版本未完成但新版本已開始 | 評估 Ticket 是否仍相關，相關則遷移 |
| Ticket 依賴已在新版本實作的功能 | 遷移到新版本 |
| Ticket 描述的問題已被新版本解決 | 關閉並記錄原因 |

使用 `/ticket migrate` 執行遷移。

---

## 版本遷移觸發條件與判斷流程

### 觸發條件

| 觸發時機 | 說明 | 判斷入口 |
|---------|------|---------|
| 版本內所有 Ticket 完成 | 決策樹情境 C2 觸發 | 版本收尾技術債整理 → /version-release check |
| 新功能需求超出當前版本範圍 | Q1 回答「否」時 | Q2-Q4 判斷決定新版本層級 |
| todolist.yaml current_version 不一致 | Version Consistency Guard Hook 偵測 | 修正 todolist.yaml 或完成舊版本任務 |
| 舊版本有遺留未完成 Ticket | Version Consistency Guard Hook 偵測 | 評估遷移、關閉或完成 |

### 判斷流程

```
觸發遷移評估
    |
    v
[Step 1] 確認當前版本所有 Ticket 已完成
    → ticket track list --version {current} --status pending in_progress
    → 有未完成? → 先處理完成或遷移
    |
    v
[Step 2] 執行 /version-release check
    → CHANGELOG 更新? Smoke test 通過?
    |
    v
[Step 3] 更新 todolist.yaml
    → current_version: {new}
    → previous_version: {old current}
    → next_version: {new + 1}
    |
    v
[Step 4] 確認舊版本遺留 Ticket 處理方式
    → 仍相關 → /ticket migrate
    → 已解決 → 關閉並記錄原因
    → 不再相關 → 關閉並記錄原因
```

---

**Last Updated**: 2026-09-23
**Version**: 4.1.0 — 〈版本生命週期〉凍結列補「凍結動作含兩步」說明：凍結不只標記版本條目，還須對凍結前已存在的必要 pending 票逐張 `ticket track set-scope-blocker` 回溯標記，否則發版檢查會把它們誤判為可前移；補一句規劃頁面不是 CLI 資料來源，必要性須進票面欄位。
**Version**: 4.0.0 — 衍生問題歸屬規則改為 scope 凍結模型：強制規則表舊有三列免版本判斷、一律無條件收入 active 版本的規則改寫為「scope 開放時進本版本」「scope 凍結後依品質/能力/框架三性質分流」兩列；快速判斷檢查清單新增第 1 項 scope 凍結檢查；新增〈版本生命週期〉段，明寫版本歸屬／收件資格／執行資格三軸解耦，以及執行早已與版本狀態解耦（claim 不查版本狀態）的事實。舊制在實測中造成 pending 池膨脹至遠超必要交付範圍的規模，且與版本範圍凍結硬閘門（`ticket create` 子命令的可攜問題分流閘門旁側機制）的路由結論直接衝突——同一 create 路徑上，凍結閘門引導改投下一版本，而本文件舊制要求免判斷收入本版本。`PC-121-pm-recommends-framework-ticket-to-future-version.md` 因前提（框架 ticket 當時無版本收件資格路由選項）改變已標 superseded，見該檔 Superseded 註記段。歷史 1.0–3.4 版見 git log。
