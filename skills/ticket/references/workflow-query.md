# 查詢流程決策樹

此決策樹描述 Ticket 查詢的完整流程。

> **何時讀**：判斷 Ticket 查詢路徑時——查詢範圍選擇（全局摘要/版本進度/單一 Ticket/任務鏈/代理人）與詳細程度選擇（基本/詳細/完整/5W1H 單欄位）。**亦由此進入**：無（`grep -rn` 排除 `SKILL.md` 路由表本檔自身列、`track-command.md`／`architecture.md` 同目錄列後零命中，目前無其他檔案的步驟把讀者送到本檔）。
>
> **同目錄**：`track-command.md`（READ 操作對應的 CLI 子命令細節，決策樹在本檔、細節在那份）、`workflow-execute.md`（同屬 `track` 命令的 UPDATE 操作決策樹，與本檔互補）、`architecture.md`（系統模型與測試路徑推導）。
>
> **溯源**：本檔於本專案匯入 commit `f375ae675` 時即已存在，本機 git log 對本檔僅見這一筆，未見後續修改或外移點（可用 `git log --oneline -- references/workflow-query.md` 查證）。

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

**覆蓋指令**：

- [x] `/ticket track summary` - 全局摘要
- [x] `/ticket track version <ver>` - 版本進度
- [x] `/ticket track query <id>` - 基本查詢
- [x] `/ticket track full <id>` - 完整內容
- [x] `/ticket track log <id>` - 執行日誌
- [x] `/ticket track tree <id>` - 樹狀查詢
- [x] `/ticket track chain <id>` - 關聯鏈查詢
- [x] `/ticket track agent <name>` - 代理人進度
- [x] `/ticket track list [--status]` - 列出 Tickets
- [x] `/ticket track who|what|when|where|why|how <id>` - 5W1H 單欄位查詢
