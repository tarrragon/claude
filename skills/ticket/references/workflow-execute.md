# 執行流程決策樹

此決策樹描述 Ticket 執行、更新、批量操作和完成判斷的完整流程。

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

**覆蓋指令**：

- [x] `/ticket track claim <id>` - 認領 Ticket
- [x] `/ticket track complete <id>` - 完成 Ticket
- [x] `/ticket track release <id>` - 釋放 Ticket

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

**覆蓋指令**：

- [x] `/ticket track set-who|what|when|where|why|how <id> <value>` - 設定 5W1H
- [x] `/ticket track phase <id> <phase> <agent>` - 更新 Phase
- [x] `/ticket track check-acceptance <id> <index>` - 勾選驗收條件
- [x] `/ticket track append-log <id> --section ...` - 追加執行日誌
- [x] `/ticket track add-child <parent> <child>` - 添加子任務

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

**覆蓋指令**：

- [x] `/ticket track batch-claim "ids"` - 批量認領
- [x] `/ticket track batch-complete "ids"` - 批量完成

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
                      阻止                  │                   │
                      exit 1                否                  是
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
[交接流程]        [任務完成]
```

## 完成後同步提醒

Ticket 完成後，系統會自動提示以下同步操作：

| 項目 | 說明 |
|------|------|
| Worklog 進度 | 自動追加完成記錄到主工作日誌 |
| Proposals 同步 | 若 Ticket 被 `proposals-tracking.yaml` 引用，需同步更新提案的 checklist 狀態和 `verified_by` 欄位 |
