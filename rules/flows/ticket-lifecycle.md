# Ticket 生命週期流程

本文件定義 Ticket 從建立到完成的完整生命週期。

---

## 生命週期總覽

```
需求/問題產生
    |
    v
建立 Ticket (/ticket-create)
    |
    v
Ticket 狀態: pending
    |
    v
認領 Ticket (/ticket-track claim)
    |
    v
Ticket 狀態: in_progress
    |
    +-- 正常完成 --> /ticket-track complete --> 狀態: completed
    |
    +-- 無法繼續 --> /ticket-track release --> 狀態: blocked
    |                                              |
    |                                              v
    |                                         升級到 PM 處理
    |
    v
完成
```

---

## Ticket 狀態定義

| 狀態 | 說明 | 允許操作 |
|------|------|---------|
| pending | 等待處理 | claim |
| in_progress | 處理中 | complete, release |
| completed | 已完成 | - |
| blocked | 被阻塞 | claim（重新認領） |

---

## Ticket 建立流程

### 建立時機

| 時機 | 建立者 |
|------|-------|
| 新功能需求 | rosemary-project-manager |
| 錯誤分析後 | incident-responder |
| 階段任務開始 | rosemary-project-manager |
| 技術債務記錄 | cinnamon-refactor-owl |

### 建立格式

```markdown
---
id: {版本}-W{波次}-{序號}
title: {動詞} {目標}
type: IMP/RES/ANA/INV/DOC
status: pending
priority: P0/P1/P2
assignee: pending
created: {日期}
---

# {Ticket ID}: {標題}

## 目標
{目標描述}

## 驗收條件
- [ ] {條件1}
- [ ] {條件2}
```

### Atomic Ticket 檢查

| 檢查項目 | 標準 |
|---------|------|
| 語義檢查 | 能用「動詞 + 單一目標」表達 |
| 修改原因 | 只有一個修改原因 |
| 驗收一致 | 所有驗收條件指向同一目標 |
| 依賴獨立 | 無循環依賴 |

---

## Ticket 有效性驗證

### 有效 Ticket 定義

有效的 Ticket 必須滿足以下條件：

| 條件 | 說明 | 驗證方式 |
|------|------|---------|
| 決策樹欄位 | 包含 `decision_tree_path` 欄位 | YAML frontmatter 檢查 |
| 或決策樹區段 | 包含「## 決策樹路徑」Markdown 區段 | 內容檢查 |

### 驗證時機

| 時機 | 驗證者 | 動作 |
|------|-------|------|
| 建立 Ticket | /ticket-create | 自動要求填寫決策樹欄位 |
| 派發任務 | agent-ticket-validation-hook | 阻止使用無效 Ticket |
| 認領 Ticket | /ticket-track claim | 確認 Ticket 有效性 |

### 無效 Ticket 處理

無效 Ticket（缺少決策樹欄位）：
- 無法用於 Task 派發（被 Hook 阻止）
- 需要補充決策樹欄位才能使用
- 建議使用 /ticket-create 重新建立

### 補充決策樹欄位

如果 Ticket 缺少決策樹欄位，可手動補充：

1. **YAML 格式**（在 frontmatter 中）：

```yaml
decision_tree_path:
  entry_point: "第X層"
  decision_nodes:
    - layer: "X"
      question: "決策問題"
      answer: "答案"
      next_action: "下一步"
  final_decision: "最終決策"
  rationale: "決策理由"
```

2. **Markdown 格式**（在內容中）：

```markdown
## 決策樹路徑

### 進入點
- **層級**: 第X層
- **觸發條件**: ...
```

---

## Ticket 認領流程

```bash
/ticket-track claim {ticket-id}
```

### 認領規則

| 規則 | 說明 |
|------|------|
| 單一認領 | 同一時間只能有一個代理人處理 |
| 階段匹配 | 只能認領對應階段的 Ticket |
| 依賴檢查 | 前置 Ticket 必須完成 |

---

## Ticket 執行流程

```
認領 Ticket
    |
    v
執行對應階段工作
    |
    v
更新工作日誌
    |
    v
驗證驗收條件
    |
    +-- 全部通過 --> 完成 Ticket
    +-- 部分通過 --> 繼續處理或升級
    +-- 無法完成 --> 釋放 Ticket
```

---

## Ticket 完成流程

```bash
/ticket-track complete {ticket-id}
```

### 完成檢查

| 檢查項目 | 標準 |
|---------|------|
| 驗收條件 | 所有條件都已勾選 |
| 測試通過 | 相關測試全部通過 |
| 文件更新 | 相關文件已更新 |
| 工作日誌 | 執行記錄完整 |

---

## Ticket 釋放流程

### 釋放時機

| 時機 | 說明 |
|------|------|
| 被阻塞 | 依賴其他 Ticket 完成 |
| 超出範圍 | 發現需要額外工作 |
| 技術限制 | 當前無法解決 |
| 資訊不足 | 需要更多資訊 |

```bash
/ticket-track release {ticket-id}
```

---

## Ticket 類型說明

| 類型 | 代碼 | 用途 | 典型時長 |
|------|------|------|---------|
| Research | RES | 探索未知領域 | 1-2 小時 |
| Analysis | ANA | 理解現狀和問題 | 30 分鐘 - 1 小時 |
| Implementation | IMP | 執行具體任務 | 1-4 小時 |
| Investigation | INV | 深入追蹤問題根因 | 1-2 小時 |
| Documentation | DOC | 記錄和傳承經驗 | 30 分鐘 - 1 小時 |

---

## Ticket 追蹤命令

| 命令 | 用途 |
|------|------|
| `/ticket-track summary` | 查詢所有 Ticket 進度 |
| `/ticket-track query {id}` | 查詢特定 Ticket 詳情 |
| `/ticket-track claim {id}` | 認領 Ticket |
| `/ticket-track complete {id}` | 完成 Ticket |
| `/ticket-track release {id}` | 釋放 Ticket |
| `/ticket-track list` | 列出當前版本 Ticket |

---

## 與其他流程的整合

### 與 TDD 流程整合

```
Phase 0 Ticket (SA 審查)
    ↓
Phase 1 Ticket (功能設計)
    ↓
Phase 2 Ticket (測試設計)
    ↓
Phase 3a Ticket (策略規劃)
    ↓
Phase 3b Ticket (實作執行)
    ↓
Phase 4 Ticket (重構優化)
```

> 詳細流程：[tdd-flow](tdd-flow.md)

### 與事件回應流程整合

incident-responder 分析 → 建立錯誤修復 Ticket → 派發對應代理人

> 詳細流程：[incident-response](incident-response.md)

### 與技術債務流程整合

Phase 4 發現技術債務 → 記錄到工作日誌 → /tech-debt-capture → 建立技術債務 Ticket

> 詳細流程：[tech-debt](tech-debt.md)

---

## 相關文件

- [decision-tree](../core/decision-tree.md) - 主線程決策樹
- [document-system](../core/document-system.md) - 五重文件系統

---

## 變更日誌

- v2.1.0 (2026-01-27): 新增 Ticket 有效性驗證章節
  - 定義有效 Ticket 的條件（決策樹欄位）
  - 說明驗證時機和驗證者（Hook 系統）
  - 說明無效 Ticket 的處理方式
  - 提供補充決策樹欄位的格式說明
  - 與 agent-ticket-validation-hook 實作對應
- v2.0.0 (2026-01-23): 重構為 TDD 含 SA 前置審查流程版本

**Last Updated**: 2026-01-27
**Version**: 2.1.0
