# create 子命令

建立 Atomic Ticket，遵循 5W1H 引導式建立。

## 基本用法

```bash
# 快速建立
/ticket create --version 0.31.0 --wave 1 --action "實作" --target "XXX"

# 完整 5W1H 建立
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
  --priority "P1"

# 指定 decision_tree_path（決策樹路由記錄）
/ticket create \
  --version 0.31.0 \
  --wave 1 \
  --action "實作" \
  --target "XXX" \
  --decision-tree-entry "W13-wave-review" \
  --decision-tree-decision "create-refactor-ticket" \
  --decision-tree-rationale "quality-baseline-rule-5"

# 建立子 Ticket
/ticket create-child --parent-id 0.31.0-W1-001 --wave 1 --action "更新" --target "XXX"

# 初始化版本目錄
/ticket init 0.31.0
```

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

| 參數 | 說明 | 範例 |
|------|------|------|
| `--decision-tree-entry` | 進入決策樹的層級/觸發點 | `W13-wave-review`, `incident-response` |
| `--decision-tree-decision` | 做出的決策 | `create-refactor-ticket`, `dispatch-fix` |
| `--decision-tree-rationale` | 決策理由 | `quality-baseline-rule-5`, `test-failure` |

三個參數均為可選，建議在非臨時建立的 Ticket 中填寫，便於後續追溯任務來源。
