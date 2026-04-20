# create 子命令

建立 Atomic Ticket，遵循 5W1H 引導式建立。

## 基本用法

```bash
# 建立根任務（必須提供 decision-tree 三參數）
/ticket create --version 0.31.0 --wave 1 --action "實作" --target "XXX" \
  --decision-tree-entry "第五層:TDD" \
  --decision-tree-decision "Phase 完成後建立 Ticket" \
  --decision-tree-rationale "quality-baseline-rule"

# 完整 5W1H 建立 + 決策樹
/ticket create \
  --version 0.31.0 \
  --wave 1 \
  --action "實作" \
  --target "XXX" \
  --who "parsley-flutter-developer" \
  --what "任務描述" \
  --when "Phase 3b 開始時" \
  --where-layer "Domain" \
  --where-files "lib/path/to/file.dart" \
  --why "需求依據" \
  --how-type "Implementation" \
  --how-strategy "TDD 循環" \
  --priority "P1" \
  --decision-tree-entry "第五層:TDD" \
  --decision-tree-decision "Phase 完成後建立 Ticket" \
  --decision-tree-rationale "quality-baseline-rule"

# 建立子任務（可省略 decision-tree 參數）
/ticket create --parent 1.0.0-W1-001 --action "更新" --target "XXX"

# 建立衍生任務（與 --parent 互斥，見下方「--parent vs --source-ticket」章節）
/ticket create --version 0.31.0 --wave 1 --action "實作" --target "XXX" \
  --source-ticket 0.18.0-W17-001 --type IMP

# 建立 DOC 類型（可省略 decision-tree 參數）
/ticket create --version 0.31.0 --wave 1 --action "撰寫" --target "工作日誌" --type DOC

# 初始化版本目錄
/ticket init 0.31.0
```

**重要**：建立根任務時，必須提供 `--decision-tree-entry`、`--decision-tree-decision`、`--decision-tree-rationale` 三個參數。只在以下情況可省略：
- 建立子任務（使用 `--parent` 參數）
- Ticket 類型為 DOC（`--type DOC`）

## 類型說明

| 類型           | 代碼 | 用途             |
| -------------- | ---- | ---------------- |
| Implementation | IMP  | 開發新功能       |
| Testing        | TST  | 執行測試驗證     |
| Adjustment     | ADJ  | 調整/修復問題    |
| Research       | RES  | 探索未知領域     |
| Analysis       | ANA  | 理解現狀和問題   |
| Investigation  | INV  | 深入追蹤問題根因 |
| Documentation  | DOC  | 記錄和傳承經驗   |

## 決策樹路由參數

`decision_tree_path` 記錄 Ticket 建立時的決策樹路由資訊，用於追蹤任務來源。

| 參數 | 必填？ | 說明 | 範例 |
|------|--------|------|------|
| `--decision-tree-entry` | **(必填)** | 進入決策樹的層級/觸發點 | `第三層:命令處理`, `第五層:TDD`, `第六層:事件回應` |
| `--decision-tree-decision` | **(必填)** | 做出的決策 | `create-refactor-ticket`, `dispatch-fix`, `派發 parsley 實作` |
| `--decision-tree-rationale` | **(必填)** | 決策理由 | `quality-baseline-rule-5`, `test-failure`, `Phase 3b 完成` |

### 必填條件

三個參數**必須同時提供或同時省略**。

**必須提供**的情況：
- 建立根任務（非子任務）
- Ticket 類型不是 DOC

**可省略**的情況：
- 建立子任務（`--parent` 參數）
- Ticket 類型為 DOC（`--type DOC`）

### 常見 entry 值

| 層級 | 說明 | 常見值 |
|------|------|-------|
| 第三層 | 命令處理 | `第三層:命令處理` |
| 第三層半 | 執行中額外發現 | `第三層半:執行中額外發現` |
| 第五層 | TDD Phase 完成 | `第五層:TDD`, `第五層:Phase 4a 完成` |
| 第六層 | 事件回應（錯誤修復） | `第六層:事件回應`, `第六層:測試失敗` |
| 其他層級 | 其他決策點 | `Wave 完成`, `並行評估` |

### 範例

```bash
# 根任務 — 必須提供 decision-tree 三參數
ticket create --wave 2 --action "實作" --target "HTTP Handler" \
  --decision-tree-entry "第五層:TDD" \
  --decision-tree-decision "Phase 3b 完成後建立重構 Ticket" \
  --decision-tree-rationale "quality-baseline-rule-5"

# 子任務 — 可省略 decision-tree 參數
ticket create --parent 1.0.0-W2-001 --action "實作" --target "事件融合層"

# DOC 類型 — 可省略 decision-tree 參數
ticket create --wave 2 --action "撰寫" --target "工作日誌" --type DOC
```

## --source-ticket 參數（衍生關係）

`--source-ticket <SOURCE-ID>` 用於建立「衍生 Ticket」關係（spawned_tickets），典型場景為 ANA 衍生 IMP / ADJ、執行中發現的獨立技術債。

### 兩個副作用（顯性契約）

建立新 Ticket 時帶 `--source-ticket <SOURCE-ID>`，CLI 會執行以下兩個副作用：

| # | 副作用 | 寫入位置 |
|---|------|---------|
| 1 | 在**新 Ticket** 設定 `source_ticket: <SOURCE-ID>` 欄位 | 新 Ticket YAML frontmatter |
| 2 | **自動**將新 Ticket ID 追加至 `<SOURCE-ID>` 的 `spawned_tickets` 清單 | source Ticket YAML frontmatter |

副作用 2 為 CLI 自動完成，無需人工編輯 source Ticket；成功時 stdout 顯示 `[INFO] 已自動追加 <new_id> 至 <source_id>.spawned_tickets（雙向關聯）`，失敗時顯示 `[WARNING]` 提示手動檢查。

### 前置驗證（fail-fast）

| 檢查 | 說明 |
|------|------|
| 互斥檢查 | `--source-ticket` 與 `--parent` 不可同時使用（血緣語意不同） |
| ID 格式 | 沿用 `validate_ticket_id` |
| 存在性 | source Ticket 必須存在，否則拒絕建立 |
| 狀態提醒 | source 狀態為 `completed` 時輸出 WARNING，仍允許建立 |

### --parent vs --source-ticket 對比表

| 面向 | `--parent` | `--source-ticket` |
|------|-----------|-------------------|
| 語意 | 血緣關係（直系子任務） | 衍生關係（副產品 / 延伸） |
| 關係欄位 | `parent_id` + `<parent>.children[]` | `source_ticket` + `<source>.spawned_tickets[]` |
| Complete 阻擋 | 父 Ticket 被未完成 children 阻擋 | source **不被** spawned 阻擋（獨立排程） |
| 序號規則 | 自動子序號（如 `W17-001.1`） | 獨立 Ticket ID（不繼承序號） |
| 使用時機 | 功能拆分、上游結論要求的落地 | ANA 衍生 IMP、執行中發現的獨立項 |
| 典型場景 | ANA Solution 落地為 IMP/DOC | 執行中發現 bug/技術債另開單獨追蹤 |
| 決策樹參數 | 可省略（繼承自 parent） | 不可省略（root ticket 規則） |

> **判別問題**：新 Ticket 是上游結論「要求」的落地，還是執行中「衍生」的副產品？
> - 要求的落地（上游 complete 前必須完成）→ `--parent`
> - 衍生的副產品（獨立排程）→ `--source-ticket`
>
> 詳見 `.claude/pm-rules/ticket-lifecycle.md`「ANA Ticket children 建立原則」與 PC-073。
