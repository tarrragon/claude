# track 子命令

追蹤和更新 Ticket 狀態。

## READ 操作

```bash
# 快速摘要
/ticket track summary

# 查詢單一 Ticket
/ticket track query <id>

# 版本進度
/ticket track version 0.31.0

# 樹狀查詢
/ticket track tree <id>

# 代理人進度
/ticket track agent parsley

# 關聯鏈查詢
/ticket track chain <id>

# 完整內容
/ticket track full <id>

# 執行日誌
/ticket track log <id>

# 列出 Tickets
/ticket track list [--pending|--in-progress|--completed|--blocked]

# 看板視圖（樹狀未完成任務總覽）
/ticket track board [--wave <wave>] [--all]

# 5W1H 單欄位查詢
/ticket track who|what|when|where|why|how <id>
```

## UPDATE 操作

```bash
# 接手 Ticket
/ticket track claim <id>

# 完成 Ticket
/ticket track complete <id>

# 放棄 Ticket
/ticket track release <id>

# 更新 Phase
/ticket track phase <id> <phase> <agent>

# 添加子 Ticket
/ticket track add-child <parent-id> <child-id>

# 設定 5W1H 欄位
/ticket track set-who|set-what|set-when|set-where|set-why|set-how <id> <value>

# 追加執行日誌
/ticket track append-log <id> --section "Problem Analysis" "內容"

# 勾選驗收條件（--uncheck 取消勾選）
/ticket track check-acceptance <id> <index> [--uncheck]

# 標記建立後驗收已通過
/ticket track accept-creation <id>

# 執行驗收檢查
/ticket track audit <id>

# 批量操作
/ticket track batch-claim "id1,id2,id3"
/ticket track batch-complete "id1,id2,id3"
```

## track board 子命令

提供樹狀看板視圖，視覺化展示各 Wave 的未完成任務分佈。

### 用法

```bash
# 顯示未完成任務看板（預設）
/ticket track board

# 指定版本
/ticket track board --version 0.31.0

# 只顯示特定 Wave
/ticket track board --wave 7

# 顯示所有任務（包含已完成）
/ticket track board --all
```

### 選項說明

| 選項        | 說明                       |
| ----------- | -------------------------- |
| `--version` | 版本號（自動偵測）         |
| `--wave`    | 只顯示特定 Wave            |
| `--all`     | 顯示所有任務（包含已完成） |

## track audit 子命令

執行驗收檢查，產出結構化的驗收報告。

### 用法

```bash
# 對特定 Ticket 執行驗收檢查
/ticket track audit <ticket-id>
```

### 檢查內容

- Ticket 結構完整性（必填欄位）
- 驗收條件完成度
- 執行日誌填寫狀態
- 子任務完成狀態
- 品質標準符合性
