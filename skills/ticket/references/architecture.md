# Ticket 系統架構

> **何時讀**：查詢目錄結構、共用模組設計、自動化分析功能、系統模型設計自我描述完整版（含 named agent 三態生命週期），或覆核 skill 自身測試套件時；亦收錄 CLI 安裝與執行方式的完整說明。**亦由此進入**：`SKILL.md`〈系統模型（設計自我描述）〉節末（named agent 三態生命週期指標）、`SKILL.md`〈執行方式〉節（安裝指令指標）、`SKILL.md`〈執行方式〉節末（覆核測試指令指標）、`track-command.md`「Python 測試路徑推導」小節末（覆核測試指令指標）。
>
> **同目錄**：`track-command.md`（測試路徑推導與 skill 測試套件互相引用）、`workflow-execute.md` / `workflow-query.md`（依系統模型設計的執行/查詢決策樹）。
>
> **溯源**：本檔於本專案匯入 commit `f375ae675` 時即已存在，此後累積增補模組清單與用語校準；「覆核測試指令」章節於 2026-09-07 由 `SKILL.md`〈執行方式〉節末逐字搬入檔尾；「安裝與執行方式」章節同日由 `SKILL.md`〈執行方式〉節下的〈全局安裝（推薦，shim 化）〉〈本地執行〉兩子節逐字搬入（可用 `git log --oneline -- references/architecture.md` 查證）。

本檔章節：〈系統模型（設計自我描述，完整版）〉〈目錄結構〉〈共用模組設計〉〈自動化分析功能〉〈安裝與執行方式〉〈覆核測試指令（skill 自身測試套件）〉。

## 系統模型（設計自我描述，完整版）

本系統的參照模型是 **issue tracker + CI runner**（batch job queue 為輔助類比），不是 OS process。三個與 OS process 直覺相反的預設（設計回顧確認：誤用 process 直覺是共享樹競態與身份回填缺口兩類歷史事故的共同根因）：

1. **身份晚綁定**：ticket 建立時不知道執行者（submit 與 assign 分離）；身份在 claim 時以 `--as` 綁定，不是 fork 即繼承。
2. **共享工作區**：agent 預設共享 working tree（thread 語意）而非 process 隔離；檔案變更型派發應優先採 feat branch / worktree 隔離。
3. **type 與 instance 一對多**：agent 類型（能執行某類任務的角色，如「能做 IMP 的類型」）與執行體（實際在跑的 process）不是一對一，同一類型可同時 spawn 多個獨立執行體；「該類型只有一種」不等於「同時只能跑一個」。**反向風險**：誤讀為可無限開執行體同樣危險，真正的並行上限來自三項約束——共享 git index 的寫入競爭、主線程自身序列化的驗收與建票工作、單一執行體 context 隨任務數累積而飽和，而非類型數。

scheduler 層類比同樣成立：runqueue／dashboard 對應 Linux `schedule()`／`top`。

### named agent 生命週期三態（v2.9.0 擴展）

`agent = CI runner` 類比原僅二態（running → stopped），named agent（Agent tool 帶 name 參數 spawn）完工後不自動終止，實際存在第三態：

| 狀態 | 含義 | 觸發 | 對應 CI runner 語意 |
|------|------|------|---------------------|
| running | agent 正在執行 ticket 工作 | Agent tool spawn / SendMessage 派發新任務 | job 執行中 |
| idle | agent 完工無新任務，process 保持存活且可定址 | agent 完成回報後 CC runtime 發送 `idle_notification` | warm runner（跑完不銷，省下次冷啟動成本） |
| stopped | agent process 終止 | SubagentStop（自然結束）/ `shutdown_request` approve / session 結束 | job 完成後 runner 回收 |

idle 態不改變 agent = runner 的核心類比（身份仍在 claim 綁定、工作區仍隔離），只是擴展 runner 生命週期從「單 job 即銷」到「可選續用多 job」。PM 對 idle agent 的續用/放生判準與回收 SOP 見 `.claude/pm-rules/parallel-dispatch.md`「idle agent 回收 SOP」章節。

> SKILL.md 入口保留壓縮版三預設 + 一行指標，兩者不重複維護——本節為完整論證，入口為主張句速查。

---

## 目錄結構

```
.claude/skills/ticket/
├── SKILL.md                    # 入口文件 - 統一入口
├── pyproject.toml              # 套件定義（uv 管理）
├── ticket_system/              # 主套件目錄
│   ├── __init__.py
│   ├── lib/                    # 共用模組（72 個，依功能分組）
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
│   │   ├── absence_assertion_detector.py  # 缺席斷言未查證提示模組（PC-BAL-053 承接）
│   │   ├── ana_ticket_metadata_validator.py  # ANA Ticket metadata 品質驗證模組（PC-058）
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
│   │   ├── dispatch_skeleton.py           # Dispatch 骨架純組裝邏輯（供 CLI 與測試共用，抽離自 track_dispatch）
│   │   ├── relatedto_index.py             # relatedTo 反向索引模組（單向儲存、消費端 1-hop symmetric union）
│   │   │
│   │   ├── [併發、身份與版控]
│   │   ├── lease.py                       # Lease 生命週期管理（multi-PM 協調層 Phase 3：claim/complete/release/reclaim）
│   │   ├── file_lock.py                   # Per-ticket-file advisory lock 模組
│   │   ├── identity_guard.py              # 身份申報守衛（identity guard）— --as 旗標與 ticket who.current 對照
│   │   ├── registry_loader.py             # Registry Loader - 共用的 registry 載入函式
│   │   ├── git_utils.py                   # md auto-commit 薄封裝
│   │   ├── git_ops.py                     # 共用隔離索引提交（commit_files_isolated，供 auto-commit hook 與 lifecycle.complete() 共用）
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
│   ├── commands/               # 子命令實作（52 個；各命令的用法與語意見 SKILL.md）
│   │   ├── __init__.py         # 註冊 8 個頂層子命令（create/track/handoff/resume/migrate/generate/batch-create/show）；version-shift 另於 `ticket_system/scripts/ticket.py:150` 直接註冊
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
│   │   ├── track_set_closed_by.py         # ticket track set-closed-by 子命令（closed 票 closed_by 欄位修正路徑）
│   │   ├── track_commit.py                # ticket track commit 子命令（隔離索引提交 where.files 子集，取代裸 git add+commit）
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
│   │   ├── track_hook_liveness.py         # ticket track hook-liveness 命令（查 `.claude/hook-logs/_liveness/*.jsonl` 觸發記錄）
│   │   ├── track_dispatch.py              # ticket track dispatch 子命令（派發即落票：--note 落票派發日誌 + 輸出骨架 prompt）
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

### cycle_detector.py

循環依賴檢測模組（W7 新增）。以 `blockedBy` 依賴關係構建有向圖，DFS 演算法偵測環（時間複雜度 O(V+E)，V 為 Ticket 數、E 為依賴數），供 `validate_blocked_by` 在設定/更新 `blockedBy` 時攔截循環。`blockedBy` 讀取支援清單格式與逗號分隔字串兩種寫法（見 `ticket_validator.py` 標準化邏輯）。

| 函式                       | 用途                                       |
| -------------------------- | ------------------------------------------ |
| `CycleDetector.has_cycle()` | 檢測單一 Ticket 起點的依賴圖是否有環，回傳 `(bool, cycle_path)` |
| `CycleDetector.detect_cycles_in_all_tickets()` | 掃描全部 Ticket 找出所有環 |
| `CycleDetector.validate_blocked_by()` | 驗證新增/更新的 `blockedBy` 是否會產生循環 |

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

共用常數定義。canonical location 為 `ticket_system/constants.py`；`ticket_system/lib/constants.py` 為向後相容 shim（`from ticket_system.constants import *`），skill 內部與 hook 皆可用，理由見該檔 docstring（避免 hook 在無 yaml 系統 Python 環境下經 `lib/__init__.py` eager-import 觸發 `ModuleNotFoundError`）。

```python
# 狀態常數（ticket_system/constants.py:125-130）
STATUS_PENDING = "pending"
STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETED = "completed"
STATUS_BLOCKED = "blocked"
STATUS_SUPERSEDED = "superseded"
STATUS_CLOSED = "closed"

# 類型常數：正典 4 型為 dict，非個別 TYPE_* 常數（:279-284）
TICKET_TYPES = {
    "IMP": "Implementation (實作)",
    "ADJ": "Adjustment (調整/修復)",
    "ANA": "Analysis (分析)",
    "DOC": "Documentation (文件)",
}
# 歷史化石容忍集：讀取/審計接受、寫入拒絕（:288）
LEGACY_TICKET_TYPES = frozenset({"TST", "RES", "INV"})

# 路徑常數（:264）；無獨立 HANDOFF_PATH 常數，pending 目錄由 handoff_utils 動態組出
WORK_LOGS_DIR = "docs/work-logs"

# 正則表達式（:204，尾段含可選 slug 段）
TICKET_ID_PATTERN = r"^(\d+\.\d+\.\d+)-W(\d+)-(\d+(?:\.\d+)*)(-[a-z0-9][a-z0-9-]{0,59})?$"
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

## 安裝與執行方式

> **禁止直接執行 Python 檔案。** `ticket_system` 是 Python 套件，必須透過 `pyproject.toml` 定義的入口點執行。

### 全局安裝（推薦，shim 化）

`ticket` CLI 透過 cwd-resolving shim 安裝（非 `uv tool install`，ARCH-APP-002 / framework issue #12）：shim 依當前 cwd 所在專案的 git toplevel 解析 `.claude/skills/ticket` 源碼並 `uv run`，源碼修改後**無需重新安裝**、改動即時生效，多專案共用同名 skill 不碰撞。`uv-tool-staleness-check-hook` / `ticket-reinstall-hook` 兩 hook 仍註冊於 `.claude/settings.json`，非「已取代」：`ticket-reinstall-hook.py` 偵測到已 shim 化即略過；`uv-tool-staleness-check-hook.py` 無 shim 分支，兩者保留註冊為舊 `uv tool install` 路徑的殘留防護。

```bash
# 安裝 / 更新 shim（一次安裝 ticket / doc / worktree 三個 shim）
python3 .claude/scripts/install-skill-clis.py

# 檢查是否已 shim 化（exit 0/1）
python3 .claude/scripts/install-skill-clis.py --check

# 之後在任何目錄執行
ticket track summary
ticket track claim <id>
```

### 本地執行

```bash
(cd .claude/skills/ticket && uv run ticket track summary)
```

## 覆核測試指令（skill 自身測試套件）

> **唯一標準指令**：裸 `pytest`，不帶任何路徑參數。`pyproject.toml` 的 `[tool.pytest.ini_options]` 已設定 `testpaths = ["tests", "ticket_system/tests"]`，一次 pytest session 涵蓋 skill 根層 `tests/` 與 `ticket_system/tests/` 兩個目錄，無需（也不應）分開執行。

```bash
(cd .claude/skills/ticket && uv run --with pytest --with pyyaml --with filelock python -m pytest -q)
```

**禁止**：以顯式路徑（如 `pytest tests/`、`pytest ticket_system/tests`）作為覆核依據。顯式路徑參數會**覆蓋** `testpaths` 設定，僅收集單一目錄下的測試，另一目錄的測試會被靜默漏跑而不觸發任何錯誤或警告——覆核者若只跑其中一個目錄卻在 Test Results 宣稱「測試通過率 100%」，該宣稱在結構上未涵蓋另一半測試。

`ticket_system/tests/` 與 `tests/` 兩目錄並存的分裂現況、路徑推導細節見 `references/track-command.md`「Python 測試路徑推導」小節。
