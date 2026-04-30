## [1.28.0] - 2026-04-30

### Summary
feat: resume --list 改採 runqueue 排序; feat: 落地 agent 自律 complete 收尾責任; feat: ANA ticket metadata validation hook (+19 more)

Changes: 4 feat, 8 refactor, 2 fix, 4 docs, 2 chore, 2 test

- feat: resume --list 改採 runqueue 排序
- feat: 落地 agent 自律 complete 收尾責任
- feat: ANA ticket metadata validation hook
- feat: active-dispatch guard for process-skip-guard-hook
- refactor: 解耦 wrap-decision 外部引用 + 移除違規 README
- refactor: extract _is_fully_unblocked predicate
- refactor: extract cascade messages to command_lifecycle_messages
- refactor: introduce ChildOutcome + classify/dispatch in cascade
- refactor: inject ticket_map into _cascade_unblock_children + extract _post_complete_cascade
- refactor: AUQ hook keyword dedup + DRY
- refactor: extract where.files parsing to hook_utils
- refactor: Phase 4b polish _resolve_path_classification
- fix: _is_placeholder regex 加字邊界避免 substring 誤判
- fix: process-skip-guard PEP 723 缺 pyyaml + IMP-069 錯誤學習
- docs: 整合官方 skill-creator 規範並以 compositional-writing 重寫
- docs: add UTF-8 enforcement template to hook-architect-technical-reference
- docs: record PC-113 + PC-114 error patterns + memory
- docs: 補完 track-command.md 常見錯誤實測症狀
- chore: restore exec bit on transcript_tail_reader and related test files
- chore: complete ticket body + YAML quote fix
- test: add cascade save-order contract tests + docstring
- test: add boundary tests for _resolve_path_classification

---

## [1.27.1] - 2026-04-29

### Summary
sync .claude configuration

---

## [1.27.0] - 2026-04-29

### Summary
feat: phase3b 完成 16 整合測試 GREEN（migrate 反向引用 W11 重組情境）; feat: phase3b 完成 type/phase guard + 關鍵字精確化 GREEN; feat: GREEN — _resolve_path_classification helper L1+L2+L3 整合 (+12 more)

Changes: 9 feat, 2 docs, 4 chore, 1 test

- feat: phase3b 完成 16 整合測試 GREEN（migrate 反向引用 W11 重組情境）
- feat: phase3b 完成 type/phase guard + 關鍵字精確化 GREEN
- feat: GREEN — _resolve_path_classification helper L1+L2+L3 整合
- feat: 新增 Schema H2 idempotent dedupe 防止重複 placeholder
- feat: upgrade PROP-009 checklist validation from WARNING to blocking
- feat: mcp-write-tool guard hook + tool-selection rule
- feat: WRAP 研究 serena MCP 必要性 + 修正 search-tools-guide 過時紀錄
- feat: AGENT_PRELOAD + thyme 加入工具選擇規則防止 serena MCP 誤選與 early stop
- feat: basil v4 改用 progressive disclosure 載入策略
- docs: 新增 PC-112 — subagent 對非程式碼檔案誤選 MCP 寫入工具
- docs: PC-059 retry6 補強 — 主 repo cwd .claude/ subagent Edit 失效
- chore: phase2 sage 測試設計 RED 骨架
- chore: 寫入 Context Bundle + claim ticket
- chore: worklog + settings.local.json 同步
- test: Phase 2 RED — _resolve_path_classification helper 測試

---

## [1.26.0] - 2026-04-28

### Summary
feat: 情境 C/D/F/G 加入 basil-writing-critic 視角; feat: 新增 basil-writing-critic 至 registry.yaml 和 decision-tree.md; feat: stuck-anas CLI + source ANA / group 提示行（.13/.14 方案 D） (+6 more)

Changes: 3 feat, 1 refactor, 2 docs, 3 chore

- feat: 情境 C/D/F/G 加入 basil-writing-critic 視角
- feat: 新增 basil-writing-critic 至 registry.yaml 和 decision-tree.md
- feat: stuck-anas CLI + source ANA / group 提示行（.13/.14 方案 D）
- refactor: track.py 雙 dict 消除 5 命令 if-elif 雙軌
- docs: agents README 新增 basil 前綴群組命名說明
- docs: 補強 multi-pass review 層次意識（writing-articles.md ）
- chore: complete IMP — basil agent 手抄改 @-import 重構
- chore: complete IMP — wrap-decision SKILL 納入決策路徑層因子 5-8
- chore: complete IMP — PM session 結束自檢 checklist

---

## [1.25.0] - 2026-04-27

### Summary
feat: error-pattern README 新增「抽象層級分析」必填章節 + PC-111 backfill; feat: compositional-writing SKILL 原則 3 升級為「意圖顯性與層級貼合」

Changes: 2 feat

- feat: error-pattern README 新增「抽象層級分析」必填章節 + PC-111 backfill
- feat: compositional-writing SKILL 原則 3 升級為「意圖顯性與層級貼合」

---

## [1.24.0] - 2026-04-27

### Summary
feat: IMP-B/C/D 落地（PC-111 升級 + 2 張新 IMP ticket）; feat: pm-judgment-interference-map （ IMP-A 直接落地）; feat: 強化 agent 自定義 H2 防護（PC-110 根因 B 落地） (+26 more)

Changes: 7 feat, 3 fix, 16 docs, 3 chore

- feat: IMP-B/C/D 落地（PC-111 升級 + 2 張新 IMP ticket）
- feat: pm-judgment-interference-map （ IMP-A 直接落地）
- feat: 強化 agent 自定義 H2 防護（PC-110 根因 B 落地）
- feat: ANA 雙根因分析落地 + IMP-1/2 + PC-110
- feat: 擴充 charset hook 涵蓋 emoji + PC-085 + 隱含表達 6 句型
- feat: agent-prompt-length-guard 新增軟提示層偵測缺模板關鍵字
- feat: 擴充 agent-ticket-validation 白名單支援情報蒐集類 agent
- fix: validate_execution_log_by_type 章節定位改用 line-anchored regex 避免 backtick 誤判
- fix: validator + hook body-check false negative 症狀修復
- fix: 修復 body-check h3 子標題誤判章節結束 bug
- docs: frontend-with-playwright 更新主文與 references + 新增 principles 卡片
- docs: compositional-writing 更新主文與 references + 新增 principles 卡片
- docs: 新增 requirement-protocol skill — 從需求確認到實作的對話協議
- docs: 新增 frontend-with-playwright skill — 框架無關前端開發協議 + Playwright 驗證
- docs: compositional-writing 五大原則 → 六大原則 + 情境 5b 文集管理
- docs: session-switching-sop — worklog/CLI handoff 雙軌同步
- docs: PC-111 新增 R5 素材跨層誤推 + 素材溯源鏈 + R1 改寫
- docs: .2 pm-judgment-interference-map
- docs: PC-111 PM 論述編造 + 根因淺層歸因雙層錯誤
- docs: ARCH-020 驗證邏輯跨進程重複實作架構教訓
- docs: 新增 parallel-evaluation --skip-basil opt-out + 重寫 thyme-doc-integrator description
- docs: basil-writing-critic v2（3 職責 + Hook 層化 + 6 句型偵測）
- docs: 建立 basil-writing-critic agent definition 檔案
- docs: .1 + .3 派發流程範本化前台產出
- docs: 更新 hook 技術參考文件補充 / 新功能
- docs: 新增二次審查強制執行原則至 document-writing-style 與 compositional-writing
- chore: 修正 新建 hook 檔案執行權限 (IMP-054 auto-fix)
- chore: auto-fix exec bit for test_language_guard.py (IMP-054)
- chore: HookCheck 自動加上 test 檔執行權限 (IMP-054)

---

## [1.23.1] - 2026-04-22

### Summary
docs: add rule 6 — positive framing in anti-pattern sections

Changes: 1 docs

- docs: add rule 6 — positive framing in anti-pattern sections

---

## [1.23.0] - 2026-04-22

### Summary
feat: 新增 SessionStart Hook 偵測 .claude/ 未排除檔案 (.3); docs: 補充 sync 腳本排除清單分類規範與開發 checklist; docs: add PC-109 runtime state missing sync exclusion (.2)

Changes: 1 feat, 2 docs

- feat: 新增 SessionStart Hook 偵測 .claude/ 未排除檔案 (.3)
- docs: 補充 sync 腳本排除清單分類規範與開發 checklist
- docs: add PC-109 runtime state missing sync exclusion (.2)

---

## [1.22.2] - 2026-04-22

### Summary
fix: 修復 sync 腳本遺漏 runtime state 排除清單

Changes: 1 fix

- fix: 修復 sync 腳本遺漏 runtime state 排除清單

---

## [1.22.1] - 2026-04-22

### Summary
docs: 新增「最重要的話優先說」資訊優先序原則

Changes: 1 docs

- docs: 新增「最重要的話優先說」資訊優先序原則

---

## [1.22.0] - 2026-04-22

### Summary
feat: show runqueue after auto handoff; fix: remove dead version flag from ticket track; docs: complete dispatch plan templates (+6 more)

Changes: 1 feat, 1 fix, 7 docs

- feat: show runqueue after auto handoff
- fix: remove dead version flag from ticket track
- docs: complete dispatch plan templates
- docs: update hook system guidance
- docs: expand worktree operation guidance
- docs: clarify hook test execution with uv
- docs: record subagent completion lifecycle pattern
- docs: point handoff prompt to runqueue
- docs: switch ticket resume entry to runqueue

---

## [1.21.1] - 2026-04-21

### Summary
docs: 補完 check/set-acceptance 語法組合表 + 決策樹 + 5 常見錯誤警示; docs: 補列 set-blocked-by / set-related-to / set-acceptance CLI 範例

Changes: 2 docs

- docs: 補完 check/set-acceptance 語法組合表 + 決策樹 + 5 常見錯誤警示
- docs: 補列 set-blocked-by / set-related-to / set-acceptance CLI 範例

---

## [1.21.0] - 2026-04-21

### Summary
feat: 落地 軸 C 規則面（runqueue spawned 加權）; feat: session-start hook 新增 spawned pending 提醒; feat: 落地 軸 D 規則面（session-switching-sop Spawned 推進清單） (+4 more)

Changes: 5 feat, 1 fix, 1 docs

- feat: 落地 軸 C 規則面（runqueue spawned 加權）
- feat: session-start hook 新增 spawned pending 提醒
- feat: 落地 軸 D 規則面（session-switching-sop Spawned 推進清單）
- feat: 落地 軸 B priority 繼承 + PC-105 CLI autopilot
- feat: 落地 軸 A+C 規則擴充 + PC-075 擴充（/042 complete）
- fix: _is_placeholder 剝除 HTML 註解後再判斷實質內容
- docs: 核心文件路徑示範改三層結構（v{major}/v{minor}/v{patch}/tickets）

---

## [1.20.0] - 2026-04-21

### Summary
feat: 優化 Context Bundle extractor P2 風格與增強項; feat: Context Bundle CLI wire-in (create + claim); feat: 實作 Context Bundle 自動抽取機制 (+25 more)

Changes: 12 feat, 1 fix, 11 docs, 4 chore

- feat: 優化 Context Bundle extractor P2 風格與增強項
- feat: Context Bundle CLI wire-in (create + claim)
- feat: 實作 Context Bundle 自動抽取機制
- feat: NeedsContext + Exit Status protocol + hook listener
- feat: sync completed_at to body Completion Info on ticket complete
- feat: type-aware ticket body schema
- feat: append-log VALID_SECTIONS 加入 Context Bundle
- feat: dispatch hook fallback 讀 ticket where.files
- feat: 新建 session-start-scheduler-hint-hook（排程上下文恢復）
- feat: 實作 ticket track runqueue 統一 scheduler CLI
- feat: ticket handoff --auto 自動生成模式
- feat: group ticket + 11 children 清理 遺漏項
- fix: patch validate_execution_log_by_type mock + close ticket
- docs: 新增 PC-107 Phase 3b 派發前未走拆分檢查
- docs: agent body 填寫責任標準化
- docs: 文件化 create --source-ticket 副作用 + parent vs source 對比表
- docs: PC-106 規則失效跳過讀 code + .2 claim
- docs: PC-105 新功能實作後缺乏文件引導整合（雙通道）
- docs: 補 runqueue scheduler CLI 引導文件（4 檔）
- docs: SKILL.md 補 ticket show 子命令使用範例與短 flag 對照
- docs: PC-104 Agent 執行邊界誤判導致結果未落地（雙通道）
- docs: 新增 PC-103 大型類比框架維度漏排（雙通道）
- docs: 補 group + 11 children Context Bundle + group methodology
- docs: 新增 PC-100 / PC-101 錯誤學習（雙通道記錄）
- chore: 並行 session 未提交變更收整（scheduler hint hook 測試 + + worklog）
- chore: complete .4 hook + group 收尾
- chore: show enhancement commit（他人並行產出收整）
- chore: .1 ticket show 實作登錄 + worklog 更新（pre-dispatch）

---

## [1.19.0] - 2026-04-20

### Summary
feat: 新增 ticket track dispatch-check CLI (PC-050 CLI 化); docs: worklog 進度追加 + PC-077 累積 Meta 循環案例; docs: 建立 plugin 管理準則文件 (+1 more)

Changes: 1 feat, 2 docs, 1 chore

- feat: 新增 ticket track dispatch-check CLI (PC-050 CLI 化)
- docs: worklog 進度追加 + PC-077 累積 Meta 循環案例
- docs: 建立 plugin 管理準則文件
- chore: 版號基底修正 + complete

---

## [1.18.0] - 2026-04-20

### Summary
feat: add TestDictFieldFlattenRegression tests; feat: Phase 4 添加檔級 self-reference 豁免機制; feat: implement PC-093 phase4 decision enforcement hook (+542 more)

Changes: 126 feat, 43 refactor, 103 fix, 228 docs, 39 chore, 5 test, 1 perf

- feat: add TestDictFieldFlattenRegression tests
- feat: Phase 4 添加檔級 self-reference 豁免機制
- feat: implement PC-093 phase4 decision enforcement hook
- feat: 新增文件撰寫明示性原則規則
- feat: tiered verdict for agent-dispatch-validation hook
- feat: Phase 3b GREEN 落地三命令決策建議型輸出
- feat: implement whitelist filter rules A-D
- feat: 擴充 FORBIDDEN_KEYWORD_MAP A-F 六類新 pattern
- feat: Phase 3b GREEN - dispatch_stats.py + hook JSONL event 寫入
- feat: Phase 3b 派發 3 - Group D+E + 主函式整合
- feat: Phase 3b 派發 2 Group B+F 5 層 fail-open 資料來源 + 模組邊界
- feat: Phase 3b 派發 1 (Group A+C) CheckpointState dataclass + _derive_checkpoint
- feat: agent-dispatch-validation Hook 新增禁止行為關鍵字衝突掃描
- feat: agent-dispatch-validation hook 偵測並行場景廣域 staging
- feat: 新建 agent-definition-standard 規則 + 補 2 agent 三區塊
- feat: 固化 PM prompt 職責邊界聲明模板
- feat: 刪除被取代的方法論檔 + 清理殘留引用
- feat: 實作 portability-check.sh 可攜性自動掃描腳本（Phase 1）
- feat: 擴充 ticket CLI close --reason 枚舉驗證
- feat: 建立 PC-090 推延性 close 反模式 error-pattern
- feat: 擴充 ticket-lifecycle.md close 條件規則（C1-C4）
- feat: 執行 PC-088 v2 find_files 子類因果驗證（Path A）
- feat: 依 E3 實驗結果更新 PC-088 v2 分類防護策略
- feat: wrap-tripwire-hook category 分流 + reflection_trigger
- feat: 更新 wrap-decision SKILL 觸發條件 + tdd-flow Phase 4 引用
- feat: 擴充 ticket deps 指令反思鏈深度警示（Layer 2）
- feat: 新增 pm-rules 反思終止閘門規則（Layer 3）
- feat: 擴充 wrap-triggers.yaml 新增 S4 反思訊號 + category 欄位
- feat: 新增 three-phase-reflection-methodology 終止條件章節
- feat: 新增 scripts/experiments/ 到 branch-verify-hook 豁免
- feat: 新增 ticket track deps 命令顯示衍生關係
- feat: 擴展 acceptance-auditor 與 gate-hook 檢查 spawned_tickets
- feat: WRAP skill A 階段擴充 tool-selection layer
- feat: 新增 bash 規則五 heredoc 長文字傳遞預設
- feat: 新增 set-acceptance 和 validate 子命令（）
- feat: 新建 ticket-frontmatter-validator Hook 事後警告 frontmatter YAML 違規
- feat: §5.4 Layer 4 新增訊號偵測/觸發閾值/PM 降權三表（）
- feat: §5.11 監測機制具體化（019.5 Phase A 落地）
- feat: 新增規則 5 權力不對等下的對話品質（.2）
- feat: 新增 writing-articles 完整文章情境 reference
- feat: 擴充 charset guard hook 偵測日文漢字污染
- feat: 升級 writing-prompts 為 ai-communication-rules 框架規範
- feat: wrap-decision skill A 階段補框架檢查（PC-080 防護升級）
- feat: 新增規則四 PC-079 防護到 bash-tool-usage-rules.md
- feat: skills/ + templates/ emoji 全清 + .4.{1,2,3} complete
- feat: templates emoji 全清 + 拆 .4 為 3 子任務
- feat: Hook stdout emoji 替換為 ASCII 標記（PM 輸出污染源清理）
- feat: Phase 3b Commit 2 - CLI 整合 source-ticket 參數
- feat: Phase 3b Commit 1 - builder 層新增 source_ticket 支援
- feat: ANA spawned 非 terminal CLI 閘門（PC-075 Phase 2 遺留）
- feat: PC-072 charset guard 補強「隶/遗」攔截清單
- feat: ana_spawned_checker Phase 1 警告層 + dedicated field
- feat: tripwire-catalog.md L27/L96 清洗（ 5 子任務全完成）
- feat: SKILL.md 6 處正文前向引用清除（依 F 案指向尾部索引）+
- feat: AUQ payload 字元集攔截 Hook
- feat: source-verification.md L38 死連結修復
- feat: wrap-decision SKILL.md 專案術語清洗 + PC-073
- feat: wrap-decision SKILL.md description 從 423 字瘦身至 238 字
- feat: Ticket 建立年齡 stale 警告機制（PROP-010 方案 4）
- feat: 完成 + compositional-writing Skill 建立（11 代理人並行產出）
- feat: 實作互動層 + lifecycle 整合 + Group F/G/H/K 測試
- feat: commit 新建檔案（3 SOP + quality-common references）
- feat: 實作 AC 驗證執行層 5 函式 + Group D/E/I/J 測試
- feat: 實作 AC 驗證資料層 + Group A-C 測試
- feat: 升級 agent-commit-verification-hook 為 SubagentStop-driven + 文件更新
- feat: 升級 dispatch-tracker 為 SubagentStop-driven
- feat: 強化 PM 代理人狀態查詢防護（pm-role Step 0.5-A + 決策樹 + agent-status CLI）
- feat: 建立 Hook 完成訊號誤觸 ANA ticket + PC-070
- feat: 批次修復 37 處 subprocess 呼叫補齊 UTF-8 encoding
- feat: Windows 平台 Hook 跨平台支援三項核心改善
- feat: wrap-decision-tripwire-hook 實作完成（basil）
- feat: SKILL 簡化三問與 claim 觸發條件完成（thyme）
- feat: 規則 8 違規清理完成（thyme）
- feat: 執行 .claude/ 根目錄清理 — REMOVE 16 + ARCHIVE 2 + MIGRATE 2
- feat: Phase 1 功能規格設計完成（lavender）
- feat: acceptance-gate-hook 強制 ANA Solution multi_view_status 標註
- feat: PC-066 決策品質防護單點強制 + fallback 結構
- feat: 完成 Meta ANA — 開發流程摩擦力配置倒置結構性分析
- feat: 強化 saffron Phase 0 系統衝突檢查 checklist
- feat: 產出 proposal-evaluation-gate 規則 + 完成 M-1 ANA
- feat: 實作 agent-dispatch Hook 路徑分類與 .claude/ 豁免
- feat: 實作 acceptance-gate-hook 父 complete 前置 block 檢查
- feat: Phase 3b AUQ Option Pattern Detector Hook 實作（16 測試全綠）
- feat: ticket claim ANA 簡化 WRAP 新增 Reality Test 第四問（PC-063 防護 4）
- feat: 新增 ANA Ticket 模板「重現實驗結果」必填章節（PC-063 防護 1）
- feat: 修復 測試範本 版本字面值污染根治（F+D 方案）
- feat: 放寬 Hook 允許主線程直接編輯 .gitignore
- feat: 擴充 ticket claim 附加簡化 WRAP 三問提示
- feat: 10 個代理人加入 permissionMode: bypassPermissions + 新增 authoring guide
- feat: 父 complete 自動解鎖子 Ticket + children 警告
- feat: 全域授權 Edit/Write/Grep + 新增 + PC-058
- feat: 實作 ac_parser ( Phase 3b-B)
- feat: 實作 validation_templates ( Phase 3b-A)
- feat: Phase 1-2 產出（AC 解析器設計 + RED 測試）
- feat: 新增 Hook output JSON schema 驗證腳本
- feat: 新增 UTF-8 完整性檢查 Hook（）
- feat: version-consistency-guard 新增版本註冊狀態檢查（）
- feat: ticket create 版本存在性檢查（）
- feat: WRAP — 新增 Consider the Opposite + Zoom Out 搜尋範圍確認（）
- feat: 統一 emit_hook_output helper + 3 Hook 遷移（）
- feat: bash-tool-usage 新增 chpwd Shell Hook 環境警告（IMP-056）
- feat: acceptance-gate 新增 Complete 清單式驗證（PROP-009 面向 C）
- feat: PROP-009 面向 A — 新增 5 個 CLI 欄位命令
- feat: PROP-009 面向 B — create 清單式欄位驗證
- feat: agent-commit-verification-hook 新增 Hook error 自動摘要（）
- feat: acceptance-gate-hook 新增 error-pattern 衝突檢查（Step 2.7, ）
- feat: 新增 dispatch-record-hook 記錄代理人派發到 dispatch-active.json
- feat: .2 新增 Checkpoint 0.5 PM 進度更新時機
- feat: 新增 ticket track close 指令 + ~006 改用 close 結案
- feat: PM-代理人解耦自動化（snapshot 命令 + 查詢範圍限制）
- feat: 合併 PostToolUse:Bash hooks 從 12 個精簡為 7 個
- feat: 實作 ticket track search 和 list --version all
- feat: agent-dispatch-logger-hook 自動記錄 Agent 派發
- feat: 修正派工規則 — 從行數閾值改為 tool call 預算模型
- feat: 派工改善方案落地 — 規則更新三件組
- feat: 擴充 Worktree 狀態檢查流程（PC-039）
- feat: agent-commit-verification-hook 新增 worktree 合併檢查（）
- feat: 完成 — worktree-merge-reminder-hook 實作 + 註冊
- feat: + 實作完成 — ticket create why 必填 + commit-before-dispatch Hook
- feat: W2 規劃 — resume next-wave 修正 + 7 個實作 Ticket 建立
- feat: 新增 /version-release start 子命令 + 修復 handoff stop hook 誤觸發
- feat: 完成 — worktree 基底距離驗證 Hook 新增
- feat: /bugfix 新增測試完整性保護規則（）
- feat: 新增 evidence-driven-bugfix Skill（證據驅動除錯流程 ）
- feat: Wave 收尾流程加入多視角審查建議（）
- feat: 新增 session 經驗持久化提醒 Stop hook（）
- refactor: Phase 4b P2 追蹤集合清理
- refactor: lift blockers to lib + PRIORITIES NamedTuple + reuse render_ready_check
- refactor: Phase 4b P0 caller Literal 一致性 + degraded snapshot DRY
- refactor: whitelist rules driven by list iteration (eliminate _rule_b_wrapper)
- refactor: 扁平化 annotate_event 移除 overwrote_different 旗標
- refactor: 收斂 dispatch_stats path helper 為 _resolve_path
- refactor: Phase 4 三視角共識重構 dispatch_stats.py
- refactor: __all__ 收斂私有符號 (C1)
- refactor: metrics log rotate 擴充多份保留 (TD3)
- refactor: phase_label/next_action 抽 view function (L10)
- refactor: DATA_SOURCES table 提煉 5 SAFE_CALL (R1)
- refactor: _run_subprocess helper 統一 subprocess 呼叫 (R3)
- refactor: _read_json_dict helper 統一 JSON 讀取 (R4)
- refactor: caller 欄位 Literal 型別 (TD6)
- refactor: 移除防禦性 list/dict copy 冗餘 (linux L8)
- refactor: Phase 4 immediate (TD1+TD5+L7+L11)
- refactor: target-based agent-dispatch-validation hook (ARCH-015 修正落地)
- refactor: 消除 AUQ 象限標註 DRY 違反（單一來源重構）
- refactor: PC-088 框架重寫 + 方法論升級 Phase 3
- refactor: track_validate 改 import 共用 frontmatter_validator
- refactor: 整併 TERMINAL_STATUSES 為單一來源 (hook+skill 共用)
- refactor: 消除 commands/ 模組 local re-import 反模式
- refactor: 抽取 checkbox 前綴解析為共用模組
- refactor: test_wrap_decision_tripwire_hook DEFAULT_YAML 改結構化 fixture
- refactor: wrap-decision-tripwire 群組 B + CE-3 品質重構
- refactor: wrap-decision-tripwire 群組 A 結構重構
- refactor: Phase 4 — 2 件下游風險項 + 8 件風格精修
- refactor: 完成 — 摩擦力方法論分層拆分
- refactor: task-splitting 核心目標重定位為 SRP 品質（.3）
- refactor: WRAP 重分析後移除 task-splitting 重複三階表格（.3）
- refactor: acceptance-gate-hook God Hook 拆分（）
- refactor: completion-checkpoint 複雜度拆分（157→101 行）
- refactor: 決策樹二元化拆分 — 主檔案精簡為路由索引 + 5 個路由子檔案
- refactor: /009 Hook 輸出機制統一 variant B + 低優先級清理
- refactor: 消除 EXCEPTION 層，path_permission 改為 ALLOWED 優先檢查
- refactor: 路徑權限邏輯提取至 lib/path_permission.py，Hook 從 444 行降至 172 行
- refactor: dart_parser 泛型 regex 改為通用 PascalCase<...> 模式
- refactor: 統一 27 個 Hook stdin JSON 解析到 read_json_from_stdin (IMP-048 根治)
- refactor: 拆分檔案語義化重新命名（用戶反饋）
- refactor: decision-tree DDD domain 拆分為 4 檔案 (.1)
- refactor: 多視角審查修正 — Context Bundle 精簡 + 不一致修復
- refactor: 多視角審查修正 — DRY 精簡 + phase3b-dispatch-guide 更新
- refactor: TDD SKILL 全面重整 + worktree 自動 commit hook
- fix: 新增 git_update_index_chmod 治本 Windows mode loss
- fix: sanity check + BOM strip 防護版號異常跳躍
- fix: restore hook executable bits in sync-pull/push
- fix: acceptance-gate-hook #17 meta-ticket attribution filter
- fix: support top-level YAML lists in hook_utils parser
- fix: scan_hook_errors regex-based log level matching
- fix: align acceptance_checker data source to frontmatter
- fix: calibrate whitelist rule windows (path/negation/meta)
- fix: meta-task whitelist per-match degrade (TD-2 security)
- fix: 限縮 thyme-extension-engineer allowed-tools
- fix: 修正 ANA 落地 Ticket 血緣關係 + 升級規則防護
- fix: ticket resume 兼容 legacy v{id}-handoff.json 命名
- fix: 補 ticket-frontmatter-validator-hook 執行權限
- fix: 修復 acceptance-gate-hook yaml import regression
- fix: 修正 test_project_root_symmetry.py 日文漢字「両」污染
- fix: 新增 pytest-mock 依賴修復 26 個 fixture setup 失敗
- fix: 刪除測試中的 emoji 而非還原（規則 3 絕對禁 emoji）
- fix: 移除 execute_claim local re-import 恢復測試 mock 攔截
- fix: version_shift 直接讀檔避開 load_ticket project_root 隱式依賴
- fix: 新增 PC-078 + 還原 誤 release（PC-076 交叉引用）
- fix: 修正 AUQ charset guard Hook 繁簡共用字「出」false positive + PC-074
- fix: 解除 dispatch-validation-hook .claude/+docs/ 雙向阻塞
- fix: 清理 .claude/ 框架文件中的簡體字和禁用詞（48 處 / 33 檔案）
- fix: PostToolUse(Agent) 背景派發時機套用 模板至剩餘 3 Hook
- fix: active-dispatch-tracker-hook 時機與訊息三態修正
- fix: main-thread 白名單加入 .claude/output-styles/
- fix: thyme-documentation-integrator 補 permissionMode: acceptEdits
- fix: 修復 ticket migrate parent_id typo 與 cross_references 誤跳過
- fix: thyme permissionMode 改為 bypassPermissions
- fix: thyme-python-developer 加入 permissionMode: acceptEdits
- fix: GREEN — 跨版本 blockedBy 支援
- fix: 修復 agent-ticket-validation-hook JSON 輸出格式（IMP-055）
- fix: 修正 PostToolUse:Agent hook JSON 輸出格式（IMP-055 再發）
- fix: 修復 handoff-auto-resume-stop-hook 路徑查找支援三層階層結構
- fix: 修復 3 個文件的 UTF-8 截斷亂碼（auto-compaction 邊界問題）
- fix: 修復 children/spawned checker YAML list 型別處理（）
- fix: 修復雙 JSON stdout 問題 — bash-edit-guard + pre-test（）
- fix: 8 個 Pre/PostToolUse Hook stdout JSON 合規修復（IMP-055）
- fix: Ticket 遷移至階層結構 + 防止跨專案版本目錄污染
- fix: 4 個 PostToolUse:Bash Hook 新增 subagent 跳過（ WRAP 結論）
- fix: 修正 3 個 PostToolUse Hook stdout 輸出為 JSON 格式（）
- fix: Hook 權限修正 + completeness-check 權限自動防護 + dataclass 欄位順序 bug 修復
- fix: WRAP 修正 — 選擇性回退 + exit code 規範統一
- fix: Hook exit code 統一為 0 — 避免 CLI 顯示 hook error
- fix: project-init gitignore 檢查新增 .claude/dispatch-active 規則
- fix: 補強 — 代理人完成時自動報告剩餘活躍派發數量
- fix: 確保 Hook stdout 一定有 JSON 輸出（防止空輸出觸發 hook error）
- fix: 修復 Hook exit code 問題 — 異常時改為 exit 0 + JSON additionalContext
- fix: 改善代理人完成後的分支偵測和 PM 提示流程
- fix: registry 範圍釐清 + dispatch 觸發優先級整合
- fix: 決策路由完整性 + 術語一致性 + 命名更新
- fix: .3 流程圖拆分明確性/類型判斷 + 閘門職責純化
- fix: .1 路徑表新增 thyme-extension-engineer + 查詢規則分工修正
- fix: snapshot 統計修正 closed Ticket 從分母排除並獨立顯示
- fix: PC-046 ticket CLI 改為全域直接呼叫，移除多餘 cd+uv run
- fix: PC-045 追加修正 — PM 背景派發後立刻切換，禁止空等（pm-role ）
- fix: PC-045 PM 禁止寫產品程式碼 + 代理人失敗 SOP（pm-role ）
- fix: 修復 PM 派發流程引導缺失（PC-040 防護）
- fix: 修復 test_track_query 10 個測試 mock 路徑和方式錯誤
- fix: /004 Hook 寫入保護 + 廢棄常數清理 + where 三元式重構
- fix: /002 track_query 跨版本標題修正 + flag fallback 死碼清理
- fix: ~007 W9 審查發現批次修復
- fix: parallel-evaluation 強制延後項目必須建 Ticket — SKILL + 方法論同步更新
- fix: W10 修復 check_changelog_update tool_result 欄位名錯誤 + 補建 4 個審查追蹤 Ticket
- fix: W9 審查清理 — 刪除原始 hooks + 修復 6 項發現 + 建立 4 個追蹤 Ticket
- fix: ANA Ticket 驗收流程新增衍生 Ticket 強制檢查
- fix: dispatch_tracker 並行寫入加入 fcntl.flock 檔案鎖防護
- fix: dispatch_tracker 3 個 except 區塊補充 stderr 可觀測性日誌
- fix: detect_orphan_branches 改為精確 branch name 比對
- fix: 註冊 3 個未登記 Hook + 排除 2 個非 Hook 腳本
- fix: 補齊其餘 12 個 Hook 的 read_json_from_stdin None guard
- fix: 修復 4 個 Hook read_json_from_stdin None guard
- fix: 註冊 active-dispatch-tracker-hook 到 settings.json
- fix: 整合 dispatch 警告到 edit restriction + worktree SOP 更新
- fix: 建立 active dispatch tracker 共用模組和 Hook
- fix: 修復 test_manual_verification 測試 pyproject.toml 缺少 scripts 段落
- fix: 修復 javascript_parser TS arrow function 型別註解匹配
- fix: 修復 dart_parser 巢狀泛型匹配支援多行函式簽名
- fix: 修復散布的 38 個 FAILED 測試（35 修復 + 3 待追蹤）
- fix: 修復 5w1h-compliance-check-hook 26 個 FAILED 測試
- fix: 修復 test_agent_dispatch_check 56 個 FAILED 測試
- fix: 修復 4 個 Hook 測試 collection errors
- fix: Hook stdin JSON 解析統一防護分析 + P0 修復
- fix: StreamHandler level WARNING→CRITICAL 防止 hook error 顯示
- fix: 5 個 Hook json.load(sys.stdin) 加 JSONDecodeError 保護
- fix: PM 角色規則 v2.0 — 前台分析+背景實作分工
- fix: phase3b-dispatch-guide L27 明確指向 Ticket Context Bundle (PC-040)
- fix: 移除「嵌入 prompt」後門，強制 context 存 Ticket
- fix: Context Bundle CLI section 修正 + 品質基線新增文件即知識原則
- fix: 修復方向修正 — ticket create 強制 why 必填（非 resume 檢查）
- fix: handoff stop hook reason 從複述改為引導檢查
- fix: 修正 todolist.yaml 活躍版本 — 補上 ，對齊 CLAUDE.md 里程碑
- fix: /006 完成 — worktree 污染緩解 + 過時分支根因分析
- fix: 規格文件引用穩定性 — 移除 ticket 引用，建立規則 7
- fix: Hook 允許清單加入 CHANGELOG.md（主線程編輯 + 保護分支豁免）
- fix: resume.py INVALID_OPERATION 語義修正 + _execute_resume routing 抽離（, ）
- fix: 多視角審查修復 — resume 審計記錄、direction 分支、DRY 違規（）
- fix: ticket resume 已完成 Ticket 時自動導向 handoff 目標（）
- fix: preflight Phase emoji 檢查改為 Ticket 完成率驗證（）
- fix: 修復 ticket list --wave 跨版本搜尋失敗（）
- fix: 修正 version-release Skill 路徑/專案類型/CLI 不一致（）
- fix: 修正 ticket CLI 版本解析優先從 ID 提取（）+ 建立
- fix: 修正 index.lock 殘留 + hook 權限問題（, ）
- docs: IMP-067 + IMP-068 雙通道記錄
- docs: Windows 使用者 sync-push 注意事項文件
- docs: basil completion docs + PC-099 + main log
- docs: add PC-099 meta-ticket self-reference hook false positive
- docs: rewrite PC-066 with three-explicit principle (Why/Consequence/Action)
- docs: expand comment writing principles (business context + abstraction layer)
- docs: 新增 PC-098 PM 寫規則本能引用 ticket ID
- docs: Phase 4 follow-up tickets + error-patterns
- docs: Phase 3a 4 視角審查修正（priority table + except whitelist + Optional）
- docs: 補 6 agent description 三區塊（batch 5）
- docs: parallel-dispatch.md 新增「並行場景路徑區分（.claude/ vs src/）」
- docs: parallel-dispatch.md 加入 PC-092 精準 staging 規則
- docs: 新增 IMP-066 記錄 subagent-worktree ticket 不可見模式
- docs: ARCH-015 重驗完成，修正為「target 是否在主 repo 樹內」為分界線
- docs: 記錄並行代理人 git index 競爭錯誤模式
- docs: 補 7 agent description 三區塊內容（batch 2 實體變更）
- docs: 補 6 agent description 三區塊（batch 4）
- docs: 新增 TDD Phase 代理人職責清單表格
- docs: 新增 AUQ 選項前提檢查規則，封閉假選項漏洞
- docs: 移除 SKILL.md Version 歷史殘留 標註
- docs: 補齊 dry-run-guide.md 於 SKILL.md 路由
- docs: 聚合 designing-fields.md §6 十二欄位結構
- docs: 重構 writing-logs.md 章節聚合 + 自包含修復
- docs: 拆分 writing-prompts.md 雙職責
- docs: 新增 Phase 2 dry-run 流程文件（可攜性語意層驗收）
- docs: 遷移框架引用從既有方法論指向新 Skill
- docs: 新增 PC-089 hook 豁免路徑與 ticket 範圍不一致
- docs: IMP-065 CLI 單檔查詢檔名約定 vs 批量欄位比對不一致
- docs: 新增 PC-088 LLM 預設 tool selection 架構層偏誤
- docs: 新增 PC-087 PM 寫 /tmp 中介檔繞路
- docs: 新增 PC-086 subagent 建 Hook 缺 exec bit
- docs: 新增題型判別輔助與 PC-064 適用邊界章節（019.4 Phase A）
- docs: 規則 6 新增 Recommended 標籤分級（Phase A / 019.3 方案 G）
- docs: 擴充 wrap-decision skill 以四輪查詢方法論
- docs: 新建 PC-085 記錄 CJK codepoint 相鄰肉眼混淆錯誤模式
- docs: 追加 session 案例實證
- docs: 新建 PC-084 繁日共用字誤判 error-pattern
- docs: PC-083 framework footer Wave ID 污染 + 完成
- docs: 決策樹新增「並行 Session/Terminal 判斷層」(PC-078)
- docs: TEST-006 pytest plugin fixture 依賴未宣告導致全類 setup error
- docs: 新增 PC-082 regression 修復方向偏見（還原 vs 移除）
- docs: 新增 PC-081 PM 保守偏見（自我檢查比用戶規則更嚴格）
- docs: IMP-064 函式體 local re-import 遮蔽 unittest.mock.patch
- docs: language-constraints emoji 範例改寫 + complete
- docs: 新增 PC-080 WRAP A 階段框架檢查未做
- docs: 新增 PC-079 Bash CLI 參數 backtick substitution
- docs: 新增 PC-076/077 + 小幅清理
- docs: PC-075 spawned-children 狀態檢查語義不對稱
- docs: 建立污染再現追查 ANA + PC-072 再現紀錄
- docs: wrap-decision 通用 4 檔版本尾註轉換歷史清理
- docs: 新增品質基線規則 6 失敗案例學習原則
- docs: PC-072 AUQ payload 字元集污染 + ANA Ticket 調查系統性污染源
- docs: wrap-decision 多視角審查報告 + W12 修復 Ticket 結構建立
- docs: 合併 W5 同根 Hook 任務為子任務 — 4 個 ticket 遷入 (.8~.11)
- docs: 代理人 model 重新評估 — 26 個代理人按 4 維度分類
- docs: mark complete + 同步其他 session 變更
- docs: mark complete + worklog 更新
- docs: 文件化 AC 漂移偵測機制（PC-055 / PROP-010 防護）
- docs: 父 Ticket 完成 + 同步其他 session 變更
- docs: mark .1.3 complete + 同步其他 session 變更
- docs: 新增 Hook 路徑分類混淆 context vs target 錯誤模式
- docs: 撰寫 personalized-consultation-methodology
- docs: WRAP skill 新增 Step 0 資料充足度檢查章節
- docs: 建立 personalized-advice-rules PM rule
- docs: 建立 PC-071 advice-without-personal-context error-pattern
- docs: Hook event 選擇指引三檔交叉引用網
- docs: wrap-decision R 階段新增「來源核對」章節防 LLM 清單幻覺
- docs: 建立 ARCH-019 Hook event 時機錯位錯誤模式
- docs: 完成 CC runtime Hook events 調研並 spawn /067
- docs: 收編 PC-070 為模式 E，建立代理人狀態誤判家族全景
- docs: PC-069 Subagent 被擋時多檔機械性修改的批次腳本策略
- docs: 新增 PC-068 Phase 3a 規劃新建既有 utility 而未先掃描重用
- docs: 修正 subagent .claude/ Edit 限制範圍 — 主 repo 也被擋
- docs: 新增 PC-067 執行 ANA 規劃時未質疑規劃本身設計品質
- docs: 擴充 friction-management-methodology v3.0 新增流程階段摩擦力曲線
- docs: 完成實作並新建 ARCH-018 + 系統性審查
- docs: 引入串行兄弟合法模式，解決 ARCH-017 自身矛盾
- docs: 標註 Hook 形式驗證 vs acceptance-auditor 實質驗收邊界
- docs: 修復 atomic-ticket-methodology.md 規則 8 違反
- docs: 修復 ticket-lifecycle-details.md 規則 8 違反
- docs: 補強 Ticket 任務設計、拆分、銜接實務指南
- docs: 更新 skills/ticket references 呼應任務鏈哲學與父子規則
- docs: 擴展 ticket-lifecycle 規則強制父 complete 需子全部 completed
- docs: 新增 IMP-061 migrate bug + ARCH-017 兄弟無依賴原則
- docs: 新增 atomic-ticket 任務鏈核心哲學章節
- docs: 新增 PC-065 並行派發 prompt 缺 Ticket ID 格式錯誤模式
- docs: Phase 2 測試設計完成（16 個 RED 測試案例）
- docs: Phase 1 功能規格完成 + PM 誤判澄清
- docs: 增補 pm-role.md 列選項時必用 AskUserQuestion 強制條款
- docs: 升級 PM 列選項必用 AUQ 教訓為 PC-064 error-pattern
- docs: 建立 IMP-060 error-pattern + / Ticket
- docs: WRAP SKILL Widen 章節新增「偽 vs 真 Widen」對照與質疑假設步驟引導（PC-063 防護 3）
- docs: 新增 incident-response Reality Test 閘門章節（PC-063 防護 2）
- docs: 建立 PC-063 ANA 階段過早收斂於假設方案錯誤模式
- docs: 建立 ARCH-016 Hook 允許清單過度限制錯誤模式
- docs: ticket-lifecycle 認領階段新增強制簡化 WRAP 規則
- docs: 建立 PC-062 派發後焦慮性檢查錯誤模式
- docs: async-mindset 新增「派發後注意力出口」章節
- docs: Memory 升級鏈歷史債務清理（5 個 memory 升級至框架）
- docs: Memory 升級鏈 skill 與 hook 落地
- docs: 新增 quality-baseline 規則 7 + PC-061 memory 升級盲點
- docs: 清理 references + methodologies 專案 ticket ID 引用
- docs: 勾選 acceptance + 補 references 遺漏檔案
- docs: 清理 skills/ 與 best-practices/ 專案 ticket ID 引用
- docs: 清理 hooks/ Python docstring/註解 ticket ID 引用
- docs: 清理 error-patterns/ 專案 ticket ID 引用
- docs: 清理 references/ 與 methodologies/ 專案 ticket ID 引用
- docs: 清理 pm-rules 8 檔案專案 ticket ID 引用（Group C+D+B 補漏）
- docs: 清理 pm-rules 8 檔案專案 ticket ID 引用
- docs: 部分清理 rules/core/ 和 pm-rules/ 專案 ticket ID 引用
- docs: 落地 Option E 框架規則 .claude/ 變更不在 worktree 進行
- docs: ARCH-015 subagent .claude/ 寫入保護 + 整併後續 ticket
- docs: 釐清 subagent .claude/ 寫入限制 + 框架規則 ticket
- docs: 新增 PC-060 meta-tool-discovery-blindness error pattern
- docs: 抽象 ToolSearch 為通用 tool-discovery 規則
- docs: search-tools-guide 新增 CC Meta-Tools 章節
- docs: 新增規則 8 + DOC-010 — 框架文件禁引用專案識別符
- docs: 新增代理人派發決策表（解決 worktree 隔離阻塞）
- docs: 移除今日 3 commit 新增的專案 ticket ID 引用
- docs: 新增 pm-agent-observability.md 整合四工具分工
- docs: pm-role.md 加入 TaskOutput Step 0.5 + PC-050 修訂
- docs: retry5 — permissionMode 受 subagent cwd 限制教訓
- docs: retry4 修訂 — acceptEdits 範圍限制 + bypassPermissions 為 worktree 場景標準值
- docs: PC-059 根因修訂 + 批次修復 Ticket
- docs: 建立 /010 與 PC-057，擴充 PC-050 模式 D
- docs: 完成 — 象限分類整合到 AskUserQuestion 場景
- docs: PC-056 parallel-evaluation 強勢視角結論需 WRAP 驗證
- docs: 結案 — 建立摩擦力管理方法論
- docs: 新增驗證類任務自動派發規則（）
- docs: 新增 Hook 開發 JSON schema 檢查清單（IMP-055 防護）
- docs: IMP-055 新增半結構化 JSON 失敗變體（bac38ac4 再發）
- docs: 記錄 PC-055 Ticket AC 與實況漂移未被系統偵測
- docs: IMP-059 auto-compaction UTF-8 截斷導致文件亂碼
- docs: PC-054 分析視角錨定防禦性而非品質目標
- docs: tool call 預算閾值校準 ��� 15 次為安全預算非硬斷（.3）
- docs: 補充子任務 vs 獨立 Ticket 決策流程圖和案例（.2）
- docs: 新增 task-splitting 策略 8 — 按依賴鏈序列拆分（.1）
- docs: IMP-058 YAML 欄位型別假設錯誤（）
- docs: 新增規則 6 — 框架修改優先於專案進度（）
- docs: IMP-057 grep 多行 print 語句誤報模式
- docs: 完成 + IMP-056 chpwd shell hook 錯誤模式
- docs: PC-053 錯誤模式 + 補建 Ticket + 品質清單新增 Ticket 追蹤檢查
- docs: 新增影響範圍驗證機制 — 防止修改不完整/判斷不全面
- docs: 決策樹系統整合 WRAP 強制觸發路由（ANA/Debug/提案/事件回應）
- docs: WRAP 觸發條件擴大 — ANA/Debug/提案類 Ticket 強制使用 WRAP 分析
- docs: pm-role.md 失敗判斷前置步驟新增 Step -1 hook-logs 檢查（）
- docs: 新增 IMP-055 錯誤模式 + / Ticket 完成記錄
- docs: WRAP 決策落地 — AC 凍結機制 + complete 前 error-pattern 檢查
- docs: 新增「完成後發現」決策路由（3.5-B 層）— WRAP 教訓
- docs: 新增 IMP-053 + PC-052 錯誤模式 — WRAP 修正教訓
- docs: 認領時 Context 驗證檢查清單 — 新增 3 項前提驗證機制
- docs: 方案 D 收尾 — 遷移 到 -（測試重寫版本）
- docs: WRAP Skill 三項改善 — 快速模式重設計/雙錨點/Hook 設計（~007）
- docs: 建立 WRAP 決策框架 Skill — 認知偏誤防護和選項擴增工具（）
- docs: PC-051 過早宣稱做不到 + 完成記錄
- docs: 代理人狀態追蹤 SOP 整合到決策樹系統
- docs: PC-050 PM 代理人完成誤判錯誤模式 + Ticket + W11 完成狀態
- docs: IMP-049 記錄 hook error 是 Claude Code CLI 已知 bug（非 Hook 問題）
- docs: 新增 ARCH-013/014 錯誤模式 + parallel-evaluation 流程加入錯誤模式記錄步驟
- docs: 補充規則 + 版本日期 + 引用驗證通過
- docs: .4 文件微調 — 空章節移除、跨專案引用清理、優先級表分離
- docs: ~006 批量完成（已在 修復）+ 遷移至
- docs: AGENT_PRELOAD 新增 Ticket 進度更新規範
- docs: pm-role 新增工作階段切換 SOP
- docs: Controller 拆分從 遷移至
- docs: IMP-051/052 錯誤模式 — Hook 未註冊 + 批量遷移 None guard 遺漏
- docs: IMP-050 錯誤模式 — hook_utils 是 Package 路徑資訊不準確
- docs: IMP-049 錯誤模式 — Hook 常數未定義靜默失敗
- docs: DOC-009 錯誤模式 — 「靜默處理」用語誤用
- docs: 修正「靜默退出」用語為「正常退出（已記錄到日誌）」
- docs: 修正 Hook 錯誤處理決策樹用語 — 消除「靜默處理」誤導
- docs: Hook 開發規範更新 — 禁止直接 json.load(sys.stdin)
- docs: IMP-048 Hook stderr 觸發 hook error 顯示錯誤模式
- docs: Agent 失敗標準除錯 SOP
- docs: PC-043 PM 跳過階段轉換 + PC-044 拆分命名結構化
- docs: 認領階段 5W1H 補全 + 執行階段即時日誌要求 (.1)
- docs: 認知負擔評估框架重構 — DDD domain 邊界 + 檔案體量維度 (, PC-042)
- docs: ANA 結論轉化從存在性升級為完整性檢查 (, PC-041)
- docs: PC-042 規則文件過長 + 分析 Ticket
- docs: PC-041 錯誤模式 + 改善 Ticket
- docs: PC-040 錯誤模式 + 流程改善 Ticket
- docs: 文件即知識原則用 OCP 重新定義
- docs: PROC-001 — 擴展為「所有角色依照文件做事」通用原則
- docs: PROC-001 錯誤模式 — 錯誤假設 PM 具備人類學習能力
- docs: 建立 Context Bundle Phase Guide — 各 Phase 特定欄位指引
- docs: Context Bundle 產出契約定義
- docs: 派發指南統一指向 Context Bundle
- docs: tdd-flow + decision-tree 整合 Context Bundle
- docs: 建立 Context Bundle 規範
- docs: 建立 Claude Code 平台限制參考文件
- docs: PC-039 錯誤模式 — Worktree 未合併導致代理人產出不可見
- docs: PC-020 錯誤模式 — 修復方向應在生產端而非消費端
- docs: ~010 流程修復完成 — Worktree SOP + Resume 5W1H + Phase 3b 派發指南
- docs: 記錄 3 個錯誤模式 + 建立 3 個修復/分析 Ticket
- docs: W1 — 4 Ticket 完成（26 failed → 2 failed）
- docs: handoff — 發布完成，規劃下一版本
- docs: TDD 案例「來源」改為「背景」故事格式，自包含來龍去脈
- docs: 案例「發現位置」改為自包含描述，移除 Ticket 引用依賴
- docs: TDD 粒度規則 P2 修復 — SOLID/行為單元關係、案例格式、Phase 4 粒度提醒
- docs: TDD 任務粒度規則 — Use Case 驅動拆分 + 多視角審查修復
- docs: 新增 PC-037 error pattern — 背景代理人完成前過早驗證產出物
- docs: /003/004 完成 — 4 個 DQ 案例新增 + 流程追蹤修正 + 測試驗證
- docs: 完成 — 三視角遺漏掃描，建立 4 個 W5 修復 Ticket
- docs: TDD SKILL 案例體系完善 — 新增 6 個案例覆蓋 DQ 缺口
- docs: W4 收尾 — TDD SKILL 案例索引補充 + worktree 調查結論
- docs: worktree 調查 + TDD 結構清理完成
- docs: .2 完成 — Phase 2 rules.md 新增案例索引 + Ticket 狀態更新
- docs: TDD Phase 1/2 references 目錄重構（.1 + .2）
- docs: TDD Phase 3/4 references 目錄重構（.3）
- docs: 新增 TDD Phase 1.5 規格多視角審查 + 3 個修正 Ticket
- docs: roadmap 重整 — PROP-007 tag-based model 提前至 v0.17，建立水平式 TDD Ticket 結構
- docs: 整合 Chrome Extension 實戰知識庫到 thyme-extension-engineer（）
- docs: 修正 thyme-extension-engineer 描述移除錯誤的 Flutter 限制說明（）
- docs: 合併 project-init 和 ticket SKILL.md 重複的執行方式章節（）
- docs: 統一所有 Skill SKILL.md 加入 Version + Last Updated 尾部標記（）
- docs: legacy-code-workflow 步驟 3/6 加入明確的 /ticket create 和 /doc-flow 引用（）
- docs: project-init 加入後續流程銜接說明（）
- docs: ticket complete 流程加入 proposals-tracking.yaml 同步提示（）
- docs: 重構 version-release SKILL.md 偽程式碼移至 references/（）
- docs: 建立跨 Skill 引用格式規範（）
- docs: 統一主工作日誌命名為 v{VERSION}-main.md（）
- docs: 修正 legacy-code-workflow 步驟數描述矛盾（）
- docs: 提取三系統同步原則為共用 reference（）
- docs: 新增 doc-flow 三方分工速查表（）
- docs: 記錄 PC-035 版本 status 與 ticket 狀態不一致錯誤模式
- docs: 消除 legacy-code-workflow worklog 初始化重複描述（）
- docs: 完成 W3 流程更新 — worklog 前置步驟 + Roadmap 步驟 6 + 變更流程
- docs: 補建 ~ 主工作日誌 + 更新 Hook 路徑
- chore: sync-pull after round-trip verification
- chore: pull .claude framework updates
- chore: add executable bit to acceptance checker hook (auto-fix)
- chore: summarize file-size-guardian SessionStart output
- chore: externalize power asymmetry rules to lazy-load
- chore: complete as obsolete - premise voided by PC-066 multi-perspective review
- chore: 修復 set-* dict 欄位壓扁 bug + regression fixture 8/8
- chore: 補充 ticket-lifecycle 雙向檢查規則 + acceptance-auditor 檢查職責
- chore: 擴充 atomic-ticket-methodology 拆分檔案配對章節
- chore: add exec bit to 3 test files (IMP-054 auto-fix)
- chore: 新建 TD-F Ticket + 附帶他人 hook/.1.3.1 變更 (Session 收尾)
- chore: 附帶他人 dispatch_stats permission + .1.3 hook 自動更新 (PC-019 派發前置)
- chore: Phase 3a 完成 + v2.3 Q5/Q6 + 52 RED 測試 + 附帶他人變更
- chore: 落地 charset-guard-hook 雙通道輸出（方案 C）
- chore: v2.2 Q1-Q4 規格補充 + Phase 3a 派發前置 + 附帶他人 ticket 索引
- chore: Phase 1 v2 設計 + Phase 2 RED 測試（45 cases）
- chore: Phase 1 v1 + 多視角審查衍生 /PC-096/097
- chore: complete DOC - PC-095 WRAP-W 選項池結構性偏見 error-pattern
- chore: ticket completion metadata + session 權限累積
- chore: 清理 meta-metrics 殘留 + 擴充 portability-check 覆蓋
- chore: 多視角評估後快修 + 追蹤 3 ticket
- chore: 固化 ticket frontmatter YAML 格式規則到集中參考文件 + 代理人引用
- chore: test_ana_spawned_checker.py 權限 0644→0755
- chore: pre-dispatch commit — 同步其他 session 的框架與 ticket 變更
- chore: pre-dispatch commit — 同步其他 session 框架改善變更
- chore: test_wrap_decision_tripwire_hook.py 加執行權限
- chore: 前 session housekeeping — chmod 修正 + 補 案例 + ANA 建立
- chore: 強化 加 source-of-truth 約束（Hook 不可硬編碼觸發條件）
- chore: 修正 test_agent_dispatch_validation_hook.py 執行權限
- chore: Hook 檔案補齊執行權限
- chore: 修正 test_gitignore_main_thread_edit.py 檔案執行權限
- chore: memory-upgrade-reminder-hook 加上執行權限
- chore: 加入 context7 MCP 工具至 allow 清單
- chore: 設定 hook_output_validator.py 為可執行
- chore: 註冊 commit-before-dispatch Hook + worklog 更新
- chore: sync .claude 配置更新（ — CHANGELOG/Hook/決策樹/提案流程）
- chore: 遷移審查延後 Ticket 到 （, ）
- chore: 遷移 ticket resume 流程修復從 v0.19 到 （ → ）
- chore: sync-pull .claude 配置更新（58 檔案，+1293/-419）
- test: RED tests for whitelist filter rules A-D
- test: align TestDetectKeywordConflicts with Dict contract
- test: AC 漂移回歸測試（PROP-010 / PC-055 防護驗證）
- test: 擴充 acceptance_gate_hook 測試覆蓋至 15 項
- test: RED — 跨版本 blockedBy 依賴檢查
- perf: dispatch_tracker _read_state 加入 mtime 驅動記憶體快取

---

## [1.17.0] - 2026-04-01

### Summary
feat: ticket complete 自動追加 worklog 進度行（）; feat: 整合 Legacy Code 評估到 TDD 流程和決策樹（）; feat: 修復 UC-01 整合測試 Mock 配置，確認核心功能正常 (+23 more)

Changes: 3 feat, 3 refactor, 6 fix, 14 docs

- feat: ticket complete 自動追加 worklog 進度行（）
- feat: 整合 Legacy Code 評估到 TDD 流程和決策樹（）
- feat: 修復 UC-01 整合測試 Mock 配置，確認核心功能正常
- refactor: 更新 ticket 系統和文件支援階層式 work-logs 結構
- refactor: 移除 project-init FLUTTER.md 引用改用 CLAUDE.md 技術選型
- refactor: 消除 FLUTTER.md，統一專案設定與代理人知識分離
- fix: 移除 sage-test-architect 中 parsley 硬編碼引用（/ARCH-012）
- fix: 撤回 sage 硬編碼 parsley 引用，改為通用 CLAUDE.md 引導
- fix: 修復 ticket-id-validator 版本誤報 + parallel-eval 加入語言代理人（, , ）
- fix: 修復 hook_ticket.py 不支援三層 work-logs 目錄結構
- fix: 遷移 22 個 Hook + 2 個 Skill + 3 個同步腳本的 Python shebang 至 uv script 模式
- fix: 修復 UC-04 Widget 層前 3 個測試檔案 (data_diff_preview, search_candidate_list, search_dialog)
- docs: 擴充 legacy-code-workflow 步驟 5 可觀測性設計指引（）
- docs: 新增 rules/core/observability-rules.md 可觀測性通用規則（）
- docs: 新增 Legacy Code 測試重建方法論（）
- docs: 新增 ARCH-012 錯誤模式 - 通用代理人禁止專案特定引用
- docs: sage 代理人新增引用 parsley Widget 測試知識的規則（）
- docs: 更新 CLAUDE.md 和 parsley 知識庫反映四視角審查結論（）
- docs: 從 教訓新增 Widget 測試常見陷阱指引
- docs: 修正 legacy-code-workflow 步驟 4 策略 — UC 整合測試優先於全量測試
- docs: 補強 legacy-code-workflow 流程記錄機制 — 新增回溯盤點和逐 UC 即時記錄要求
- docs: 重寫 worklog 為敘事性事件日誌風格
- docs: 修正 worklog/ticket 追蹤機制缺失
- docs: 更新 rules/README/agent-collaboration 反映專案設定與代理人知識分離
- docs: 建立版本發布前標準化檢討流程
- docs: 實作 Worklog 即時進度同步規範 (.1)

---

## [1.16.0] - 2026-03-31

### Summary
feat: 新增 Legacy Code 評估報告機制 — 解決跨 session 進度遺失問題; docs: 修正評估報告模板和實際報告的審查發現; docs: 記錄 PC-034 錯誤模式 — 流程產出物無持久化導致跨 session 進度遺失 (+3 more)

Changes: 1 feat, 4 docs, 1 chore

- feat: 新增 Legacy Code 評估報告機制 — 解決跨 session 進度遺失問題
- docs: 修正評估報告模板和實際報告的審查發現
- docs: 記錄 PC-034 錯誤模式 — 流程產出物無持久化導致跨 session 進度遺失
- docs: 完成 workflow 平台遷移 — 步驟 0/4/5 改為語言無關
- docs: 重寫 legacy-code-workflow 步驟 2 並完成三視角審查修正
- chore: sync-pull 從 tarrragon/claude.git 拉取最新 .claude 配置

---

## [1.15.0] - 2026-03-30

### Summary
refactor: 精簡 legacy code 接手流程（多視角審查修復 4 項）; docs: 新增 Legacy Code 接手處理標準化七步驟流程（）

Changes: 1 refactor, 1 docs

- refactor: 精簡 legacy code 接手流程（多視角審查修復 4 項）
- docs: 新增 Legacy Code 接手處理標準化七步驟流程（）

---

## [1.14.0] - 2026-03-30

### Summary
feat: doc CLI 新增 create/update 子命令（建立文件+狀態更新+tracking 同步）; fix: 新增 Bash 規則三 — 禁止串接多個 git 寫入操作（index.lock 競爭防護）; docs: 更新 /doc SKILL.md — 觸發詞+CLI 狀態+關係圖+評估路徑

Changes: 1 feat, 1 fix, 1 docs

- feat: doc CLI 新增 create/update 子命令（建立文件+狀態更新+tracking 同步）
- fix: 新增 Bash 規則三 — 禁止串接多個 git 寫入操作（index.lock 競爭防護）
- docs: 更新 /doc SKILL.md — 觸發詞+CLI 狀態+關係圖+評估路徑

---

## [1.13.0] - 2026-03-30

### Summary
feat: worktree create 自動合併 blockedBy 依賴分支; feat: 實作 doc CLI 全部 6 個子命令（query/list/status/nav/domain/test-map）; feat: 建立 doc_system Python 套件骨架（CLI 入口 + frontmatter 解析 + 檔案定位） (+5 more)

Changes: 3 feat, 2 fix, 3 docs

- feat: worktree create 自動合併 blockedBy 依賴分支
- feat: 實作 doc CLI 全部 6 個子命令（query/list/status/nav/domain/test-map）
- feat: 建立 doc_system Python 套件骨架（CLI 入口 + frontmatter 解析 + 檔案定位）
- fix: /doc CLI 10 項品質修復（精確匹配+project_root+模組解耦+BOM+常數）
- fix: Hook 允許 .claude/skills/ 在 feat 分支上編輯（解決代理人 4 次被攔截問題）
- docs: 補充 SKILL.md/references 設計決策理由（防審查重複覆議）
- docs: 修正 PROP-000 frontmatter + tracking.md 欄位名稱 + 引用格式慣例
- docs: 記錄 三視角審查結果 — 4 個簡化建議均被否決（含歷史理由）

---

## [1.12.0] - 2026-03-30

### Summary
feat: 建立 /doc Skill — 需求追蹤文件系統管理; refactor: 模板移至 Skill，docs/ 只放產物; fix: 記錄 PC-010 錯誤模式 + 更新 UC 完整性探問需求 (+7 more)

Changes: 1 feat, 1 refactor, 4 fix, 4 docs

- feat: 建立 /doc Skill — 需求追蹤文件系統管理
- refactor: 模板移至 Skill，docs/ 只放產物
- fix: 記錄 PC-010 錯誤模式 + 更新 UC 完整性探問需求
- fix: 修復全部 7 個延後項目 — 無延後項目殘留
- fix: 第二輪審查修復 — PROP-000 命名、PROP-005 引用鏈、tracking verified_by
- fix: 修復多視角審查發現的 4 個高嚴重程度問題
- docs: 提案評估指南新增資安維度探問（認證/加密/稽核/機密管理）
- docs: 建立提案評估指南 — 三關式審查架構（必要性/完整性/流程）
- docs: 補充審查延後項目到文件，避免交接資訊遺失
- docs: 記錄 ARCH-011 框架資產與專案產物混放錯誤模式

---

## [1.11.0] - 2026-03-30

### Summary
feat: 新增 git index.lock 自動清理 PreToolUse hook（）; feat: 啟用跨設備同步 45/45 + 效能基準 9/9 測試通過（.7, .8）; fix: Hook git 呼叫加上 --no-optional-locks 消除 index.lock 競爭根因（） (+1 more)

Changes: 2 feat, 1 fix, 1 chore

- feat: 新增 git index.lock 自動清理 PreToolUse hook（）
- feat: 啟用跨設備同步 45/45 + 效能基準 9/9 測試通過（.7, .8）
- fix: Hook git 呼叫加上 --no-optional-locks 消除 index.lock 競爭根因（）
- chore: 同步 .claude 配置變更

---

## [1.10.0] - 2026-03-29

### Summary
feat: SessionStart Hook 自動檢查 Skill description 長度（）; feat: PreToolUse Hook 強制實作代理人使用 worktree 隔離（）; refactor: parallel-dispatch 精簡至核心決策 （） (+11 more)

Changes: 2 feat, 2 refactor, 7 fix, 2 docs, 1 chore

- feat: SessionStart Hook 自動檢查 Skill description 長度（）
- feat: PreToolUse Hook 強制實作代理人使用 worktree 隔離（）
- refactor: parallel-dispatch 精簡至核心決策 （）
- refactor: ticket_builder 提取 _normalize_children 消除 DRY 違反（）
- fix: 框架清理 /015/016
- fix: worktree 表格同步 Hook 清單 + git commit 規則語義修正（/005）
- fix: parallel-evaluation description 縮短至 70 字 + /018 完成（/018）
- fix: ticket CLI update_parent_children 根因修復（）
- fix: 代理人 worktree 隔離規則（）
- fix: parallel-evaluation 觸發詞新增多視角審核/code review（）
- fix: ticket CLI --parent 子 Ticket 序號不遞增（）
- docs: decision-tree worktree 提醒 + Skill 創建流程文件（/020/021）
- docs: skill-design-guide 加入 description 長度限制為最重要規則（）
- chore: sync-pull .claude 框架 → 1.9.2

---

## [1.9.2] - 2026-03-29

### Summary
sync .claude configuration

---

## [1.9.1] - 2026-03-29

### Summary
fix: W4 審查修復 — symlink 防護 + clean 排除補充 + 空目錄清理

Changes: 1 fix

- fix: W4 審查修復 — symlink 防護 + clean 排除補充 + 空目錄清理

---

## [1.9.0] - 2026-03-29

### Summary
feat: sync W4 完整改善 — 6 個審查技術債全部清零

Changes: 1 feat

- feat: sync W4 完整改善 — 6 個審查技術債全部清零

---

## [1.8.1] - 2026-03-29

### Summary
fix: sync 審查最終修復 — 路徑格式/大小寫/hash 長度/.gitignore; chore: 完成 + sync-state hash 基線建立

Changes: 1 fix, 1 chore

- fix: sync 審查最終修復 — 路徑格式/大小寫/hash 長度/.gitignore
- chore: 完成 + sync-state hash 基線建立

---

## [1.8.0] - 2026-03-29

### Summary
feat: 新增 sync-claude-status 版本+內容 hash 快速比對工具

Changes: 1 feat

- feat: 新增 sync-claude-status 版本+內容 hash 快速比對工具

---

## [1.7.1] - 2026-03-29

### Summary
sync .claude configuration

---

## [1.7.0] - 2026-03-29

### Summary
refactor: sync-push VERSION 魯棒性 + 模式匹配改善

Changes: 1 refactor

- refactor: sync-push VERSION 魯棒性 + 模式匹配改善

---

## [1.6.1] - 2026-03-29

### Summary
fix: W3 審查修復 — filecmp 例外保護 + .env.* 通配符 + 密鑰格式補充

Changes: 1 fix

- fix: W3 審查修復 — filecmp 例外保護 + .env.* 通配符 + 密鑰格式補充

---

## [1.6.0] - 2026-03-29

### Summary
feat: sync 腳本 W3 改善 — 版本衝突檢測 + preserve 更新提示 + 敏感檔案保護

Changes: 1 feat

- feat: sync 腳本 W3 改善 — 版本衝突檢測 + preserve 更新提示 + 敏感檔案保護

---

## [1.5.1] - 2026-03-29

### Summary
sync .claude configuration

---

## [1.5.0] - 2026-03-29

### Summary
feat: sync 腳本改為 merge 機制，新增 sync-preserve.yaml; fix: sync-pull 審查修復 — P0 preserve 保護 + P1 解析/路徑修正

Changes: 1 feat, 1 fix

- feat: sync 腳本改為 merge 機制，新增 sync-preserve.yaml
- fix: sync-pull 審查修復 — P0 preserve 保護 + P1 解析/路徑修正

---

## [1.4.11] - 2026-03-29

### Summary
chore: sync-pull + 還原本地特化

Changes: 1 chore

- chore: sync-pull + 還原本地特化

---

## [1.4.10] - 2026-03-29

### Summary
docs: 決策樹新增效能問題發現後代理人更新規則; docs: 代理人新增效能與資源管理章節 (parsley + fennel); docs: parsley agent 新增 Widget 重建效能意識章節 (+2 more)

Changes: 4 docs, 1 chore

- docs: 決策樹新增效能問題發現後代理人更新規則
- docs: 代理人新增效能與資源管理章節 (parsley + fennel)
- docs: parsley agent 新增 Widget 重建效能意識章節
- docs: Phase 1 加入 ARCH-010 框架內建機制驗證步驟
- chore: sync-pull .claude 框架 1.4.0 → 1.4.9 + 還原本地新增檔案

---

## [1.4.9] - 2026-03-29

### Summary
fix: 重新啟用 44 個 skip 測試（191→147）; fix: 重構 parseBookElement 採用容錯策略（必要/可選欄位分離）; fix: 移除 overview-page-controller 雙環境偵測，統一使用 CJS require (+4 more)

Changes: 3 fix, 2 docs, 2 chore

- fix: 重新啟用 44 個 skip 測試（191→147）
- fix: 重構 parseBookElement 採用容錯策略（必要/可選欄位分離）
- fix: 移除 overview-page-controller 雙環境偵測，統一使用 CJS require
- docs: 建立資料流架構與已知陷阱參考文件，擴展 docs/ 白名單
- docs: 記錄 ARCH-010 模組組裝遺漏模式，建立 W4 文件和整合測試 Ticket
- chore: sync-pull + 還原本地特化（hooks 白名單/block 行為、ARCH-010）
- chore: 遷移 skip 測試任務到

---

## [1.4.8] - 2026-03-28

### Summary
docs: 規則系統架構優化 — observability 歸類 + hook-governance 合併

Changes: 1 docs

- docs: 規則系統架構優化 — observability 歸類 + hook-governance 合併

---

## [1.4.7] - 2026-03-28

### Summary
fix: 多視角審查 P1/P2 修復 7 項; docs: 新增可觀測性設計規則和品質基線要求; docs: 補充 PM 規則 7 個決策空白覆蓋方案

Changes: 1 fix, 2 docs

- fix: 多視角審查 P1/P2 修復 7 項
- docs: 新增可觀測性設計規則和品質基線要求
- docs: 補充 PM 規則 7 個決策空白覆蓋方案

---

## [1.4.6] - 2026-03-28

### Summary
docs: 新增 PC-030 錯誤模式 — Phase 4 未使用程式碼需全專案 grep 驗證; chore: 完成 小型技術債批量清理 (/006/007)

Changes: 1 docs, 1 chore

- docs: 新增 PC-030 錯誤模式 — Phase 4 未使用程式碼需全專案 grep 驗證
- chore: 完成 小型技術債批量清理 (/006/007)

---

## [1.4.5] - 2026-03-27

### Summary
docs: 記錄 PC-032 跳過版本發布流程 + PC-033 工作日誌過時阻塞發布

Changes: 1 docs

- docs: 記錄 PC-032 跳過版本發布流程 + PC-033 工作日誌過時阻塞發布

---

## [1.4.4] - 2026-03-27

### Summary
fix: 遷移 Manager Skill 到 rules/core/pm-role.md（自動載入）

Changes: 1 fix

- fix: 遷移 Manager Skill 到 rules/core/pm-role.md（自動載入）

---

## [1.4.3] - 2026-03-27

### Summary
fix: 遷移 CQ-001~006 到 .claude/error-patterns/ 並刪除 docs/error-patterns/ 舊目錄; fix: 代理人定義 slash command 引用改為 Read SKILL.md; fix: Manager Skill 精簡為角色行為準則 + PM 規則路由表 (+3 more)

Changes: 4 fix, 2 docs

- fix: 遷移 CQ-001~006 到 .claude/error-patterns/ 並刪除 docs/error-patterns/ 舊目錄
- fix: 代理人定義 slash command 引用改為 Read SKILL.md
- fix: Manager Skill 精簡為角色行為準則 + PM 規則路由表
- fix: worktree merge 子命令 — behind>0 時阻擋合併並列出 main 新 commit，通過時自動執行 git merge
- docs: 新增 PC-030/PC-031 錯誤模式 + 修正 Ticket
- docs: W7 tickets、IMP-045 錯誤學習、FileWatcher 技術選型、CLAUDE.md 重啟觀測流程

---

## [1.4.2] - 2026-03-27

### Summary
fix: pyproject_scanner 排除無 CLI entrypoint 的套件

Changes: 1 fix

- fix: pyproject_scanner 排除無 CLI entrypoint 的套件

---

## [1.4.1] - 2026-03-27

### Summary
新增 IMP-043/044 錯誤模式和 zellij skill

---

## [1.4.0] - 2026-03-27

### Summary
refactor: 統一 Logger 靜態呼叫第二參數為物件格式; fix: 時間敏感測試、 ESLint toThrow 修復、 版本同步; docs: 新增 PC-029 並行代理人共用檔案衝突

Changes: 1 refactor, 1 fix, 1 docs

- refactor: 統一 Logger 靜態呼叫第二參數為物件格式
- fix: 時間敏感測試、 ESLint toThrow 修復、 版本同步
- docs: 新增 PC-029 並行代理人共用檔案衝突

---

## [1.3.0] - 2026-03-27

### Summary
feat: 新增 __pycache__ 到 .gitignore 必須規則檢查

Changes: 1 feat

- feat: 新增 __pycache__ 到 .gitignore 必須規則檢查

---

## [1.2.2] - 2026-03-27

### Summary
fix: 將 __pycache__ 加入 .gitignore 並從 git 追蹤移除; fix: 移除 FLUTTER.md pathspec 避免非 Flutter 專案執行失敗; chore: 同步遠端更新 — sync-push 增強與版本遞增至 1.2.1 (+1 more)

Changes: 2 fix, 2 chore

- fix: 將 __pycache__ 加入 .gitignore 並從 git 追蹤移除
- fix: 移除 FLUTTER.md pathspec 避免非 Flutter 專案執行失敗
- chore: 同步遠端更新 — sync-push 增強與版本遞增至 1.2.1
- chore: 同步更新 .claude 配置至 並更新專案文件

---

## [1.2.1] - 2026-03-27

### Summary
fix: sync-push commit 訊息改用實際變更描述取代純計數統計

Changes: 1 fix

- fix: sync-push commit 訊息改用實際變更描述取代純計數統計

---

## [1.2.0] - 2026-03-27

### Summary
1 feat [minor bump suggested]

---

## [1.1.53] - 2026-03-27

### Summary
fix: 排除 handoff 暫時性交接資料夾

---

## [1.1.52] - 2026-03-27

### Summary
feat: Wave 5 重構完成 — Hook 配置更新、Ticket 文件同步

---

## [1.1.51] - 2026-03-26

### Summary
feat: 新增 Agent commit 驗證 Hook + Go build artifact 清理指引

---

## [1.1.50] - 2026-03-25

### Summary
feat(v0.1.2): Phase Contract 驗證 + Agent Registry + 檔案所有權 Hook + 82 Ticket 品質改善

---

## [1.1.49] - 2026-03-13

### Summary
release(v0.1.0): 同步 v0.1.0 版本發布配置 — 語言感知版本檢查、monorepo 警告降級

---

## [1.1.48] - 2026-03-13

### Summary
docs(0.1.0-W51-001): 標準化 complete 前主動勾選驗收條件流程

---

## [1.1.47] - 2026-03-12

### Summary
sync: W45-001 完成後同步 .claude 配置

---

## [1.1.46] - 2026-03-11

### Summary
sync: W34-W37 變更同步 — hook 重構、quality-common 分離、test_track_board 測試、error-pattern IMP-030

---

## [1.1.45] - 2026-03-10

### Summary
refactor: W28~W31 Hook DRY 重構 — hook_utils 共用函式、sentinel 統一、error-pattern 偵測修復

---

## [1.1.44] - 2026-03-09

### Summary
流程更新

---

## [1.1.43] - 2026-03-06

### Summary
docs: 新增 IMP-021 手動文字解析結構化格式錯誤模式

---

## [1.1.42] - 2026-03-06

### Summary
fix: 移除 handoff/archive/ 並加入 .gitignore

---

## [1.1.41] - 2026-03-06

### Summary
feat: 新增 CLI 失敗提醒 Hook (PC-005) + IMP-020 Hook 共存觸發碰撞模式

---

## [1.1.40] - 2026-03-06

### Summary
feat: prompt-submit-hook 否定詞過濾完整修復

---


## [1.1.39] - 2026-03-06

### Summary
fix: merge fix/prompt-submit-hook-negation - hook 否定語境誤觸發修正

---


## [1.1.38] - 2026-03-06

### Summary
fix: merge fix/prompt-submit-hook-status-syntax - 修正 hook 中的 --status 語法

---


## [1.1.37] - 2026-03-06

### Summary
fix: merge fix/ticket-list-multi-status - ticket --status 多值篩選

---


## [1.1.36] - 2026-03-06

### Summary
fix: merge fix/ticket-cross-version-warning - 跨版本任務遺漏防護

---


## [1.1.35] - 2026-03-05

### Summary
fix: sync-pull 補齊 symlink 檢查 + git 返回碼驗證

---

## [1.1.34] - 2026-03-05

### Summary
feat: sync-pull 新增遠端已刪除檔案清理機制

---

## [1.1.33] - 2026-03-05

### Summary
fix: escape sequence warning + 移除舊 .sh 腳本

---

## [1.1.32] - 2026-03-05

### Summary
refactor: 移除舊 sync .sh 腳本，統一使用 .py 版本

---

## [1.1.31] - 2026-03-05

### Summary
chore: W1-014/015/016 sync 腳本修正、project-init Python 3.14、IMP-016 error-pattern

---

## [1.1.30] - 2026-03-05

### Summary
docs: 新增 PC-003 錯誤模式 + CLI 失敗調查流程改進（decision-tree, incident-response）

---


## [1.1.29] - 2026-03-05

### Summary
docs: 新增 IMP-015 腳本自我刪除錯誤模式

---


## [1.1.28] - 2026-03-05

### Summary
fix: sync-push 移除 rsync verbose，防止 31KB 輸出溢出

---


## [1.1.27] - 2026-03-05

### Summary
fix: sync-claude-pull.sh 修復自我刪除風險、untracked 誤判、clone timeout + 同步 v1.1.26 更新

---


## [1.1.26] - 2026-03-05

### Summary
feat: 新增 incident-response 修復三階段規則 + 測試金字塔驗證順序 + PC-004 error-pattern (W1-009)

---


## [1.1.25] - 2026-03-05

### Summary
fix: 跨版本任務遺漏防護

---


## [1.1.24] - 2026-03-05

### Summary
fix: 修正 Stop hook reason 欄位被 Claude 解讀為命令導致自動執行 resume (IMP-014)

---


## [1.1.23] - 2026-03-05

### Summary
fix: 修正框架路徑偵測 - get_project_root() 支援 Go/混合型專案（CLAUDE.md/go.mod 搜尋），version.py 加入 fallback WARNING log，sync-push 排除 Python 暫存目錄

---


## [1.1.22] - 2026-03-05

### Summary
feat: 新增 Go 代理人 + i18n/常數規範 + 移除 emoji

---


## [1.1.21] - 2026-03-05

### Summary
feat: W5-006 handoff 驗收前置檢查 + W5-007 resume --list stale 過濾修復

---


## [1.1.20] - 2026-03-04

### Summary
fix: 修復 handoff GC 誤刪 bug + 新增 IMP-010 錯誤模式

---


## [1.1.19] - 2026-03-04

### Summary
feat: sync-pull 後自動重新安裝全域 CLI 套件

---


## [1.1.18] - 2026-03-04

### Summary
feat: v0.2.0 onboarding framework - onboard 子指令 + Hook 分類 + settings 模板 + 文件泛化

---


## [1.1.17] - 2026-03-03

### Summary
refactor: 簡化 sync 機制，移除 FLUTTER.md 獨立處理邏輯

---


## [1.1.16] - 2026-03-03

### Summary
fix: agent-ticket-validation-hook stderr 輸出優化 + IMP-006 案例 D

---


## [1.1.15] - 2026-03-03

### Summary
feat: 建立 Bash 工具使用規範和錯誤模式防護（IMP-008/IMP-009）

---


## [1.1.14] - 2026-03-03

### Summary
feat: sync-pull 加入 AskUserQuestion 覆蓋確認保護機制

---


## [1.1.13] - 2026-01-28

### Summary
feat(decision-tree): v3.1.0 新增規則變更同步檢查機制

---


## [1.1.12] - 2026-01-28

### Summary
feat(decision-tree): 決策樹二元化重構 v3.0.0 + Mermaid 圖表

---


## [1.1.11] - 2026-01-19

### Summary
feat(lib): 新增 Markdown 連結檢查工具並修復 27 個失效連結

---


## [1.1.10] - 2026-01-19

### Summary
feat(hooks): ticket-track complete 自動同步 todolist + wave 欄位改為可選

---


## [1.1.9] - 2026-01-14

### Summary
fix(DOC-003): 移除 CLAUDE.md 中的 Flutter 特定規範

---


## [1.1.8] - 2026-01-14

### Summary
docs(DOC-003): 新增 ViewModel 層硬編碼規範和 i18n 管理方法論

---


## [1.1.7] - 2026-01-14

### Summary
refactor(CLAUDE.md): 精簡重構 1299→388 行（-70%）

---


## [1.1.6] - 2026-01-14

### Summary
docs: 新增 PC-001 未照規格實作錯誤模式 + TM-008 dynamic 繞過

---


## [1.1.5] - 2026-01-13

### Summary
feat: output-style + sync-push 修復

---


## [1.1.4] - 2026-01-13

### Summary
sync: 加強 5W1H 格式要求，移除 TodoWrite Hook 檢查

---

## [1.1.3] - 2025-12-24

### Summary
fix: 版本號改為遠端自動遞增

---

## [1.1.2] - 2025-12-24

### Summary
feat(sync): 改進同步機制 - 保留 commit 歷史

### Added
CHANGED:- .claude/README-subtree-sync.md
---


## [1.1.1] - 2025-10-27

### Summary
fix: 修正 CHANGELOG 產生邏輯與 commit 訊息傳遞

### Added
CHANGED:- .claude/hooks/changelog-update.sh
### Removed
- .claude/work-logs/v0.13.0-pdf-cleanup-task.md
---


## [1.1.0] - 2025-10-27

### Summary
refactor: 改進 Hook 代理人分派機制與 Ticket 方法論設計

### Changed
- `.claude/methodologies/ticket-design-dispatch-methodology.md` - 新增「必要檔案」核心欄位，解決 agent 檔案定位問題
- `.claude/hooks/task-dispatch-readiness-check.py` - 改進代理人分派檢查機制，新增代理人名稱優先判定
- `.claude/hooks/agent_dispatch_analytics.py` - 增強分派檢查的準確性
- `.claude/methodologies/agile-refactor-methodology.md` - 明確 Phase 3a 簡化版格式，避免輸出超限

---


## [1.0.4] - 2025-10-19

### Summary
fix(Hook): 修正 task-dispatch-readiness-check 增加 Phase 明確標記優先判斷

### Added
CHANGED:- .claude/hooks/task-dispatch-readiness-check.py
---


## [1.0.3] - 2025-10-18

### Summary
fix(hooks): 修復 changelog-update.sh 在臨時 repo 中無法檢測變更

### Added
CHANGED:- .claude/hooks/changelog-update.sh
---


## [1.0.2] - 2025-10-18

### Summary
fix(hooks): 修復 Hook 任務分派誤判問題 - v0.12.O

### Changed
- `.claude/hooks/task-dispatch-readiness-check.py`：修復 Phase 2 任務誤判為 Phase 1
  - 新增 EXCLUDE_KEYWORDS 排除負面語境機制
  - 移除提前退出，評估所有任務類型後選最高權重
  - 測試驗證 4/4 通過，向後相容性完整保留

### Added
- `.claude/test-hook-all.py`：完整測試套件（4 個測試案例）
- `.claude/test-hook-tc001.py`：測試案例範例
- `docs/work-logs/v0.12.O-hook-improvement-task-dispatch.md`：Hook 改善設計文件

---

## [1.0.1] - 2025-10-18

### Summary
refactor(.claude): 調整 CHANGELOG 更新時機為 sync-push

### Changed
- `.claude/hooks/changelog-update.sh`：調整 CHANGELOG 更新時機

---

## [1.0.0] - 2025-10-18

### Added
- 建立版本管理系統（VERSION 檔案）
- 建立 CHANGELOG 自動化機制
- 新增 `hooks/changelog-update.sh`：自動更新 CHANGELOG 的 Pre-commit Hook
- 代理人分派檢查 Hook 系統（來自 v0.12.N）
  - `hooks/task-dispatch-readiness-check.py`：任務分派準備度檢查
  - `hooks/agent_dispatch_recovery.py`：錯誤恢復機制
  - `hooks/agent_dispatch_analytics.py`：智慧分析工具
- 完整的測試套件（93 個測試，100% 通過率）
- Hook 模式切換功能（Strict/Warning 雙模式）
- 主線程錯誤恢復使用指南和快速參考

### Changed
- 更新 `hooks/pre-commit-hook.sh`：整合 CHANGELOG 自動更新
- 更新 `scripts/sync-claude-push.sh`：同步推送 VERSION 和 CHANGELOG
- 修正 Python Hook 腳本執行權限

### Documentation
- 新增 `docs/agent-dispatch-auto-retry-guide.md`：完整使用指南
- 新增 `docs/agent-dispatch-analytics-guide.md`：分析工具指南
- 新增快速參考卡片和 CLI 工具文件

---

## 未來規劃

### [2.0.0] - 待定
- CLAUDE.md 重大架構調整（如有需要）

### [1.1.0] - 待定
- 新增更多 Hook 功能
- 新增更多方法論文件

---

**說明**：
- 本 CHANGELOG 從 v1.0.0 開始記錄
- 版本號獨立管理，不與專案版本同步
- 每次 commit .claude 相關變更時自動更新
