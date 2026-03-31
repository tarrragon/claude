# PC-034: 流程產出物無持久化導致跨 session 進度遺失

## 錯誤資訊

| 項目 | 值 |
|------|-----|
| 編號 | PC-034 |
| 類別 | process-compliance |
| 嚴重度 | 高 |
| 首次發現 | 2026-03-31 |
| 發現來源 | Legacy Code Workflow 步驟 0-3 實戰執行 |

## 症狀

多步驟流程（如 Legacy Code Workflow）執行到一半中斷後，下次 session 無法得知：
- 哪些步驟已完成
- 各步驟的產出物在哪裡
- 關鍵數據摘要（如測試通過率、失敗分類）
- 後續步驟需要的輸入

## 根因

流程設計定義了每個步驟的**產出物格式**（Markdown 表格、清單、摘要），但**未定義持久化策略和落地路徑**。產出物僅存在於對話 context 中，session 結束即消失。

具體缺失：
- 無進度追蹤文件記錄步驟完成狀態
- 無標準化路徑存放各步驟產出物
- 無 frontmatter 記錄 current_step 供下次 session 讀取

## 影響範圍

- 所有多步驟流程（不僅限於 Legacy Code Workflow）
- 任何需要跨 session 延續的長期任務
- 團隊協作場景（不同人接手同一流程）

## 解決方案

1. 為多步驟流程設計**評估報告模板**
2. 流程開始時強制建立報告文件
3. 每完成一個步驟立即更新報告（不等到最後回填）
4. 報告包含：步驟完成狀態、產出物路徑、關鍵數據、commit hash

已實作：`legacy-assessment-report-template.md`

## 防護措施

- 任何多步驟流程設計必須包含「進度文件」章節
- 流程文件中標注「（必要）」強制建立報告
- 每個步驟的操作流程最後一步應為「更新評估報告」

## 設計原則

**產出物必須落地**：如果一個步驟的產出物只存在於對話 context 中，那這個步驟的設計是不完整的。每個產出物都需要有明確的持久化路徑。

## 相關文件

- `.claude/skills/doc/references/legacy-code-workflow.md` - 修正後的流程（v1.5.0）
- `.claude/skills/doc/templates/legacy-assessment-report-template.md` - 評估報告模板
