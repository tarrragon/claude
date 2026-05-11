---
id: PC-134
title: ANA 自我指涉反諷（分析 X 反模式的 ANA 自身重蹈 X）
category: process-compliance
severity: high
created: 2026-05-08
source_ticket: 0.18.0-W17-167
related_pc:
  - PC-066
  - PC-093
  - PC-075
  - PC-091
related_arch: []
---

## 症狀

ANA 主題為「分析某個流程反模式 X」，但執行該 ANA 的代理人 / PM 在 complete 流程中**自身重蹈反模式 X**。最完美的反例：分析「acceptance 勾選不等於動作落地」的 ANA，自身 acceptance 全勾 `[x]`、Solution 寫了 spawn 規劃表格，但 frontmatter `spawned_tickets=[]`，complete 後 PM 才事後補建。

**辨識訊號**：

| 訊號 | 說明 |
|------|------|
| ANA 主題分析「規劃 vs 落地斷裂」 | 主題本身就是 acceptance 勾選與實際動作的差距 |
| Solution 含 spawn 規劃（IMP/DOC/ANA 表格 ≥ 1 項） | 寫了規劃 = 確認問題存在 |
| frontmatter spawned_tickets / children 為空 | 規劃未轉為實際 ticket |
| acceptance 全 `[x]` 且 saffron / 代理人自律 complete 通過 | 代理人從文字產出視角判定完成 |
| PM 驗收時才察覺缺口 | 缺口在 complete 之後才被人工發現 |

## 根因

**Root Cause 1：acceptance 設計只檢文字產出，不檢動作落地**

acceptance 條目「產出 spawned IMP/DOC 清單」對代理人語意是「在 Solution 寫表格」，對 PM 語意是「實際建立 ticket」。兩者語意差距無 hook 強制檢查，代理人勾選 `[x]` 即可 complete。

**Why**：acceptance 是可勾選的 checkbox，文字產出與動作落地共用同一條目時，較容易勾選的（文字）會成為實際標準。

**Consequence**：ANA Solution 規劃永久遺忘，違反規則 5（所有發現必須追蹤），重現 PC-093（無 trigger 延後決策累積）模式。

**Action**：拆分 acceptance 條目為「Solution 表格已寫」與「spawned_tickets 已填」兩條，或在 hook 強制比對。

**Root Cause 2：規則自律在壓力 / context 重量下系統性失效**

即使代理人讀過 quality-baseline 規則 5、ticket-lifecycle.md，正在分析「規劃落地斷裂」此問題時，仍會在 complete 流程中重蹈。此非「教育能解決」的個別疏失。

**Why**：自律機制與最需要它的場景負相關（PC-066 同構）。代理人 context 重量上升時，主動觸發「Solution 規劃 vs spawned_tickets 比對」的機率下降；ANA 完成時的成就感反而抑制最後一步驗證。

**Consequence**：規則層 / 行為層防護不足以兜底，必須加入 hook 強制層；否則歷史 ANA 持續累積漏建。

**Action**：以 hook 強制層攔截（W17-168），規則 / 行為層僅作自律訓練與認知降載。

**Root Cause 3：W17-168 hook 強制層在事件當下缺失**

acceptance-gate-hook Step 2.5 對 ANA 僅 warn 不 block；Step 2.5.1 已退場（W17-120.2 / PC-091）。Solution spawn 規劃 vs spawned_tickets 一致性無任何強制檢查。

**Why**：W17-120.2 將 spawned_tickets 重定位為弱 metadata 後，未補上替代強制檢查（語意比對而非單純存在性）。

**Consequence**：在 W17-168 上線前，所有 ANA 漏建均無自動防護，依賴 PM 人工驗收。

**Action**：W17-168 IMP 落地 ana_spawn_consistency_checker.py，將 Solution 表格行數 vs frontmatter ticket 數比對納入 complete 阻擋條件。

## 案例

**觸發案例（PC-134 命名動機）**：W17-162（2026-05-08）

ANA 結論「ANA spawn 規劃靜默遺忘」需固化防護。saffron-system-analyst 完成 W17-162 時 spawned_tickets 為空，PM 事後補建 4 張 ticket。

**完美元反諷自證案例**：W17-167（2026-05-08）

W17-167 主題即為「分析 ANA complete 前未建 spawned tickets 即放行的流程缺口」。執行紀錄：

| 項目 | 狀態 |
|------|------|
| status | completed（saffron 自律 complete） |
| frontmatter spawned_tickets | `[]`（complete 當下） |
| Solution 規劃 spawn 數 | 3（IMP P1 + DOC P2 × 2） |
| acceptance 勾選狀態 | 全 `[x]` 含「產出 spawned 清單」條目 |
| 實際補建時機 | PM 驗收時察覺，於 complete 後補建 W17-168 / 169 / 170 |

W17-167 完美重現自身分析的反模式：(1) Solution 寫了 3 張 spawn 規劃表格；(2) 勾選了 acceptance；(3) complete 時 spawned_tickets=[]。即使代理人正在分析此問題仍會犯，證明這不是教育能解決的疏失。

**歷史審計案例（saffron L1 審計）**：

| Ticket ID | 症狀 |
|-----------|------|
| W11-003.6 | spawned=0, children=0, 3 項 IMP 表格已確認漏建 |
| W17-041 | spawned=0, children=0, 10 處 spawn 規劃語句疑似漏建 |
| W17-065 | spawned=0, children=0, 3 處 spawn 規劃語句疑似漏建 |
| W17-008.12 | spawned=0, children=0, 5 處 spawn 規劃語句疑似漏建 |

至少 6 個歷史案例（含 W17-162 / W17-167），問題明確為系統性而非個案。

## 防護

採三層防護組合（強制層 + 自律層 + 行為層），對應 W17-167 ANA Solution 規劃：

| 層級 | Ticket | 機制 |
|------|--------|------|
| L2 Hook 強制層 | W17-168 | acceptance-gate-hook 新增 ana_spawn_consistency_checker.py：解析 Solution 章節 spawn 規劃表格行（`| (IMP\|DOC\|ANA) |` + `P[0-3]`），與 frontmatter spawned_tickets + children 數量比對；N > 0 且 S+C == 0 時阻擋 complete；豁免條件為 Solution 含「無需建 ticket」顯性標記 |
| L3 規則自律層 | W17-169 | quality-baseline 規則 5 延伸至「ANA Solution 內 spawn 規劃也是發現必須追蹤」；ticket-lifecycle.md ANA complete 條件補強；ticket-body-schema.md ANA Solution 章節新增「Spawn 落地確認」子節 |
| L4 行為層 | W17-170 | PM 派發 ANA 完成驗收時 checklist 三明示問題（Solution 表格 vs spawned_tickets 一致性 / 數量比對 / 豁免標記） |

**三層互補**：

- Hook 是強制層，防代理人遺漏（最重要兜底，本 PC 案例證明規則自律不足）
- 規則是自律層，防 PM 遺漏（Hook 未涵蓋的 edge case）
- 行為層是操作指引，降低 PM 認知負擔（驗收時不需重新推論）

**閉環驗證**：W17-168 hook 上線後，W17-167 自身應從反例變正例——若以同 prompt 重新派發 saffron 執行 W17-167，hook 應在 complete 前阻擋，要求補建 spawned_tickets。此為 W17-168 RED 測試的最強樣本。

## 同構連結

| 相關 PC | 同構點 |
|---------|--------|
| **PC-066**（decision-quality-autopilot） | 規則寫了但壓力 / context 重量下系統性失效；自律機制與最需要它的場景負相關。本 PC 是 PC-066 在 ANA spawn 場景的具體化 |
| **PC-093**（無 trigger 延後決策累積） | Solution 寫了規劃但無 ticket 追蹤 = 無 trigger 延後決策；規劃永久遺忘 = PC-093 累積後果 |
| **PC-075**（spawned children 狀態不對稱） | acceptance-gate 對 spawned 僅檢存在性不檢狀態；本 PC 進一步揭示「連存在性都不檢的 ANA 場景」更嚴重 |
| **PC-091**（spawned_tickets 弱 metadata 重定位） | PC-091 將 spawned_tickets 改為弱 metadata 後，未補上替代強制檢查，是本 PC Root Cause 3 的歷史成因 |

## 規則 6 失敗案例學習落地

依 quality-baseline.md 規則 6（失敗案例學習原則），本 PC 是失敗案例學習的具體應用：

1. **不回退既成工作**：W17-167 已 complete 且 spawned 補建完成，不回退或重派
2. **提煉教訓**：本 PC error-pattern 記錄元層級反諷現象與三層防護設計
3. **建 Ticket 追蹤**：W17-168 / 169 / 170 / 171 已建並依優先序排入 Wave
4. **固化為規則**：W17-169 將規則 5 延伸條款寫入 quality-baseline.md，使本案的教訓成為通用約束

## 與既有 PC 的邊界

| PC | 差異 |
|------|------|
| PC-066（decision-quality-autopilot） | PC-066 處理「Hook 偵測決策品質訊號 + WRAP 觸發」通用框架；本 PC 處理「ANA spawn 場景的元反諷」具體化案例 |
| PC-093（YAGNI deferred decision accumulation） | PC-093 處理「無 trigger 延後決策的累積後果」；本 PC 處理「ANA 在 complete 流程中產生無 trigger 延後」的源頭機制 |
| PC-075（spawned children status asymmetric） | PC-075 處理「acceptance-gate 對 spawned 僅檢存在性不檢狀態」；本 PC 處理「連 Solution 規劃與 spawned 存在性的比對都缺失」的更深層缺口 |

---

**Last Updated**: 2026-05-08
**Version**: 1.0.0 — 從 W17-167 元反諷案例（分析 X 反模式的 ANA 自身重蹈 X）提煉，記錄三層防護（W17-168 hook / W17-169 規則 / W17-170 行為）對應與規則 6 失敗案例學習落地
**Source**: 0.18.0-W17-167（元反諷自證案例）+ W17-162（觸發案例）+ saffron L1 審計（W11-003.6 / W17-041 / W17-065 / W17-008.12）
