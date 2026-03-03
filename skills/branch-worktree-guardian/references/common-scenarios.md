# 常見情境處理

## 情境 1：發現在錯誤分支上

當發現自己在錯誤的分支上進行開發時，應該按照以下步驟修正：

```bash
# 1. 暫存當前變更
git stash

# 2. 創建正確的分支和 worktree
git checkout main
git checkout -b feat/correct-branch
git worktree add ../project-correct-branch feat/correct-branch

# 3. 切換到新 worktree
cd ../project-correct-branch

# 4. 恢復變更
git stash pop
```

### 檢查清單

- [ ] 確認目標分支名稱正確
- [ ] 使用 `git status` 驗證工作區乾淨
- [ ] 新 worktree 目錄不存在
- [ ] 變更恢復後確認代碼完整

---

## 情境 2：多個 AI 同時開發

在多代理人協作的環境中，每個代理人應該遵循以下原則：

1. **使用獨立的 worktree 目錄**
   - 避免 worktree 之間的衝突
   - 確保每個 Agent 有隔離的開發環境

2. **使用不同的分支名稱**
   - 使用明確的分支命名約定
   - 避免分支名稱衝突

3. **在 Session 開始時確認分支**
   ```bash
   git branch --show-current
   git worktree list | grep $(pwd)
   ```

### 多 Agent 場景下的最佳實踐

- 每個 Agent 應在獨立的 worktree 中工作
- 定期同步 main 分支確保信息一致
- 避免在同一分支上進行併行修改
- 使用 feature 分支完成隔離

---

## 情境 3：緊急修復需要在 main 上操作

有時需要在保護分支上進行緊急修復。Hook 會詢問是否繼續。選擇「繼續」時，應遵循以下步驟：

```bash
# 1. 明確知道這是緊急修復
# 2. 進行最小化修改
# 3. 完成後立即 commit
git add <changed-files>
git commit -m "hotfix: [description]"

# 4. 考慮是否需要 cherry-pick 到其他分支
git checkout develop
git cherry-pick <commit-hash>
```

### 風險提示

- **謹慎使用**：只在必要時才在保護分支上操作
- **最小化範圍**：只修改必要的代碼
- **記錄原因**：在 commit message 中清楚說明原因
- **及時同步**：修復完成後應同步到相關分支

### 檢查清單

- [ ] 確認這是真正的緊急修復
- [ ] 修改範圍已最小化
- [ ] 修改已測試驗證
- [ ] Commit message 清楚說明原因
- [ ] 相關分支已同步

---

## 情境 4：worktree 清理

在開發完成或不再使用某個 worktree 時，應該正確清理：

```bash
# 查看所有 worktree
git worktree list

# 移除已合併分支的 worktree（保留分支）
git worktree remove /path/to/worktree

# 移除 worktree 並刪除分支（謹慎使用）
git worktree remove /path/to/worktree
git branch -d branch-name

# 清理空的 worktree 目錄
git worktree prune
```

### 清理前檢查清單

- [ ] 確認分支已合併到主分支
- [ ] 確認沒有未提交的變更
- [ ] 確認分支對應的 PR 已合併
- [ ] 備份任何需要的補丁或說明

---

## 情境 5：分支狀態不清

當分支狀態混亂，不清楚現在在哪個分支時：

```bash
# 檢查當前分支
git branch --show-current

# 檢查所有分支及其跟蹤狀態
git branch -vv

# 檢查 worktree 狀態
git worktree list

# 驗證當前目錄的 git 信息
python .claude/skills/branch-worktree-guardian/scripts/verify_branch.py
```

### 恢復步驟

1. **識別當前狀態**：使用上述命令確認當前位置
2. **整理分支**：刪除已合併的分支，清理廢棄分支
3. **重新建立環境**：如需要，創建新的清潔 worktree
4. **文檔化**：記錄清理過程

---

**Last Updated**: 2026-03-02
