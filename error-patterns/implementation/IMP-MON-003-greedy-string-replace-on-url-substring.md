---
id: IMP-MON-003
title: 貪婪字串替換誤中 URL 子字串
severity: medium
category: implementation
first_seen: 2026-06-25
frequency: low
---

## 症狀

GitHub raw URL 請求失敗（`nodename nor servname provided`），域名被截斷為 `raw.hubusercontent.com`。

## 根因

`.replace('.git', '')` 用於移除 repo URL 的 `.git` 後綴，但 `raw.githubusercontent.com` 域名中也包含 `.git` 子字串，導致域名被截斷。

**Why**：Python `str.replace()` 替換所有匹配位置，不限後綴。

## 觸發條件

對 GitHub URL 先做域名替換（`github.com` → `raw.githubusercontent.com`），再做 `.replace('.git', '')` 去後綴。兩步順序執行時 `.git` 在域名和後綴各出現一次，後者的 replace 同時命中前者。

## 修正方式

```python
# 錯誤：全域替換
url.replace(".git", "")

# 正確：僅移除後綴
url.removesuffix(".git")
```

## 防護措施

對 URL 字串操作時，優先使用位置精確的方法（`removesuffix` / `removeprefix` / `rsplit`），避免全域 `replace`。

## 相關

- 0.3.5-W1-001：sync-push + skill-sync 同時命中
