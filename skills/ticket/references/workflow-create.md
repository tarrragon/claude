# 建立流程決策樹

拿到新任務、不確定走 create 還是 track 時，先確認這是全新任務：若任務已存在（正在做或要查現況），改讀 `workflow-execute.md`／`workflow-query.md`；確定要新建才用本樹判斷根任務或子任務。

> **何時讀**：確定要建立新 Ticket、需要判斷是否為子任務並對應 `/ticket create`（含 `--parent` 子任務路由）的路由決策時查閱。**亦由此進入**：無（grep 零命中）。
>
> **同目錄**：`create-command.md`（`/ticket create` 的完整參數清單、必填條件與範例，本檔只給根/子任務的路由判斷）。
>
> **溯源**：匯入時已存在，無拆分點。

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

> decision-tree 三參數：`--decision-tree-entry` / `--decision-tree-decision` / `--decision-tree-rationale`，完整用法與必填條件見 `create-command.md`〈用法〉。

> 版本目錄不參與此決策：`ticket --help` 無 `init` 子命令，`create` 執行時以 `get_tickets_dir(version)` 自動建立版本目錄，無需前置初始化步驟。

**本樹涵蓋的命令**：

- `/ticket create ...` - 建立根任務（版本目錄不存在時自動建立）
- `/ticket create --parent <id> ...` - 建立子任務
