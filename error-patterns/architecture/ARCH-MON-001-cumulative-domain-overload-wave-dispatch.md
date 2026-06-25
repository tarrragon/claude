---
id: ARCH-MON-001
title: 多 wave 票各加進同一中心檔，累積 domain 過載而無單票觸發閾值
type: architecture
severity: medium
status: active
source: 0.2.0-W4-003 Phase 4 parallel-evaluation
related:
  - ARCH-004
  - ARCH-009
  - cognitive-load
---

# ARCH-MON-001: 累積型 Domain 過載（wave 增量派發）

## 摘要

把單一功能拆成多個 wave ticket，每票各自把功能加進**同一個中心檔**，會使該檔累積 domain 過載——沒有任何單一 ticket 觸發 cognitive-load 的「單檔 >2 domain」閾值（每票只加一個 domain），但累積結果超標。本案 Flutter SDK 拆 W2-003（離線）/W2-004（自動攔截）/W2-005（lifecycle）三票各加進 `monitor.dart`，結束時該檔達 556 行、5+ domain，直到 Phase 4 才被審查發現。

## 症狀

| 症狀 | 觀察點 |
|------|--------|
| 單檔行數/domain 數隨 wave 推進單調膨脹 | 中心檔（單例/main class）持續被多票 append |
| 每票 diff 看似合理（只加一個功能） | per-ticket review 無異常 |
| `resetForTest()` 或初始化需手動歸零大量欄位 | 跨 domain 共享的可變狀態膨脹（耦合體溫計） |
| Phase 4 才發現超 cognitive-load 閾值 | 中途無攔截機制 |

## 根因

per-ticket 的認知負擔檢查只看單票增量，看不到跨票累積。wave-based 增量派發為了並行安全把功能切票，但多票指向同一中心檔時，膨脹發生在「票與票之間」，落在任何單票的審查視野之外。

## 防護

1. 派發「多票改同一中心檔」的 wave 前，**預判該檔最終 domain 數**；若預期累積 >2，規劃時即拆檔（每 domain 一檔/mixin/委派類別），而非全堆進一檔事後再拆。
2. Phase 4 parallel-evaluation 務必含「單檔 domain 混合」維度（本案 linux/parsley 據此發現，建拆分票）。
3. 拆分走獨立 wave + 既有測試當安全網 + **公開 API 凍結**（Never break userspace）。

## 來源

0.2.0-W4-003 Phase 4 三視角審查 → 拆分票 0.3.0-W1-005。專案 memory `cumulative-domain-overload-wave-dispatch` 升級（0.2.0-W4-005）。
