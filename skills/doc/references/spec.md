# Spec 文件規範

## 核心原則

> **Spec 是 domain knowledge 的載體**。依 domain 組織，降低理解業務知識的心智負擔。

## Domain 組織

Spec 檔案必須放在對應的 domain 子目錄下：

```
docs/spec/{domain}/{feature}.md
```

### Domain 列表

| Domain | 核心責任 | 依賴 |
|--------|---------|------|
| core | 資料模型、錯誤處理、事件系統 | 無（基礎層） |
| extraction | 從網頁提取書籍資料 | core, platform, messaging |
| platform | 平台偵測、適配器管理 | core |
| data-management | 儲存、匯入匯出、同步 | core |
| messaging | 跨 context 通訊 | core |
| page | 頁面偵測、Content Script | core, messaging |
| system | 生命週期、健康監控 | core |
| user-experience | UI、搜尋、篩選 | core, data-management |

## 模板

模板位置：`.claude/skills/doc/templates/spec-template.md`

### 必填 frontmatter

| 欄位 | 說明 |
|------|------|
| id | SPEC-NNN |
| domain | 所屬 domain（必填） |
| subdomain | 子領域（如有） |
| source_proposal | 來源提案 ID |
| related_usecases | 對應 UC |
| depends_on_domains | 依賴的 domain |

### 正文結構

| 章節 | 必填 | 說明 |
|------|------|------|
| 概述 | 是 | 一段話描述範圍 |
| 功能需求（FR-NN） | 是 | 優先級、狀態、描述、驗收標準 |
| 非功能需求（NFR-NN） | 否 | 效能、安全性等 |
| 資料模型 | 否 | 資料結構定義 |
| 變更歷史 | 是 | 版本記錄 |

## FR 狀態標記

| 標記 | 說明 |
|------|------|
| `[x] 已實作` | 程式碼已實作且有測試 |
| `部分實作` | 有基本架構但功能不完整 |
| `[ ] 未實作` | 尚未有實作 |
| `刻意暫置` | 程式碼已寫但刻意不啟用 |

## 介面規格章節指引

Spec 的「介面規格」和「資料模型」章節需要比 FR 更具體的設計細節（endpoint 路徑、參數格式、回應結構、DDL）。這些細節的來源：

| 來源 | 優先序 | 說明 |
|------|--------|------|
| 專案既有設計文件（教學/RFC/ADR） | 最高 | 若 CLAUDE.md 指向既有設計文件，介面設計以該文件為準 |
| SaaS 決策記錄 §2 介面契約段 | 次高 | 訪談中確認的介面契約 |
| 教學/範例程式碼中的具體定義 | 中 | 教學文章中的 Go interface、SQL DDL、config YAML |
| Claude 推導填補 | 最低 | 標記為 `<!-- inferred -->`（見 saas skill 推導標記規範） |

撰寫介面規格時，先查來源 1-3 再推導。推導的設計必須標記，交付時附推導項清單。

## Spec → Ticket 轉換指引

Spec 完成後轉為 ticket 時，依以下原則拆分：

| 拆分依據 | 說明 | 範例 |
|---------|------|------|
| 功能邊界 | 每個 FR 群組可獨立測試 | Storage DDL + Store + Query = 一個 ticket |
| 依賴順序 | 被依賴的先做 | interface 定義先於實作 |
| 認知負擔 | 單一 ticket 修改 ≤ 5 個檔案 | 大 FR 拆成子 ticket |

轉換後須執行三方交叉比對驗證：

1. **Spec FR ↔ Ticket**：每個 FR 至少被一個 ticket 覆蓋
2. **UC 場景 ↔ Ticket**：每個 UC 主成功/替代/例外場景都有 ticket 對應
3. **Proposal 驗收條件 ↔ Ticket**：每項驗收條件都有 ticket 對應

任一比對有遺漏即需補 ticket 或修 Spec。

## 銜接 TDD 流程

Spec/UC 轉為 TDD 流程時，見 `.claude/skills/tdd/references/doc-handoff.md`。銜接流程把 Spec FR→Phase 1 功能規格種子、UC 步驟→GWT 行為場景種子、UC 資訊鏈→整合測試映射。銜接由 TDD 端消費（`/tdd start` 時偵測 doc 文件自動觸發），doc 端不需額外操作。
