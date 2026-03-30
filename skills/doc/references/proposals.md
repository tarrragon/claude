# Proposal 文件規範

## 核心原則

> **一個提案 = 一個版本的明確功能範圍**

| 原則 | 說明 |
|------|------|
| 單版本綁定 | 提案必須綁定 target_version，禁止跨大版本設計 |
| 明確做與不做 | 必須列出 In Scope 和 Out of Scope |
| 不做 → 新提案 | Out of Scope 的項目如果未來需要，建立獨立提案 |
| 驗收對應做 | 驗收條件必須與 In Scope 項目一一對應 |

## 狀態流轉

```
draft → discussing → confirmed → implemented
                  ↘ withdrawn
```

| 狀態 | 觸發動作 |
|------|---------|
| draft | 建立提案文件 |
| discussing | 開始評估可行性 |
| confirmed | 轉化為 spec/usecase，開 ticket |
| implemented | 所有相關 ticket 完成 |
| withdrawn | 主動撤回或審查後否決，記錄理由 |

## 與 Ticket 的關係

提案是 ticket 的上游：

1. 提案 confirmed → 開立 ticket，ticket.why 引用 PROP-NNN
2. ticket 完成 → 更新 proposals-tracking.yaml checklist
3. 所有 checklist 完成 → 提案 status 改為 implemented

## 模板

模板位置：`.claude/skills/doc/templates/proposal-template.md`

### 欄位說明

| frontmatter | 必填 | 正文章節 |
|-------------|------|---------|
| id, title, status | 是 | 需求來源 |
| source, target_version | 是 | 問題描述 |
| priority | 是 | 範圍界定（In Scope / Out of Scope） |
| outputs.spec_refs/usecase_refs/ticket_refs | 是 | 驗收條件 |
| proposed_by, proposed_date | 是 | 提案方案 |
| confirmed_date | 否 | 風險與權衡 |
| related_proposals, supersedes | 否 | 討論記錄、轉化記錄 |

### Frontmatter 欄位結構化用途

| 欄位 | 用途 | 消費者 |
|------|------|--------|
| id | 唯一識別，跨文件引用的錨點 | /doc query, /doc nav |
| status | 提案生命週期狀態，驅動 /doc status 摘要 | /doc status, tracking.yaml |
| source | 需求來源分類，支援按來源篩選 | /doc list --source |
| priority | 排程優先級（P0/P1/P2） | PM 排程決策 |
| target_version | 綁定目標版本，確保單版本範圍 | /doc list --version |
| proposed_by, proposed_date | 追蹤提案歷史 | 審查記錄 |
| confirmed_date | 標記確認時間點，觸發 ticket 開立 | 流程節點 |
| outputs.spec_refs | 連結到對應的 spec 文件（相對路徑） | /doc nav 跨文件導航 |
| outputs.usecase_refs | 連結到對應的 UC 文件（裸 ID） | /doc nav 跨文件導航 |
| outputs.ticket_refs | 連結到對應的 ticket（裸 ID） | /doc nav 跨文件導航 |
| related_proposals | 關聯提案，建立提案間的依賴圖 | /doc nav |
| supersedes | 標記被取代的舊提案 | 歷史追溯 |

> outputs.* 三個欄位是跨文件導航（/doc nav）的核心資料來源。移除任何一個都會讓導航功能無法從 Proposal 連結到對應的 Spec/UC/Ticket。

## 命名規範

格式：`PROP-{NNN}-{簡短描述}.md`
範例：`PROP-001-multi-platform-isolation.md`
