# Hooks Archive - 廢棄腳本存檔

本目錄存放已停用或已被新實現取代的 Hook 腳本。

## 歸檔目錄結構

```
archived/
├── ARCHIVE-README.md                  # 本文件
├── 5w1h-token-generator.py           # 廢棄: 5W1H Token 生成器
├── agent_dispatch_analytics.py       # 廢棄: 代理人分派智慧分析工具
├── agent_dispatch_recovery.py        # 廢棄: 代理人分派錯誤恢復工具
├── check-next-objectives.py          # 廢棄: 檢查中版本層級的 todolist.yaml
├── generate-context-resume.py        # 廢棄: 上下文恢復提示詞生成器
├── hook-auto-register.py             # 廢棄: Hook 自動註冊機制
├── pre-compact.py                    # 廢棄: PreCompact Hook
├── required-features-check.py        # 廢棄: Session 啟動必要功能驗證
├── show-cache-stats.py               # 廢棄: Ticket Quality Gate 快取統計查詢
├── tdd-phase-check-hook.py           # 廢棄: TDD Phase 完整性檢查
├── test-summary.py                   # 廢棄: 測試摘要腳本（已由 test-summary.sh 取代）
├── ticket-creator.py                 # 廢棄: 已由 /ticket create SKILL 取代
└── ticket-tracker.py                 # 廢棄: 已由 /ticket track SKILL 取代
```

## 歸檔原因

### 功能已被新實現取代

- **ticket-creator.py** → `/ticket create` SKILL
- **ticket-tracker.py** → `/ticket track` SKILL
- **test-summary.py** → `test-summary.sh` (shell 版本更輕)

### 未使用的實驗性功能

- **5w1h-token-generator.py** - Token 管理工具，未在實際使用
- **agent_dispatch_analytics.py** - 分析工具，功能完整但未納入流程
- **agent_dispatch_recovery.py** - 恢復工具，功能完整但未納入流程
- **hook-auto-register.py** - 自動註冊工具，已停用
- **pre-compact.py** - 上下文恢復工具，未在實際使用

### 舊版本工具

- **check-next-objectives.py** - v0.16 版本的任務檢查工具
- **generate-context-resume.py** - 舊版本上下文恢復工具
- **required-features-check.py** - 功能驗證工具，功能完整但未使用
- **show-cache-stats.py** - 快取統計工具
- **tdd-phase-check-hook.py** - 未在 settings.json 中註冊

## 恢復廢棄腳本

若要恢復廢棄腳本到正式使用：

1. 使用 `git mv` 將檔案移回 `.claude/hooks/` 根目錄
2. 更新 `.claude/settings.json` 以註冊該 Hook
3. 執行 hook-completeness-check.py 驗證

```bash
git mv .claude/hooks/archived/script-name.py .claude/hooks/script-name.py
```

## 清理舊備份

本目錄不包含被取代的舊版本備份（如 `*-backup.py` 檔案），這些由 `hook-exclude-list.json` 的 `*-backup.py` 模式管理。

## 日期

- **歸檔時間**: 2026-02-11
- **對應版本**: v0.31.0
- **對應 Ticket**: 0.31.0-W18-001.2
