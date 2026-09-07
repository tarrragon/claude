# ID 遷移流程決策樹

此決策樹描述 Ticket ID 遷移的完整流程。

> **何時讀**：判斷 Ticket ID 遷移路徑時——單一或批量遷移、是否使用預覽模式。**亦由此進入**：無（`grep -rn` 排除 `SKILL.md` 路由表本檔自身列與 `migrate-command.md` 同目錄列後零命中，目前無其他檔案的步驟把讀者送到本檔）。
>
> **同目錄**：`migrate-command.md`（遷移的 CLI 用法、前置檢查、collision detection 與備份機制細節，決策樹在本檔、細節在那份）。
>
> **溯源**：本檔於本專案匯入 commit `f375ae675` 時即已存在，本機 git log 對本檔僅見這一筆，未見後續修改或外移點（可用 `git log --oneline -- references/workflow-migrate.md` 查證）。

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
