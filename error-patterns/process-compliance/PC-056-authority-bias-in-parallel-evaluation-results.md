---
id: PC-056
title: parallel-evaluation 強勢視角結論直接轉執行 Ticket 而未經 WRAP 驗證
category: process-compliance
severity: high
first_seen: 2026-04-12
---

# PC-056: parallel-evaluation 強勢視角結論直接轉執行 Ticket 而未經 WRAP 驗證

## 症狀

- PM 在 /parallel-evaluation 產出報告後，看到強勢視角的極端評分（如 Linus Acceptable with fatal smell、建議廢除），立即建立對應的執行 Ticket（例如「廢除方法論」Ticket）
- 未對該強勢結論做 WRAP 擴增選項和機會成本檢驗
- Ticket 的 how.strategy 直接對應單一視角的建議，形成偽多視角決策（表面上有三視角，實際被單一強勢視角主導）
- 產出的執行 Ticket 可能朝「過度反應個別視角」的方向走（例如完全廢除 vs. 實際上分層拆分就夠了）

## 根因

PM 在面對三視角結論時有多重偏誤疊加：

| 偏誤 | 表現 | 觸發訊號 |
|------|------|---------|
| 權威偏誤 | Linus 被標記為「常駐委員」「Good Taste 把關」，其評分被視為最終品質判定 | 強勢措辭（Acceptable with fatal smell、Garbage、建議廢除） |
| 確認偏誤 | PM 對自己產出的自我懷疑，遇批評容易全盤接受 | 剛完成的產出被強烈批評 |
| 聚光燈偏誤 | 三視角中最嚴厲者吸引全部注意力 | 其他視角的溫和建議被忽視 |
| 結果偏誤 | 把「批評尖銳」等於「結論正確」 | 批評越尖銳 PM 越覺得該執行 |

根本原因：parallel-evaluation 產出的是**掃描結果**（發現了什麼），而非**決策結果**（該做什麼）。PM 誤將掃描結果直接當決策依據，跳過了應有的 WRAP 決策流程。

## 影響範圍

1. **框架決策品質**：方法論/規則/架構的重大變更可能朝錯誤方向執行，造成知識流失或過度重構
2. **資源浪費**：執行過度反應的 Ticket 投入大量工時，事後發現方向錯誤又要回退
3. **信心損失**：PM 的產出被輕易否定，影響後續主動建立框架文件的意願
4. **多視角機制失效**：parallel-evaluation 設計為多視角交叉驗證，但若被單一視角主導決策，等同退化為單視角審查

## 觸發條件

- 任何包含 linux 常駐委員的 parallel-evaluation 審查
- 審查結論含 Garbage / Acceptable with fatal smell 等強勢評分
- 審查對象是剛完成的高投入產出（新建方法論、大重構、新規則）
- 尤其危險：審查對象是 ANA Ticket 的產出（Ticket 本身被「評估」）

## 防護措施

### 強制流程

parallel-evaluation 產出報告後，若結論含以下任一特徵，**強制啟動 WRAP**：

| 特徵 | 範例 | 強制動作 |
|------|------|---------|
| 強勢評分 | Garbage / Acceptable with fatal smell | 啟動 WRAP 完整模式 |
| 建議完全廢除 | 「廢除此方法論/規則/功能」 | 啟動 WRAP 完整模式 |
| 大幅重構 | 「縮減至原本 30% 以下」 | 啟動 WRAP 快速模式 |
| 多視角共識否定 | 三視角都建議廢除 | 啟動 WRAP 完整模式 |

### WRAP 檢查重點

- **W 擴增**：強制爬梯子到至少 5 個光譜選項（不只「廢除 vs 保留」二元）
- **R 基本率**：檢查同類產出在專案的比例和使用情況（例如：廢除一個方法論前，查看其他同類方法論是否也該廢除）
- **A 機會成本**：執行該決策會錯過什麼正軌工作？
- **P Pre-mortem**：每個選項的失敗機率與代價

### 認知檢查

執行決策 Ticket 前，PM 應問自己：
1. 「我被單一視角的措辭強度影響嗎？」
2. 「如果 linux 的評分是 Acceptable（非 fatal smell），我會做相同決策嗎？」
3. 「三視角中，溫和視角的建議和強勢視角的建議有共通核心嗎？」（共通核心往往是真正的行動重點）

## 正確做法對照

| 錯誤做法 | 正確做法 |
|---------|---------|
| 看到 linux 建議廢除 → 建「廢除 Ticket」 | 看到 linux 建議廢除 → 執行 WRAP → 推薦方案 → 建對應 Ticket |
| 掃描結論 = 決策依據 | 掃描結論 = 決策**輸入**，WRAP 才是決策依據 |
| 三視角全部採納 | 三視角交叉驗證後提取**共通核心** |
| Ticket how.strategy 對應單一視角建議 | Ticket how.strategy 列出多選項評估 |

## 相關錯誤模式

- PC-054: 分析視角錨定在防禦性限制而非品質目標 — 同屬 PM 分析決策偏誤
- PC-051: 過早宣稱不可能 — 權威偏誤的近親（未檢驗替代方案）
- feedback_wrap_mandatory_for_analysis (memory) — ANA/Debug/提案必須主動用 WRAP

## 來源案例


**事件經過**：
1. 某 Ticket 建立 160 行方法論檔案
2. /parallel-evaluation 三視角審查（一致性/認知負擔/linux）
3. linux 評 Acceptable with fatal smell 建議廢除
4. PM 未經 WRAP 直接建某 Ticket「重構方法論」Ticket（方向傾向廢除）
5. 用戶糾正：「linux 的意見是一種觀點，應用 WRAP 納入相關評論想法，重新考慮不同的機會成本跟選項」
6. PM 執行 WRAP：擴增到 8 個光譜選項，基本率檢驗發現本專案 45 個方法論中 10+ 使用分類概念，推薦「分層拆分+修復」（選項 3），非廢除
7. Pre-mortem 顯示「廢除」選項有 30% 可能 3 年後需重建，「分層拆分」失敗率僅 20%

**損失**：未造成實際損失（用戶及時糾正）。若用戶未糾正，將朝錯誤方向執行某 Ticket。

**教訓**：parallel-evaluation 是**掃描工具**（findings），WRAP 是**決策工具**（decisions）。兩者不可互換。

---

**Last Updated**: 2026-04-12
**Version**: 1.0.0
