---
name: branch-worktree-guardian
description: "Branch Worktree Guardian - Git 分支和 Worktree 管理工具。Use for: (1) 新開發需求時建立隔離分支, (2) 使用 worktree 機制避免分支衝突, (3) 驗證當前工作分支正確性, (4) 預防在錯誤分支上開發"
---

# Branch Worktree Guardian

Git 分支和 Worktree 管理工具，用於預防在錯誤分支上開發的問題。

## 問題背景

在多 AI Agent 同時開發或複雜的分支管理場景中，容易發生以下問題：
1. **分支混淆**：在錯誤的分支上進行開發
2. **覆蓋風險**：不同開發者的變更互相覆蓋
3. **合併混亂**：分支狀態不清導致合併困難

## 核心原則

### 1. 新開發需求 = 新分支 + 新 Worktree

```bash
# 標準流程
1. 確認 main 分支為最新
2. 創建 feature 分支
3. 創建 worktree 到獨立目錄
4. 切換到 worktree 目錄開發
```

### 2. 保護分支禁止直接編輯

保護分支列表：
- `main`
- `master`
- `develop`
- `release/*`

在這些分支上嘗試編輯時，Hook 會詢問是否繼續或建立新分支。

### 3. Worktree 命名規範

格式：`{project-name}-{branch-short-name}`

範例：
- `book_overview_app-5w1h-skill`
- `book_overview_app-branch-worktree`
- `book_overview_app-ui-unification`

---

## 快速參考

### 建立新開發環境（完整流程）

```bash
# 1. 確保 main 是最新的
git checkout main
git pull origin main

# 2. 創建 feature 分支
git checkout -b feat/your-feature-name

# 3. 創建 worktree（在專案同級目錄）
git worktree add ../project-name-feature-name feat/your-feature-name

# 4. 切換到 worktree 目錄
cd ../project-name-feature-name

# 5. 確認分支正確
git branch --show-current
```

### 查看現有 Worktree

```bash
git worktree list
```

### 清理已合併的 Worktree

```bash
# 移除 worktree（保留分支）
git worktree remove /path/to/worktree

# 移除 worktree 並刪除分支（謹慎使用）
git worktree remove /path/to/worktree
git branch -d branch-name
```

### 驗證當前分支

```bash
# 使用 SKILL 腳本
python .claude/skills/branch-worktree-guardian/scripts/verify_branch.py

# 手動檢查
git branch --show-current
git worktree list | grep $(pwd)
```

---

## 使用腳本

### create_feature_worktree.py

創建新的 feature 分支和對應的 worktree。

```bash
# 基本用法
python .claude/skills/branch-worktree-guardian/scripts/create_feature_worktree.py \
    --branch feat/new-feature \
    --worktree ../project-new-feature

# 從特定基礎分支創建
python .claude/skills/branch-worktree-guardian/scripts/create_feature_worktree.py \
    --branch feat/new-feature \
    --worktree ../project-new-feature \
    --base develop
```

### verify_branch.py

驗證當前分支是否適合編輯。

```bash
# 檢查當前目錄
python .claude/skills/branch-worktree-guardian/scripts/verify_branch.py

# 檢查指定目錄
python .claude/skills/branch-worktree-guardian/scripts/verify_branch.py --path /path/to/project
```

---

## Hook 整合

### PreToolUse Hook (branch-verify-hook.py)

在 Edit 或 Write 工具執行前自動檢查：
- 是否在保護分支上
- 如果是，詢問用戶是否繼續

### SessionStart Hook (branch-status-reminder.py)

Session 啟動時提醒：
- 當前所在分支
- 現有 worktree 列表
- 如果在保護分支，建議建立 feature 分支

---

## 常見情境處理

常見的分支管理和 worktree 操作場景包括：

1. **發現在錯誤分支上** - 快速切換到正確分支並恢復變更
2. **多個 AI 同時開發** - 使用獨立 worktree 避免衝突
3. **緊急修復** - 在保護分支上操作的風險和步驟
4. **worktree 清理** - 正確移除已完成的 worktree
5. **分支狀態混亂** - 診斷和恢復清潔環境

詳見：[常見情境處理 (common-scenarios.md)](references/common-scenarios.md)

---

## 配置說明

### settings.json 配置和保護分支自訂

Hook 整合和分支保護規則的配置說明：

詳見：[配置說明 (configuration.md)](references/configuration.md)

---

## 相關文件

- [Git Worktree 官方文件](https://git-scm.com/docs/git-worktree)
- [專案 Hook 系統方法論](../../methodologies/hook-system-methodology.md)
- [敏捷重構方法論](../../methodologies/agile-refactor-methodology.md)

---

**Last Updated**: 2026-03-18
**Version**: 1.0.0
