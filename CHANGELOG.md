## [2.52.2] - 2026-09-04

### Summary
docs: 時序變體 Action 改為可數觸發判準; docs: 補時序變體「被否證的猜測為取代它的猜測背書」; chore: VERSION 回寫，P0 執法型 hook 測試補齊推送至 canonical

Changes: 2 docs, 1 chore

- docs: 時序變體 Action 改為可數觸發判準
- docs: 補時序變體「被否證的猜測為取代它的猜測背書」
- chore: VERSION 回寫，P0 執法型 hook 測試補齊推送至 canonical

---

## [2.52.1] - 2026-09-04

### Summary
chore: VERSION 回寫，本波九票修復推送至 canonical; test: 補齊三支零測試執法型 hook 的功能性測試，遷移 domain-import-lint-hook.py 至 hook_utils 統一日誌

Changes: 1 chore, 1 test

- chore: VERSION 回寫，本波九票修復推送至 canonical
- test: 補齊三支零測試執法型 hook 的功能性測試，遷移 domain-import-lint-hook.py 至 hook_utils 統一日誌

---

## [2.52.0] - 2026-09-04

### Summary
feat: 擴充 dispatch-readiness 檢查 4 涵蓋 glob 路徑提及; feat: owned-issues 本地登記檔取代 SessionStart hook gh search 粗篩; fix: 錯誤信封尾部摘要行防 tail -N 截斷（某票） (+10 more)

Changes: 2 feat, 3 fix, 7 docs, 1 chore

- feat: 擴充 dispatch-readiness 檢查 4 涵蓋 glob 路徑提及
- feat: owned-issues 本地登記檔取代 SessionStart hook gh search 粗篩
- fix: 錯誤信封尾部摘要行防 tail -N 截斷（某票）
- fix: sync-push skill 雜湊分歧清單免責句前置
- fix: sync-push 訊息產生器移除留可見佔位，消除句中剝除斷句
- docs: 補自指檢查節，明示本筆處置與其所修缺陷同構
- docs: 沉默有多種成因而其中一種被預設
- docs: 補「借來的嚴謹性本身未經驗證，兩端一致是它製造的」
- docs: 剝除 CHANGELOG.md 既有歷史區塊殘留的 12 處 consumer 專屬 ticket ID
- docs: 補 A/B 型邊界與 Action 前提
- docs: 補延伸節「正確的計數掩蓋脆弱的方法」
- docs: 同一產出中查證與猜測並列，查證的部分使猜測看似也經查證
- chore: VERSION 回寫 某版本，本波七票修復推送至 canonical

---

## [2.51.0] - 2026-09-04

### Summary
feat: SessionStart hook 對本專案擁有區段的 framework issue 執行 check; feat: dispatch-readiness 新增檢查 6，acceptance 提及路徑未落在 where.files 內即 FAIL; fix: 收窄 bare-commit-guard -a／--all 並行期豁免並改寫 DENY 訊息 (+6 more)

Changes: 2 feat, 3 fix, 3 docs, 1 chore

- feat: SessionStart hook 對本專案擁有區段的 framework issue 執行 check
- feat: dispatch-readiness 新增檢查 6，acceptance 提及路徑未落在 where.files 內即 FAIL
- fix: 收窄 bare-commit-guard -a／--all 並行期豁免並改寫 DENY 訊息
- fix: section_comment dedup 關鍵字含 - 開頭 token 不再誤判為旗標
- fix: sync-push CHANGELOG 產生器不再把 revert 原 commit 的 ticket ID 寫入條目
- docs: 同步 dispatch-readiness 文件至檢查 4/5/6 與 exit code 分流語意
- docs: 泛化規則二截斷方向為輸出過濾方向，涵蓋 grep 白名單/-v
- docs: 同一名稱跨兩個同步狀態，讀者把分歧歸因至錯誤的一邊
- chore: sync-pull （6 delta，0 衝突）

---

## [2.50.9] - 2026-09-04

### Summary
chore: 合併結果回推，驗證 consumer 側手動補齊內容與上游一致

前次 push（v2.50.8）之後本地無實質內容變更，本次為合併結果的確認性
回推。若判定 no-change 則屬預期——第一次 pull 的手動補齊（七檔採
upstream、README 合併保留 PC-GPD、PC-BAL-024 去重）已隨 v2.50.8 推送，
之後的 pull 為 0 delta。

---

## [2.50.8] - 2026-09-04

### Summary
chore: PC-GPD-005/006 進 canonical，收斂 consumer 側 sync 落差

本次推送的實質內容是兩份 error-pattern（檔案 + README 索引兩行），
建立於上次 push（2.43.1）之後，故 canonical 只有 PC-GPD-001~004：

- PC-GPD-005 版號是單調計數器不表達分叉，兩個 consumer 各自前進一步
  即撞號，內容雜湊只證明不同不證明誰新
- PC-GPD-006 「各專案自建」目錄跨 consumer 整包複製，夾帶他方 ticket
  編號與指向不存在檔案的索引

未推送使該 consumer 的 README 與上游在同一表格區塊持續分歧，每次 pull
重現同一衝突且 base SHA 無法推進（腳本以「本輪有衝突」為不推進條件，
而人工解衝突發生在腳本結束之後）。推送後兩側一致，下次 pull 即收斂。

settings.json 另含一項本地多出的 hook 註冊
（skills/ticket/hooks/ana-ticket-metadata-validation-hook.py，該檔
canonical 已有、僅未註冊）。

---

## [2.50.7] - 2026-09-03

### Summary
feat: framework-issue comment-as-section 協作 CLI（section_comment 六命令）與 framework-issue-curator 代理人；fix: needs-context-listener 與 workspace-wipe-guard 改為命令位置 token 比對（共用 parse_command_statements）；docs: PC-BAL-064/065、ARCH-BAL-013、PC-BAL-024 案例補充（跨 consumer 協作實證，tarrragon/claude#81 #82 #61）

---

## [2.50.6] - 2026-09-03

### Summary
feat: idle agent 回收 SOP 觸發層（SessionStart 唯讀掃描、歸屬三分、孤兒兩級判定）與 agent_handle 識別碼修復（取代對命名派發不可靠的 agentId，解平行情境候選恆空）；另含 PC-163 部分過期評估、狀態列語意判定為框架不可介入、PC-BAL-064 判準取樣維度

---

## [2.50.5] - 2026-09-03

### Summary
fix: 三張衍生修復票——hook_base 新增預設關閉的測試隔離逃生艙解 worktree 內假失敗、error-patterns 索引重複列偵測改比對實際檔案數、baseline 測試改邏輯不變式消除並行寫入假紅燈；另修正 worktree/ticket SKILL.md 對 ticket 狀態隔離的過期文件承諾

---

## [2.50.4] - 2026-09-03

### Summary
fix: 四張修復票——SubagentStop 改標記回合結束使 dispatch 記錄不再於代理人存活期間消失（並行安全防護恢復）、sync-pull 衝突檔改寫回合併結果不再靜默丟棄 upstream 變更、wrap-decision guard 訊息內嵌自足 yaml 範例、error-patterns 索引新增 README 重複列偵測；另含 PC-BAL-062/063 與 PC-BAL-045 更正

---

## [2.50.3] - 2026-09-03

### Summary
fix: 更正 PC-BAL-045 的 ListAgents 覆蓋缺口軸判斷、新增 ARCH-BAL-021 撞號分叉模式、收下方法論 1.12.1 與 doc 1.12.1 欄位數修正、還原 neurodivergent-output 被繞過的 1.9.0（合併為 1.10.0）

---

## [2.50.2] - 2026-09-03

### Summary
feat: canonical skill 四項更新（component-contract-design 新增、doc 1.12.0、version-bootstrap 1.5.0、foundation-design 6.2.0 合併撞號）與 component-library 方法論 1.12.0、PC-GPD-003/004

---

## [2.50.1] - 2026-09-03

### Summary
fix: 統一五處掃描搬移命令的根目錄解析為 ticket 狀態 root; fix: 修復 checkpoint_state handoff pending 目錄路徑錯字; fix: topic_registry 改用 ticket 狀態 root 解析 (+1 more)

Changes: 3 fix, 1 chore

- fix: 統一五處掃描搬移命令的根目錄解析為 ticket 狀態 root
- fix: 修復 checkpoint_state handoff pending 目錄路徑錯字
- fix: topic_registry 改用 ticket 狀態 root 解析
- chore: VERSION 回寫 （ 骨架固定句 + runqueue root 修復傳播至 canonical）

---

## [2.50.0] - 2026-09-03

### Summary
feat: 骨架加前景執行固定句 + parallel-dispatch 補 in_progress idle 逾時判準; fix: track_runqueue handoff pending root 解析改用 get_ticket_state_root; chore: VERSION 回寫 、兩票派發骨架、 關閉為 重複

Changes: 1 feat, 1 fix, 1 chore

- feat: 骨架加前景執行固定句 + parallel-dispatch 補 in_progress idle 逾時判準
- fix: track_runqueue handoff pending root 解析改用 get_ticket_state_root
- chore: VERSION 回寫 、兩票派發骨架、 關閉為 重複

---

## [2.49.2] - 2026-09-03

### Summary
fix: 統一 handoff/dispatch-active 協調狀態根目錄解析為 ticket 狀態 root; fix: sync commit_files_isolated fake signature with cwd param; fix: 統一 list_ticket_files_from_main 的 project_root 解析根目錄 (+2 more)

Changes: 3 fix, 1 docs, 1 chore

- fix: 統一 handoff/dispatch-active 協調狀態根目錄解析為 ticket 狀態 root
- fix: sync commit_files_isolated fake signature with cwd param
- fix: 統一 list_ticket_files_from_main 的 project_root 解析根目錄
- docs: 新增 PC-BAL-061 驗收範圍以 where.files 為界漏檢同函式 mock 簽名漂移（ 回歸復盤，修復票 ）
- chore: VERSION 回寫 （/026/027 worktree 根目錄修復傳播至 canonical）

---

## [2.49.1] - 2026-09-03

### Summary
fix: 修復 _resolve_ticket_state_root 測試隔離分支消除 worktree 假失敗; fix: 修正 complete 自動提交在 linked worktree 內以呼叫端 cwd 為 repo; fix: 統一 topic-assignments 與工作日誌 appender 的根目錄解析 (+1 more)

Changes: 3 fix, 1 chore

- fix: 修復 _resolve_ticket_state_root 測試隔離分支消除 worktree 假失敗
- fix: 修正 complete 自動提交在 linked worktree 內以呼叫端 cwd 為 repo
- fix: 統一 topic-assignments 與工作日誌 appender 的根目錄解析
- chore: VERSION 回寫 （dispatch --dry-run 傳播至 canonical）

---

## [2.49.0] - 2026-09-02

### Summary
feat: ticket track dispatch 新增 --dry-run 只輸出骨架不落票; chore: 回寫 .claude/VERSION 至

Changes: 1 feat, 1 chore

- feat: ticket track dispatch 新增 --dry-run 只輸出骨架不落票
- chore: 回寫 .claude/VERSION 至

---

## [2.48.1] - 2026-09-02

### Summary
chore: 回寫 .claude/VERSION 至 ；建立 快取測試票並登記主題; test: 補齊 ticket frontmatter 磁碟快取與 ticket_state_root 行程快取的專屬測試

Changes: 1 chore, 1 test

- chore: 回寫 .claude/VERSION 至 ；建立 快取測試票並登記主題
- test: 補齊 ticket frontmatter 磁碟快取與 ticket_state_root 行程快取的專屬測試

---

## [2.48.0] - 2026-09-02

### Summary
refactor: 抽離 dispatch 骨架純組裝函式使行數測試量測 CLI 本體; fix: rule8 guard 補新建巢狀目錄下新檔的 repo root 解析回退; docs: tool-selection 規則二增列非專案來源拒絕處置 (+4 more)

Changes: 1 refactor, 1 fix, 3 docs, 1 chore, 1 perf

- refactor: 抽離 dispatch 骨架純組裝函式使行數測試量測 CLI 本體
- fix: rule8 guard 補新建巢狀目錄下新檔的 repo root 解析回退
- docs: tool-selection 規則二增列非專案來源拒絕處置
- docs: 收窄 foundation-design 三維度路由 saas-tech-selection 適用條件
- docs: 補與 wrap-decision 的分工與路由
- chore: 回寫 .claude/VERSION 至
- perf: frontmatter 快取解 conflicts --for/--among 票面讀取瓶頸

---

## [2.47.0] - 2026-09-02

### Summary
revert: manual verify fix (will be reverted); feat: set-where --files/value 路徑補 auto-commit 留痕; fix: set-where 同時帶路徑與 --layer 時 files 靜默未同步 (+3 more)

Changes: 1 revert, 1 feat, 2 fix, 1 chore, 1 perf

- revert: manual verify fix (will be reverted)
- feat: set-where --files/value 路徑補 auto-commit 留痕
- fix: set-where 同時帶路徑與 --layer 時 files 靜默未同步
- fix: resolve track commit against linked worktree repo root
- chore: 回寫 .claude/VERSION 至 並登記 主題歸屬
- perf: conflicts --for/--among 改走 O(k·n) 針對性比對，取代全量 O(n^2)

---

## [2.46.0] - 2026-09-02

### Summary
feat: where.files 快照路徑存在性檢查與失效標示; feat: where.files 路徑存在性檢查納入建票與派發前防線; feat: 新增 track conflicts --for/--among 針對性查詢 (+1 more)

Changes: 3 feat, 1 chore

- feat: where.files 快照路徑存在性檢查與失效標示
- feat: where.files 路徑存在性檢查納入建票與派發前防線
- feat: 新增 track conflicts --for/--among 針對性查詢
- chore: 回寫 .claude/VERSION 至

---

## [2.45.2] - 2026-09-02

### Summary
fix: star-anise-system-designer 補上 Write/Edit/Bash 使工具清單與職責相符; fix: 修正 rule8 guard 對 worktree 路徑的誤判; docs: 補強 multi-round-review reviewer 回報指引 (+2 more)

Changes: 2 fix, 2 docs, 1 chore

- fix: star-anise-system-designer 補上 Write/Edit/Bash 使工具清單與職責相符
- fix: 修正 rule8 guard 對 worktree 路徑的誤判
- docs: 補強 multi-round-review reviewer 回報指引
- docs: bash 規則二補截斷方向條款
- chore: 回寫 .claude/VERSION 至

---

## [2.45.1] - 2026-09-02

### Summary
fix: P0 修復 skill 版本擷取未涵蓋 CHANGELOG 外移格式; chore: 回寫 VERSION 至 並登記主題歸屬

Changes: 1 fix, 1 chore

- fix: P0 修復 skill 版本擷取未涵蓋 CHANGELOG 外移格式
- chore: 回寫 VERSION 至 並登記主題歸屬

---

## [2.45.0] - 2026-09-02

### Summary
feat: 遷移 ANA ticket metadata 驗證邏輯至 ticket create CLI; fix: 升級兩個 hook 的 CLAUDE_PROJECT_DIR fallback 為 get_project_root; fix: comment-qa-hook.py 的 PROJECT_ROOT 改用 get_project_root (+39 more)

Changes: 1 feat, 8 fix, 31 docs, 2 chore

- feat: 遷移 ANA ticket metadata 驗證邏輯至 ticket create CLI
- fix: 升級兩個 hook 的 CLAUDE_PROJECT_DIR fallback 為 get_project_root
- fix: comment-qa-hook.py 的 PROJECT_ROOT 改用 get_project_root
- fix: spec skill test_spec_014_v1_4_passes 改用自足 fixture
- fix: 擴充 portability gate 至裸格式 ticket ID，清理四個 skill 違規
- fix: 錨定 skill-sync/ticket 的 hook-logs 路徑至專案根目錄
- fix: 合併 spec skill 1.6.2 內容改進並清理雙向專案 ticket ID
- fix: 移除 broken-link-check CHANGELOG.md 的專案 ticket ID 並合併重複 Source
- fix: 修復 broken-link-check 與 wrap-decision 推送造成的格式回退
- docs: 清除 ticket skill SKILL.md 全部 80 處識別符（fence 內外皆處理）
- docs: 清除 broken-link-check scan_links.py 與 SKILL.md 殘留識別符
- docs: 外移 error-pattern 與 doc 版本紀錄（D6 批次，D 類最後一批）
- docs: 外移 continuous-learning 與 parallel-evaluation 版本紀錄（D5 批次）
- docs: 外移 version-bootstrap 與 chrome-extension-mcp-debug 版本紀錄（D4 批次）
- docs: 外移 version-release 與 framework-issue 版本紀錄（D3 批次）
- docs: 外移 worktree 與 design-decision-framework 版本紀錄（D2 批次）
- docs: 外移 search-tools-guide 與 test-assertion-design 版本紀錄（D1 批次）
- docs: 回補 C 類批次 15-17 遺漏的 Last Updated（判準 2 反轉）
- docs: 外移 ticket 版本紀錄，保留 bullet 結構並清除 14 處識別符
- docs: 外移 skill-design-guide 與 version-sequencing 版本紀錄（C 類批次 17）
- docs: 外移 foundation-design 與 test-effectiveness 版本紀錄（C 類批次 16）
- docs: 外移 dart-provider-architecture 版本紀錄（C 類批次 15，framework-issue 排除）
- docs: 補做 teaching-sync 版本紀錄外移（PM 裁決：兩版號並存）
- docs: 外移 zellij 版本紀錄（批次 14，ticket 排除）
- docs: 外移 tech-debt-capture 版本紀錄（批次 13，teaching-sync 排除）
- docs: 外移 startup-check 與 strategic-compact 版本紀錄（批次 12）
- docs: 外移 project-init 與 scope-confirmation 版本紀錄（批次 11）
- docs: 外移 mermaid-ascii 與 pre-fix-eval 版本紀錄（批次 10）
- docs: 外移 lsp-first 與 methodology-writing 版本紀錄（批次 9）
- docs: 外移 doc-flow 與 evidence-driven-bugfix 版本紀錄（批次 8）
- docs: 外移 decision-tree-helper 與 dispatch-strategy-review 版本紀錄（批次 7）
- docs: 外移 dart-test-async-guardian 與 data-extraction 版本紀錄（批次 6）
- docs: 外移 cognitive-load-assessment 與 dart-style-guardian 版本紀錄（批次 5）
- docs: 外移 bulk-evaluate 與 cc-release-impact-review 版本紀錄（批次 4）
- docs: 外移 agent-team 與 branch-worktree-guardian 版本紀錄（批次 3）
- docs: 外移 impeccable 版本紀錄（批次 2）
- docs: 外移 dart-domain-modeling 與 verify 版本紀錄（批次 1）
- docs: 記錄 hook-logs cwd 路徑解析疊加 shim 造成稽核錯置的 error-pattern
- docs: 移除 broken-link-check 測試檔內的專案 ticket ID
- docs: 新增 PC-BAL-060 逃生閥授權範圍僅及發放它的閘門
- chore: 同步 11 個 skill 至發佈庫版本並帶入 CHANGELOG 格式
- chore: 回寫 .claude/VERSION 至

---

## [2.44.0] - 2026-09-01

### Summary
feat: reference-stability-rule8-guard 新增 relocation 逃生閥類別; feat: 新增 get_ticket_state_root 使 worktree 內 ticket 狀態寫入主倉庫; fix: acceptance-gate-hook 步驟 8 self_check_warning 套用 chained-write 抑制 (+9 more)

Changes: 2 feat, 5 fix, 3 docs, 2 chore

- feat: reference-stability-rule8-guard 新增 relocation 逃生閥類別
- feat: 新增 get_ticket_state_root 使 worktree 內 ticket 狀態寫入主倉庫
- fix: acceptance-gate-hook 步驟 8 self_check_warning 套用 chained-write 抑制
- fix: 收斂自檢 warning 層 type 範圍為 IMP/ANA，對齊 gate 層 DOC 豁免
- fix: 依 Layer 2 審查修正 ARCH-BAL-013 第四例的事實錯誤與文字品質
- fix: 修復 bare-commit-guard 空 files 派發記錄使不相交放行路徑失效
- fix: 骨架瘦身修復 dispatch prompt 超出 length guard 30 行硬上限
- docs: 外移叢集 B/C（Worktree 隔離、派發機制選用+idle 回收 SOP）至 references/
- docs: 外移叢集 D 實驗器材治理至 references/，主文件 stub 化
- docs: 補充 tool-output-trust 規則 5 的瞬時狀態維度
- chore: 熱點取向定案後的票面補齊與 error-pattern 沉澱
- chore: 推送 並回寫 VERSION

---

## [2.43.6] - 2026-08-28

### Summary
chore: 推送 並回寫 VERSION

Changes: 1 chore

- chore: 推送 並回寫 VERSION

---

## [2.43.5] - 2026-08-28

### Summary
fix: 標題式 handoff 段落終點補進度追蹤條列判準; fix: turn-end auto-commit 補 session 歸屬過濾; fix: auto_commit 改用隔離索引 CAS，取代 pathspec commit (+9 more)

Changes: 5 fix, 6 docs, 1 chore

- fix: 標題式 handoff 段落終點補進度追蹤條列判準
- fix: turn-end auto-commit 補 session 歸屬過濾
- fix: auto_commit 改用隔離索引 CAS，取代 pathspec commit
- fix: 對齊 liveness 索引與業務日誌的 root 解析
- fix: FIFO fallback 停用於候選數>1 + 日誌/狀態 root 對齊
- docs: PC-BAL-008 新增衝突合併收尾廣域 staging 變體
- docs: 新增反向變體——守衛較嚴而規則層滯後
- docs: 規則七涵蓋擴充至衝突合併收尾的廣域 staging
- docs: 補規則七第三則邊界說明（過期 index 快照）
- docs: 新增 IMP-BAL-018 module 層級路徑常數繞過測試隔離
- docs: 新增 PC-BAL-059 驗收子項移交未同步上游
- chore: 推送 並回寫 VERSION

---

## [2.43.4] - 2026-08-28

### Summary
fix: auto_register_hooks 於 yaml 不可用時補雙通道警訊; chore: 推送 並回寫 VERSION

Changes: 1 fix, 1 chore

- fix: auto_register_hooks 於 yaml 不可用時補雙通道警訊
- chore: 推送 並回寫 VERSION

---

## [2.43.3] - 2026-08-28

### Summary
fix: 正向孤兒稽核命中大小寫變體時不再建議手動移除; chore: 推送 並回寫 VERSION

Changes: 1 fix, 1 chore

- fix: 正向孤兒稽核命中大小寫變體時不再建議手動移除
- chore: 推送 並回寫 VERSION

---

## [2.43.2] - 2026-08-28

### Summary
fix: correct diagnosis - dedup logic sound, real gap is missing pyyaml dependency causing silent no-op; fix: 反向孤兒提醒對大小寫變體改述，不建議誤導性補齊; fix: bind commit-stage-guard-gate scan to ref-write event via reference-transaction (+3 more)

Changes: 4 fix, 1 docs, 1 chore

- fix: correct diagnosis - dedup logic sound, real gap is missing pyyaml dependency causing silent no-op
- fix: 反向孤兒提醒對大小寫變體改述，不建議誤導性補齊
- fix: bind commit-stage-guard-gate scan to ref-write event via reference-transaction
- fix: 修復 sync-pull 三方合併純大小寫改名誤刪本地檔
- docs: PC-BAL-058 補列舉有效性的觀察者獨立性限定
- chore: pull .claude 更新（上游 6d969410）並還原跨專案引用

---

## [2.43.1] - 2026-08-28

### Summary
fix: 修三條——第 7 步反向會合法化 bug、走訪漏符號 ref、數量誤述; docs: 修翻譯探針的三條，第四條判為誤報; docs: 依 63 條審查 finding 完整重寫並拆出衛星檔 (+11 more)

Changes: 1 fix, 11 docs, 2 chore

- fix: 修三條——第 7 步反向會合法化 bug、走訪漏符號 ref、數量誤述
- docs: 修翻譯探針的三條，第四條判為誤報
- docs: 依 63 條審查 finding 完整重寫並拆出衛星檔
- docs: 補 rev-parse 的狀態相依語意
- docs: 補 rev-parse 消歧義法，示範升級為三段
- docs: old-oid 全零的實測全貌，並新增操作面章節
- docs: 收窄閘門宣稱並更正「不宜作內容檢查」的理由
- docs: 落點推論修正為 reference-transaction 與伺服器端
- docs: 更正限定節，補上遺漏的 commit 層補網
- docs: 新增 naming-verifies-taxonomy 方法論並註冊索引
- docs: 移除死引用並限定案例二的證據範圍
- docs: 補 PC-BAL-057 雙向引用與「意圖抑制追問」一節
- chore: base SHA 推進至 15d14be8，README 索引重生
- chore: 框架同步至 2.43.0 並解三個 sync 衝突

---

## [2.43.0] - 2026-08-27

### Summary
feat: 擴充 install-skill-clis shim 涵蓋全部 7 個 uv-tool CLI; fix: 修復 sync-pull 案例級大小寫刪除 skill 入口檔且強化刪除訊號顯著性; docs: IMP-BAL-017 補轉述方向變體 + 建 shim 覆蓋票 (+2 more)

Changes: 1 feat, 1 fix, 2 docs, 1 chore

- feat: 擴充 install-skill-clis shim 涵蓋全部 7 個 uv-tool CLI
- fix: 修復 sync-pull 案例級大小寫刪除 skill 入口檔且強化刪除訊號顯著性
- docs: IMP-BAL-017 補轉述方向變體 + 建 shim 覆蓋票
- docs: 補三個 pattern 缺漏的基本資訊區塊；建 追蹤 pull 刪檔
- chore: 回寫 .claude VERSION ->

---

## [2.42.11] - 2026-08-27

### Summary
fix: sync-pull hook 自動登記去重 key 改為腳本身分; fix: skill.md 大小寫檢查機制擴充與訊息改寫; fix: sync-push 推送前檢查遠端 skill.md 大小寫 (+3 more)

Changes: 4 fix, 2 docs

- fix: sync-pull hook 自動登記去重 key 改為腳本身分
- fix: skill.md 大小寫檢查機制擴充與訊息改寫
- fix: sync-push 推送前檢查遠端 skill.md 大小寫
- fix: 還原 settings.json 至 pull 前狀態，消除 105 組重複 hook 登記
- docs: IMP-BAL-017 交叉引用 PC-GPD-001；建 追蹤 gitignore 缺口
- docs: PC-BAL-056 補必要細分（執行本身也分維度）

---

## [2.42.10] - 2026-08-27

### Summary
收尾同步：skill-design-guide 1.2.0 外部引用規則、兩份 skill 引用改指名身分、component-library 1.8.0 Web 端元件庫產物定義

---

## [2.42.9] - 2026-08-27

### Summary
skill-design-guide 1.2.0：外部引用規則

---

## [2.42.8] - 2026-08-27

### Summary
skill 引用形式改為指名身分

---

## [2.42.7] - 2026-08-27

### Summary
component-library 方法論 1.8.0：補 Web 端元件庫產物定義

---

## [2.42.6] - 2026-08-27

### Summary
skill Version footer 補正

---

## [2.42.5] - 2026-08-27

### Summary
foundation-design 5.0.0：判準通則化，六 repo 實跑驗證

---

## [2.42.4] - 2026-08-27

### Summary
foundation-design 4.2.0：實跑驗證後修正，含一處已推送的事實錯誤更正

---

## [2.42.3] - 2026-08-27

### Summary
多輪審查（Round 1-3）修正：foundation-design 判定對象改為產物、version-sequencing 補不變量 4 散文落地形態、方法論四塊表述一致化、PC-BAL-010 補空集合子群

---

## [2.42.2] - 2026-08-27

### Summary
feat: 新增 foundation-design 與 version-sequencing 兩個跨專案 skill（規格與實作之間的基礎設施設計區塊；規格完備後的版本序列規劃）

---

## [2.42.1] - 2026-08-27

### Summary
fix: 落地 PC-BAL-022 baseline 對照要求至派發鏈; fix: doc update 冪等呼叫誤判為失敗導致 tracking.yaml 永不同步; docs: 新增 IMP-BAL-016（兩因壓成一回傳值，訊息指名錯誤方向）並建 1118 (+1 more)

Changes: 2 fix, 1 docs, 1 chore

- fix: 落地 PC-BAL-022 baseline 對照要求至派發鏈
- fix: doc update 冪等呼叫誤判為失敗導致 tracking.yaml 永不同步
- docs: 新增 IMP-BAL-016（兩因壓成一回傳值，訊息指名錯誤方向）並建 1118
- chore: 回寫 .claude VERSION ->

---

## [2.42.0] - 2026-08-26

### Summary
feat: commit 層阻擋 tracking_schema.json 相對 .py 過期; chore: 回寫 .claude VERSION ->

Changes: 1 feat, 1 chore

- feat: commit 層阻擋 tracking_schema.json 相對 .py 過期
- chore: 回寫 .claude VERSION ->

---

## [2.41.0] - 2026-08-26

### Summary
feat: doc schema export --json 圖譜型別表 JSON 匯出; fix: 雙向一致性測試改比對磁碟 JSON，非即時產生的同源 dict; chore: 回寫 .claude VERSION ->

Changes: 1 feat, 1 fix, 1 chore

- feat: doc schema export --json 圖譜型別表 JSON 匯出
- fix: 雙向一致性測試改比對磁碟 JSON，非即時產生的同源 dict
- chore: 回寫 .claude VERSION ->

---

## [2.40.3] - 2026-08-26

### Summary
fix: dispatch-record-hook 補入 hook exclude 清單; chore: 回寫 .claude VERSION ->

Changes: 1 fix, 1 chore

- fix: dispatch-record-hook 補入 hook exclude 清單
- chore: 回寫 .claude VERSION ->

---

## [2.40.2] - 2026-08-26

### Summary
fix: 圖譜型別層級改為可查證判準，EVT 載體定案 per-file; fix: 統一圖譜型別表節點與邊的 layer 欄位命名; fix: 刪除 test_uc_registry UC-01 回填後的過期斷言 (+2 more)

Changes: 3 fix, 2 chore

- fix: 圖譜型別層級改為可查證判準，EVT 載體定案 per-file
- fix: 統一圖譜型別表節點與邊的 layer 欄位命名
- fix: 刪除 test_uc_registry UC-01 回填後的過期斷言
- chore: 拉取 saas-tech-selection 1.2.1 並修用詞
- chore: 回寫 .claude VERSION -> 並登記 1106 主題

---

## [2.40.1] - 2026-08-26

### Summary
chore: 拉取 compositional-writing 與 multi-round-review 1.52.1 並重修用詞; chore: 回寫 .claude VERSION ->

Changes: 2 chore

- chore: 拉取 compositional-writing 與 multi-round-review 1.52.1 並重修用詞
- chore: 回寫 .claude VERSION ->

---

## [2.40.0] - 2026-08-26

### Summary
feat: 落成文件圖譜型別表 Python 常數 SSOT; feat: uses_uv 判準優先讀 settings.json 登記方式; feat: 註冊 skill 禁用詞掃描 hook 至 SessionStart (+34 more)

Changes: 10 feat, 1 refactor, 7 fix, 13 docs, 3 chore, 2 test, 1 other

- feat: 落成文件圖譜型別表 Python 常數 SSOT
- feat: uses_uv 判準優先讀 settings.json 登記方式
- feat: 註冊 skill 禁用詞掃描 hook 至 SessionStart
- feat: 新增 skill 禁用詞掃描 hook（use vs mention 判別）
- feat: EMOJI_RANGES 三份副本改由程式交叉驗證
- feat: 擴充 hook 依賴檢查器解析 lib 遞移依賴
- feat: worktree create 自動補齊 macOS gitignored xcconfig
- feat: ticket 寫入端新增 emoji 與代理碼位字元閘
- feat: 接線 cli.py 的 event choices，補真實 argv 解析路徑測試
- feat: 新增 EVT 領域事件文件型別（模板/配號/producer-consumer 交叉驗證）
- refactor: 合併 validate.py._find_event_file 與 FileLocator 重複邏輯
- fix: 統一四個 dispatch-active.json 呼叫端使用 git_utils.get_project_root
- fix: 修復 ticket track commit 無法處理目錄型 where.files 宣告
- fix: uc-reference-validation-hook 尊重明確 CLAUDE_PROJECT_DIR 覆寫
- fix: 對齊 uv 隔離判準並修正 CLAUDE_PROJECT_DIR 環境變數繼承缺陷
- fix: 補齊 traceability schema 第四軸 runtime_tests 並改頂層鍵驗證為必要/選補語意
- fix: 修正 BUILD_SUMMARY.md ANSI 禁用詞用法
- fix: active-dispatch-tracker-hook 補 pyyaml PEP 723 依賴
- docs: 新建跨 session 協調區完整規則檔
- docs: 跨 session 協調區外移閾值改指名偵測承擔者
- docs: 記錄 ARCH-BAL-020 並升級 1093 為 P1
- docs: 新增 IMP-BAL-015 環境變數繼承使 cwd 隔離失效
- docs: 落地 relatedTo 方向性裁決——語意對稱、儲存單向、消費端 1-hop symmetric union
- docs: 新增 IMP-BAL-014 讀取端 sanitizer 不寫回
- docs: 記錄 TEST-BAL-010 並建隔離環境測試票
- docs: usecase 模板新增結構化 flow 區塊，uc_registry 雙軌解析
- docs: 合併 compositional-writing 與發佈庫雙向分歧，收入 5 個新 principle 卡並攔截禁用詞回歸
- docs: 改寫 wrap-decision 兩份機制文件的框架路徑引用為通用敘述
- docs: 合併 wrap-decision 與發佈庫雙向分歧（4 檔）
- docs: 移除已搬移至 references/ 的舊路徑檔案
- docs: 提升 pseudo-widen-guard 與 source-verification 至 wrap-decision 正規 references 層
- chore: dispatch 記錄
- chore: 同步 canonical 審查與寫作 skill 並重修禁用詞
- chore: --clean 傳播 6 個孤兒檔刪除後回寫版本 2.39.1
- test: 補 UC hook 隔離 venv 生產啟動方式測試（TEST-BAL-010）
- test: uc_registry 結構化 flow 雙軌解析測試
- other: 實作 relatedTo 反向索引，整合 context bundle extractor 的 1-hop symmetric union

---

## [2.39.1] - 2026-08-24

### Summary
chore: 框架資產推送後回寫版本 2.38.1 -> 2.39.0

Changes: 1 chore

- chore: 框架資產推送後回寫版本 2.38.1 -> 2.39.0

---

## [2.39.0] - 2026-08-24

### Summary
revert: chore: metadata sync post-completion (原 commit: 0.2.1-W3-868); revert: 還原 readme_index 欄位級 upsert 至基線，契約歸屬轉 決策 (原 commit: 0.2.1-W3-878); feat: 新增 set-parent 命令修正 parent_id 並同步上游 children (+165 more)

Changes: 2 revert, 21 feat, 5 refactor, 49 fix, 82 docs, 4 chore, 3 test, 2 other

- revert: chore: metadata sync post-completion (原 commit: 0.2.1-W3-868)
- revert: 還原 readme_index 欄位級 upsert 至基線，契約歸屬轉 決策 (原 commit: 0.2.1-W3-878)
- feat: 新增 set-parent 命令修正 parent_id 並同步上游 children
- feat: 新增 --discovered-during 旗標區分規劃衍生與發現衍生的建票語意
- feat: portability-check 排除誤報並依 §2.4 分類輸出
- feat: scan_links.py 新增 opt-in fence 稽核模式
- feat: 建立 compositional-writing Phase 1 portability-check.sh
- feat: ticket create 新增缺席斷言未查證軟提示
- feat: 擴充 broken-link 掃描器射程至 .py/.sh 並接上合併宣告索引
- feat: 共用 index 裸操作可觀測性 tripwire
- feat: add ticket track hook-liveness subcommand
- feat: add ticket track commit subcommand, repoint STAGING_PHRASE_AGENT
- feat: migrate_settings_hooks.py 不變式改正規形式並加對帳模式
- feat: complete auto-commit 改為隔離索引提交，不留 staged 殘留
- feat: release 對無 lease 記錄的票輸出 INFO 提示
- feat: commit 階段補網 hook 統一轉呼 12 支既有 guard 判斷函式
- feat: Bash matcher hook 補網 main-thread-edit-restriction 職責邊界
- feat: 遷移 settings.json hook 註冊為顯式解譯器形式
- feat: 攔截目錄級 where.files 近似宣告（dispatch 硬擋、create/set-where WARNING）
- feat: dispatch 骨架補 --commit-policy 與 hook 票四項提醒
- feat: length-guard 訊息指向 ticket track dispatch，模板骨架改引用 CLI 單一權威
- feat: 新增 ticket track dispatch 子命令（派發即落票）
- feat: add dispatch prompt baseline reproduction script
- refactor: multi-round-review 與 parallel-evaluation 的 8 筆跨 skill 硬連結轉條件語
- refactor: 降級 hook 可執行位防護（889 遷移後不再必要）
- refactor: 消除意圖標記正規表示式就地複本，改 import ticket_system
- refactor: 收斂 lease 三項機械債務並修正失真註解
- refactor: lease 可回收性判定收斂為單一實作，status 判定收回函式內
- fix: 修正 Context Bundle 抽取失敗時票面被截斷為 0 byte 且謊報無影響
- fix: 落地數改用集合語意，消除 processed SR 重複計數
- fix: Step 2.5.2 認 resolved spawn request 並收窄豁免判定
- fix: 放寬佔位符 hook 判定錨點涵蓋巢狀 archived/ 子目錄
- fix: 修正 scan_links.py 兩類路徑解析誤報
- fix: 更正六檔散落的 6 筆 fence 內真實 drift
- fix: pre-test-hook pubspec mtime 比較加容差
- fix: 清除範本與功能檢查設定中的失效腳本引用
- fix: workspace-wipe-guard 剝離 heredoc 資料引用避免誤判
- fix: commit_files_isolated 於 update-ref 成功後同步共用 index
- fix: 五支 hook 補接線 run_hook_safely 存活驗證
- fix: 四支 hook 補接線 run_hook_safely（943）
- fix: 補接線防護類三支 hook _liveness 存活驗證
- fix: hook_health 觸發次數改讀 _liveness 索引取代日檔行數
- fix: track_hook_health CLI 傳真實 settings.json 給 classify_hook
- fix: bootstrap 期絕對閾值依 hook_type 分級，消除高頻 hook 假 WARNING
- fix: dispatch --note 改寫入 Problem Analysis 下 H3，消除 噪音
- fix: bootstrap baseline when log coverage < 7 days
- fix: track_commit base_dir 固定用 repo_root 避免 shim cwd 誤判越界
- fix: scan_logs 適配每日輪替日誌，觸發次數改由內容行數推導
- fix: compute_content_hash 改 os.walk 剪枝取代 rglob 後過濾
- fix: _is_placeholder 逐行判定避免列表 N/A 行誤判整段
- fix: setup_hook_logging 改每日輪替 append
- fix: release INFO 提示改依結構化列舉判定，不再比對 reason 文字
- fix: scan_logs 改檔名時間戳解析取代全樹逐檔 stat
- fix: normalize commit_files_isolated paths to repo-relative before scope self-check
- fix: 正規化提交範圍自我驗證的路徑比較，修復絕對/相對路徑誤判
- fix: P0 續接——_newest_file_mtime 改非遞迴 scandir 避免逾時
- fix: guard find_nearest_tests_dir against absolute-path infinite loop
- fix: hook-health-monitor 修正 mtime 判準與 HOOK_NAME 解析
- fix: identity_guard_adoption log 路徑絕對化並禁止靜默無檔
- fix: 修正 identity_guard 測試對 complete 未帶 --as 的過期斷言
- fix: hook-health-monitor 支援顯式解譯器 command 形式解析
- fix: acceptance 兩個修改入口的 precondition 對齊
- fix: ghost 鑑識 Exit Status 缺失降為 soft warning
- fix: identity_guard 對 complete/finish 未帶 --as 由 warn 轉 deny
- fix: DENY 訊息措辭修正（不建議 pathspec fallback）
- fix: STAGING_PHRASE_AGENT 禁還原段明列動作清單
- fix: parallel-suggestion-hook 讀取巢狀 where.files schema
- fix: parallel-suggestion-hook 納入在飛票衝突邊並消除意圖解析複本
- fix: 衝突圖納入 live in_progress 票為佔用節點，消除多輪 runqueue --groups 撞擊
- fix: 移除 _warn_fresh_conflicts 自身 session 跳過
- fix: 孤兒分支稽核 undetermined 訊息依實際失敗因輸出
- fix: dispatch_prompt_baseline ticket ID 抽取加 fallback
- fix: ticket-md-auto-commit-hook 改用獨立臨時 index + plumbing 提交，杜絕 TOCTOU
- fix: 降級旗標不落盤，並自癒既有被污染的 registry 檔
- fix: 對齊 is_lease_reclaimable 與 check_reclaimable 的 owner=None 語意
- fix: compute_parallel_groups 對重複 ticket id 保序去重
- fix: where.files 意圖標記剝離下沉至共用 parser
- docs: 記錄 sort/uniq 預設 locale 合併相異 CJK 字串的統計陷阱
- docs: 修正 focus topic 宣告段可執行 grep 在巢狀 worklog 下無法解析
- docs: 更正 topic_inference.py docstring S1 覆蓋率數字與優先序論述
- docs: 移除 parallel-dispatch.md 競態窗口維度小節（前提經查證為假）
- docs: session-switching-sop 補 focus topic 宣告與收尾主題審視
- docs: idle agent 回收 SOP 補競態窗口維度（assigned 欄位）
- docs: idle agent 回收判準加入主題聚焦維度
- docs: 規則七補檔案內夾帶邊界說明
- docs: 補 runqueue callout 的 blockedBy= 輸出語意標註
- docs: 裁決 6 筆待確認用語替換
- docs: 替換 compositional-writing 與 multi-round-review 用語違規 27 筆
- docs: 替換其餘 13 skill 共 23 檔 33 筆臺灣用語違規
- docs: 替換 version-release 批次的用語違規
- docs: 記錄派發真空期未落票使 pending 被誤讀為無人處理
- docs: 轉條件語 4 個 skill 的 7 筆跨 skill 硬連結
- docs: 轉條件語 5 個單檔 skill 的 6 筆跨 skill 硬連結
- docs: 新增 ANA Solution 逐筆清單落地要求子節
- docs: 轉條件語 requirement-protocol/search-tools-guide 2 筆跨 skill 硬連結
- docs: 轉條件語 version-release/bootstrap 4 筆跨 skill 硬連結
- docs: 補明跨 ticket 禁令不涵蓋建立自身衍生票
- docs: 規則 5 spawn 情境表與 schema 對齊強制層
- docs: 轉條件語 doc skill 4 筆跨 skill 硬連結
- docs: 新增 PC-BAL-054 分析票逐筆清單未落地錯誤模式
- docs: 新增 skill-marketplace-standard §2.4 框架共用層引用條文
- docs: PC-137 與 parallel-dispatch 同步 none 模式已驗證範圍
- docs: 同步 AUQ hook 規格與測試設計的實作落差
- docs: 改指 hook_messages.py hint 至 tool-selection.md
- docs: 移除已失效的 broken-link-exempt marker
- docs: 刪除 .claude 根目錄殘留的 format-fix-examples.md 重複副本
- docs: 還原依錯誤分類誤處置的三處引用
- docs: 改寫 genuine_mixed 豁免行使 marker 只覆蓋死引用
- docs: 更正 pre-fix-eval 範本中硬編碼的已合併 hook 名稱
- docs: 更正高流量文件 10 筆 fence 內真實 drift
- docs: 新增防護「移除某物前按每一種被引用形態各搜一次」
- docs: 記錄合併標記語彙的正則抹除來源致清理任務靜默破壞另一機制
- docs: 刪除 commands/ 四檔模板遺留並清理入向引用
- docs: 移除 superfluous 豁免行的多餘 broken-link-exempt marker
- docs: 更正 commands 四檔 fence 內的 42 筆失效引用
- docs: 移除 output style 的 Session Token 欄位
- docs: 更正 references 與 hook-specs 的 45 筆失效引用
- docs: 更正 error-patterns 下 37 筆失效引用
- docs: 更正自動載入層與可執行指引層的 10 筆失效引用
- docs: 更正 pre-fix-eval 文件的舊 hook 名稱引用
- docs: 標註五處更正說明行為 broken-link 豁免
- docs: 修正兩份 error-pattern 的模態漂移與跨文件編號錨點
- docs: 更正 PC-BAL-053 立論並補 IMP-BAL-011 第四層查證
- docs: 新增 PC-BAL-053 文件宣稱的強制層從未部署
- docs: 更正 agents 與 skills 中 8 處 hook 路徑漂移引用
- docs: 新增 IMP-BAL-011 刪除工具後殘留引用的載體分級與職責交接
- docs: 修復 agent 定義與 skill 指向已刪除 test-summary.sh 的失效引用
- docs: 記錄判準在並行期間誕生未回頭同步的流程缺口
- docs: 更正 LSP 環境檢查改用 uv run --quiet --script
- docs: PC-148 佔位符範例補雙分支選用判準（PM 驗收回饋）
- docs: 修復文件中指向已刪除 hook 腳本的失效引用
- docs: 改寫依賴 shebang 直接執行的驗證慣例為顯式解譯器前綴
- docs: PC-BAL-033 補「結構性消除範圍限定」段
- docs: 依 Layer 2 審查修正新增段的四項阻塞問題
- docs: 追加實作檔與測試檔配對遺漏案例並補預防措施 4、5
- docs: 新增 ARCH-BAL-019 共享狀態變更使隱式下游靜默失效
- docs: hook-system-reference 追加撰寫紀律六
- docs: 標註 PC-BAL-033/PC-132 因 hook 日誌每日輪替而失效的診斷步驟
- docs: hook-system-reference 紀律四/五 + 紀律二升規格條文
- docs: 落地 922 收斂結論——掃描上限/路徑正規化/禁以檔案系統狀態推執行事實三紀律
- docs: 文件化 complete 的 metadata/程式碼恆分兩個 commit 語意與 --no-stage 覆蓋範圍
- docs: PC-BAL-051 補來源版本並同步 README 索引
- docs: PC-BAL-051 AUQ 選項未附量化後果致不可逆操作在資訊不完整下被授權
- docs: identity_guard 註解首句改列目前不阻擋的命令
- docs: PC-BAL-008 補實證八（過期 index 項進入 HEAD）
- docs: parallel-dispatch.md commit 紀律段移除 path-limited 主防護，改兩層制（規則七 / 隔離索引三要件）
- docs: PC-BAL-008 追加實證七（PM 前台在途 vs 派發代理人跨執行體型）
- docs: parallel-dispatch where.files 交集檢查改強制 CLI 並擴大範圍
- docs: 補述隔離索引提交完整性三要素 + hook docstring 清單來源條件
- docs: 修正 pathspec commit 首選建議與 bash 規則七的矛盾
- docs: 補 runqueue --groups 多輪重跑安全性條件並校正舊前提
- docs: harness 指令與框架正本衝突以正本為準
- docs: bash-tool-usage-rules 規則七補隔離索引 CAS 加強做法
- docs: PC-BAL-004 補「既有行為被斷言為缺陷」形態與案例二
- docs: PC-BAL-008 補實證六（反向套用還原撤銷他人合法寫入）與兩條預防措施
- docs: 補齊 11 個實作類 agent 定義與範本的讀票指令
- docs: PC-BAL-008 補實證五（核對與提交之間的殘留競態）
- docs: 依 Layer 2 審查修正 PC-BAL-050 並補 PC-168 反向連結
- docs: 新增 PC-BAL-050 單點量測升級為分佈宣稱
- chore: move AUQ hook specs into version control
- chore: 補提交 version-release 檢查項（identity-guard 採用率監測）
- chore: STAGING_PHRASE_AGENT 追加禁止還原掃入內容條款
- chore: sync-push --clean 回寫版本 2.38.1 並補 CHANGELOG
- test: 補 pre-test-hook pubspec mtime 容差回歸測試
- test: 補 heredoc 內操作名稱誤判的回歸測試
- test: 補齊四支 hook 對應測試檔（gate 命名慣例）
- other: 新增 S2 主題涵蓋度門檻，排除 hub 檔案匹配
- other: Reapply "chore: metadata sync post-completion"

---

## [2.38.1] - 2026-08-21

### Summary
sync .claude configuration

---

## [2.38.0] - 2026-08-21

### Summary
feat: 新增 audit_version 的 detect_orphan_references 雙向一致性檢查; feat: 新增 set-closed-by 修正 closed 票 closed_by 欄位; feat: check-acceptance 補上 auto-commit 對齊 set-acceptance 保護等級 (+33 more)

Changes: 7 feat, 1 refactor, 14 fix, 10 docs, 3 chore, 1 test

- feat: 新增 audit_version 的 detect_orphan_references 雙向一致性檢查
- feat: 新增 set-closed-by 修正 closed 票 closed_by 欄位
- feat: check-acceptance 補上 auto-commit 對齊 set-acceptance 保護等級
- feat: append-log 新增 --replace 旗標支援整段覆寫章節
- feat: 補強主 repo turn 結束時的 ticket md 收尾提交
- feat: 實作 onboard 無主髒檔小節
- feat: 新增 ticket create 的 when-blockedBy 一致性 WARNING
- refactor: 清空 ticket_system/lib/__init__.py 的 re-export
- fix: 補齊 skill-sync EXCLUDE_DIRS 的工具產物排除
- fix: create 命令 auto-commit 移至 Context Bundle 寫入之後
- fix: 修正 precondition completed 建議文案指向不存在的 reopen 命令
- fix: ticket create 版本未註冊時提供 --version 繞過指令
- fix: 修正 test_context_bundle_extractor fixture 以 snake_case 建 frontmatter 致三項回歸
- fix: Context Bundle 讀取端補雙態相容修復 blockedBy/relatedTo 恆失效
- fix: set-blocked-by/set-related-to 逗號分隔誤用改回專屬提示
- fix: test_pm_only_prefix 排除 worktree 副本消除跨環境擺盪
- fix: WARNING 指令範例改空格分隔，敘述位置維持頓號
- fix: 補齊 execution_log_checker 免填/選填佔位符 strip 並同步 DOC 豁免
- fix: 收斂 parser.py 至 file_lock 的模組層級匯入邊
- fix: 主套件計時斷言違反規則 D1 標記 @pytest.mark.perf
- fix: 統一全部 yaml dump 寫入點加 width 參數
- fix: 補齊 _is_placeholder 的免填佔位符變體
- docs: 校準 CLI 形態分化並補寫入端後果的案例
- docs: SKILL.md 遞增 2.15.0 並彙整本輪介面變更
- docs: 依 Layer 2 審查補上位根因、改寫歸因並收窄標題失準
- docs: 校準 ticket-lifecycle.md 的 auto-stage 範圍過時描述
- docs: 補第三形態並更正 票面與實際不符的標題
- docs: 修正 ticket SKILL.md 的 auto-stage 範圍過時描述
- docs: 補 YAML block style 延伸形態，並代建 修復票
- docs: 依 Layer 2 審查補判準與防護，修正隱喻與計數
- docs: 補 2026-08-20 續案六例與範圍平移變體
- docs: 更新 ticket-quality-gate-hook 文件引用為已刪除機制
- chore: 遞增框架版本至 2.38.0 並補 CHANGELOG
- chore: 清理 ticket-quality-gate 退場殘留
- chore: 建票追蹤 skill 發佈庫同版號異內容分歧
- test: 補回歸測試守護 create auto-commit 涵蓋 Context Bundle

---

## [2.37.1] - 2026-08-20

### Summary
chore: 拉取 compositional-writing 並回寫框架 VERSION; test: 收斂四個 ticket 測試檔的硬編碼時間播種為 conftest 共用語意化 helper

Changes: 1 chore, 1 test

- chore: 拉取 compositional-writing 並回寫框架 VERSION
- test: 收斂四個 ticket 測試檔的硬編碼時間播種為 conftest 共用語意化 helper

---

## [2.37.0] - 2026-08-20

### Summary
feat: create.py 原生票主題三選一要求（warn-only 過渡期）; feat: create.py 主題自動推導（判準 S1/S2/S3）; feat: 實作 complete 前實驗器材殘留掃描 checker (+164 more)

Changes: 32 feat, 10 refactor, 55 fix, 59 docs, 8 chore, 3 test

- feat: create.py 原生票主題三選一要求（warn-only 過渡期）
- feat: create.py 主題自動推導（判準 S1/S2/S3）
- feat: 實作 complete 前實驗器材殘留掃描 checker
- feat: board 新增依主題分組排列的模式
- feat: 新增派發前檢查目標票 md 是否已同步至 origin/main
- feat: 升級 acceptance-gate 對非法 multi_view_status 由警告改為阻擋
- feat: 新增 ticket track fix-multi-view-status CLI
- feat: 主題指派改派途徑（reassign_assignment + 歷史查詢）
- feat: 新增 ticket track topics/topic 主題視圖命令
- feat: runqueue 新增 --topic 過濾與 list 前綴標記
- feat: 派發規則新增主題層前置條款
- feat: 建票時可從主題中央清單選取，新增主題須經顯式旗標
- feat: 新增既有 pending 票的主題分批回填入口
- feat: 實作主題中央清單的 append-only 讀寫層
- feat: where.files 讀寫意圖解析（type 推導 + 逐檔標記覆寫）
- feat: add ticket track add-exempt-marker CLI
- feat: 實驗器材登記子命令 CLI 化
- feat: dispatch-staging-phrase-guard 新增獨立 Category C
- feat: 移除 append-log 對 Execution Log 的支援
- feat: hook shebang 與 PEP 723 依賴一致性檢查
- feat: frontmatter YAML 語法源頭驗證 hook
- feat: 新增 set-title 子命令，補上 title 欄位的合法更新途徑
- feat: Bash PreToolUse 廣域 git add 守衛（PC-092 執行期防線）
- feat: 補強可攜性閘門四條旁路
- feat: add Layer 2 soft hint for dispatch prompts missing precise-staging phrases
- feat: push/pull preview 補行數與方向警示
- feat: Context Bundle 抽取器 status 感知（render 標籤 + acceptance 過濾）
- feat: 補同步基準，diverged 細分三態方向判定
- feat: 限縮 related 雙向性檢查為同批次（7 天窗口）+ WARNING 行數上限
- feat: 擴充 error-pattern index hook 檢查 related 雙向性
- feat: create 對 in_progress source ticket 發出警告並收斂上行對稱條款
- feat: skill-sync push 新增可攜性閘門
- refactor: 欄位驗證抽出至 lib/field_validators.py
- refactor: ID 與序號配置抽出至 lib/ticket_id_allocator.py
- refactor: acceptance 解析抽出至 lib/acceptance_parser.py
- refactor: 主題推導抽出為 lib/topic_inference.py
- refactor: 移除 track_board.py 生產不可達的死碼
- refactor: 收斂六個繞過 where_files 的獨立讀取實作
- refactor: 抽出 _consume_global_options 降低認知負擔
- refactor: 三個 Bash git 守衛的命令解析抽為共用 lib
- refactor: 退役經判定為 parser 缺陷補償的字串型別分支
- refactor: parse_ticket_frontmatter 改用 yaml.safe_load
- fix: worktree-branch-check is_main 改為 worktree list 順序判定
- fix: stuck-anas 納入 children 落地路徑
- fix: close remaining fail-open gaps in merged worktree audit hook
- fix: 修復 get_current_branch 判定失敗時當前分支排除被跳過的 fail-open
- fix: list_worktree_branches 判定失敗時不再誤判孤兒分支
- fix: topic-backfill-assign 預設拒絕未知主題名防呆
- fix: 補上主題回填模組 CLI 入口
- fix: runqueue 空清單訊息依實際排空階段歸因
- fix: create 選定主題後接線寫入 ticket_id -> topic 映射
- fix: --new-topic 延後至建票成功後才寫入 registry
- fix: 修復 append_assignment 對無尾換行 log 的條目黏合
- fix: 修復 append_topic 對無尾換行清單檔的條目黏合
- fix: 修正 改造後未同步的文件與訊息（）
- fix: batch-claim/batch-complete 補呼叫 registry lease
- fix: 孤兒分支稽核區分判定失敗與 ahead=0，避免 fail-open 誤標可刪除
- fix: 擴充 session-start Section 3 孤兒分支掃描至人工命名分支
- fix: 降級主 repo 髒污判定由 DENY 為 WARN
- fix: workspace-wipe-guard DENY 條件擴充涵蓋主 repo 未提交變更
- fix: 修正絕對路徑 main_repo 分類在 worktree 環境的截斷誤判
- fix: PC-093 DENY 訊息補強 code fence 豁免路徑說明
- fix: 配號鎖為目錄級致跨 worktree 並行 create 撞號
- fix: 修復 M1 pattern 收逗號導致含逗號的真延後話術漏攔
- fix: 修正被阻擋的派發在 dispatch-active.json 留下幽靈記錄
- fix: 修正 PC-093 M1 規則將已完成決定的過去式敘述誤判為延後語彙
- fix: 修正 extract_ticket_id_from_command 誤判 payload 內文為真實呼叫
- fix: 擴充 bare-commit-guard 加入不相交放行條件
- fix: 修正 phase4-decision-enforcement 誤掃已 resolved spawn request 欄位
- fix: 修正 bare-commit-guard 對 payload 文字的字面誤攔
- fix: 修正 bare-commit-guard 指引訊息推人走向丟棄 index 的 pathspec 語法
- fix: dispatch-staging-phrase-guard 範本 A 對齊規則七
- fix: set-acceptance 多值旗標重複形式靜默丟棄
- fix: 修復 test_lease 的時鐘基準失配
- fix: 移除權限修復回報的 stale「未經驗證」宣稱
- fix: 回退誤入前次 commit 的 docstring 變更
- fix: 修正 children/spawned_tickets 純量寫法被靜默解析為空清單
- fix: phase_complete.py 改用 ticket CLI 寫入驗證結果，移除自維護解析
- fix: _write_validation_log 補 exact-match-first，避免寫入父子票誤配
- fix: phase_complete.py 路徑修正，Phase Contract 驗證正式上線
- fix: 重寫 contracts.yaml 對應現行單一 ticket.md 慣例，補 phase 4
- fix: 移除 DENY 訊息「可直接複製」的誤導性承諾
- fix: 修正廣域 git add 守衛判準、補三類漏放（多視角審查）
- fix: 7 個 .py 缺 .claude/lib/ 時改優雅降級（不再崩潰）
- fix: restrict phrase negation window to preceding context only
- fix: 補齊 79 個 uv-run 登記 hook 的 PEP 723 pyyaml 依賴宣告
- fix: address 14 multi-view review findings on staging phrase guard
- fix: 補五個 portable skill 的 .py 消費端引用存量
- fix: 撤回誤判，PC-BAL-033 根因 1 改判版本相依
- fix: 缺口二判準修正——存在於 canonical 不等於已跨 consumer
- fix: stop Category A phrase match crediting forbidden wording as compliance
- fix: 消除 non-uv hook 對 ambient pyyaml 的隱性依賴
- fix: wrap-decision 與 tdd 分層，blog 斷鏈歸零
- fix: 修復 .claude/hooks 測試套件內違反 D1 的絕對計時斷言
- fix: 四個 skill 的消費端引用改可攜表述，blog 斷鏈 59 → 35
- fix: 收斂 install-guide-edit-reminder-hook 硬編 hook-logs 路徑
- fix: broken-link-check 格式示範表補齊並調整豁免 marker 位置
- docs: architecture.md 模組清單校準完成
- docs: architecture.md 補本次重構新增的 4 個 lib 模組
- docs: TEST-BAL-009 同秒 pyc mtime 保留變異位元碼
- docs: TEST-BAL-008 fixture 資料形狀與真實分佈不同
- docs: SKILL.md 同步 create 主題自動推導行為
- docs: 依 Layer 2 審查修正 TEST-BAL-007 與 PC-BAL-004 第五例
- docs: 補缺陷類未驗證前提形態與第五例
- docs: 新增 TEST-BAL-007 繞道旗標綠燈誤歸因為環境問題
- docs: track_board.py 可達性盤點結論與 TEST-008
- docs: 同步 board --group-by 至 SKILL.md 與 track-command.md
- docs: 消解版本記錄兩筆並存的 1.7.0
- docs: 補防護類 hook 必含項改名的兩處散文漏網
- docs: 收尾 PC-BAL-033 機制更正的下游同步
- docs: 定案 PC-BAL-033 主文結構與檔名 slug 兩項待決問題
- docs: PC-154 補順序陷阱與靜默失效形態
- docs: 新增 PC-BAL-049 全稱結論類驗收措辭失誤
- docs: 主題層條款補回 handoff --next 的具體用法
- docs: 記錄顯式測試路徑覆蓋 testpaths 的收集母體縮小
- docs: 新增 patch 覆蓋不全的變體
- docs: 追加跨專案復發實證與同批對照組
- docs: 同步 PC-019 髒污措辭為 WARN（ 後）
- docs: 改寫回測重放測試區塊註解使其與現行 fixture 一致
- docs: 補記 --only/-o 誤判邊界延伸自既有 -a 設計限制
- docs: 修正 neurodivergent-output skill 的自我指涉敘事與計數錯誤
- docs: 新增「免費的變異：修復前的紅綠分佈」
- docs: 補強 git commit pathspec 語法丟棄 index 的並行風險條文
- docs: 新增 TEST-BAL-005 合法值收窄致測試巧合綠燈
- docs: 同步 PC-BAL-033 機制收窄至三處真命中下游
- docs: 改寫 extract_where_files docstring 的失真 rationale
- docs: 更正兩支 hook 註解層已失效的快照模型 rationale
- docs: 改寫五份測試對 str 分支存在理由的失真敘述
- docs: 更正 PC-BAL-033 可執行位檢查條目的攔截點描述
- docs: 補強 metadata.portable 的語意邊界
- docs: 記錄守衛禁止範圍大於受控介面提供範圍的錯誤模式
- docs: 記錄上游結論修訂未回溯衍生票扇出面的錯誤模式
- docs: 依兩份 Layer 2 審查報告改寫 PC-BAL-045
- docs: 實測否證 hook session 快照模型，PC-BAL-033 收窄至缺可執行位
- docs: 新增 PC-BAL-045 產出未落地被記載為 process 已結束
- docs: DOC-V1-001 補被命名端同型失效實例
- docs: 新增 PC-BAL-044 連號推定衍生票 ID
- docs: Layer 2 修正仲裁行為條文（可執行 Action+資訊優先序+去新造詞）
- docs: 新增 decision-trigger-binding 規則 2.5 條件式操作規範
- docs: 落地仲裁行為條文（agent停手上報+PM裁決回票面）
- docs: 依三視角審查改寫實驗器材規範
- docs: 精準 staging 制式句收斂為單一權威版
- docs: 新增 ARCH-BAL-018 快照正確性隨來源終態反轉
- docs: 依 zhtw 檢查修正用語與長句
- docs: 新增實驗器材自我標示與存活期治理規範
- docs: 收斂 agent-dispatch-template.md 為單一權威骨架
- docs: 修正外移閾值的性質判定並建三張 follow-up
- docs: 記錄 DOC-BAL-003 表格行尾豁免標記被下游工具刪除
- docs: 補 PC-BAL-038 對 TEST-BAL-003 的回指（該檔已解封）
- docs: 定位背景 agent 文字輸出未送達的區辨因子
- docs: 建立 TEST-BAL-004 error-pattern
- docs: 修正三則 error-pattern 的主張句位置與 related 掛錯
- docs: 協調區外移閾值自票面移入條文
- docs: 補 PC-BAL-038 觀測證據引用到 named-agent 代價段
- docs: 重寫 PC-BAL-038 根因為載體送達失效，併回 agent-dispatch-template
- docs: 刪除層級升級註記並移除其外溢引用
- chore: 修復 list_worktree_branches fail-open，記錄 IMP-BAL-010
- chore: 文件與訊息失同步修正完成，並補多輪重跑的已知缺口警語
- chore: Phase 4 審查落地與 判定降格
- chore: 安全與歸屬拆層，撤回跨群連邊移除，衍生票重規劃
- chore: 多視角審查更正 — E3 為量測假象，開修訂 ANA 並擋住五張衍生票
- chore: PC-MON-001 補記 + 關閉重複票 （duplicate of ）
- chore: 補齊 hook 入口點 PEP 723 pyyaml 依賴宣告
- chore: 完成收尾——canonical 推送、issue #78 關閉、VERSION 回寫
- test: 補齊四項前提回歸測試（無尾換行/有尾換行/空檔/缺檔）
- test: 判定 B1-B16 補償邏輯存廢並固定 str 分支行為
- test: 補齊 utf8-integrity-check-hook 測試覆蓋

---

## [2.36.0] - 2026-08-18

### Summary
refactor: lease 三態判定移至公開 API（CQ-001 防護）; fix: 計數器路徑改由 get_project_root 動態解析，解除測試對 production 抽樣計數器依賴; fix: dashboard In Progress 接線 registry lease 三態標記 (+21 more)

Changes: 1 refactor, 4 fix, 16 docs, 3 chore

- refactor: lease 三態判定移至公開 API（CQ-001 防護）
- fix: 計數器路徑改由 get_project_root 動態解析，解除測試對 production 抽樣計數器依賴
- fix: dashboard In Progress 接線 registry lease 三態標記
- fix: frontend-with-playwright 可攜性修復 + 收斂 blog 側改進
- fix: requirement-protocol 移除內嵌的本專案 ticket ID
- docs: 建立 PC-BAL-043 並修正 PC-123 被證偽的歸因
- docs: SKILL.md 接手流程排除 [LIVE] 票並路由 [RECLAIMABLE] 至 reclaim
- docs: 補齊兩則 error-pattern 的家族交叉引用
- docs: 退場條件自票面移入條文
- docs: 補齊並行 session 四載體的兩條低頻交叉引用
- docs: Layer 2 修正——並發歧義、雙向互引、原則句前移
- docs: 新增 PM 對執行中 ticket 的上行對稱條款
- docs: 落地跨 session 訊息脈絡存續判讀規則
- docs: 落地不明變更查證順位條款於 tool-output-trust-rules 規則5
- docs: 明文化 subagent 執行中建票的衍生血緣回填義務
- docs: 區分防護類 hook acceptance 前三項與第四項查核對象
- docs: PC-BAL-042 案例段補可定位錨點
- docs: 完成跨 session thread 生命週期缺漏分析，新增 PC-BAL-042
- docs: 接管判準章節 v2 整體改寫
- docs: 補發射方留痕義務與 PC-078 處方區辨
- docs: 新增跨 session 同儕沉默時的接管判準
- chore: 補齊缺卡與 business-analysis skill，恢復兩處連結
- chore: 同步 canonical 審查與寫作 skill 並合併本地客製
- chore: sync-push 回寫框架版本號 + 599 CB 殘留入庫

---

## [2.35.0] - 2026-08-18

### Summary
feat: set-acceptance 新增 --add/--edit/--remove 建票後修訂子操作; feat: ticket CLI auto-commit 附 Session trailer 歸屬; feat: worktree create 後確定性 merge main（issue #77 決議 A） (+49 more)

Changes: 8 feat, 6 refactor, 17 fix, 19 docs, 1 chore, 1 perf

- feat: set-acceptance 新增 --add/--edit/--remove 建票後修訂子操作
- feat: ticket CLI auto-commit 附 Session trailer 歸屬
- feat: worktree create 後確定性 merge main（issue #77 決議 A）
- feat: 防護 release 命令對非自身 FRESH lease 的繞過閘門路徑
- feat: AC1/2 — runqueue --groups CLI 旗標接線
- feat: 抽取共用交集判定實作 + 並行群組切分演算法
- feat: AC3 — sessions/runqueue 輸出標記 reclaimable
- feat: 實作 lease claim/reclaim 生命週期（registry 寫入端 + reclaim ghost 鑑識）
- refactor: 收斂 ticket_system 測試 fixture 複本與別名退場
- refactor: 收斂 lease 周邊 helper 複本清理批次
- refactor: pm_registry 整備批次（R3/R6/R1 部分 + recompute_lease 量化門檻文件化）
- refactor: 收斂 runqueue --groups 與 parallel-check 為共用衝突圖核心
- refactor: 收斂 resolve_session_id 五份逐字副本至 lib 單一定義
- refactor: 收斂全 hooks 的 ticket ID regex 至 lib 單一 SSOT
- fix: 放寬 FILENAME_ID_PATTERN 接受無 slug 佔位檔名
- fix: acceptance-gate 補明產生路徑盤點表讀取優先序訊息
- fix: 校準 acceptance-gate 的 Spawn Request status 解析格式
- fix: dispatch_tracker.py fsync 靜默 catch 補 stderr 提示
- fix: worklog 主檔編輯段包 flock 防 lost update + 寫後重讀驗證
- fix: pm_registry.py 的 git_utils 匯入改防禦式相對/絕對匯入
- fix: 修正三命令 docstring 自相矛盾與術語漂移批次
- fix: 對齊 track_dashboard.py 四處空狀態字面為中文樣式
- fix: pm_registry 靜默 catch 補日誌 + hook stderr 補後果說明
- fix: 步驟三 — 抽出 ARG_ALL_COMPAT 常數並收斂 5 處引用
- fix: 步驟二 — 去除 --all hedge 措辭並修正 --version 虛構互斥宣稱
- fix: 步驟一 — 刪除 5 個 track 命令的 all_versions 死參數與死分支
- fix: sessions FRESH/STALE 判定改委派 pm_registry.is_fresh（判準統一組 4）
- fix: lease.py 鑑識 fail-open 修正 + 複用收斂 + 文字修正（安全語意組 1-3、6-7、9-10、12-13）
- fix: 修正 dispatch-record-hook 回歸測試的過時存在性斷言
- fix: hooks-test-gate 過濾已刪除/改名 hook 檔避免誤報
- fix: registry files 欄位改為 tickets 推導物化值（整組重算覆蓋取代 append）
- docs: 校正 ticket-body-schema.md 第四項強制層過時宣稱
- docs: PC-BAL-041 檔名補 slug（git mv 對 untracked 檔靜默失敗的補正）
- docs: 新增即時生效工具源碼共享樹編輯紀律 + PC-BAL-041
- docs: 對齊 onboard 空狀態字面「（無活同事）」與源碼一致
- docs: 校正 --all 措辭為 576 已修正的無作用旗標字面
- docs: 校正 track_runqueue.py --groups 與 --format 關係的過期內部註解
- docs: 補齊 SKILL.md track stuck-anas 子命令總覽列
- docs: 同步 553 系列 CLI 行為變更至 ticket skill 文件
- docs: 修正 pm_registry docstring 過時延後語意 + 補測試可達性註記
- docs: 修正 track-command.md 空狀態規範範圍與 Flag 表未同步
- docs: --groups help 文字修正（文字組修正 11）
- docs: PC-BAL-040 依 basil Layer 2 審查修正四項
- docs: PC-BAL-040 檔名補 slug 使 index 一致性檢查可識別
- docs: 新增 PC-BAL-040 where.files 入口檔近似宣告缺口
- docs: 落地 PC-BAL-037 預防面規範
- docs: 校正 Stop hook 計數過期記載
- docs: 記錄 PC-BAL-039 與 CQ-BAL-001 兩則清查與修正模式
- docs: 記錄 PC-BAL-038 背景 agent 純文字產出不送達
- docs: 記錄 TEST-BAL-003 消費端先於生產端落地
- chore: sync-push 回寫框架版本號
- perf: files_intersect 改 tuple 前綴比對 + lru_cache（效能組修正 5）

---

## [2.34.0] - 2026-08-18

### Summary
feat: scan_links.py 新增可疊加掃描根，納入 docs/ 規劃文件; feat: 新增 ticket track onboard 命令（PM 入場四節彙整）; feat: 新增 ticket track conflicts 命令（where.files 交集 + impl-test 擴張啟發式） (+14 more)

Changes: 4 feat, 4 fix, 7 docs, 1 chore, 1 test

- feat: scan_links.py 新增可疊加掃描根，納入 docs/ 規劃文件
- feat: 新增 ticket track onboard 命令（PM 入場四節彙整）
- feat: 新增 ticket track conflicts 命令（where.files 交集 + impl-test 擴張啟發式）
- feat: 新增 ticket track activity 命令（multi-PM 協調層 Phase 2 L1 新鮮度）
- fix: 修正三命令文字批次與 --all 死 flag 全域清查
- fix: 修正 conflicts 的 Python impl→test 啟發式與 registry 新鮮度過濾
- fix: 修正 onboard 髒檔歸屬節的 status 過濾與呈現方向
- fix: 修正 activity 的 git --grep 父子票訊號污染
- docs: 標註 track-command.md 三處示意路徑 skill-residue-exempt
- docs: 更正 Stop event pm_only 條款過度宣稱措辭
- docs: 補三項 Layer 2 遺留發現，含新專案會復活的 template
- docs: 依 Layer 2 修正 SOP 三項 Critical 與回測誠實性
- docs: 外移 SOP 四步擴為六步，補三個實證缺口
- docs: 依 Layer 2 修正檔頭 stale 與 relocated 檔死路由
- docs: 建立載體 registry 並將已重分配條款替換為指標
- chore: sync-push 回寫框架版本號
- test: 補齊 onboard 空狀態測試四節斷言

---

## [2.33.1] - 2026-08-18

### Summary
chore: sync-push 回寫框架版本號

Changes: 1 chore

- chore: sync-push 回寫框架版本號

---

## [2.33.0] - 2026-08-18

### Summary
feat: land registry contract v2 (SessionEnd release + merge upsert); refactor: pm-role 外移與兩個 index 改按需，auto-load 降至預算內; fix: 修復 ticket 檔案存取守衛的絕對路徑與 handoff 模式兩破口 (+5 more)

Changes: 1 feat, 1 refactor, 1 fix, 4 docs, 1 chore

- feat: land registry contract v2 (SessionEnd release + merge upsert)
- refactor: pm-role 外移與兩個 index 改按需，auto-load 降至預算內
- fix: 修復 ticket 檔案存取守衛的絕對路徑與 handoff 模式兩破口
- docs: 寫入三段受眾限定條款至 11 個實作類 agent 定義檔
- docs: 補修 decision-tree 分支對舉並完成收尾
- docs: 全庫掃描修正 AGENT_PRELOAD 失效宣告與失效建議
- docs: 依 Layer 2 審查修正兩處執行期誤導並收斂自動載入層字數
- chore: sync-push 回寫框架版本號

---

## [2.32.0] - 2026-08-17

### Summary
feat: pm-registry session lifecycle hooks + dispatch-active session/ticket/files fields; feat: 新增 ticket track sessions 子命令（multi-PM 協調層 Phase 1 CLI 職責）; feat: hook protection checker 第四項改讀 how.strategy 盤點表正本 (+55 more)

Changes: 13 feat, 2 refactor, 16 fix, 22 docs, 5 chore, 1 test

- feat: pm-registry session lifecycle hooks + dispatch-active session/ticket/files fields
- feat: 新增 ticket track sessions 子命令（multi-PM 協調層 Phase 1 CLI 職責）
- feat: hook protection checker 第四項改讀 how.strategy 盤點表正本
- feat: hook_protection_acceptance_checker 新增產生路徑盤點宣告的第四項必含檢查
- feat: 強制防護類 hook ticket 三項 acceptance 並加硬擋
- feat: 改以 hook 檔案落地為監控對象，修正可執行位防護的攔截面
- feat: 改用 branch-verify-hook 的 fail-closed 語意
- feat: 改用 workspace-wipe-guard 的 fail-closed 語意
- feat: 新增 run_hook_safely 的 fail_closed 參數
- feat: 完成 AC3 跨 session 探針驗證與 Phase 4 多視角審查
- feat: 前移 hook 可執行位檢查至 settings.json 註冊當下
- feat: hook liveness 訊號使未載入與未命中可區分
- feat: 並行守衛擴充涵蓋 git stash 等全工作區破壞性操作
- refactor: 收斂 hook 註冊命令字串解析的重複實作
- refactor: 正名方向語意為假的集合名稱
- fix: dispatch-record-hook ticket_id extraction limited to prompt first line
- fix: pm-registry/dispatch-active writes use tempfile + os.replace atomic swap
- fix: frontmatter 邊界改用逐行錨定比對，修復三連減號誤判
- fix: 修正 HANDOFF_DIRECTION_REMINDER.format 缺 next_ticket_id 參數的 KeyError
- fix: 修正 _parse_yaml_lines 對頂層列表項目 YAML 折行延續行的靜默截斷
- fix: 收斂 acceptance-gate-hook subagent 早退範圍至僅抑制 AskUserQuestion 提醒
- fix: 補強 settings-registration-exec-guard 的例外可觀測性與邊界測試
- fix: 清除 append-log 寫入章節時殘留的佔位符文字
- fix: 補齊 workspace-wipe-guard 未涵蓋的等同風險變體
- fix: 修復 .skill-sync-override 被 push 推上遠端的傳染性缺陷
- fix: 補 framework 通道對無副檔名私鑰檔的排除
- fix: 補上 skill-sync push 的憑證檔排除
- fix: 收斂 docstring 排除樣式為行首錨定，消除三引號賦值型字串漏檢
- fix: 補 python profile string_exclude 缺漏的 docstring 排除
- fix: 修正 presence 字串偵測跨引號配對造成的 CJK false positive
- fix: 補齊 presence python profile 遺漏的 .claude/lib/ 與 .claude/scripts/ 框架自身豁免
- docs: 修正框架文件中已被證偽的 @-import 生效宣告
- docs: 新增 PC-BAL-037 實驗證據範圍誤擴 error-pattern
- docs: 完整 WRAP 後改採方案 F，機器讀正本取消副本宣告
- docs: 新增 PC-BAL-036 規格宣稱與實作機制脫節錯誤模式
- docs: 修正 schema 合格填法範例不通過自身 regex
- docs: 換掉被推翻的判準軸，降級 cargo cult 結論為未知
- docs: 修正 5c0fbd6b 的強制層失準宣稱與四項不一致
- docs: 重評硬擋可行性，採維度型硬擋（用戶裁示）
- docs: 依三視角審查修訂 PC-BAL-035 落地條文
- docs: 落地 PC-BAL-035 三項預防措施（全採自律層）
- docs: 修正 exec-guard docstring 自我矛盾與超前結論用語
- docs: 補對照實證章節，prompt 禁令改變衝突處理路徑
- docs: 補變體章節，新建 ticket 未讀兄弟票 acceptance 為同根因異載體
- docs: 修正鑑別方法與根因 3 的自相矛盾，補 Why 與操作型判準
- docs: 記錄注入 context 取代既有 acceptance 的靜默範圍遺失模式
- docs: PC-BAL-033 補實測條件式陳述與第二獨立成因
- docs: 記錄 PC-BAL-033 新註冊 hook 對既有 session 零效力
- docs: 補充 acceptance 的框架資產交付物相容性條款
- docs: 補 IMP-BAL-006 框架層可追溯錨點
- docs: 記錄 IMP-BAL-006 同一排除集合的多條消費路徑處置相反
- docs: 修正 sync_exclude_manifest 組合集合的註解宣稱
- docs: 補充 should_exclude 規則 1 為規則 4 效能快速路徑的說明
- chore: 測試檔更名以符合 hooks-test-gate 命名慣例
- chore: auto-fix executable permissions for hook files (IMP-054)
- chore: 補回 PC-BAL-033 缺可執行位成因與鑑別兩步
- chore: sync-push 回寫框架版本號
- test: add unit tests for session-registry-{start,heartbeat,stop} hooks

---

## [2.31.1] - 2026-08-12

### Summary
docs: 統一外部 repo 變數命名並重述五張票的環境模型; chore: sync-push 回寫框架版本號 與 worklog 進度

Changes: 1 docs, 1 chore

- docs: 統一外部 repo 變數命名並重述五張票的環境模型
- chore: sync-push 回寫框架版本號 與 worklog 進度

---

## [2.31.0] - 2026-08-12

### Summary
feat: 24 處跨 repo 引用遷移至環境無關形式; chore: sync-push 回寫框架版本號

Changes: 1 feat, 1 chore

- feat: 24 處跨 repo 引用遷移至環境無關形式
- chore: sync-push 回寫框架版本號

---

## [2.30.0] - 2026-08-12

### Summary
feat: 跨 repo 引用定出兩種環境無關形式; chore: sync-push 回寫框架版本號

Changes: 1 feat, 1 chore

- feat: 跨 repo 引用定出兩種環境無關形式
- chore: sync-push 回寫框架版本號

---

## [2.29.2] - 2026-08-12

### Summary
fix: 撤回虛構判定，定性為並行 working copy 的路徑不相容; chore: sync-push 回寫框架版本號 與 worklog 進度

Changes: 1 fix, 1 chore

- fix: 撤回虛構判定，定性為並行 working copy 的路徑不相容
- chore: sync-push 回寫框架版本號 與 worklog 進度

---

## [2.29.1] - 2026-08-12

### Summary
fix: 校正反向的 blog 路徑結論並凍結虛構立案前提; chore: sync-push 回寫框架版本號

Changes: 1 fix, 1 chore

- fix: 校正反向的 blog 路徑結論並凍結虛構立案前提
- chore: sync-push 回寫框架版本號

---

## [2.29.0] - 2026-08-12

### Summary
feat: skill 庫檢查套用 private 排除清單; feat: 阻擋 private skill 經 skill-sync push 推上公開發佈庫; chore: sync-push 回寫框架版本號

Changes: 2 feat, 1 chore

- feat: skill 庫檢查套用 private 排除清單
- feat: 阻擋 private skill 經 skill-sync push 推上公開發佈庫
- chore: sync-push 回寫框架版本號

---

## [2.28.0] - 2026-08-12

### Summary
feat: 建立 session init 實機驗證環境確認 hook; feat: saas-tech-selection 新增 verification-surface 維度; feat: 新增 acceptance 編號列表摺疊偵測警告 (+37 more)

Changes: 11 feat, 1 refactor, 12 fix, 14 docs, 2 chore

- feat: 建立 session init 實機驗證環境確認 hook
- feat: saas-tech-selection 新增 verification-surface 維度
- feat: 新增 acceptance 編號列表摺疊偵測警告
- feat: 建立 dart-provider-architecture skill 2.0.0
- feat: verify 首跑產出 build-and-drive 配方 + 首個實機驗證發現
- feat: 建立 sync-skills.yaml 專案特化 skill push 排除設定
- feat: 重疊提示改依交集特異性排序並標註熱度
- feat: complete 時提示 where.files 重疊的 pending 票
- feat: Summary 留空提示與自檢表掃描手段欄
- feat: ticket 建立與認領時掃描機器專屬絕對路徑
- feat: skill-shadowing-check-hook 增加 personal 目錄非空政策警告
- refactor: skill-shadowing-check-hook 命名漂移與論證重複清理
- fix: -t <tag> 觀察指令補 --run-skipped（skip 對命中 tag 無條件生效）
- fix: 平行審查 PM 側修正——hook UDID 穩健化 + 文件四項
- fix: set-where 路徑判定收緊，不再吞含斜線的層級描述
- fix: 依第二輪多視角審查修正偵測缺陷與結論錯誤
- fix: 機器專屬路徑偵測補上散文裸家目錄形態
- fix: set-where 路徑型輸入不再覆寫 where.layer
- fix: 依多視角審查修正假陳述、健壯性缺口與欄位損壞
- fix: 修正 Context Bundle auto 區塊邊界誤判致尾端內容重複
- fix: 修正 SKILL.md 機械鏡射段的先例引用倒置與未度量量化聲明
- fix: 修正 pm-quality-baseline 規則 7 的空 checklist 落點與涵蓋邊界
- fix: 抽出共用判準函式對齊 preview 與執行路徑 should_exclude 判定
- fix: sync-preserve.yaml 目錄項靜默無效補 stderr 警告
- docs: 多輪審查 Round 3 修正——steelman 五論點 + self-app/outbound
- docs: 多輪審查 Round 2 修正——冷讀與路由承接
- docs: wip tag 觀察指令補 --run-skipped + SR-1 落票 447
- docs: gate 連動三落點——traceability 第四軸 + 發版 on-device 項 + 實機 AC 規則
- docs: 紅燈層級順序落地三 skill（outside-in 雙迴圈）
- docs: pm-role 新增實機驗證屬 PM 職責條款
- docs: 新增 PC-BAL-031 未驗證 why 前提經自動抽取傳播至衍生票
- docs: 規則 8 補記守衛的實際執法邊界
- docs: 新增規則 9 環境事實的記錄形式
- docs: 校正 tickets 目錄以外的機器專屬絕對路徑殘留
- docs: 新增 PC-BAL-029 機器專屬絕對路徑記錄環境事實
- docs: 新增 IMP-BAL-009 非 UTF-8 檔案 grep 假陰性
- docs: skill.md severity 不變式加註適用範圍與存量遷移狀態
- docs: 修正 pm-quality-baseline 規則 7 驗證方式段落宣稱不存在的稽核能力
- chore: 測試檔改名對齊 hooks-test-gate 命名慣例
- chore: sync-push 回寫框架版本號

---

## [2.27.8] - 2026-08-10

### Summary
fix: 截斷 sync-push VERSION 回寫自反饋迴路（tarrragon/claude#66）; chore: sync-push 回寫框架版本號 （零實質變更鑄版問題見 tarrragon/claude#66）

Changes: 1 fix, 1 chore

- fix: 截斷 sync-push VERSION 回寫自反饋迴路（tarrragon/claude#66）
- chore: sync-push 回寫框架版本號 （零實質變更鑄版問題見 tarrragon/claude#66）

---

## [2.27.7] - 2026-08-10

### Summary
chore: sync-push 回寫框架版本號

Changes: 1 chore

- chore: sync-push 回寫框架版本號

---

## [2.27.6] - 2026-08-10

### Summary
fix: framework-issue scripts 統一接受三種 issue ref 形態; fix: skill-sync get_skills_dir 改以 git toplevel 解析消除 cwd 依賴; chore: sync-push 回寫框架版本號

Changes: 2 fix, 1 chore

- fix: framework-issue scripts 統一接受三種 issue ref 形態
- fix: skill-sync get_skills_dir 改以 git toplevel 解析消除 cwd 依賴
- chore: sync-push 回寫框架版本號

---

## [2.27.5] - 2026-08-10

### Summary
fix: skill 庫檢查輸出標示比對遠端 repo; chore: sync-push 回寫框架版本號

Changes: 1 fix, 1 chore

- fix: skill 庫檢查輸出標示比對遠端 repo
- chore: sync-push 回寫框架版本號

---

## [2.27.4] - 2026-08-10

### Summary
fix: canonical-schema hook WARNING 改走 additionalContext 注入 session context; docs: 新增 PC-BAL-028 差集稽核對無宣稱變更的結構性盲區; docs: 有副作用取捨的選擇題強制觸發 WRAP 規則條文 (+2 more)

Changes: 1 fix, 3 docs, 1 chore

- fix: canonical-schema hook WARNING 改走 additionalContext 注入 session context
- docs: 新增 PC-BAL-028 差集稽核對無宣稱變更的結構性盲區
- docs: 有副作用取捨的選擇題強制觸發 WRAP 規則條文
- docs: 新增驗收條件爭議兩條裁決判準
- chore: 回寫框架版本號 （sync-push 產出）

---

## [2.27.3] - 2026-08-10

### Summary
docs: 校準 language-constraints.md 非 MoE 標準字; chore: 回寫框架版本號 （sync-push 產出）

Changes: 1 docs, 1 chore

- docs: 校準 language-constraints.md 非 MoE 標準字
- chore: 回寫框架版本號 （sync-push 產出）

---

## [2.27.2] - 2026-08-10

### Summary
docs: 清理 rules 目錄 38 處 ticket ID 引用（規則 8 全禁原則階段 2 試點）; docs: 補記 error-pattern 與 skill-sync 的版本註腳; chore: .claude 同步至 （--clean 傳播兩筆刪除）

Changes: 2 docs, 1 chore

- docs: 清理 rules 目錄 38 處 ticket ID 引用（規則 8 全禁原則階段 2 試點）
- docs: 補記 error-pattern 與 skill-sync 的版本註腳
- chore: .claude 同步至 （--clean 傳播兩筆刪除）

---

## [2.27.1] - 2026-08-10

### Summary
chore: .claude 同步至

Changes: 1 chore

- chore: .claude 同步至

---

## [2.27.0] - 2026-08-10

### Summary
feat: 新增 error-patterns README 索引與目錄一致性檢查 Hook; feat: 抽取共用 skill.md 大小寫告警 helper 並接線四處; feat: skill-sync 對大小寫不符的 SKILL.md 輸出告警 (+12 more)

Changes: 3 feat, 4 fix, 4 docs, 3 chore, 1 test

- feat: 新增 error-patterns README 索引與目錄一致性檢查 Hook
- feat: 抽取共用 skill.md 大小寫告警 helper 並接線四處
- feat: skill-sync 對大小寫不符的 SKILL.md 輸出告警
- fix: 索引一致性 Hook 依凍結登記表分流 ID 碰撞誤報
- fix: skill-registration-check-hook 小寫偵測在 case-insensitive fs 上永不觸發
- fix: 更正 IMP-V1-006 對 pathlib.glob 大小寫行為的錯誤敘述
- fix: 本地重命名三個 skill 為大寫 SKILL.md 並同步活引用
- docs: 整併 IMP-026 至 IMP-054，PC-086 補姊妹模式交叉引用
- docs: ARCH-BAL-007 案例補後續更正，七組碰撞中 ARCH-010 實為孤兒重複
- docs: 新增 PC-BAL-027 稽核器缺政策輸入把已裁定設計報為缺陷
- docs: IMP-V1-006 補二次觸發擴充，涵蓋 case-sensitive 掃描器靜默漏樣本
- chore: 完成全庫孤兒重複稽核，spawn 清理 IMP-026/054/PC-086
- chore: 刪除 ARCH-010 孤兒重複檔並修正索引與凍結表
- chore: 框架同步至 ，驗收判定 acceptance 1 未達成轉 承接
- test: 兩份 skill.md 大小寫判準實作對照測試 + 文案更正

---

## [2.26.3] - 2026-08-09

### Summary
fix: skill 庫檢查拆分兩類盲區並補齊 5 個缺漏的 manifest 記錄; fix: 移除 layer-boundary-validator 的 effort=low 短路; chore: 框架 repo 同步至 （ticket 掃描修復與 hook 註冊清理）

Changes: 2 fix, 1 chore

- fix: skill 庫檢查拆分兩類盲區並補齊 5 個缺漏的 manifest 記錄
- fix: 移除 layer-boundary-validator 的 effort=low 短路
- chore: 框架 repo 同步至 （ticket 掃描修復與 hook 註冊清理）

---

## [2.26.2] - 2026-08-09

### Summary
fix: 移除 hook 重複註冊與被合併版並存; fix: ticket 掃描改依實際結果分派，修復九個 hook 恆掃到空; chore: 框架 repo 同步至 （本 session hook 變更）

Changes: 2 fix, 1 chore

- fix: 移除 hook 重複註冊與被合併版並存
- fix: ticket 掃描改依實際結果分派，修復九個 hook 恆掃到空
- chore: 框架 repo 同步至 （本 session hook 變更）

---

## [2.26.1] - 2026-08-09

### Summary
chore: 框架 repo 同步至 （傳播三個 dart skill 移除）

Changes: 1 chore

- chore: 框架 repo 同步至 （傳播三個 dart skill 移除）

---

## [2.26.0] - 2026-08-09

### Summary
refactor: 規則 8 守衛的兩份掃描邏輯統一為單一實作; fix: layer-boundary-validator 改用 lib 套件修復測試套件收集中斷; chore: 框架 repo 同步至 ，回填 至 spawned_tickets

Changes: 1 refactor, 1 fix, 1 chore

- refactor: 規則 8 守衛的兩份掃描邏輯統一為單一實作
- fix: layer-boundary-validator 改用 lib 套件修復測試套件收集中斷
- chore: 框架 repo 同步至 ，回填 至 spawned_tickets

---

## [2.25.0] - 2026-08-09

### Summary
feat: 規則 8 守衛升級為 exit 2 阻擋並加行內 marker 逃生閥; feat: skill 殘留偵測器與 session 警告加 push 硬擋雙層防護; feat: style_checker 專案校準設定化並讓 hook 共用同一份規則 (+15 more)

Changes: 4 feat, 2 refactor, 5 fix, 3 docs, 2 chore, 2 test

- feat: 規則 8 守衛升級為 exit 2 阻擋並加行內 marker 逃生閥
- feat: skill 殘留偵測器與 session 警告加 push 硬擋雙層防護
- feat: style_checker 專案校準設定化並讓 hook 共用同一份規則
- feat: skill-sync push 新增 --prune 刪除傳播
- refactor: 移除三個無工具且綁定他專案路徑的 dart skill
- refactor: skill 庫漂移檢查收斂為 skill-sync 的 public API
- fix: test-assertion-design 交叉引用改回 dart 前綴命名
- fix: 收斂本地與 canonical skill 庫的 16 項內容分歧
- fix: prune 排除範圍、cmd_push 測試覆蓋、pull/push 對稱化
- fix: 恢復 sync-push 的 skill 庫漂移自動檢查
- fix: 修復 3 個 skill 的 5 處失效連結並回推 canonical 庫
- docs: 記錄 PC-BAL-026 驗證管道經快取層讀取的滯後模式
- docs: 修正 skill-sync 文件與實際行為的四處脫節
- docs: 記錄多視角審查產出的兩個結構性錯誤模式
- chore: 從 canonical 庫同步 5 個過期 skill
- chore: 本地 VERSION 回寫至 2.24.15（sync-push 收尾）
- test: 補雙層防護 hook 的測試納入 hooks 測試 gate
- test: 補 dart-style-guardian-hook 測試納入 hooks 測試 gate

---

## [2.24.15] - 2026-08-07

### Summary
fix: 修復 broken-link-check 既存失效連結，broken 23 處歸零; chore: 本地 VERSION 回寫至 2.24.14（issue #62 群聚收尾）

Changes: 1 fix, 1 chore

- fix: 修復 broken-link-check 既存失效連結，broken 23 處歸零
- chore: 本地 VERSION 回寫至 2.24.14（issue #62 群聚收尾）

---

## [2.24.14] - 2026-08-07

### Summary
fix: write_local_version 回傳 OSError 細節供呼叫端警告; chore: 本地 VERSION 回寫至 2.24.13（write_local_version 首次 runtime 產物）

Changes: 1 fix, 1 chore

- fix: write_local_version 回傳 OSError 細節供呼叫端警告
- chore: 本地 VERSION 回寫至 2.24.13（write_local_version 首次 runtime 產物）

---

## [2.24.13] - 2026-08-07

### Summary
fix: sync-push 成功後回寫本地 .claude/VERSION

Changes: 1 fix

- fix: sync-push 成功後回寫本地 .claude/VERSION

---

## [2.24.12] - 2026-08-07

### Summary
docs: 記錄 PC-BAL-025 框架自我修改的授權鏈自我背書

Changes: 1 docs

- docs: 記錄 PC-BAL-025 框架自我修改的授權鏈自我背書

---

## [2.24.11] - 2026-08-07

### Summary
fix: 移除 ticket_quality 產出內容中的 emoji 字面

Changes: 1 fix

- fix: 移除 ticket_quality 產出內容中的 emoji 字面

---

## [2.24.10] - 2026-08-06

### Summary
fix: 修復 why 欄位跨行冒號誤判巢狀 dict 的資料遺失; fix: 修復 where.files 型別假設死碼（error-pattern/doc-only）

Changes: 2 fix

- fix: 修復 why 欄位跨行冒號誤判巢狀 dict 的資料遺失
- fix: 修復 where.files 型別假設死碼（error-pattern/doc-only）

---

## [2.24.9] - 2026-08-06

### Summary
fix: 移除 ticket-quality-gate 註冊並刪除已無效 hook; fix: 移植 C1/C3 判準至 acceptance_checkers 並實測誤判率

Changes: 2 fix

- fix: 移除 ticket-quality-gate 註冊並刪除已無效 hook
- fix: 移植 C1/C3 判準至 acceptance_checkers 並實測誤判率

---

## [2.24.8] - 2026-08-06

### Summary
fix: PM 補修 .1 漏抓的 skills 深層路徑 11 處 dependency_ref; fix: 補正 30 處第 1 類論證依據型 ticket ID 引用; fix: 複核 error-patterns/pm-rules/methodologies/rules/scripts/lib 36 行引用，修正 6 行 (+4 more)

Changes: 7 fix

- fix: PM 補修 .1 漏抓的 skills 深層路徑 11 處 dependency_ref
- fix: 補正 30 處第 1 類論證依據型 ticket ID 引用
- fix: 複核 error-patterns/pm-rules/methodologies/rules/scripts/lib 36 行引用，修正 6 行
- fix: 複核 references/hooks 44 行引用，移除 19 行 ticket ID
- fix: 複核 skills 目錄 ticket ID 引用並按五類分類修正
- fix: 規則 8 守衛改全禁偵測 + 逐檔淨增量存量凍結
- fix: agent-ticket-validation-hook 補 filelock 依賴並改 noisy fallback

---

## [2.24.7] - 2026-08-06

### Summary
fix: 修復 hook 權限自動修正的掃描軸過寬與 auto-commit 永不觸發; fix: 第三輪 Phase 4 品質修復（規則 8/Action 句/不變式/事實）; fix: 三個 handoff hook PEP 723 補 filelock，修復 PC-135 復發 (+11 more)

Changes: 8 fix, 4 docs, 2 chore

- fix: 修復 hook 權限自動修正的掃描軸過寬與 auto-commit 永不觸發
- fix: 第三輪 Phase 4 品質修復（規則 8/Action 句/不變式/事實）
- fix: 三個 handoff hook PEP 723 補 filelock，修復 PC-135 復發
- fix: 三個 handoff hook 顯示/排序/判定路徑改以 target 為對象
- fix: 第三輪修復 Phase 4 審查發現（SSOT 合併/靜默 fallback/註解）
- fix: resume.py 三處消費者改用 resolve_target 統一對象解析
- fix: 統一 handoff JSON 消費者對象解析為 target/source 判準
- fix: 修復 handoff 同步檢查的段落界定失效與交接語意錯置
- docs: 誤差預算原則上移至框架規則層 quality-baseline
- docs: 記錄 PC-BAL-024 規則收緊而守衛判準過期
- docs: 記錄 ARCH-BAL-014 上游過濾修復擴大下游暴露面
- docs: 依 Layer 2 審查修正 PC-BAL-023 兩處實質缺陷
- chore: test_dispatch_record_hook.py 補上執行權限
- chore: 完成框架 issue 歸屬盤點並補 PC-BAL-023

---

## [2.24.6] - 2026-08-05

### Summary
sync .claude configuration

---

## [2.24.5] - 2026-08-05

### Summary
fix: sync-push --clean 不再被 no-change early-exit 攔下

Changes: 1 fix

- fix: sync-push --clean 不再被 no-change early-exit 攔下

---

## [2.24.4] - 2026-08-05

### Summary
sync .claude configuration

---

## [2.24.3] - 2026-08-05

### Summary
fix: 遷移派發身份綁定至 PostToolUse 修復混合批次自我阻塞; test: 補 dispatch-record-hook.py 依命名慣例對應測試檔

Changes: 1 fix, 1 test

- fix: 遷移派發身份綁定至 PostToolUse 修復混合批次自我阻塞
- test: 補 dispatch-record-hook.py 依命名慣例對應測試檔

---

## [2.24.2] - 2026-08-05

### Summary
docs: 互鏈 PC-BAL-008 與 PC-SCLK-005 跨 consumer 姊妹模式; chore: pull .claude 更新（上游 2c488f543ddf，）

Changes: 1 docs, 1 chore

- docs: 互鏈 PC-BAL-008 與 PC-SCLK-005 跨 consumer 姊妹模式
- chore: pull .claude 更新（上游 2c488f543ddf，）

---

## [2.24.1] - 2026-08-05

### Summary
feat(screen_clock): 回推 11 個 SCLK error-pattern 與三項框架層修復

error-pattern（consumer screen_clock 於 v1.4.0 捕獲，上游先前無 SCLK 條目）：
- PC-SCLK-001~008：並行 agent amend 改寫他人 commit／編碼混淆繞過 sandbox／
  task context 指定解法形態／推測性歸因污染後續票／共享 index commit 夾帶
  他人 staged 檔／規格散文與形式定義相反／hook 讀錯 payload 欄位靜默失效／
  PM 分析措辭被照抄成事實
- IMP-SCLK-001：macOS bash 3.2 在 UTF-8 locale 下裸 $VAR 緊鄰全形標點
- CQ-SCLK-001：宣稱的保證無測試訊號
- TEST-SCLK-001：快取建置使不存在斷言空洞

程式碼修復：
- hooks/hook-completeness-check.py：新增 extract_merge_declarations()，解析
  hook docstring 的合併宣告，偵測已合併卻仍與合併版共同註冊的 hook
  （screen_clock 1.4.0-W2-029 實證：三個 hook 每次 commit 重複執行）
- skills/doc/doc_system/commands/validate.py + tests：修 _fixed_name_exemptions
  對無對應模板之固定命名文件的推導盲區（1.4.0-W1-013）

框架知識：
- references/agent-dispatch-decision.md：新增 isolation:worktree 派發的
  complete 收尾限制專節，含逐字阻擋原文與探針證據（1.4.0-W1-023）

---

## [2.24.0] - 2026-08-05

### Summary
feat: framework-issue fix-version 註記與 close 命令; feat: framework-issue create 環境資訊自動收集; docs: PC-BAL-008 增補檔案級共用跨票吸收變體 (+1 more)

Changes: 2 feat, 2 docs

- feat: framework-issue fix-version 註記與 close 命令
- feat: framework-issue create 環境資訊自動收集
- docs: PC-BAL-008 增補檔案級共用跨票吸收變體
- docs: 建立框架問題升級與 issue 生命週期正規化流程文件

---

## [2.23.1] - 2026-08-05

### Summary
chore: 傳播 9 個已刪除檔案的刪除，清理遠端孤兒

包含 ticket-skill-sync-check 系列（已改名為 skill-cli-sync-check，繼任者
已在位）、memory upgrade 相關腳本與測試、hook-registry.json、
phase-contract-validator-hook。避免 full overlay sync 將死檔複製回下游。

---

## [2.23.0] - 2026-08-05

### Summary
feat: agent-commit-verification-hook 逐 worktree 檢查未落地產品碼; feat: 實作 bare-commit-guard 並行期裸 commit 防線; feat: 保障 worktree 內 ticket create 產出的追蹤與清理防護 (+96 more)

Changes: 14 feat, 8 refactor, 34 fix, 38 docs, 4 chore, 1 perf

- feat: agent-commit-verification-hook 逐 worktree 檢查未落地產品碼
- feat: 實作 bare-commit-guard 並行期裸 commit 防線
- feat: 保障 worktree 內 ticket create 產出的追蹤與清理防護
- feat: dispatch_mode readonly 豁免路徑（fallback 版）
- feat: 增設 complete 別名 finish 避開 CC worktree guard 誤判
- feat: 實作 spawn request 狀態標記 CLI 子命令
- feat: dispatch-readiness 新增 acceptance 與寫入集一致性檢查
- feat: 泛化 skill CLI 文件同步防護 hook 至七個 skill
- feat: WAVE_WRAP_UP_REMINDER 觸發端實查 Wave pending 數
- feat: 新增雙軌皆空但 session 有交接訊號的 Stop hook 偵測第 7 格
- feat: 封閉 NotebookEdit memory 寫入路徑並誠實化 Bash 缺口
- feat: 新增 hooks 變更目標式測試 gate
- feat: SKILLS 清單漂移偵測落在 SessionStart
- feat: agent-dispatch-template 交付通道補派發形態維度
- refactor: 收斂 4 份 worktree/porcelain 重複實作至 lib.git_utils
- refactor: Guard 表驅動 + worktree 回傳型別具名化
- refactor: 收斂 git worktree/porcelain 重複解析至 git_utils 共用層
- refactor: 刪除 phase-contract-validator-hook 死碼及其測試與豁免條目
- refactor: 抽取 memory 路徑與分流訊息的單一真相來源
- refactor: memory 稽核改 SessionStart 加 Stop 事件式偵測
- refactor: memory 稽核 layout 表格化與 docstring 敘事收斂
- refactor: 移除 memory 升級工作流的程式碼層殘留
- fix: 修正 worktree hook 訊息的互斥指示與 Guard 代號撞號
- fix: 共用 git runner 改為只 rstrip 換行，保留 porcelain 首行前導空白
- fix: 修正 worktree hook 阻擋訊息的裸 cd 與無 pathspec commit 建議
- fix: 補上 worktree 清理路徑對已追蹤檔未提交修改的遺失防護
- fix: readme_index 略過原子配號的 reserved 佔位檔
- fix: 修復 worktree skill 測試套件 collection error 與 patch target 漂移
- fix: 封閉 error-pattern allocator 兩面配號競爭
- fix: dashboard Ready 判定加入 children 未完成過濾
- fix: worktree-commit-before-dispatch 阻擋訊息改用「主 repo」取代歧義的 main
- fix: set-acceptance 補上 auto-commit 消除 worktree 靜默遺失風險
- fix: _auto_commit_ticket_md commit 訊息不再誤標 append-log
- fix: Context Bundle 冪等判定改為 content-aware 使 claim 時重抽生效
- fix: worktree 派發跳過主 repo 端搶先身份綁定，消除雙寫洩漏
- fix: runqueue list 視圖不再硬編 blockedBy=[] 後綴
- fix: 收斂 complete auto-stage 排除 siblings 與 children 路徑
- fix: 補 hook 與測試檔的執行權限
- fix: 移除 hook-completeness-check.py 對已刪除 hook-registry.json 的 docstring 引用
- fix: 修正 skill-shadowing-check-hook docstring 優先序方向與過時數量
- fix: 校準 path_permission 白名單與拒絕訊息清單，改為機制綁定
- fix: WAVE_WRAP_UP_REMINDER 移除偽裝偵測結果的靜態文案
- fix: handoff --from-worklog 掃描範圍限縮至交接段落
- fix: worktree 內測試 fixture 隔離逃生艙，消除假紅燈污染
- fix: 修復 dashboard 的 handoff target 呈現與 key 語意錯位
- fix: 修復 worklog 交接段偵測與本專案書寫慣例失配
- fix: get_current_version_from_todolist 改解析 status=active
- fix: AUDIT_MESSAGE 首句改陳述能力事實、Action 改可執行指令
- fix: 依 shell 語意分流處理跳脫引號，消除配對錯位繞過
- fix: 重寫字面區段掃描為單趟狀態機，消除 DENY 繞過
- fix: 消除 bash-edit-guard 模式 A 對字面命中的誤報
- fix: 修復 memory 稽核目錄定位失效並補可攜測試
- fix: 收斂 hooks-test-gate 的字面提及誤觸發路徑
- fix: 修復 uv-tool-ownership-guard 測試過期成員清單
- fix: 場景 16 提醒改為捕獲時分流，移除 memory 雙通道殘留
- fix: 校準 uv-tool-ownership-guard 的 SKILLS 清單
- docs: 修正 EXCLUDED_PATH_PREFIXES 排除理由表述
- docs: 對齊 AGENT_PRELOAD 規則 12 Version footer 表述至規則 8 現行判準
- docs: 補 writing-code-comments 原則二框架檔案路由註
- docs: 載明唯讀派發豁免 worktree 強制的聲明方式與適用判準
- docs: 載明 worktree 派發的非 git 狀態前置需求機制
- docs: error-pattern SKILL 步驟 7 改接原子配號入口
- docs: 修訂 bash-tool-usage 規則三，index.lock 競爭因果改為 lock 本身而非串接
- docs: 規則 8 新增實證錨點型類別，commit hash 條件允許
- docs: 收斂 SHA 擷取為 commit 同一次呼叫內完成
- docs: PC-BAL-008 預防措施改 SHA 錨定驗證
- docs: 補寫系統模型章節的 type 與 instance 一對多條款
- docs: path-limited commit 補新增檔案的 git add 前置條款
- docs: PC-BAL-008 補實證二與工具層修法
- docs: 補強並行 commit 防護條款納入 path-limited commit
- docs: 修正 ARCH-001-config-code-mixing 內文風險等級由高改為中
- docs: 修訂 language-constraints 規則 5 對齊實際防護機制
- docs: 補齊規則 8 適用範圍表與守衛掃描範圍的落差
- docs: 消除二元處置取捨條款在四份框架文件間的 substance 重複
- docs: 規則 8 改寫為全禁原則加五類分類
- docs: 校正 parallel-dispatch.md 檔尾三個 Last Updated 並存
- docs: idle agent 回收 SOP 補檔案佔用前提與通知語意
- docs: 關閉 並擴充 PC-BAL-022（同一 pattern 發生在派發者身上）
- docs: 記 PC-BAL-022（因果核對取代 baseline 對照）
- docs: PC-BAL-020 併入例四並補 PC-BAL-004 邊界
- docs: 記 PC-BAL-021 並建兩張後續追蹤票
- docs: Round 3 三項承重論點修正，skill 升 2.0.0
- docs: Round 2 兩項嚴重與摘要行一組
- docs: Round 1 兩項嚴重必修
- docs: DOC-BAL-002 補入否定式保證的加重形態
- docs: 新增 DOC-BAL-002 契約漂移錯誤模式
- docs: 判定三例回報偏差並落地為兩份 error-pattern
- docs: 記 ARCH-BAL-011 主題式命名造成的覆蓋假象
- docs: 記 DOC-BAL-001 規則缺 Consequence 層退化為偏好
- docs: 套用第二位審查員的獨立 finding
- docs: 套用 Layer 2 審查的 1 Critical 與 12 Warning
- docs: 記 ARCH-BAL-010 並補既有兩則模式的實證與症狀變體
- docs: 記 PC-BAL-019 並追蹤場景 16 提醒的 memory 殘留
- docs: 判定經審查推翻後重寫，記 PC-BAL-018
- chore: Phase 4 審查落地——2 個 error-pattern + 6 張衍生票 bookkeeping
- chore: 補 test_bare_commit_guard_hook.py 執行權限
- chore: metadata sync post-completion
- chore: 補提交測試檔的執行權限位
- perf: get_project_root 加程序內快取消除重複 git subprocess

---

## [2.22.2] - 2026-07-30

### Summary
feat: sync 守衛與工具修復三輪 + wrap-decision 2.8.0

守衛（跨專案保護分支）三個獨立繞道封閉：
- 完全未掛 Bash matcher，Bash git commit 可直接寫外部 repo 保護分支
- 讀當下 staged 而非推導本次命令會 stage 什麼，add && commit 串接可繞過
- -C 目標含 shell 展開語法時解析失敗即 fail-open

同步工具兩項 fail-open 修復：
- sync-pull --audit 增讀 base sha，正向孤兒分為將被刪除與將保留兩組
- sync-push 無 base 帶 --clean 時中止（三方保護依賴 base_files 非空）

wrap-decision 2.8.0：移植 blog 分支獨有演化（觸發條件兩項、快速+模式
定義、claim-quick-wrap orphan 修復、基礎設施累積型絆腳索）。

新增 error-pattern PC-BAL-015 / PC-BAL-016。

---

## [2.22.1] - 2026-07-29

### Summary
fix: clean 豁免清單依比對維度拆集合; docs: 收尾 並記錄 clean 豁免比對維度錯置

Changes: 1 fix, 1 docs

- fix: clean 豁免清單依比對維度拆集合
- docs: 收尾 並記錄 clean 豁免比對維度錯置

---

## [2.22.0] - 2026-07-29

### Summary
feat: 移除 personal 遮蔽副本並訂定全域覆蓋層正規流程; refactor: 刪除 wrap-decision 孤兒目錄 integration-patterns; fix: 移除 sync-claude-push 已隨 schema 變更失效的漂移檢查 (+9 more)

Changes: 1 feat, 1 refactor, 5 fix, 4 docs, 1 chore

- feat: 移除 personal 遮蔽副本並訂定全域覆蓋層正規流程
- refactor: 刪除 wrap-decision 孤兒目錄 integration-patterns
- fix: 移除 sync-claude-push 已隨 schema 變更失效的漂移檢查
- fix: 改用內容雜湊取代 skill-sync 的版本字串比對
- fix: 修正 error-pattern severity frontmatter/內文分歧
- fix: 遷移 README 7 筆模糊碰撞列一級資料至精確列後移除
- fix: readme_index 支援一 ID 對多檔複合鍵，補列 7 個隱形 pattern
- docs: 記錄 PC-BAL-014 skill 註冊表 session 快取遮蔽檔案系統變更
- docs: personal 覆蓋層的收斂方向與已發生損害
- docs: 校正三項幽靈重編陳述與碰撞登記表脫節
- docs: 記錄 ARCH-BAL-007 非唯一識別符被當主鍵
- chore: 補上 test_error_pattern_severity_audit.py 執行權限

---

## [2.21.1] - 2026-07-27

### Summary
sync .claude configuration

---

## [2.21.0] - 2026-07-27

### Summary
feat: error-pattern README 索引改保守 upsert 並接線; feat: error-pattern README 索引全量 sync 純函式層 + CLI; feat: memory 寫入攔截改為 PreToolUse deny 加改道指引 (+49 more)

Changes: 9 feat, 11 fix, 28 docs, 2 chore, 2 test

- feat: error-pattern README 索引改保守 upsert 並接線
- feat: error-pattern README 索引全量 sync 純函式層 + CLI
- feat: memory 寫入攔截改為 PreToolUse deny 加改道指引
- feat: 刪除 test-timeout-post.py 死碼 + config 白名單納入
- feat: 規則 8 守衛實作依賴型 vs 歷史錨點型判別
- feat: WRAP 觸發綁定至二元處置取捨
- feat: version-tracking-consistency-guard-hook 新增 todolist.yaml 解析失敗偵測
- feat: 新增 doc validate-filenames 檔名慣例驗證
- feat: 擴充 TICKET_EXEMPT_AGENT_TYPES 收錄唯讀常駐審查委員
- fix: skill-shadowing hook 修復 N1 context 送達與 H1/N5 目錄層級靜默失效
- fix: skill-shadowing hook 修正 L1 大小寫偵測與 L3 版本正則
- fix: skill-shadowing hook 改遞迴比對整個目錄
- fix: 修復 wrap-decision/zellij 全域 skill 遮蔽專案版
- fix: 修正 ask_user_question_reminders.py 六處失效路徑引用
- fix: 降級 ticket-quality-gate 失敗出口為 advisory
- fix: 移除 8 個事實判斷型 hook 的 effort=low 短路 + 同步固化測試
- fix: acceptance-gate 誤判 create 命令引號文字為 complete 呼叫致死鎖
- fix: acceptance-gate-hook effort=low 短路不再豁免 complete 命令
- fix: PEP 723 依賴宣告取代 version-tracking hook 的 python3 探測
- fix: validate-filenames 豁免框架約定固定命名文件
- docs: PC-BAL-013 更正 team 訊息路由的事實陳述
- docs: PC-BAL-013 context 中斷誤判為代理人終止
- docs: error-patterns README 的 memory 定位改為排除論述
- docs: 補齊 error-patterns README 索引 148 筆缺漏
- docs: 修正規則 12 依賴型判準的字面矛盾
- docs: AGENT_PRELOAD 規則 12 自我稽核，發現規則本身的字面矛盾
- docs: 多階段分支流落地，memory 目錄清空
- docs: PC-061 / PC-160 防護章改寫指向現行攔截機制
- docs: 清理 error-patterns 內指向不存在 memory 檔的引用
- docs: memory 五檔處置 4/5，餘一檔阻塞於落地位置設計
- docs: 框架檔案禁依賴型 ticket 引用禁令上移至預設載入層
- docs: 移除 memory-capture-guide 與死指標，記錄 PC-BAL-012
- docs: 改寫四處剩餘 memory 目的地表述
- docs: 改寫規則層分流表述為 memory 排除 policy
- docs: PC-160 補 v3 案例——框架落地已在飛行仍寫 memory
- docs: 新增 ARCH-BAL-006 宣告層窄於執行層
- docs: PC-BAL-002 補案例二與比對維度分流
- docs: 新增 PC-BAL-011 + 修正 Layer 2 發現 1
- docs: Recommended 標記適用邊界對稱補述
- docs: IMP-BAL-001 適用範圍擴充至 PostToolUse
- docs: 新增 ARCH-BAL-005 自證式豁免 error-pattern
- docs: 新增 PC-BAL-010 驗證管道對待驗現象不敏感（家族層）
- docs: 新增 PC-BAL-009 測試套件顏色隨 cwd 翻轉
- docs: 新增 ARCH-BAL-004 + spawn
- docs: 修文件範例源頭 + 記錄 診斷修正
- docs: 修正 AGENT_PRELOAD claim 前提衝突 + PC-V1-002 第三變體固化
- docs: 新增 ARCH-BAL-003 白名單判準與成員脫節
- docs: 新增 IMP-BAL-003 稽核器與消費端解析器嚴格度落差
- chore: test_version_tracking_consistency_guard_hook_yaml_parse.py 權限 644 -> 755
- chore: 清除 hook-exclude-list 五個殭屍條目與失效 archived 模式
- test: hook 測試 cwd 無關化 + 防 fixture 殘留污染 repo
- test: 修復 hook 測試三紅燈 + 一無鑑別力測試（測試側）

---

## [2.20.16] - 2026-07-26

### Summary
fix: set-exit-status 冪等取代語意; docs: 完成收尾 + PC-BAL-008 並行 index 危害 + spawn; docs: 記錄 ARCH-BAL-002 識別符雙載體工具只讀一側（book 實證）

Changes: 1 fix, 2 docs

- fix: set-exit-status 冪等取代語意
- docs: 完成收尾 + PC-BAL-008 並行 index 危害 + spawn
- docs: 記錄 ARCH-BAL-002 識別符雙載體工具只讀一側（book 實證）

---

## [2.20.15] - 2026-07-26

### Summary
fix: 框架簡體字清理

Changes: 1 fix

- fix: 框架簡體字清理

---

## [2.20.14] - 2026-07-26

### Summary
docs: 記錄 TEST-BAL-002 測試替身建構路徑分歧（monitor 實證）

Changes: 1 docs

- docs: 記錄 TEST-BAL-002 測試替身建構路徑分歧（monitor 實證）

---

## [2.20.13] - 2026-07-26

### Summary
fix: doc validate 子命令; fix: doc skill 既有測試紅燈修復; docs: 分冊判準 + domain 清單去專案化

Changes: 2 fix, 1 docs

- fix: doc validate 子命令
- fix: doc skill 既有測試紅燈修復
- docs: 分冊判準 + domain 清單去專案化

---

## [2.20.12] - 2026-07-26

### Summary
fix: TRACEABILITY_SCHEMA 三軸補齊; docs: methodology dormant 豁免 + traceability 判準成文; docs: PC-APP-012 防護收編 canonical

Changes: 1 fix, 2 docs

- fix: TRACEABILITY_SCHEMA 三軸補齊
- docs: methodology dormant 豁免 + traceability 判準成文
- docs: PC-APP-012 防護收編 canonical

---

## [2.20.11] - 2026-07-26

### Summary
fix: doc CLI data-contract 接線 + next-id; docs: spec data-contract 防誤用 + 維度 4 降級; docs: PC-BAL-007 實查約束落地

Changes: 1 fix, 2 docs

- fix: doc CLI data-contract 接線 + next-id
- docs: spec data-contract 防誤用 + 維度 4 降級
- docs: PC-BAL-007 實查約束落地

---

## [2.20.10] - 2026-07-25

### Summary
docs: 記錄 PC-BAL-007 並行文件票未交叉驗證的事實漂移（/006 實證）

Changes: 1 docs

- docs: 記錄 PC-BAL-007 並行文件票未交叉驗證的事實漂移（/006 實證）

---

## [2.20.9] - 2026-07-25

### Summary
docs: 記錄 PC-BAL-006 chpwd ls 淹沒被誤診為 CLI 故障（ 驗收重現實證）

Changes: 1 docs

- docs: 記錄 PC-BAL-006 chpwd ls 淹沒被誤診為 CLI 故障（ 驗收重現實證）

---

## [2.20.8] - 2026-07-25

### Summary
docs: 記錄 IMP-BAL-002 sync-pull 未知參數推進 base SHA 缺陷（framework issue #18）

Changes: 1 docs

- docs: 記錄 IMP-BAL-002 sync-pull 未知參數推進 base SHA 缺陷（framework issue #18）

---

## [2.20.7] - 2026-07-25

### Summary
docs: 記錄 IMP-BAL-001 PreToolUse 提前 emit stdout 被 exit 2 丟棄模式

Changes: 1 docs

- docs: 記錄 IMP-BAL-001 PreToolUse 提前 emit stdout 被 exit 2 丟棄模式

---

## [2.20.6] - 2026-07-25

### Summary
fix: lag 警告延後 emit 至 PC-019 判定後，四路徑零丟失

Changes: 1 fix

- fix: lag 警告延後 emit 至 PC-019 判定後，四路徑零丟失

---

## [2.20.5] - 2026-07-25

### Summary
sync .claude configuration

---

## [2.20.4] - 2026-07-25

### Summary
fix: 警告升 additionalContext + lag 超閾值 deny; docs: version-bootstrap Step 2.6 資料契約產出 + domain-map §3 契約引用連結欄; docs: 建立 data-contract-template 模板 + doc SKILL.md 註冊 (+2 more)

Changes: 1 fix, 4 docs

- fix: 警告升 additionalContext + lag 超閾值 deny
- docs: version-bootstrap Step 2.6 資料契約產出 + domain-map §3 契約引用連結欄
- docs: 建立 data-contract-template 模板 + doc SKILL.md 註冊
- docs: 建立 data-layer-contract-methodology 方法論 + 索引註冊
- docs: domain-map 補標實作狀態欄 + 修正目標路徑

---

## [2.20.3] - 2026-07-24

### Summary
fix: doc skill + saffron agent 加 domain-map bundle 存在性驗證（PC-APP-012 防護）

Changes: 1 fix

- fix: doc skill + saffron agent 加 domain-map bundle 存在性驗證（PC-APP-012 防護）

---

## [2.20.2] - 2026-07-24

### Summary
docs: domain-map 模板和 9 個既有 map 補標 bundle 實作狀態欄; docs: PC-APP-012 domain-map 未實作 bundle 衍生不可執行 ticket; chore: pull .claude 更新（上游 e41fd80）

Changes: 2 docs, 1 chore

- docs: domain-map 模板和 9 個既有 map 補標 bundle 實作狀態欄
- docs: PC-APP-012 domain-map 未實作 bundle 衍生不可執行 ticket
- chore: pull .claude 更新（上游 e41fd80）

---

## [2.20.1] - 2026-07-23

### Summary
chore: skill 庫雙向同步 + 新增 neurodivergent-output skill

Changes: 1 chore

- chore: skill 庫雙向同步 + 新增 neurodivergent-output skill

---

## [2.20.0] - 2026-07-23

### Summary
feat: domain-layer import 方向 lint hook; feat: /spec validate domain 覆蓋閘門 + 收掛; feat: 測試規劃消費 domain-map 不變式（兩軸測試設計） (+15 more)

Changes: 5 feat, 2 refactor, 4 fix, 4 docs, 3 chore

- feat: domain-layer import 方向 lint hook
- feat: /spec validate domain 覆蓋閘門 + 收掛
- feat: 測試規劃消費 domain-map 不變式（兩軸測試設計）
- feat: version-bootstrap Step 2.5 Domain 規劃 + doc saas 調和
- feat: domain-map-template.md + doc skill 五種文件類型註冊
- refactor: 中立化 framework 判準本體的專屬 domain 不變式
- refactor: domain-map-template 去除專案專屬細節提升可重用性
- fix: 校準 observability-rules AppLogger → developer.log
- fix: phase4-hook M1 regex 不再誤傷標準章節名
- fix: multi-round Round 3 修正 + spawn 延伸票
- fix: multi-round Round 2 修正（含 gate 假通過致命 bug）
- docs: 接線 domain map outbound 反向引用
- docs: TEST-BAL-001 理想化 fixture 遮蔽 validator 假通過
- docs: domain-bundle-mapping 方法論
- docs: PC-BAL-005 phase4-hook 觸發詞誤傷標準章節名
- chore: extend domain-bundle-mapping for multi-aggregate + command-side
- chore: ARCH-BAL-001 Layer 2 潤飾（定語堆疊拆句）
- chore: domain map 定案 + 四視角審查 + ARCH-BAL-001 + 防護票

---

## [2.19.4] - 2026-07-21

### Summary
chore: pull .claude 更新（上游 5ec670b）

Changes: 1 chore

- chore: pull .claude 更新（上游 5ec670b）

---

## [2.19.3] - 2026-07-21

### Summary
chore: pull .claude 更新（上游 680073cf）

Changes: 1 chore

- chore: pull .claude 更新（上游 680073cf）

---

## [2.19.2] - 2026-07-20

### Summary
feat: depends_on schema 宣告與 version-bootstrap 權威來源修正

---

## [2.19.1] - 2026-07-20

### Summary
feat: doc CLI 模板打包修復、CLI 子欄位寫入路徑、schema 一致性檢查與派發 context 品質規範

---

## [2.19.0] - 2026-07-20

### Summary
feat: 建立 schema 清單一致性檢查與驗證器過期判斷規則; feat: 移植 envelope 抑制邏輯至 cli-error-feedback-hook; feat: 註冊 pre-test-scan hook，刪除 superseded checkpoint hook (+5 more)

Changes: 3 feat, 2 fix, 2 docs, 1 chore

- feat: 建立 schema 清單一致性檢查與驗證器過期判斷規則
- feat: 移植 envelope 抑制邏輯至 cli-error-feedback-hook
- feat: 註冊 pre-test-scan hook，刪除 superseded checkpoint hook
- fix: 補列三份 _SCHEMA_SECTION_NAMES 的 Spawn Requests 成員
- fix: 改用真實檔案取代失效 mock，4 項紅燈轉綠
- docs: 記錄越層建票模式並新增載體選擇閘門
- docs: 記錄合併遺漏子功能但檔頭宣稱完整的錯誤模式
- chore: 從 skill 庫拉取 compositional-writing →

---

## [2.18.3] - 2026-07-20

### Summary
docs: 新增 error-pattern 專案代號 BAL 與 PC-BAL-001（驗證端清單過期誤判 canonical 結構）

---

## [2.18.2] - 2026-07-20

### Summary
sync .claude configuration

---

## [2.18.1] - 2026-07-20

### Summary
fix: 新增靜默佔位偵測到 version-release 佔位掃描器; fix: 修復 version-release 下一版本候選掃描窗口越界誤傷 tech_debt; fix: 修復 version-release 安裝版 CLI 跨 skill import 斷裂 (+3 more)

Changes: 4 fix, 2 chore

- fix: 新增靜默佔位偵測到 version-release 佔位掃描器
- fix: 修復 version-release 下一版本候選掃描窗口越界誤傷 tech_debt
- fix: 修復 version-release 安裝版 CLI 跨 skill import 斷裂
- fix: skill-sync push 排除清單補 hook-logs 目錄
- chore: ux-interaction-feedback 升級替換為 ux-design-evaluation（skill-sync pull）
- chore: skill-sync pull compositional-writing + multi-round-review 1.10.1

---

## [2.18.0] - 2026-07-17

### Summary
feat: complete 阻擋訊息加入 type-aware 內容引導 note; feat: create placeholder 依 ticket type 差異化引導文字; fix: spec_reference_checker 改讀兩份 SPEC 登錄簿聯集

Changes: 2 feat, 1 fix

- feat: complete 阻擋訊息加入 type-aware 內容引導 note
- feat: create placeholder 依 ticket type 差異化引導文字
- fix: spec_reference_checker 改讀兩份 SPEC 登錄簿聯集

---

## [2.17.0] - 2026-07-15

### Summary
feat: complete cascade 新增 blockedBy 反向掃描解鎖機制; feat: Phase 4 審查證據 WARNING hook + 規則 2 覆蓋修正; feat: 實作 doc uc acceptance-check CLI + dispatch-validate 規則 5 (+18 more)

Changes: 8 feat, 5 fix, 5 docs, 3 chore

- feat: complete cascade 新增 blockedBy 反向掃描解鎖機制
- feat: Phase 4 審查證據 WARNING hook + 規則 2 覆蓋修正
- feat: 實作 doc uc acceptance-check CLI + dispatch-validate 規則 5
- feat: 實作 UC fingerprint 漂移偵測 CLI + PostToolUse hook
- feat: context_bundle_extractor UC 自動注入
- feat: uc CLI trace 截斷分組 + 錯誤訊息 actionable + except 觀測性
- feat: 實作 uc-reference-validation-hook.py（PreToolUse UC 引用驗證，WARNING-only）
- feat: 實作 doc skill uc list/verify/trace/context 子命令群組
- fix: get_uc_summary 非標準 UC 結構容錯
- fix: test_stop_hook 5 測試 project_root 隔離修復
- fix: UC 掃描 token 變體/豁免路徑/常數治理 hardening
- fix: uc hook 補 MultiEdit 提取分支 + settings 註冊
- fix: uc verify 壞路徑/空白名單 fail-fast exit 2
- docs: quality-baseline 規則 2 補充非 TDD 流程覆蓋
- docs: UC 規範實作對齊 + 框架碼 ticket ID 抽象化
- docs: 平行審查 UC 治理交付——建 ~072 + IMP-APP-005
- docs: 補完 doc SKILL.md frontmatter uc 能力宣告
- docs: 新增 PC-APP-011 驗收 pattern 盲區 + IMP-APP-004 pipeline exit 假守衛
- chore: pre-dispatch — ticket 分析 + hook 權限修正
- chore: redirect 派發反模式禁令文件化
- chore: 為 install-skill-clis.py 補執行位元

---

## [2.16.0] - 2026-07-14

### Summary
feat: ux-interaction-feedback Skill 補畫面級回饋 + spinner/skeleton 判準 + 去專案化; feat: 新增 ux-interaction-feedback Skill（三層回饋模型 + 按鈕狀態 + 時間門檻）; feat: version-release check 新增佔位掃描（WARNING only） (+5 more)

Changes: 3 feat, 1 fix, 3 docs, 1 chore

- feat: ux-interaction-feedback Skill 補畫面級回饋 + spinner/skeleton 判準 + 去專案化
- feat: 新增 ux-interaction-feedback Skill（三層回饋模型 + 按鈕狀態 + 時間門檻）
- feat: version-release check 新增佔位掃描（WARNING only）
- fix: ux-interaction-feedback Skill 三輪審查修法（9 finding）
- docs: 新增 PC-APP-010 code 杜撰 UC- 前綴偽需求 ID
- docs: DI 架構規格化 + 可觀測性規則 5 落地
- docs: 發版前實機冒煙驗證清單三層結構
- chore: manifest APP 對照對帳完成 + PC-APP-009 錯誤模式記錄

---

## [2.15.1] - 2026-07-11

### Summary
chore: 傳播 5 個 dart-prefixed skill 遷移的刪除（清理 17 個遠端孤兒）

---

## [2.15.0] - 2026-07-11

### Summary
feat: spawn_request_checker 區分三種未處理成因的診斷訊息; feat: 遷移 security-review 為 dart-security-review; feat: 遷移 style-guardian 為 dart-style-guardian（含 hook 配置同步） (+32 more)

Changes: 5 feat, 4 refactor, 6 fix, 15 docs, 5 chore

- feat: spawn_request_checker 區分三種未處理成因的診斷訊息
- feat: 遷移 security-review 為 dart-security-review
- feat: 遷移 style-guardian 為 dart-style-guardian（含 hook 配置同步）
- feat: style-guardian 新增原生元件直用偵測規則（WARNING 模式）
- feat: 掃描器新增範例佔位偵測與歷史封存排除
- refactor: 遷移 i18n-checker 為 dart-i18n-checker
- refactor: 遷移 test-async-guardian 為 dart-test-async-guardian
- refactor: 補上 provider-architecture 遷移遺漏的引用更新
- refactor: 遷移 provider-architecture 為 dart-provider-architecture
- fix: 補回 dart-style-guardian 內容變更（並行 commit race 遺漏）
- fix: 修正規則檔憑空引用不存在的 IMP-APP-004
- fix: 移除框架檔案中的專案 ticket ID（reference-stability 規則 8）
- fix: 落地 worktree gen-l10n 防護，納 lib/l10n/generated/ 入版控
- fix: 對照實驗定案 worktree 全套件不可信 + 建 3 票 + IMP-APP-003
- fix: 修復 .claude/ 活文件 25 筆真失效引用
- docs: 新增 PC-APP-008 外部 API 測資虛構防護 + 規則 D5
- docs: 建立 dart-domain-modeling skill + parsley 觸發引用
- docs: 定義不可靠斷言判準 + Dart/Flutter 落地規則 D1-D4
- docs: 新增 PC-APP-007 spawn request 合併缺陷
- docs: parallel-dispatch 增補 named agent vs 一般 subagent 選用準則
- docs: IMP-APP-002 補記第六起同族案例（spec 層格式假設無實證， 修正）
- docs: 30 秒/1 頁 stale 定位引用全量 sweep（21 檔 29 處）
- docs: 方法論 元件文字歸屬判準 + README 定位反轉同步
- docs: 方法論 多輪審查 R3 修正 + outbound 接線收官
- docs: 方法論 多輪審查 R2 修正 17 項
- docs: 方法論 多輪審查 R1 修正 15 項
- docs: 元件庫雙向約束框架執法三落地
- docs: 方法論 補命名判準與形態因素先決 + saas skill 缺口票
- docs: 元件庫雙向約束框架執法評估 + 方法論用語修正
- docs: 元件庫雙向約束方法論 （L1 通用原則）
- chore: complete ANA — openBD + NDL Search 日本書目 API 整合設計
- chore: handoff → （openBD + NDL Search 日本書目 API 整合）
- chore: Worktree 隔離從「強制」改為「風險分級」（ 方案 C 分段採納）
- chore: 清理 parallel-dispatch.md 2 處依賴型 ticket ID 引用（ 結論落地）
- chore: 建票修 live 測試 not-found 斷言的 429 鑑別缺陷

---

## [2.14.0] - 2026-07-09

### Summary
feat: 建立 reference-stability 規則 8 強制 hook; feat: 建立 doc skill tracking_schema.py SSOT + conformance test; fix: test_update.py fixture 改從 SSOT 生成（list 格式） (+7 more)

Changes: 2 feat, 6 fix, 2 chore

- feat: 建立 reference-stability 規則 8 強制 hook
- feat: 建立 doc skill tracking_schema.py SSOT + conformance test
- fix: test_update.py fixture 改從 SSOT 生成（list 格式）
- fix: hook 範例改合成 ID 避免規則8自我違反
- fix: status.py 改 list iterate 修復對真實檔 crash
- fix: create.py proposals dict→list + confirmed→confirmed_at + 引用 SSOT
- fix: create.py 頂層 last_updated 鍵與真實 schema 對齊
- fix: 移除 _sync_tracking_yaml 頂層 last_updated 鍵
- chore: doc skill 框架碼 ticket ID 最終 sweep（reference-stability 規則 8）
- chore: batch_init.py traceability 頂層鍵引用 TRACEABILITY_SCHEMA

---

## [2.13.0] - 2026-07-08

### Summary
feat: 實作提案 confirmed 時 target_version 註冊 todolist 的源頭引導; feat: guard 增補版本目錄缺 main worklog 偵測; feat: guard 增補 confirmed 提案 target_version 與 todolist 註冊對賬 (+14 more)

Changes: 4 feat, 6 fix, 3 docs, 4 chore

- feat: 實作提案 confirmed 時 target_version 註冊 todolist 的源頭引導
- feat: guard 增補版本目錄缺 main worklog 偵測
- feat: guard 增補 confirmed 提案 target_version 與 todolist 註冊對賬
- feat: ticket migrate 新增版本合法性守衛
- fix: confirmed 欄位名對齊真實 schema confirmed_at
- fix: _sync_tracking_yaml 相容 proposals-tracking.yaml list 結構
- fix: list 統計與截斷顯示分離（total_stats 全量統計）
- fix: 修復 activate_next_planned_version 版本推進選擇防護
- fix: 阻斷框架 v2.x tags 混入 APP repo
- fix: 修復 version-tracking-consistency-guard 幽靈版本誤報
- docs: shutdown_request 驗證狀態升級為單層已驗證（實機 8/8）
- docs: 落地 idle agent 三態模型與回收 SOP（ ANA 三處落地）
- docs: 新增 IMP-APP-002 regex 解析多條目檔案未以條目邊界為先
- chore: shutdown 8/8 直接驗證 + SR-1 轉 （IMP-APP-002 第五起）
- chore: 驗收收尾——SR-2 轉 + IMP-APP-002 補第四起案例
- chore: / 驗收收尾——SR-1 轉 + IMP-APP-002 補第三起案例
- chore: pull .claude 更新（上游 6b4450666ed6）

---

## [2.12.0] - 2026-07-05

### Summary
feat: ticket CLI mutation self-verify 輸出; feat: Stop hook confabulation 事後審計; feat: batch annotate 130 memory backlog (+42 more)

Changes: 16 feat, 1 refactor, 5 fix, 18 docs, 5 chore

- feat: ticket CLI mutation self-verify 輸出
- feat: Stop hook confabulation 事後審計
- feat: batch annotate 130 memory backlog
- feat: version-release memory 升級稽核 check
- feat: dashboard 自動歸檔 stale pending handoff
- feat: emit protocol_version 至新建票 frontmatter
- feat: 新增 create --parent 時 children 數 warning
- feat: 實作 runqueue/list type 權重排序與 type 標籤顯示
- feat: rename Exit Status body key status → exit_status
- feat: enum-gate 切換 deny 模式
- feat: memory promote/scan 升級工具核心
- feat: stale-list 追加 stale in-progress 章節與 release 提示
- feat: 派發身份前移——dispatch hook 條件式綁定 + 模板 claim --as 強制
- feat: lifecycle 狀態轉移矩陣接入驗證閘
- feat: save_ticket 落盤前枚舉驗證閘
- feat: 枚舉 SSOT 收斂 + argparse choices 封口
- refactor: import _CATEGORY_DIRS from allocator (T1 SSOT)
- fix: frontmatter YAML 解析 graceful 處理 malformed 資料
- fix: main-thread-edit-restriction-hook 改用 lib import 取代已刪除的 hook_utils
- fix: 測試套件 todolist 環境依賴隔離
- fix: create --parent 無條件繼承父票版本
- fix: 移除 Write matcher 內 style-guardian-hook 重複註冊
- docs: 規則 6 補 error-pattern 記錄授權——判斷值得即做，不需請求用戶確認
- docs: 補 .3 confabulation 案例 + 防護 F + 建 enforcement 升級評估票
- docs: basil 審查修正——hook docstring/路徑表副本化 + 載體地圖版本行/受眾欄
- docs: 分流語意引用點同步——載體地圖（含補 user-level 條目）+ pm-role 路由 + reminder hook 文案
- docs: IMP-V1-006 大小寫不敏感 fs Edit 成功 vs git pathspec 失敗（捕獲時分流直寫 canonical）+ 檔名慣例追蹤票
- docs: basil 審查修正——升級後處理對齊規則 7 升級即搬家 + 情境 B 消除延後語意
- docs: 錯誤學習知識捕獲時分流——規則 7 語意前移 + 鏡像/skill/決策樹四檔同步
- docs: PC-092 補 v3 案例（PM 裸 commit 掃入 subagent 暫存檔）
- docs: 套用 Layer 2 審查修正（2 Warning）
- docs: context 充足度閘門三機制分工邊界
- docs: P 階段新增早期警訊條款
- docs: 新增關鍵禁令附最小正反例手法條款
- docs: 新增過度設計四反模式條目
- docs: 新增依賴引入紀律
- docs: 新增最小變更紀律（Surgical Changes）
- docs: When 提及 vs blockedBy 誤判率量測定案——零機制慣例落 field-semantics
- docs: SKILL.md 有效區段值對齊 10 章正典 + spawn
- docs: ticket 系統自我描述模型修正
- chore: 記錄 gate bypass 語意載體替換錯誤模式
- chore: HookCheck 自動修正 test_dispatch_record_identity_binding.py 執行權限 (IMP-054)
- chore: metadata sync post-completion
- chore: pull .claude 更新（上游 f6b5d50bcc2d）
- chore: 測試檔加執行權限（HookCheck 自動修正 IMP-054）

---

## [2.11.1] - 2026-07-03

### Summary
chore: multi-round-review 1.3.0 -> 1.4.1（skill 庫拉取，新增 minimum-three-rounds 原則文件）

Changes: 1 chore

- chore: multi-round-review 1.3.0 -> 1.4.1（skill 庫拉取，新增 minimum-three-rounds 原則文件）

---

## [2.11.0] - 2026-07-03

### Summary
feat: claim --as 自動推導 tdd_phase + phase 手動覆蓋保護（F4 接線）; feat: 自檢結果子章節升 CLI 層 gate 阻擋（IMP/ANA，判定邏輯與 warning 共用單一來源，F7 執法升級）; feat: version-bootstrap 跨提案依賴檢查 + 移版硬耦合盤點 SOP（ 模式固化） (+20 more)

Changes: 10 feat, 4 fix, 6 docs, 3 test

- feat: claim --as 自動推導 tdd_phase + phase 手動覆蓋保護（F4 接線）
- feat: 自檢結果子章節升 CLI 層 gate 阻擋（IMP/ANA，判定邏輯與 warning 共用單一來源，F7 執法升級）
- feat: version-bootstrap 跨提案依賴檢查 + 移版硬耦合盤點 SOP（ 模式固化）
- feat: spec API surface 完整性檢核（啟發式提醒，SPEC-014 v1.1 缺口回歸驗證，F5 防護）
- feat: spec 版本一致性 SessionStart hook — 抓 8 個既有漂移，spawn （F2 防護）
- feat: 建票 SPEC 引用驗證 — traceability.yaml 對照警告（F1 防護）
- feat: version-release check 可觀測性強化 — 配置載入揭露 + 跳過標籤名實對齊
- feat: version-tracking guard hook 擴充第五、六類偵測
- feat: close CLI resolved_by 驗證強化 — 依 reason 分歧驗證 + 延後語意攔截
- feat: 新增版本追蹤一致性守衛 session-start hook
- fix: dispatch_recommender 死路徑修復 + registry tdd_phases 補齊（fennel/thyme phase3b）+ cinnamon phase4b→phase4 對齊
- fix: acceptance gate 同命令鏈滯後誤報 — 偵測降級標記 [--]（F6 修復，24 測綠）
- fix: check_technical_debt_status 依 worklog_path_pattern 解析 nested 票目錄
- fix: 修復 version-release 版本生命週期推進斷鏈
- docs: dispatch template 收尾義務標準段（set-acceptance + 自檢子章節，F3/F7 供給側）
- docs: IMP-V1-005 依 Layer 2 審查修正 — 偵測判據獨立成章 + IMP-046 定位措辭對齊 + 標點
- docs: PROP-010 移 節點決策 + 建 _flags schema 定形票 + IMP-V1-005 error-pattern
- docs: agent-dispatch-template 補 worktree 快照過舊防護 SOP
- docs: PC-MON-002 必填不等於有效 — CLI 欄位缺格式/存在性驗證
- docs: PC-MON-001 防護落地於可繞過執行點導致復發 + 建 守衛 hook 票
- test: hooks 測試機械性缺陷修復 — LIB_DIR/patch target 8 檔 + CLAUDE_PROJECT_DIR fixture 補遮蔽紅燈；15f/59e → 0f/0e（3047 passed）
- test: dispatch validation 測試 fixture mock 化 — 移除上游 ticket ID 依賴（殘留 1 處為說明註解）
- test: stale 斷言同步現行設計 — 邊界測試改 config.json + staleness 清單移除已遷移 shim（ticket/worktree）

---

## [2.10.1] - 2026-07-02

### Summary
fix: exec-bit 還原網補 scripts/ 缺口（install-skill-clis Permission denied）; chore: pull .claude 更新（上游 51b471b）

Changes: 1 fix, 1 chore

- fix: exec-bit 還原網補 scripts/ 缺口（install-skill-clis Permission denied）
- chore: pull .claude 更新（上游 51b471b）

---

## [2.10.0] - 2026-07-02

### Summary
feat: 完成 CC release 全量評估主票 — .7 採用 respondToBashCommands: false; fix: settings.json Task/Agent matcher 收斂; fix: 修復 2 hook 內部 tool_name 字面守衛失效（Task→Agent 改名） (+4 more)

Changes: 1 feat, 2 fix, 4 docs

- feat: 完成 CC release 全量評估主票 — .7 採用 respondToBashCommands: false
- fix: settings.json Task/Agent matcher 收斂
- fix: 修復 2 hook 內部 tool_name 字面守衛失效（Task→Agent 改名）
- docs: 升級 IMP-V1-004 error-pattern — hook 字面守衛 vs matcher 別名漂移
- docs: 修正 chrome-extension-mcp-debug skill 工具名漂移
- docs: WRAP 分析落地 — Tool(param:value) 改知識註記、.7 結論待授權
- docs: CC release 2.1.173-2.1.198 全量影響評估與落地

---

## [2.9.1] - 2026-07-02

### Summary
chore: untrack skills/*/uv.lock（已被 *.lock gitignore 涵蓋）

Changes: 1 chore

- chore: untrack skills/*/uv.lock（已被 *.lock gitignore 涵蓋）

---

## [2.9.0] - 2026-07-02

### Summary
feat: 新增同義詞擴展去重機制（issue #14 選項 A）; docs: 整合 Workflow vs Agent 決策路由到 decision-tree.md; chore: 執行類代理人模型降級 inherit → sonnet (+1 more)

Changes: 1 feat, 1 docs, 2 chore

- feat: 新增同義詞擴展去重機制（issue #14 選項 A）
- docs: 整合 Workflow vs Agent 決策路由到 decision-tree.md
- chore: 執行類代理人模型降級 inherit → sonnet
- chore: pull .claude 更新（上游 4535e3b）

---

## [2.8.5] - 2026-07-01

### Summary
fix: 移除 .gitignore 對 sample_events.jsonl 的錯誤排除; chore: 新增 PC-APP-006 錯誤模式（.gitignore 排除測試 fixture）

Changes: 1 fix, 1 chore

- fix: 移除 .gitignore 對 sample_events.jsonl 的錯誤排除
- chore: 新增 PC-APP-006 錯誤模式（.gitignore 排除測試 fixture）

---

## [2.8.4] - 2026-07-01

### Summary
fix: 同步孤兒檔 sample_events.jsonl 測試 fixture

---

## [2.8.3] - 2026-07-01

### Summary
feat: 新增 design-system-spec-template.md 範本（W8-002）

---

## [2.8.2] - 2026-06-29

### Summary
sync .claude configuration

---

## [2.8.1] - 2026-06-26

### Summary
fix: skill-sync push 排除 __pycache__ 目錄; chore: skill-sync pull 自動版本比對 + 批量拉取 3 個更新 skill; chore: pull .claude 更新（上游 543ce90d）

Changes: 1 fix, 2 chore

- fix: skill-sync push 排除 __pycache__ 目錄
- chore: skill-sync pull 自動版本比對 + 批量拉取 3 個更新 skill
- chore: pull .claude 更新（上游 543ce90d）

---

## [2.8.0] - 2026-06-26

### Summary
feat: project-init 對 ticket/doc/worktree 改走 shim installer

Changes: 1 feat

- feat: project-init 對 ticket/doc/worktree 改走 shim installer

---

## [2.7.2] - 2026-06-25

### Summary
docs: WINDOWS-NOTES 補 CLI shim Windows 相容章節

Changes: 1 docs

- docs: WINDOWS-NOTES 補 CLI shim Windows 相容章節

---

## [2.7.1] - 2026-06-25

### Summary
docs: 落地流程教訓 PC-APP-004/005 + ARCH-007 觸發時機

Changes: 1 docs

- docs: 落地流程教訓 PC-APP-004/005 + ARCH-007 觸發時機

---

## [2.7.0] - 2026-06-25

### Summary
feat: guard hook 偵測 cwd-resolving shim 即略過; feat: 新增 cwd-resolving CLI shim installer（取代 uv tool install）; docs: 新增 ARCH-APP-002 uv tool install 全域 namespace 碰撞 (+1 more)

Changes: 2 feat, 1 docs, 1 chore

- feat: guard hook 偵測 cwd-resolving shim 即略過
- feat: 新增 cwd-resolving CLI shim installer（取代 uv tool install）
- docs: 新增 ARCH-APP-002 uv tool install 全域 namespace 碰撞
- chore: pull .claude 更新（上游 62c2ee388051）

---

## [2.6.0] - 2026-06-25

### Summary
feat: push 版本比對提示 + IMP-MON-003 error-pattern; feat: pull 不帶名稱時批次更新已安裝 skill（）; fix: SKILL.md 引導更新為前綴號格式和通用類別

Changes: 2 feat, 1 fix

- feat: push 版本比對提示 + IMP-MON-003 error-pattern
- feat: pull 不帶名稱時批次更新已安裝 skill（）
- fix: SKILL.md 引導更新為前綴號格式和通用類別

---

## [2.5.0] - 2026-06-25

### Summary
feat: sync-push 自動檢查 skill 庫版本 drift（）; feat: basil 升級為 universal_lens 全情境常駐; feat: create 加自動 ID 分配 + domain 推導（） (+19 more)

Changes: 7 feat, 5 refactor, 8 fix, 2 chore

- feat: sync-push 自動檢查 skill 庫版本 drift（）
- feat: basil 升級為 universal_lens 全情境常駐
- feat: create 加自動 ID 分配 + domain 推導（）
- feat: checklist enforcement 加建議值引導（）
- feat: full overlay 加 confirm 阻擋機制（）
- feat: clean_stale_files 加三方比對防護（）
- feat: rmtree 全量替換改為 overlay + diff preview（）
- refactor: public API 去除 _ prefix（）
- refactor: 提取 create_reporter.py 從 create.py（）
- refactor: 提取 duplicate_detector.py 從 create.py（）
- refactor: ana_spawn_consistency_checker typing 統一為內建泛型（）
- refactor: 提取 _should_skip_clean_file 共用 helper（）
- fix: 移除常駐委員加入情境的冗餘列舉（A-G）
- fix: 移除 basil opt-out 機制（）
- fix: 並行審查修正 — dead import 清除 + 用字修正（W4 Phase 3）
- fix: 情境表 Agent 數更新為 3+2（含常駐 linux + basil）
- fix: 禁止自創不行動/排除類別（）
- fix: 並行審查修復 — 安全 bug + dead code + 簡化
- fix: acceptance-gate spawn 計數加行級豁免（）
- fix: 恢復被 sync-pull 誤刪的 compositional-writing hooks（1037 行）
- chore: bump SKILL.md to
- chore: W3 批量完成 — known-limitation 標記 + 語意差異文件化

---

## [2.4.3] - 2026-06-25

### Summary
chore: basil-writing-critic 對齊 compositional-writing

Changes: 1 chore

- chore: basil-writing-critic 對齊 compositional-writing

---

## [2.4.2] - 2026-06-25

### Summary
sync .claude configuration

---

## [2.4.1] - 2026-06-25

### Summary
chore: pull multi-round-review 版本號更新（1.0.0）; chore: pull 寫作 skill 更新（compositional-writing + multi-round-review）; chore: pull .claude 更新（上游 cb11e8a3）

Changes: 3 chore

- chore: pull multi-round-review 版本號更新（1.0.0）
- chore: pull 寫作 skill 更新（compositional-writing + multi-round-review）
- chore: pull .claude 更新（上游 cb11e8a3）

---

## [2.4.0] - 2026-06-25

### Summary
feat: sync-pull post-sync 自動登記 Hook（hook-registry.yaml）; fix: project-init onboard 三項 false positive 修正; docs: 新增 error-pattern PC-V1-013（lenient build 驗證遮蔽 prod gate） (+3 more)

Changes: 1 feat, 1 fix, 2 docs, 2 chore

- feat: sync-pull post-sync 自動登記 Hook（hook-registry.yaml）
- fix: project-init onboard 三項 false positive 修正
- docs: 新增 error-pattern PC-V1-013（lenient build 驗證遮蔽 prod gate）
- docs: agent-dispatch-template 補 append-log 收尾持久化驗證準則
- chore: 登記 7 個通用 Hook + 排除 3 個語言專屬 Hook
- chore: pull .claude 更新（upstream ）

---

## [2.3.0] - 2026-06-25

### Summary
feat: lib/ 吸收 hook_utils 獨有函式成為單一 SSOT; refactor: 全 consumer import hook_utils→lib 並移除 hook_utils/; fix: 清理 bare git_utils import 殘留 + lib script-mode sys.path (+2 more)

Changes: 1 feat, 1 refactor, 2 fix, 1 docs

- feat: lib/ 吸收 hook_utils 獨有函式成為單一 SSOT
- refactor: 全 consumer import hook_utils→lib 並移除 hook_utils/
- fix: 清理 bare git_utils import 殘留 + lib script-mode sys.path
- fix: 修復 hook-health-monitor.py SessionStart str/Path 型別錯誤
- docs: 新增 IMP-APP-001 get_project_root 雙實作型別分歧

---

## [2.2.0] - 2026-06-24

### Summary
feat: 新增 skill-sync 至 uv tool staleness 監控; chore: pull .claude 更新（上游 7df1b31）

Changes: 1 feat, 1 chore

- feat: 新增 skill-sync 至 uv tool staleness 監控
- chore: pull .claude 更新（上游 7df1b31）

---

## [2.1.4] - 2026-06-24

### Summary
fix(tests): 追蹤 dispatch stats 測試 fixture sample_events.jsonl（修正 *.jsonl 規則誤殺）

---

## [2.1.3] - 2026-06-24

### Summary
fix(hooks): main hook sys.path 對齊 W2010 正規化範本 + 落地 Phase 2 條件式判斷/FR↔Ticket 覆蓋矩陣/spec 維度 3a3b 框架增強

---

## [2.1.2] - 2026-06-24

### Summary
fix: 修復 version.py 衝突解決遺漏的 docstring 和 import; chore: pull .claude 更新（上游 3c0445ab77b4）

Changes: 1 fix, 1 chore

- fix: 修復 version.py 衝突解決遺漏的 docstring 和 import
- chore: pull .claude 更新（上游 3c0445ab77b4）

---

## [2.1.1] - 2026-06-24

### Summary
sync .claude configuration

---

## [2.1.0] - 2026-06-24

### Summary
feat: sync-pull post-sync 告警 settings.local.json 含 hook; feat: hook-completeness --fix opt-in prune 幽靈 local hook; feat: sync-pull post-sync hook import 驗證 (+15 more)

Changes: 4 feat, 2 refactor, 7 fix, 5 docs

- feat: sync-pull post-sync 告警 settings.local.json 含 hook
- feat: hook-completeness --fix opt-in prune 幽靈 local hook
- feat: sync-pull post-sync hook import 驗證
- feat: test-hook-imports.sh 一鍵 hook import 煙霧測試
- refactor: lib/ 內 from hook_utils import 正規化
- refactor: 清理 hooks/lib 文字殘留 + 刪殘留目錄
- fix: dashboard 重用已載入 tickets 消除冗餘 subprocess
- fix: staleness 警告排除 trigger_bound ticket
- fix: 修 lib/tests 16 個 stale patch 目標
- fix: 修 scripts/tests 2 個 stale 測試
- fix: 修 test_dispatch_stats.py 38 errors（雙根因）
- fix: .gitignore 補齊 sync-skills.yaml + git rm --cached untrack
- fix: skill-sync SKILL.md 補齊 YAML frontmatter + 建立 issue #10 追蹤 tickets
- docs: cbm MCP namespace 已曝光於 ToolSearch，更新工具參考
- docs: 固化框架 hook 單一註冊來源原則於 PC-148
- docs: 新增 PC-V1-012 防護置於便利攔截介面而非變異源頭
- docs: hook sys.path 標準模板文件
- docs: sync-pull breaking change consumer checklist

---

## [2.0.1] - 2026-06-23

### Summary
chore: VERSION bump to 2.0.0 (align with framework breaking change)

Changes: 1 chore

- chore: VERSION bump to 2.0.0 (align with framework breaking change)

---

## [1.62.0] - 2026-06-23

### Summary
feat: sync-push/pull 新增 skill 版本 diff 摘要

Changes: 1 feat

- feat: sync-push/pull 新增 skill 版本 diff 摘要

---

## [1.61.2] - 2026-06-23

### Summary
chore: 補齊 8 個 skill 版本號

Changes: 1 chore

- chore: 補齊 8 個 skill 版本號

---

## [1.61.1] - 2026-06-23

### Summary
docs: IMP-V1-003 補充 復發案例——scripts/ 遺漏 + 擴充預防措施

Changes: 1 docs

- docs: IMP-V1-003 補充 復發案例——scripts/ 遺漏 + 擴充預防措施

---

## [1.61.0] - 2026-06-23

### Summary
feat: ticket CLI 全完成版本偵測 warning; feat: TDD 紅綠燈計數改用結構化 JSON 輸出; feat: identity-guard telemetry 新增 caller_type 欄位 (+11 more)

Changes: 3 feat, 2 refactor, 5 fix, 3 docs, 1 chore

- feat: ticket CLI 全完成版本偵測 warning
- feat: TDD 紅綠燈計數改用結構化 JSON 輸出
- feat: identity-guard telemetry 新增 caller_type 欄位
- refactor: merge hooks/lib/ into lib/
- refactor: migrate 8 hooks to skill directories
- fix: sync scripts import 路徑對齊 lib 合併（ 遺漏）
- fix: update_todolist 支援不帶引號的 YAML status 格式
- fix: 修正搬移回歸——test import 路徑 sync_exclude_manifest → lib.sync_exclude_manifest
- fix: 修正 version-release-guard-hook sys.path（搬移後 hook_io import 失敗）
- fix: update sys.path and test imports for migrated hooks
- docs: --as 轉強制重評裁決——維持 warn-only（使用率 49.3% 未達 80%）
- docs: IMP-V1-003 hook 搬移後 sys.path 指向錯誤 lib 目錄
- docs: 更新 sync-exclusion-guide — 新增類型 E + sync-skills.yaml 說明
- chore: pull .claude 更新（上游 36b86cc）

---

## [1.60.2] - 2026-06-23

### Summary
fix: 恢復 sync-pull 覆蓋的 TDD/Doc/Ticket Skill 更新; chore: pull .claude 更新（上游框架 skill 庫分離）

Changes: 1 fix, 1 chore

- fix: 恢復 sync-pull 覆蓋的 TDD/Doc/Ticket Skill 更新
- chore: pull .claude 更新（上游框架 skill 庫分離）

---

## [1.60.1] - 2026-06-23

### Summary
sync .claude configuration

---

## [1.60.0] - 2026-06-23

### Summary
feat: 建立 UC↔測試追溯矩陣 + 邊界回補流程; refactor: TDD Skill Round 2 冷讀審查修正; refactor: TDD Skill 跨專案適用性審查（移除專案特定引用） (+6 more)

Changes: 1 feat, 2 refactor, 1 fix, 5 docs

- feat: 建立 UC↔測試追溯矩陣 + 邊界回補流程
- refactor: TDD Skill Round 2 冷讀審查修正
- refactor: TDD Skill 跨專案適用性審查（移除專案特定引用）
- fix: sync-push --clean 日誌措辭修正（檔案→項目）
- docs: 更新 TDD/Ticket/Doc Skill 觸發關鍵字
- docs: TDD Skill 新增拆分邊界判讀規則（測試變綠驗收點）
- docs: TDD Skill 實證回饋（5 項調整）
- docs: 補充防護驗證結果（ 單一 worktree 驗證通過）
- docs: 記錄並行 worktree commit 交叉混入錯誤模式

---

## [1.59.1] - 2026-06-23

### Summary
sync .claude configuration

---

## [1.59.0] - 2026-06-23

### Summary
feat: 整合 blog 測試知識至 TDD skill（4 新 reference + 路由更新）; feat: 建立 doc→TDD 銜接機制（WRAP 評估：銜接放 TDD 端）; refactor: doc→TDD 銜接文件多輪審查修正（3 輪 33 項） (+3 more)

Changes: 2 feat, 1 refactor, 1 fix, 2 chore

- feat: 整合 blog 測試知識至 TDD skill（4 新 reference + 路由更新）
- feat: 建立 doc→TDD 銜接機制（WRAP 評估：銜接放 TDD 端）
- refactor: doc→TDD 銜接文件多輪審查修正（3 輪 33 項）
- fix: app_tunnel 測試教訓回饋至 TDD skill（畫面狀態機 + 操作覆蓋深度）
- chore: 移除已 DEPRECATED 的 tdd-phase1-split skill
- chore: pull .claude 更新（上游 36ab0f7）

---

## [1.58.1] - 2026-06-22

### Summary
chore: add PC-V1-011 error pattern + complete ANA; chore: pull .claude 更新（上游 b3aadb8ff140）

Changes: 2 chore

- chore: add PC-V1-011 error pattern + complete ANA
- chore: pull .claude 更新（上游 b3aadb8ff140）

---

## [1.58.0] - 2026-06-22

### Summary
feat: SaaS skill state-storage 維度補 ID/主鍵選型訪談; chore: pull .claude 更新（上游 4012a25）

Changes: 1 feat, 1 chore

- feat: SaaS skill state-storage 維度補 ID/主鍵選型訪談
- chore: pull .claude 更新（上游 4012a25）

---

## [1.57.1] - 2026-06-22

### Summary
fix: detect_version reads todolist active + decouple activate from git (/004); chore: add ARCH-APP-001 version detection desync error pattern; chore: pull .claude 更新（上游 627ed412d54b）

Changes: 1 fix, 2 chore

- fix: detect_version reads todolist active + decouple activate from git (/004)
- chore: add ARCH-APP-001 version detection desync error pattern
- chore: pull .claude 更新（上游 627ed412d54b）

---

## [1.57.0] - 2026-06-22

### Summary
feat: teaching-sync skill v2.0 + CLAUDE.md 教學互補流程; docs: Spec/UC review — 對齊教學設計 + SaaS skill 推導標記機制; chore: pull .claude 更新（上游 7f24696）

Changes: 1 feat, 1 docs, 1 chore

- feat: teaching-sync skill v2.0 + CLAUDE.md 教學互補流程
- docs: Spec/UC review — 對齊教學設計 + SaaS skill 推導標記機制
- chore: pull .claude 更新（上游 7f24696）

---

## [1.56.7] - 2026-06-20

### Summary
fix: 新增反向孤兒偵測（上游有本地無）; chore: pull 補齊上游 IMP-V1-002 error-pattern + 清理本地 build artifacts

Changes: 1 fix, 1 chore

- fix: 新增反向孤兒偵測（上游有本地無）
- chore: pull 補齊上游 IMP-V1-002 error-pattern + 清理本地 build artifacts

---

## [1.56.6] - 2026-06-20

### Summary
fix: release 後自動推進下一個 planned 版本為 active

Changes: 1 fix

- fix: release 後自動推進下一個 planned 版本為 active

---

## [1.56.5] - 2026-06-19

### Summary
sync .claude configuration

---

## [1.56.4] - 2026-06-19

### Summary
chore: CC 2.1.173-2.1.183 release impact review; chore: pull .claude 更新（上游 ac320f3501e3）

Changes: 2 chore

- chore: CC 2.1.173-2.1.183 release impact review
- chore: pull .claude 更新（上游 ac320f3501e3）

---

## [1.56.3] - 2026-06-19

### Summary
sync .claude configuration

---

## [1.56.2] - 2026-06-19

### Summary
chore: pull .claude 更新（上游 73a76fb4866a）

Changes: 1 chore

- chore: pull .claude 更新（上游 73a76fb4866a）

---

## [1.56.1] - 2026-06-19

### Summary
sync .claude configuration

---

## [1.56.0] - 2026-06-19

### Summary
feat: renumber native intruder PC-177/178→184/185 + lineage-aware 孤兒守衛; feat: sync-push 補撞號對稱（鏡像 pull）+ 首跑對帳辨識上游 mess; fix: 修正 +build 後綴崩潰與 monorepo in-dev 版本偵測 (+1 more)

Changes: 2 feat, 2 fix

- feat: renumber native intruder PC-177/178→184/185 + lineage-aware 孤兒守衛
- feat: sync-push 補撞號對稱（鏡像 pull）+ 首跑對帳辨識上游 mess
- fix: 修正 +build 後綴崩潰與 monorepo in-dev 版本偵測
- fix: PC-183 lineage typo PC-18→PC-018 + H1 對齊 183（修 038 parser 誤判隱因）

---

## [1.55.0] - 2026-06-18

### Summary
feat: 泛化 presence-detection hook 為 language-pluggable; feat: worktree 守護 hook + 規則（固化兩起事故）; feat: presence-detection hook（偵測應有設施缺席） (+7 more)

Changes: 5 feat, 1 fix, 4 docs

- feat: 泛化 presence-detection hook 為 language-pluggable
- feat: worktree 守護 hook + 規則（固化兩起事故）
- feat: presence-detection hook（偵測應有設施缺席）
- feat: 落地集中化 acceptance 維度（prevention gate）
- feat: 落地決策閘門預算+退場 meta 規則 + 並行層搬遷 pilot
- fix: presence hook skip 對齊 sink 命名 + 排除 dev 訊息
- docs: 補 see-also（linux 審查 should-fix）— 釐清 D 軸對帳與並行 session 層職責分工
- docs: 落地 F+D 認知接地雙層 + 軸登錄協議（）
- docs: 方法論修 basil 兩 Warning（G 軸語意化 + F 子軸可重跑邊界）
- docs: 實證決策軸發現方法論

---

## [1.54.9] - 2026-06-18

### Summary
docs: 回饋 report #169 — 新增「原子筆記要有議題入口」principle（）; docs: 補「冷讀/零脈絡單卡落地」frame（）

Changes: 2 docs

- docs: 回饋 report #169 — 新增「原子筆記要有議題入口」principle（）
- docs: 補「冷讀/零脈絡單卡落地」frame（）

---

## [1.54.8] - 2026-06-18

### Summary
chore: pull .claude 更新（上游 c389f9a，含 PR #7 merge）

Changes: 1 chore

- chore: pull .claude 更新（上游 c389f9a，含 PR #7 merge）

---

## [1.54.7] - 2026-06-18

### Summary
docs: 固化 SA 前置審查提醒的假陽性邊界（）

Changes: 1 docs

- docs: 固化 SA 前置審查提醒的假陽性邊界（）

---

## [1.54.6] - 2026-06-18

### Summary
chore: pull .claude 更新（上游 9e734b9，含 PR #5/#6 merge）

Changes: 1 chore

- chore: pull .claude 更新（上游 9e734b9，含 PR #5/#6 merge）

---

## [1.54.5] - 2026-06-18

### Summary
docs: 補 push 側孤兒過刪變體

Changes: 1 docs

- docs: 補 push 側孤兒過刪變體

---

## [1.54.4] - 2026-06-18

### Summary
docs: 持久化 monorepo 版本取捨判斷 + 開 version-release 設計缺口 issue; docs: 固化「monorepo 子端未進 CI 守門」流程缺口; chore: version-release CLI 在地適配 monorepo (+1 more)

Changes: 2 docs, 2 chore

- docs: 持久化 monorepo 版本取捨判斷 + 開 version-release 設計缺口 issue
- docs: 固化「monorepo 子端未進 CI 守門」流程缺口
- chore: version-release CLI 在地適配 monorepo
- chore: pull .claude 更新（上游 70c4576）

---

## [1.54.3] - 2026-06-18

### Summary
fix: dashboard 漏報 NO-CB pending ticket + list --status 逗號語法錯誤

Changes: 1 fix

- fix: dashboard 漏報 NO-CB pending ticket + list --status 逗號語法錯誤

---

## [1.54.2] - 2026-06-17

### Summary
docs: 新增變體 B（PM append-log 觸發）及預防方案; docs: 新增 ARCH-TUNL-001 local settings hook 註冊幽靈模式; chore: pull .claude 更新（上游 beaca2e2ec36）

Changes: 2 docs, 1 chore

- docs: 新增變體 B（PM append-log 觸發）及預防方案
- docs: 新增 ARCH-TUNL-001 local settings hook 註冊幽靈模式
- chore: pull .claude 更新（上游 beaca2e2ec36）

---

## [1.54.1] - 2026-06-17

### Summary
chore: 傳播刪除 test_monorepo_version_sync.py 孤兒

---

## [1.54.0] - 2026-06-17

### Summary
feat: cmd_start_version 多專案類型整合（）; feat: schema 擴展 + 專案偵測 + yaml/toml bump（/100/101）; feat: 擴展版本源候選 + resolve_version_source（） (+1 more)

Changes: 3 feat, 1 docs

- feat: cmd_start_version 多專案類型整合（）
- feat: schema 擴展 + 專案偵測 + yaml/toml bump（/100/101）
- feat: 擴展版本源候選 + resolve_version_source（）
- docs: SKILL.md 多專案類型文件更新（）

---

## [1.53.2] - 2026-06-17

### Summary
fix: 移除 repo 常數 .git 後綴致 gh --repo 解析失敗

Changes: 1 fix

- fix: 移除 repo 常數 .git 後綴致 gh --repo 解析失敗

---

## [1.53.1] - 2026-06-17

### Summary
docs: 新增 Behavioral Core Principle 行為核心準則; chore: pull .claude 更新（上游 aa4f0038）

Changes: 1 docs, 1 chore

- docs: 新增 Behavioral Core Principle 行為核心準則
- chore: pull .claude 更新（上游 aa4f0038）

---

## [1.53.0] - 2026-06-17

### Summary
refactor: REQUIRED 清單 derive 自 manifest GITIGNORE_EXPECTED

Changes: 1 refactor

- refactor: REQUIRED 清單 derive 自 manifest GITIGNORE_EXPECTED

---

## [1.52.6] - 2026-06-17

### Summary
fix: 補 TASK_AVOIDANCE_FIX_MODE 入 sync 排除清單

Changes: 1 fix

- fix: 補 TASK_AVOIDANCE_FIX_MODE 入 sync 排除清單

---

## [1.52.5] - 2026-06-17

### Summary
docs: 新增 ARCH-TUNL-001 local settings hook 註冊幽靈 + 登錄 TUNL 專案代號

Changes: 1 docs

- docs: 新增 ARCH-TUNL-001 local settings hook 註冊幽靈 + 登錄 TUNL 專案代號

---

## [1.52.4] - 2026-06-17

### Summary
fix: 固化 hook 註冊單一來源原則 + 偵測 local 層 latent ghost; chore: pull .claude 更新（上游 d2424984）

Changes: 1 fix, 1 chore

- fix: 固化 hook 註冊單一來源原則 + 偵測 local 層 latent ghost
- chore: pull .claude 更新（上游 d2424984）

---

## [1.52.3] - 2026-06-17

### Summary
chore: pull .claude 更新（上游 d2424984）

Changes: 1 chore

- chore: pull .claude 更新（上游 d2424984）

---

## [1.52.2] - 2026-06-17

### Summary
fix: 允許 PM 編輯任意層級 README.md

Changes: 1 fix

- fix: 允許 PM 編輯任意層級 README.md

---

## [1.52.1] - 2026-06-17

### Summary
sync .claude configuration

---

## [1.52.0] - 2026-06-17

### Summary
feat: saas↔doc 雙向銜接 + CLAUDE.md 瘦身（決策記錄移交為代謝機制）

Changes: 1 feat

- feat: saas↔doc 雙向銜接 + CLAUDE.md 瘦身（決策記錄移交為代謝機制）

---

## [1.51.3] - 2026-06-16

### Summary
sync .claude configuration

---

## [1.51.2] - 2026-06-16

### Summary
fix: _is_placeholder 補行尾空殼偵測修 行首語意回歸; chore: pull .claude 更新（上游 2c3d77f7）; chore: .claude 框架同步 + 還原至 docs/analyses

Changes: 1 fix, 2 chore

- fix: _is_placeholder 補行尾空殼偵測修 行首語意回歸
- chore: pull .claude 更新（上游 2c3d77f7）
- chore: .claude 框架同步 + 還原至 docs/analyses

---

## [1.51.1] - 2026-06-16

### Summary
chore: 整理 settings.json 共用層權限; chore: 移除原作者專案產物殘留並補齊 sync/gitignore 排除

Changes: 2 chore

- chore: 整理 settings.json 共用層權限
- chore: 移除原作者專案產物殘留並補齊 sync/gitignore 排除

---

## [1.51.0] - 2026-06-16

### Summary
feat: 導入 saas-tech-selection 選型訪談 skill（上游來源 blog repo）

Changes: 1 feat

- feat: 導入 saas-tech-selection 選型訪談 skill（上游來源 blog repo）

---

## [1.50.0] - 2026-06-16

### Summary
feat: ticket create --where 驗證並拒絕非路徑 token 防 where.files 髒值

Changes: 1 feat

- feat: ticket create --where 驗證並拒絕非路徑 token 防 where.files 髒值

---

## [1.49.1] - 2026-06-16

### Summary
docs: 修正 README stale PC-018 引用為 PC-183

Changes: 1 docs

- docs: 修正 README stale PC-018 引用為 PC-183

---

## [1.49.0] - 2026-06-16

### Summary
feat: sync-push 前框架 import smoke test 閘門（C1 生產閘）; feat: sync tagged-release + pin-aware pull; feat: framework-issue fix-status 跨 consumer 修復矩陣（軸 C） (+8 more)

Changes: 5 feat, 2 fix, 3 docs, 1 chore

- feat: sync-push 前框架 import smoke test 閘門（C1 生產閘）
- feat: sync tagged-release + pin-aware pull
- feat: framework-issue fix-status 跨 consumer 修復矩陣（軸 C）
- feat: framework-issue link 命令 + canonical_issue stamp
- feat: 建立 /framework-issue SKILL（create/list + scaffold）
- fix: sync-pull preserve fallback parser fail-loud on malformed YAML
- fix: 去重 file_lock.py 重複函式定義（死碼 shadow 活碼）
- docs: 新增 PC-V1-010 + 補 PC-V1-009/ARCH-V1-002 索引缺漏
- docs: 規則 8 補框架 code 註解識別符衛生 + frontmatter/trailer 溯源慣例
- docs: 框架治理 ANA 評估產物 — 2 error-pattern + 4 spawn ticket
- chore: pull .claude 更新（上游 a883d6e321b9）

---

## [1.48.8] - 2026-06-16

### Summary
sync .claude configuration

---

## [1.48.7] - 2026-06-16

### Summary
fix: 移除 v1.48.6 誤推的專案特化檔（PC-177/178 + wrap-decision project-integration 7 檔）

v1.48.6 由 consumer 專案 sync-push 全樹 overlay 誤推上來的 project-specific 內容。
push 端 preserve-aware 排除已落地（防未來復發），本次外科手術移除已推副本。
保留 PC-APP-001/002（staging error-pattern，跨專案適用）。

Changes: 1 fix

- fix: 移除 9 個誤推的專案特化檔（preserve-listed），framework 回歸通用內容

---

## [1.48.6] - 2026-06-16

### Summary
--help

---

## [1.48.5] - 2026-06-16

### Summary
fix: check_gitignore_completeness 改 git check-ignore 混合語意消除 false positive; fix: dispatch-active missing 建議字面改 .claude/dispatch-active*; fix: 同步 project-init gitignore/check 測試斷言並修 _create_missing_gitignore_result 漏列 dispatch-active (+1 more)

Changes: 3 fix, 1 chore

- fix: check_gitignore_completeness 改 git check-ignore 混合語意消除 false positive
- fix: dispatch-active missing 建議字面改 .claude/dispatch-active*
- fix: 同步 project-init gitignore/check 測試斷言並修 _create_missing_gitignore_result 漏列 dispatch-active
- chore: test_hook_completeness_reverse_check.py 執行權限對齊 100755

---

## [1.48.4] - 2026-06-16

### Summary
fix: get_tickets_dir 加既有 flat 結構讀取相容（issue #1 問題4）; fix: save_ticket 保留檔尾換行 + race 測試 win32 skip（跨平台收尾）; fix: hook-completeness 新增反向檢查（幽靈註冊+跨檔重複偵測） (+3 more)

Changes: 6 fix

- fix: get_tickets_dir 加既有 flat 結構讀取相容（issue #1 問題4）
- fix: save_ticket 保留檔尾換行 + race 測試 win32 skip（跨平台收尾）
- fix: hook-completeness 新增反向檢查（幽靈註冊+跨檔重複偵測）
- fix: uv-tool-staleness install 指令改絕對路徑免 cd（PowerShell 相容）
- fix: project-init Python 偵測多候選+uv fallback、安裝指引 OS 感知（Windows 跨平台）
- fix: file_lock 改用 filelock 取代 fcntl（Windows 跨平台 P0）

---

## [1.48.3] - 2026-06-15

### Summary
清理遠端孤兒：傳播過時 legacy 文件與 dead 範本之刪除

移除 agent 協作規範舊副本、tdd 協作流程 legacy 副本、ticket-system 範本
（本地已刪除，--clean 傳播至遠端避免 full overlay 復發孤兒）

---

## [1.48.2] - 2026-06-15

### Summary
--help

---

## [1.48.1] - 2026-06-14

### Summary
fix: 非阻塞 reap 收割殘留 stale .md.lock

Changes: 1 fix

- fix: 非阻塞 reap 收割殘留 stale .md.lock

---

## [1.48.0] - 2026-06-14

### Summary
feat: SessionStart agent 定義標準執法掃描 hook; docs: campaign 收尾 gate broken-link 修復 + methodology-index 補齊; docs: 瘦身 five-document-system-methodology 336→202 (+34 more)

Changes: 1 feat, 36 docs

- feat: SessionStart agent 定義標準執法掃描 hook
- docs: campaign 收尾 gate broken-link 修復 + methodology-index 補齊
- docs: 瘦身 five-document-system-methodology 336→202
- docs: 瘦身 business-layer-i18n 方法論 354->145 行 + 衛星檔
- docs: 瘦身 personalized-consultation-methodology 431->275 + 衛星檔
- docs: 瘦身 cognitive-load-design-methodology 419->139 + 衛星檔外移 + rule 去重
- docs: 合併 multi-perspective(419) → parallel-evaluation 方案 A
- docs: 整併 hook 家族 3 檔為 1 主檔 + 2 衛星檔
- docs: 瘦身 frontmatter-ticket-tracking-methodology 561→232 行
- docs: 瘦身 5w1h-self-awareness-methodology 605->265 行
- docs: 瘦身 problem-awareness-evaluation-methodology 698->227
- docs: 瘦身 acceptance-criteria-methodology 701→297 行 + 外移衛星檔
- docs: 校準審查 B2 修正 — 衛星檔回指補 intent 情境句
- docs: 瘦身 package-import-methodology 736→86 行 + 衛星檔外移
- docs: 移除 thyme 品質檢查清單冗餘標題，路由併入品質標準章節
- docs: 批 C TRIM 通用4階段骨架（thyme-ext/ginger/basil-event）
- docs: 批 B 外移 SD/SE/DBA 輸出範本至 references/
- docs: 批A ROUTE 三檔流程外移（thyme-doc/pepper/basil-hook）
- docs: 外移 parsley Phase3b+Phase4 交接通用骨架至 tdd skill
- docs: 外移 fennel Phase3b 通用骨架至 tdd/phase3-implementation skill
- docs: 外移 cinnamon Phase4 重構流程到 tdd/phase4-refactor
- docs: 外移 oregano 資料提取流程到 data-extraction skill
- docs: 外移 lavender Phase1 通用六階段流程至 tdd/phase1
- docs: 外移 sage Phase2 流程到 tdd/phase2/rules
- docs: 建立 data-extraction skill（oregano 流程外移目標）
- docs: 補強 malformed-tool-call-detector docstring 架構邊界說明
- docs: 整併瘦身 group-ticket-design(156→83)+ticket-lifecycle-management(178→144)
- docs: 整併瘦身 atomic-ticket(884→366)+ticket-design-dispatch(1168→180)
- docs: 整併瘦身 layered-ticket 家族 4 檔 → 30 秒核心
- docs: 去重整併 TDD/testing 家族其餘 5 檔
- docs: 整併瘦身 tdd-collaboration-flow 完整流程外移 tdd skill
- docs: thyme-python C3 品質清單 + C4 IMP-003 路由化
- docs: 清理 C1 輕量 5 檔搜尋工具路由化 + DEPRECATED 2 檔確認
- docs: 清理 oregano/sage/star-anise/sumac C1+C6
- docs: 清理中檔 linux/saffron/mint/project-compliance/clove 的 C1/C5（linux 含 C6）
- docs: 清理 parsley/cinnamon/lavender 重檔 C1/C5/C6 錯置
- docs: 統一 ANA 衍生票血緣模型為 children（Option A）+ 修跨檔矛盾

---

## [1.47.0] - 2026-06-12

### Summary
feat: 回流 blog 實戰改良版寫作 skill（compositional-writing + 新增 multi-round-review）; docs: multi-round-review R4 收斂 + ANA 收口（方法論 ）; docs: multi-round-review Round 3 修正（框架側 8 檔） (+4 more)

Changes: 1 feat, 6 docs

- feat: 回流 blog 實戰改良版寫作 skill（compositional-writing + 新增 multi-round-review）
- docs: multi-round-review R4 收斂 + ANA 收口（方法論 ）
- docs: multi-round-review Round 3 修正（框架側 8 檔）
- docs: multi-round-review Round 2 修正（框架側）
- docs: multi-round-review Round 1 修正（框架側）
- docs: README 註記寫作 skill 訓練上游（blog repo git URL）
- docs: 新增 DOC-V1-001 位置編號引用靜默失效 error-pattern + 審查票

---

## [1.46.2] - 2026-06-12

### Summary
docs: 知識載體責任分配方法論落地 + 盤點 ticket spawn

Changes: 1 docs

- docs: 知識載體責任分配方法論落地 + 盤點 ticket spawn

---

## [1.46.1] - 2026-06-12

### Summary
docs: 新增 PC-V1-006 規則變更未盤點既有規則矛盾即上線; docs: 防膨脹機制正規化三缺口收口

Changes: 2 docs

- docs: 新增 PC-V1-006 規則變更未盤點既有規則矛盾即上線
- docs: 防膨脹機制正規化三缺口收口

---

## [1.46.0] - 2026-06-12

### Summary
feat: file-size-guardian 擴充 auto-load 集合 token 預算量測; feat: sync-pull 衝突處理標準化; fix: 校準 file-size-guardian CHARS_PER_TOKEN 係數 3 → 1.3 (+9 more)

Changes: 2 feat, 1 fix, 2 docs, 7 chore

- feat: file-size-guardian 擴充 auto-load 集合 token 預算量測
- feat: sync-pull 衝突處理標準化
- fix: 校準 file-size-guardian CHARS_PER_TOKEN 係數 3 → 1.3
- docs: 新增 IMP-V1-001 估算係數未經實測校準即上線 error-pattern
- docs: 新增 PC-V1-005 acceptance 量化目標未考慮 substance 密度上限
- chore: 測試檔執行權限修正（HookCheck IMP-054 自動 chmod +x）
- chore: 三檔 token 收斂瘦身
- chore: 六檔 auto-load 文件輕量修剪（減量 20.8%）
- chore: 三檔主文外移 references/，core/ 降速查 stub
- chore: CLAUDE.md 收斂至 149 行 + project-conventions @ 改純路徑
- chore: test-assertion-design-rules 主文外移 references/ 降 stub
- chore: sync-pull — .version-release.yaml 納入 local-only 排除 + VERSION/CHANGELOG 採上游解衝突

---

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
