---
id: PC-APP-006
title: .gitignore 排除測試 fixture 導致新環境測試失敗
category: process-compliance
severity: medium
created: "2026-07-01"
related_tickets: []
---

# PC-APP-006: .gitignore 排除測試 fixture 導致新環境測試失敗

## 症狀

- `sync-push --clean` 報告孤兒檔（本地存在但遠端已刪除）
- 新 clone 環境執行測試時 `FileNotFoundError`（fixture 檔案不存在）
- `git ls-files --error-unmatch <file>` 回報 untracked

## 根因

測試 fixture 檔案（如 `sample_events.jsonl`）在某次重構中被 `git rm` 刪除，並同時加入 `.gitignore`。之後某次操作重新產生了該檔案到本地，但因 `.gitignore` 排除而無法被 `git add` 追蹤。本地開發者感知不到問題（檔案存在），但新 clone 環境缺少該 fixture。

根因鏈：`git rm` + 加入 `.gitignore` → 本地殘留 untracked → 本地測試通過（檔案存在）→ 新環境測試失敗（檔案不存在）

## 解決方案

1. 檢查 `.gitignore` 中是否有測試 fixture 路徑
2. 確認該 fixture 是否被測試程式碼直接引用（`shutil.copy` / `open` / `Path`）
3. 若被引用：移除 `.gitignore` 中的排除行，`git add` 重新追蹤
4. 若未被引用：確認是 runtime 產物，保留 `.gitignore` 排除

```bash
# 診斷指令
git check-ignore -v <file>          # 找出匹配的 .gitignore 規則
git ls-files --error-unmatch <file> # 確認是否被追蹤
grep -rn "<filename>" .claude/hooks/tests/  # 確認是否被測試引用
```

## 預防措施

- 刪除測試相關檔案時，先 `grep -rn` 確認無引用再加入 `.gitignore`
- `.gitignore` 中 `tests/fixtures/` 下的排除規則應逐一審查：fixture 通常需要被追蹤
- 區分 **靜態 fixture**（需追蹤）和 **runtime 產物**（應排除）：靜態 fixture 被 `shutil.copy` 或直接讀取；runtime 產物由測試程式動態產生

## 辨識訊號

| 訊號 | 含義 |
|------|------|
| `sync-push` 報告孤兒檔在 `tests/fixtures/` | 可能是被 `.gitignore` 排除的靜態 fixture |
| 新 clone 測試失敗 `FileNotFoundError` | fixture 未被追蹤 |
| `git check-ignore` 命中 `tests/fixtures/` 下的檔案 | 應審查是否為誤排除 |
