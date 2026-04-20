---
id: PC-046
title: 全域安裝的 CLI 工具使用多餘的 cd + uv run
severity: low
category: process-compliance
first_seen: "2026-04-08"
occurrences: 50+
status: active
---

# PC-046: 全域安裝的 CLI 工具使用多餘的 cd + uv run

## 問題描述

`ticket` CLI 已透過 `uv tool install` 全域安裝在 `~/.local/bin/ticket`，可在任何目錄直接執行 `ticket track ...`。但整個 session 中所有 ticket 呼叫都使用了多餘的 `(cd .claude/skills/ticket && uv run ticket ...)` 模式，浪費 shell 操作且違反 bash-tool-usage-rules.md 的 cd 規則。

## 錯誤模式

```bash
# 錯誤（多餘的 cd + uv run）
(cd .claude/skills/ticket && uv run ticket track query 0.17.3-W1-001)

# 正確（直接呼叫全域 CLI）
ticket track query 0.17.3-W1-001
```

## 影響範圍

- AGENT_PRELOAD.md 中的範例程式碼教了錯誤的呼叫方式
- 代理人會學到錯誤的 ticket 呼叫模式
- 每次呼叫多一個子 shell + uv 啟動時間

## 根因

SKILL.md 中同時列出了全域安裝和本地執行兩種方式。PM 在 session 開始時看到 SKILL.md 的本地執行範例就沿用了，沒有確認全域安裝是否已完成。

## 正確做法

| 工具 | 安裝方式 | 正確呼叫 |
|------|---------|---------|
| ticket | `uv tool install .claude/skills/ticket` | `ticket track ...` |
| doc | `uv tool install .claude/skills/doc` | `doc ...` |
| worktree | `uv tool install .claude/skills/worktree` | `worktree ...` |

只有在工具**尚未全域安裝**時才需要 `(cd ... && uv run ...)`。

## 防護措施

1. AGENT_PRELOAD.md 範例改為直接呼叫
2. PM session 開始時確認全域安裝狀態（project-init 已檢查）
