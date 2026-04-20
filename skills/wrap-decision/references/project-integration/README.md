# 本專案 WRAP 整合層

本目錄集中存放 WRAP 決策框架**在本專案的落地實作**：觸發條件對應、簡化三問 CLI 對齊、偽 Widen 本專案案例、源頭核對本專案案例、Step 0 個人化建議落地、pm-rules 索引、案例集。

---

## 依賴方向（關鍵架構）

```
通用 WRAP 規則                   本專案落地                     本專案系統組件
─────────────                    ─────────                      ──────────────
SKILL.md                    ←    本目錄                    ←    YAML / Hook
detailed-techniques.md                                           CLI / pm-rules
pm-checklist.md                                                  methodologies
tripwire-catalog.md                                              error-patterns
```

**規則**：
- 通用規則（SKILL 本體 + 同層 references）**不得引用本目錄或本專案任何組件**
- 本專案系統組件（YAML/Hook/CLI/pm-rules）引用本目錄，**不直接引用 SKILL**
- 本目錄可引用 SKILL 作為上游原理；可引用本專案系統組件作為下游落地

此方向允許 SKILL 跨專案複用：只需複製 SKILL.md + 同層 references，本專案特定內容（本目錄）留給各專案自行建立。

---

## 目錄清單

| 檔案 | 內容 |
|------|------|
| [triggers-alignment.md](./triggers-alignment.md) | YAML ↔ SKILL ↔ Hook 三層觸發條件對應；失敗判定、關鍵字清單、狀態追蹤、提醒訊息設計 |
| [simplified-three-questions.md](./simplified-three-questions.md) | 簡化 WRAP 三問（Claim 版）完整規格 — CLI Source of Truth；W/A/P 範本、ticket 類型差異、升級條件、反模式 |
| [pseudo-widen-guard.md](./pseudo-widen-guard.md) | 偽 Widen vs 真 Widen 本專案防護 — PC-063 案例、三層質疑步驟、警告信號、執行時機 |
| [source-verification.md](./source-verification.md) | 來源核對 — W10-064 案例、LLM 幻覺模式、逐項核對流程、反模式 |
| [personalized-advice.md](./personalized-advice.md) | Step 0 個人化建議落地 — 銜接 pm-rules/personalized-advice-rules 三層機制、PC-071 脈絡 |
| [pm-rules-map.md](./pm-rules-map.md) | pm-rules 索引 — decision-tree、incident-response、proposal-evaluation-gate 等與 WRAP 的銜接 |
| [case-studies.md](./case-studies.md) | 本專案 WRAP 案例集 — PC-051/063/066/067/071、W5-031、W10-009/027/028/052/056/064/075 |

---

## 讀取路徑

**場景 1：遇到 WRAP 觸發情境**
1. 先讀 SKILL.md 判定觸發類別
2. 若需要本專案可執行細節 → 查 `triggers-alignment.md`

**場景 2：Ticket claim**
1. CLI 會輸出簡化三問（`ClaimWrapMessages`）
2. 填答細節見 `simplified-three-questions.md`
3. ANA 類型升級完整 WRAP → 參考 `pseudo-widen-guard.md`

**場景 3：Bug 根因調查**
1. 讀 SKILL 的 W/R 階段原理
2. 讀 `pseudo-widen-guard.md` 執行三層質疑
3. 讀 `source-verification.md` 對清單類 agent 報告做核對
4. 查 `incident-response.md` Reality Test 閘門（透過 `pm-rules-map.md` 導航）

**場景 4：個人化建議**
1. 讀 SKILL 的 Step 0 通用原理
2. 讀 `personalized-advice.md` 了解本專案銜接
3. 執行時依照 `pm-rules/personalized-advice-rules.md` 三層機制

**場景 5：提案評估**
1. 讀 SKILL 完整 WRAP 原理
2. 查 `pm-rules/proposal-evaluation-gate.md`（透過 `pm-rules-map.md`）

**場景 6：理解歷史脈絡**
- 任何 PC/W 編號 → `case-studies.md`

---

## 新增內容時的維護原則

### 新增觸發訊號

1. 設計訊號（對應 SKILL 抽象類別）
2. 更新 `wrap-triggers.yaml`
3. 更新 `triggers-alignment.md`（對應表）
4. 更新 Hook 實作（從 YAML 讀取）
5. 更新 SKILL description（如需新關鍵字）

### 新增本專案防護機制

1. 確認是否為本專案特定（若通用 → 放 SKILL）
2. 建立新檔於本目錄
3. 更新本 README.md 的目錄清單
4. 更新 `pm-rules-map.md`（若關聯 pm-rules）

### 新增本專案案例

1. 建立 error-pattern（若對應 PC 編號）
2. 更新 `case-studies.md`（收錄情境、根因、衍生防護）
3. 更新相關 project-integration/ 檔案（若衍生新防護規則）

### 禁止操作

- **禁止修改 SKILL.md 引入本專案特定術語**（Ticket/Wave/CLAUDE.md/slash command 等）
- **禁止把本目錄內容往 SKILL 上搬**（即使看起來通用，先考慮是否有其他專案不適用的細節）
- **禁止多處複述觸發條件/關鍵字清單**（DRY，PC-066 教訓；指向 YAML 或 SKILL description）

---

## 跨專案複用 checklist

若要在其他專案使用本 wrap-decision skill：

1. 複製 `.claude/skills/wrap-decision/SKILL.md`
2. 複製 `references/detailed-techniques.md`、`pm-checklist.md`、`tripwire-catalog.md`
3. **跳過** `references/project-integration/` 整個目錄
4. 新專案自行建立 `references/project-integration/`，對應該專案的：
   - 任務管理系統（不必是 Ticket/Wave）
   - 決策諮詢規則（不必是 pm-rules）
   - 自動觸發機制（不必是 YAML/Hook，可以是別的）
   - 案例集

---

**Last Updated**: 2026-04-16
**Version**: 1.0.0 — 建立本專案 WRAP 整合層，從 SKILL.md 抽離本專案耦合內容
