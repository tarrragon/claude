---
id: ARCH-APP-001
title: 多工具版本偵測邏輯不同步
category: architecture
severity: medium
first_seen: 2026-06-22
last_seen: 2026-06-22
occurrences: 1
status: open
---

# ARCH-APP-001: 多工具版本偵測邏輯不同步

## 症狀

`ticket track board` 顯示錯誤版本（v1.0.0），`version-release check` 顯示「版本源 0.35.0 落後開發中 worklog 版本 1.0.0」。兩套工具對「當前版本」的回答不一致。

## 根因

ticket CLI 與 version-release 的版本偵測優先序完全獨立，無共同真相來源：

| 工具 | 優先序 | 讀 todolist active? |
|------|--------|-------------------|
| ticket CLI | todolist.yaml `active` → fallback work-logs 目錄掃描 | 是 |
| version-release | git branch → pubspec.yaml → worklog 目錄掃描 | 否 |

觸發條件：`version-release release` 的 git commit 步驟失敗 → 「推進下一版本為 active」步驟未執行 → todolist.yaml 無 active 版本 → ticket CLI fallback 到目錄掃描選出最高版本目錄（v1.0.0）。

## 解決方案

即時修復：手動將 todolist.yaml 中下一版本設為 `status: active`。

## 預防措施

- release 失敗後檢查 todolist 是否有 active 版本
- 長期：version-release 的 `detect_version()` 應優先讀 todolist.yaml active（另票追蹤）
- 長期：activate-next-version 步驟應與 git commit 解耦，即使 commit 失敗也能推進（另票追蹤）

## 識別方式

`ticket track board` 輸出包含「使用目錄掃描的版本」警告訊息，且顯示的版本與 pubspec.yaml 不符。

## 後續變更：發版後沒有 active 版本已屬正常

version-release 3.0.0 起，`release`／`finish` 標 completed 後預設不推進下一版，todolist 進入版本空窗（定義見 `.claude/pm-rules/version-progression.md`〈版本生命週期〉）。「發版後沒有 active 版本」不再只出現在推進步驟失敗時，上方的即時修復不再適用：

- 不要為了消除警告而手動把下一版設為 `active`。下一版要等發版後回饋檢查決定，決定後以 `version-release start --version <下一版>` 轉 active。
- 本 pattern 的風險仍在：空窗期間 ticket CLI 會退回目錄掃描。建根票一律以 `--version` 明示目標版本，不依賴後備結果。
