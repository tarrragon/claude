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

# Scheduler 排程視圖（可執行清單 / DAG / 關鍵路徑）
/ticket track runqueue [--format={list|dag|critical-path}] [--top N] [--context=resume] [--wave N]

# 5W1H 單欄位查詢
/ticket track who|what|when|where|why|how <id>
```

## track runqueue 子命令（Scheduler）

**用途**：回答「下一個該做哪個 ticket」（Linux schedule() 類比）。合併原 next/schedule/resume-hint 三概念為單一命令。

**核心使用場景**：

| 場景 | 命令 | 輸出 |
|------|------|------|
| PM 迷失方向 / 新 session 接手 | `ticket track runqueue --wave N` | priority 排序的可執行清單（blockedBy=[]） |
| 查看完整依賴 DAG | `ticket track runqueue --wave N --format=dag` | 拓撲層級分組，關鍵路徑高亮 |
| 查看關鍵路徑節點 | `ticket track runqueue --wave N --format=critical-path` | slack=0 節點（CPM） |
| /clear 後接手 | `ticket track runqueue --context=resume --top 3` | 與 handoff/pending 交集 top 3 |

**參數**：

| 參數 | 值域 | 語意 |
|------|------|------|
| `--format` | `list`（預設）/ `dag` / `critical-path` | 輸出視圖 |
| `--top N` | int | 限制 N 筆（list / critical-path 有效，dag 忽略） |
| `--context=resume` | — | 交集 `.claude/handoff/pending/` |
| `--wave N` | int | 過濾 wave |

**新 session 自動引導**：`session-start-scheduler-hint-hook.py` 在 SessionStart 時自動呼叫 `runqueue --context=resume --top 3`（若無 handoff 則 fallback `--format=list --top 1`），結果顯示為 hook additionalContext。

### 排序規則（priority + spawned 加權）

**第一層：Priority tier 排序**

| Tier | 條件 | 優先度 |
|------|------|--------|
| L1 | priority=P1 | 最優先 |
| L2 | priority=P2 | 次之 |
| L3 | priority=P3 或未指定 | 最低 |

**第二層：同 tier 內加權（來源 W17-036 軸 C 分析）**

| 加權項 | 觸發條件 | 效果 |
|-------|---------|------|
| `spawned_from_completed_ana` | `source_ticket` 存在且該 source ANA status=completed | 排在同 tier 其他 ticket 前面 |

**Why**: ANA 結論已產出的衍生 IMP 推進急迫性高於一般 pending —— source ANA 已結案代表分析完成、結論等待落地；若與其他同 priority pending 同等對待會造成結論擱置（PC-075 下游傳播防護；詳見 `.claude/error-patterns/process-compliance/PC-075-spawned-children-status-check-asymmetric.md`）。

**第三層：依存關係過濾**

`runqueue` 僅列出 `blockedBy=[]` 的 ticket（可執行清單）。被阻塞的 ticket 在 `--format=dag` 可見，在 `--format=list`（預設）不顯示。

### Wave 完成判定與 spawned 清點

Wave 完成判定規則（Checkpoint 2 情境 C 前置條件）：

1. 當前 Wave 無 `pending` / `in_progress` ticket
2. **本 Wave 已 completed ANA 的 `spawned_tickets` 皆非 `pending`**（W17-037 落地）

兩條件均滿足才算 Wave 完成。詳見 `.claude/pm-rules/completion-checkpoint-rules.md` 第八層 Checkpoint 2 情境 C。

### 實作現況

| 層 | 狀態 | 檔案 |
|----|------|------|
| 規則面（本章節） | 已落地 | `.claude/skills/ticket/references/track-command.md`（W17-040） |
| Wave 完成判定 | 已落地 | `.claude/pm-rules/completion-checkpoint-rules.md` L76（W17-037） |
| CLI 排序邏輯（第二層加權實作） | 未實作（若未來發現序列差異造成問題再建 IMP） | `.claude/skills/ticket/ticket_system/commands/track_runqueue.py` |

**典範**：W17-011.1 實作（基礎 runqueue），W17-009 ANA 三視角審查（Evidence/Alternatives/linux）收斂結論；W17-036 軸 C 補強 spawned 加權規則。

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

# 設定 5W1H 欄位（僅以下 6 個 set-* 命令）
/ticket track set-who <id> <value>
/ticket track set-what <id> <value>
/ticket track set-when <id> <value>
/ticket track set-where <id> <value>
/ticket track set-why <id> <value>
/ticket track set-how <id> <value>

# 追加執行日誌
# 有效 section: Problem Analysis / Context Bundle / Solution / Test Results / Execution Log
/ticket track append-log <id> --section "Problem Analysis" "內容"
/ticket track append-log <id> --section "Context Bundle" "PCB 內容（派發前分析結果，PC-040）"

# 勾選驗收條件（check-acceptance，舊語法）
/ticket track check-acceptance <id> 1                  # 勾選第 1 項（1-based 整數）
/ticket track check-acceptance <id> 1 --uncheck        # 取消勾選第 1 項
/ticket track check-acceptance <id> --all              # 勾選全部驗收條件
/ticket track check-acceptance <id> --all --uncheck    # 取消勾選全部
/ticket track check-acceptance <id> "實作完成"          # 文字搜尋勾選（模糊比對）

# 勾選驗收條件（set-acceptance，W14-030 推薦語法）
/ticket track set-acceptance <id> --check 1 2 3        # 勾選多個 index（空白分隔，支援 nargs）
/ticket track set-acceptance <id> --uncheck 1 2        # 取消勾選多個 index
/ticket track set-acceptance <id> --all-check          # 勾選全部
/ticket track set-acceptance <id> --all-uncheck        # 取消勾選全部

# 設定阻擋關係（blockedBy 欄位）
/ticket track set-blocked-by <id> <blocked-by-id>      # 覆寫（設定單一 blockedBy）
/ticket track set-blocked-by <id> <id2> --add          # 追加（去重）
/ticket track set-blocked-by <id> <id2> --remove       # 移除指定 blockedBy

# 設定相關關係（relatedTo 欄位）
/ticket track set-related-to <id> <related-id>         # 覆寫（設定單一 relatedTo）
/ticket track set-related-to <id> <id2> --add          # 追加（去重）
/ticket track set-related-to <id> <id2> --remove       # 移除指定 relatedTo

# 驗證 frontmatter 合規性（W14-030）
/ticket track validate <id>                            # 檢查 status/completed_at/acceptance/who 4 欄位

# 標記建立後驗收已通過
/ticket track accept-creation <id>

# 執行驗收檢查
/ticket track audit <id>

# 批量操作
/ticket track batch-claim "id1,id2,id3"
/ticket track batch-complete "id1,id2,id3"
```

## 驗收條件操作詳解

### 語法組合完整表

#### check-acceptance 完整組合（舊語法，單索引）

| 組合 | 指令 | 行為 |
|------|------|------|
| 單項勾選 | `check-acceptance <id> 1` | 勾選第 1 個驗收條件 |
| 單項取消勾選 | `check-acceptance <id> 1 --uncheck` | 取消勾選第 1 項 |
| 全部勾選 | `check-acceptance <id> --all` | 勾選全部驗收條件 |
| 全部取消勾選 | `check-acceptance <id> --all --uncheck` | 取消勾選全部 |
| 文字搜尋勾選 | `check-acceptance <id> "實作完成"` | 模糊比對後勾選 |
| 文字搜尋取消 | `check-acceptance <id> "實作完成" --uncheck` | 模糊比對後取消勾選 |

#### set-acceptance 完整組合（W14-030 推薦，多索引）

| 組合 | 指令 | 行為 |
|------|------|------|
| 多項勾選 | `set-acceptance <id> --check 1 2 3` | 同時勾選第 1/2/3 項 |
| 多項取消勾選 | `set-acceptance <id> --uncheck 1 2` | 同時取消勾選第 1/2 項 |
| 全部勾選 | `set-acceptance <id> --all-check` | 勾選全部驗收條件 |
| 全部取消勾選 | `set-acceptance <id> --all-uncheck` | 取消勾選全部 |

### set vs check 決策樹

```
需要操作驗收條件？
    |
    v
一次操作多個 index？
    |
    +── 是 ──> 用 set-acceptance --check 1 2 3（check-acceptance 不支援多索引）
    |
    +── 否 ──> 用文字搜尋？（不確定 index）
                  |
                  +── 是 ──> 用 check-acceptance <id> "關鍵字"（set-acceptance 不支援文字）
                  |
                  +── 否 ──> 兩者皆可，推薦 set-acceptance（語意清晰）
```

**場景對照（7 情境）**：

| 場景 | 推薦命令 | 原因 |
|------|---------|------|
| 完成所有驗收條件 | `set-acceptance --all-check` | 語意清晰，等同批量操作 |
| 逐一勾選（不確定 index） | `check-acceptance "關鍵字"` | 唯一支援文字搜尋的命令 |
| 一次勾選多項 | `set-acceptance --check 1 3 5` | check-acceptance 不支援多索引 |
| 取消上一個勾選 | `set-acceptance --uncheck 2` | 語意明確，等同 check + --uncheck |
| 確認哪幾項已勾選 | `ticket track query <id>` | 先查再操作 |
| 重置全部再重選 | `set-acceptance --all-uncheck` + `--check 1 2` | 分兩步清除後選取 |
| 腳本自動化 | `set-acceptance --check ...` | 有具名 flag，腳本可讀性高 |

### index 三種格式（僅 check-acceptance 支援）

| 格式 | 範例 | 說明 |
|------|------|------|
| 1-based 整數 | `1`, `2`, `3` | 標準格式，第 1 項 = 索引 1 |
| 0-based 整數 | `0` | 特殊支援，視為第 1 項（等同 `1`） |
| 文字搜尋 | `"實作完成"` | 模糊比對 AC 條目文字；唯一比對才成功 |

> **注意**：`set-acceptance` 只接受 1-based 整數，不支援 0-based 或文字搜尋。

### 5 常見錯誤組合警示

| 錯誤用法 | 症狀 | 正確用法 |
|---------|------|---------|
| `check-acceptance <id> 1 2 3` | argparse 錯誤（只接受單 index） | `set-acceptance <id> --check 1 2 3` |
| `check-acceptance <id>`（無 index 無 --all） | `CHECK_ACCEPTANCE_MISSING_INDEX` 錯誤 | 加 index 或 `--all` |
| `check-acceptance <id> --all 1` | `CHECK_ACCEPTANCE_ALL_WITH_INDEX` 錯誤（互斥） | 二選一：要嘛 `--all`，要嘛指定 index |
| `set-acceptance <id> --check`（無數字） | argparse 錯誤（--check 需至少 1 個值） | `--check 1` 或 `--check 1 2 3` |
| `check-acceptance <id> "關鍵字"`（比對多項）| `匹配到 N 個項目，請使用索引` 錯誤 | 改用具體 index 避免歧義 |

---

## CLI 可修改欄位 vs 手動編輯欄位

並非所有 frontmatter 欄位都有對應的 CLI 命令。修改欄位前請查閱此表：

| 欄位 | CLI 命令 | 備註 |
|------|---------|------|
| who/what/when/where/why/how | `set-who` ~ `set-how` | 僅此 6 個 set-* 命令 |
| status | `claim` / `complete` / `release` | 由生命週期命令管理，禁止手動編輯 |
| tdd_phase | `phase <id> <phase> <agent>` | Phase 進度更新 |
| children | `add-child <parent> <child>` | 父子關係 |
| acceptance | `check-acceptance` / `set-acceptance` | 勾選/取消勾選驗收條件（set-acceptance 為 W14-030 明確語意版） |
| frontmatter 驗證 | `validate <id>` | 檢查 status/completed_at/acceptance/who 4 欄位合規性（W14-030） |
| blockedBy | `set-blocked-by <id> <value> [--add\|--remove]` | 建立時用 `--blocked-by`；之後用 CLI 更新 |
| relatedTo | `set-related-to <id> <value> [--add\|--remove]` | 建立時用 `--related-to`；之後用 CLI 更新 |
| priority | 無 CLI 命令 | 手動編輯 frontmatter |
| dispatch_reason | 無 CLI 命令 | 手動編輯 frontmatter |

**不存在的操作**（禁止嘗試）：

| 錯誤呼叫 | 正確做法 |
|---------|---------|
| `set-status` | 使用 `claim` / `complete` / `release` |
| `set-priority` | 手動編輯 frontmatter `priority` 欄位 |

---

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
