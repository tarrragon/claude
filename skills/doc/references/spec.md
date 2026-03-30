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
