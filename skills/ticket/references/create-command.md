# create 子命令

建立 Atomic Ticket，遵循 5W1H 引導式建立。

本檔章節：〈基本用法〉〈版本歸屬引導〉〈主題歸屬（自動推導）〉〈多值參數格式〉〈類型說明〉〈決策樹路由參數〉〈重複偵測（兩層防護）〉〈--source-ticket 參數（衍生關係）〉。

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

## 版本歸屬引導

`create` 時根據 `--type` 和 `--action` 自動建議目標版本。新功能（IMP + 實作/新增/建立/開發）→ 大版本（0.x+1.0）；修復/改善/分析/文件 → 小版本（最新已完成版本 +1 patch）。未指定 `--version` 時自動套用建議；指定但與建議不符時輸出 WARNING（不阻擋）。

## 主題歸屬（自動推導）

未指定 `--topic` / `--new-topic` 時，`create` 依三條判準自動推導主題，命中即自動指派並印出依據，建票者可否決後改派：

| 判準 | 條件 | 成本 |
|------|------|------|
| S1 上游繼承 | `--source-ticket` 或 `--parent` 的上游已有主題 | 約 32 ms |
| S2 檔案叢集 | `--where` 路徑與某主題既有涵蓋路徑交集達 3 段特異性 | 約 350-490 ms（僅 S1 未命中時執行） |
| S3 ANA 標記 | `--type ANA` 且 S1/S2 皆未命中 | 僅輸出提示，不阻擋 |

三判準皆未命中時印 WARNING 但**不改 rc**（過渡期 warn-only）：以 exit code 表達強制力會讓代理人誤判建票失敗而重試。要免除警告有兩條路——指定主題，或以 `--no-topic` 明示不指派（該旗標與 `--topic` / `--new-topic` 互斥，同給時於任何持久化前 exit 1）。

顯式 `--topic` / `--new-topic` 一律優先，推導只在兩者皆未給時啟動。S2 設 3 段特異性門檻是因為 `docs/` 這類單段路徑與該目錄下任何路徑都相交，不設門檻會使擁有淺層路徑的主題成為所有新票的推導結果。改派用 `ticket track topic-backfill-assign --reassign`。

## 多值參數格式

```bash
#   --acceptance：多次指定或用分隔符（vertical bar）分隔
ticket create ... --acceptance "條件A" --acceptance "條件B"
ticket create ... --acceptance "條件A|條件B|條件C"
#   注意：分隔符是 --acceptance 的多條拆分字元。
#   若 acceptance 內文本身需含該字元（如描述 shell pipe「-q | tail」），
#   用反斜線跳脫保留字面，避免被靜默拆條：
ticket create ... --acceptance "重現實證 -q \| tail 導致 0 行"
#   未跳脫時，單一 --acceptance 值被拆成多條會印出 [WARNING] 供確認。

#   --where：逗號分隔
ticket create ... --where "file1.py,file2.py"

#   --blocked-by / --related-to：逗號分隔
ticket create ... --blocked-by "<id>.1,<id>.2"
```

## 類型說明

正典 4 型（SSOT：`ticket_system/constants.py` 的 `TICKET_TYPES`；CLI `--type` 以 argparse choices 強制）：

| 類型           | 代號 | 用途             |
| -------------- | ---- | ---------------- |
| Implementation | IMP  | 開發新功能       |
| Adjustment     | ADJ  | 調整/修復問題    |
| Analysis       | ANA  | 理解現狀和問題（含研究/調查類任務） |
| Documentation  | DOC  | 記錄和傳承經驗   |

> 歷史化石：TST / RES / INV 已移出正典（TST 職能由 `tdd_phase` 欄位承載、RES/INV 併入 ANA）。語料既存化石票（INV 3 筆）讀取/審計容忍、不回填；新票使用化石 type 會被 CLI 拒絕。

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

`create` 在持久化前對同版本既有 Ticket 做語意相似度（Jaccard）比對，分兩層防護。閾值設定依據五場景 Jaccard 相似度實測定調（TP 逐字相同 / TP 近似改寫 / FP 同域不同標的等，量測資料見 `ticket_system/constants.py` 閾值常數註解）。

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

### --discovered-during vs --source-ticket（發現衍生 vs 規劃衍生）

兩者皆記錄衍生血緣，但語意不同、彼此互斥（同給時於任何持久化前 exit 1）：

| 旗標 | 適用情境 | 上游主題的意義 | 對 S1 判準的影響 |
|------|---------|---------------|-----------------|
| `--source-ticket` | 規劃衍生：ANA 拆 IMP、父票拆子票，上游本就決定了新票主題 | 主題必然相同 | S1 正常繼承 |
| `--discovered-during` | 發現衍生：執行中撞到跨主題問題，主題取決於撞到什麼，與上游無關 | 只反映「當時剛好在改哪個檔案」 | S1 短路不觸發 |

新票的 `discovered_during` frontmatter 欄位記錄血緣供追溯，但不驅動任何主題指派——S2 檔案叢集判準不受影響，仍依新票自身 `--where` 正常運作（可能命中，也可能未命中）。

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
