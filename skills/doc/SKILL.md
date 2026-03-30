---
name: doc
description: "需求追蹤文件系統（proposals/spec/usecases）的查詢、建立、導航和管理。Use for: (1) 查詢提案、規格、用例文件, (2) 建立新提案/規格/用例（從模板）, (3) 跨文件導航（從 UC 找 spec/ticket）, (4) Domain 地圖查詢, (5) 追蹤索引管理, (6) UC 測試對應驗證, (7) 提案評估與審查。Use when: user mentions PROP-, UC-, SPEC-, 功能, 需求, feature, issue, 提案, 用例, 規格, 需求文件, 需求追蹤"
---

# Doc SKILL

需求追蹤文件系統 — 管理 proposals/spec/usecases 三種需求文件。

> 與 doc-flow（管理 CHANGELOG/worklog/ticket/todolist）互補，不重疊。

---

## 四種文件類型

| 類型 | 目錄 | 核心問題 | 詳細規範 |
|------|------|---------|---------|
| Proposal | `docs/proposals/` | 為什麼要做？做什麼不做什麼？ | Read `references/proposals.md` |
| Spec | `docs/spec/{domain}/` | 功能規格是什麼？ | Read `references/spec.md` |
| UseCase | `docs/usecases/` | 使用場景和驗收標準？ | Read `references/usecases.md` |
| Tracking | `docs/proposals-tracking.yaml` | 提案進度如何？ | Read `references/tracking.md` |

---

## 命令格式

```bash
/doc <subcommand> [options]
```

> **CLI 狀態**：已實作 Python CLI，使用 `doc <subcommand>` 執行。首次使用需安裝：`(cd .claude/skills/doc && uv tool install .)`

## 子命令

| 子命令 | 用途 | 範例 |
|--------|------|------|
| `query` | 查詢文件 | `/doc query PROP-001` 或 `/doc query UC-01` |
| `list` | 列出文件 | `/doc list proposals` 或 `/doc list specs` |
| `nav` | 跨文件導航 | `/doc nav UC-01` → 相關 spec/proposal/ticket |
| `domain` | Domain 地圖 | `/doc domain extraction` |
| `status` | 追蹤狀態 | `/doc status` |
| `test-map` | UC 測試對應 | `/doc test-map UC-01` |

---

## 無子命令時的預設行為

1. 執行 `/doc status` 顯示追蹤索引摘要
2. 列出近期更新的文件

---

## 快速參考

### 文件關係圖

```
Proposal ──spec_refs──→ Spec
    │                      │
    │                 related_usecases
    │                      │
    └──usecase_refs──→ UseCase
    │                      │
    └──ticket_refs──→ Ticket（doc-flow 管理）
```

### Domain 列表

| Domain | 目錄 | 說明 |
|--------|------|------|
| core | `spec/core/` | 資料模型、錯誤處理、事件系統 |
| extraction | `spec/extraction/` | 資料提取 |
| platform | `spec/platform/` | 平台管理 |
| data-management | `spec/data-management/` | 儲存、匯出、同步 |
| messaging | `spec/messaging/` | 跨 context 通訊 |
| page | `spec/page/` | 頁面偵測 |
| system | `spec/system/` | 生命週期管理 |
| user-experience | `spec/user-experience/` | UI、搜尋 |

---

## 模板

模板是框架資產，放在 Skill 內。`docs/` 只放產物，不放模板。

| 模板 | 位置 | 用途 |
|------|------|------|
| 提案模板 | `templates/proposal-template.md` | 建立新提案 |
| 規格模板 | `templates/spec-template.md` | 建立新規格 |
| 用例模板 | `templates/usecase-template.md` | 建立新用例 |

### 使用方式

```bash
# 建立提案
cp .claude/skills/doc/templates/proposal-template.md docs/proposals/PROP-{NNN}-{desc}.md

# 建立規格
cp .claude/skills/doc/templates/spec-template.md docs/spec/{domain}/{name}.md

# 建立用例
cp .claude/skills/doc/templates/usecase-template.md docs/usecases/UC-{XX}-{desc}.md
```

---

## 參考資料

| 資料 | 說明 |
|------|------|
| `references/proposals.md` | 提案文件規範、流程、範圍界定原則 |
| `references/spec.md` | 規格文件規範、Domain 組織、FR/NFR 格式 |
| `references/usecases.md` | 用例規範、UC 測試對應要求、資訊鏈驗證 |
| `references/tracking.md` | 追蹤索引格式、跨文件導航機制 |
| `references/proposal-evaluation-guide.md` | 提案評估指南（跨專案通用的三關式審查） |

---

## 與現有系統的整合

### 與 doc-flow 的分工

| 系統 | 管理範圍 | 追蹤層級 |
|------|---------|---------|
| /doc | proposals, spec, usecases | 需求生命週期（提案 → 確認 → 實作） |
| doc-flow | CHANGELOG, worklog, ticket, todolist | 任務生命週期（建立 → 執行 → 完成） |

**協作觸發點**：

| 場景 | /doc 動作 | doc-flow 動作 |
|------|----------|--------------|
| 提案確認 | status → confirmed | 開立 ticket（/ticket create） |
| Ticket 完成 | 更新 tracking.yaml checklist | ticket 標記 complete |
| 提案評估 | 提案 draft → discussing 時，執行 `references/proposal-evaluation-guide.md` 三關式審查 | - |
| 所有 checklist 完成 | 提案 status → implemented | 版本 worklog 記錄 |

### 與 /spec Skill 的關係

| 項目 | /doc 管理的 spec | /spec Skill 產物 |
|------|-----------------|-----------------|
| 性質 | Domain 知識資產（持久） | Ticket 執行工件（臨時） |
| 位置 | `docs/spec/{domain}/` | Ticket 目錄下的 feature-spec |
| 用途 | 擴充/重構時審視 domain 設計 | TDD Phase 1 功能設計 |
| 轉化時機 | Ticket 完成後，設計成果沉澱為 domain spec | - |

### 設計決策備註

以下設計決策經過多次審查確認，記錄理由以避免重複覆議：

| 決策 | 理由 |
|------|------|
| tracking.yaml 保留 checklist | 需求生命週期（提案確認/撤回/變更）!= 任務生命週期（ticket 建立/完成）。提案可能在 ticket 完成後仍需變更 |
| CLI 保留 6 個子命令 | 查詢精確性是長期需求。文件數量增長後 grep 會產生大量不相關結果。nav 是核心功能無法用 grep 替代 |
| proposal-evaluation-guide 保持完整 | .claude/ 是跨專案通用框架。資安/UX/效能維度對其他專案類型完全適用 |
| proposal frontmatter 保持 12 欄位 | outputs.* 是跨文件導航的核心欄位，source/priority 是分類排程必要欄位。砍掉會讓 /doc nav 無法運作 |

> 完整審查歷史見 `references/review-notes.md`

### 審查記錄

審查歷史和修復記錄見 `references/review-notes.md`。

---

**Version**: 1.5.0
**Last Updated**: 2026-03-30
