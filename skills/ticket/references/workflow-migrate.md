# ID 遷移流程決策樹

此決策樹描述 Ticket ID 遷移的完整流程。

## ID 遷移決策樹

```
[ID 遷移]
    |
    v
┌─ 批量遷移? ─┐
│             │
否            是
│             │
v             v
/ticket       /ticket
migrate       migrate
<src> <tgt>   --config file.yaml
    │              │
    v              v
┌─ 預覽模式? ─┐    [批量處理]
│             │
是            否
│             │
v             v
--dry-run     [執行遷移]
```

**覆蓋指令**：

- [x] `/ticket migrate <src> <tgt>` - 單一遷移
- [x] `/ticket migrate --config file` - 批量遷移
- [x] `/ticket migrate ... --dry-run` - 預覽模式
- [x] `/ticket migrate ... --no-backup` - 停用備份
