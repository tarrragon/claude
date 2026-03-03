# 交接與恢復流程決策樹

此決策樹描述 Ticket 交接和恢復的完整流程。

## 交接流程決策樹

```
[交接流程]
    |
    v
┌─ 知道方向? ─┐
│             │
否            是
│             │
v             v
/ticket       ┌─ 交接方向? ────────────────┐
handoff       │                            │
(自動判斷)    父任務        子任務        兄弟任務
              │             │             │
              v             v             v
         /ticket        /ticket       /ticket
         handoff        handoff       handoff
         --to-parent    --to-child    --to-sibling
                        <id>          <id>
                            │
                            v
                     [產生 Handoff 檔案]
                            │
                            v
                     [等待恢復]
```

**覆蓋指令**：

- [x] `/ticket handoff` - 自動判斷交接
- [x] `/ticket handoff --to-parent` - 返回父任務
- [x] `/ticket handoff --to-child <id>` - 切換到子任務
- [x] `/ticket handoff --to-sibling <id>` - 切換到兄弟任務
- [x] `/ticket handoff --status` - 查看交接狀態

## 恢復流程決策樹

```
[恢復流程]
    |
    v
┌─ 知道 ID? ─┐
│            │
否           是
│            │
v            v
/ticket      /ticket
resume       resume <id>
--list           │
│                v
v           [載入 Context]
[顯示待恢復]     │
     │           v
     └──────► [繼續執行流程]
```

**覆蓋指令**：

- [x] `/ticket resume <id>` - 恢復特定任務
- [x] `/ticket resume --list` - 列出待恢復任務
