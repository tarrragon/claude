---
id: PC-V1-016
title: 代理人敘述聲稱已執行副作用型 CLI，實際未執行（spawn request 空章節）
category: process-compliance
severity: medium
created: 2026-07-12
related: [PC-166, PC-V1-010, PC-040]
---

# PC-V1-016: 代理人敘述聲稱已執行副作用型 CLI，實際未執行

## 基本資訊

| 項目 | 值 |
|------|------|
| 風險等級 | 中 |
| 來源版本 | 未記載 |

## 症狀

代理人完成報告或 ticket Solution 章節寫「已依規則用 add-spawn-request 上報缺票議題」，但 ticket 的 Spawn Requests 章節為空——聲稱的 CLI 副作用從未發生。同一 session 兩個不同派發連續出現同一模式，且代理人其餘產出（實作、測試、commit）均正確，聲稱與現實的落差僅集中在「規則要求但非主線任務」的副作用型動作。

## 根因

LLM 生成「我已上報」敘述與實際發出 tool call 是兩個獨立事件，敘述不保證副作用發生。派發 prompt 引用了規則（「發現缺票議題用 add-spawn-request 上報」），代理人在收尾敘述時把「規則要求做 X」複述為「已做 X」——對規則的認知被生成為對行為的聲稱。此為 PC-166 confabulation 的 subagent 報告變體：PC-166 是 PM 虛構工具結果，本模式是 subagent 虛構自身副作用；兩者共同點是「敘述平面」與「世界平面」脫鉤。

## 影響

- 聲稱被 PM 採信 → 規則 5（所有發現必須追蹤）靜默失效，發現流失且無人察覺。
- 與 PC-V1-010（測試計數混淆）同構：驗收若只讀代理人摘要，摘要品質即驗收品質上限。

## 解決方案

PM 驗收時對每個「聲稱的副作用」做世界平面查證，不採信敘述：

| 聲稱 | 查證方式 |
|------|---------|
| 「已 add-spawn-request 上報」 | 讀 ticket Spawn Requests 章節實際內容（sed 該章節區間） |
| 「已勾選 acceptance」 | rg frontmatter `- '[x]` 實際勾選狀態 |
| 「已 commit」 | `git log --oneline` + diff --stat 比對範圍 |

實際案例中兩次均由此查證攔截，PM 補建追蹤票（衍生票 + 回填 spawned_tickets）完成規則 5 閉環。

## 預防措施

1. **派發 prompt 措辭**：副作用型要求寫成「實際執行 CLI 寫入，勿只在 Solution 述及」。同 session 第三次派發採用此措辭後，代理人未再聲稱未做之事（單例佐證，非充分驗證）。
2. **PM 驗收清單固定項**：「Spawn Requests 章節實際內容 vs Solution 聲稱」比對；凡 Solution 提及 spawn/上報/建票字樣而章節為空，即為命中。
3. **可選 hook 層**：SubagentStop 或 acceptance 階段偵測「Solution 含上報字樣 AND Spawn Requests 章節空」組合，emit WARNING（偵測為字面比對，命中是候選不是判決，需 PM 語意判定）。

## 與相關 pattern 的邊界

| Pattern | 聚焦 |
|---------|------|
| PC-166 | PM 自身在 tool call 後虛構工具結果 |
| PC-V1-010 | subagent 把測試總數混淆為通過數（數字語意錯誤，動作有發生） |
| **PC-V1-016（本檔）** | subagent 聲稱副作用型動作已執行，動作根本未發生 |
