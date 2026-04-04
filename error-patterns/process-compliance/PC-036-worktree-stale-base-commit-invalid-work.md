# PC-036: Worktree 分支基底過舊導致代理人工作無效

## 錯誤編號
PC-036

## 類別
process-compliance

## 症狀

- 代理人在 worktree 中完成工作，報告「測試通過」
- 嘗試 `git merge worktree-agent-xxx` 時發現會 revert 大量已完成的工作
- `git log --oneline main..worktree-agent-xxx` 顯示分支只有 1-2 個 commit
- `git log --oneline worktree-agent-xxx..main` 顯示 main 已遠遠超前（10+ commit）
- diff 顯示代理人修改的檔案與 main 版本完全不同（舊版本）

## 根因

1. **Worktree 建立時機不對**：worktree 在 N 個 session 前建立，基於當時的 main HEAD。後續 session 持續推進 main，但舊 worktree 的分支基底不會自動更新。
2. **舊 worktree 未清理**：Claude Code 不會自動清理已完成或過時的 worktree。累積的 worktree 可能被誤用。
3. **代理人缺乏基底驗證**：代理人在 worktree 中開始工作時，不會檢查自己的程式碼基底是否與 main 同步。

## 行為模式

```
Session 1: main HEAD = ec25000
  → 建立 worktree-agent-xxx（基底 ec25000）
  → 代理人可能完成也可能未完成工作

Session 2~N: main 持續推進
  → ec25000 → 5450fd8 → b7cc6c8 → ... → 79fbe99 (22 commits later)

Session N+1: 派發新代理人到 worktree（或重用舊 worktree）
  → 代理人在 ec25000 基底上工作
  → 代理人修改的檔案在 main 上已被大幅重寫
  → 代理人報告「測試通過」（針對舊版程式碼）
  → PM 嘗試合併 → 災難性 revert
```

## 影響

- 代理人的工作完全浪費（基於舊程式碼的修改無法合併）
- 代理人報告的測試結果不反映 main 的真實狀態
- PM 信任代理人的報告，可能做出錯誤的決策
- 時間和 token 浪費

## 正確做法

### 派發前

```bash
# 檢查是否有可重用的 worktree（且基底不過時）
git worktree list
git log --oneline worktree-branch..main | wc -l  # 應為 0 或很小

# 如果基底過舊，刪除重建
git worktree remove .claude/worktrees/agent-xxx --force
git branch -D worktree-agent-xxx
```

### 代理人工作開始時

```bash
# 在 worktree 中 rebase 到最新 main
git rebase main
```

### PM 驗收時

```bash
# 檢查分支落後距離
behind=$(git log --oneline worktree-agent-xxx..main | wc -l)
if [ "$behind" -gt 5 ]; then
    echo "[WARNING] worktree 分支落後 main $behind 個 commit，結果不可信"
fi
```

## 防護措施

| 措施 | 優先級 | 說明 |
|------|--------|------|
| SessionStart worktree GC | P2 | 清理超過 3 天且已合併的 worktree |
| 派發前基底檢查 | P1 | 確認 worktree 分支與 main 的距離 <= 5 |
| 代理人自動 rebase | P1 | 代理人開始工作前在 worktree 中 rebase |
| PM 驗收距離檢查 | P1 | 合併前檢查分支落後距離 |

## 與既有模式的關係

- **PC-021**：跨任務變更污染（不同問題，是多任務在同一 worktree）
- **PC-025**：合併時分支狀態不一致（後果相似，但根因是 PM 操作錯誤）
- **PC-036（本模式）**：worktree 基底過舊導致代理人工作本身就無效

## 關聯

- **Ticket**: 0.17.0-W5-006
- **發現日期**: 2026-04-04

---

**Last Updated**: 2026-04-04
**Version**: 1.0.0
