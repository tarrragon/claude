# 版本推進詳細規則

本文件包含版本推進的 Wave 獨立性規則、Ticket 歸屬規則和二元決策流程。

> 精簡版（常駐載入）：.claude/pm-rules/version-progression.md
> 案例分析：.claude/references/version-decision-case-studies.md

---

## 版本語義快查

- **Wave**：同版本新批次，主題相同
- **Patch**：獨立可交付，主題不同但可獨立發布
- **Minor**：用戶可感知的功能里程碑
- **Major**：系統基本能力改變，架構里程碑

---

## Wave 獨立性規則

> 核心原則：Wave 是相互隔離的執行單位。不同 Wave 的任務在執行時必須完全獨立。

| 規則 | 說明 | 範例 |
|------|------|------|
| **任務隔離** | 執行 Wx 時只處理 Wx 的任務 | 「繼續 W7」只處理 W7 任務 |
| **查詢隔離** | 查詢時過濾到當前 Wave | `ticket track list \| grep W7-` |
| **派發隔離** | 不得跨 Wave 並行派發 | W7 和 W6 任務不可並行 |
| **狀態隔離** | 各 Wave 狀態獨立追蹤 | W6 in_progress 不影響 W7 決策 |

**違規場景**：

| 違規行為 | 正確做法 |
|---------|---------|
| 「繼續 W7」時處理 W6 任務 | 只查詢並處理 W7 任務 |
| W7 和 W6 任務並行派發 | 分開處理，一次一個 Wave |
| 將 W6 進度納入 W7 決策 | W7 決策只考慮 W7 狀態 |

---

## Ticket Wave 歸屬規則

**Wave 歸屬判斷流程**：

```
新增 Ticket
    |
    v
[Q1] 這個任務與當前 Wave 的任務鏈相關嗎？
    |
    +-- 是（屬於同一任務鏈）--> 歸入當前 Wave
    |
    +-- 否（獨立任務鏈）--> 歸入新 Wave（W{n+1}）
```

**判斷標準**：

| 歸入當前 Wave | 歸入新 Wave |
|--------------|------------|
| 是當前任務的子任務 | 與當前 Wave 完全無關 |
| 修復當前 Wave 任務發現的問題 | 是獨立的新任務鏈 |
| 補充當前 Wave 任務的缺漏 | 可以完全獨立執行 |
| 依賴當前 Wave 的產出 | 不依賴當前 Wave 的任何任務 |

**禁止：跨 Wave 依賴**

| 禁止行為 | 正確做法 |
|---------|---------|
| W8 的任務依賴 W7 的任務 | 將依賴任務放入同一 Wave |
| W7 任務的 blockedBy 包含 W6 任務 | 重新規劃 Wave 歸屬 |
| 新任務鏈放入有依賴的 Wave | 獨立任務鏈放新 Wave |

---

## 版本決策流程（優先判斷）

> **已由 scope 凍結模型取代**：本節原「二元決策流程」以「.claude 工件一律直接歸入 active 版本、免除 Q1-Q4」與「開發衍生問題一律當前版本處理」為前置分支，未區分版本現在收不收票。現行判斷改以 scope 為第一道分支，完整規則見 `.claude/pm-rules/version-progression.md`〈強制規則〉與〈版本生命週期〉，本節僅同步流程圖供對照。

所有版本決策的第一步：

```
任務類型判斷
    |
    v
目標版本 scope 是否凍結？
    |
    +-- 是（凍結）→ 依問題性質分流
    |        - 品質改善（bug/技術債） → 下一個 patch
    |        - 新能力 → 下一個 minor
    |        - 框架問題（抽象可攜 + 根源在 .claude/） → canonical issue，不進本地版本判斷
    |
    +-- 否（開放）↓
    |
是開發過程中發現的問題?（含 .claude 工件修正）
    |
    +-- 是 → 本版本處理
    |        - 流程缺口 → 新增 Wave
    |        - 技術債務 → 新增 TD Ticket
    |        - Bug 修復 → 新增 Patch
    |        - 工具改善 → 新增 Wave
    |
    +-- 否 → 用戶主動新需求? YES → 執行 Q1-Q4 判斷
             否 → 維持本版本
```

> **版本邊界說明**：「當前版本」= todolist.yaml `status: active` 的版本。跨版本邊界時（舊版剛完成、新版剛啟動）無需額外推斷，直接以 active 版本為準。

---

## 活躍版本判定規則

**Source of Truth**：`docs/todolist.yaml` 中 `status: active` 的版本

| 判定優先級 | 方式 | 說明 |
|-----------|------|------|
| 1（最高） | todolist.yaml `status: active` | 語義化宣告，推薦使用 |
| 2（次要） | work-logs 目錄掃描 | Fallback，僅在 YAML 無效時使用 |

**版本狀態**：active（開發中）/ planned（規劃中）/ completed（已完成）/ paused（暫停）

---

## 相關文件

- .claude/pm-rules/version-progression.md - 精簡版（常駐）
- .claude/references/version-decision-case-studies.md - 案例分析
- .claude/pm-rules/ticket-lifecycle.md - Ticket 生命週期

---

**Last Updated**: 2026-09-23
**Version**: 1.2.0 — 二元決策流程重命名為「版本決策流程」，第一道分支改為 scope 凍結檢查（原「.claude 工件」前置分支併入 scope 開放後的本版本處理路徑），補「已由 scope 凍結模型取代」註記說明變更緣由；主規則見 `.claude/pm-rules/version-progression.md`〈版本生命週期〉。
**Version**: 1.1.0 - 二元決策流程新增 .claude 工件前置分流 + 版本邊界語義說明
