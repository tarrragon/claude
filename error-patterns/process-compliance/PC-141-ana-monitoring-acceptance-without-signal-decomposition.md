# PC-141: 監測類 ANA acceptance 未預先區分設計性偏差 vs 失效性訊號

## 基本資訊

- **Pattern ID**: PC-141
- **分類**: 流程合規（process-compliance）
- **來源版本**: v0.18.0
- **發現日期**: 2026-05-12
- **風險等級**: 中
- **相關 Pattern**: PC-063（ANA premature solution convergence）、PC-067（ANA plan execution without design review）、PC-054（analysis anchored on defense not quality）

---

## 問題描述

### 症狀

規劃監測類 / 校準類 / 後驗類 ANA ticket 時，acceptance criteria 用單一指標閾值作決策依據（例：「偏差率 > X% 觸發 Y / <= X% 結案」），但未在規劃階段預先區分該指標的**訊號類型**——什麼算「設計性偏差」（合理不對齊 / by design），什麼算「失效性偏差」（系統真正失效）。

### 表現形式

| 表現 | 說明 |
|------|------|
| Acceptance 用「對齊度」單一指標 | 例：「按 A 分級 vs 按 B 分級偏差率 > 30%」 |
| 規劃時假設「不對齊 = 失效」 | 未考慮兩個分級系統可能測量不同維度 |
| 執行才發現指標被 design-by-default 偏差 dominate | 主指標 86.7% 但其中 33% 是 over-restricted by design |
| 觸發的後續動作與測量本意脫節 | 例：偏差率高觸發「重啟設計」但實際 under-restricted = 0 表示系統健康 |
| Spawned ticket 需先修正測量框架才能繼續 | 規劃缺口轉嫁到下游 |

---

## W10-096 案例

### 時序

1. W10-030 結論：認知負擔三層攔截已足夠，建 W10-096 後驗校準作為「先驗證再決定是否擴展」（WRAP 選項 f）
2. W10-096 acceptance 寫入：
   - AC 2: 統計按類型 WRAP 深度與實際指數分級的偏差率
   - AC 3: 若偏差率 > 30% 則建立重啟 W10-030 設計的 ticket
   - AC 4: 偏差率 <= 30% 則標註三層攔截足夠，結案
3. 執行採樣 N=30，主指標 86.7%（> 30%），形式上觸發 AC 3
4. 但偏差細分發現：
   - Over-restricted (ANA 強制 full but idx 認為簡化) = 10/30 = 33.3% — by W10-028 design
   - Under-restricted (IMP/DOC 簡化但 idx 認為需 full) = **0/30 = 0%** — 真正失效訊號
5. 結論衝突：strict 讀法觸發「重啟設計」，但實際資料顯示三層攔截在「不漏網」目標**完全有效**
6. 化解：spawned W10-111 「重啟 W10-030 設計（含測量框架修正）」，把「修正 acceptance 測量框架」變成下游任務

### 根因推測

| 推測 | 描述 |
|------|------|
| A 規劃時兩個分級系統的維度差異未明示 | type-based 測「分析品質要求」，index-based 測「認知負擔閾值」，本就不該對齊 |
| B 假設「兩個系統應該對齊，偏差 = 失效」 | 未做 Reality Test 質疑此前提 |
| C Acceptance 寫成 if-else 二選一觸發動作 | 排除了「兩者都不適用」「需要重新定義測量」的中間狀態 |
| D 訊號類型決策被推遲到執行階段 | 規劃應預先回答「什麼算失效」，但實際在採樣後才浮現問題 |

最可能：A + B 共同作用——規劃時將兩個本質測量不同維度的分級系統假設為同構，未事先區分。

---

## 防護機制

### 已存在的相關防護

- PC-063 ANA Reality Test 強制：要求 ANA 在列方案前完成重現實驗，但未強制 acceptance 預先定義訊號分類
- PC-067 ANA 規劃直接執行未做設計品質審查：相關但聚焦規劃 vs 多視角審查
- `acceptance-gate-hook`：驗證 acceptance 全勾選，但無法檢驗 acceptance 本身設計品質

### 缺口

無 hook / 規則要求監測類 / 校準類 ANA 在 acceptance 中預先聲明「失效訊號定義」。Acceptance 可寫成單一閾值決策，閾值本身的訊號分解（什麼算失效）不在驗收範圍。

### 規則建議

1. **ANA acceptance writing checklist 增條款**：監測類 / 校準類 / 後驗類 ANA 的 acceptance 必須在 AC 中（或 Solution 預先寫入）回答：
   - Q1: 此指標的「失效訊號」如何定義？（哪些值算系統真正失效）
   - Q2: 此指標的「設計性偏差」是否可能存在？（哪些不對齊是 by design）
   - Q3: 若兩者共存如何拆解？（決策依據應為失效訊號還是總偏差）
2. **Phase 4 acceptance review**：ANA complete 前 acceptance-gate-hook 偵測「偏差率 > X% 觸發 Y」字面模式，提示確認是否已完成訊號分類
3. **Lavender-interface-designer 訓練**：規劃監測類 ANA 時，Phase 1 spec 模板新增「訊號分類」必填欄位

---

## 與 PC-063 / PC-067 / PC-054 的差異

| Pattern | 焦點 |
|---------|------|
| PC-063 | ANA 在列方案前必須完成重現實驗，防止 premature convergence |
| PC-067 | ANA 規劃直接執行未做設計品質審查，多視角能識破過度設計 |
| PC-054 | ANA 錨定於「防禦既有決策」而非品質評估 |
| **PC-141** | ANA 規劃時 acceptance 用單一閾值決策，未預先分解指標訊號類型 |

PC-063 / PC-067 / PC-054 聚焦 ANA **執行 / 收斂階段**的偏差；PC-141 聚焦 ANA **acceptance 設計階段**的偏差——前者問「分析品質」，後者問「驗收標準品質」。

---

**Last Updated**: 2026-05-12
**Version**: 1.0.0
**Source**: W10-096 後驗校準 ANA 完成時發現原 acceptance「偏差率 > 30% → 重啟設計」未區分設計性 (10/30 over-restricted by design) vs 失效性 (0/30 under-restricted) 偏差，主指標 86.7% 形式觸發重啟但實際資料顯示系統健康；化解為 spawned W10-111 修正測量框架
