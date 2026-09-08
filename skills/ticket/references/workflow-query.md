# 查詢流程決策樹

想知道 Ticket 現況，但不確定該查全局摘要、版本進度還是單一任務時，用本樹選對子命令。

> **何時讀**：需要選擇查詢範圍（全局摘要/版本進度/單一 Ticket/任務鏈/代理人）與詳細程度（基本/詳細/完整/5W1H 單欄位）時查閱。**亦由此進入**：`workflow-create.md` 首段引言句（任務已存在、要查現況時，從該檔判斷送至本檔）。
>
> **同目錄**：`track-command.md`（`summary`/`query`/`full`/`log`/`tree`/`chain`/`agent` 等 READ 子命令細節）、`workflow-execute.md`（UPDATE 操作決策樹）、`architecture.md`（系統模型與測試路徑推導）。
>
> **溯源**：匯入時已存在，無拆分點。

## 查詢流程決策樹

```
[查詢流程]
    |
    v
┌─ 查詢範圍? ──────────────────────────────────────────────────┐
│                                                               │
全局摘要      版本進度      單一 Ticket      任務鏈       代理人
│             │             │                │            │
v             v             v                v            v
/ticket       /ticket       ┌─ 詳細程度? ─┐  /ticket      /ticket
track         track         │             │  track        track
summary       version       基本   詳細   完整  tree/chain   agent
              <ver>         │      │      │    <id>        <name>
                            v      v      v
                         /ticket  /ticket  /ticket
                         track    track    track
                         query    log      full
                         <id>     <id>     <id>
                                     │
                                     v
                            ┌─ 查詢 5W1H 單欄位? ─┐
                            │                     │
                            是                    否
                            │                     │
                            v                     v
                     /ticket track            [查詢完成]
                     who|what|when|
                     where|why|how <id>
```

**本樹涵蓋的命令**：

- `/ticket track summary` - 全局摘要
- `/ticket track version <ver>` - 版本進度
- `/ticket track query <id>` - 基本查詢
- `/ticket track full <id>` - 完整內容
- `/ticket track log <id>` - 執行日誌
- `/ticket track tree <id>` - 樹狀查詢
- `/ticket track chain <id>` - 關聯鏈查詢
- `/ticket track agent <name>` - 代理人進度
- `/ticket track list [--status]` - 列出 Tickets
- `/ticket track who|what|when|where|why|how <id>` - 5W1H 單欄位查詢
