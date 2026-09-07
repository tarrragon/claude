# generate 子命令

從 Plan 檔案自動生成 Atomic Tickets（Plan-to-Ticket 轉換）。

> **何時讀**：從 Plan 檔案批次生成 Atomic Ticket 時——確認 `/ticket generate` 用法、參數說明（`--version`/`--wave`/`--dry-run`）或 Plan-to-Ticket 轉換流程（任務識別、type 分類、TDD Phase 順序映射、依賴關係識別）。**亦由此進入**：無（`grep -rn` 排除 `SKILL.md` 路由表本檔自身列後零命中，目前無其他檔案的步驟把讀者送到本檔）。
>
> **同目錄**：`create-command.md`（生成結果遵循相同的 type 分類規則，兩者常對照查閱）、`ticket-lifecycle-details.md`（生成結果需符合的 Ticket 建立格式範本）。
>
> **溯源**：本檔於本專案匯入 commit `f375ae675` 時即已存在，本機 git log 對本檔僅見這一筆，未見後續修改或外移點（可用 `git log --oneline -- references/generate-command.md` 查證）。

## 用法

```bash
# 從 Plan 檔案生成 Tickets
/ticket generate <plan_file> --version <version> --wave <wave>

# 預演模式（不實際建立檔案）
/ticket generate <plan_file> --version <version> --wave <wave> --dry-run
```

## 參數說明

| 參數        | 說明                           | 必填 |
| ----------- | ------------------------------ | ---- |
| `plan_file` | Plan 檔案路徑（Markdown 格式） | 是   |
| `--version` | 版本號（如 0.31.0）            | 是   |
| `--wave`    | 基礎 Wave 編號                 | 是   |
| `--dry-run` | 預演模式，不實際建立檔案       | 否   |

## 範例

```bash
# 正常生成
/ticket generate .claude/plans/feature-plan.md --version 0.31.0 --wave 5

# 預演（只顯示摘要，不建立檔案）
/ticket generate .claude/plans/feature-plan.md --version 0.31.0 --wave 5 --dry-run
```

## 流程

1. 解析 Plan 檔案中的實作步驟
2. 識別任務項目並分類（IMP/ADJ/DOC）
3. 根據任務類型映射 TDD Phase 順序
4. 自動識別依賴關係
5. 產生 Atomic Tickets 並保存

> 詳細流程：`.claude/pm-rules/plan-to-ticket-flow.md`
