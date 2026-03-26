# PC-025: Worktree 代理人結果整合時分支狀態不一致

## 錯誤模式

PM 整合 worktree 代理人的結果到 main 時，未先確認主倉庫當前分支，導致變更被套用到錯誤分支，stash pop 產生非相關衝突。

## 症狀

- `git stash pop` 產生與當前任務無關的衝突
- `git branch --show-current` 顯示非預期分支（如 `feat/xxx` 而非 `main`）
- 檔案存在於某分支但不存在於 main（如 `docs/tech-evaluations/`）

## 根因

1. **Session 啟動時的分支狀態可能過時**：Session 開始時 Hook 報告在 `main`，但其他 session 或 worktree 操作可能已切換分支
2. **Worktree 操作影響 shell 工作目錄**：`cd` 到 worktree 目錄後，git 指令的 context 改變；回到主目錄後可能在非預期分支
3. **Worktree 代理人的變更是未提交的**：isolation worktree 的代理人可能未 commit，需要手動複製檔案而非 cherry-pick

## 行為模式

PM 在 worktree 代理人完成後，直接嘗試合併而不驗證：
- 當前分支是否為目標分支（main）
- 變更是已提交還是未提交
- 其他分支是否有需要的檔案（如另一個代理人建立的文件）

## 正確做法

### 整合 worktree 結果的標準步驟

```bash
# Step 1: 確認主倉庫當前分支
git branch --show-current

# Step 2: 如非目標分支，先暫存再切換
git stash  # 如有未提交變更
git checkout main
git stash pop  # 如需要

# Step 3: 確認 worktree 變更狀態
cd <worktree-path> && git status --short  # 已提交 or 未提交？

# Step 4a: 如 worktree 有 commit → cherry-pick
git cherry-pick <commit-hash>

# Step 4b: 如 worktree 未提交 → 複製檔案
cp <worktree-path>/file <main-path>/file

# Step 5: 驗證後提交
dart analyze && flutter test
git add <files> && git commit
```

## 防護措施

| 措施 | 說明 |
|------|------|
| 合併前必查分支 | `git branch --show-current` 確認在目標分支 |
| 確認變更狀態 | worktree 代理人的變更可能是未提交的 |
| 避免 stash 跨分支 | stash 在不同分支 pop 容易產生無關衝突 |
| 多代理人檔案追蹤 | 不同代理人（如 parsley A 建文件、parsley B 改程式碼）的產出可能在不同位置 |

## 關聯

- **Ticket**: 0.2.0-W5-007（移除 freezed）
- **相關模式**: PC-021（Worktree 隔離機制未正確使用）
- **發現日期**: 2026-03-26

---

**Last Updated**: 2026-03-26
**Version**: 1.0.0
