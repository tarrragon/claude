# Tracking 追蹤索引規範

## 追蹤檔案

位置：`docs/proposals-tracking.yaml`

## 格式

```yaml
proposals:
  PROP-NNN:
    title: "提案標題"
    status: draft / discussing / confirmed / implemented / withdrawn
    proposed: "YYYY-MM-DD"
    confirmed: null
    target_version: "vX.Y.Z"
    source: "development / bug-fix / user-feedback / tech-debt / spec"
    spec_refs: []
    usecase_refs: []
    ticket_refs: []
    checklist:
      - item: "項目描述"
        status: done / pending / in_progress
        verified_by: "ticket-id 或 null"
```

> **設計備註**：tracking.yaml 的 checklist 與 ticket 系統的職責不同。tracking 追蹤的是**需求確認進度**（提案層級），ticket 追蹤的是**任務執行進度**（實作層級）。提案可能在 ticket 完成後仍因需求變更而重新評估。

## 跨文件導航

基於 YAML frontmatter 的引用欄位：

| 起點 | 可導航到 | 透過欄位 |
|------|---------|---------|
| Proposal | Spec | spec_refs |
| Proposal | UseCase | usecase_refs |
| Proposal | Ticket | ticket_refs |
| Spec | Proposal | source_proposal |
| Spec | UseCase | related_usecases |
| UseCase | Proposal | source_proposal |
| UseCase | Spec | related_specs |
| UseCase | Ticket | ticket_refs |

### 引用格式慣例

| 欄位 | 格式 | 範例 |
|------|------|------|
| spec_refs | 相對路徑（從 docs/ 起算） | `spec/platform/platform-management.md` |
| usecase_refs | 裸 ID | `UC-01` |
| ticket_refs | 裸 ID | `{version}-W{wave}-{seq}` |
| source_proposal | 裸 ID 或裸 ID 清單（可為清單） | `PROP-001` 或 `[PROP-003, PROP-002]` |

### 正向基數（forward_cardinality）

`GRAPH_EDGE_TYPES` 每個邊型以 `forward_cardinality`（`one` / `many`）宣告其 `forward_field` 可有幾個終點；權威為 `tracking_schema.py`，`doc schema export` 匯出的 `edge_types` 同步帶出。

- `many`：欄位可寫清單；寫成純量時視為只有一項的清單。`source_proposal`（provenance）為 `many`：一個 Spec／UseCase 可有多個來源提案，純量 `PROP-001` 等同 `[PROP-001]`。
- `one`：欄位為純量（`parent_id`、`source_ticket`、`discovered_during`、`branch_from`、`return_to`）。
- 消費端讀 `source_proposal` 必須先正規化為清單，不可假設為字串。

## 查詢方式

| 方式 | 工具 | 範例 |
|------|------|------|
| 手動查看 | Read 工具 | 直接閱讀 YAML |
| CLI 查詢 | yq | `yq '.proposals[] \| select(.status == "confirmed")' proposals-tracking.yaml` |
| 未來 | /doc CLI | `/doc status` |

## 維護規則

| 時機 | 動作 |
|------|------|
| 建立提案 | 新增 tracking entry |
| 提案確認 | 更新 status + confirmed date |
| Ticket 完成 | 更新 checklist status + verified_by |
| 所有 checklist 完成 | 提案 status → implemented |
