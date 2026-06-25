---
id: PC-APP-004
title: 症狀緩解累積偏誤——同一根因累積多個緩解機制而非根治
type: process-compliance
severity: medium
status: active
source: 0.37.0-W7-003 retrospective ANA（saffron）
related:
  - ARCH-007
  - ARCH-APP-002
---

# PC-APP-004: 症狀緩解累積偏誤（Symptom-Relief Accumulation Bias）

## 摘要

面對同一個根因的反覆症狀時，逐一建立緩解機制（guard hook / 補救流程 / 自動修復）——每個在建立時各自合理，但**累積的緩解數量本身是「根因未解」的信號，卻未被讀成觸發根治的警訊**。本案（ARCH-APP-002）對全域 namespace 碰撞建了 3 個緩解（`ticket-reinstall-hook` + `uv-tool-staleness-check-hook` + `uv-tool-ownership-guard-hook`），直到症狀外溢到用戶才根治。

## 症狀

| 症狀 | 觀察點 |
|------|--------|
| 同一根因有 >= 2 個獨立緩解機制 | 多個 hook / 重試 / 補救流程的 docstring 指向同一問題 |
| 緩解機制的註解明文寫出根因 | 「知道根因」卻仍在建緩解 |
| 每個緩解單看 diff 合理 | per-change review 無異常 |
| 症狀反覆出現、churn 持續 | 緩解只是延後/搶救，未消除問題 |

## 根因

- **沉沒成本**：每建一個緩解就增加對「緩解路線」的投入，切換到根治的心理成本上升。
- **局部最佳化**：每個緩解都是對「當前最痛症狀」的合理回應，但全局看是對同一根因的重複治標。
- **缺少複雜度觸發閥值**：沒有「同一根因的緩解機制達 N 個時必須質疑是否該根治」的強制檢查點。複雜度信號（緩解數遞增）無人讀。

## 防護

1. **觸發閥值規則**：當同一根因（同一 error-pattern ID / ARCH issue / 多個緩解 docstring 明文指向同一問題）的緩解機制達 **2 個**時，必須建立 ANA ticket 質疑「是否應根治根因而非繼續緩解」。**第 3 個緩解禁止**在無該 ANA 結論的情況下建立。
2. **建緩解時的自問**：寫 guard hook / 重試 / 補救流程前，先問「這是治標還是治本？根因是什麼？是否已有其他緩解處理同一根因？」若答案是「已有 >= 1 個」，停下走防護 1。
3. **複雜度信號當警訊**：cognitive-load 視角——多個機制處理同一問題是耦合/重複的味道，應觸發根因審查。

## 來源

0.37.0-W7-003 retrospective ANA（root cause 1）。動機案例 ARCH-APP-002（全域 namespace 碰撞，3 緩解累積後才根治）。相關 ARCH-007（作用域不匹配，本案的技術根因可由其推論）。
