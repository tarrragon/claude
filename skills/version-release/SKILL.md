---
name: version-release
description: "版本發布整合工具。Use for: (1) 發布新版本（合併到 main、打 Tag、推送）, (2) 發布前健康檢查（所有 Ticket 完成？CHANGELOG 更新？）, (3) 更新版本文件（worklog 狀態、CHANGELOG）。Use when: 準備發布版本、執行 /version-release check 確認發布前狀態、完成所有 Ticket 後要收尾時。"
---

# Version Release Skill

版本發布整合工具。結合工作日誌檢查、CHANGELOG 更新、Git 操作（合併、Tag、推送、清理）。

## 三步驟發布流程

1. **Pre-flight 檢查** - 驗證 Ticket 完成度、技術債務、版本同步
2. **文件更新** - 清理 todolist、更新 CHANGELOG、確認版本號
3. **Git 操作** - 合併、建立 Tag、推送、清理分支

> 各步驟的完整偽程式碼和檢查邏輯：`references/release-workflow-details.md`

## CLI 使用

```bash
# 啟動新版本
/version-release start --version 0.18.0 --description "測試重寫"

# 啟動新版本（預覽模式）
/version-release start --version 0.18.0 --from 0.17.2 --dry-run

# 完整發布（自動偵測版本）
/version-release release

# 指定版本 + 預覽模式
/version-release release --version 0.19 --dry-run

# 只執行檢查
/version-release check

# 只更新文件
/version-release update-docs
```

| 子命令 | 說明 |
|--------|------|
| `start` | 啟動新版本（Options: `--version`(必填)、`--from`、`--description`、`--dry-run`） |
| `release` | 完整發布流程（Options: `--version`、`--dry-run`、`--force`） |
| `check` | 只執行 Pre-flight 檢查 |
| `update-docs` | 只更新文件 |

### start 子命令

程式化版本啟動流程，完整生命週期：`start` -> `check` -> `release`。

**執行步驟**：
1. 前版本驗證（檢查 completed 狀態和 git tag）
2. 重複檢查（確認新版本不存在）
3. 更新 todolist.yaml（插入新版本條目，字串操作保留格式）
4. 建立 worklog 目錄結構和主檔案（從模板生成）
5. Bump package.json 和 manifest.json 版本號
6. 輸出摘要報告和下一步建議

## 版本偵測

偵測優先順序：`--version 參數` -> `git branch (feature/vX.Y)` -> `package.json` -> `git tag`

## 版本策略（Chrome Extension 雙版本來源）

| 來源 | 檔案 | 說明 |
|------|------|------|
| NPM 版本 | `package.json` | 專案主版本，Ticket/Wave 以此為準 |
| Chrome 版本 | `manifest.json` | Chrome Web Store 發布版本 |

`check` 子命令驗證兩者一致，不一致視為錯誤。配置檔：`.version-release.yaml`（可選）。

## 前置條件

- Python 3.10+、Git 2.0+、`pyyaml`
- 完成 Phase 4 重構評估，技術債務已分類
- 在 `feature/v{VERSION}` 分支上，`package.json`/`manifest.json` 版本號已更新

## 使用流程檢查清單

- [ ] 所有 Ticket 已完成（無 pending/in_progress）
- [ ] 技術債務已分類到 todolist.yaml
- [ ] 運行 `check` 確認所有檢查通過
- [ ] 運行 `release --dry-run` 預覽
- [ ] 運行 `release` 完成發布
- [ ] 驗證 main 分支已更新、Tag 已建立、feature 分支已清理

## 參考資料

| 資料 | 說明 |
|------|------|
| `references/release-workflow-details.md` | 三步驟完整偽程式碼和檢查邏輯 |
| `references/cli-output-examples.md` | CLI 輸出範例和版本偵測說明 |
| `references/troubleshooting.md` | 常見問題和恢復指引 |

**相關 Skill**: `tech-debt-capture`（Phase 4 技術債務提取）

---

**Last Updated**: 2026-04-01
**Version**: 1.0.0
