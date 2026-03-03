# 查詢流程決策樹

此決策樹描述 Ticket 查詢的完整流程。

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
