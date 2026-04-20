---
id: IMP-051
title: 新建 Hook 未同步註冊到 settings.json
category: implementation
severity: medium
first_seen: 2026-04-07
---

# IMP-051: 新建 Hook 未同步註冊到 settings.json

## 症狀

- 新建的 Hook 檔案存在於 `.claude/hooks/` 目錄
- Hook 完整性檢查報告「未註冊」
- Hook 在真實環境中不觸發（但本地測試通過）

## 根因

建立新 Hook 時只建立了 `.py` 檔案，忘記在 `settings.json` 中新增對應的註冊項目。Hook 系統只執行 `settings.json` 中註冊的 Hook。

## 解決方案

新建 Hook 時，必須同時完成：
1. 建立 `.py` 檔案
2. 在 `settings.json` 對應事件區段新增註冊
3. 確認 `hook-completeness-check.py` 不報告未註冊

## 防護措施

1. **Hook 建立檢查清單**：建立 Hook 的 AC 必須包含「settings.json 已註冊」
2. **hook-completeness-check**：SessionStart 自動檢查，但需要人工關注警告
3. **非 Hook 腳本**：應加入 `hook-exclude-list.json` 排除

## 行為模式

代理人建立檔案時專注於程式碼邏輯，容易遺漏配置層面的同步。這與 IMP-003（作用域變更未更新引用）是同類問題——修改了一處但漏了其他相關位置。
