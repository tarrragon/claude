# 版本推進決策規則

> **核心原則**：開發過程中發現的問題，優先在當前版本處理。

---

## 版本層級語義

| 層級 | 語義 | 核心問題 |
|------|------|---------|
| **Wave** | 執行批次 | 同一個目標，分幾批做？ |
| **Patch** | 獨立可交付 | 完成後能獨立發布嗎？ |
| **Minor** | 功能里程碑 | 用戶能感知到新功能嗎？ |
| **Major** | 架構里程碑 | 系統基本能力改變了嗎？ |

---

## Q1-Q4 語義判斷

```
[Q1] 和當前版本主題相同? → 是 → 新增 Wave
                          → 否 ↓
[Q2] 完成後能獨立發布? → 是 → 推進 Patch
                        → 否 ↓
[Q3] 需當前版本完成後才能開始? → 是 → 等待後推進 Patch
                                → 否 → 可並行開發，推進 Patch
[Q4] Patch 系列達成功能里程碑? → 是 → 推進 Minor
```

---

## 快速判斷檢查清單

1. [ ] 是開發衍生問題？ YES → **當前版本處理** STOP
2. [ ] [Q1] 和當前版本主題相同？ YES → **新 Wave** STOP
3. [ ] [Q2] 完成後能獨立發布？ YES → **新 Patch** STOP
4. [ ] [Q4] 達成功能里程碑？ YES → **新 Minor**

---

## 強制規則

| 規則 | 說明 |
|------|------|
| 開發衍生不推進版本 | 流程缺口/技術債務/Bug 在當前版本處理 |
| 工具改善不推進版本 | Hook/SKILL/驗證機制在當前版本處理 |
| 版本推進需語義理由 | 必須通過 Q1-Q4 判斷 |
| 活躍版本由 todolist.yaml 決定 | `status: active` 為 Source of Truth |
| 版本邊界以 active 為準 | 版本邊界時（舊版剛完成/新版剛啟動），todolist.yaml active 版本即為「當前版本」，無需推斷 |
| .claude 工件歸活躍版本 | .claude 規則/Hook/Skill 修正歸入 active 版本，無需 Q1-Q4 判斷 |

---

## Ticket 版本歸屬規則

| 規則 | 說明 |
|------|------|
| 新 Ticket 預設歸活躍版本 | 建立 Ticket 時，版本號預設跟隨當前 active 版本，除非有明確跨版本要求 |
| 版本號不主動調整 | Ticket 版本號建立後不主動變更；只有 wave 可根據任務鏈位置調整 |
| 版本目標改變時同步處理 | 版本開發目標改變時，必須同步執行：(1) 更新版本目標設定，(2) 遷移受影響 Ticket，(3) 重新規劃 wave |

---

## Wave 獨立性原則

Wave 是相互隔離的執行單位。禁止跨 Wave 依賴和並行派發。

> 詳細 Wave 規則和 Ticket 歸屬判斷：.claude/references/version-progression-details.md

---

## 版本收尾技術債整理流程

> **觸發時機**：決策樹第八層情境 C2（版本內所有 Ticket 已完成，無任何待處理任務）
>
> **來源**：W49 實踐 — Wave 收尾多視角審查 + 版本收尾技術債批量建 Ticket 模式

版本完成後、執行 `/version-release check` 之前，**必須**整理未追蹤的技術債。

### 流程

```
情境 C2：版本無任何待處理任務
    |
    v
[強制] 檢查 todolist.yaml
    → 篩選與當前版本相關的未排程項目
    → 識別需要帶入下一版本的技術債
    |
    v
有需要建立的技術債 Ticket?
    |
    +── 是 → /ticket batch-create 批量建立（歸入下一版本）
    |         → 建立後不影響當前版本完成狀態
    |
    +── 否 → 繼續
    |
    v
[強制] /version-release check
    → AskUserQuestion #13（版本推進確認）
```

### 技術債篩選標準

| 來源 | 判斷 | 處理 |
|------|------|------|
| todolist.yaml 已記錄但未排程 | 是否與下一版本目標相關？ | 相關 → 建立 Ticket；不相關 → 保留在 todolist |
| Phase 4 `/tech-debt-capture` 產出 | 已建立 Ticket？ | 已建 → 確認版本歸屬；未建 → 補建 |
| Wave 審查發現但未處理 | 是否阻塞版本發布？ | 阻塞 → 當前版本處理；不阻塞 → 歸入下一版本 |

### 禁止行為

| 禁止 | 說明 |
|------|------|
| 跳過 todolist 檢查直接發布 | 可能遺漏已知技術債 |
| 將技術債 Ticket 建在當前版本 | 版本已完成，應歸入下一版本 |
| 只口頭記錄不建 Ticket | 必須有可追蹤的 Ticket |

---

## 相關文件

- .claude/pm-rules/monorepo-version-strategy.md - Monorepo 三層版本定義和同步規則（L1/L2/L3）
- .claude/references/version-progression-details.md - Wave 獨立性、Ticket 歸屬、二元決策流程
- .claude/references/version-decision-case-studies.md - 案例分析
- .claude/pm-rules/ticket-lifecycle.md - Ticket 生命週期

---

## 跨版本 Ticket 遷移決策

當 Ticket 需要從一個版本遷移到另一個版本時：

| 情境 | 決策 |
|------|------|
| 當前版本未完成但新版本已開始 | 評估 Ticket 是否仍相關，相關則遷移 |
| Ticket 依賴已在新版本實作的功能 | 遷移到新版本 |
| Ticket 描述的問題已被新版本解決 | 關閉並記錄原因 |

使用 `/ticket migrate` 執行遷移。

---

## 版本遷移觸發條件與判斷流程

### 觸發條件

| 觸發時機 | 說明 | 判斷入口 |
|---------|------|---------|
| 版本內所有 Ticket 完成 | 決策樹情境 C2 觸發 | 版本收尾技術債整理 → /version-release check |
| 新功能需求超出當前版本範圍 | Q1 回答「否」時 | Q2-Q4 判斷決定新版本層級 |
| todolist.yaml current_version 不一致 | Version Consistency Guard Hook 偵測 | 修正 todolist.yaml 或完成舊版本任務 |
| 舊版本有遺留未完成 Ticket | Version Consistency Guard Hook 偵測 | 評估遷移、關閉或完成 |

### 判斷流程

```
觸發遷移評估
    |
    v
[Step 1] 確認當前版本所有 Ticket 已完成
    → ticket track list --version {current} --status pending in_progress
    → 有未完成? → 先處理完成或遷移
    |
    v
[Step 2] 執行 /version-release check
    → CHANGELOG 更新? Smoke test 通過?
    |
    v
[Step 3] 更新 todolist.yaml
    → current_version: {new}
    → previous_version: {old current}
    → next_version: {new + 1}
    |
    v
[Step 4] 確認舊版本遺留 Ticket 處理方式
    → 仍相關 → /ticket migrate
    → 已解決 → 關閉並記錄原因
    → 不再相關 → 關閉並記錄原因
```

---

**Last Updated**: 2026-03-28
**Version**: 3.4.0 - 補充版本遷移觸發條件和判斷流程（0.2.1-W3-002）
