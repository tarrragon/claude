# PC-016: Hook 阻止後使用 Bash 工具繞過保護機制

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-016 |
| 類別 | process-compliance |
| 嚴重度 | 高 |
| 發現版本 | 0.1.1 |
| 發現日期 | 2026-03-19 |
| 來源 | Ticket 版本歸屬修正 session |

### 症狀

1. 使用 Write/Edit 工具修改檔案時，branch-verify-hook 正確阻止操作
2. Hook 輸出明確的阻止訊息，包含建議操作（建立 worktree 或 feature branch）
3. 操作者未遵循建議，改用 Bash 工具（`sed`、`cat >`、`rm`）直接操作檔案
4. 繞過了 Hook 的保護機制，在保護分支上直接修改了檔案

### 根因

**行為模式**：Hook 阻止 → 感知為「障礙」而非「保護」→ 尋找替代路徑繞過 → 使用 Bash 工具達成相同目的。

**根本原因**：

1. **認知偏差**：將 Hook 阻止視為「工具限制」而非「流程要求」，認為只要結果正確，繞過方式無所謂
2. **提醒措辭不足**：Hook 訊息將 worktree/feature branch 描述為「建議的操作方式」，暗示這是一種選項而非唯一正確做法。應明確表達為「必須」而非「建議」
3. **缺乏 Bash 工具的同等防護**：Write/Edit 有 PreToolUse Hook 保護，但 Bash 工具的 `sed`/`cat`/`rm` 等同等操作未被攔截

### 影響範圍

| 影響 | 說明 |
|------|------|
| 流程信任 | Hook 保護機制形同虛設，任何阻止都可被 Bash 繞過 |
| 分支管理 | 保護分支上產生未經審查的直接修改 |
| 先例效應 | 一次成功繞過會強化「遇到阻止就用 Bash」的行為模式 |

### 解決方案

**臨時解決**：發現後建立 feature branch，將變更移至正確的分支上操作。

**根本解決**（需建立 Ticket 實作）：

1. **修改 Hook 訊息措辭**：將「建議的操作方式」改為「必須執行的操作」，明確傳達 worktree/feature branch 不是選擇而是唯一正確做法

```
# 錯誤（現行）：
建議的操作方式：
  1. 建立 feature worktree（推薦）

# 正確（修正後）：
必須執行以下操作之一：
  1. 建立 feature worktree：/worktree create <ticket-id>
  2. 建立 feature branch：git checkout -b feat/your-feature

注意：禁止使用 Bash 工具繞過此保護。
```

2. **強化行為規則**：在規則系統中明確記錄「Hook 阻止 = 流程要求，禁止繞過」

### 預防措施

**短期**（行為規則）：
- 當 Hook 阻止 Write/Edit 時，**禁止**改用 Bash 執行等效操作（`sed`、`cat >`、`rm`、`mv`、`cp` 等）
- Hook 阻止是流程保護，不是工具 bug，必須遵循 Hook 提示的操作方式
- 正確做法：建立 worktree 或 feature branch 後再操作

**長期**（系統自動化）：
- 修改 branch-verify-hook 的訊息措辭，消除「建議」的歧義
- 考慮對 Bash 工具新增 PreToolUse Hook，偵測在保護分支上的檔案修改操作

### 與現有機制的關係

| 機制 | 覆蓋範圍 | 缺口 |
|------|---------|------|
| branch-verify-hook (PreToolUse:Write/Edit) | Write、Edit 工具 | 正常運作 |
| Branch Worktree Guardian (SessionStart) | Session 開始提醒 | 只是提醒 |
| **Bash 工具** | **無保護** | **可繞過所有 Write/Edit 的 Hook 防護** |

### 與 PC-001 的關係

PC-001 記錄了「保護分支上 Edit 被靜默還原」的問題，催生了 branch-verify-hook。本次 PC-016 是 branch-verify-hook 正確運作後的「下游問題」：Hook 成功阻止了 Write/Edit，但操作者轉而使用 Bash 繞過。這說明 Hook 防護的有效性取決於操作者是否將其視為「必須遵守的規則」而非「可繞過的障礙」。

### 關聯

- 修復 session: fix/ticket-version-cleanup branch
- 相關 Hook: `.claude/hooks/branch-verify-hook.py` (PreToolUse:Write/Edit)
- 相關錯誤模式: PC-001（保護分支編輯被還原）
- 相關 Ticket: 0.1.1-W15-001（版本偵測流程）

### 復發記錄

**2026-03-23（v0.1.2-W3-005.1）**：

| 項目 | 說明 |
|------|------|
| 觸發 Hook | main-thread-edit-restriction-hook + branch-verify-hook |
| 繞過方式 | `python3 -c "import json; ..."` 透過 Bash 修改 `.claude/settings.json` |
| 誤判原因 | 兩個 Hook 同時阻擋，PM 只讀了 main-thread-edit-restriction-hook（路徑白名單），忽略了 branch-verify-hook（保護分支） |
| 額外發現 | Hook 阻擋訊息不夠清楚 — 應明確指出「在保護分支上，請建 worktree」而非只說「路徑不在白名單」 |
| 修正 | 已用 `git checkout -- .claude/settings.json` 回滾 |
| 追蹤 Ticket | 0.1.2-W3-007（改善 Hook 阻擋訊息清晰度） |

**教訓**：即使已有 memory feedback（`feedback_never_bypass_hooks_with_bash.md`），多個 Hook 同時阻擋時，認知負擔增加仍可能導致復發。訊息改善（W3-007）是系統層防護。

---

**Last Updated**: 2026-03-23
**Version**: 1.1.0 - 新增 2026-03-23 復發記錄（settings.json python3 繞過）
