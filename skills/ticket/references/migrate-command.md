# migrate 子命令

Ticket ID 遷移（支援單一和批量遷移）。

## 基本用法

```bash
# 單一 Ticket 遷移
/ticket migrate <source_id> <target_id>

# 批量遷移（配置檔案驅動）
/ticket migrate --config migration.yaml

# 預覽模式（不實際執行）
/ticket migrate <source_id> <target_id> --dry-run

# 停用備份
/ticket migrate <source_id> <target_id> --no-backup
```

## 單一遷移範例

```bash
# 遷移根任務
/ticket migrate 0.31.0-W4-001 0.31.0-W5-001

# 遷移子任務
/ticket migrate 0.31.0-W4-001.1 0.31.0-W5-001.1

# 預覽遷移結果
/ticket migrate 0.31.0-W4-001 0.31.0-W5-001 --dry-run
```

## 批量遷移配置檔案格式

```yaml
# migration.yaml
migrations:
  - from: "0.31.0-W4-001"
    to: "0.31.0-W5-001"
  - from: "0.31.0-W4-001.1"
    to: "0.31.0-W5-001.1"
  - from: "0.31.0-W4-002"
    to: "0.31.0-W5-002"
```

或 JSON 格式：

```json
{
  "migrations": [
    { "from": "0.31.0-W4-001", "to": "0.31.0-W5-001" },
    { "from": "0.31.0-W4-001.1", "to": "0.31.0-W5-001.1" }
  ]
}
```

## 遷移邏輯

遷移會自動更新以下欄位：

| 欄位             | 更新邏輯                |
| ---------------- | ----------------------- |
| `id`             | 直接替換為目標 ID       |
| `wave`           | 從目標 ID 提取波次號    |
| `chain.root`     | 重新計算根 ID           |
| `chain.parent`   | 重新計算父 ID           |
| `chain.depth`    | 重新計算深度            |
| `chain.sequence` | 重新計算序號            |
| `parent_id`      | 根據新的 chain 資訊更新 |
| `blockedBy`      | 更新所有 Ticket ID 引用 |
| `children`       | 更新子任務 ID 引用      |
| `source_ticket`  | 更新來源引用            |

## 備份機制

預設情況下，遷移前會自動建立備份：

- 備份位置：`.claude/migration-backups/{timestamp}/`
- 支援 `--no-backup` 停用備份

## 選項說明

| 選項            | 說明                               |
| --------------- | ---------------------------------- |
| `--config FILE` | 批量遷移配置檔案（.yaml 或 .json） |
| `--version VER` | 指定版本（預設自動偵測）           |
| `--dry-run`     | 預覽遷移結果，不實際執行           |
| `--backup`      | 遷移前備份（預設啟用）             |
| `--no-backup`   | 停用備份                           |
