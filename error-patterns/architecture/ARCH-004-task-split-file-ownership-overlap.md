# ARCH-004: 批量拆分檔案所有權重疊

## 基本資訊

- **Pattern ID**: ARCH-004
- **分類**: 架構設計
- **來源版本**: v0.31.0
- **發現日期**: 2026-02-26
- **風險等級**: 高
- **來源 Ticket**: 0.31.0-W24（Code Review 後的批量修正拆分）

## 問題描述

### 症狀

W24 第一次拆分（3 個 Ticket）時，多個 Ticket 都需要修改 `hook_messages.py`：
- W24-001：修復 C-001/C-002 Critical bug（修改 hook_messages.py）
- W24-003：遷移硬編碼訊息（修改 hook_messages.py + acceptance-gate + bash-edit-guard）

如果並行派發，兩個代理人同時寫入同一檔案會產生衝突或覆蓋。

### 根本原因 (5 Why 分析)

1. Why 1: 多個 Ticket 的代理人同時修改同一檔案
2. Why 2: 拆分時按「問題類型」分組，而非按「修改檔案」分組
3. Why 3: 沒有在拆分時建立「問題-檔案矩陣」
4. Why 4: 拆分策略缺乏「檔案所有權驗證」步驟
5. Why 5 (根本原因): **批量修正的拆分單元應該是「檔案」而非「問題類型」**

### 拆分演進

**第一次拆分（按問題類型，有重疊）**：

```
| Ticket  | 問題      | 觸及檔案              |
|---------|-----------|----------------------|
| W24-001 | C-001/002 | hook_messages.py     | <-- 重疊
| W24-002 | M-002/003 | 43 個 hooks          |
| W24-003 | M-004/005 | hook_messages.py + 3 | <-- 重疊
```

**第二次拆分（按檔案所有權，無重疊）**：

```
| Agent | 獨佔檔案                                              |
|-------|------------------------------------------------------|
| 1     | hook_messages.py, acceptance-gate, creation-gate, bash-edit-guard |
| 2     | hook_utils.py                                        |
| 3     | 5w1h, agent-ticket, branch-status, command-entrance  |
| 4     | handoff-auto-resume, handoff-cleanup, handoff-prompt, handoff-reminder |
| 5     | hook-health, lsp-env, main-thread-edit, parallel-suggestion |
| 6     | phase-completion, pre-fix-eval, task-dispatch, tech-debt |
| 7     | ticket-file-access, ticket-id-validator, ticket-path-guard, ticket-quality-gate |
```

關鍵改變：W24-003 被合併入 W24-001（因為都修改 hook_messages.py）。

## 解決方案

### 正確做法

**Step 1: 建立問題-檔案矩陣**

在拆分任何批量修正前，先建立矩陣：

```markdown
| 問題 ID | 觸及檔案            |
|---------|---------------------|
| C-001   | hook_messages.py    |
| C-002   | hook_messages.py    |
| M-001   | hook_utils.py       |
| M-002   | hook_a.py, hook_b.py, ... (22 個) |
| M-004   | hook_messages.py, gate_a.py |
| M-005   | hook_messages.py, bash-edit-guard.py |
```

**Step 2: 識別共用檔案，合併 Ticket**

```
hook_messages.py 被 C-001, C-002, M-004, M-005 觸及
→ 合併為 1 個 Ticket，由單一代理人獨佔
```

**Step 3: 建立檔案所有權矩陣並驗證零衝突**

```markdown
| 檔案路徑          | Ticket A | Ticket B | Ticket C | 衝突 |
|-------------------|----------|----------|----------|------|
| hook_messages.py  | W        | -        | -        | 無   |
| hook_utils.py     | -        | W        | -        | 無   |
| hook_a.py         | -        | -        | W        | 無   |
| gate.py           | W        | -        | W        | 衝突! |
```

**衝突解決**：Write-Write 衝突 → 強制合併到同一個 Ticket。

**Step 4: 分批基準**

| 修正複雜度 | 每批檔案數 | 判斷依據 |
|-----------|-----------|---------|
| 機械修正（搜尋/替換級） | 4-6 檔案 | 每檔案改動 < 5 行 |
| 結構修正（需理解上下文） | 2-4 檔案 | 每檔案需局部判斷 |
| 邏輯修正（需推理） | 1 檔案 | 每檔案都需獨立思考 |

### 錯誤做法 (避免)

| 錯誤做法 | 問題 |
|---------|------|
| 按問題類型拆分（不看檔案） | 多 Ticket 觸及同一檔案，並行時衝突 |
| 不建立問題-檔案矩陣 | 無法發現隱藏的檔案重疊 |
| 共用檔案分給不同代理人 | 並行寫入衝突 |
| 拆分後不驗證所有權矩陣 | 可能遺漏衝突 |

### 防護措施

1. **拆分前強制檢查清單**：
   - [ ] 已建立問題-檔案矩陣
   - [ ] 已識別所有共用檔案
   - [ ] 共用檔案的問題已合併到同一 Ticket
   - [ ] 檔案所有權矩陣無 Write-Write 衝突
   - [ ] 每個檔案在同一 Wave 中最多被一個 Ticket 寫入

2. **拆分單元優先級**：檔案 > 問題類型 > 架構層

## 影響統計

| 指標 | 數值 |
|------|------|
| 第一次拆分（有重疊） | 3 個 Ticket，2 個觸及 hook_messages.py |
| 第二次拆分（無重疊） | 7 個 Ticket，檔案完全隔離 |
| 重新拆分耗時 | 需要用戶反饋後重新分析和建立矩陣 |

## 相關資源

- `docs/work-logs/v0.31.0/tickets/0.31.0-W24-004.md` - W24 完整決策記錄（第 2-3 節詳述拆分演進）
- `.claude/rules/guides/task-splitting.md` - 任務拆分指南（策略 5 批量修正拆分、策略 6 檔案所有權隔離）
- `.claude/rules/guides/parallel-dispatch.md` - 並行派發指南

## 標籤

`#拆分` `#檔案所有權` `#並行派發` `#批量修正` `#Code-Review` `#Write-Write衝突`
