# Command Entrance Gate Hook - 快速參考指南

## 如果你遇到 exit code 2（阻塊）

當執行開發命令時收到 exit code 2，表示 Ticket 驗證失敗。按以下步驟修正：

### 問題 1：「未找到待處理的 Ticket」

**症狀**：執行 `實作...` 命令時被阻止

**原因**：沒有 pending 或 in_progress 的 Ticket

**解決**：
```bash
# 1. 建立新 Ticket
/ticket create

# 2. 填寫 Ticket 基本資訊（ID、標題、描述）
# 3. 重新執行命令
```

### 問題 2：「Ticket 尚未認領」

**症狀**：Ticket 存在但狀態為 pending

**原因**：Ticket 還未被認領

**解決**：
```bash
# 1. 認領 Ticket（用實際 ID 替換 {ticket-id}）
/ticket track claim {ticket-id}

# 2. 重新執行命令
```

### 問題 3：「缺少決策樹欄位」

**症狀**：Ticket 已認領，但執行命令還是被阻止

**原因**：Ticket 缺少決策樹欄位

**解決**：

在 Ticket 中添加以下任一項：

**選項 A：在 YAML frontmatter 添加**
```yaml
---
id: 0.30.1-W2-001
title: 我的 Ticket
decision_tree_path: /path/to/decision/tree
---
```

**選項 B：在內容中添加「## 決策樹」區段**
```markdown
---
id: 0.30.1-W2-001
---

## 決策樹

該 Ticket 的決策過程如下：
1. 需求分析：[...]
2. 方案選擇：[...]
3. 實作策略：[...]
```

**選項 C：添加「## 決策流程」區段**
```markdown
## 決策流程

我選擇使用 X 的原因：
- 理由 1
- 理由 2
```

## 錯誤訊息解讀

### 完整的阻塊錯誤訊息格式

```
錯誤：[具體問題]

為什麼阻止執行：
  [為什麼此規則必要的解釋]

建議操作:
  1. [具體操作步驟]
  2. [替代方案或其他步驟]

詳見: [相關文件連結]
```

## Hook 概覽

### 何時會被觸發

- **何時**：執行包含開發命令關鍵字的命令
- **關鍵字**：實作、修復、建立、處理、重構、轉換、新增、刪除、修改、優化、改進、升級、設計、規劃、實現

### 何時會允許執行

Hook 允許執行的條件：
- ✓ 非開發命令（查詢、諮詢等）
- ✓ 有有效的 Ticket（pending 或 in_progress）
- ✓ Ticket 已被認領（status: in_progress）
- ✓ Ticket 包含決策樹欄位

### 何時會阻止執行

Hook 阻止執行的條件（返回 exit code 2）：
- ✗ 是開發命令但無 Ticket
- ✗ Ticket 存在但未被認領
- ✗ Ticket 已認領但缺少決策樹欄位

## Exit Code 說明

| Code | 含義 | 動作 |
|------|------|------|
| 0 | 允許執行 | 繼續執行命令 |
| 1 | Hook 錯誤 | 檢查日誌：`.claude/hook-logs/command-entrance-gate/` |
| 2 | 驗證失敗 | 按 Hook 輸出中的建議操作修正 |

## 常見 Ticket 模板

### 功能實作 Ticket 範例

```markdown
---
id: 0.30.1-W2-003
title: 實作搜尋功能
type: IMP
status: in_progress
decision_tree_path: .claude/decisions/search-feature.md
---

# 搜尋功能實作

## 決策樹

### 為什麼選擇本方案
- 使用者需要快速搜尋書籍
- 全文搜尋是最合適的方案
- 可利用現有資料庫索引

### 實作策略
1. 在 Domain 層建立 SearchQuery 值物件
2. 在 Application 層建立 SearchUseCase
3. 在 Presentation 層建立搜尋 Widget

### 預期的風險和對策
- 風險：大量資料搜尋性能問題
- 對策：實現資料庫索引和分頁

## 驗收條件
- [ ] 搜尋功能可正確運作
- [ ] 性能在可接受範圍內
- [ ] 所有測試通過
```

### Bug 修復 Ticket 範例

```markdown
---
id: 0.30.1-W2-004
title: 修復登入頁面崩潰問題
type: IMP
status: in_progress
decision_tree_path: .claude/decisions/login-crash-fix.md
---

## 決策樹

### 問題分析
發現使用者在輸入特殊字元時應用崩潰

### 根本原因
輸入驗證邏輯缺少邊界檢查

### 修復方案
添加 UTF-8 字元驗證和邊界檢查

## 驗收條件
- [ ] 特殊字元輸入不再導致崩潰
- [ ] 所有測試通過
- [ ] 無遺留的邊界情況
```

## 日誌檢查

### 查看詳細執行日誌

```bash
# 查看當日的檢查摘要
tail .claude/hook-logs/command-entrance-gate/checks-$(date +%Y%m%d).log

# 查看完整的執行日誌
tail -100 .claude/hook-logs/command-entrance-gate/command-entrance-gate.log
```

### 啟用詳細日誌

```bash
# 臨時啟用 DEBUG 模式
export HOOK_DEBUG=true
# 執行命令
```

## 常見問題 FAQ

### Q：為什麼我的非開發命令也被阻止？

A：Hook 可能誤識別了命令中的關鍵字。檢查你的命令是否包含：`實作、修復、建立` 等關鍵字。

### Q：我修改了 Ticket，但還是被阻止？

A：Hook 會緩存 Ticket 資訊。等待幾秒鐘後重試，或檢查決策樹欄位是否正確添加。

### Q：決策樹可以很簡短嗎？

A：可以。只要有決策樹欄位即可，內容可以簡短，但建議至少說明「為什麼選擇此方案」。

### Q：我可以跳過決策樹欄位嗎？

A：不可以。決策樹是 Skip-gate 防護機制的核心部分，是強制要求。

### Q：如何禁用此 Hook？

A：不建議禁用。Hook 是確保工作可追蹤的重要機制。如有特殊需求，請聯繫專案管理員。

## 最佳實踐

### 1. 盡早建立 Ticket

在開始開發前：
```bash
# 1. 建立 Ticket
/ticket create

# 2. 添加決策樹欄位
# 編輯 Ticket，添加 decision_tree_path 或 ## 決策樹 區段

# 3. 認領 Ticket
/ticket track claim {ticket-id}

# 4. 開始開發
```

### 2. 保持決策樹更新

隨著開發進行，保持決策樹最新：
- 發現新風險時添加對策
- 設計調整時更新決策說明
- 遇到問題時記錄解決方案

### 3. 定期檢查 Ticket

開發過程中定期檢查：
```bash
/ticket track query {ticket-id}
```

### 4. 完成後按時標記

開發完成後：
```bash
/ticket track complete {ticket-id}
```

## 相關文件

- [Skip-gate 防護機制](../../.claude/rules/forbidden/skip-gate.md)
- [Ticket 生命週期](../../.claude/rules/flows/ticket-lifecycle.md)
- [決策樹規則](../../.claude/rules/core/decision-tree.md)
- [Hook 更新詳情](COMMAND_ENTRANCE_GATE_UPDATES.md)

---

**最後更新**：2026-01-27
**版本**：2.0.0
**針對**：Command Entrance Gate Hook 阻塊式驗證
