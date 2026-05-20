# PC-149: Ticket complete 後合併分支 worktree 無自動清理

## 基本資訊

- **Pattern ID**: PC-149
- **分類**: 流程合規（process-compliance）
- **來源版本**: v0.18.0
- **發現日期**: 2026-05-17
- **風險等級**: 中
- **影響範圍**: 所有走 `/worktree create` + `ticket track complete` 流程的 ticket

---

## 問題描述

### 症狀

`git worktree list` 累積大量 ticket 已 complete 且分支已完全合併（`ahead=0`）的 worktree 目錄，但無人清理。長期累積：

- 浪費 disk（每個 worktree 含完整 node_modules，可達數百 MB）
- `git worktree list` 視圖污染（PM 一眼難辨「哪些是 active / 哪些是死的」）
- statusline / 視覺工具列出殭屍項目
- 部分 worktree 含 npm install 副作用（`?? node_modules` 或 `M package-lock.json`），但 branch 本體已完全合併

### 表現形式

| 階段 | 系統行為 |
|------|---------|
| `/worktree create <ticket-id>` | 建立 `../<project>-<ticket-id>` + 分支 `feat/<ticket-id>` |
| 開發 + commit | worktree 內 commit 累積 |
| 合併回 main（`git merge feat/<ticket-id>`） | 分支變 `ahead=0`，但 worktree 目錄保留 |
| `ticket track complete <id>` | 觸發 `worktree-merge-reminder-hook` 只檢查**未合併 commit**；合併後檢查通過則靜默 |
| **缺口** | 既無 hook 提醒清理，也無自動 GC | 

---

## 案例（2026-05-17 統計）

統計 `book_overview_v1` 倉庫：

| Ticket | 完成時間 | worktree dirty? | branch ahead |
|--------|---------|----------------|--------------|
| 0.18.0-W5-015 | 838h29m 前（~35 天） | clean | 0 |
| 0.18.0-W6-012.2.1 | 22h41m 前 | `?? node_modules` | 0 |
| 0.18.0-W6-012.2.2.1 | 7h9m 前 | `?? node_modules` | 0 |
| 0.18.0-W6-012.2.2.2 | 6h55m 前 | `?? node_modules` | 0 |
| 0.18.0-W6-012.7.1 | 4h8m 前 | `M package-lock.json` | 0 |
| 0.18.0-W6-012.7.2 | 3h47m 前 | `M package-lock.json` | 0 |
| 0.18.0-W6-012.7.3 | 3h41m 前 | `M package-lock.json` | 0 |
| 0.18.0-W6-012.9.1 | 3h41m 前 | clean | 0 |

8 個 worktree 全部「branch fully merged 但目錄殘留」。最久殘留 35 天。

---

## 根因分析

### 直接原因

1. **`worktree-merge-reminder-hook` 設計範圍狹窄**：hook 只在 `ticket track complete` PreToolUse 階段檢查「分支有未合併 commit」並警告。一旦合併後（`ahead=0`），hook 不再產生任何訊息，等同預設「合併後 worktree 自動消失」——但實際上 git 不會自動刪 worktree。
2. **ticket-lifecycle 缺 post-complete cleanup step**：`.claude/pm-rules/ticket-lifecycle.md` 列 ticket complete 條件（acceptance / body / commit），但未列出「合併後清理 worktree」。PM 完成 ticket 後直接進下個 ticket，殘留 worktree 無人回頭處理。
3. **無 audit 機制**：SessionStart / Stop 都沒有列出「已合併但未移除 worktree」的累積；統計只有靠 PM 偶然執行 `git worktree list` 才暴露。
4. **基類 zombie cleanup hook 範圍不重疊**：`worktree-zombie-cleanup-hook` 只處理 cc runtime 自建的 `.claude/worktrees/agent-*`（PID 死亡的）；不處理使用者建的 `../project-<ticket-id>`。兩類 worktree 路徑不同、生命週期不同、清理機制不同，後者目前無對應 GC。

### 為何長期被忽略

- 殘留 worktree 不會立即造成測試失敗或執行錯誤，屬「持續累積」型問題，每天看不出來
- PM 完成一個 ticket 後立即推進下一個（PC-009 handoff first 心態），少有「回頭看 worktree」機會
- `git worktree list` 不在 dashboard / runqueue 預設輸出，看不到視覺壓力

---

## 解決方案

### 立即清理

```bash
# 列出 ahead=0 的合併 worktree（候選清理對象）
git worktree list --porcelain | grep "^worktree " | awk '{print $2}' | while read wt; do
  branch=$(git -C "$wt" branch --show-current 2>/dev/null)
  [ -z "$branch" ] && continue
  [ "$branch" = "main" ] && continue
  ahead=$(git rev-list --count main..$branch 2>/dev/null)
  [ "$ahead" = "0" ] && echo "$wt ($branch)"
done

# 批次清理（先 dry-run 確認，再 --force）
git worktree remove --force <path>
git branch -d <branch>
```

### 系統性修復（高優先）

| 修復 | 範圍 |
|------|------|
| 擴充 `worktree-merge-reminder-hook` | PostToolUse 階段加：分支 fully merged 時推 reminder「請執行 `git worktree remove <path>`」 |
| SessionStart 加 audit | 列出「ahead=0 的 user worktree」總數，超過閾值（如 3）時警告 |
| ticket-lifecycle.md 補步驟 | complete 後 cleanup 加入正式步驟（hook 落地後再寫到規則） |

### 預防措施

| 措施 | 行動 |
|------|------|
| Hook 兩階段覆蓋 | PreToolUse 警告未合併；**PostToolUse 警告已合併未清** |
| 區分使用者 worktree vs cc runtime worktree | 兩類 GC 機制不可混用：cc runtime 用 PID 死活檢測，使用者用 ahead/merge 狀態檢測 |
| Dashboard 整合 | `ticket track dashboard` 加 `[Worktree Cleanup]` 章節顯示已合併未清項 |

---

## 相關案例

- `worktree-zombie-cleanup-hook` 處理 cc runtime worktree（PC-149 範圍外）
- `feedback_worktree_unmerged_invisible`（PC-039 系列）處理未合併產出不可見問題（**前一步**問題）；PC-149 是**後一步**問題
- W11-018 完成時 PM 因用戶提醒主動清理 → 暴露系統長期累積（trigger event）

---

## 驗證

修復後驗證：

- `ticket track complete <id>` 對「分支已合併但 worktree 未移除」狀態產生 reminder
- SessionStart 列出累積 user worktree（已合併未清）總數
- 30 天內無新增「已合併未清」worktree 累積（從清理後重新計數）

---

**Source**: book_overview_v1 2026-05-17 W11-018 完成後審計，發現 8 個 worktree 殘留至 35 天未清
