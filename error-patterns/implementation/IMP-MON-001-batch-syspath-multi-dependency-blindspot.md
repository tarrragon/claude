---
id: IMP-MON-001
title: 批量 sys.path 修改前未盤點多重依賴導致 import 斷裂
category: implementation
severity: medium
frequency: low
first_seen: "2026-06-23"
project: monitor
status: resolved
resolution: 修復後加回 hooks 路徑
canonical_issue: null
---

## 問題描述

框架 sync-pull 後，32 個 skill hooks 的 `sys.path` 含 `parents[3] / "hooks"` 指向 `.claude/hooks/`。批量 sed 移除這些行時，未意識到 `hook_utils`（位於 `.claude/hooks/hook_utils/`）依賴此路徑。移除後所有 `from hook_utils import ...` 崩潰。

## 根因

**Why**：批量修改前只盤點了「新模組在哪」（`.claude/lib/`），未盤點「舊路徑上還有什麼別的模組」（`hook_utils`）。
**Consequence**：40 個 hook 的 stop/start/pre-tool 全部 `ModuleNotFoundError`，等同框架癱瘓。
**Action**：批量修改 sys.path / import 前，必須先列出該路徑下所有被 import 的模組，確認新路徑能覆蓋全部，再移除舊路徑。

## 防護措施

1. 批量 sys.path 修改前：`rg "from |import " <affected-files> | sort -u` 列出所有依賴模組
2. 交叉比對：每個模組在新路徑是否可達
3. 修改後立即 `py_compile` 全量驗證（本次有做但在第二輪才做）

## 分類資訊

| 屬性 | 值 |
|------|-----|
| 觸發條件 | 框架 sync-pull 後批量修正 sys.path |
| 影響範圍 | 所有 skill hooks（40 個） |
| 偵測方式 | Stop hook 執行時 ModuleNotFoundError |
| 修復成本 | 低（加回一行 sys.path） |
