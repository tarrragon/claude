---
id: PC-121
title: PM 推薦框架 ticket 至未來 planned 版本（規則 6 與 version-progression 引用斷裂）
category: process-compliance
severity: medium
status: superseded
created: 2026-05-03
related:
- pm-quality-baseline-rule-6
- pm-quality-baseline-rule-6.1
- version-progression
- ai-communication-rules-rule-5
- PC-066
---

# PC-121: PM 推薦框架 ticket 至未來 planned 版本

## Superseded 註記

本 PC 的前提與防護機制已被 scope 凍結模型（`.claude/pm-rules/version-progression.md`〈版本生命週期〉）取代，以下三點記錄取代理由；原文不刪，保留作為根因與觸發案例的歷史記錄。

- **前提不成立**：本 PC 的 Consequence 原主張「框架改善若放 planned 版本，需等 planned 版本啟用才能執行」。查證 `lifecycle.py` 對版本狀態零檢查，claim 不查版本狀態——任何版本（含 `planned`）下已存在的票，今天就能被 claim 並執行。執行資格與版本狀態早已解耦，「等啟用才能執行」的前提不成立。
- **框架問題的合法收件方已改變**：本 PC 撰寫時，框架 ticket 只能落在本地版本（active 或 planned 二選一）。現行規則下，抽象可攜、根源在 `.claude/` 通用資產的框架問題改路由至 canonical framework issue（見 `framework-issue` skill〈決策入口〉），不再是「該放 active 還是 planned」的二選一問題；只有該問題在本 consumer 的落地實作票才回頭建本地票。
- **防護目的由新機制滿足**：本 PC 意圖避免「重要框架改善被延後執行」。此目的現由「執行資格與版本狀態解耦」直接滿足——票一旦建立（無論掛哪個版本），即可立即 claim 執行，不需要靠「禁止放 planned 版本」這條規則來保證不被延後。

新規則見 `.claude/pm-rules/version-progression.md`〈版本生命週期〉與〈強制規則〉；`.claude/pm-rules/pm-quality-baseline.md` 規則 6.1 已同步補「已由 scope 凍結模型部分取代」註記。

---

## 問題描述

PM 設計 `.claude/` 框架改善 ticket 時，若當前 active 版本主題與框架 ticket 內容不符（如 active 版本目標為「測試重寫」、框架 ticket 屬「對話品質規則」），PM 會傾向推薦 planned 狀態的未來版本（理由：主題吻合度高、不干擾現有規劃）。實際違反 `pm-quality-baseline.md` 規則 6「框架修改優先於專案進度」與 `version-progression.md` 強制規則「.claude 工件歸活躍版本」。

PM 走「規則 6 → 主題吻合度判斷」路徑，跳過「version-progression.md → active 版本強制」路徑，因兩規則之間原本缺乏交叉引用（規則 6.1 補強之前）。version-progression.md 第 50 行「.claude 工件歸活躍版本，無需 Q1-Q4 判斷」是強制規則，但 PM 在規則 6 情境內不主動切換至 version-progression.md。

**Why**：規則間引用斷裂導致 PM 行為差距。規則 6 意圖明確（框架優先 + 當前 Wave 處理），執行細節漏掉「Wave 必須屬於 active 版本」。當 PM 內心偏好「主題吻合」勝過「立即執行」時，缺乏明文規則禁止延後框架改善至 planned 版本。

**Consequence**：框架改善若放 planned 版本，需等 planned 版本啟用才能執行（時間阻塞而非技術阻塞，違反規則 6 唯一允許延後條件）；framework debt 累積；其他相關 ticket 在等待期間重複支付成本。本 session 案例：W14-019 規則 5 設計若放 v0.20.0 (planned)，則本 session 內所有對話品質決策無強制框架支撐，依賴 PM 自律判斷。

**Action**：

PM 建立 `.claude/` 框架改善 ticket 時，必須依以下順序判斷：

1. 讀 `docs/todolist.yaml` 確認當前 active 版本（`status: active`）
2. 直接建在 active 版本（無論主題是否吻合）
   - 主題吻合 → 對應 Wave
   - 主題不符 → 新增「框架雜項」Wave 或借用最新 Wave
3. AskUserQuestion 提供版本選項時，禁止把 planned 版本標 (Recommended)（違反 `ai-communication-rules.md` 規則 5 機制 4）
4. 若需啟用 planned 版本（active 版本即將完結），先走 `/version-release check` + 啟用流程，再建框架 ticket

**禁止**：以「主題吻合度」「不干擾現有規劃」「將框架雜項放未來版本」為由推薦 planned 版本。

---

## 觸發案例

### 案例：W14-019 ticket 設計 session（2026-04-17）

PM 設計 W14-019（規則 5「權力不對等下的對話品質」設計，修改 `.claude/rules/core/ai-communication-rules.md`）時，內心傾向放 v0.20.0 (planned)，需用戶介入糾正才改放 v0.18.0 W14。

**決策過程**：

1. PM 確認 W14-019 屬框架改善（修改 `.claude/rules/core/ai-communication-rules.md`）
2. PM 查當前版本狀態：v0.18.0 active（測試重寫）、v0.20.0 planned（Tag 管理）
3. PM 內心傾向：v0.20.0 W1（理由：v0.20.0 還無 ticket 不會干擾既有規劃）
4. PM 嘗試 `ticket create --version 0.20.0`，系統回應：「版本 0.20.0 狀態為 planned（非 active）。只能在 active 版本中建立 Ticket。」
5. PM 透過 AskUserQuestion 將「啟用 v0.20.0 並建在 W1」標 (Recommended) — 違反規則 5 機制 4
6. 用戶選擇「v0.18.0 W14」（覆蓋 PM 推薦）
7. 用戶事後指出：「框架相關的 ticket 也都無條件放在當前版本，避免延後處理，這是規則上的缺失」

**根因分析**：

- 表層：規則 6 未明示「Wave 必須屬於 active 版本」
- 深層：規則 6 與 version-progression.md（已有 `.claude 工件歸活躍版本` 強制規則）缺交叉引用，PM 漏看
- 共振：PM 違反規則 5 機制 4（用 (Recommended) 暗示用戶選 v0.20.0），與規則 6 漏洞互為犯案環境

---

## 防護機制

| 機制 | 層次 | 說明 |
|------|------|------|
| 規則 6.1 補強條款 | 規則層 | `pm-quality-baseline.md` 規則 6.1 明示「active 版本強制 + planned 禁止 + 處置情境表」 |
| version-progression.md 交叉引用 | 規則層 | 規則 6.1「相關規則」表中明文引用 `.claude 工件歸活躍版本` 強制規則 |
| 規則 5 機制 4 | 對話層 | AskUserQuestion 禁止把 planned 版本標 (Recommended)，限縮 PM 推薦行為 |
| ticket create 系統強制 | 工具層 | 已強制「不能在 planned 版本建 ticket」（本 session 實證），但需配合 PM 不嘗試啟用 planned 版本 |
| 用戶 sanity check | 對話層 | 用戶有權覆蓋 PM 推薦（本 session 即為案例） |

**未來考慮（建監測 ticket，依 decision-trigger-binding 規則 2）**：

若本 PC 累積 3+ 案例（不同 session、不同框架 ticket 類型）仍出現 PM 推薦 planned 版本傾向，評估建立 Hook 攔截 PM 推薦未來版本的行為（暫不開 Hook，依形式 B 規則先行）。

---

## 相關規則與 ticket

- `.claude/pm-rules/pm-quality-baseline.md` 規則 6 / 6.1 — 本 PC 防護的主規則
- `.claude/pm-rules/version-progression.md` — 「.claude 工件歸活躍版本」強制規則來源
- `.claude/pm-rules/monorepo-version-strategy.md` — L1 monorepo 版本權威來源
- `.claude/rules/core/ai-communication-rules.md` 規則 5 機制 4 — 反討好設計
- `.claude/rules/core/decision-trigger-binding.md` — 決策合法狀態
- 0.18.0-W14-019 — 規則 5 設計（觸發 session）
- 0.18.0-W14-020 — 規則 6 補強分析 ticket（本 PC 落地任務）
- PC-066 — 決策品質自動駕駛（相關 PM 行為偏誤）

---

**Last Updated**: 2026-09-23
**Superseded by**: `.claude/pm-rules/version-progression.md`〈版本生命週期〉（scope 凍結模型）— 前提（`lifecycle.py` 對版本狀態零檢查，claim 不查版本狀態）、收件方變更（框架問題改路由至 canonical framework issue）、防護目的（執行資格與版本狀態已解耦）三點取代理由詳見上方「Superseded 註記」。
**Source**: 0.18.0-W14-020 ANA 落地產出
