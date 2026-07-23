---
id: PC-BAL-005
title: phase4-hook M1 正則觸發詞「評估」誤傷標準章節名「Phase 4 重構評估」（PC-113/138/144 同家族，跨 hook 復發）
category: process-compliance
severity: medium
source_ticket: 0.1.0-W2-016.1
related:
 - PC-113
 - PC-138
 - PC-144
---

# PC-BAL-005: 決斷強制 hook 觸發詞正則誤傷標準章節名

## 症狀

`ticket track complete <id>` 被 `phase4-decision-enforcement-hook.py` 阻擋，報「偵測到延後話術，禁止遞迴延後」，命中 `line NN [M1]: 「Phase 4 重構評估」`。但該行是 IMP ticket 的**標準 Phase 4 章節標題**「### Phase 4 重構評估」，其下結論為「重構需要：否」——完全合規，非延後話術。

## 觸發情境

| 條件 | 說明 |
|------|------|
| IMP/ANA ticket 的 Phase 4 結論用標準標題「Phase 4 重構評估」 | quality-baseline 規則 2 要求記錄 Phase 4，「重構評估」是最自然的章節名 |
| M1 regex 含觸發詞「評估」 | `Phase\s*[0-9]+[^\n]{0,30}?(?:再\|在)?(?:決定\|決斷\|判斷\|評估)` |
| 「Phase 4」與「評估」距離 <= 30 字（中間夾「重構」） | 完全落入 pattern 的 `[^\n]{0,30}` 窗口 |

## 根因（PC-113/138/144 同家族，載體換成 phase4-hook）

觸發詞正則無法區分「Phase X 再**評估**（真延後）」與「Phase 4 重構**評估**（標準章節名）」——與 PC-144 `\bTODO\b` 誤傷合規 TODO 描述、PC-138 `\bN/A\b` 誤傷 trade-off 表格 cell 同根因：**防呆 guard 的觸發詞比對沒有「合規術語豁免」層，同一個詞的合法用法與違規用法被一視同仁**。

本案的新意：此機制先前僅記錄於 `ticket_validator.py._is_placeholder`（PC-113/138/144），本案確認**同缺陷跨 hook 復發於 `phase4-decision-enforcement-hook.py` 的 M1 pattern**——證明這是防呆 hook 的通用設計盲點，非單一 validator 的個案。

## 防護措施

### Layer A：作者端（規避，已驗證可行）

| 規避 | 替代 |
|------|------|
| 「### Phase 4 重構評估」 | 「### Phase 4 審查結論」（避開觸發詞「評估」） |

### Layer B：hook 修復（治本，W2-017 追蹤）

M1 regex 排除標準章節名情形（如章節標題行 `^###?\s` 前綴 + 「重構評估」白名單，或要求觸發詞前有「再/之後/以後」等真延後錨點），保留「Phase N 再評估」的真延後偵測。W2-017（IMP）追蹤。

## 與家族其他成員的差異

| Pattern | 載體 hook | 觸發詞 | 合規用法被誤傷 |
|---------|-----------|--------|---------------|
| PC-113 | ticket_validator | 短英文標記無字邊界 | `TodoList` 中的 `Todo` |
| PC-138 | ticket_validator | `\bN/A\b` | trade-off 表格 cell |
| PC-144 | ticket_validator | `\bTODO\b`/`\bTBD\b` | 描述程式碼 TODO 註解 |
| **PC-BAL-005（本）** | **phase4-decision-enforcement-hook** | **「評估」（M1 pattern）** | **標準章節名「Phase 4 重構評估」** |

四者共同根因：guard 觸發詞比對無「合規術語豁免」層。系統性根除方向：所有防呆 hook 的觸發詞偵測都應內建「合法用法白名單/上下文豁免」，而非事後靠作者改寫繞過（違反「validator 應符合作者直覺」原則）。

## Action

| 情境 | 建議動作 |
|------|---------|
| 撞到本模式 | Phase 4 章節標題改「審查結論」等不含觸發詞措辭，記下 PC-BAL-005 防護成本 |
| 系統性根除 | 推進 W2-017 + 家族共用治本方案（guard 觸發詞加合規術語豁免層） |

---

**Last Updated**: 2026-07-22 | **Source**: 0.1.0-W2-016.1 complete 實測誤擋；W2-017 追蹤修復
