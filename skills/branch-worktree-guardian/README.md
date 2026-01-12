# Branch Worktree Guardian - 快速參考

## 30 秒快速開始

### 新開發需求建立流程

```bash
# 在 main 分支的專案目錄中執行
git checkout main && git pull

# 創建分支和 worktree（一行完成）
git checkout -b feat/my-feature && \
git worktree add ../project-my-feature feat/my-feature && \
cd ../project-my-feature

# 確認
git branch --show-current  # 應顯示: feat/my-feature
```

## 常用命令

| 操作 | 命令 |
|-----|------|
| 查看所有 worktree | `git worktree list` |
| 查看當前分支 | `git branch --show-current` |
| 創建 worktree | `git worktree add <path> <branch>` |
| 移除 worktree | `git worktree remove <path>` |
| 驗證分支 | `python .claude/skills/branch-worktree-guardian/scripts/verify_branch.py` |

## 保護分支列表

以下分支會觸發 Hook 警告：
- `main`
- `master`
- `develop`
- `release/*`

## Worktree 命名規範

格式：`{project-name}-{branch-short-name}`

範例：
- `book_overview_app-5w1h-skill`
- `book_overview_app-ui-fix`

## 發現在錯誤分支時的修復步驟

```bash
git stash                                    # 暫存變更
git checkout -b feat/correct-branch          # 建立正確分支
git worktree add ../project-correct feat/correct-branch
cd ../project-correct                        # 切換目錄
git stash pop                                # 恢復變更
```

## Hook 觸發說明

- **PreToolUse (Edit/Write)**：編輯前檢查分支，在保護分支上會詢問是否繼續
- **SessionStart**：啟動時顯示分支狀態和 worktree 列表
