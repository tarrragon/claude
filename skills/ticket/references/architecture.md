# Ticket 系統架構

## 目錄結構

```
.claude/skills/ticket/
├── SKILL.md                    # 入口文件 - 統一入口
├── ticket.md                   # 完整使用指南
├── pyproject.toml              # 套件定義（uv 管理）
├── ticket_system/              # 主套件目錄
│   ├── __init__.py
│   ├── lib/                    # 共用模組（67 個，依功能分組）
│   │   ├── __init__.py
│   │   │
│   │   ├── [Ticket 核心 I/O 與解析]
│   │   ├── ticket_loader.py               # 載入和解析模組（統一入口）
│   │   ├── parser.py                      # 格式解析模組
│   │   ├── ticket_ops.py                  # 操作共用函式模組
│   │   ├── ticket_builder.py              # 建構模組
│   │   ├── ticket_formatter.py            # 格式化模組
│   │   ├── ticket_validator.py            # 驗證模組
│   │   ├── id_parser.py                   # ID 解析模組
│   │   ├── migrations.py                  # Protocol Version 遷移邏輯
│   │   ├── protocol_version_checker.py    # Protocol Version Checker - Library Function
│   │   ├── section_locator.py             # Section locator helper — 統一 Markdown section 標題定位邏輯
│   │   │
│   │   ├── [建票輔助（多數自 create.py 抽出）]
│   │   ├── topic_inference.py             # 主題歸屬推導與參數驗證
│   │   ├── acceptance_parser.py           # acceptance 條目的 CLI 輸入解析
│   │   ├── ticket_id_allocator.py         # ID 與 wave 的解析與配號
│   │   ├── field_validators.py            # 建票參數的欄位合法性驗證
│   │   ├── create_reporter.py             # create 報告輸出模組
│   │   ├── duplicate_detector.py          # 重複偵測模組
│   │   ├── context_bundle_extractor.py    # Context Bundle 自動抽取模組
│   │   ├── depth.py                       # 嵌套深度計算模組
│   │   ├── tdd_phase_inference.py         # TDD Phase 自動推導
│   │   │
│   │   ├── [驗收與 AC]
│   │   ├── ac_parser.py                   # AC 解析器：解析 Ticket frontmatter 的 acceptance list 為結構化 AC 物件
│   │   ├── acceptance_auditor.py          # Acceptance Auditor 驗收檢查模組
│   │   ├── validation_templates.py        # validation_templates — AC 驗證模板規則庫
│   │   ├── verification_result.py         # AC 驗證結果資料結構
│   │   ├── checkbox_utils.py              # Checkbox 前綴處理共用工具
│   │   ├── multi_view_status.py           # multi_view_status 欄位覆寫格式驗證
│   │   ├── exempt_marker.py               # PC-093 exempt marker 格式驗證與生成
│   │   ├── precondition.py                # Body-op precondition checks 
│   │   │
│   │   ├── [任務鏈與排程]
│   │   ├── chain_analyzer.py              # 任務鏈分析模組
│   │   ├── ticket_chain_index.py          # 任務鏈索引模組
│   │   ├── cycle_detector.py              # 循環依賴檢測模組
│   │   ├── critical_path.py               # 關鍵路徑分析模組
│   │   ├── wave_calculator.py             # Wave 自動計算模組
│   │   ├── parallel_analyzer.py           # 並行分析模組
│   │   ├── file_conflict.py               # where.files 交集判定共用實作（multi-PM 協調層 Phase 2/3）
│   │   ├── priority_utils.py              # 票清單優先級聚合工具
│   │   ├── staleness.py                   # 有效期 Stale 警告機制（PROP-010 方案 4）
│   │   ├── blocker_resolution.py          # Blocker 解除狀態判定共用 predicate
│   │   ├── tdd_sequence.py                # TDD 序列建議模組
│   │   ├── dispatch_recommender.py        # Dispatch Recommender - Agent 派發建議演算法
│   │   ├── dispatch_common.py             # 共用 dispatch-* CLI 前置處理
│   │   │
│   │   ├── [併發、身份與版控]
│   │   ├── lease.py                       # Lease 生命週期管理（multi-PM 協調層 Phase 3：claim/complete/release/reclaim）
│   │   ├── file_lock.py                   # Per-ticket-file advisory lock 模組
│   │   ├── identity_guard.py              # 身份申報守衛（identity guard）— --as 旗標與 ticket who.current 對照
│   │   ├── registry_loader.py             # Registry Loader - 共用的 registry 載入函式
│   │   ├── git_utils.py                   # md auto-commit 薄封裝
│   │   │
│   │   ├── [Handoff、worklog 與 checkpoint]
│   │   ├── handoff_utils.py               # Handoff 共用判斷函式模組
│   │   ├── worklog_appender.py            # Worklog 進度行自動追加模組
│   │   ├── worklog_parser.py              # Worklog 交接段落解析模組
│   │   ├── checkpoint_state.py            # CheckpointState dataclass + Checkpoint 推導 + 5 層 fail-open 資料來源 + 主函式 + 觀測 log
│   │   ├── checkpoint_view.py             # Checkpoint view function 模組
│   │   │
│   │   ├── [Plan 與規格]
│   │   ├── plan_parser.py                 # Plan 檔案解析器模組
│   │   ├── ticket_generator.py            # 生成模組
│   │   ├── spec_reference_checker.py      # SPEC 引用驗證模組
│   │   │
│   │   ├── [主題歸屬]
│   │   ├── topic_assignments.py           # ticket_id -> topic 映射（assignment log）的讀寫層
│   │   ├── topic_registry.py              # 主題中央清單的 append-only 讀寫層
│   │   │
│   │   ├── [訊息與常數]
│   │   ├── constants.py                   # System 常數定義（向後相容 shim）
│   │   ├── messages.py                    # 標準化訊息定義模組
│   │   ├── command_lifecycle_messages.py  # commands/ 批次 A 硬編碼字串集中化模組
│   │   ├── command_tracking_messages.py   # commands/ 批次 B 硬編碼字串集中化模組
│   │   ├── ui_constants.py                # UI 常數定義模組
│   │   │
│   │   ├── [路徑與環境]
│   │   ├── paths.py                       # 路徑管理模組
│   │   ├── project_root.py                # 專案根目錄解析工具
│   │   ├── machine_path_detector.py       # 機器專屬絕對路徑偵測模組
│   │   ├── claude_lib_loader.py           # 共用 `.claude/lib/` 動態載入與 git toplevel 解析工具
│   │   ├── version.py                     # 版本管理模組
│   │   ├── audit_version.py               # 版本審計模組
│   │   └── ambiguous_prefix.py            # 共用的 argparse 縮寫歧義攔截 helper
│   ├── commands/               # 子命令實作（48 個；各命令的用法與語意見 SKILL.md）
│   │   ├── __init__.py         # 匯出六大子命令
│   │   │
│   │   ├── [頂層命令]
│   │   ├── create.py                      # create 命令模組
│   │   ├── bulk_create.py                 # 批次建立 Ticket 命令模組
│   │   ├── generate.py                    # generate 命令模組
│   │   ├── handoff.py                     # handoff 命令模組
│   │   ├── handoff_gc.py                  # Handoff GC（垃圾清理）命令模組
│   │   ├── migrate.py                     # 遷移命令模組
│   │   ├── resume.py                      # resume 命令模組
│   │   ├── show.py                        # ticket show 子命令
│   │   ├── version_shift.py               # 版本遷移命令模組
│   │   ├── audit_version.py               # audit-version 子命令實作
│   │   ├── topic_backfill.py              # 既有 pending 票的主題分批回填入口
│   │   ├── lifecycle.py                   # lifecycle 操作模組
│   │   ├── fields.py                      # 5W1H 欄位操作模組
│   │   ├── claim_verification.py          # claim 命令的 AC 驗證子系統
│   │   ├── exceptions.py                  # Handoff 系統 Exception 階層
│   │   │
│   │   ├── [track 路由與核心操作]
│   │   ├── track.py                       # track 命令模組
│   │   ├── track_query.py                 # track 查詢操作模組
│   │   ├── track_relations.py             # 關係和狀態管理模組
│   │   ├── track_batch.py                 # 批量操作模組
│   │   ├── track_acceptance.py            # 驗收條件和執行日誌模組
│   │   ├── track_set_acceptance.py        # ticket track set-acceptance 子命令
│   │   ├── track_audit.py                 # audit 子命令實作
│   │   ├── track_validate.py              # ticket track validate 子命令
│   │   ├── track_board.py                 # 看板命令模組
│   │   ├── track_structured_body.py       # ticket track set-exit-status / set-completion-info 子命令
│   │   ├── track_exempt_marker.py         # ticket track add-exempt-marker 子命令
│   │   ├── track_multi_view_status.py     # ticket track fix-multi-view-status 子命令
│   │   │
│   │   ├── [track 排程、派發與診斷]
│   │   ├── track_runqueue.py              # ticket track runqueue 命令
│   │   ├── track_dashboard.py             # ticket track dashboard 命令
│   │   ├── track_stale_list.py            # ticket track stale-list 命令
│   │   ├── track_stuck_anas.py            # ticket track stuck-anas 命令
│   │   ├── track_td_status.py             # ticket track td-status 命令
│   │   ├── track_depth.py                 # track depth 查詢模組
│   │   ├── track_snapshot.py              # 專案狀態快照命令
│   │   ├── track_topics.py                # ticket track topics / topic 命令
│   │   ├── track_dispatch_check.py        # ticket track dispatch-check 命令
│   │   ├── track_dispatch_readiness.py    # ticket track dispatch-readiness 命令
│   │   ├── track_dispatch_validate.py     # ticket track dispatch-validate 命令
│   │   ├── track_parallel_check.py        # ticket track parallel-check 命令
│   │   ├── track_agent_status.py          # track agent-status 命令
│   │   ├── track_handoff_ready.py         # ticket track handoff-ready 命令
│   │   ├── track_checkpoint_status.py     # ticket track checkpoint-status 命令
│   │   ├── track_hook_health.py           # ticket track hook-health 命令
│   │   │
│   │   ├── [multi-PM 協調層]
│   │   ├── track_sessions.py              # ticket track sessions 命令
│   │   ├── track_activity.py              # ticket track activity 命令
│   │   ├── track_conflicts.py             # ticket track conflicts 命令
│   │   ├── track_onboard.py               # ticket track onboard 命令
│   │   └── track_artifacts.py             # ticket track register-artifact / resolve-artifact / list-artifacts 子命令
```

> **本節與 SKILL.md 的分工**：本節描述**檔案結構**——哪個模組放哪裡、承擔哪類職責；
> `SKILL.md` 描述**對外契約**——每個命令的旗標、語意與使用時機。`commands/` 的描述刻意
> 只標示該模組實作哪個命令，不重述用法，避免同一份契約寫在兩處而各自漂移。



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
  - 1.0.0-W4-001.1 (lib/a.dart)  <!-- skill-residue-exempt: 範例情境的示意路徑，非本專案實際檔案 -->
  - 1.0.0-W4-001.2 (lib/b.dart)  <!-- skill-residue-exempt: 範例情境的示意路徑，非本專案實際檔案 -->

理由: 任務間無依賴，檔案無重疊，可以並行執行
```

### TDD 順序建議（tdd_sequence.py）

`ticket create` 時，系統會根據任務類型自動建議合適的 TDD Phase 順序。

**任務類型與 TDD 順序對應**：

| 任務類型  | 代號 | TDD Phase 順序                        |
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
| DOC  | 文件、文檔、documentation、記錄 <!-- banned-term-exempt: keyword synonym enumeration for type matching --> |
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
