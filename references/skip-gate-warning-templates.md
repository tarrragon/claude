# Skip-gate 警告訊息模板

本文件定義 Skip-gate 防護機制的所有標準警告訊息格式，供 Hook 系統使用。

---

## Level 1 警告訊息

### 錯誤上下文中的直接修改嘗試

```
[WARNING] Skip-gate Protection Triggered (Level 1)
- 偵測到錯誤上下文中的直接修改嘗試
- 請遵循正確流程：
  1. 執行 /pre-fix-eval
  2. 等待 incident-responder 分析
  3. 建立 Ticket
  4. 派發對應代理人

詳見: .claude/rules/forbidden/skip-gate.md
```

---

## Level 2 警告訊息

### 無 Ticket 情況

```
[WARNING] Skip-gate Protection Triggered (Level 2)
- 命令入口驗證失敗：未找到待處理的 Ticket
- 請先執行：/ticket create
- 詳見：.claude/rules/forbidden/skip-gate.md
```

### Ticket 未認領情況

```
[WARNING] Skip-gate Protection Triggered (Level 2)
- 命令入口驗證失敗：Ticket {id} 尚未認領
- 請先執行：/ticket track claim {id}
- 詳見：.claude/rules/forbidden/skip-gate.md
```

### Hook 內部警告（無 Ticket 詳細版）

```
警告：未找到待處理的 Ticket

建議操作:
1. 執行 `/ticket create` 建立新 Ticket
2. 或執行 `/ticket track claim {id}` 認領現有 Ticket

詳見: .claude/rules/core/decision-tree.md
```

### Hook 內部警告（Ticket 未認領詳細版）

```
警告：Ticket {id} 尚未認領

建議操作:
1. 執行 `/ticket track claim {ticket_id}` 認領 Ticket
2. 使用 `/ticket track query {ticket_id}` 查看詳細資訊

詳見: .claude/rules/core/decision-tree.md
```

---

## Level 3 警告訊息

### 程式碼檔案編輯嘗試

```
[ERROR] Skip-gate Protection Triggered (Level 3)
- 主線程禁止直接編輯程式碼檔案：{file_path}
- 建議操作：
  1. 確認任務是否應由代理人執行
  2. 建立對應 Ticket
  3. 派發 parsley-flutter-developer 或對應代理人
- 詳見：.claude/rules/forbidden/skip-gate.md
```

### 依賴檔案編輯嘗試

```
[ERROR] Skip-gate Protection Triggered (Level 3)
- 主線程禁止直接編輯依賴管理檔案：{file_path}
- 建議操作：
  1. 派發 system-engineer 處理依賴更新
  2. 使用 /ticket create 建立環境配置 Ticket
- 詳見：.claude/rules/forbidden/skip-gate.md
```

### 超出允許範圍的編輯

```
[ERROR] Skip-gate Protection Triggered (Level 3)
- 檔案路徑超出主線程允許編輯範圍：{file_path}
- 允許編輯的路徑：.claude/plans/*, .claude/rules/*, docs/work-logs/*, 等
- 詳見：.claude/rules/forbidden/skip-gate.md
```

---

**Last Updated**: 2026-02-06
**Version**: 1.0.0
