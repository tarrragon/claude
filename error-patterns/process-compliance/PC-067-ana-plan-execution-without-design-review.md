# PC-067: 執行 ANA 規劃時未質疑規劃本身的設計品質

## 錯誤症狀

PM 在 ANA Ticket 完成後執行其規劃內容（建立 follow-up tickets 或直接實作）時，傾向把 ANA Solution 視為「已驗證的設計」，直接執行，而**不質疑 ANA 規劃本身的設計品質**。典型表現：

- ANA Ticket 規劃出 N 個 follow-up tickets，PM 直接照單建立並執行，未審查方案品質
- ANA Solution 提出的「方法論抽象」「元架構」未經多視角驗證即被當作既定設計
- ANA 與執行 Ticket 由同一 PM 進行時，執行階段繼承 ANA 階段的同一視角偏誤
- 多視角審查在執行**完成後**才介入，不在執行**規劃時**介入

## 根因分析

### 表層原因：ANA Ticket 的 Solution 區段被視為「已決定」

ANA Ticket 的目的是「分析與規劃」，Solution 區段是分析產出。但執行階段的 PM 易將其當作「已通過審查的設計」，跳過質疑步驟。

### 深層原因：同一 PM 跨階段的視角繼承

ANA 與後續執行 Ticket 由同一 PM 主線程處理時，執行階段繼承 ANA 階段的所有設計假設、偏好、盲點。這違反多視角審查的核心精神——**獨立性**。

### 第三層原因：parallel-evaluation Use when 缺失「ANA 規劃完成後」明示

`parallel-evaluation` SKILL 原本列出的觸發時機聚焦在「程式碼 / 架構 / 重構 / 結論」，未明示「ANA Solution 規劃完成、follow-up tickets 建立前」這個關鍵節點。導致 PM 自然不會在此節點觸發多視角。

### 第四層原因：ANA 視角效率優化的副作用

ANA 階段為了快速產出方案，常採用「快速 WRAP」模式。快速模式以速度換深度，產出方案常含未經 Reality Test 的假設。執行階段若不補多視角，這些假設直接成為實作。

## 實際案例

### 案例：W10-008 執行 W9-004 規劃的「三層防護元架構」

W9-004（決策品質防護分析）規劃出 S2-S7 五個方案，包含「規則層 + Skill 層 + 持續層」三層防護元架構。W10-008 PM 直接執行此規劃：

- 6 處變更全部依規劃落地
- 過程中無人質疑「三層複寫同概念」是 DRY 違反
- 多視角審查（含 linux）在執行**完成後**才介入
- linux 視角直接給出 Acceptable 偏 Garbage 評分，揭示「元架構是空洞包裝」「WRAPCheck 是儀式稅」
- 用戶選擇全盤接受批評，回退 WRAPCheck 欄位、PC-066 改寫為「single source of truth + fallback」結構

**代價**：
- 完整實作 6 處變更後再回退其中 1 處（5w1h-format WRAPCheck）
- PC-066 文件需重寫核心抽象結構（從「三層元架構」改為「單點強制 + fallback」）
- 多視角審查的 context 成本（4 個代理人 + 整合決策）原可避免

**根本原因**：ANA Solution 區段被當作既定設計，未在執行**規劃時**啟動多視角審查。

### 案例：W10-012 claim 前未偵測前提已被上游否決（stale-premise 變體）

W10-012（2026-04-13 建立）規劃把 W9-002/003/004 共通「三層防護元架構」提煉為 methodology。在 W10-012 仍 pending 的兩天後（2026-04-15），PC-066 多視角審查後修訂，直接寫入「三者沒有可重用的『三層元架構』，將其抽象為通用結構是錯誤的概念升維」。又過 4 天（2026-04-19）接手 PM session 從 handoff 恢復 W10-012，若未獨立驗證前提，將照原計畫執行並再次重蹈 W10-008 覆轍。

**與 W10-008 的對比**：

| 維度 | W10-008（in-session blindness） | W10-012（stale-premise blindness） |
|------|------------------------------|----------------------------------|
| ANA 產出到執行的時差 | 同一 session 內執行 | 跨 6 天擱置後接手 |
| 視角換檔機會 | 無（同一 PM 連續執行） | 有（另一次 session 已否決前提）但未觸發同步檢查 |
| 失敗觸發點 | 執行中未質疑設計 | claim 前未偵測 AC 漂移 + 上游 PC 變更 |
| 已有防護 | 措施 1（parallel-evaluation SKILL Use when） | 措施 2（claim 自省）+ PC-055 AC 漂移（ticket CLI） |

**此變體凸顯的防護缺口**：

- pending 超過 N 天的 ticket 的**前提引用**（PC / methodology / 上游 ANA Solution）若在期間被修訂，ticket 本身無自動同步機制
- 措施 2「claim 自省」對 stale-premise 場景是**結構性低效**——PM claim 時記憶中 ANA 是「N 天前建立時的版本」，不會主動重讀上游 PC
- 現有 PC-055 AC 漂移偵測聚焦 S3/S4 外溢（上游已實作 AC），未覆蓋「上游 PC 否決了抽象本身」情境

**結果**（2026-04-19 session）：
- PM 接手時獨立驗證發現 PC-066 line 131-133 + PC-067 自身（W10-008 案例）已否決前提
- 透過 AskUserQuestion 將決策交給用戶，選擇「轉 complete 標 obsolete + 補 PC-067 案例章節」
- W10-012 本身成為本 PC 案例章節，以防護鏈閉合

**代價對比** W10-008：

| 代價項 | W10-008 | W10-012 |
|--------|---------|---------|
| 實作浪費 | 6 處變更後回退 1 處 | 0（claim 前偵測） |
| 文件改寫 | PC-066 核心抽象重寫 | 無 |
| context 成本 | 4 代理人多視角 + 整合決策 | 1 次 PM 前台驗證 + 1 次 AUQ |

W10-012 透過 claim 前驗證將代價壓至最低，驗證了「措施 2（claim 自省）+ 獨立驗證 + AUQ 決策路徑」可攔截 stale-premise 變體。

## 防護措施

### 措施 1：parallel-evaluation SKILL Use when 補強

`.claude/skills/parallel-evaluation/SKILL.md` description 已含「ANA Ticket 結論審查」「任何分析報告產出後」（W10-008 落地）。本錯誤模式進一步要求：**ANA Solution 規劃完成 + 建立 follow-up tickets 前**必須執行多視角，不可等執行**完成後**才補。

### 措施 2：執行 Ticket claim 時的設計品質自省

ANA 衍生的執行 Ticket（如 IMP / DOC type）認領時，PM 必須自問：

- ANA Solution 中的設計選擇是否已通過多視角審查？
- 若沒有，是否應在執行前先補審查？
- 我（執行階段 PM）是否與 ANA 階段 PM 是同一視角？是 → 多視角審查不可省

### 措施 3：ticket CLI claim 提示（待落地）

`ticket track claim` 在偵測 ticket 為「ANA 衍生」時，輸出提醒：

```
[提示] 本 Ticket 為 ANA 衍生（source: <ana_id>）。
       執行前建議先確認 ANA Solution 是否經過多視角審查。
       若無，可派發 parallel-evaluation 後再執行。
```

### 措施 4：ANA Ticket Solution 區段加註審查狀態

ANA Ticket 完成時 Solution 區段必須註明：

- [ ] 多視角審查狀態（已執行 / 未執行 / 不適用）
- [ ] 若未執行，理由（如：方案僅為事實陳述，非設計選擇）

未註明的 ANA Ticket 視為「未審查」，後續執行 Ticket 必須補審。

## 自我檢查清單

執行 ANA 衍生 Ticket 前自問：

- [ ] ANA Solution 區段是否註明多視角審查狀態？
- [ ] 若未審查，本執行 Ticket 是否包含設計選擇（非單純執行）？
- [ ] 若包含設計選擇，是否能識別 ANA 設計中的潛在 DRY / 過度設計風險？
- [ ] 若無法獨立識別，是否應派發 parallel-evaluation 含 linux 常駐委員？

任一答「否」→ 補多視角審查，或在執行 Ticket Problem Analysis 中說明跳過理由。

## 關聯

- **相關模式**：PC-066（決策系統未主動觸發，本模式為其執行階段的具體變體）
- **相關模式**：PC-063（ANA Premature Solution Convergence，本模式聚焦執行階段繼承 ANA 偏誤）
- **相關 Skill**：`.claude/skills/parallel-evaluation/SKILL.md`（措施 1 落點）
- **相關 Skill**：`.claude/skills/wrap-decision/SKILL.md`（執行階段觸發 WRAP 補審查）
- **本專案整合**：`.claude/skills/wrap-decision/references/project-integration/pseudo-widen-guard.md`（偽 Widen 防護，ANA 類型強制執行）
- **相關 ARCH**：ARCH-018（Hook × 架構規則衝突也屬同類「執行階段未質疑既定設計」）

---

**Created**: 2026-04-15
**Last Updated**: 2026-04-15
**Category**: process-compliance
**Severity**: P2（單次成本中等，但累積成本高——每個 ANA 都可能複現）
**Key Lesson**: ANA Solution 不是已驗證的設計，是「分析階段的方案草稿」。執行階段必須將 ANA 視為輸入而非結論，獨立啟動多視角審查（至少含 linux good-taste），特別是當 ANA 與執行由同一 PM 主線程處理時。多視角的價值來自獨立性，繼承同一視角的執行不是審查。
