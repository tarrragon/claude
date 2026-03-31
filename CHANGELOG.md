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
