# PC-001: 保護分支上編輯被靜默還原導致工作浪費

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-001 |
| 類別 | process-compliance |
| 嚴重度 | 高 |
| 發現版本 | feat/workflow-improvement |
| 發現日期 | 2026-03-04 |
| 來源 | manager SKILL.md 一致性修正 session |

### 症狀

1. 在 `main`（保護分支）上執行多個 Edit 操作
2. 每個 Edit 都顯示 `PreToolUse:Edit hook error` 但仍回傳 diff 輸出（看似成功）
3. 後續的 Edit 操作失敗：`Error: File has been unexpectedly modified`
4. 執行 `git status` 發現工作樹完全乾淨 — 所有修改已被 Hook 還原
5. 必須建立 feature 分支後重新套用全部修改（本次為 9 個 edit 操作）

### 根因

**行為模式**：Branch Worktree Guardian Hook 僅在 SessionStart 時輸出提醒訊息，但不阻止後續的 Edit/Write 操作。另一個 Hook（可能是 PreToolUse 的分支保護 Hook）在 Edit 執行後還原變更，但錯誤訊息不夠明確，導致操作者在多次修改後才發現問題。

**根本原因**：
1. SessionStart 的分支提醒是被動的「資訊訊息」，不是「強制阻止」
2. PreToolUse:Edit hook error 的錯誤訊息未明確說明「因為在保護分支上所以被還原」
3. Edit 工具回傳了 diff 輸出（看似成功），但實際上檔案被 Hook 還原了
4. 操作者在連續 9 個 edit 後才從 `git status` 發現全部無效

### 影響範圍

| 影響 | 說明 |
|------|------|
| 時間浪費 | 9 個 edit 操作 + 分析 + 重做 = 多花 ~3 分鐘 |
| Context 消耗 | 重複的 edit 操作佔用寶貴的 context 空間 |
| 信任損失 | 工具回傳成功但實際無效，降低對系統可靠性的信心 |

### 解決方案

**臨時解決**：發現後手動建立 feature 分支，重新套用所有修改。

**根本解決**（需建立 Ticket 實作）：

建立 PreToolUse Hook，在 Edit/Write 工具執行**前**檢查分支狀態：

```python
# 虛擬碼
def check_branch_before_edit(tool_name, tool_input):
    if tool_name not in ("Edit", "Write"):
        return  # 只檢查修改操作

    current_branch = get_current_branch()
    protected_branches = ["main", "master"]

    if current_branch in protected_branches:
        file_path = tool_input.get("file_path", "")
        # 允許 .claude/ 下的非程式碼修改（按 skip-gate 規則）
        # 但仍發出警告
        return {
            "decision": "block",  # 或 "warn"
            "message": f"[Branch Guard] 當前在保護分支 {current_branch} 上。"
                       f"請先建立 feature 分支或 worktree。"
                       f"建議：git checkout -b feat/your-feature"
        }
```

### 預防措施

**短期**（人工）：
- 每次 session 開始收到 Branch Worktree Guardian 提醒時，立即確認分支
- 在第一個 Edit 操作前，主動檢查 `git branch --show-current`

**長期**（Hook 自動化）：
- 建立 PreToolUse Hook 在 Edit/Write 前自動檢查
- 在保護分支上時 block 操作並輸出明確的分支切換指引
- 與現有 Branch Worktree Guardian（SessionStart）形成雙重防護

### 與現有機制的關係

| 機制 | 時機 | 行為 | 問題 |
|------|------|------|------|
| Branch Worktree Guardian (SessionStart) | Session 開始 | 提醒訊息 | 只是提醒，不阻止 |
| PreToolUse:Edit hook (現有) | Edit 執行時 | 還原修改 | 錯誤訊息不明確 |
| **PreToolUse 分支檢查 (提案)** | **Edit/Write 前** | **阻止操作** | **本 Ticket 要建立** |

### 關聯

- 修復 session: feat/workflow-improvement merge (dc235c6)
- 相關 Hook: `.claude/hooks/branch-status-reminder.py` (SessionStart)
- 相關 Skill: `/branch-worktree-guardian`

---

**Last Updated**: 2026-03-04
**Version**: 1.0.0
