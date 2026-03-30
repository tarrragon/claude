---
# 功能規格（Spec）模板
# 複製本檔案到對應的 domain 子目錄並重新命名
# 例如：docs/spec/extraction/extraction-pipeline.md

id: SPEC-NNN
title: "{規格標題}"
status: draft                    # draft / review / approved / deprecated
source_proposal: null            # 來源提案 ID，如 PROP-001
created: "YYYY-MM-DD"
updated: "YYYY-MM-DD"
version: "1.0"                   # 規格版本（非專案版本）
owner: ""                        # 負責維護此規格的角色

# Domain 歸屬
domain: ""                       # 所屬 domain：core / extraction / platform /
                                 #   data-management / messaging / page / system /
                                 #   user-experience
subdomain: null                  # 子領域（如有），如 "storage", "import-export"

# 關聯
related_usecases: []             # 對應的用例，如 [UC-01, UC-02]
related_specs: []                # 相關的其他規格（跨 domain 引用）
implements_requirements: []      # 實作的需求項目
depends_on_domains: []           # 依賴的其他 domain，如 [core, messaging]
---

# {規格標題}

## 概述

{一段話描述本規格的範圍和目的。}

## 功能需求

### FR-{NN}: {需求名稱}

| 項目 | 值 |
|------|-----|
| 優先級 | P0 / P1 / P2 |
| 來源 | {PROP-NNN 或原始需求} |
| 對應用例 | {UC-XX} |

**描述**：{需求的具體描述}

**約束條件**：

- {約束 1}
- {約束 2}

**驗收標準**：

- [ ] {可驗證的標準 1}
- [ ] {可驗證的標準 2}

---

### FR-{NN}: {需求名稱}

{...重複上方格式...}

---

## 非功能需求

### NFR-{NN}: {需求名稱}

| 項目 | 值 |
|------|-----|
| 類型 | 效能 / 安全性 / 可用性 / 相容性 |
| 指標 | {量化指標} |

**描述**：{需求的具體描述}

---

## 資料模型（如適用）

{描述相關的資料結構、欄位定義、驗證規則}

| 欄位 | 型別 | 必填 | 說明 |
|------|------|------|------|
| {欄位名} | {型別} | 是/否 | {說明} |

## 介面規格（如適用）

{API 介面、事件介面、模組間通訊的規格定義}

## 錯誤處理

| 錯誤場景 | 錯誤碼 | 處理方式 | 使用者提示 |
|---------|--------|---------|-----------|
| {場景} | {ErrorCode} | {處理} | {提示} |

## 設計約束

{列出技術限制、平台限制、向後相容性要求等}

| 約束 | 說明 | 影響 |
|------|------|------|
| {約束} | {說明} | {影響} |

## 變更歷史

| 版本 | 日期 | 變更內容 |
|------|------|---------|
| 1.0 | YYYY-MM-DD | 初始版本 |
