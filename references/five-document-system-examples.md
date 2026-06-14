# 五重文件系統：格式範例與工作流程逐字命令

> **用途**：本檔為 `.claude/methodologies/five-document-system-methodology.md` 的衛星參考檔，存放五重文件各自的詳細格式範本（worklog 自給自足範本、技術債務評估表格與處理流程、error-patterns 核心理念框）以及工作流程三階段的逐字命令序列。需照抄某一格式範本，或需逐字工作流程指令時按需讀取。
>
> **核心方法論（五重文件職責定義 + 三大設計原則 + 文件關係圖 + 工作流程概念，30 秒核心）**：`.claude/methodologies/five-document-system-methodology.md`（需回顧各文件的核心問題、職責邊界或設計原則時讀）

---

## worklog 自給自足範本

對應主檔「worklog - 版本企劃」節的「自給自足原則」。任何工程師不需其他 context，只讀 worklog 就能理解：

```
- 版本目標是什麼
- 為什麼這樣設計
- 執行企劃的步驟
- 相關的 ticket 在哪裡
```

---

## 技術債務評估範本與處理流程

對應主檔「worklog - 版本企劃」節的技術債務記錄要求。worklog 的 Phase 4 章節必須包含技術債務評估表格：

```markdown
## 技術債務評估

| ID | 描述 | 風險等級 | 建議處理時機 | 影響範圍 |
|----|------|---------|------------|---------|
| TD-001 | [描述] | 高/中/低/極低 | [時機] | [範圍] |
```

**處理流程**：

1. Phase 4 完成時記錄技術債務表格
2. 執行 `/tech-debt-capture` 建立 Ticket
3. 確認 Ticket 建立成功後才能提交版本

---

## error-patterns 核心理念框

對應主檔「error-patterns - 經驗學習系統」節：

```
犯錯是行為模式，不是單一行為。
收集、歸檔錯誤經驗，建立安全防護措施。
```

---

## 工作流程三階段逐字命令

對應主檔「工作流程」節的三階段概念表。本節提供每一階段的完整逐字命令序列。

### 開始新版本

```
1. 從 todolist.yaml 識別要處理的問題
2. /doc-flow worklog init v{VERSION}
   - 定義版本目標
   - 規劃執行策略
3. /ticket create
   - 建立具體 tickets
4. worklog 自動索引 tickets
```

### 執行任務

```
1. /error-pattern query <關鍵字>
   - 查詢既有經驗
2. /ticket track claim <ticket-id>
   - 開始執行
3. 執行過程更新 ticket
4. /error-pattern add
   - 記錄新發現模式
5. /ticket track complete <ticket-id>
   - 完成任務
```

### 完成版本

```
1. /doc-flow worklog update
   - 更新版本狀態
2. /doc-flow todo resolve <已解決的問題>
   - 移除已解決項目
3. /version-release
   - 發布版本
   - 自動更新 CHANGELOG
```

---

**Last Updated**: 2026-06-14
**Version**: 1.0.0 - 從 five-document-system-methodology.md 外移：worklog 自給自足範本 + 技術債務評估表格與處理流程 + error-patterns 核心理念框 + 工作流程三階段逐字命令（W8-020.11 方法論瘦身校準）
