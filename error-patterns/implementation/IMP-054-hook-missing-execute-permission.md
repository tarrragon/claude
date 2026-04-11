---
id: IMP-054
title: Hook 腳本缺少執行權限導致靜默失敗
category: implementation
severity: high
first_seen: 2026-04-11
ticket: N/A（Session 中直接發現）
---

# IMP-054: Hook 腳本缺少執行權限導致靜默失敗

## 症狀

- Claude Code 顯示 `Failed with non-blocking status code: /bin/sh: ... Permission denied`
- Hook 看似正常但檢查從未執行
- 新建的 Hook 在 settings.json 已註冊，但不觸發

## 根因

`.claude/hooks/` 下的 `.py` 檔案缺少執行權限（`chmod +x`）。shell 嘗試直接執行腳本時因 `Permission denied` 失敗。

常見發生場景：
1. 代理人用 Write 工具建立新 Hook 檔案，預設無 `+x` 權限
2. 從其他系統複製或 git clone 後權限遺失
3. 批量建立 Hook 時遺漏權限設定

## 影響範圍

- 所有 Hook 事件（SessionStart / PreToolUse / PostToolUse / Stop）
- 2026-04-11 發現時有 45 個腳本缺少執行權限

## 解決方案

```bash
# 一次性修正所有 Hook 權限
chmod +x .claude/hooks/**/*.py
```

## 防護措施

1. **初始化流程檢查**：`hook-completeness-check.py` 新增權限掃描，SessionStart 時自動偵測並修正
2. **Hook 建立檢查清單**：建立 Hook 的 AC 必須包含「檔案已設定執行權限」
3. **與 IMP-051 聯動**：新建 Hook 時同時確認註冊（IMP-051）和權限（IMP-054）

## 行為模式

Write 工具建立檔案時不會設定執行權限，這是平台機制而非人為疏忽。必須在流程中加入自動防護，不能依賴人工記憶。與 IMP-051（未註冊）屬同類問題——建立檔案只是第一步，還需要完成配套設定。
