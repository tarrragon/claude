# PC-V1-005: Acceptance 量化目標設定未考慮 substance 密度上限

## 分類

- 類型：Process Compliance（ticket 設計缺陷）
- 嚴重度：中（執行者陷入「達標 vs 守鐵則」二難，需 NeedsContext 中斷 + 用戶決策才能收口）
- 觸發頻率：中（任何「文件修剪 / 程式碼瘦身 / token 收斂」類 ticket 設定量化減量目標時皆可能）

## 症狀

- 修剪 / 瘦身類 ticket 的 acceptance 量化目標（如「減量 >= 40%」）執行後實得遠低於目標（如 20.8%）
- 執行者誠實執行 strategy 全部明細後仍無法達標，且達標路徑全數被 ticket 自身鐵則排除
- ticket 收口需 NeedsContext 補料流程 + 跨 session 用戶決策，產生額外往返成本
- acceptance 反覆勾選 / 取消勾選（commit 歷史出現「取消勾選 acceptance」類 chore）

## 根因

設定量化目標時以「檔案總量」為基數估計，未先盤點目標物的 substance 密度——載重表格（格式規範 / 閾值表 / 替代對照表）、導航中樞（路由表）、外部引用錨點（hook 引用的規則編號、閾值數字）均屬不可刪減範圍。當不可刪減部分佔比高（substance-dense），可修剪空間的誠實上限遠低於直覺估計。

**Why**：量化目標（40%）與保護性鐵則（substance 零刪失、修剪而非大幅外移、路由表完整保留）由同一張 ticket 同時宣告，但兩者的可滿足性從未交叉驗證；目標數字來自願望（token 預算缺口）而非來自 strategy 明細的逐項加總。

**Consequence**：執行者面臨三選一——(1) 刪 substance 達標（傷害載重規則，違反 quality-baseline 規則 6）；(2) 大幅外移達標（違反 ticket 鐵則）；(3) 誠實回報未達標（acceptance 無法 check，需中斷補料）。誠實執行者必然走 (3)，ticket 必然無法一次收口。

## 案例

- 1.0.0-W7-004.5：六檔 auto-load 修剪目標 >= 40%，strategy 明細全數執行後實得 20.8%；NeedsContext 三選一交 PM，用戶跨 session 兩度確認放寬至 >= 20% 後才 complete。同票 Problem Analysis 早已明示「pm-role 情境觸發路由必須完整保留」「cognitive-load 閾值數字不可動」，與 40% 目標的衝突在 create 時即可偵測。

## 防護

**Action**：

| 時機 | 防護 | 操作 |
|------|------|------|
| ticket create 時 | 量化目標必須由 strategy 明細逐項加總推導，禁止由預算缺口反推 | 先列「各檔保留 / 砍除明細表」，加總砍除量得出目標；無明細表時量化目標標註「待 Problem Analysis 盤點後校準」 |
| Problem Analysis 完成時 | substance 密度盤點與目標交叉驗證 | 盤點不可刪減範圍（外部引用錨點 grep、載重表格、路由表）；若不可刪減佔比與目標矛盾，立即 set-acceptance 校準，不等執行後才暴露 |
| 執行中發現衝突時 | 走 NeedsContext 流程，禁止為達標傷害 substance | 依 quality-baseline 規則 6 + ai-communication 規則 6（價值優於數字指標）誠實回報，衝突交 PM / 用戶決策 |

**識別訊號**：修剪類 ticket acceptance 同時含「減量 >= N%」與「X 完整保留」雙條件；目標數字無 strategy 明細加總支撐；Problem Analysis 的「保留」欄涵蓋大半內容但目標仍維持高減量比。

## 相關文件

- `.claude/rules/core/quality-baseline.md` 規則 6 — 失敗案例學習（不為達標數字傷害載重規則）
- `.claude/rules/core/ai-communication-rules.md` 規則 6 — 以價值 / 容量 / 優先級為決策依據
- `docs/work-logs/v1/v1.0/v1.0.0/tickets/1.0.0-W7-004.5.md` — 動機案例（NeedsContext 三選一全文）

---

**Last Updated**: 2026-06-12
**Version**: 1.0.0 — 自 W7-004.5 acceptance 門檻與 substance 鐵則衝突案例建立（症狀 / 根因 / 三時機防護）
