# CSV Ticket 追蹤方法論 - 遺留版本參考

> **已棄用** - 本方法論僅供 v0.15.x 版本向後相容查詢使用

---

## 新版本請使用

[Frontmatter Ticket 追蹤方法論](./frontmatter-ticket-tracking-methodology.md)

---

## 遺留格式說明

v0.15.x 版本使用 CSV 格式追蹤 Ticket 狀態：

| 欄位 | 說明 |
|------|------|
| ticket_id | Ticket 識別碼 |
| status | pending / in_progress / completed |
| started_at | 開始時間 |
| completed_at | 完成時間 |

### CSV 檔案範例

```csv
ticket_id,status,started_at,completed_at
T-001,completed,2025-12-25T00:30:00,2025-12-25T01:15:00
T-002,in_progress,2025-12-25T02:00:00,
T-003,pending,,
```

---

## 向後相容

- `ticket-tracker.py` 自動偵測版本格式
- v0.15.x CSV 格式為**唯讀模式**
- 新操作一律使用 v0.16.0+ Markdown 格式

---

**棄用日期**: 2025-12-27
**替代方案**: [Frontmatter Ticket 追蹤方法論](./frontmatter-ticket-tracking-methodology.md)
