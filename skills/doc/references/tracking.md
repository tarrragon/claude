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

## 跨文件導航

基於 YAML frontmatter 的引用欄位：

| 起點 | 可導航到 | 透過欄位 |
|------|---------|---------|
| Proposal | Spec | outputs.spec_refs |
| Proposal | UseCase | outputs.usecase_refs |
| Proposal | Ticket | outputs.ticket_refs |
| Spec | Proposal | source_proposal |
| Spec | UseCase | related_usecases |
| UseCase | Proposal | source_proposal |
| UseCase | Spec | related_specs |
| UseCase | Ticket | ticket_refs |

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
