# 決策樹 — 代理人管理 Domain

> 本文件從 decision-tree.md 按 DDD domain 邊界拆分。
> 路由入口：.claude/pm-rules/decision-tree.md
> 來源：0.17.2-W3-007.1

---

## 代理人觸發優先級

> 觸發優先級表已合併至 dispatch-gate.md（派發閘門），統一在派發前參考。

| 觸發組合 | 處理方式 |
|---------|---------|
| 錯誤 + 任何 | incident-responder 先處理 |
| SA + security | SA 先審查架構 |
| 多個專業代理人 | SA 協調或分解為多 Ticket |

---

## 派發記錄要求

所有 Ticket 必須包含 `decision_tree_path` 欄位（entry_point、final_decision、rationale）。

---

## 強制執行命令

| 情境 | 強制命令 |
|------|---------|
| 錯誤/失敗發生 | `/pre-fix-eval` |
| Phase 4 完成 | `/tech-debt-capture` |
| 版本發布前 | `/version-release check` |
| 用戶決策確認 | AskUserQuestion（17 個場景，詳見 askuserquestion-rules.md） |
| Commit 後 | AskUserQuestion #16（錯誤學習）→ #11（Handoff 確認） |
| 流程省略偵測 | AskUserQuestion #12（省略確認） |
| **執行中發現技術債/問題/回歸/超範圍需求** | **`/ticket create` 建立 pending Ticket（立即，不詢問，不延後）** |
| **ANA Ticket 完成前** | **確認 children 或 spawned_tickets 非空（PC-017）+ AC 覆蓋率 100%（PC-041）** |
| **派發代理人前** | **派發前複雜度關卡：認知負擔指數 > 10 必須先拆分（W15-004）** |

---

## 違規處理

| 違規行為 | 處理方式 |
|---------|---------|
| 跳過 incident-responder 直接修復 | 停止，回滾，重新走流程 |
| 未建立 Ticket 就開始實作 | 停止，先建立 Ticket |
| 跳過 SA 前置審查（新功能） | 停止，派發 SA |
| 跳過 Phase 4 | 強制執行 Phase 4 |
| 計畫執行中發現額外需求未立即建立 Ticket | 補建 Ticket，記錄遺漏原因 |
| ANA Ticket 完成時無後續 Ticket（PC-017） | 阻塞完成，先建立修復+防護 Ticket |
| **跳過複雜度關卡直接派發** | **停止派發，執行認知負擔評估，超標則先拆分** |

---

**Last Updated**: 2026-04-09
**Version**: 1.1.0 - 觸發優先級合併至 dispatch-gate.md + 優先級表分離（W9-003/W8-001.4）
