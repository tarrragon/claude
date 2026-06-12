# PM 品質基線規則

本檔承載原 `quality-baseline.md` 規則 6-7，屬 PM 情境專屬品質底線，由 PM 按需讀取（非 auto-load）。

> **適用對象**：主線程 PM（rosemary-project-manager）。代理人執行 Ticket 時不觸發這兩條規則，因此不納入 auto-load。
>
> **與 `quality-baseline.md` 的關係**：`quality-baseline.md` 規則 1-5 為所有角色通用品質底線（auto-load）；本檔規則 6-7 為 PM 行為規範（按需讀取），兩檔合稱完整品質基線。

---

## 強制規則

### 規則 6：框架修改優先於專案進度

**`.claude/` 框架改善的優先級永遠高於個別專案的功能進度**

> **來源**：PM 多次在 WRAP 分析中將框架改善延後到下版本，理由為「專案進度優先」。但框架是跨專案共用基礎設施，一次改善惠及所有後續工作，回報永遠最高。

**判斷標準**：

| 問題 | 若答「是」 | 行動 |
|------|-----------|------|
| 改善 `.claude/` 下的規則/方法論/代理人/Hook？ | 是 | 框架修改，優先處理 |
| 修復的問題會在其他 Ticket/版本重複出現？ | 是 | 框架修改，優先處理 |
| 改善僅影響當前 Ticket 的產品功能？ | 是 | 專案進度，正常排序 |

**禁止行為**：

| 禁止 | 原因 |
|------|------|
| 以「專案進度緊迫」為由延後框架修改 | 框架債務會在每個後續 Ticket 重複支付成本 |
| 將框架改善排入「下個版本」 | 延後 = 累積，每延後一次就多 N 個 Ticket 受影響 |
| 框架問題只記錄不立即處理 | 記錄不等於解決，必須當前 Wave 內處理 |

**執行原則**：
- 發現框架可改善時，**當前 Wave 內**建立 Ticket 並執行
- 框架修改 Ticket 的優先級自動提升為 P1（至少）
- 唯一允許延後的情況：框架修改依賴尚未完成的前置工作（技術阻塞，非時間阻塞）

---

### 規則 6.1：框架 ticket 版本歸屬補強

**框架 ticket 必須建在當前 active 版本，禁止建在 planned 狀態的未來版本**

> **來源**：規則 6 原條款規定「當前 Wave 內建立」但未明示「Wave 必須屬於 active 版本」。當 active 版本主題與框架 ticket 不符時，PM 易傾向放主題吻合的 planned 版本（如 W14-019 設計時 PM 內心傾向 v0.20.0 planned），實質延後框架改善並違反規則 6 本意。`version-progression.md` 已強制「.claude 工件歸活躍版本」，但規則 6 未交叉引用，造成 PM 漏看。

**「當前 active 版本」定義**：

| 來源 | 說明 |
|------|------|
| `docs/todolist.yaml` 中 `status: active` 的版本 | 與 `version-progression.md` 強制規則「活躍版本由 todolist.yaml 決定」「版本邊界以 active 為準」「.claude 工件歸活躍版本」一致 |
| 多個 active 版本（monorepo） | 建在最早完成的 active 版本 |
| 無 active 版本（罕見） | 先依 `version-progression.md` 啟用 planned 版本為 active，再建立 |

**情境處置表**：

| 情境 | 處置 |
|------|------|
| active 版本主題與框架 ticket 吻合 | 直接建在 active 版本對應 Wave |
| active 版本主題與框架 ticket 不符 | **仍建在 active 版本**，新建專屬「框架雜項」Wave 或借用最新 Wave |
| 多個 active 版本（monorepo） | 建在最早完成的 active 版本（L1 monorepo 版本） |
| 框架 ticket 跨多版本適用 | 仍建在當前 active 版本，於 ticket 中說明跨版本適用性 |

**禁止行為補強**：

| 禁止 | 原因 |
|------|------|
| 以「主題吻合度」為由放 planned 版本 | 「主題吻合」是次要考量；「立即執行」才是規則 6 本意 |
| 為避免「干擾現有版本規劃」放未來版本 | 框架 ticket 本質是「非版本主題的雜項」，不會干擾主題 |
| 在 AskUserQuestion 用 (Recommended) 暗示用戶選未來版本 | 違反規則 5 機制 4「反討好設計」（`ai-communication-rules.md`）；規則 6 同樣禁止 |
| 用「啟用未來版本」當建議選項規避 active 版本 | 啟用版本是版本規劃決策，不該為單一框架 ticket 變更 |

**Why**: 規則 6 與 `version-progression.md` 之間缺乏交叉引用，導致 PM 設計框架 ticket 時走「規則 6 → 主題吻合度判斷」路徑，跳過「version-progression.md → active 版本強制」路徑。本 session（W14-019 ticket 設計）即為實證案例。

**Consequence**: 框架改善若放 planned 版本，需等 planned 版本啟用才能執行，框架債務累積；其他相關 ticket 在等待期間重複支付成本（違反規則 6 上位原則）。

**Action**:

1. 建立框架 ticket 前先讀 `docs/todolist.yaml` 確認 active 版本。
2. 若 active 版本主題與框架 ticket 不符，仍建在 active 版本（新增「框架雜項」Wave 或借用最新 Wave）。
3. AskUserQuestion 提供版本選項時，禁止把 planned 版本標 (Recommended)（規則 5 機制 4）。
4. 若實在需要啟用 planned 版本（例如 active 版本即將完結），先走 `/version-release check` + 啟用流程，再建框架 ticket。

**與其他規則邊界**：

| 規則 | 關係 |
|------|------|
| `version-progression.md`「.claude 工件歸活躍版本」 | 本條款是規則 6 對該強制規則的明文引用 + 補強執行細節 |
| `monorepo-version-strategy.md` L1 權威來源 | 完全一致——L1 即 active 版本，Ticket 版本基於 L1 |
| `ai-communication-rules.md` 規則 5 機制 4 反討好設計 | 互相引用——本 session PM 違反規則 5 才暴露規則 6 漏洞 |
| `PC-121-pm-recommends-framework-ticket-to-future-version.md` | 本條款的反模式案例 + 防護記錄 |

---

### 規則 7：Memory 寫入必須評估跨專案升級

**寫入 feedback 類 memory 時，必須同時評估是否升級為框架規則**

> **來源**：W9-003 分析發現 PM 有 5/13（約 38%）的 feedback memory 僅存 memory 未升級，包含跨專案適用的原則（如「框架/產物分離」「Ticket 引導優先於 Hook」「/clear 前持久化」）。Memory 是**專案層級儲存**（`~/.claude/projects/<project>/memory/`），不會隨 `.claude/` sync 到其他專案；跨專案原則若僅存 memory，會在其他專案消失並可能重複踩同樣的雷。

**強制四問檢查**（寫入 feedback memory 時必須回答；目的地拿不準時先查 `.claude/methodologies/knowledge-carrier-allocation-methodology.md` 受眾 x 形態地圖）：

| 檢查問題 | 回答「是」的升級路徑 |
|---------|-------------------|
| 此原則對其他專案也適用嗎？ | 至少升級到 `.claude/` 框架層；否則加 `project_` 前綴標示為專案特定 |
| 此原則是通用品質或流程原則嗎？ | 預設升級至 `.claude/references/`；僅當屬「每回合都需遵守的行為禁令」且通過預算閘門（見下）時進 `rules/core/`（quality-baseline.md 加一行或速查 stub） |
| 此原則是 PM 行為規範嗎？ | 升級至 `.claude/pm-rules/`（按需層）；pm-role.md（自動載入）僅加路由行 |
| 此原則是單一代理人的身份 / 偏好嗎？ | 升級至 `.claude/agents/<name>.md`（內容邊界見 knowledge-carrier-allocation「代理人定義內容規範」節：偏好 / 邊界可裝，流程外移 skill） |
| 此原則是錯誤學習嗎？ | 升級至 `.claude/error-patterns/`（PC/IMP/ARCH 對應分類） |
| 此原則是流程方法論嗎？ | 升級至 `.claude/methodologies/` |
| 此原則是 Skill 引導嗎？ | 升級至 `.claude/skills/<skill>/` |

**升級目的地預算閘門**（W7-007）：升級目的地屬自動載入層（`rules/core/`、CLAUDE.md、rules/README.md、pm-role.md）時，必須先通過 `rules/README.md`「自動載入預算原則」自問——「這是否每回合都需要遵守？」答否一律改放按需層（references/ / pm-rules/ / error-patterns/），自動載入層至多加一行路由。**Why**：升級路徑若預設指向自動載入層，每次知識固化即膨脹一次，45k 預算單調耗盡（W7-004 根因「每次事故教訓傾向寫進自動載入層」的制度化版本）。寫入形態依 `document-writing-style.md`「載入層邊界」：自動載入層為禁令 + 路由，論證放按需層。

**四問都回答「否」才允許僅存 memory**（代表確為專案特定 context 索引）。

**升級後處理**（升級即搬家，非複製——W7-004.6 索引修剪原則成文化）：
- 原 memory 檔案頂部註明「本原則已升級為框架規則」並列出升級目的地路徑
- 自 `MEMORY.md` 索引**移除**該條目（MEMORY.md 每 session 自動載入，升級後保留索引行即雙重儲存；memory 單檔可保留供考古，對照關係記於升級 commit 或 ticket）
- 升級完成後才能視為「原則已落地」

**禁止行為**：

| 禁止 | 原因 |
|------|------|
| 以「之後再升級」為由僅寫 memory | 升級摩擦是永久性的，下次只會更不想動 |
| 寫入 feedback memory 時未執行四問檢查 | 評估缺失直接導致跨專案原則流失 |
| 將跨專案原則誤歸為「專案特定」以規避升級 | Memory 不是跨 session 知識庫，專案層級儲存不會自動傳播 |

**驗證方式**：定期（或每版本發布前）檢視 `MEMORY.md` 索引，確認每個 feedback 項目皆已標註升級位置或顯式標為專案特定。

---

## PM 品質檢查清單

以下兩項為 PM 專屬檢查（規則 1-5 的通用清單見 `quality-baseline.md`）：

- [ ] 發現框架可改善時，是否已在當前 Wave 建立 Ticket？（規則 6）
- [ ] 寫入 feedback memory 時已執行四問升級檢查？（規則 7，PC-061 / PC-160）

> **Auto-load 鏡像**：規則 7 的四問檢查項已鏡像至 `.claude/rules/core/quality-baseline.md` 通用檢查清單末端（W3-060），確保 PM auto-load context 含此檢查項。本檔為完整四問定義的權威來源；auto-load 層僅含指向本檔的提醒項。修改本規則時必須同步檢查 quality-baseline.md 鏡像項是否需更新。

---

## 底線要求總結（PM 專屬）

| 要求 | 說明 | 可協商 |
|------|------|--------|
| 框架修改優先於專案進度 | `.claude/` 改善不可因專案進度延後 | 否 |
| Memory 寫入必須評估升級 | feedback memory 必須執行四問檢查，跨專案原則須升級框架 | 否 |

---

## 相關規則

- `.claude/rules/core/quality-baseline.md` - 通用品質基線（規則 1-5，auto-load）
- `.claude/rules/core/pm-role.md` - 主線程角色行為準則
- `.claude/pm-rules/plan-to-ticket-flow.md` - Plan 轉 Ticket 流程
- `.claude/error-patterns/process-compliance/PC-061-memory-upgrade-blindness.md` - 規則 7 錯誤模式來源
- `.claude/skills/continuous-learning/skill.md` - Memory 升級流程 Skill

---

**Last Updated**: 2026-06-12
**Version**: 1.2.0 - 規則 7 升級路徑表補「單一代理人身份/偏好 → agents/<name>.md」分支（原六分支對偏好類教訓無目的地，fall through 誤置）+ 表前補知識載體地圖路由（W8 multi-round-review R3）
**Version**: 1.1.0 - 規則 7 新增「升級目的地預算閘門」（自動載入層需過「每回合都需要」自問，預設按需層）；升級後處理改「升級即搬家」（MEMORY.md 索引移除條目，修正與 W7-004.6 索引修剪實務的矛盾）（W7-007）
**Version**: 1.0.0 - 從 quality-baseline.md v1.9.0 規則 6-7 外移；auto-load 僅保留通用品質底線（規則 1-5），PM 情境專屬規則移至此處按需讀取（對應 0.18.0-W10-073.4 WRAP 選項 B）
