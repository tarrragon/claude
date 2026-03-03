# Ticket 系統架構

## 目錄結構

```
.claude/skills/ticket/
├── SKILL.md                    # 入口文件 - 統一入口
├── ticket.md                   # 完整使用指南
├── pyproject.toml              # 套件定義（uv 管理）
├── ticket_system/              # 主套件目錄
│   ├── __init__.py
│   ├── lib/                    # 共用模組
│   │   ├── __init__.py
│   │   ├── ticket_loader.py    # Ticket 載入和版本解析
│   │   ├── ticket_validator.py # 驗證邏輯
│   │   ├── ticket_formatter.py # 格式化輸出
│   │   ├── ticket_builder.py   # Ticket 建構器
│   │   ├── ticket_generator.py # Plan → Ticket 生成器
│   │   ├── plan_parser.py      # Plan 檔案解析器
│   │   ├── acceptance_auditor.py # 驗收檢查邏輯
│   │   ├── chain_analyzer.py   # 任務鏈分析器
│   │   ├── cycle_detector.py   # 循環依賴檢測
│   │   ├── parallel_analyzer.py # 並行分析（檔案重疊/依賴檢查）
│   │   ├── tdd_sequence.py     # TDD 順序建議（任務類型識別）
│   │   ├── constants.py        # 共用常數
│   │   ├── messages.py         # 標準化訊息定義（lib/ 共用）
│   │   ├── command_lifecycle_messages.py # commands/ 訊息常數（handoff/lifecycle/resume/create/fields）
│   │   ├── command_tracking_messages.py # commands/ 訊息常數（track 系列/migrate/generate）
│   │   ├── critical_path.py    # 關鍵路徑分析
│   │   ├── ticket_chain_index.py # 任務鏈索引
│   │   ├── wave_calculator.py  # Wave 計算邏輯
│   │   ├── ui_constants.py     # UI 顯示常數
│   │   ├── paths.py            # 路徑工具
│   │   ├── parser.py           # 通用解析工具
│   │   └── version.py          # 版本管理工具
│   ├── commands/               # 子命令實作
│   │   ├── __init__.py         # 匯出六大子命令
│   │   ├── create.py           # create 子命令
│   │   ├── track.py            # track 子命令（路由器）
│   │   ├── track_query.py      # track 查詢操作
│   │   ├── track_board.py      # track board 看板視圖
│   │   ├── track_batch.py      # track 批量操作
│   │   ├── track_acceptance.py # track 驗收條件/日誌
│   │   ├── track_audit.py      # track audit 驗收檢查
│   │   ├── track_relations.py  # track 關係/狀態管理
│   │   ├── lifecycle.py        # claim/complete/release
│   │   ├── fields.py           # 5W1H 欄位讀寫
│   │   ├── handoff.py          # handoff 子命令
│   │   ├── resume.py           # resume 子命令
│   │   ├── migrate.py          # migrate 子命令
│   │   └── generate.py         # generate 子命令
│   └── scripts/
│       └── ticket.py           # 統一入口腳本
└── tests/                      # 測試目錄
    ├── conftest.py
    └── fixtures/
```

## 共用模組設計

### ticket_loader.py

負責 Ticket 檔案的載入和版本解析。

| 函式                                | 用途                           |
| ----------------------------------- | ------------------------------ |
| `load_ticket(ticket_id)`            | 載入單一 Ticket                |
| `load_all_tickets(version)`         | 載入版本所有 Tickets           |
| `parse_frontmatter(content)`        | 解析 YAML frontmatter          |
| `find_ticket_path(ticket_id)`       | 尋找 Ticket 檔案路徑           |
| `resolve_version(explicit_version)` | 解析版本號（優先使用明確指定） |
| `require_version(explicit_version)` | 要求版本號（失敗時拋出異常）   |

### ticket_validator.py

負責 Ticket 驗證邏輯。

| 函式                                                    | 用途                         |
| ------------------------------------------------------- | ---------------------------- |
| `validate_id_format(ticket_id)`                         | 驗證 ID 格式                 |
| `validate_required_fields(ticket)`                      | 驗證必填欄位                 |
| `validate_atomic_ticket(ticket)`                        | 驗證 Atomic 原則             |
| `validate_chain(parent_id, child_id)`                   | 驗證任務鏈關係               |
| `validate_claimable_status(id, status)`                 | 驗證是否可認領               |
| `validate_completable_status(id, status, completed_at)` | 驗證是否可完成（返回三元組） |
| `validate_acceptance_criteria(id, acceptance_list)`     | 驗證驗收條件完成度           |

#### 「先查後做」驗證流程

`track complete` 執行時會進行四步驟驗證：

```
Step 1: 載入 Ticket
    ↓ 找不到 → [Error] exit 1
Step 2: 驗證狀態（validate_completable_status）
    ↓ completed → [Info] 友好訊息，exit 0
    ↓ pending/blocked → [Error] 阻止，exit 1
Step 3: 驗證驗收條件（validate_acceptance_criteria）
    ↓ 有未完成項 → [Error] 列出未完成項，exit 1
Step 4: 執行完成操作
    ↓ [OK] exit 0
```

### messages.py

lib/ 共用的標準化訊息定義，遵循 DRY 原則。

| 類別                                 | 用途                             |
| ------------------------------------ | -------------------------------- |
| `ErrorMessages`                      | 錯誤訊息常數                     |
| `WarningMessages`                    | 警告訊息常數                     |
| `InfoMessages`                       | 資訊訊息常數                     |
| `SummaryMessages`                    | 摘要訊息常數                     |
| `StatusMessages`                     | 狀態訊息常數                     |
| `SectionHeaders`                     | 區段標題常數                     |
| `LifecycleMessages`                  | Ticket 生命週期相關訊息          |
| `AgentProgressMessages`              | 代理人進度相關訊息               |
| `MigrationMessages`                  | 遷移命令相關訊息                 |
| `GenerateMessages`                   | Generate 命令相關訊息            |
| `ModuleMessages`                     | 模組相關訊息                     |
| `format_error(template, **kwargs)`   | 格式化錯誤訊息                   |
| `format_warning(template, **kwargs)` | 格式化警告訊息                   |
| `format_info(template, **kwargs)`    | 格式化資訊訊息                   |
| `print_not_executable_and_exit()`    | 統一的 `__main__` guard 訊息輸出 |

### command_lifecycle_messages.py

commands/ 生命週期管理訊息常數。統一管理 handoff.py、lifecycle.py、resume.py、create.py、fields.py 的硬編碼訊息。

| 類別                | 用途                   |
| ------------------- | ---------------------- |
| `HandoffMessages`   | handoff 命令相關訊息   |
| `LifecycleMessages` | lifecycle 命令相關訊息 |
| `ResumeMessages`    | resume 命令相關訊息    |
| `CreateMessages`    | create 命令相關訊息    |
| `FieldsMessages`    | fields 命令相關訊息    |

### command_tracking_messages.py

commands/ 追蹤操作訊息常數。統一管理 track 系列、migrate.py、generate.py 的硬編碼訊息。

| 類別                      | 用途                         |
| ------------------------- | ---------------------------- |
| `TrackQueryMessages`      | track_query.py 相關訊息      |
| `TrackBoardMessages`      | track_board.py 相關訊息      |
| `TrackBatchMessages`      | track_batch.py 相關訊息      |
| `TrackAcceptanceMessages` | track_acceptance.py 相關訊息 |
| `TrackAuditMessages`      | track_audit.py 相關訊息      |
| `TrackRelationsMessages`  | track_relations.py 相關訊息  |
| `TrackMessages`           | track.py 相關訊息            |
| `MigrateMessages`         | migrate.py 相關訊息          |
| `GenerateMessages`        | generate.py 相關訊息         |

### critical_path.py

關鍵路徑分析模組（W7 新增）。

| 函式                 | 用途                     |
| -------------------- | ------------------------ |
| 分析任務鏈的關鍵路徑 | 識別阻塞任務和最長依賴鏈 |

### ticket_chain_index.py

任務鏈索引模組（W7 新增）。

| 函式                 | 用途                       |
| -------------------- | -------------------------- |
| 建立和查詢任務鏈索引 | 加速任務關聯查詢和樹狀展示 |

### wave_calculator.py

Wave 計算邏輯模組（W7 新增）。

| 函式                | 用途                     |
| ------------------- | ------------------------ |
| Wave 號碼計算和分配 | 自動建議任務的 Wave 歸屬 |

### ticket_formatter.py

負責輸出格式化。

| 函式                      | 用途             |
| ------------------------- | ---------------- |
| `format_summary(tickets)` | 格式化摘要輸出   |
| `format_tree(ticket)`     | 格式化樹狀輸出   |
| `format_detail(ticket)`   | 格式化詳細輸出   |
| `format_5w1h(ticket)`     | 格式化 5W1H 輸出 |

### constants.py

共用常數定義。

```python
# 狀態常數
STATUS_PENDING = "pending"
STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETED = "completed"
STATUS_BLOCKED = "blocked"

# 類型常數
TYPE_IMP = "IMP"
TYPE_TST = "TST"
TYPE_ADJ = "ADJ"
# ...

# 路徑常數
TICKETS_BASE_PATH = "docs/work-logs"
HANDOFF_PATH = ".claude/handoff/pending"

# 正則表達式
TICKET_ID_PATTERN = r"^(\d+\.\d+\.\d+)-W(\d+)-(\d+(?:\.\d+)*)$"
```

## 自動化分析功能

### 並行分析（parallel_analyzer.py）

`ticket create` 建立子任務時，系統會自動分析任務的並行可行性。

**分析邏輯**：

| 檢查項目 | 條件                    | 結果     |
| -------- | ----------------------- | -------- |
| 檔案重疊 | 任務修改的檔案有交集    | 無法並行 |
| 依賴關係 | 任務間有 blockedBy 依賴 | 無法並行 |
| 無衝突   | 檔案無重疊 + 無依賴     | 可以並行 |

**輸出範例**：

```
[並行分析結果]
結論: 可以並行執行
群組數: 1

群組 1:
  - 0.31.0-W4-001.1 (lib/a.dart)
  - 0.31.0-W4-001.2 (lib/b.dart)

理由: 任務間無依賴，檔案無重疊，可以並行執行
```

### TDD 順序建議（tdd_sequence.py）

`ticket create` 時，系統會根據任務類型自動建議合適的 TDD Phase 順序。

**任務類型與 TDD 順序對應**：

| 任務類型  | 代碼 | TDD Phase 順序                        |
| --------- | ---- | ------------------------------------- |
| 新功能    | IMP  | Phase 1 → 2 → 3a → 3b → 4（完整流程） |
| 調整/修復 | ADJ  | Phase 2 → 3a → 3b → 4（跳過功能設計） |
| 文件      | DOC  | 無需 TDD 流程                         |
| 研究      | RES  | 無需 TDD 流程（前置工作）             |
| 分析      | ANA  | 無需 TDD 流程（前置工作）             |

**識別關鍵字**：

| 類型 | 關鍵字                                   |
| ---- | ---------------------------------------- |
| IMP  | 實作、新增、建立、implement、add、create |
| ADJ  | 重構、優化、修復、調整、refactor、fix    |
| DOC  | 文件、文檔、documentation、記錄          |
| RES  | 研究、探索、評估、research               |
| ANA  | 分析、調查、analyze、investigate         |

**輸出範例**：

```
[TDD 順序建議]
任務類型: IMP (新功能)
建議流程: Phase 1 → Phase 2 → Phase 3a → Phase 3b → Phase 4
理由: 新功能需要完整的 TDD 流程以確保設計合理、測試完整、品質穩定
```

### Phase 前置條件驗證

系統會自動驗證 Phase 進入的前置條件：

| Phase    | 前置條件      |
| -------- | ------------- |
| Phase 1  | 無            |
| Phase 2  | Phase 1 完成  |
| Phase 3a | Phase 2 完成  |
| Phase 3b | Phase 3a 完成 |
| Phase 4  | Phase 3b 完成 |

**驗證失敗範例**：

```
[ERROR] 無法進入 Phase 3b（實作執行），尚需完成：Phase 3a（策略規劃）
```
