---
id: PC-BAL-055
title: 派發到 claim 的真空期未落票，pending 被誤讀為無人處理
category: process-compliance
severity: medium
created: 2026-08-24
---

# PC-BAL-055: 派發到 claim 的真空期未落票，pending 被誤讀為無人處理

## 基本資訊

- **類別**: process-compliance
- **風險等級**: medium
- **發現日期**: 2026-08-24
- **來源版本**: 0.2.1
- **關聯案例**: PM 以訊息派發 A 票給代理人甲（甲需先完成前置票 B 才能接手 A），稍後查 A 票狀態為 `pending`，判定「無人處理」轉派給空閒的代理人乙；甲隨即接手完成 A，所幸乙尚未動工，查證後無重複勞動

## 摘要

**PM 以自然語言訊息（Agent prompt / SendMessage）派發任務時，若未同步呼叫 `ticket track dispatch` 落票，派發意圖只存在於訊息紀錄，票面上與「從未被指派」完全無法區分。** `pending` 只表示「尚未 claim」，不表示「無人負責」；派發到 claim 之間存在一段真空——已指派、尚未接手——這段期間的歸屬只存在於訊息，PM 事後查票時看到的是一個與「從未被指派」語意相同的狀態，容易誤判為無人處理而轉派，造成潛在重複派工。

## 症狀

- PM 稍早以自然語言訊息指派一票（A）給代理人甲，甲因需先完成另一張前置票（B），尚未 `claim` A
- PM 之後執行 `ticket track query` / `ticket track full` 查 A 票狀態，看到 `status: pending`，與從未被指派的票在票面上完全相同
- PM 依「`pending` = 無人負責」的直覺，將 A 轉派給另一位空閒代理人乙
- 甲隨即完成 B，回頭 `claim` A 並開始執行，與剛被轉派的乙形成潛在重複派工
- 本次因乙尚未動工、事後查證工作區乾淨，未造成實際重複勞動，但風險結構已完整重現，下次未必能全身而退

## 根因

| 環節 | 事實 | 後果 |
|------|------|------|
| `pending` 語意單一 | 票面 `status` 只表達「尚未 claim」，不表達「是否已被指派」 | 已指派未認領與從未指派在票面上是同一個值，無法區分 |
| 派發動作只存在於訊息通道 | PM 以自然語言 prompt / SendMessage 派發，未寫入任何持久化欄位 | 派發意圖不進入任何可查詢的世界平面紀錄，PM 自己事後也查不到自己下過的派工指令 |
| 既有工具未被呼叫 | `ticket track dispatch <id> --as <agent> --note "..."` 早已存在，會把 `--note` 帶時間戳寫入該票「Problem Analysis」下「派發日誌」H3 子節；`assigned` 欄位仍只由 `claim` 寫入，`dispatch` 本身不改 `status` / `assigned` | 工具具備留痕能力但未被使用；即使呼叫了 `dispatch`，票的 `status` 依然顯示 `pending`——防護落在「派發日誌」章節有無內容，不在 `status` 值本身 |
| 轉派前無查核步驟 | PM 判定「無人處理」時未先讀「派發日誌」章節確認有無並行派發訊號 | 直接執行轉派動作，把已指派的工作二次外派 |

## 解決方案

1. PM 派發任何票給代理人時（無論即時可 `claim` 或需等前置票完成後才能接手），同步呼叫 `ticket track dispatch <ticket-id> --as <agent-name> --note "<派發原因，如：待 B 完成後接手>"`，把派發時間戳與備註寫入該票「Problem Analysis」下的「派發日誌」H3 子節。
2. 轉派或判定某票「無人處理」前，先執行 `ticket track full <ticket-id>` 讀「派發日誌」子節，確認有無已存在但尚未 `claim` 的派發紀錄；有紀錄且被指派者仍在忙前置票時，不轉派，等待或直接向該代理人查核進度。
3. `pending` 狀態不可單獨作為「無人處理」的充分證據——必須同時確認「派發日誌」章節是否為空，兩者皆空才視為真正未指派。
4. 若確認需要轉派（原指派者已明確釋出或逾時未回應），轉派前先以 SendMessage 詢問原指派對象是否仍打算接手，不僅憑票面狀態推斷。

## 預防措施

1. **工具預設行為改善（opinionated-default-design）**：評估在既有 `agent-dispatch-validation-hook.py`（Agent 工具的 PreToolUse hook）或新增 hook 中加一道提醒層——偵測 prompt 中的票 ID，若對應票近期無 `ticket track dispatch` 紀錄，印出 INFO 提醒。此為工具化防護的候選方向，可行性（如何從 prompt 可靠抽取票 ID、如何判定「近期」）與實作範圍留待獨立票評估，不在本模式記錄中預先決定設計（見同票 Spawn Request）。
2. 撰寫或修訂 `.claude/pm-rules/parallel-dispatch.md` 或 `.claude/references/pm-role-details.md`，補一條轉派前檢查項：先讀「派發日誌」章節。
3. 此模式跨專案可重現：任何「指派與認領分離」的任務系統都存在派發到認領之間的真空期，本模式的教訓（意圖需落地為可查詢紀錄，不能只存在於瞬時通道）可直接套用於其他 ticket / issue tracker。

## 關聯

- `PC-078`（並行 session 活躍）：處理的是「觀察到票狀態從 `pending` → `in_progress` 的變化，誤判變化來源」；本模式中票狀態從未離開 `pending`，落差在「該有紀錄卻沒紀錄」，票面看起來與從未被指派完全相同，觸發機制不同，不可互相取代判斷。
- `PC-076`（前 session 遺留）：處理的是靜態 git 工作區遺留的未 commit 檔案；與本模式的 ticket 派發語意無關。
- `.claude/rules/core/tool-output-trust-rules.md` 規則 5（記錄平面 vs 世界平面）：規則 5 處理「對話記憶」（記錄平面）與「filesystem / git / ticket」（世界平面）何者為準的信任誤判；本模式中 PM 查詢的 ticket `status` 本身就是世界平面且忠實反映事實（`pending` 為真），問題不是誤信記錄平面，而是世界平面裡「派發意圖」這個事實從未被寫入任何持久化欄位——是記錄手段缺失，不是記錄平面與世界平面之間的信任誤判，兩者性質不同故未擴充該規則，另立本模式記錄。
- `.claude/skills/ticket/ticket_system/commands/track_dispatch.py`：本模式建議防護措施的既有工具本體（`execute_dispatch` / `_append_dispatch_note`）。

## 案例

2026-08-23 session，本模式記錄者（PM）本人的轉派誤判事件。

PM 以訊息（非 `ticket track dispatch`）派發 A 票給代理人甲，甲因需先完成前置票 B 才能接手 A，當下未 `claim` A。稍後 PM 執行 `ticket track query` 查 A 票狀態，見 `status: pending`，未進一步確認是否已有派發紀錄，直接判定「無人處理」並轉派給當時空閒的代理人乙。

甲隨即完成 B，回頭 `claim` A 並開始執行。PM 查證乙的工作區與 A 票執行日誌，確認乙尚未動工、無任何檔案異動，本次未造成重複勞動。若乙已先一步開始實作，兩位代理人會對同一票產生衝突的產出，需額外成本釐清取捨。

事後追查根因：`ticket track dispatch <id> --as <agent> --note "..."` 子命令早已存在，會把派發備註帶時間戳寫入票的「派發日誌」章節，可作為 PM 事後查核的世界平面紀錄。本次 PM 全程以手寫 prompt 搭配訊息派發，未呼叫該命令，因此自己的派工意圖對自己不可見——不是工具缺席，是工具未被使用。
