# IMP-046: git index.lock 競爭條件導致 commit 失敗

## 錯誤摘要

git commit 失敗，錯誤訊息 `fatal: Unable to create '.git/index.lock': File exists`。重複發生。

## 根因分析

PostToolUse/PreToolUse hooks（如 `agent-commit-verification-hook.py`）呼叫 `git status --porcelain`，此命令在重新整理 index 時會短暫建立 `index.lock`。當多個 git 操作同時進行時（Hook 的 git status + 主線程的 git add/commit，或背景 Agent 的 git 操作），產生競爭條件，留下殘留的 `index.lock`。

## 觸發條件

- 主線程執行 `git add && git commit` 時，Hook 同時執行 `git status`
- 背景 Agent 執行 git 操作與主線程 commit 時間重疊
- 前一個 git 命令異常中斷（如 timeout）未清理 lock

## 影響

- commit 失敗，需要手動 `rm -f .git/index.lock` 後重試
- 打斷工作流程，增加額外步驟

## 防護措施

### 短期（目前做法）

遇到 `index.lock` 錯誤時，先移除再重試：

```bash
rm -f .git/index.lock && git add <files> && git commit -m "..."
```

### 中期建議

1. **Hook 中的 git 操作加入 retry/lock 檢查**：在 Hook 中呼叫 git 命令前，檢查 index.lock 是否存在，若存在則跳過或等待
2. **Hook 中使用 `GIT_INDEX_FILE` 環境變數**：讓 Hook 的 git status 使用獨立的 index 副本，避免與主線程競爭

### 長期建議

1. 建立 PreToolUse hook 在 `git commit` 前自動清理過期的 index.lock（超過 10 秒的 lock 視為殘留）
2. 評估 Hook 中是否真的需要 git status 操作，能否用其他方式取代

## 發生次數

多次（用戶回報至少 2-3 次）

## 相關檔案

- `.claude/hooks/agent-commit-verification-hook.py` — Hook 中的 git status 呼叫
- `.git/index.lock` — 競爭條件的鎖定檔案

---

**Created**: 2026-03-29
**Source**: 0.16.1-W2-002.7 執行期間用戶回報
**Severity**: 中（可繞過但頻繁打斷）
