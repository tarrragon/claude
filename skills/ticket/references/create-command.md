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
/ticket create --parent 0.31.0-W1-001 --action "更新" --target "XXX"

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
ticket create --parent 0.2.0-W2-001 --action "實作" --target "事件融合層"

# DOC 類型 — 可省略 decision-tree 參數
ticket create --wave 2 --action "撰寫" --target "工作日誌" --type DOC
```
