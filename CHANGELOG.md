## [1.45.1] - 2026-06-12

### Summary
fix: .version-release.yaml 納入 local-only 排除 + gitignore 補顯式條目; chore: 保留本地框架變更（sync-pull 前快照）

Changes: 1 fix, 1 chore

- fix: .version-release.yaml 納入 local-only 排除 + gitignore 補顯式條目
- chore: 保留本地框架變更（sync-pull 前快照）

---

## [1.45.0] - 2026-06-12

### Summary
feat: identity-guard 呼叫端傳遞 command 參數（telemetry per-command 歸因）; feat: identity-guard telemetry pass/exempt 路徑落盤; feat: dispatch hook 嵌套深度感知強制層 (+76 more)

Changes: 15 feat, 1 refactor, 30 fix, 21 docs, 11 chore, 1 test

- feat: identity-guard 呼叫端傳遞 command 參數（telemetry per-command 歸因）
- feat: identity-guard telemetry pass/exempt 路徑落盤
- feat: dispatch hook 嵌套深度感知強制層
- feat: ticket CLI 嵌套深度防護（depth 命令 + create --parent warning）
- feat: identity-guard warn/deny telemetry 落盤
- feat: ticket CLI 寫入命令 --as 身份申報與 who.current 對照（warn-only 過渡）
- feat: create Tier 2 高相似度阻擋層 + bulk-create 警告層補齊
- feat: argparse 縮寫歧義模式化治理
- feat: create 必填欄位一次列全 + --how 縮寫歧義友善提示
- feat: create UX — 必填欄位一次列全 + --how 友善提示
- feat: bash-edit-guard 加裸 cd warn 偵測
- feat: bash-rules git -C 首選 + 輸出可疑協議 + IMP-056 受眾修補
- feat: PC-166 升級唯讀 stdout 虛構 + 反污染協議規則固化
- feat: error-pattern flat 號 negative gate hook
- feat: 整合 blocker_resolution 共用 predicate 至 lifecycle/runqueue
- refactor: collision guard 內聚 get_next_seq 並覆蓋 bulk_create
- fix: basil model 行清理（移除行內註解）+ ANA 結論與驗證票
- fix: set-where 同步更新 where.files
- fix: SubagentStop 自激迴圈斷路器 + WAIT 廣播 dedup
- fix: 效能測試 pytest -m perf 標記隔離
- fix: agent-commit-verification porcelain 首行截斷與豁免繞過
- fix: append-log 派發前章節允許 pending 直寫，消除 PM bookkeeping --force 常態化
- fix: 移除 handoff-auto-resume-stop-hook Stop 事件雙重註冊（PC-148）
- fix: append-log 自動補建缺失 Schema 章節 + 前置檢核聚合
- fix: ticket create ID 分配 fcntl file lock
- fix: worktree skill dev deps 改用 PEP 735 dependency-groups 宣告
- fix: ticket-quality-gate hook tool-aware 輸入驗證分流
- fix: AGENT_PRELOAD 加 [PM-ONLY] 前綴忽略規則 + Stop 類 hook 注入訊息加前綴
- fix: emit_hook_output 加 audience 受眾過濾 + 10 gap hook 遷移統一出口
- fix: 4 個 PostToolUse hook 加入 subagent 偵測早期跳過
- fix: 修復 uv-tool-staleness hook 的 registry 佈局假設
- fix: worktree-auto-commit hook 防 race 代捕 + 訊息富化
- fix: ticket_generator 配號改經 resolve_available_seq 補 collision guard
- fix: conftest autouse 隔離 project root 防 ticket 測試 lock 污染真實 work-logs
- fix: 修復 ticket create auto-seq 衝突（三層缺陷鏈）
- fix: identity guard 僅對 str as_value 生效，修復 Mock-args 測試回歸
- fix: Stop hook 加 subagent context 偵測消除最終訊息劫持
- fix: 強健化 ana_spawn_consistency_checker 表格變體偵測
- fix: error-pattern flat-gate 數字開頭描述段繞過修復
- fix: 修復 bash-edit-guard 裸 cd 偵測五項盲區
- fix: conftest autouse fixture 隔離 hook 測試日誌至 tmp_path
- fix: decision-tree 全缺併入 checklist 一次列全（A2 同手法）
- fix: checklist 驗證補空字串 why/how_strategy 漏判
- fix: 建票路徑 checklist 執法一致性（batch-create/generate 補 warning）
- fix: 收窄裸 cd guard 絕對路徑排除為僅 repo-root 還原
- fix: basil Layer 2 修正（規則3補Consequence + PC-166移除inline ticket ID）
- docs: footer 同號條目歸位標註 + PRELOAD 禁用詞摘要顯性說明（basil P2 殘項）
- docs: 收尾 --as 全覆蓋與建票 who 對齊 SOP（PRELOAD + dispatch-template ）
- docs: PC-V1-002 補入執行 agent 違抗決策權保留約束案例變體
- docs: hook 開發受眾評估 checklist 規則（PC-V1-004 防護 B）
- docs: PC-143 追加案例 3 — ANA 規劃 dated model ID 拼接錯誤
- docs: 卸載零使用 bundled plugins + 防復裝清單
- docs: agent-dispatch-template 新增嵌套派發派發端指引章節
- docs: parallel-dispatch.md 新增嵌套派發整合條款
- docs: 新增 PC-V1-003 聯想式參照個案修補消音 error-pattern
- docs: 升級 PC-069 批量腳本衛生規範
- docs: AGENT_PRELOAD 新增規則 9 嵌套派發資訊協議
- docs: Phase 4 兩視角回填 + 兩處註解一致性立即修正
- docs: PRELOAD 2.4 雙判準 — who.current 機械對照為主判準
- docs: 探針派發防護落地 — 唯讀探針 SOP + 引用非指派邊界 + PC-V1-002
- docs: ghost branch 宿主機制補證收斂 — 同進程同 turn 雙執行流
- docs: confabulation 規則檔群交叉引用與版本標記稽核
- docs: SKILL.md 標註頂層命令 vs track 子命令層級慣例
- docs: 固化「單點執法、多入口繞過」反模式（/043/029 學習）
- docs: tool-output-trust 新增規則 5 記錄/世界平面二相性
- docs: PC-166 跨境用語修正（並發→並行/導出→匯出/批量→批次）
- docs: PC-166 整合 ghost branch 鑑識判據（防護 D 延伸）
- chore: 收編前 session 遺留的測試檔 exec bit 變更（644→755）
- chore: 清理 23 個 agent 檔 model 行行內註解
- chore: spawn 3 IMP children + worktree egg-info 隨 pyproject 再生成
- chore: ticket bookkeeping — metadata sync + /070 結案 + .1 spawn + set-where 補欄
- chore: 補上 2 個 hook 測試檔執行權限（HookCheck 自動 chmod +x, IMP-054）
- chore: 補 commit hook 測試檔執行權限修正（HookCheck IMP-054 自動 chmod）
- chore: ANA 完成 — PC-V1-004 落地 + 三張防護 spawn ticket
- chore: fallbackModel 設定 + 16 agent opus 改 inherit 統一
- chore: 跨 session 同日二度撞號案例追加 + 防護排程
- chore: CC 2.1.164-2.1.172 release impact review 評估落地
- chore: 測試檔執行權限修正（HookCheck IMP-054 自動 chmod +x）
- test: 清理 create 驗證測試債（--force why 豁免覆蓋 + 死 errno 收斂）

---

## [1.44.6] - 2026-06-09

### Summary
docs(PC-V1-001): sync-push 無 --help 未知參數觸發真實推送 near-miss（首個來源前綴格式 error-pattern，編號體系上線）

---

## [1.44.5] - 2026-06-09

### Summary
error-pattern 來源前綴編號體系：新規方法論 + 專案代號註冊表 + PC-ID regex 拓寬 + allocator/negative-gate + V1 flat base A+B+D remediation + 跨專案 detect 腳本（補正 v1.44.4 commit 訊息）

---

## [1.44.4] - 2026-06-09

### Summary
--help

---

## [1.44.3] - 2026-06-09

### Summary
fix: .gitignore generic **/hook-logs/ 根治巢狀涵蓋缺口

Changes: 1 fix

- fix: .gitignore generic **/hook-logs/ 根治巢狀涵蓋缺口

---

## [1.44.2] - 2026-06-09

### Summary
fix: 修復 ticket skill 4 個既有測試失敗; fix: conftest autouse fixture 隔離 HOOK_LOGS_DIR 杜絕巢狀 hook-logs 污染; fix: sync exec-bit 還原涵蓋 settings.json 註冊的 skill 根目錄執行檔 (+2 more)

Changes: 4 fix, 1 chore

- fix: 修復 ticket skill 4 個既有測試失敗
- fix: conftest autouse fixture 隔離 HOOK_LOGS_DIR 杜絕巢狀 hook-logs 污染
- fix: sync exec-bit 還原涵蓋 settings.json 註冊的 skill 根目錄執行檔
- fix: 修復 evaluate-session.py exec bit + 建 ticket 追蹤 sync 邊界遺漏
- chore: pull .claude 框架改進（PC-180 + sync-push SOP + PC-162 延伸）

---

## [1.44.1] - 2026-06-08

### Summary
chore: round-trip 驗證收尾 + SOP/PC-162 DOC + spawn; other: 新增 PC-180：雙專案 sync 混淆共享納入與本地保留範圍; other: 採納跨專案 ticket 系統共用 predicate 與 worklog 冪等測試

Changes: 1 chore, 2 other

- chore: round-trip 驗證收尾 + SOP/PC-162 DOC + spawn
- other: 新增 PC-180：雙專案 sync 混淆共享納入與本地保留範圍
- other: 採納跨專案 ticket 系統共用 predicate 與 worklog 冪等測試

---

## [1.44.0] - 2026-06-08

### Summary
feat: 新增未 commit ticket md 偵測 hook（ 方案 4）; feat: auto-commit index.lock retry（sleep 1s 重試一次）; fix: execution_log_checker 偵測 ANA 重現實驗結果空殼 (+1 more)

Changes: 2 feat, 1 fix, 1 test

- feat: 新增未 commit ticket md 偵測 hook（ 方案 4）
- feat: auto-commit index.lock retry（sleep 1s 重試一次）
- fix: execution_log_checker 偵測 ANA 重現實驗結果空殼
- test: 添加 uncommitted-ticket-md-reminder-hook 測試套件

---

## [1.43.0] - 2026-06-08

### Summary
feat: dispatch hook 新增 stale-origin 警示（非阻擋）; fix: 修復 test_scenario_1_invalid_section fixture 設計缺陷; fix: 修復 ticket-skill 測試基礎設施 G1+G2+G3 (+10 more)

Changes: 1 feat, 5 fix, 5 docs, 2 chore

- feat: dispatch hook 新增 stale-origin 警示（非阻擋）
- fix: 修復 test_scenario_1_invalid_section fixture 設計缺陷
- fix: 修復 ticket-skill 測試基礎設施 G1+G2+G3
- fix: cascade 解鎖擴展至 blocker→dependents
- fix: runqueue 動態解析 blocker 完成狀態（修正 B）
- fix: 解耦 dispatch-validation hook 測試對已移除 ticket md 的依賴
- docs: 新增 PC-179 worktree agent 完成後 cwd 污染致 merge 誤判
- docs: 補強 bash 規則二有界列舉禁截斷 carve-out + 新建 PC-177
- docs: 派發 SOP 加入 push-before-dispatch + agent-writes-to-ticket
- docs: PC-148 擴充變體 B（hook 搬移後 settings.local.json 殘留舊路徑）
- docs: 新增 PC-178 UI 功能測試綠但 runtime 不可達
- chore: 移除 632 MagicMock 測試污染 + scoped gitignore（G3 repo-hygiene）
- chore: 授予 suggest-compact.py 執行權限（用戶請求）

---

## [1.42.0] - 2026-06-05

### Summary
feat: 7 過載代理人 model sonnet→inherit（sonnet 1m 訂閱停用）; chore: sync-pull 同步框架配置（base 138bf04e，27 delta 無衝突）

Changes: 1 feat, 1 chore

- feat: 7 過載代理人 model sonnet→inherit（sonnet 1m 訂閱停用）
- chore: sync-pull 同步框架配置（base 138bf04e，27 delta 無衝突）

---

## [1.41.0] - 2026-06-05

### Summary
feat: SubagentStop hook 改用 additionalContext + 版本相容 fallback; feat: command-entrance-gate-hook 引導式互動 + 描述性前綴/merge 誤判修補; fix: 移除過時 Flutter-monorepo 測試解除 collection error (+11 more)

Changes: 2 feat, 2 fix, 8 docs, 2 chore

- feat: SubagentStop hook 改用 additionalContext + 版本相容 fallback
- feat: command-entrance-gate-hook 引導式互動 + 描述性前綴/merge 誤判修補
- fix: 移除過時 Flutter-monorepo 測試解除 collection error
- fix: version-release release 收尾完整性（CHANGELOG finalize + todolist 自動 completed）
- docs: 新增 PC-176 + 補強 PC-172（codegraph 跨電腦乒乓兩個錯誤學習）
- docs: src 字串輸出變更 acceptance 必含測試套件規則
- docs: ANA 全量 grep/regex 範圍驗證完整性規範
- docs: 新增 IMP-079 批次替換工具誤傷偵測目標字面 error-pattern
- docs: 新增 PC-175 框架跨 sync 攜帶來源專案類型專屬資產
- docs: search-tools-guide 速查表版本無關化，杜絕 MCP 工具名漂移
- docs: PC-174 根因段補顯式 Consequence
- docs: 新增 PC-174 命令閘門誤判描述性陳述 + 硬阻擋應改引導式
- chore: #9 PC-157 $TMPDIR workaround 驗證 + 版本註記
- chore: CC 2.1.162/2.1.163 release 影響評估 ANA

---

## [1.40.1] - 2026-06-04

### Summary
fix: 統一 settings template serena MCP 權限前綴; docs: 新增 PC-173 框架 MCP 工具名與實機暴露漂移; docs: 修正 project-init/search-tools-guide MCP 工具名漂移 (+3 more)

Changes: 1 fix, 3 docs, 2 chore

- fix: 統一 settings template serena MCP 權限前綴
- docs: 新增 PC-173 框架 MCP 工具名與實機暴露漂移
- docs: 修正 project-init/search-tools-guide MCP 工具名漂移
- docs: 新增 PC-172 wrapper command 參數推斷未經 runtime 驗證
- chore: 對齊 .gitignore handoff 規則與 sync manifest GITIGNORE_EXPECTED
- chore: 修正 sync_exclude_manifest.py + test 檔執行權限為 755

---

## [1.40.0] - 2026-06-03

### Summary
feat: session-start hook gitignore↔manifest 交叉驗證; feat: sync-pull import-time PC 編號撞號偵測與自動重編號; feat: push git-archive 改造（C1+K）取代磁碟 copy_filtered (+11 more)

Changes: 5 feat, 1 refactor, 5 fix, 3 docs

- feat: session-start hook gitignore↔manifest 交叉驗證
- feat: sync-pull import-time PC 編號撞號偵測與自動重編號
- feat: push git-archive 改造（C1+K）取代磁碟 copy_filtered
- feat: pull 三方合併改造（A3+L+M）取代全量 overlay
- feat: sync-state 加單一 last_synced_base_sha + status 顯示
- refactor: 建 sync 排除分類 SSOT manifest，根治 push/status 漂移
- fix: pull robustness — preserve fail-loud (H) + 備份排除工具產物 (Q)
- fix: exec-bit 還原遞迴覆蓋 skills/*/hooks/（缺陷 G）
- fix: push clean-check 改 should_exclude 過濾 porcelain + .gitignore 補齊漂移項
- fix: push 機密洩漏防護 abort gitignored/untracked .claude 檔
- fix: 修復 track list priority 排序 datetime.date vs str 混型 TypeError
- docs: D2 PC 編號區段 policy + sync README base snapshot 更新
- docs: 修正 README-subtree-sync.md 與程式碼對齊三處矛盾
- docs: 新增 PC-171（上游 PC-165 重編號避免本地撞號）

---

## [1.39.2] - 2026-06-03

### Summary
chore: 更新 sync-state（sync-push bookkeeping）

Changes: 1 chore

- chore: 更新 sync-state（sync-push bookkeeping）

---

## [1.39.1] - 2026-06-03

### Summary
fix: app shell 新增資料管理導航入口; chore: sync-pull .claude framework 更新（claude.git）; chore: 移除誤入的 worktree gitlink

Changes: 1 fix, 2 chore

- fix: app shell 新增資料管理導航入口
- chore: sync-pull .claude framework 更新（claude.git）
- chore: 移除誤入的 worktree gitlink

---

## [1.39.0] - 2026-06-03

### Summary
feat: vendoring impeccable 設計 skill 至框架（納入 sync）; feat: config 化 version-release CLI 硬編碼假設支援 all-on-main; feat: 新增 parallel-claim-audit-hook 記錄 claim 時同 wave 快照（非阻擋） (+16 more)

Changes: 4 feat, 13 docs, 2 chore

- feat: vendoring impeccable 設計 skill 至框架（納入 sync）
- feat: config 化 version-release CLI 硬編碼假設支援 all-on-main
- feat: 新增 parallel-claim-audit-hook 記錄 claim 時同 wave 快照（非阻擋）
- feat: 新增 cc-release-impact-review skill
- docs: ARCH-015 整合四測矩陣 + 選項 3 決策落地
- docs: ARCH-015 實測回填 — CC 2.1.161 #15 解鎖 worktree 內 .claude/ 編輯
- docs: CC 2.1.161 框架影響評估 + 三衍生落地
- docs: 標註 CC 2.1.161 #18 修復（subagent 卡 running 已消解）
- docs: 更新 ARCH-015 標註 CC 2.1.161 #15 修復資訊（worktree 背景編輯解鎖）
- docs: 第三方 CC skill vendoring 四陷阱（process-compliance）
- docs: 文件化 subagent claim 推薦用法（半成功 root cause 已治本，不需 code fix）
- docs: Layer 2 修正 — 三明示補全與正向錨點前置
- docs: SOP 化 cc runtime worktree base 過舊處理流程
- docs: 釐清 frontmatter exempt marker 不一致（ 已消解）
- docs: 收尾 workflow 評估（不引入）+ MCP env 補記
- docs: AUQ 規則新增維度 A 前置關卡（對齊 CC ）
- docs: 落地 框架調整（worktree 清理 SOP + PC-059 釐清 + OTEL 補記）
- chore: 提交遺留 mode 變更 test_parallel_claim_audit_hook.py (644->755)
- chore: 推進 last-reviewed 至 2.1.160

---

## [1.38.1] - 2026-06-01

### Summary
fix: 修復 command-entrance-gate-hook 三層誤判（組合 F）; fix: migrate 反向引用更新保留被引用 ticket body

Changes: 2 fix

- fix: 修復 command-entrance-gate-hook 三層誤判（組合 F）
- fix: migrate 反向引用更新保留被引用 ticket body

---

## [1.38.0] - 2026-06-01

### Summary
feat: 移除 --skip-verify flag + 拆 ticket track verify 子命令; feat: 擴 VALID_SECTIONS 加 Task Summary + Completion Info; feat: Phase 3 GREEN hook 訊息中性化 + Phase 4 評估 (+23 more)

Changes: 6 feat, 2 refactor, 2 fix, 14 docs, 2 test

- feat: 移除 --skip-verify flag + 拆 ticket track verify 子命令
- feat: 擴 VALID_SECTIONS 加 Task Summary + Completion Info
- feat: Phase 3 GREEN hook 訊息中性化 + Phase 4 評估
- feat: dashboard 醒目標記 trigger-bound ticket
- feat: saffron + agent-definition-standard 跨 ticket 物件操作禁令
- feat: standalone --skip-verify 加 deprecation warning + AC2/AC3/AC4 評估
- refactor: 移除 light evaluation_level enum ( 結論落地)
- refactor: IMP-078 認知負擔重構（363→251 行 / 10→7 H2 / API SSOT 整併）
- fix: post-test-hook 綠燈字面誤判修復
- fix: worktree skill project_root 推導改用雙策略 fallback
- docs: PC-166 補「情境因子 vs 根因」區分章節
- docs: record merge interruption + --no-verify empty merge commit pattern (.3 incident)
- docs: 建立 PC-168 flaky baseline lucky streak + quality-baseline 規則 1 邊界並列引用
- docs: 建立 W4 session SOP 驗證 case study 並固化 8 case source data
- docs: 新增「分析代理人 worktree 內無 commit ticket body」error pattern
- docs: 補追 stale ticket cleanup 案例 + SOP
- docs: Phase 4 評估結論 + load_top_ready docstring 小修
- docs: 升級 PC-077 為 behavior-loop-details 派發決策矩陣
- docs: Layer 2 審查修正 proposal-evaluation-gate.md
- docs: IMP-075/076/077 補抽象層級分析章節
- docs: IMP-078 + PC-165 並列關係雙向修訂（3 項）
- docs: IMP-078 hot-fix（Rule 8 marker + bundle crypto + global.gc + no-restricted-imports）
- docs: 新建 IMP-078 CE-Node 環境前提誤判 error-pattern
- docs: PC-166 新增防護 D 區分 confabulation vs 異地真實執行
- test: Phase 2 RED 新增 hook 訊息中性化測試
- test: Phase 2 RED + spawn

---

## [1.37.0] - 2026-05-29

### Summary
feat: 新增 uv-tool ownership-guard hook 防跨專案全域工具污染; fix: phase4-hook 跳過 Context Bundle auto-extracted 區塊; fix: --acceptance 分隔符支援反斜線跳脫 + 拆條警告 (+10 more)

Changes: 1 feat, 5 fix, 6 docs, 1 chore

- feat: 新增 uv-tool ownership-guard hook 防跨專案全域工具污染
- fix: phase4-hook 跳過 Context Bundle auto-extracted 區塊
- fix: --acceptance 分隔符支援反斜線跳脫 + 拆條警告
- fix: 修復 no_bare_status allowlist 行號漂移並去耦合
- fix: 修復 error_channel + hook_health 兩 pre-existing 測試失敗
- fix: release 依 blockedBy 決定目標狀態（空回 pending 非一律 blocked）
- docs: 套用 basil Layer 2 審查修正 PC-166
- docs: 記錄 PM confabulation 事件並建立 PC-166 防護
- docs: 套用 basil Layer 2 審查 Warning 修正
- docs: PC-142 新增 case 5 frontmatter 引用 + 防護同步 修復
- docs: 新增規則六「長背景任務可觀測性」至 bash-tool-usage-rules
- docs: 移除 basil-hook-architect.md 殘留 ticket ID 引用（規則 8 清理）
- chore: 固化 uv-tool ownership-guard hook 執行權限位

---

## [1.36.1] - 2026-05-29

### Summary
chore: chmod +x test_session_start_gitignore_check_hook.py

Changes: 1 chore

- chore: chmod +x test_session_start_gitignore_check_hook.py

---

## [1.36.0] - 2026-05-28

### Summary
feat: session-start gitignore 必要 entry 檢查 hook; feat: sync-pull 自動清理超期 backup_dir; chore: untrack PM_INTERVENTION_REQUIRED runtime state

Changes: 2 feat, 1 chore

- feat: session-start gitignore 必要 entry 檢查 hook
- feat: sync-pull 自動清理超期 backup_dir
- chore: untrack PM_INTERVENTION_REQUIRED runtime state

---

## [1.35.3] - 2026-05-28

### Summary
fix: sync-push 無變更時 early-exit 避免空 commit

Changes: 1 fix

- fix: sync-push 無變更時 early-exit 避免空 commit

---

## [1.35.2] - 2026-05-28

### Summary
sync .claude configuration

---

## [1.35.1] - 2026-05-28

### Summary
fix: phase4-hook frontmatter YAML 區塊跳過 (PC-142 case 5); fix: 強化 project-init OUTDATED 警示顯眼度; fix: 修正 mcp_detector.py codegraph binary 名稱 (+5 more)

Changes: 3 fix, 5 docs

- fix: phase4-hook frontmatter YAML 區塊跳過 (PC-142 case 5)
- fix: 強化 project-init OUTDATED 警示顯眼度
- fix: 修正 mcp_detector.py codegraph binary 名稱
- docs: ticket-lifecycle.md 三明示文字微調
- docs: SKILL.md dashboard-first 落地（補前 session 遺留 commit）
- docs: 新建 PC-164 MCP binary 名稱同源誤判 anti-pattern
- docs: PC-163 Layer 2 補強 — 表格後橋接 + 防護三層適用條件
- docs: 新建 PC-163 PM-worktree ticket md 偏離 error-pattern

---

## [1.35.0] - 2026-05-27

### Summary
feat: 升級 skill-cli-error-feedback-hook 加入系統功能缺失分類; feat: 並行受控實驗 + PC-137/ARCH-015 規則升級; feat: 建立 pm-rules/ticket-handoff-archaeology.md（接手考古 SOP） (+78 more)

Changes: 19 feat, 4 refactor, 6 fix, 37 docs, 10 chore, 5 test

- feat: 升級 skill-cli-error-feedback-hook 加入系統功能缺失分類
- feat: 並行受控實驗 + PC-137/ARCH-015 規則升級
- feat: 建立 pm-rules/ticket-handoff-archaeology.md（接手考古 SOP）
- feat: 新增 install-guide-edit-reminder-hook (PC-159 Hook 層)
- feat: 升級至 hook-system-methodology § 6 觀察類工具雙重身份設計
- feat: SessionStart source diagnostic hook 用於 bg session resume 觀察
- feat: 為 3 hook 啟用 continueOnBlock（4 處註冊）
- feat: handoff gc 新增 --force 清理 task-chain handoff
- feat: resume 擴充 target_ticket_id 反向查找
- feat: inline pyproject_scanner API 消除 CLI sys.path hack
- feat: claim 預設不執行 AC verification + complete 並行安全分析
- feat: cbm + codegraph MCP detector 整合 project-init check
- feat: S6 wire complete status precondition (B11/B13/B15 green)
- feat: S5 wire set-acceptance status precondition (B6-B10 + E2 green)
- feat: S3 wire append-log status precondition (B1-B5 + E1 green)
- feat: S1 add require_in_progress helper (status precondition)
- feat: append-log CLI 自動降級 H2 → H3（ 方案 B 落地）
- feat: ticket create ID 掃描改用 main ref 聯集（B3 GREEN）
- feat: 建立 test-assertion-design skill
- refactor: charset guard find_violations 重構為 CATEGORY_MAP 統一 lookup
- refactor: 刪除 handoff hook dead code get_active_version
- refactor: 部分拆分 handoff-auto-resume-stop-hook 抽出 session 管理模組
- refactor: has_background_agents 提升出 scan 迴圈為一次性 bool
- fix: 清理 衍生：substring 比對 + cache 殘留 + sync-preserve 過時 + schema PC 引用
- fix: post-test-hook 加 ticket body 寫入豁免
- fix: 移除 SKILL.md 3 個 ✓ emoji 違反規則 3
- fix: 修復 install + runtime path 兩個 framework bug
- fix: 修正 .mcp.json --load-extension 路徑（採方案 B）
- fix: 縮窄 post-test-hook ANALYZER_WARNING_PATTERNS 避免誤報 jest console.warn
- docs: basil Layer 2 補審查回應 - 補三明示 Consequence/Action + 表格 OR 說明
- docs: ticket-body-schema.md IMP 安裝指令 acceptance 條件補強 (PC-159 三層防護收尾)
- docs: Layer 2 補修 basil 審查 2W+2I 回饋
- docs: 升級 worktree-operations 與 parallel-dispatch 為策略 C
- docs: parallel-dispatch.md 新增 bgIsolation:none 並行安全警告
- docs: worktree-operations.md 新增 bgIsolation 策略選擇章節
- docs: 錯誤學習雙通道 + 衍生 追蹤建立
- docs: 對齊 CC plugin 管理機制
- docs: 新增 /goal × acceptance 邊界章節
- docs: PC-092 v2 案例補強（/ 並行 commit）+ PM 自評
- docs: 鏡像 memory 升級四問檢查至 auto-load + pm-role 路由補強
- docs: ANA 驗收修正 + PC-161 固化 + .1 closed
- docs: PC-160 PM 跳過升級評估閘門直接寫 memory 處理 session 浮現洞察
- docs: .2 實機驗證落地 + SessionStart source 對照表
- docs: footer 描述移除具體 ticket ID 純粹符合 PC-083
- docs: session-switching-sop 補充 /resume bg session 場景
- docs: 新增 claude agents --json 速查附錄段落
- docs: 整併 acceptance 反模式表 DRY + Why 欄 + Action 步驟
- docs: Layer 2 修正反模式範例英文混入
- docs: 遷移既有 acceptance 「npm test 100%」為 complete-time 語義 + 文件規範完善
- docs: Layer 2 微調收尾責任段落
- docs: 補強 mint-format-specialist 收尾責任段落
- docs: PC-074 補升級備註指向 language-constraints 規則 5
- docs: language-constraints 新增規則 5 字元集子集動態驗證
- docs: 文件落地三 MCP 路由與 cbm 限制（方案 B 改良）
- docs: 建立 PC-159 安裝指令未在 fresh shell 驗證
- docs: 新增 PC-158 — mint-format-specialist 視覺標記場景 emoji 違規
- docs: 新增三 MCP 設計對照表與三刀流工作流決策樹至 search-tools-guide skill
- docs: 新增 IMP-077 測試 helper 設計反模式
- docs: 新增 IMP-076 skill packaging install/runtime 二態盲點（ 衍生）
- docs: 新增 PC-157 + IMP-075（.2 衍生）
- docs: language-constraints 規則 3 補規格文件 emoji 豁免條款
- docs: 修正 PC-115 既有 6 處「數據」→「資料」 + Session 總結 worklog
- docs: Layer 2 basil 審查修補 + PC-115 deadlock 變體章節 + spawn
- docs: PM cwd auto-switch 到 agent worktree 錯誤模式記錄
- docs: 新增 PC-155 auto-stage × worktree 並行編輯同檔造成 merge conflict
- docs: 落地 worktree 派發防護方案 A1+B1
- chore: gitignore 擴大 hook-logs 覆蓋嵌套 skill 目錄 + 接受 IMP-054 auto exec bit
- chore: allow ZIP install verification commands (.2 leftover)
- chore: 補 test_post_test_hook.py exec bit
- chore: spawn ticket 落地 + dispatch plan 註記
- chore: 正規化版本發布時的權限需求變更檢查
- chore: 固化 worktree 派發失敗為 PC-154 error-pattern
- chore: 補提交 .2 第二次中斷紀錄 + 修正 handoff gitignore
- chore: 收斂 test-assertion 設計檔為 skill stub
- chore: compositional-writing 多輪審查第 2 輪修正 + complete
- chore: 套用第 1 輪審查 F1-F7 修正到 test-assertion-design skill
- test: test_mcp_detector 9 情境覆蓋 success/missing/index
- test: S7 add precondition × file_lock safety tests (D1-D2)
- test: S4 add force-usage logging tests (C1-C4 complete)
- test: S2 add conftest precondition fixtures
- test: TDD Phase 1-2 — B3 ID 掃描 main ref 功能設計 + RED 測試

---

## [1.34.0] - 2026-05-21

### Summary
feat: stop-worklog-handoff-sync-check-hook 整合 background_tasks 降級誤報; feat: handoff-auto-resume hook 整合 background_tasks 取代 started_at 推斷; feat: pm-role.md caveat 區塊信號判讀規則 + PC-153 新建 (+88 more)

Changes: 29 feat, 3 refactor, 16 fix, 29 docs, 8 chore, 6 test

- feat: stop-worklog-handoff-sync-check-hook 整合 background_tasks 降級誤報
- feat: handoff-auto-resume hook 整合 background_tasks 取代 started_at 推斷
- feat: pm-role.md caveat 區塊信號判讀規則 + PC-153 新建
- feat: 遷移 worktree skill 專用 hook (7 個) 至 .claude/skills/worktree/hooks/
- feat: 遷移 wrap-decision-tripwire-hook 至 .claude/skills/wrap-decision/hooks/
- feat: 遷移 ticket skill 專用 hook (20 個) 至 .claude/skills/ticket/hooks/
- feat: uv-tool-staleness-check-hook 偵測 7 skill source vs installed 漂移
- feat: branch-status-reminder 列全量 + PC-076 防護落地
- feat: 實作 ticket track hook-health CLI 子命令
- feat: 擴充 hook-health-monitor 加觸發頻率掃描與 session marker
- feat: hook_health 核心引擎（scan/classify/evaluate/marker）
- feat: ticket migrate collision detection (dry-run warn + default reject + --force-overwrite)
- feat: ticket complete 自動 git add metadata + 提示 commit 指令（方案 D）
- feat: PC-093 exempt 白名單納入 history 類別
- feat: commands/ 下 4 檔批量加 file_lock 保護
- feat: lifecycle.py 4 處 load→save 加 file_lock
- feat: file_lock 包圍 extract_and_write_context_bundle load→modify→save
- feat: fcntl Windows conditional import + explicit NotImplementedError fallback
- feat: Phase 3 GREEN — 注入 _file_lock 於 update_* 消除 logical race
- feat: worktree merge reminder cleanup + SessionStart audit (PC-149)
- feat: enhance git-index-lock-cleanup hook with GUI app detection hint
- feat: add ticket track dispatch-readiness CLI (pending review)
- feat: complete dispatch-validate CLI (linux+basil reviewed)
- feat: add ticket track dispatch-validate CLI (Context Bundle sanity check)
- feat: add CLI append-log H2 content warning
- feat: add PreCommit homoglyph guard hook (PC-150 protection)
- feat: phase4-decision-enforcement-hook fenced code block 豁免
- feat: ticket track parallel-check 子命令偵測子任務衝突
- feat: sync-claude-push 改善 revert commit 分類與淨效應摘要
- refactor: 抽 lib/file_lock.py + _append_unique_to_list_field helper
- refactor: improve dispatch-readiness code quality
- refactor: improve dispatch-validate code quality
- fix: ticket track append-log 替換 Schema 章節 placeholder
- fix: 修正 pm-role.md + PC-153 共 13 處「信號→訊號」跨海峽用語
- fix: get_tickets_dir 移除存在性檢查，v1+ 主版本三層化
- fix: _ABSOLUTE_CLAUDE_PATTERN 加 lookbehind 防雙層 .claude/ 多重匹配誤判
- fix: 修 test_track_batch 3 個 stale exit code 期望（1→2）+ PC-151 basil 修訂
- fix: 修 test_track_acceptance 4 個 stale exit code 期望（1→2）
- fix: 擴充 phase-completion-gate-hook 主檔 regex 涵蓋 -main/-work-log suffix
- fix: dedupe ticket frontmatter I/O in handoff stop hook
- fix: align ticket CLI exit codes to three-value contract
- fix: correct dispatch-active.json path in checkpoint_state
- fix: worktree skill path/import mismatch
- fix: runqueue --context=resume 優先讀 target_ticket_id
- fix: 移除 settings.local.json PreToolUse:Agent 重複註冊
- fix: 修復 mint 形似字混淆「汲染」→「汙染」3 處
- fix: validator _is_placeholder 對非表格描述性 N/A 字面豁免（PC-138/PC-144 家族延伸）
- fix: agent-dispatch-validation-hook 補 pyyaml dep 修 ModuleNotFoundError
- docs: hook-architect-technical-reference 補 + -143 缺口
- docs: 追加 案例（acceptance 列表中文描述 inline N/A）
- docs: PC-068 擴充 ANA 階段案例
- docs: migrate-command.md 加入「前置檢查（強制）」章節
- docs: sync migrate-command.md with --force-overwrite flag and collision detection behavior
- docs: 落地 PC-152 ticket migrate 撞既有目標 ID 靜默覆寫
- docs: 同步 ticket complete --no-stage flag 至 SKILL.md / ticket-lifecycle.md
- docs: 新增 stale test exit code 期望飄移錯誤模式
- docs: Phase 4 評估完成 — 三視角共識無阻擋性重構，4 項延後追蹤建 spawned tickets
- docs: 啟用 Claude Code worktree.bgIsolation:none 設定
- docs: neutralize ticket ID references in single-source-io rules
- docs: add single-source I/O collection rules SSOT
- docs: neutralize ticket ID references in cli-exit-code-rules
- docs: add CLI exit code layering spec + complete parent ticket
- docs: add 3b dispatch-readiness check section to task-splitting.md
- docs: fix language-constraints violation in track-command.md
- docs: 修正 basil Layer 2 審查發現（H3 層級說明 + 場景辨識訊號）
- docs: 新增 PM 預寫策略放 Context Bundle 三條款規範
- docs: add normalize whitelist and grep verification to mint agent
- docs: merged worktree no post-complete cleanup + fix
- docs: IMP-074 + ticket H2→H3 schema fix
- docs: askuserquestion-rules 新增規則 7 多子任務必含平行派發選項
- docs: 新增 IMP-073 Logger 方法解構導致 this 遺失 + promise hang error-pattern
- docs: PC-148 Layer 2 修正 + complete
- docs: 建立 PC-148 hook 雙重註冊 error-pattern
- docs: 修正 compositional-writing Layer 2 C 段 5 類風格建議
- docs: 補 fixture ImportError 靜默 fallback 註解
- docs: 新增 2 原則卡 + 3-reviewer 33 issue 修正
- docs: 追加案例 #2 agent-dispatch-validation-hook 漏 sync
- chore: chmod +x 6 個 hook lib/tests 檔案
- chore: 修正 hook tests 執行權限（IMP-054 自動套用）
- chore: sync pre-existing W17 ticket metadata and worklog updates
- chore: commit orphaned complete metadata + settings allow Skill(error-pattern)
- chore: 完成 ticket（status=completed）
- chore: complete ANA ticket pair + spawn 4 children
- chore: 收尾 /041 ticket md 與 effort test 檔 exec mode 修正
- chore: l10n-sync-verification-hook 加 continueOnBlock:true
- test: handoff-auto-resume hook main stdin 整合測試 4 路徑
- test: 補實作檔案（fork mode assert）
- test: Phase 2 RED v2 — 模擬 update_* race 確認真紅
- test: Phase 2 RED 7 測試實作 全紅 baseline
- test: Phase 2 RED 測試 — worktree merge reminder + SessionStart audit
- test: 新增 conftest autouse fixture mock track_snapshot 檔案系統掃描

---

## [1.33.0] - 2026-05-14

### Summary
feat: 6 個中頻 strict-validator hook 加 effort 感知; feat: 類別 A 剩餘 6 hook 加 effort 感知; feat: hook 系統 effort 感知（類別 A 高頻 4 hook） (+9 more)

Changes: 4 feat, 4 refactor, 2 fix, 1 docs, 1 chore

- feat: 6 個中頻 strict-validator hook 加 effort 感知
- feat: 類別 A 剩餘 6 hook 加 effort 感知
- feat: hook 系統 effort 感知（類別 A 高頻 4 hook）
- feat: dispatch-active GC + TTL 降為 1h
- refactor: 補齊 _update_ticket_id_references 六欄位 + 收斂 monkeypatch + 降低 local import
- refactor: test_migrate_reverse_refs.py Phase 4 三項共識重構
- refactor: process-skip-guard-hook 三項細節改善
- refactor: 統一 hook active ticket 解析機制
- fix: 修復 create.py child_info/new_ticket where 字串格式防護
- fix: ticket create 對 parent ticket 字串格式 where/who 防護
- docs: 固化「事實判斷必擋 + effort 解耦」設計鐵則為 hook 設計指引
- chore: 遷移 settings.json hook command 至 args 陣列形式

---

## [1.32.0] - 2026-05-14

### Summary
feat: 派發前假設驗證機制 Phase A 落地; feat: cognitive-load.md 新增監測校準框架章節 + 結案; feat: proposal-evaluation-gate hook 新增 status=draft 豁免 + 規則 light 收斂純語意 (+48 more)

Changes: 9 feat, 5 refactor, 11 fix, 23 docs, 3 chore

- feat: 派發前假設驗證機制 Phase A 落地
- feat: cognitive-load.md 新增監測校準框架章節 + 結案
- feat: proposal-evaluation-gate hook 新增 status=draft 豁免 + 規則 light 收斂純語意
- feat: ticket complete 加入 pending children blocking + --force 豁免
- feat: Phase 3b 實作完成 — ticket track list --top 10 + --all
- feat: 新增 ticket track dashboard 聚合視圖（Phase 3b）
- feat: 新增 ticket track td-status 子命令（PC-094 TD 清單校準）
- feat: 審查模式關鍵字豁免 worktree 強制
- feat: build staleness check SessionStart hook
- refactor: process-skip-guard main emit 點收斂
- refactor: Phase A 精準裁剪，總 token 減 ~5.5K
- refactor: is_stale_in_progress 改為 compute_stale_minutes 薄包裝（DRY）
- refactor: 遷移泛化 3 個 .claude/ 違反規則 8 檔案
- refactor: error_pattern_attribution 6 項低優整理
- fix: phase-completion-gate 三層 guard 過濾 ticket md 文本引用誤判
- fix: sync ALLOWED_FILTER_SITES resume.py 193 to 195
- fix: 對齊 VALID_SECTIONS 與 ticket-body-schema.md 補入「重現實驗結果」
- fix: phase4-hook 跳過 Schema placeholder 區塊內 PC-093-exempt 範例字串
- fix: phase4-hook 拒絕訊息加白名單清單 + inline 提示
- fix: self_check_visibility_checker 改前綴匹配支援 H3 補充說明
- fix: ticket-quality-gate-hook type-aware 觸發 + 移除 Flutter 硬編碼
- fix: _is_placeholder 表格情境豁免 + acceptance_auditor consolidate (PC-138 / PC-144 治本)
- fix: 泛化 thyme-extension-engineer 與 oregano-data-miner 移除產品名稱與書城列舉
- fix: phase4-hook 新增 [ref] 行豁免修復 Context Bundle 誤判
- fix: phase4-hook 新增 rule-quote 豁免類別（PC-093 治本）
- docs: 規則文件收斂 //PC-146 修復對應
- docs: 新增 PC-146 PC-093 exempt marker 位置誤用
- docs: 新增 PC-145 Stale CLI install 偽裝 validator bug
- docs: priority normalization 介面評估結論採方案 C（維持 + cross-ref）
- docs: 新增 PC-144 validator TODO/TBD 字面誤判 placeholder
- docs: 跨模組 _ private import 評估結論採方案 B（rule of three 未達）
- docs: cognitive-load.md 補三明示缺口（Layer 2 follow-up）
- docs: Layer 2 修正 claude-code-tools-reference.md
- docs: 補 initialPrompt/memory 節三明示（二次審查修正）
- docs: 補充代理人 frontmatter 撰寫指南（8 新欄位 + 升級建議清單）
- docs: 新增 Claude Code 進階工具參考索引
- docs: 補 reference-stability-rules.md 規則 8 豁免機制章節
- docs: ANA 評估 7 個 .claude/ 規則 8 違反 + B 類 5 檔加豁免註解 + spawn /
- docs: 補 ticket SKILL.md dashboard + list 預設行為文件
- docs: 補入案例 4 ( complete) + 跨 session 重現警示
- docs: 補 /080 遷移成果記錄與路徑修正
- docs: 新增 PC-143 lavender Phase 1 spec 對既有 CLI 行為假設未驗證
- docs: 新增 PC-142 phase4-hook 字面抓觸發詞誤判規則引用
- docs: 新增 PC-141 監測類 ANA acceptance 未預先區分訊號類型
- docs: 新增 PC-140 + IMP-072 記錄本 session 兩個 framework bug
- docs: 補 SKILL.md td-status 同步 + ticket completed 收尾
- docs: Layer 2 修正（P2 違規）
- docs: 同步 td-status 子命令到決策層文件
- chore: test_ticket_quality_gate_type_aware.py +x 權限修正
- chore: 補 漏帶的 chmod +x
- chore: 補齊 test_build_staleness_check_hook 測試檔執行權限

---

## [1.31.0] - 2026-05-12

### Summary
feat: 新增 chrome-extension-mcp-debug SKILL; feat: 新增 ticket track stale-list 子命令列舉 stale ticket 明細; feat: framework-rule-edit hook 補 edit metrics log (+134 more)

Changes: 35 feat, 5 refactor, 25 fix, 59 docs, 13 chore

- feat: 新增 chrome-extension-mcp-debug SKILL
- feat: 新增 ticket track stale-list 子命令列舉 stale ticket 明細
- feat: framework-rule-edit hook 補 edit metrics log
- feat: humanize PC-093 hook invalid exempt marker output
- feat: hook-completeness-check 支援雙層 hook 架構掃描
- feat: wrap-tripwire context-aware blacklist filter (.1.1.2)
- feat: wrap-tripwire pytest 環境豁免 (.1.1.1)
- feat: 建立 .claude/hooks/pyproject.toml + CLAUDE.md §5
- feat: PC-115 重啟調查收斂 + 並行派發 ≤ 2 防護落地
- feat: PC-115 trigger 計數機制設計落地
- feat: 擴充 ana_spawn_consistency_checker 支援 heading-based spawn 偵測
- feat: auq-option-pattern-detector 新增 §3.4-bis 表格選項偵測 + E6 豁免
- feat: handoff --next CLI 與 target_ticket_id 欄位（L2-A）
- feat: SessionStart 提示語改寫 + Stop hook terminal 過濾
- feat: 實作 ana_spawn_consistency_checker + acceptance-gate-hook Step 2.5.2 整合
- feat: basil-writing-critic Layer 3 升級加入 zhtw-mcp 機械層審查
- feat: 新增 acceptance-gate-hook Layer 1 自檢可觀測性 checker
- feat: hook 註冊 + SOP/SKILL.md 引用 + follow-up
- feat: 實作 handoff --from-worklog CLI + Stop hook 雙軌同步偵測
- feat: S1 lib/worklog_parser.py + 12 RED tests 全綠
- feat: branch-verify-hook 跨專案豁免清單退化 + deny 切換指令
- feat: main-thread hook 跨專案編輯放行
- feat: wrap-tripwire hook S2 log 補 matched_keyword/prompt_excerpt
- feat: 建立 Hook 降級觀察期方法論與快速恢復機制
- feat: ANA 5/5 + Method 6 落地（hook log 反推 12 簡體字）
- feat: ANA 5/5 完成 + detector self-test 第五層落地
- feat: codepoint-aware 污染偵測工具落地，實證 推論
- feat: acceptance-gate 純文件 IMP 訊息差異化
- feat: 新增 wrap-skill-yaml-consistency-hook + 雙向映射檔
- feat: 整合 zhtw-mcp 跨專案可用性檢查（hook + sync 排除）
- feat: proposal-evaluation-gate PreToolUse Hook 落地
- feat: PROP 模板新增 Reality Test 必填章節
- feat: 實作兄弟 blockedBy 4 條件違規偵測 Hook
- feat: 新增 cognitive-load.md 3b 派發前閾值章節
- feat: hook-completeness-check 自動 commit chmod 修正
- refactor: hook is_ticket_completed delegate 至 lib SSOT
- refactor: branch-verify-hook 改用 git_utils.find_target_repo
- refactor: 降級 Phase 3b P3 五 Hook（worklog-format / utf8-integrity / language-guard / comment-qa / file-type-permission）
- refactor: 降級 Phase 3b P1 三 Hook（parallel-dispatch / bash-edit-guard / acceptance-gate）
- refactor: zhtw-mcp hook 探測機制改為 file-based 三層 scope
- fix: commit-msg-layer2-marker-check-hook 補 uv-run shebang + pep723 pyyaml dep
- fix: 移除 TestK_DocSync test_k2/k3 對齊 / 解耦
- fix: 4 檔測試 assert 對齊（Group 4+5+6+7 共 11 failures）
- fix: stop hook 測試對齊現行 API（Group 2+3 共 18 failures）
- fix: test_ticket_tracker.py 廢棄 CSV tracker 整檔 skip
- fix: test_analytics.py stale module reference 整檔 skip
- fix: tech-debt-reminder 改用 hook_utils.parse_ticket_frontmatter
- fix: 5 hook 改用 hook_utils helper 支援 ticket 雙結構
- fix: 三 handoff hook silent fallback 改 noisy（PC-135 防護落地）
- fix: 補 pyyaml dep 修 .1 regression
- fix: lib handoff_utils SSOT delegate find_ticket_file 修子進程環境 stale GC
- fix: handoff-prompt-reminder 路徑解析改用 find_ticket_file 支援三層階層
- fix: 修復 stop-worklog-handoff-sync-check-hook 三根因
- fix: handoff 機制 L1 三項同步修復（GC delegate + 移除 to-source + terminal 防護）
- fix: stop-worklog-handoff-sync-check-hook 加 _extract_handoff_section helper（SOT-mirror）修 false positive
- fix: 修復 agent-commit-verification-hook SubagentStop schema 違反
- fix: 修復 subagent-stop-dispatch-cleanup-hook SubagentStop event schema 違反
- fix: stop-worklog-handoff-sync-check-hook 改用 top-level systemMessage
- fix: runqueue --context=resume 解析 direction 取出 target
- fix: handoff stop hook 計數前 stale 過濾 + 剛建豁免窗口
- fix: phase-completion-gate-hook 排除 ticket md 與 worklog 主檔
- fix: ticket-quality-gate keyword 縮緊 + 路徑黑名單
- fix: hook stdin field naming camelCase → snake_case
- fix: layer-boundary-validator + doc-sync-check 補 pyyaml uv script 依賴
- fix: 縮窄 detect_task_type explicit phase 掃描至第一行
- docs: 補修整檔 emoji 違規（language-constraints 規則 3）
- docs: 套用 Layer 2 審查修正——SKILL Workflow C 三明示與分類完整性
- docs: MCP E2E 驗證 checklist 落地 readmoo.md + SKILL 書庫類範例
- docs: 建立 docs/bookstores/ 書城測試目標 reference 架構
- docs: 套用 Layer 2 P2 修正——SKILL 三明示與結構一致性
- docs: Layer 2 補修 §3 三明示 (Why/Consequence/Action)
- docs: framework-asset-separation §3 Skill Hook 雙層架構規範
- docs: 執行 方案 D 混合策略遷移
- docs: 建立 PC-139 index.lock GUI app fork 為衝突來源 error-pattern
- docs: ARCH-020 Layer 2 P1 修正
- docs: ARCH-020 補測試檔 script header 反模式變體條款
- docs: 修正 PC-138/IMP-071 Layer 2 P1 違規
- docs: 新增 TEST-007 archived 模組測試處理 idiom
- docs: 新增 PC-138 + IMP-071 ( 雙通道記錄)
- docs: ANA complete + spawn / (yaml deps gap)
- docs: 清理 hook-downgrade-observation.md 22 處 W10-* 引用
- docs: 清理 hook-downgrade-observation.md 8 處 / ticket ID 引用
- docs: cognitive-load.md §3b 章節 ticket ID 引用抽象化
- docs: hook-downgrade-observation 加入兩類機制定義與 Extended 觀察數據
- docs: 新增 PC-137 並行派發 .claude/ Edit deny 反模式
- docs: ANA retrospective complete + PC-136 落地 + W17 ticket 鏈收尾
- docs: 落地 PC-136 規則層三層升級（quality-common §1.2.6 + ANA 方法論 callees + 派發模板）
- docs: PC-135 子代理人 pytest 通過 vs hook 子進程環境失準
- docs: 升級 handoff 純指針設計原則至框架方法論層
- docs: 落地 AUQ S1-S6 訊號 + 三明示自檢 checklist
- docs: sync handoff --next / target_ticket_id to SKILL references
- docs: 改寫 ticket_system 4 處「待恢復任務」對齊 L2-B 設計
- docs: 建立 PC-134 ANA-self-reference-irony error-pattern
- docs: 三份規則文件同步修訂——ANA Solution spawn 規劃落地強制條款
- docs: 新增 PM ANA 驗收 checklist 三明示問題（Solution spawn 一致性）
- docs: bay-quality-auditor 審計 Phase 3b Hook 削減比 57.8% vs 預估 85% 差距 27.2 ppt + spawn
- docs: PC-133 代理人對同性質任務接受/拒絕不一致
- docs: Layer 2 P1+P2 修正 + trigger 計數機制 spawn
- docs: PC-115 真根因收斂為候選 1 transient runtime（4 子實驗閉環）
- docs: cognitive-load.md 跨進程同步修復豁免條款落地（ ANA 收斂）
- docs: 整合 hindsight + multi-pass 顆粒度
- docs: 案例 2 三明示形式對稱化（Layer 2 P2 建議落地）
- docs: 擴充案例 2 — PM append-log 違反
- docs: 外部佐證落地 + Anthropic Issue 監測 tracker
- docs: 新增 — Hook self-check 警示是被忽視的反推資料源
- docs: 新增 — 外部工具權威性預設質疑
- docs: 新增「動態驗證取代靜態維護」根本性解法章節
- docs: 撰寫 PC-130 規範性文字 dogfooding 違規 error-pattern
- docs: 新增 ARCH-022 hook 用 CLI 探測產生跨界隱性副作用
- docs: 釐清 ANA 路線方法論補強
- docs: 新建 IMP-070 error-pattern hook stdin 欄位命名混淆
- docs: 新增 uv script transitive 依賴未宣告 — `lib/` 共用模組引入 yaml 不自動安裝
- docs: 新增 規則存在但 agent 行為層未遵守 — agent-definition-standard 規範與實際輸出落差
- docs: P2 雙 hook 改善 — checklist 補強 + deny 訊息現況驗證
- docs: WRAP_SKILL_TRIGGER 訊息 Layer 2 殘留違規精緻化
- docs: agent-dispatch-template Layer 2 剩餘違規批次修正
- docs: AGENT_PRELOAD 規則 7 新增程式碼大檔讀取子節
- docs: 解決 ARCH-010 編號衝突，重編號 module-assembly-omission 為 ARCH-021
- docs: SKILL 外部依賴追蹤規則降級執行
- docs: 補 #11 前置條件三明示完整化
- docs: 新增 /clear 前 main 未提交變更強制檢查規則
- docs: sync compositional-writing and wrap-decision
- docs: 套用 compositional-writing 改寫 parallel-evaluation 5 檔
- docs: 擴充 decision-trigger-binding 涵蓋將來/以後 + worklog 排程原則
- chore: 建立父+5子 ticket 收斂 Chrome Extension MCP 實機驗證後續
- chore: 補齊 6 個 hook 檔案執行權限（IMP-054）
- chore: 累積 handoff archive 清理權限（.4 stale handoff JSON）
- chore: 累積本機 Bash 權限（worklog/handoff/git lock cleanup）
- chore: 補上測試檔執行權限 (IMP-054)
- chore: session 2+3 base rate 完成 — 6/6 Edit success, deny 0%
- chore: session 1 base rate 數據點 — 2/2 Edit success
- chore: ticket complete + tests exec bit 補齊
- chore: 同步 hook 自動產出 — .4 結案 ticket md + main worklog 條目 + pyyaml 評估報告刷新
- chore: 拆分 11 PROP 子 ticket — 5 standard + 6 heavy
- chore: ticket complete + hook 設可執行
- chore: hook-completeness-check 自動修正 exec bit (IMP-054)
- chore: auto-fix executable permissions for hook files (IMP-054)

---

## [1.30.0] - 2026-05-04

### Summary
feat: commit-msg Layer 2 marker check hook 補事後維度防護; feat: framework-rule-edit-skill-trigger-hook + lifecycle.py 改用 framework_paths SSOT; feat: 擴增 claim WRAP 三問新增 S 問（framework 路徑提示） (+8 more)

Changes: 3 feat, 2 refactor, 4 docs, 2 chore

- feat: commit-msg Layer 2 marker check hook 補事後維度防護
- feat: framework-rule-edit-skill-trigger-hook + lifecycle.py 改用 framework_paths SSOT
- feat: 擴增 claim WRAP 三問新增 S 問（framework 路徑提示）
- refactor: framework-paths SSOT 拆 strict/broad + lifecycle.py S 問改用 broad
- refactor: 抽出 framework-paths.yaml SSOT + lib/framework_paths.py 共用模組
- docs: 設計 Layer 1 自檢 prompt 模板
- docs: agent-dispatch-template 新增 PM 自做 framework 規則編輯流程章節
- docs: Layer 2 審查後微調規則 6 為機會成本語氣
- docs: 新增 ai-communication-rules 規則 6 估時禁令條款
- chore: 補正 hook 檔案執行權限為 755
- chore: Layer 2 by basil-writing-critic — 吸納 3 P2 修正

---

## [1.29.0] - 2026-05-03

### Summary
feat: 規則 6.1 框架 ticket 版本歸屬補強 + PC-121; feat: runqueue stale in_progress 標註; feat: runqueue readiness 標註 (+52 more)

Changes: 24 feat, 3 refactor, 8 fix, 15 docs, 2 chore, 3 test

- feat: 規則 6.1 框架 ticket 版本歸屬補強 + PC-121
- feat: runqueue stale in_progress 標註
- feat: runqueue readiness 標註
- feat: handoff 寫入 exit_status 欄位
- feat: runqueue --context=resume 讀 handoff exit_status 並標 tag
- feat: handoff --auto 整合 Context Bundle 抽取器
- feat: session-start NeedsContext 警示摘要（盲區 E）
- feat: worktree-zombie-cleanup-hook (SessionStart PID 死活檢測 + 自動 GC)
- feat: skill-cli-error-feedback-hook 補充模式（偵測 ErrorEnvelope 標記跳過引導）
- feat: create.py 業務錯誤改走 ErrorEnvelope 結構化通道
- feat: argparse 業務錯誤改走 format_error 結構化路徑
- feat: format_error 升級為雙路徑（legacy str + ErrorEnvelope）
- feat: ticket track log 新增 --section 過濾參數
- feat: append-log section 標題容錯（A+B 合併方案）
- feat: ticket track show 作為 full 的 alias
- feat: add-spawned 支援 nargs='+' 多 ID 對齊 Unix 慣例
- feat: ticket skill sync-check hook（C 路徑落地）
- feat: 套用 multi-view review 修正規則檔 （AC-5 待 PM 二次 review）
- feat: 補強 ticket skill 行為變更同步檢查規則（AC-4 待 PM multi-view）
- feat: 決策樹閉環流程（無法立刻決策時的合法 5 step）
- feat: 落地禁用無 ticket trigger 延後決策原則
- feat: multi_view_checker 加 nested YAML 結構誤用提示
- feat: Stop hook should_preserve_pending_json 對齊 CLI stale 規則
- feat: 抽 handoff_utils.is_handoff_stale 共用函式 + 4 情境單元測試
- refactor: acceptance-gate hook ana_spawned_checker 退場
- refactor: process-skip-guard get_active_in_progress_ticket short-circuit
- refactor: 抽取 section_locator helper 移除 4 處 section pattern 重複
- fix: test_create_source_ticket 5 斷言對齊 ErrorEnvelope 新格式
- fix: 修復 complete schema 錯誤訊息使用不存在的 append-log --content
- fix: handoff-reminder-hook 套用 stale 過濾並提示已過濾數
- fix: track_relations closed/superseded 分組 + grep lint 防護
- fix: handoff/auditor/checkpoint 6 處 terminal 對齊
- fix: view 層 board+stuck_anas+query 3 處 terminal 對齊
- fix: chain_analyzer.py 8 處 terminal 語意對齊
- fix: lifecycle 內部 terminal 語意一致性對齊
- docs: 升級 提煉 memory 為 framework 規則
- docs: 統一 ANA 落地語意 + 建立 field-semantics.md SSOT
- docs: track-command.md 同步 runqueue exit_status tag 說明
- docs: worktree SKILL 新增 Agent isolation worktree GC 機制章節
- docs: 新增 PC-120 + 修正 multi-view 整合無 trigger 延後違規
- docs: 新增 PC-119 parallel-evaluation 用法誤解 — 單派 linux 視角
- docs: 補強 .5 group 引導文件 PC-105 防護（ErrorEnvelope / hook envelope 偵測說明）
- docs: 撰寫 PC-118 ticket skill 行為變更未同步決策層反模式
- docs: ana-solution-schema 加 forbidden_format 段落明示禁 nested
- docs: 新增 PC error pattern — ANA multi_view_status nested YAML hook 誤判
- docs: 落地 4 反模式防護三件式
- docs: PC-115 真因調查計畫 + 4 spawned 子實驗 ticket
- docs: Hypothesis K 強形式被否證
- docs: PC-115 五輪實驗 + Hypothesis K + tickets 紀錄
- docs: 更新 subagent .claude/ Edit deny 根因為 runtime hardcoded（）
- chore: hook-completeness-check 自動加上 test file 執行權限 (IMP-054)
- chore: 補齊 4 hook test 檔案執行權限
- test: 新增 5+ 錯誤通道整合測試（驗證 .5 group 端到端行為）
- test: 補多行 nested YAML invalid 分支測試 case
- test: 三方 handoff stale 一致性整合測試（9 case 矩陣）

---

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
