<!-- section: 待辦與來源（flutter-balance） owner: flutter-balance-77 -->
## 待辦與來源（flutter-balance）

收束時全部 pending，無進行中工作。取回原票的 acceptance 與 `where.files` 用 `ticket track query <closed-id>`，不重寫。

### 實作與文件類

| 來源票 | 型別 | 做什麼 | acceptance 條數 | 優先級 | 階段 | 狀態 |
|--------|------|--------|----------------|--------|------|------|
| 0.2.1-W3-1234 | IMP | hooks-test-gate 補 reference-transaction 承載體，使 `.claude/hooks/*.py` 測試檢查涵蓋 update-ref 提交路徑 | 1 | P1 | 本版 | 待裁票 |
| 0.2.1-W3-1235 | IMP | 保護分支檢查補 reference-transaction 承載體；實作前先判定本 repo 是否應有 commit 期分支保護 | 2 | P1 | 本版 | 待裁票 |
| 0.2.1-W3-1242 | IMP | 派發記錄的票生命週期釋放點（重判後範圍，見「當前結論」第二節） | 3 | P1 | 本版 | 待裁票 |
| 0.2.1-W3-1248 | IMP | dispatch-readiness 檢查 4 判定寫入涵蓋時排除帶 `::read` 標記的項目 | 3 | P1 | 本版 | 待裁票 |
| 0.2.1-W3-1156 | DOC | 派發規則增列判準式條文：交付物無第二載體者須指定落檔路徑，回傳僅為指標 | 3 | P1 | 本版 | 待裁票 |
| 0.2.1-W3-1236 | IMP | domain-import-lint／tracking-schema-json-staleness／homoglyph 三支補 reference-transaction 承載體 | 1 | P2 | 本版 | 待裁票 |
| 0.2.1-W3-1099 | IMP | process-skip-guard 的 dispatch-active.json 存取改用 `git_utils.get_project_root`，補 worktree 內執行的測試 | 1 | P2 | 本版 | 待裁票 |
| 0.2.1-W3-1245 | IMP | dispatch-readiness 新增識別符出現性檢查（warn-only） | 3 | P2 | 本版 | 待裁票 |
| 0.2.1-W3-1244 | IMP | `precondition.py` 的狀態前置條件拒絕訊息改走共用錯誤信封（涉 7 個呼叫端） | 4 | P2 | 本版 | 待裁票 |
| 0.2.1-W3-1148 | IMP | 精準 staging 制式句缺漏的執法層；判準須與制式句的最終載體一致 | 4 | P2 | 可立即執行 | 待裁票 |
| 0.2.1-W3-1159 | IMP | methodology-index 混合模式產生器（有 frontmatter 自動生成、其餘逐字保留） | 5 | P2 | 本版 | 待裁票 |
| 0.2.1-W3-1233 | IMP | owned-issues 登記檔的既有 issue backfill，避免登記檔轉為非空時既有 issue 靜默退出檢查範圍 | 3 | P2 | 本版 | 待裁票 |
| 0.2.1-W3-1180 | DOC | 修正逐字外移後失真的跨檔自我指涉措辭，並處置該段的 relocation marker | 3 | P2 | 本版 | 待裁票 |
| 0.2.1-W3-1237 | IMP | 兩支 advisory-only guard 評估是否值得補承載體；不涵蓋亦為終態結論 | 1 | P3 | 下版 | 待裁票 |

### 分析類（結論未產出，問題陳述已收進本 issue）

| 來源票 | 做什麼 | acceptance 條數 | 優先級 | 階段 | 狀態 |
|--------|--------|----------------|--------|------|------|
| 0.2.1-W3-1166 | 量測觸及 hooks 目錄的票的 acceptance 條目分佈，評估三個修法方向 | 1 | P2 | 本版 | 待裁票 |
| 0.2.1-W3-1179 | 查明現行查重判準，估算 `where.files` 交集作為補充訊號的誤報率 | 3 | P2 | 本版 | 待裁票 |
| 0.2.1-W3-1246 | 量測「零值觀測導出運作結論」文字形狀的偵測率與誤報面，判定兩個競爭判準 | 3 | P2 | 本版 | 待裁票 |
| 0.2.1-W3-1031 | 評估派發意圖提醒層的設計與可行性，含誤報代價與查核端併呈 | 6 | P2 | 本版 | 待裁票 |
| 0.2.1-W3-1174 | 盤點 `find_section(levels=(3,))` 全部呼叫端，判定修共用邏輯或保留 workaround | 2 | P2 | 本版 | 待裁票 |
| 0.2.1-W3-682 | 盤點會自動改寫 `.claude/` 檔案狀態的機制，產出實驗自變數隔離判準 | 4 | P2 | 本版 | 待裁票 |
| 0.2.1-W3-637 | 判定 `ListAgents` 缺列 in-process named subagent 屬預期行為或缺陷 | 3 | P2 | 可立即執行 | 待裁票 |
| 0.2.1-W3-636 | 定位 `SendMessage` 索回失敗的觸發條件（事件驅動採樣） | 3 | P2 | 待條件 | 待裁票 |
| 0.2.1-W3-537 | 對照實驗 `.claude/` 並行編輯 deny 上限的跨 process 行為（本 issue body 待驗項 1） | 1 | P2 | 可立即執行 | 待裁票 |
| 0.2.1-W3-535 | 驗證 worktree 內 session 的命名規律與 `.claude/` 狀態碎裂行為（本 issue body 待驗項 2） | 1 | P2 | 可立即執行 | 待裁票 |
| 0.2.1-W3-1094 | 驗證 `SubagentStop` input 的欄位關聯性——前提已失效，見「當前結論」第二節 | 1 | P2 | 本版 | 待裁票 |

來源票對照：本 consumer 派發票 0.2.1-W3-1267.7 的 Test Results。
