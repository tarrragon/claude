---
id: TEST-MON-002
title: TDD Phase 2 紅燈設計漏 handler/lifecycle 行為測試；GREEN agent confidence<1.0 是補洞訊號
type: test
severity: medium
status: active
source: 0.2.0-W2-004/W2-005 GREEN agent confidence 回報
related:
  - TEST-MON-001
  - PC-168
  - tdd
---

# TEST-MON-002: Phase 2 行為測試缺口

## 摘要

TDD Phase 2 紅燈測試設計容易漏掉「行為複雜但無單一回傳值」類功能的測試——自動攔截（FlutterError.onError/PlatformDispatcher）、lifecycle（WidgetsBindingObserver paused/detached）、Isolate 訊息都只有實作、無專屬 RED 測試。GREEN agent 依 SPEC 完整實作後**誠實回報 confidence < 1.0 並指出「行為僅有實作、無測試覆蓋」**，這是 Phase 2 缺口的訊號，PM 據此補建測試票（對既有實作直接通過）。

## 症狀

| 症狀 | 觀察點 |
|------|--------|
| GREEN agent Exit Status confidence 0.85/0.95（非 1.0） | task-notification result |
| agent 主動標「behavior 僅有實作、無測試覆蓋」 | reason / notes 欄 |
| 唯一轉綠的紅燈是周邊欄位（如 source field），核心行為無紅燈 | acceptance_met 對照測試檔 |
| 功能類型為 handler 註冊 / callback / 事件驅動 / 跨 isolate | FR 性質 |

## 根因

Phase 2 設計者傾向為「有明確輸入輸出」的 FR 寫測試（API 回傳、查詢結果），對「註冊 handler 後副作用觸發」「lifecycle callback 行為」「跨 isolate 訊息」這類行為覆蓋不足。GREEN-by-spec 能讓功能正確，但行為無回歸保護。

## 防護

1. Phase 2 設計時，對 handler/callback/lifecycle/事件驅動類 FR **主動列行為測試**（驗證 chain 呼叫、dedup 窗口、flag off 不註冊、副作用觸發）。
2. **GREEN agent 回報 confidence < 1.0 並標「behavior 無測試覆蓋」時，視為補洞訊號**，立即建測試補建票，不要當可接受 noise。本案兩次此訊號都正確指向 Phase 2 缺口。
3. Phase 4 parallel-evaluation 含「行為測試覆蓋」維度交叉確認。

## 來源

0.2.0-W2-004（自動攔截）/W2-005（lifecycle）GREEN confidence 訊號 → 補建票 W2-012（10 test）/W2-006（4 test）。專案 memory `phase2-behavioral-test-gap` 升級（0.2.0-W4-005）。
