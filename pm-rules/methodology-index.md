# 方法論索引

> 完整方法論位於 `.claude/methodologies/` 目錄。

---

## 核心方法論

| 方法論 | 用途 |
|-------|------|
| 5w1h-self-awareness-methodology.md | 決策框架（六維度判斷標準 + 強制檢查 + 逃避識別，核心判準） |
| .claude/references/5w1h-self-awareness-examples.md | 5W1H 六維度完整正反判斷範例 + Hook 系統整合程式碼（衛星檔） |
| atomic-ticket-methodology.md | Ticket 設計 |
| behavior-first-tdd-methodology.md | 測試設計 |
| agile-refactor-methodology.md | 開發流程 |
| cognitive-load-design-methodology.md | 程式碼設計（WHY + 三種類型 + 來源機制 + SOLID 視角，核心判準） |
| .claude/references/cognitive-load-design-examples.md | 五大來源完整程式碼範例 + SOLID 五原則認知負擔視角詳解（衛星檔） |
| five-document-system-methodology.md | 文件管理（五重文件職責定義 + 三大設計原則 + 文件關係圖 + 工作流程概念，核心判準） |
| .claude/references/five-document-system-examples.md | worklog 自給自足範本 + 技術債務評估表格與處理流程 + error-patterns 核心理念框 + 工作流程三階段逐字命令（衛星檔） |

## 程式碼品質

| 方法論 | 用途 |
|-------|------|
| natural-language-programming-methodology.md | 命名方法論 |
| .claude/skills/compositional-writing/references/writing-code-comments.md | 註解方法論 |
| package-import-methodology.md | 導入路徑方法論（5 原則 + 開發階段檢查清單，核心判準） |
| .claude/references/package-import-language-mechanisms.md | 各語言語意化導入機制 + 跨語言程式碼範例 + Linter/自動化工具配置（衛星檔） |
| code-smell-quality-gate-methodology.md | 程式碼壞味道檢測 |
| clean-architecture-implementation-methodology.md | Clean Architecture 實作 |
| layered-architecture-quality-checking.md | 分層架構品質檢查 |

## 測試相關

| 方法論 | 用途 |
|-------|------|
| bdd-testing-methodology.md | BDD 測試 |
| hybrid-testing-strategy-methodology.md | 混合測試策略 |
| acceptance-criteria-methodology.md | 驗收標準設計（4V 原則 + 情境分類 + 檢查清單，核心判準） |
| .claude/references/acceptance-criteria-templates.md | 驗收條件格式模板三式 + 好/壞範例 + 各系統整合模板（衛星檔） |

## 流程管理

| 方法論 | 用途 |
|-------|------|
| ticket-lifecycle-management-methodology.md | Ticket 生命週期 |
| ticket-design-dispatch-methodology.md | Ticket 設計與派發 |
| tdd-ticket-integration-methodology.md | TDD 與 Ticket 整合 |
| .claude/skills/compositional-writing/references/writing-documents.md | 工作日誌撰寫 |
| suggestion-tracking-methodology.md | 建議追蹤 |

## 分析與決策

| 方法論 | 用途 |
|-------|------|
| parallel-evaluation-methodology.md | 並行評估 + 多視角分析（含視角分工、衝突處理策略、分析任務並行差異） |
| .claude/references/multi-perspective-report-templates.md | 多視角分析完整報告模板（單一視角報告 + 彙整報告，衛星檔） |
| problem-awareness-evaluation-methodology.md | 問題意識評估（三大原則 + 決策樹 + 檢查清單，核心判準） |
| .claude/references/problem-awareness-evaluation-examples.md | 三大原則完整正反範例 + Hook 系統整合程式碼 + 實戰案例分析（衛星檔） |
| personalized-consultation-methodology.md | 個人化諮詢（核心理念 + 三層機制 + 決策流程 + 陷阱概念 + 檢查清單，核心判準） |
| .claude/references/personalized-consultation-examples.md | 羽球選拍實證案例 + 五個跨領域案例完整回應 + 五種陷阱完整範例（衛星檔） |
| design-driven-refactoring-methodology.md | 設計驅動重構 |
| systematic-debugging-methodology.md | 系統性除錯（程式碼層次 unused 警告） |
| error-fix-refactor-methodology.md | 錯誤修復重構 |
| operational-error-root-cause-methodology.md | 操作錯誤三層根因分析（操作行為失誤） |

## 工具與系統

| 方法論 | 用途 |
|-------|------|
| hook-system-methodology.md | Hook 設計（系統架構 + 六大設計原則 + 階段平衡 + 生命週期與降級，核心判準） |
| .claude/references/hook-system-operations.md | Hook per-hook 程式碼詳解 + 模組化開發規範 + 跨平台部署 + 完整決策樹 + 反模式（衛星檔） |
| .claude/references/hook-system-downgrade-tracking.md | 8 Hook 降級觀察追蹤表 + Rollback 觸發條件 + 快速恢復 SOP + 觀察期評估結果（衛星檔） |
| lsp-first-development-methodology.md | LSP 優先開發 |
| migration-methodology.md | 遷移策略 |
| instant-review-mechanism-methodology.md | 即時審查機制 |
| framework-meta-methodology.md | 框架元層管理（SKILL vs 方法論分工、撰寫檢查清單、經驗分享敘事） |
| methodology-rewriting-methodology.md | 方法論改寫指南 |

## i18n 與業務

| 方法論 | 用途 |
|-------|------|
| business-layer-i18n-management-methodology.md | 業務層 i18n 管理（分層責任 + 錯誤訊息流程 + 反模式概念 + 檢查清單，核心判準） |
| .claude/references/business-layer-i18n-examples.md | 三層責任完整程式碼範例 + 參數化訊息完整範例 + 四反模式正反程式碼對照（衛星檔） |
| claude-self-check-methodology.md | 自我檢查 |

## Ticket 格式（參考）

| 文件 | 用途 |
|------|------|
| layered-ticket-methodology.md | 分層 Ticket 方法論（五層架構、單層修改、粒度標準，核心判準） |
| frontmatter-ticket-tracking-methodology.md | Frontmatter 追蹤（單一文件架構 + 欄位 schema + 操作流程概念，核心判準） |
| .claude/references/frontmatter-ticket-tracking-operations.md | 逐字 bash 命令 + frontmatter 完整範例 + 執行日誌範本 + 工具速查 + 舊版 CSV 相容（衛星檔） |
| csv-ticket-tracking-methodology.md | CSV 追蹤（已棄用） |

---

**Last Updated**: 2026-06-15
**Version**: 1.8.0 - W8-041 標籤同步：11 處用途欄「30 秒核心」標籤改為「核心判準」，對齊 W8-040 方法論新定位（框架判斷標準，非 30 秒壓縮）。版本註腳歷史保留原「30 秒核心」字樣
**Version**: 1.7.0 - 補列 package-import-language-mechanisms.md 衛星檔索引項 + 主檔用途補「30 秒核心」（程式碼品質節，W8-020.1 衛星檔原未入索引，W8-020.12 campaign 收尾 gate 補齊）
**Version**: 1.6.0 - 新增 five-document-system-examples.md 衛星檔索引項 + 主檔用途補「30 秒核心」（核心方法論節，W8-020.11 方法論瘦身校準）
**Version**: 1.5.0 - 新增 business-layer-i18n-examples.md 衛星檔索引項 + 主檔用途補「30 秒核心」（i18n 與業務節，W8-020.10 方法論瘦身校準）
**Version**: 1.4.0 - 新增 personalized-consultation-methodology.md 主檔 + personalized-consultation-examples.md 衛星檔索引項（分析與決策節，原未列入索引）（W8-020.9 方法論瘦身校準）
**Version**: 1.3.0 - 新增 frontmatter-ticket-tracking-operations.md 衛星檔索引項 + 主檔用途補「30 秒核心」（W8-020.5 方法論瘦身校準）
**Version**: 1.2.0 - 新增 problem-awareness-evaluation-examples.md 衛星檔索引項 + 主檔用途補「30 秒核心」（W8-020.3 方法論瘦身校準）
**Version**: 1.1.0 - 新增 acceptance-criteria-templates.md 衛星檔索引項（W8-020.2 方法論瘦身校準）
