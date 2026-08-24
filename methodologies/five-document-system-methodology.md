# 五重文件系統方法論 v1.0.0

> **核心理念**：每個文件有單一職責，工程師只需讀對應文件就能理解全部
>
> **完整格式範例 + 工作流程逐字命令**：`.claude/references/five-document-system-examples.md`（需照抄 worklog/技術債務/error-pattern 的格式範本，或需逐字工作流程命令序列時讀）

---

## 重要規範：禁用 Emoji

**所有五重文件系統中的文件禁止使用 emoji**（理由：交接文件需專業正式；emoji 跨環境顯示不一致；CLI 處理表格內 emoji 可能導致 Rust panic）。適用範圍：CHANGELOG、todolist、worklog、ticket、error-patterns。

> 完整規則見 `.claude/rules/core/document-format-rules.md`。

---

## 問題背景

### 原有三重文件系統的問題

| 文件 | 原設計 | 實際問題 |
|------|--------|---------|
| CHANGELOG | 用戶導向 | 職責模糊，有時過度技術化 |
| todolist.yaml | 開發追蹤 | 混合已排程/未排程的任務 |
| worklog | 詳細記錄 | 包含太多執行細節，難以快速理解大方向 |

**核心問題**：職責重疊（worklog 與 ticket 邊界不清）、資訊過載（worklog 細節太多難還原 context）、狀態混淆（todolist 混合「待處理」與「執行中」）。

---

## 五重文件定義

每個文件回答一個核心問題，職責不重疊。各文件的完整格式範本見衛星檔。

### 1. CHANGELOG.md - 版本推進記錄

**核心問題**：這個版本做了什麼改變？

| 項目 | 說明 |
|------|------|
| 目標讀者 | 其他工程師 |
| 寫作風格 | 簡潔、技術導向 |
| 更新時機 | 版本發布時 |
| 更新方式 | `/version-release` 自動觸發 |

**內容範圍**：新增功能、架構變更、Bug 修復、重大決策。
**禁止內容**：開發過程的嘗試錯誤、過度詳細的實作細節、用戶不關心的內部變更。

### 2. todolist.yaml - 結構化版本索引

**核心問題**：還有哪些問題需要處理？

| 項目 | 說明 |
|------|------|
| 目標讀者 | 開發團隊 |
| 寫作風格 | 清單形式、簡短描述 |
| 更新時機 | 持續更新 |
| 更新方式 | 手動 + `/tech-debt-capture` |

**內容範圍**：已知但尚未排程的問題、技術債務、未來版本規劃。
**關鍵規則**：已解決 -> 移除（不是標記完成）；已排程 -> 移至 worklog。

### 3. worklog - 版本企劃

**核心問題**：這個版本要達成什麼目標？怎麼規劃？

| 項目 | 說明 |
|------|------|
| 目標讀者 | 任何接手的工程師 |
| 寫作風格 | 大方向、高層次 |
| 更新時機 | 版本開始/結束 |
| 更新方式 | `/doc-flow worklog` |

**內容範圍**：版本目標（一句話）、前情提要、執行策略（Step-by-Step）、Ticket 總覽（連結到細節）、Context 還原指引。
**自給自足原則**：任何工程師不需其他 context，只讀 worklog 就能理解版本目標、設計理由、執行步驟與相關 ticket 位置。
**禁止內容**：具體程式碼變更、詳細執行日誌、問題完整分析（這些屬於 ticket）。

> worklog 的 Phase 4 章節須包含技術債務評估表格，完成後執行 `/tech-debt-capture` 建立 Ticket，確認建立成功才提交版本。技術債務表格範本與處理流程見衛星檔。

### 4. ticket - 任務執行細節

**核心問題**：這個任務的完整執行歷程是什麼？

| 項目 | 說明 |
|------|------|
| 目標讀者 | 執行者、Review 者 |
| 寫作風格 | 詳細、完整 |
| 更新時機 | 執行過程中 |
| 更新方式 | `/ticket create`, `/ticket track` |

**內容範圍**：任務來源和目標、5W1H 設計、問題分析、解決方案、測試結果、執行進度。
**格式**：Markdown + YAML Frontmatter。

### 5. error-patterns - 經驗學習系統

**核心問題**：之前遇過類似問題嗎？

| 項目 | 說明 |
|------|------|
| 目標讀者 | 所有開發者 |
| 寫作風格 | 模式化、可查詢 |
| 更新時機 | 執行 ticket 前後 |
| 更新方式 | `/error-pattern` |

**內容範圍**：錯誤症狀、根因分析、解決方案、預防措施、相關 Ticket。
**核心理念**：犯錯是行為模式，不是單一行為；收集、歸檔錯誤經驗，建立安全防護措施。

---

## 三大設計原則

### 1. 職責單一化

每個文件只回答一個核心問題：CHANGELOG（這版做了什麼改變）、todolist.yaml（還有哪些問題要處理）、worklog（這版要達成什麼目標）、ticket（這任務的執行細節）、error-patterns（之前遇過類似問題嗎）。**判斷標準**：一個文件只回答一個核心問題。

### 2. 細節下沉原則

worklog 記錄大方向、策略、目標（「要做什麼」和「為什麼」）；ticket 記錄執行細節、分析、結果（「怎麼做」「進度如何」「結果是什麼」）。

### 3. 經驗累積原則

執行 ticket 前 `/error-pattern query`（查詢既有經驗），執行後 `/error-pattern add`（記錄新發現）。**目標**：每次修復都讓系統更聰明。

---

## 文件關係圖

```
                      ┌─────────────────┐
                      │   CHANGELOG     │
                      │  (版本間差異)    │
                      └────────┬────────┘
                               │ 版本發布時提取
                      ┌────────┴────────┐
                      │    worklog      │
                      │ (版本企劃+目標)  │
                      └────────┬────────┘
                               │ 索引
           ┌───────────────────┼───────────────────┐
           │                   │                   │
    ┌──────┴──────┐     ┌──────┴──────┐     ┌──────┴──────┐
    │   ticket    │     │todolist.yaml│     │error-patterns│
    │ (執行細節)   │     │ (版本索引)   │     │ (經驗學習)   │
    └─────────────┘     └─────────────┘     └─────────────┘
```

---

## 工作流程

三個階段的概念如下；各階段的逐字命令序列見 `.claude/references/five-document-system-examples.md`（需照抄逐字指令時讀）。

| 階段 | 概念 |
|------|------|
| 開始新版本 | 從 todolist.yaml 識別問題 -> `/doc-flow worklog init`（定目標、規劃策略）-> `/ticket create` 建 tickets -> worklog 自動索引 |
| 執行任務 | `/error-pattern query`（查既有經驗）-> `/ticket track claim` 開始 -> 過程更新 ticket -> `/error-pattern add` 記錄新發現 -> `/ticket track complete` |
| 完成版本 | `/doc-flow worklog update`（更新狀態）-> `/doc-flow todo resolve`（移除已解決）-> `/version-release`（發布、自動更新 CHANGELOG） |

---

## 與舊系統的差異

| 項目 | 舊系統（三重） | 新系統（五重） |
|------|--------------|--------------|
| worklog 職責 | 詳細記錄所有內容 | 只記錄大方向和策略 |
| 執行細節 | 混在 worklog 中 | 獨立到 ticket |
| todolist.yaml | 混合所有狀態 | 只保留未排程的問題 |
| 錯誤經驗 | 零散記錄 | 系統化的 error-patterns |
| Context 還原 | 需要讀大量文件 | 只讀 worklog 即可 |

---

## 遷移策略

**決策**：只對新版本使用新格式（v0.25.1 之後使用五重文件系統；舊版本保持原樣，不遷移）。

---

## 相關 SKILL

| SKILL | 用途 |
|-------|------|
| `/doc-flow` | 五重文件系統管理 |
| `/ticket create` | 建立 Atomic Ticket |
| `/ticket track` | 追蹤 Ticket 狀態 |
| `/error-pattern` | 錯誤模式查詢/新增 |
| `/version-release` | 版本發布流程 |
| `/tech-debt-capture` | 技術債務捕獲 |

---

## 參考文件

- 完整格式範例 + 工作流程逐字命令：`.claude/references/five-document-system-examples.md`（衛星檔）
- SKILL 定義：`.claude/skills/doc-flow/SKILL.md`
- Worklog 模板：`.claude/skills/doc-flow/templates/worklog.md.template`

---

**Last Updated**: 2026-06-14
**Version**: 1.1.0 - 瘦身 336 -> <300 行（各文件格式範本/工作流程逐字命令外移衛星檔 five-document-system-examples.md，加雙向 intent 路由；全形箭頭改 ASCII；emoji meta 規範濃縮路由至 document-format-rules）
*建立日期：2026-01-13*
