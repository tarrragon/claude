# Changelog

本檔案記錄 `.claude` 配置的所有重要變更。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.0.0/)，
版本號遵循 [Semantic Versioning](https://semver.org/lang/zh-TW/)。

## 版本號規則

- **Major (X.0.0)**：CLAUDE.md 或 FLUTTER.md 變更（重大更新）
- **Minor (X.Y.0)**：新增檔案（功能新增）
- **Patch (X.Y.Z)**：修改既有檔案（改進和修復）

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
