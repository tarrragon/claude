# Ticket 生命週期階段詳細說明

本文件包含 Ticket 各階段的詳細流程規則。

> 精簡版（常駐載入）：.claude/pm-rules/ticket-lifecycle.md
> 操作指南：.claude/skills/ticket/SKILL.md

---

## 建立階段詳細規則

### 建立時機

| 時機 | 建立者 |
|------|-------|
| 新功能需求 | rosemary-project-manager |
| 錯誤分析後 | incident-responder |
| 階段任務開始 | rosemary-project-manager |
| 技術債務記錄 | cinnamon-refactor-owl |

### 任務層級判斷

**核心判斷問題**：「這個任務是在執行哪個 Ticket 時產生的？」

```
這個任務是否因為執行現有 Ticket 而產生？
    |
    +-- 是 → 建立該 Ticket 的子任務（{來源}.{n}）
    |
    └-- 否 → 建立新任務鏈（新的 Wx-00n）
```

| 情境 | 新 Ticket ID | 範例 |
|------|-------------|------|
| 執行 Ticket 時發現問題 | {來源}.{n} | 執行 010.4 發現問題 → 010.4.x |
| 執行子任務時發現問題 | {來源子任務}.{n} | 執行 010.4.1 發現問題 → 010.4.1.x |
| 用戶提出新需求 | 新任務鏈 | 新功能需求 → 新的 Wx-00n |
| 發現的獨立系統問題 | 新任務鏈 | 系統級問題 → 新的 Wx-00n |

### Atomic Ticket 檢查

| 檢查項目 | 標準 |
|---------|------|
| 語義檢查 | 能用「動詞 + 單一目標」表達 |
| 修改原因 | 只有一個修改原因 |
| 驗收一致 | 所有驗收條件指向同一目標 |
| 依賴獨立 | 無循環依賴 |

### 建立後品質驗收

> 背景：W16-001 暴露品質缺口 — 研究結論未完整寫入 Ticket，子任務缺乏執行上下文。

**執行者**：acceptance-auditor

**Task Summary 完整性檢查**：

- [ ] Problem Analysis 包含前置研究結論（非空白 placeholder）
- [ ] Problem Analysis 包含現況分析（數據、結構、影響範圍）
- [ ] Solution 包含具體方案（非抽象描述）
- [ ] Solution 包含執行策略（步驟、依賴、順序）

**Solution 並行化設計檢查**：

- [ ] 是否評估了任務的可拆分性（第負一層）
- [ ] 可平行的子任務已明確標記
- [ ] 依賴關係已用 blockedBy 表達
- [ ] 並行安全檢查已完成

---

## 認領階段詳細規則

| 標準流程 | 提示強度 | 說明 |
|---------|---------|------|
| 阻塞依賴檢查 | 警告 | 如有阻塞依賴，顯示警告 |
| 設計文件閱讀 | 建議 | 提醒閱讀相關規格和設計 |
| 驗收條件理解 | 建議 | 確保理解驗收標準 |
| error-patterns 查詢 | 建議 | IMP/ADJ 類型時建議查詢 |

---

## Wave 邊界操作規則

> 核心原則：Wave 是獨立的執行單位。處理「繼續 Wx」類指令時，必須只處理指定 Wave 的任務。

**禁止行為**：

| 禁止行為 | 正確做法 |
|---------|---------|
| 「繼續 W7」時使用 `ticket track summary` | 用 `grep W7-` 過濾 |
| 「繼續 W7」時處理 W6 任務 | 只處理 W7 任務 |
| 混合不同 Wave 任務 | 一次只處理一個 Wave |

---

## 執行階段詳細規則

| 標準流程 | 提示強度 | 說明 |
|---------|---------|------|
| 問題派發 incident-responder | 強制 | 遇到錯誤時強制派發 |
| 執行日誌更新 | **強制** | 完成前必須填寫 Problem Analysis / Solution / Test Results |

---

## 驗收流程詳細規則

### 驗收代理人流程

```
執行者完成工作
    |
    v
自我檢查驗收條件
    |
    v
[PM] 派發 acceptance-auditor 驗收
    |
    +-- IMP/ADJ/複雜/安全 --> 完整驗收
    +-- DOC/簡單任務 --> 簡化驗收
    |
    v
驗收通過 --> /ticket track complete --> completed
驗收失敗 --> 回到執行者修正 --> 重新驗收
```

### 驗收執行規則

| 任務類型 | 驗收深度 | 說明 |
|---------|---------|------|
| IMP/ADJ 類型 | 完整驗收 | 實作/調整任務 |
| TDD Phase 完成 | 完整驗收 | 確保品質 |
| 複雜功能 | 完整驗收 | 高風險任務 |
| 涉及安全相關 | 完整驗收 + security-reviewer | 安全審查 |
| DOC 類型 | 簡化驗收 | 結構完整性 + 驗收條件確認 |
| 簡單任務（認知負擔 < 5） | 簡化驗收 | 結構完整性 + 驗收條件確認 |

---

## Wave/任務完成收尾（強制）

> 核心原則：Wave 或批次任務完成後，PM 必須主動執行收尾確認，不可讓對話靜默結束。

**收尾步驟**（必須按順序執行）：

1. **告知變更狀態**：列出本次修改的檔案和 git 未提交狀態
2. **查詢待處理 Ticket**：檢查是否有同版本的 pending/in_progress Ticket
3. **使用 AskUserQuestion 確認收尾動作**

> AskUserQuestion 場景定義和選項模板：.claude/rules/core/askuserquestion-rules.md

---

## 提示強度說明

| 強度 | 行為 |
|------|------|
| **強制** | Hook 阻止操作 |
| **警告** | 顯示 [WARNING] 標記 |
| **建議** | 顯示檢查清單 |
| **提示** | 輕量提醒 |

---

## 完成階段錯誤學習驗證

### 執行時序（重要：先 complete，後處理 #17）

```
[1] 用戶執行: ticket track complete X
    ↓
[2] acceptance-gate-hook 觸發（PreToolUse）
    |
    ├── [阻擋] 子任務未完成 → 阻止執行（exit 2）
    |
    ├── [有新增 error-pattern] → 輸出 #17 提醒（非阻擋，exit 0）
    |
    └── [正常情況] → 輸出 #1 驗收確認提醒（非阻擋，exit 0）
    ↓
[3] ticket track complete X 執行（in_progress → completed）
    ↓
[4] PM 根據 hook 輸出，complete 後執行對應動作
    +-- [若有 #17 提醒] → AskUserQuestion #17 → 選擇後處理
    +-- [場景 #1/#2] → AskUserQuestion #1 → 確認驗收方式 → AskUserQuestion #2 → 路由下一步
```

### 死鎖防護：complete 必須先執行，#17 在 complete 後處理

> **問題根源**：error-pattern 檔案在 #17 處理後不會自動移除。若 PM 先處理 #17 再執行 complete，下一次執行 complete 時 hook 仍會觸發 #17 提醒，造成無限循環無法完成。

| 行為 | 結果 |
|------|------|
| 看到 #17 提醒 → 先處理 → 再執行 complete | 死鎖：hook 持續觸發 #17，complete 永遠等待 |
| 看到 #17 提醒 → 直接執行 complete → 完成後處理 #17 | 正確：non-blocking，一次完成 |

### AskUserQuestion #17 觸發條件

| 條件 | 說明 |
|------|------|
| 有新增 error-pattern | ticket 執行期間 `.claude/error-patterns/` 下有新增或修改的檔案 |
| 無新增 error-pattern | 跳過 #17，正常完成 |

### #17 選項

| 選項 | 說明 |
|------|------|
| 建立改進 Ticket（Recommended） | 為新增的 error-pattern 建立修復/防護 Ticket |
| 已有對應 Ticket | error-pattern 相關修復已在現有 Ticket 中 |
| 延後處理 | 記錄到 todolist.yaml，後續版本排程 |

> 場景定義詳見：.claude/rules/core/askuserquestion-rules.md（場景 #17）

---

## 相關文件

- .claude/pm-rules/ticket-lifecycle.md - 精簡版（常駐）
- .claude/rules/core/askuserquestion-rules.md - AskUserQuestion 規則
- .claude/methodologies/acceptance-criteria-methodology.md - 驗收條件方法論
- .claude/methodologies/suggestion-tracking-methodology.md - 建議追蹤方法論

---

**Last Updated**: 2026-03-11
**Version**: 1.1.0 - 新增完成階段錯誤學習驗證詳細時序和死鎖防護（W35-001.7）
