---
name: ticket
description: "Use this skill whenever the user wants to create, track, query, or manage tickets. Triggers include: creating new tickets, claiming or releasing tickets, checking ticket status or progress, completing tickets, handing off work between agents, resuming interrupted tasks, migrating tickets between versions, converting plans to tickets, or any mention of /ticket, task tracking, or ticket lifecycle operations."
argument-hint: "<subcommand> [args]"
allowed-tools: Bash(ticket *), Read, Write, Edit, Grep, Glob
---

# Ticket System v1.0

統一 Ticket 系統 - 整合 create/track/handoff/resume/migrate/generate 六大功能。

---

## 重要：執行方式（必讀）

> **禁止直接執行 Python 檔案！** 直接執行 `.py` 檔案會導致 `ModuleNotFoundError`。

### 正確方式

```bash
# 使用已安裝的 ticket CLI（推薦）
ticket track summary
ticket track claim 0.31.0-W4-001

# 或在 ticket 目錄下使用 uv run
cd .claude/skills/ticket && uv run ticket track summary
```

### 錯誤方式（禁止）

```bash
# 以下方式會失敗，請勿使用
python3 .claude/skills/ticket/ticket_system/commands/track.py ...
python3 .claude/skills/ticket/ticket_system/scripts/ticket.py ...
```

**原因**：`ticket_system` 是 Python 套件，必須透過 `pyproject.toml` 定義的入口點執行，直接執行 `.py` 檔案無法解析套件內的導入。

---

## 執行方式

### 全局安裝（推薦）

全局安裝後可在任何目錄執行 `ticket` 指令。

```bash
# 首次安裝（只需執行一次）
cd .claude/skills/ticket
uv tool install .

# 安裝完成後，在任何目錄執行
ticket track summary
ticket track query 0.31.0-W4-001
ticket track claim 0.31.0-W4-001
```

**benefits**：

- 無需 cd 到 ticket 目錄
- 無需加上 `uv run` 前綴
- 全局可用，提升使用體驗

**修改原始碼後必須重新安裝**（IMP-023）：

```bash
# 修改 ticket_system/ 下的 .py 檔案後，必須用 --reinstall
uv tool install .claude/skills/ticket --reinstall

# 錯誤：--force 只更新執行檔，不更新套件程式碼
uv tool install .claude/skills/ticket --force  # 套件程式碼不會更新！

# 備用方案：清除快取後重新安裝
uv tool uninstall ticket-system && uv cache clean ticket-system && uv tool install .claude/skills/ticket
```

### 局部執行（不安裝）

如果不進行全局安裝，必須在 ticket 目錄下執行。

```bash
# 首次使用時初始化
cd .claude/skills/ticket
uv sync  # 只需要執行一次

# 執行命令
uv run ticket <command> [options]
```

### 常用範例

```bash
# 摘要
ticket track summary

# 查詢 Ticket
ticket track query 0.31.0-W4-001

# 認領 Ticket
ticket track claim 0.31.0-W4-001

# 完成 Ticket
ticket track complete 0.31.0-W4-001

# 建立 Ticket
ticket create --version 0.31.0 --wave 4 --action "實作" --target "XXX"
```

### 使用 SKILL 指令（透過 Claude）

```bash
/ticket <subcommand> [options]
```

> **注意**：直接執行 `python3 ticket.py` 會失敗，必須使用 `ticket` (全局) 或 `uv run ticket` (局部)。

---

## 無子命令時的預設行為

當用戶輸入 `/ticket`（無子命令或參數）時，依序執行以下流程：

1. **檢查待恢復任務** — 執行 `ticket resume --list`
   - **有待恢復任務** → 使用 AskUserQuestion 列出選項：
     - 各待恢復任務作為選項（label: `{ticket_id} - {title}`, description: `方向: {direction}`）
     - 用戶選擇後執行 `ticket resume <selected_id>`
     - 流程結束

2. **檢查待辦任務** — 執行 `ticket track list --status pending,in_progress`
   - **有待辦任務** → 使用 AskUserQuestion 列出選項：
     - 各待辦任務作為選項（label: `{ticket_id} - {title}`, description: `狀態: {status}`）
     - 額外選項：「建立新 Ticket」（description: `執行 /ticket create`）
     - 用戶選擇既有任務 → 依狀態處理（pending → claim，in_progress → 繼續執行）
     - 用戶選擇「建立新 Ticket」→ 引導進入 `/ticket create` 流程
     - 流程結束

3. **無任何待辦** → 顯示子命令總覽（下方表格）

---

## 統一命令格式

```bash
/ticket <subcommand> [options]
```

## 子命令總覽

| 子命令         | 用途                    | 範例                                                                          |
| -------------- | ----------------------- | ----------------------------------------------------------------------------- |
| `create`       | 建立新 Ticket           | `/ticket create --version 0.31.0 --wave 1 --action "實作" --target "XXX"`    |
| `batch-create` | 批次建立 Tickets        | `/ticket batch-create --template impl-parsley --targets "a,b,c" --wave 28`   |
| `track`        | 追蹤 Ticket 狀態        | `/ticket track summary`                                                       |
| `handoff`      | 任務交接                | `/ticket handoff 0.1.0-W1-002 --to-sibling 0.1.0-W2-003`                   |
| `resume`       | 恢復任務                | `/ticket resume <id>`                                                         |
| `migrate`      | Ticket ID 遷移          | `/ticket migrate 0.31.0-W4-001 0.31.0-W5-001`                                |
| `generate`     | Plan 轉換為 Tickets     | `/ticket generate plan.md --version 0.31.0 --wave 5`                         |

---

## 子命令詳細說明

各子命令的完整用法和參數說明，請參閱對應的 reference 檔案：

### create - 建立新 Ticket

建立 Atomic Ticket，支援 5W1H 引導式建立、子 Ticket 建立（create-child）、版本目錄初始化（init）。

> 決策樹：Read `references/workflow-create.md`
> 詳細用法：Read `references/create-command.md`

### batch-create - 批次建立 Tickets

從模板 + 目標清單快速建立多個 Tickets。適用於大量同質任務場景（如 30 個實作子任務）。

**使用情境**：
- W28 場景：快速建立 30 個相同類型的實作任務
- 需要多個同質 Ticket，避免逐一手工填寫

**命令格式**：
```bash
# 基本用法
ticket batch-create --template impl-parsley --targets "目標1,目標2,目標3" --wave 28

# 指定版本
ticket batch-create --template impl-parsley --targets "a,b,c" --version 0.31.0 --wave 28

# 預演模式（只顯示摘要，不建立檔案）
ticket batch-create --template impl-parsley --targets "a,b,c" --dry-run

# 建立子任務
ticket batch-create --template impl-parsley --targets "a,b" --parent 0.31.0-W28-001
```

**參數說明**：
- `--template` (必填)：使用的模板名稱（如 `impl-parsley`）
- `--targets` (必填)：目標清單，逗號分隔（如 `"BookCard Widget,LibraryListPage"`）
- `--version` (可選)：目標版本，預設自動偵測
- `--wave` (可選)：Wave 編號，預設為 1
- `--parent` (可選)：父 Ticket ID，用於建立子任務
- `--dry-run`：預演模式，只顯示摘要不建立檔案

**預定義模板**：
- `impl-parsley`：parsley-flutter-developer 實作 Ticket 模板（type: IMP, who: parsley-flutter-developer）
- 更多模板可在 `ticket_system/templates/` 目錄中定義

> 詳細設計：參考評估報告 `docs/work-logs/v0.31.0/tickets/0.31.0-W28-032.md`（CLI 設計、使用者體驗、批次操作流程）

### track - 追蹤和更新 Ticket 狀態

包含 READ 操作（summary/query/version/tree/chain/full/log/list/board/agent/5W1H）和 UPDATE 操作（claim/complete/release/set-who/set-what/set-when/set-where/set-why/set-how/phase/check-acceptance/append-log/add-child/batch-claim/batch-complete/audit/accept-creation）。`list` 支援 `--wave`、`--status`、`--format` 篩選參數。

> **注意**：僅有 6 個 `set-*` 命令（對應 5W1H 欄位）。`blockedBy`、`relatedTo`、`priority` 等欄位無 CLI 命令，需手動編輯 frontmatter。完整對照表見 `references/track-command.md`。
>
> **注意**：`append-log` 必須加上 `--section` 必填參數：`ticket track append-log <id> --section "Problem Analysis" "內容"`。有效區段值：`Problem Analysis`、`Solution`、`Test Results`。

> 決策樹：Read `references/workflow-execute.md` 和 `references/workflow-query.md`
> 詳細用法：Read `references/track-command.md`

### handoff - 任務鏈管理與 Context 交接

支援自動判斷方向、指定交接到父/子/兄弟任務。五種交接情境。

> 決策樹：Read `references/workflow-handoff.md`
> 詳細用法：Read `references/handoff-command.md`

### resume - 恢復任務

從 handoff 檔案載入 context。SessionStart hook 提醒 → 用戶 `/ticket` 或 `/ticket resume <id>` 觸發。

> 決策樹：Read `references/workflow-handoff.md`
> 詳細用法：Read `references/resume-command.md`

### migrate - Ticket ID 遷移

支援單一和批量遷移，自動更新所有 ID 引用和 chain 資訊。

> 決策樹：Read `references/workflow-migrate.md`
> 詳細用法：Read `references/migrate-command.md`

### generate - Plan 轉換為 Tickets

從 Plan 檔案自動生成 Atomic Tickets（Plan-to-Ticket 轉換）。

> 詳細用法：Read `references/generate-command.md`

---

## 參考資料

| 資料 | 說明 |
|------|------|
| `references/architecture.md` | 目錄結構、共用模組設計、自動化分析功能 |
| `references/workflow-create.md` | 建立流程決策樹 |
| `references/workflow-execute.md` | 執行+更新+批量+完成流程決策樹 |
| `references/workflow-query.md` | 查詢流程決策樹 |
| `references/workflow-handoff.md` | 交接+恢復流程決策樹 |
| `references/workflow-migrate.md` | ID 遷移流程決策樹 |
| `references/completeness-check.md` | 指令完整性驗證（39 個指令/選項覆蓋狀態） |
| `references/ticket-lifecycle-details.md` | Ticket 生命週期詳細規則 |

## 相關文件

- `.claude/methodologies/atomic-ticket-methodology.md` - Atomic Ticket 方法論
- `.claude/methodologies/ticket-lifecycle-management-methodology.md` - Ticket 生命週期管理
- `.claude/rules/flows/ticket-lifecycle.md` - Ticket 生命週期流程

---

**Version**: 2.3.0
**Last Updated**: 2026-03-11
**Status**: Completed

**Change Log**:

- v2.3.0 (2026-03-11): `/ticket` 裸指令新增待辦任務檢查步驟
  - 流程調整為三層：(1) 檢查 handoff → (2) 檢查 pending/in_progress 待辦 → (3) 顯示子命令
  - 待辦任務以 AskUserQuestion 列出，含「建立新 Ticket」選項
- v2.2.0 (2026-03-02): `/ticket` 裸指令自動檢查 handoff 待恢復任務
  - 新增「無子命令時的預設行為」章節
  - `/ticket` → 檢查 pending handoff → AskUserQuestion 選擇 → resume
  - 搭配 handoff-prompt-reminder-hook v2.0.0 停用自動接手
- v2.1.0 (2026-03-02): 決策樹拆分為 5 個 workflow 檔案（Progressive Disclosure）
  - `decision-trees.md`（327 行）拆分為 5 個按工作流分組的檔案
  - 各子命令說明新增對應決策樹引用
  - 參考資料表更新為 5 個 workflow 檔案
- v2.0.0 (2026-02-10): SKILL.md 拆分為入口 + references（0.31.0-W16-001）
  - 從 1273 行精簡為 ~170 行入口文件
  - 9 個子命令/架構/決策樹/完整性驗證移至 references/ 目錄
  - 遵循官方 Supporting Files 模式（SKILL.md < 500 行）
  - 保留執行方式和命令總覽作為入口必讀資訊
- v1.9.0 (2026-02-06): 語意化重命名 commands_messages_a/b (0.31.0-W12-002)
- v1.8.0 (2026-02-06): W7/W11 變更後文件一致性同步 (0.31.0-W12-001)
- v1.7.0 (2026-02-06): 文件同步更新 - 新增 generate/board/audit 文件 (0.31.0-W8-007)
