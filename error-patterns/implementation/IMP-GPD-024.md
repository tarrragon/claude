---
id: IMP-GPD-024
title: plugin 在事件處理中主動以 session.send 傳跨 session 訊息，auto mode 的 classifier 因沒有對應的使用者請求而不給判定，訊息不送達；失敗只記 debug 通道時，與「沒觸發」同形
status: active
severity: 中
---

# IMP-GPD-024: plugin 事件中的主動跨 session 傳訊在 auto mode 下被拒，且失敗只記 debug 時無從分辨

## 基本資訊

- **Pattern ID**: IMP-GPD-024
- **分類**: 實作 bug（implementation）
- **來源版本**: 0.5.0
- **發現日期**: 2026-10-31
- **風險等級**: 中
- **影響範圍**: Claude Code plugin 在 `session.compact`、`session.end`、`prompt.submit` 等事件處理中呼叫 `$.session.send` 傳訊給其他 session 的設計；以及任何把「送出結果」只寫到 `$.ui.log(..., { to: 'debug' })` 的通知路徑

---

## 問題描述

### 症狀

一個 plugin 設計成：線 session 在 `/compact` 之後重新開工時，自動傳一行訊息給協調用的 session。單元測試全綠，合併後實測，接收端沒有收到任何訊息。

第一次實測時，傳送結果只寫進 debug 通道，而該 session 沒開 debug 記錄。「事件沒觸發」「判定為不送」「送出被拒」三種情況在可觀測面完全相同，只能推定，無法定位。補上一份持久的送出紀錄檔後重測，紀錄為：

```
source=compact	step=sent	isDelivered=false	reason=The server-side auto mode classifier gave no verdict for SendMessage: the request that produced this action did not ask for one. ...
```

判定、名稱比對、目標解析都通過，`$.session.send` 也確實發出，失敗點在平台的權限判定。

### 根因

auto mode 的 classifier 以「產生這個動作的請求」判斷是否放行。plugin 在事件處理中主動送訊時，沒有任何使用者請求要求這個動作，classifier 不給判定，平台因此不送出。這不是 plugin 的程式錯誤，而是平台的權限邊界：由事件驅動、未經請求的對外動作，在 auto mode 下不可預期能送達。

第二個根因是可觀測性：送出結果只記在預設不可見的 debug 通道，使第一次實測的失敗無法歸因，多花了一輪實測。

---

## 解決方案

1. 不把「事件中主動跨 session 傳訊」當成主管道。主管道改用被動、可查的狀態：寫入狀態檔（例如用量檔的 phase 欄位），由接收端在讀取看板或呼叫查詢工具時讀到。
2. 主動傳訊保留為可關閉的副功能，以具名常數控制，預設關閉。
3. 不設法讓 classifier 放行。拒絕訊息中「重送一次」是給模型的指示，不是給 plugin 自動重送的；改換送出時點（例如等使用者送出 prompt 之後才送）同樣是在繞過權限判定。
4. 每一次送出（含判定不送與開關關閉）都寫一行到持久的紀錄檔，欄位含走到的步驟與平台回傳的拒絕原因，並設行數上限。

---

## 預防措施

- 設計 plugin 或 hook 的對外動作（跨 session 傳訊、外部呼叫）前，先問：這個動作有沒有對應的使用者請求？沒有的話，在 auto mode 下視為可能被拒，主管道改用被動狀態。
- 通知路徑的每個分支（不送的理由、送出結果、例外）都要寫到預設可見的持久位置，不只記 debug；否則「失敗」與「沒觸發」同形（`.claude/rules/core/quality-baseline.md` 規則 4）。
- 合併後的實測安排，把「讀紀錄檔判讀走到哪一步」列為驗收步驟，不只看接收端有沒有收到。

---

## 關聯

- 發現情境：2026-10-31，line-board plugin 的恢復開工通知，兩次 `/compact` 實測
- 相關：`.claude/skills/multi-session-orchestration/references/line-continuity.md`〈線 session 的恢復開工通知〉的〈已知限制〉（該限制的使用者面說明）
- 相關：`PC-GPD-020`（明示的選擇與預設不可區分，同屬「可觀測面同形」家族）
- 相關：`.claude/rules/core/quality-baseline.md` 規則 4（失敗必須可見）
