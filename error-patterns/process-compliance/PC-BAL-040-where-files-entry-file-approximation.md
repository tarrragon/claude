---
id: PC-BAL-040
title: where.files 以模組入口檔近似宣告，漏列 AC 實際承載檔案
status: active
severity: medium
---

# PC-BAL-040: where.files 以模組入口檔近似宣告，漏列 AC 實際承載檔案

## 基本資訊

- **類別**: process-compliance
- **風險等級**: medium
- **發現日期**: 2026-08-18
- **關聯案例**: 2026-08-18 同一 session 連續兩例——multi-PM lease 子票的顯示層接線 AC、runqueue 群組切分子票的 CLI 接線 AC，均因承載檔未列入宣告而被範圍約束擋下

## 案例

2026-08-18 同一 session 連續兩例（multi-PM 協調層 Phase 3 實作波）：

1. lease 生命週期子票：AC 要求「STALE session 持票在 sessions/runqueue 輸出標 reclaimable」，但票面只宣告 CLI 入口分派檔，實際承載的 sessions 與 runqueue 兩個獨立命令檔未列入。代理人 SR 上報停手，PM `set-where` 擴入後於本票續完。
2. 群組切分子票：AC 要求 `--groups` 旗標接線，承載檔為 runqueue 獨立命令檔，票面同樣只宣告入口分派檔。同型 SR 往返、同型處置。

## 症狀

被派發的代理人回報 partial_success：某條 acceptance 需要修改的檔案不在票面 `where.files` 宣告範圍內，依「範圍外用 add-spawn-request 上報、不自行擴 scope」約束停手待裁決。同型缺口在單一 session 內連續出現兩次，每次多付一輪 SR 上報、PM 裁決、set-where 修正、續派的往返成本。

## 根因

PM 建票時以「模組入口檔 + 目錄」直覺近似 `where.files`（例：宣告 CLI 入口檔代表某子命令功能），未逐條 acceptance 反推實際承載檔案。當目標模組的子命令實作分散於多檔（入口分派檔與各子命令獨立檔並存）時，宣告與實際承載即出現缺口。缺口在派發前不可見——dispatch-readiness 對 where.files 與 acceptance 的一致性檢查採啟發式，無法驗證「每條 AC 的承載檔案都已列入」。

## 解決方案

事發時：PM 用 `ticket track set-where` 擴入實際承載檔案，`resolve-spawn-request --status dismissed` 註明「宣告缺口在 PM」，通知代理人於本票續完。缺口屬 PM 建票疏漏時修宣告，不另開票（避免把單一功能拆成人為兩票）。

## 預防措施

1. **建票時逐條 AC 反推承載檔案**：每寫一條 acceptance，先問「這條要動哪個檔？」用 grep/codegraph 定位實際檔案再寫入 where.files；禁止以模組入口檔或目錄名近似。
2. **派發 prompt 的授權範圍直接引用票面 where.files**，不在 prompt 另列一份清單——無同步機制的兩份清單會漂移，且 prompt 版本較窄時代理人會被錯誤約束擋下。
3. **代理人端行為正確，保持**：範圍外即 SR 上報停手是對的。本 pattern 的成本是一輪往返；擅自擴 scope 則是跨票汙染。勿因本 pattern 放寬代理人約束。

## 相關

- `.claude/rules/core/cognitive-load.md` dispatch-readiness 三閾值（閾值近似的已知限制）
- 同場景另一面：acceptance 建立後缺 add/edit/remove 修訂通道（另有專票追蹤；線索：ticket skill 的 set-acceptance 目前僅支援勾選/取消，發現於同一 multi-PM 協調層實作波）
