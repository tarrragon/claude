# 建立流程決策樹

此決策樹描述 Ticket 建立的完整流程。

> **何時讀**：判斷 Ticket 建立路徑時——新任務或繼續任務判斷、是否為子任務，對應 `/ticket create`（含 `--parent` 子任務路由）的路由決策。**亦由此進入**：無（`grep -rn` 排除 `SKILL.md` 路由表本檔自身列與 `create-command.md` 同目錄列後零命中，目前無其他檔案的步驟把讀者送到本檔）。
>
> **同目錄**：`create-command.md`（建立流程的 CLI 用法與參數細節，與本檔互補：決策樹在本檔、參數細節在那份）。
>
> **溯源**：本檔於本專案匯入 commit `f375ae675` 時即已存在，本機 git log 對本檔僅見這一筆，未見後續修改或外移點（可用 `git log --oneline -- references/workflow-create.md` 查證）。

## 主流程判斷

```
[任務開始]
    |
    v
┌─ 是新任務? ─┐
│             │
是            否
│             │
v             v
[建立流程]    ┌─ 是繼續任務? ─┐
              │               │
              是              否
              │               │
              v               v
              [執行流程]      [查詢流程]
```

## 建立流程決策樹

```
[建立流程]
    |
    v
┌─ 是子任務? ─┐
│             │
是            否
│             │
v             v
/ticket create --parent <id>   /ticket create（根任務，除 --type DOC 外須含 decision-tree 三參數）
                              │
                              v
                        [Ticket 建立完成]
                              │
                              v
                        [進入執行流程]
```

> 版本目錄不參與此決策：`ticket --help` 無 `init` 子命令，`create` 執行時以 `get_tickets_dir(version)` 自動建立版本目錄，無需前置初始化步驟。

**覆蓋指令**：

- [x] `/ticket create ...` - 建立根任務（版本目錄不存在時自動建立）
- [x] `/ticket create --parent <id> ...` - 建立子任務
