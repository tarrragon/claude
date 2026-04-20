---
id: IMP-059
title: Auto-compaction UTF-8 截斷導致文件中文字元損壞
category: implementation
severity: medium
first_seen: 2026-04-11
---

# IMP-059: Auto-compaction UTF-8 截斷導致文件中文字元損壞

## 症狀

- 已 commit 的文件中出現 U+FFFD replacement character（顯示為方塊或問號）
- 中文字元被截斷為 1-2 個 replacement char（如「統一」變成「統��」）
- 問題出現在 session 後期（context 深度 > 15 個 commit 後）

## 根因

Claude Code 的 auto-compaction 機制在 context 接近上限時自動壓縮先前訊息。壓縮過程可能在 UTF-8 多字節字元（中文佔 3 bytes）的中間截斷，導致後續的 Edit/Write 工具呼叫中包含損壞的字元。

**觸發條件**：
- context 深度極深（本案例 16+ commit、20+ 個 Ticket 操作）
- 壓縮發生在包含中文的訊息邊界

## 影響範圍

本案例發現 3 個文件 5 處損壞：
- `.claude/pm-rules/task-splitting.md` — 2 處（統一、修復）

## 解決方案

### 事後修復

用 Python 掃描所有 session 修改的文件：

```python
with open(file, 'r') as f:
    text = f.read()
if '\ufffd' in text:
    # 找到損壞位置，手動修復
```

### 預防

1. **遵循 Handoff first 原則**：context 深度 > 10 個 commit 時強烈建議 /clear
2. **Session 結束前掃描**：commit 前用上述腳本掃描所有修改的文件
3. **長 session 後的 UTF-8 完整性檢查**：可考慮建立 PostToolUse:Write Hook 自動檢查

## 防護措施

### 短期（行為改變）

- 單一 session 不超過 10 個 commit（超過時 /clear）
- 發現文字顯示異常時立即停止寫入並掃描

### 中期（Hook 防護）

考慮建立 PostToolUse:Write Hook，在每次檔案寫入後檢查 UTF-8 完整性。若發現 U+FFFD 則警告。

## 關聯模式

- PC-009: Handoff first 原則 — context 深度過高的另一個副作用
- strategic-compact Skill — 策略性壓縮可降低風險
