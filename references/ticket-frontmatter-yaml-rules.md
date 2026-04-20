# Ticket Frontmatter YAML 格式要求（強制）

> **目標**：確保實作型代理人修改 ticket frontmatter 時，欄位格式符合系統預期，避免 CLI 解析失敗或資料不一致。

---

## 強制欄位格式規則

實作型代理人修改 ticket frontmatter 時，必須遵守以下 YAML 格式：

| 欄位 | 格式 | 違規範例 | 正確範例 |
|------|------|---------|---------|
| `status` | enum: `pending` / `in_progress` / `completed` / `blocked` / `closed` | `complete`（缺 d） | `completed` |
| `completed_at` | ISO 8601: `YYYY-MM-DDTHH:MM:SS`（HH 範圍 00–23）或 `null` | `T24:00:00`（超出範圍） | `T23:55:57` |
| `acceptance` | YAML list，每項獨立字串 | 4 條擠單行用 `,[ ]` 分隔 | 4 個獨立 list items（見下） |
| `who` | object 含 `current` 欄位 | `who: thyme-xxx`（純字串） | `who:\n  current: thyme-xxx`（object） |

### acceptance 正確格式示範

```yaml
acceptance:
- '[ ] 第一個驗收條件'
- '[ ] 第二個驗收條件'
- '[ ] 第三個驗收條件'
- '[ ] 第四個驗收條件'
```

### who 正確格式示範

```yaml
who:
  current: thyme-documentation-integrator
  history: {}
```

---

## 正確路徑（優先用 CLI，非直接 Edit）

代理人應優先使用 CLI 命令操作 ticket 欄位，避免直接 Edit frontmatter 造成格式錯誤：

| 操作 | 正確 CLI 命令 |
|------|-------------|
| 標記 AC 全部完成 | `ticket track check-acceptance <id> --all` |
| 標記指定 AC 完成 | `ticket track check-acceptance <id> 1 2 3` |
| 設定 status（認領） | `ticket track claim <id>` |
| 設定 status（完成） | `ticket track complete <id>` |
| 更新執行日誌 | `ticket track append-log <id> "..." --section "..."` |
| 查詢 AC 狀態 | `ticket track check-acceptance <id>` |

`completed_at` 欄位由 `ticket track complete` 自動寫入，**禁止手動設定**。

---

## Edit frontmatter 合法情境

僅在以下情況允許直接 Edit frontmatter（並應在 Ticket 日誌中記錄原因）：

- CLI 無法涵蓋的欄位修正（如 schema 遷移、欄位新增）
- PM 修復歷史資料瑕疵
- 系統初始化或批量遷移作業

---

## 自我檢查清單

修改 ticket frontmatter 前，確認：

- [ ] `status` 值為 enum 允許值之一？
- [ ] `completed_at` 由 CLI 自動寫入（非手動設定）？
- [ ] `acceptance` 為 YAML list，每項獨立一行？
- [ ] `who` 為 object 而非純字串？
- [ ] 優先使用 CLI 命令而非直接 Edit？

---

## 相關文件

- `.claude/pm-rules/context-bundle-spec.md` — Context Bundle 與代理人派發規範
- `.claude/rules/core/document-format-rules.md` — 文件格式規則

---

**Last Updated**: 2026-04-18
**Version**: 1.0.0 — 初版（來源：W14-024 Phase A IMP-2，W14-029 實作）
