# IMP-009：TaskOutput vs 暫存輸出檔案混淆

**錯誤碼**: IMP-009
**分類**: Implementation / Tool Usage
**風險等級**: 低（導致查詢失敗，無資料損失）
**發現日期**: 2026-03-03
**狀態**: 已記錄，已加入防護規則

---

## 症狀

看到 Bash 輸出被截斷並存檔：
```
Output too large (279.4KB). Full output saved to: .../tool-results/b8refllkc.txt
```

誤以為 `b8refllkc` 是背景任務 ID，嘗試：
```
TaskOutput(taskId: "b8refllkc")
```

結果：
```
Error: No task found with ID: b8refllkc
```

---

## 根本原因

兩種機制外觀相似但完全不同：

| 機制 | 觸發條件 | 正確查詢工具 |
|------|---------|------------|
| 背景任務 | `run_in_background: true` | `TaskOutput(taskId)` |
| 暫存輸出檔案 | 輸出 > 2KB | `Read(file_path)` 傳完整路徑 |

兩者都產生隨機 ID 格式的識別碼，但意義和使用方式完全不同。

---

## 判斷規則

```
看到隨機 ID 時
    |
    v
訊息包含「Full output saved to: /path/xxx.txt」？
    |
    +-- 是 → Read(file_path: "/完整路徑/xxx.txt")
    |
    +-- 否 → 確認是否用 run_in_background: true 啟動
                 +-- 是 → TaskOutput(taskId: "xxx")
                 +-- 否 → 重新檢查輸出
```

---

## 防護方案

### 正確讀取暫存輸出

```
# 系統訊息
Output too large. Full output saved to: /Users/mac-eric/.claude/projects/.../tool-results/b8refllkc.txt

# 正確做法：複製完整路徑到 Read 工具
Read(file_path: "/Users/mac-eric/.claude/projects/.../tool-results/b8refllkc.txt")
```

### 主動預防大輸出

在預期輸出很大時，提前限制輸出量：
```bash
# 測試：用摘要腳本
./.claude/hooks/test-summary.sh

# 一般命令：管道到 head
git log --oneline | head -20
```

---

## 相關規則

- @.claude/rules/core/bash-tool-usage-rules.md - 完整防護規範（規則二）

---

## 發現背景

**版本**: 0.31.1
**操作**: sync-claude-push.sh 大輸出後嘗試讀取
**根因鏈**: Bash 大輸出 → 系統存為暫存檔 → 誤以為是背景任務 ID → TaskOutput 失敗
**修復**: 認知更正，暫存輸出用 Read 工具
