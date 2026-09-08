# ID 遷移流程決策樹

ID 需要更動（重複、命名不符規範等）時，用本樹判斷該用單一遷移還是批量設定檔。

> **何時讀**：需要決定用單一遷移還是批量設定檔、是否先用預覽模式驗證時查閱。**亦由此進入**：無（grep 零命中）。
>
> **同目錄**：`migrate-command.md`（CLI 用法、前置檢查、collision detection 與備份機制）。
>
> **溯源**：匯入時已存在，無拆分點。

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

**本樹涵蓋的命令**：

- `/ticket migrate <src> <tgt>` - 單一遷移
- `/ticket migrate --config file` - 批量遷移
- `/ticket migrate ... --dry-run` - 預覽模式
- `/ticket migrate ... --no-backup` - 停用備份
