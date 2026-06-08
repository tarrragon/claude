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

# 明示授權覆寫目標 ID 既有 Ticket（W14-048）
/ticket migrate <source_id> <target_id> --force-overwrite
```

## 前置檢查（強制）

執行任何 migrate 命令前，必須先確認目標版本的既有 ticket ID 範圍，避免覆寫已存在的 ticket。

**Why**：migrate 工具預設覆寫目標路徑既有檔案（W14-048 修復前行為），PM 若未先確認目標版本已有哪些 ticket，批量遷移可能靜默覆寫重要 ticket（如 v1.0 路線圖父級 ticket）。本條款基於 W14-047 ANA 確認的 L1 規則缺口，對應 PC-152 事件。

**Consequence**：跳過前置檢查直接執行 migrate，目標版本若已有同 ID ticket，其內容（title/type/frontmatter/body）將被完全替換，commit 後除備份目錄外無法還原。本次事件（W14-047 案例 1）靠 commit 前 git status 才得以 rollback。

**SOP（必須依序執行）**：

1. **列出目標版本既有 tickets**：

   ```bash
   ls docs/work-logs/v<目標版本>/tickets/
   ```

   例：遷移目標為 `v0.19.0`：

   ```bash
   ls docs/work-logs/v0/v0.19/v0.19.0/tickets/
   ```

2. **確認既有 ID 範圍**：記錄目標版本已使用的 Wave-序號組合（如 W1-001~W1-003），配置 migrate 目標 ID 時**避開此範圍**。

3. **執行 dry-run 並觀察 git status 模擬**：

   ```bash
   ticket migrate --config migration.yaml --dry-run
   # W14-048 修復後：dry-run 會顯示 collision warning；修復前：需手動 git status 核查
   ```

4. **實際執行後、commit 前必看 git status**：

   ```bash
   git status
   ```

   | git status 訊號 | 判別 | 處置 |
   |----------------|------|------|
   | 目標路徑 `untracked` | 正常，新建 ticket | 繼續 |
   | 目標路徑 `deleted` | 正常，來源被刪除（ID 替換） | 繼續 |
   | 目標路徑 `modified` | **撞號警示**，既有 ticket 被覆寫 | 立即還原（見下） |

**撞號後的還原步驟**：

```bash
# 還原被覆寫的目標版本既有 ticket
git restore docs/work-logs/v<目標版本>/tickets/<被覆寫 ID>.md

# 刪除不應建立的遷移 ticket（未撞號但目標 ID 已被占用的新增項）
rm docs/work-logs/v<目標版本>/tickets/<誤建 ID>.md

# 還原被刪除的來源 ticket
git restore docs/work-logs/v<來源版本>/tickets/<來源 ID>.md

# 重新確認 ID 範圍後，以不撞號的目標 ID 重新 migrate
```

如 commit 已執行，從備份還原：

```bash
ls .claude/migration-backups/
cp .claude/migration-backups/<timestamp>/<被覆寫 ticket>.md docs/work-logs/v<目標版本>/tickets/
```

**參考**：PC-152（本事件完整 timeline、L1+L2 根因分析、識別模板，含 L2 工具層 collision detection 修復脈絡）

---

## 單一遷移範例

```bash
# 遷移根任務
/ticket migrate 1.0.0-W4-001 1.0.0-W5-001

# 遷移子任務
/ticket migrate 1.0.0-W4-001.1 1.0.0-W5-001.1

# 預覽遷移結果
/ticket migrate 1.0.0-W4-001 1.0.0-W5-001 --dry-run
```

## 批量遷移配置檔案格式

```yaml
# migration.yaml
migrations:
  - from: "1.0.0-W4-001"
    to: "1.0.0-W5-001"
  - from: "1.0.0-W4-001.1"
    to: "1.0.0-W5-001.1"
  - from: "1.0.0-W4-002"
    to: "1.0.0-W5-002"
```

或 JSON 格式：

```json
{
  "migrations": [
    { "from": "1.0.0-W4-001", "to": "1.0.0-W5-001" },
    { "from": "1.0.0-W4-001.1", "to": "1.0.0-W5-001.1" }
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

## Collision Detection（W14-048）

遷移會檢查目標 ID 是否與既有 Ticket 撞檔：

| 階段       | 行為                                                                                |
| ---------- | ----------------------------------------------------------------------------------- |
| `--dry-run`  | 目標已存在時輸出 `[WARNING] 目標 Ticket 已存在，實際執行時將被覆寫`，exit 0       |
| 實際執行   | 預設拒絕並 exit 1（顯示既有 Ticket 的標題/狀態，提示 `--force-overwrite` 旗標）     |
| 批量遷移   | 預掃描所有 target_id；任一撞 ID 即 fail-fast，**不執行任何 migration**             |
| `--force-overwrite` | 明示授權覆寫，並在 stdout 記錄 `[AUDIT]` log（含時間戳與既有標題）        |

例外：`source_id == target_id`（in-place rename）不視為 collision。

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
| `--force-overwrite` | 明示授權覆寫目標 ID 既有 Ticket（W14-048；會記錄 audit log） |
