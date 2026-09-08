# 執行流程決策樹

任務已認領，接下來該怎麼操作——完成？更新欄位？批量處理？用本樹判斷。

> **何時讀**：Ticket 已認領後的執行、更新、批量操作或完成路徑，對應 `/ticket track` 系列 UPDATE 操作（`claim`/`complete`/`release`/`set-*`/`append-log`/`dispatch`/`batch-claim`/`batch-complete` 等）與完成判斷四步驟驗證、完成後同步提醒時查閱。**亦由此進入**：`workflow-create.md` 首段引言句（任務已存在、正在做時，從該檔判斷送至本檔）。
>
> **同目錄**：`track-command.md`（`claim`/`complete`/`release`/`set-*` 等子命令的旗標與輸出範例）、`workflow-query.md`（READ 操作決策樹）、`ticket-lifecycle-details.md`（驗收條件 4V 格式與 acceptance-gate-hook 細節）、`architecture.md`（系統模型與測試路徑推導）。
>
> **溯源**：匯入時已存在，無拆分點。

本檔章節：〈執行流程決策樹〉〈更新操作決策樹〉〈批量操作決策樹〉〈完成判斷決策樹〉〈完成後同步提醒〉。

## 執行流程決策樹

```
[執行流程]
    |
    v
┌─ Ticket 已認領? ─┐
│                  │
否                 是
│                  │
v                  v
/ticket track      ┌─ 任務完成? ─┐
  claim <id>       │             │
    │              是            否
    v              │             │
[開始執行]         v             v
                /ticket track   ┌─ 需要放棄? ─┐
                complete <id>   │             │
                   │            是            否
                   v            │             │
            [完成判斷]          v             v
                          /ticket track   [繼續執行]
                          release <id>        │
                               │              v
                               v         ┌─ 需更新狀態? ─┐
                          [任務釋放]     │               │
                                         是              否
                                         │               │
                                         v               v
                                    [更新操作]      [回到執行]
```

**本樹涵蓋的命令**：

- `/ticket track claim <id>` - 認領 Ticket
- `/ticket track complete <id> --as <agent>` - 完成 Ticket（`--as` 未提供即 deny，exit 1，見 track-command.md）
- `/ticket track release <id>` - 釋放 Ticket

## 更新操作決策樹

```
[更新操作]
    |
    v
┌─ 更新什麼? ─────────────────────────────────────────┐
│                                                      │
5W1H 欄位        Phase 狀態        驗收條件        執行日誌
│                │                 │               │
v                v                 v               v
/ticket track    /ticket track     /ticket track   /ticket track
set-{who|what|   phase <id>        check-          append-log
when|where|      <phase> <agent>   acceptance      <id> --section
why|how}                           <id> <index>    "Section" "Content"
<id> <value>
```

**本樹涵蓋的命令**：

- `/ticket track set-who|what|when|where|why|how <id> <value>` - 設定 5W1H
- `/ticket track phase <id> <phase> <agent>` - 更新 Phase
- `/ticket track check-acceptance <id> <index>` - 勾選驗收條件
- `/ticket track append-log <id> --section ...` - 追加執行日誌
- `/ticket track add-child <parent> <child>` - 添加子任務

## 批量操作決策樹

```
[批量操作]
    |
    v
┌─ 操作類型? ─┐
│             │
認領          完成
│             │
v             v
/ticket       /ticket
track         track
batch-claim   batch-complete
"id1,id2,id3" "id1,id2,id3"
```

**本樹涵蓋的命令**：

- `/ticket track batch-claim "ids"` - 批量認領
- `/ticket track batch-complete "ids"` - 批量完成

## 完成判斷決策樹

> **「先查後做」原則**：執行 complete 前，系統自動進行四步驟驗證。

```
[執行 /ticket track complete <id>]
    |
    v
┌─ Ticket 存在? ─┐
│                │
否               是
│                │
v                v
[Error]     ┌─ 狀態是 completed? ─┐
exit 1      │                     │
            是                    否
            │                     │
            v                     v
       [Info]              ┌─ 狀態是 in_progress? ─┐
       友好訊息            │                       │
       exit 0              否                      是
                           │                       │
                           v                       v
                      [Error]               ┌─ 驗收條件全完成? ─┐
                      阻止（pending/blocked） │                   │
                      exit 2                否                  是
                                            │                   │
                                            v                   v
                                       [Error]            [完成判斷]
                                       列出未完成項
                                       exit 1
```

```
[完成判斷]
    |
    v
┌─ 有子任務? ─┐
│             │
是            否
│             │
v             v
┌─ 子任務全完成? ─┐    [任務完成]
│                 │
否                是
│                 │
v                 v
[Error]           [任務完成]
阻擋，先完成       │
children          │
（--force 可旁路，exit 1）
```

## 完成後同步提醒

Ticket 完成後，系統會自動提示以下同步操作：

| 項目 | 說明 |
|------|------|
| Worklog 進度 | 自動追加完成記錄到主工作日誌 |
| Proposals 同步 | 若 Ticket 被 `proposals-tracking.yaml` 引用，需同步更新提案的 checklist 狀態和 `verified_by` 欄位 |
