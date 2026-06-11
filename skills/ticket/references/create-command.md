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

## 重複偵測（兩層防護）

`create` 在持久化前對同版本既有 Ticket 做語意相似度（Jaccard）比對，分兩層防護。設計依據與量測數據見 ticket `1.0.0-W1-040`（五場景 Jaccard 實測）與 `1.0.0-W1-040.1`（實作）。

| 層 | 觸發條件 | 行為 | 旁路 |
|----|---------|------|------|
| Tier 1 警告層 | 同版本 pending / in_progress / completed(7d) + 相似度 >= `DUPLICATE_DETECTION_THRESHOLD`（0.3） | stdout `[WARNING]`，**不阻擋** | 無需（不阻擋） |
| Tier 2 阻擋層 | 同版本 pending / in_progress + 相似度 >= `DUPLICATE_BLOCK_THRESHOLD`（0.6） + 候選建立時間在 `DUPLICATE_BLOCK_WINDOW_MINUTES`（60 分鐘）內 | `[ERROR]` + `exit 1` 阻擋 | `--allow-duplicate` |

Tier 2 設計用途：阻擋 ghost 雙執行流同 turn（數分鐘內）重複 spawn 同語意票的冪等防護。三條件交集（高相似 + 短窗口 + 未完成）鎖定 ghost 簽名，同時排除真實兄弟票（低相似）、batch 同質模板（< 0.6）、合法重做已完成票（completed 不納入）等誤報情境。

候選建立時間以 ticket md 檔案 birth time（fallback mtime）判定，frontmatter `created` 僅日期粒度不足以支撐 60 分鐘級窗口。

### --allow-duplicate 旁路

```bash
# 失誤後刻意重建近似 Ticket 的合法情境
ticket create --wave 1 --action "實作" --target "XXX" --allow-duplicate \
  --decision-tree-entry "..." --decision-tree-decision "..." --decision-tree-rationale "..."
```

使用 `--allow-duplicate` 時放行建立，並在 stdout 標註 `[INFO] --allow-duplicate 已啟用，略過同窗口高相似度阻擋`。

> **bulk_create 差異**：`bulk-create` 僅套用 Tier 1 警告層，**不套用** Tier 2 阻擋層——批次內部同質性高，阻擋誤報風險大。

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
| Complete 阻擋 | 父 Ticket 被未完成 children 阻擋（永遠） | 非 ANA source：不被 spawned 阻擋（獨立排程）；ANA source：W15-003 升級後阻擋（過渡狀態，後續 hook 收斂後將回到「不阻擋」） |
| 序號規則 | 自動子序號（如 `W17-001.1`） | 獨立 Ticket ID（不繼承序號） |
| 使用時機 | 功能拆分、ANA 結論要求的落地（PC-091 路線） | 執行中發現獨立 bug / 技術債（PC-073 殘存範圍） |
| 典型場景 | ANA Solution 落地為 IMP/DOC（一律 children） | 執行 IMP/DOC 中發現 bug/技術債另開單獨追蹤 |
| 決策樹參數 | 可省略（繼承自 parent） | 不可省略（root ticket 規則） |

> **判別問題**：新 Ticket 是上游 ANA 結論「要求」的落地，還是執行中「衍生」的副產品？
> - ANA 結論要求的落地 → `--parent <ANA-ID>`（PC-091 唯一路線）
> - 執行中發現的獨立技術債 → `--source-ticket <CURRENT>`（PC-073 殘存範圍）
>
> 完整決策樹與用戶情境對照表：`.claude/skills/ticket/references/field-semantics.md`「欄位選擇決策樹」。
> 規則來源：`.claude/pm-rules/ticket-lifecycle.md`「ANA Ticket 落地下游血緣選擇」與 PC-091（ANA 落地）+ PC-073（執行中發現）。
