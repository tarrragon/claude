# migrate 子命令

Ticket ID 遷移（支援單一和批量遷移）。

> **何時讀**：遷移 Ticket ID 時——單一或批量遷移前的前置檢查、遷移邏輯、collision detection、備份機制或選項說明。**亦由此進入**：無（`grep -rn` 排除 `SKILL.md` 路由表本檔自身列後零命中，目前無其他檔案的步驟把讀者送到本檔）。
>
> **同目錄**：`workflow-migrate.md`（ID 遷移的決策樹，與本檔互補：決策樹在那份、CLI 用法與備份/collision 細節在本檔）。
>
> **溯源**：本檔於本專案匯入 commit `f375ae675` 時即已存在；本機 git log 僅見後續章節 TOC 補齊，未見原始拆分點（可用 `git log --oneline -- references/migrate-command.md` 查證）。

本檔章節：〈基本用法〉〈前置檢查（強制）〉〈單一遷移範例〉〈批量遷移配置檔案格式〉〈遷移邏輯〉〈Collision Detection〉〈備份機制〉〈Flag 說明〉。

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
   # 碰撞時 dry-run 判 FAIL（exit 1）並印改號預覽，非可放行的 warning
   ```

4. **實際執行後必看 migrate 產生的 commit**：migrate 會自動以單一隔離提交寫入新檔、舊檔、各引用者與 topic 追加行（exit 0 即已提交；exit 75 代表檔案已寫入工作區但提交失敗，stderr 的 `[WARNING]` 列出全部路徑）。檢查該 commit 的檔案狀態：

   ```bash
   git show --stat --name-status HEAD
   ```

   | 檔案狀態 | 判別 | 處置 |
   |---------|------|------|
   | 目標路徑 `A` | 正常，新建 ticket | 繼續 |
   | 來源路徑 `D` | 正常，來源被刪除（ID 替換） | 繼續 |
   | 目標路徑 `M` | **撞號警示**，既有 ticket 被覆寫 | 立即還原（見下） |

**撞號後的還原步驟**：migrate 已自動提交時，以 `git revert` 撤回整筆遷移 commit（舊檔、新檔、引用者與 topic 行一次還原），不要逐檔 `git restore`，因為逐檔還原會漏掉引用者的改寫：

```bash
git revert --no-edit <migrate 產生的 commit>

# 重新確認 ID 範圍後，以不撞號的目標 ID 重新 migrate
```

exit 75（提交失敗、檔案留在工作區）時，先依 `[WARNING]` 列出的路徑以 `git restore` 還原引用者與來源檔，並刪除誤建的目標檔，再重新 migrate。

如 revert 不可用（例如遷移 commit 之後已有依賴它的提交），從備份還原：

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

## 整版改號流程

`ticket version-shift` 已移除（見 CHANGELOG 2.44.21）。把整個版本的票搬到另一個版本號，用 `ticket migrate --config` 搬票，再手動完成三件 migrate 不處理的事。順序固定：

1. **先登記目標版本**：`version-release start --version <目標版本>`（建 todolist 版本條目與 worklog 結構）。須在 migrate 之前，否則 start 因目標目錄已存在而拒絕。驗證：`grep -n 'version: "<目標版本>"' docs/todolist.yaml` 命中，且 `docs/work-logs/` 下目標版本目錄存在。
2. **產生設定檔並搬票**：列出來源版本全部票，逐張寫 `from` / `to` 進 `migration.yaml`（格式見上節），先 `ticket migrate --config migration.yaml --dry-run`，再實際執行。驗證：`git show --stat --name-status HEAD` 只有來源 `D`、目標 `A`、引用者 `M`、topic 追加行，無目標路徑 `M`（撞號）。
3. **手動步驟一，todolist 版本條目**：來源版本條目改 `status` 與 `notes` 說明已改號（或依實際需要移除），確認目標條目已有正確 `worklog` 路徑。驗證：`grep -n 'version: "<來源版本>"' docs/todolist.yaml` 與目標版本各看一次；`python3 -c "import yaml;yaml.safe_load(open('docs/todolist.yaml'))"` 無例外。
4. **手動步驟二，worklog 主檔**：把來源版本 worklog 主檔（`v<版本>-main.md`）內容併入或改名為目標版本主檔。漏做不會報錯，之後每次 `complete` 靜默缺進度行。驗證：目標版本目錄下存在 `v<目標版本>-main.md`，`complete` 一張票後該檔出現進度行。
5. **手動步驟三，舊目錄**：確認來源版本目錄 `tickets/` 已空且無他人引用後移除。驗證：`ls` 來源版本 `tickets/` 為空；`grep -rl "<來源版本>-W" docs/ .claude/` 無結構欄位殘留（body 內舊 ID 依 migrate 語意保留）。

migrate 不改 todolist、不改 worklog 主檔、不移除舊目錄；這三件不做，整版改號即未完成。

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
| `discovered_during` | 更新發現來源引用     |
| `closed_by`      | 更新關閉者引用（字串或清單） |
| 他票的 `chain.root`／`chain.parent` | 等於舊 ID 者改寫為新 ID |
| `previous_ids`   | 被遷移票追加舊 ID（有序清單，長度即遷移次數；同 ID 改名不追加） |

**有子孫的票連帶遷移整個子樹**：子孫以 ID 前綴（`<來源 ID>.`）收集（parent_id 指向來源但 ID 不在前綴下者無法映射新 ID，不屬子樹，僅其 parent_id 引用被改寫），新 ID 為「目標 ID + 原相對後綴」。上表欄位對每個搬移成員各做一次；

| 子孫狀態 | 處置 |
| --- | --- |
| pending／in_progress 等非終態 | 改號搬移 |
| completed／closed | 留在原版本、ID 不變、不追加 `previous_ids`；`parent_id` 與 `chain.parent`／`chain.root` 中指向被搬移票者改寫為新 ID |
| 祖先鏈上有被留下者的子孫 | 跟著留下（搬走會失去父票），parent 不變，僅 `chain.root` 改寫 |

取捨：已完成歷史票的 ID 前綴與新父不一致，換取歷史紀錄（worklog、CHANGELOG、版本完成清單）的穩定；新父 `children` 同時列出搬移者的新 ID 與留下者的原 ID。引用改寫以 old 到 new 映射單趟完成（重疊映射如 A 到 B 且 B 也在遷移時，不會二次改寫）；子樹外票檔的引用同樣單趟改寫。

| 子樹遷移項目 | 語意 |
| --- | --- |
| `previous_ids` | 每個成員各自追加自己的舊 ID（舊 ID 散見 commit message、worklog、issue，不會被改寫） |
| `parent_id` | 根票依新 ID 重算；子孫對應新父 |
| preflight | 碰撞（任一新 ID 已被佔用）、深度（任一成員遷移後超過 MAX_TICKET_DEPTH，訊息列出票 ID 與深度）、目標版本註冊；任一項失敗整體拒絕、零寫入、exit 非 0，訊息列出全部失敗項 |
| 碰撞處理 | 子樹遷移不自動改號（單票碰撞才自動取下一可用序號）；`--force-overwrite` 可放行碰撞 |
| `--dry-run` | 列出完整 old 到 new 映射表，不寫入 |
| 提交 | 整個子樹、子樹外引用者、舊檔刪除與 topic 追加行為單一隔離提交 |
| 中途寫入失敗 | exit 1，輸出已寫入的檔案集合（不自動回滾） |

沒有子孫的票維持單票路徑，行為不變。

topic-assignments 以追加一行「新 ID、原主題」承接，不改寫舊行。遷移以單一隔離提交寫入新檔、舊檔、各引用者與 topic 追加行；提交失敗時 exit 75，`[WARNING]` 列出全部路徑。

## Collision Detection

> 來源：W14-048

遷移會檢查目標 ID 是否與既有 Ticket 撞檔。發版前移撞號改號機制生效後，預設行為由
「拒絕」改為「改取目標版本同 Wave 下一可用序號完成遷移」：

| 階段       | 行為                                                                                |
| ---------- | ----------------------------------------------------------------------------------- |
| `--dry-run`  | 目標已存在時判 `[ERROR]` FAIL（exit 1），印改號預覽（下一可用序號）；不再是可放行的 WARNING |
| 實際執行   | 預設改取下一可用序號完成遷移（exit 0），改號後的票面 frontmatter 寫入 `migrated_from: <原目標 ID>`；既有的碰撞目標不受影響 |
| 批量遷移   | 不再預掃描 fail-fast；每筆遷移各自對當下檔案系統狀態判斷碰撞並改號，天然支援批次內連環碰撞（前一筆改號後的新目標仍會被下一筆的碰撞檢查看見） |
| `--force-overwrite` | 語意不變：明示授權覆寫既有 Ticket，並在 stdout 記錄 `[AUDIT]` log（含時間戳與既有標題）；dry-run 下仍為可放行的 `[WARNING]` |

例外：`source_id == target_id`（in-place rename）不視為 collision。

## 備份機制

預設情況下，遷移前會自動建立備份：

- 備份位置：`.claude/migration-backups/{timestamp}/`
- 支援 `--no-backup` 停用備份

## Flag 說明

| Flag            | 說明                               |
| --------------- | ---------------------------------- |
| `--config FILE` | 批量遷移配置檔案（.yaml 或 .json） |
| `--version VER` | 指定版本（預設自動偵測）           |
| `--dry-run`     | 預覽遷移結果，不實際執行           |
| `--backup`      | 遷移前備份（預設啟用）             |
| `--no-backup`   | 停用備份                           |
| `--force-overwrite` | 明示授權覆寫目標 ID 既有 Ticket（W14-048；會記錄 audit log） |
