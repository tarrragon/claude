---
id: PC-APP-005
title: ANA 建議方案的可行性驗證僅跑 happy path，前提與 UX 後果到 IMP 才暴露
type: process-compliance
severity: medium
status: active
source: 0.37.0-W7-003 retrospective ANA（saffron）
related:
  - ARCH-APP-002
  - PC-055
---

# PC-APP-005: ANA 建議未綁實測（Untested ANA Recommendation）

## 摘要

ANA 提出「全面取代既有機制」的建議方案並聲稱「已驗證可行性」，但驗證僅限「單一指令能跑」（happy path），未覆蓋 UX 變化與取代後的前提條件——這些未測面向在 IMP 階段才暴露，導致需 PM 介入修正方案。本案（W7-001）建議 `uv run --directory` 全面取代全域 install，實測僅跑一行 `ticket track list`，但 (a) 破壞 bare CLI 互動 UX、(b) 規劃移除 `[project.scripts]` 後 `uv run` 根本無法解析 CLI——最終改採 ANA 自己列的方案 4（shim）。

## 症狀

| 症狀 | 觀察點 |
|------|--------|
| ANA Solution 寫「已驗證可行性」但僅附 1 個指令 | 驗證證據單薄（happy path） |
| ANA 建議方案在 IMP 階段被推翻或大改 | ANA 結論 vs IMP 現實 gap |
| Solution 內部自相矛盾 | 如「已驗證」與「移除前提條件」並存 |
| 最終採用的是 ANA 列為次選/備選的方案 | 首選建議未經充分驗證 |

## 根因

- **確認偏誤**：找到一個能跑的指令即判定「可行」，未主動尋找反例或邊界。
- **可行性驗證標準過低**：「能跑」≠「可全面替代」。缺少「候選方案須覆蓋代表性場景」的要求。
- **分析未綁 spike**：設計建議在無實測/spike 下產出，可行性誤判直接進入 spawn 規劃。

## 防護

1. **代表性場景實測要求**：ANA 建議方案若涉及「全面取代既有機制」，其可行性驗證須至少覆蓋 **3 個代表性場景**：(a) happy path，(b) 與用戶互動的 UX 變化，(c) 取代後前提條件（config / dependency / entry point）是否仍成立。僅 happy path 通過**不可聲稱「已驗證可行性」**。
2. **Solution 自相矛盾檢查**：聲稱「已驗證」的方案，其 spawn 規劃不得含「移除被驗證指令所依賴的前提」（如移除 `[project.scripts]` 卻仍用 `uv run <cli>`）。
3. **與 PC-055 區隔**：PC-055 是「AC 已存在但未執行」（acceptance drift）；本 PC 是「ANA 可行性驗證的覆蓋面不足」（驗證做了但範圍太窄）。兩者皆為「驗證不充分」但層面不同。

## 來源

0.37.0-W7-003 retrospective ANA（root cause 3）。動機案例 W7-001 ANA（建議方案 1 在 IMP 階段被推翻，改採方案 4 shim）。
