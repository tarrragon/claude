# Hook 修改審核流程

Hook 是系統治理的核心基礎設施。任何 Hook 修改必須經過審核。

---

## 審核層級

| 修改類型 | 審核要求 |
|---------|---------|
| 新增 Hook | PM 評估必要性 + 測試驗證 |
| 修改既有 Hook 行為 | PM 確認影響範圍 + AST 語法驗證 |
| 刪除 Hook | PM 確認無依賴 + 記錄刪除原因 |
| 降級 Hook（如 AUTO→WARN） | 建立 Ticket 追蹤，記錄降級原因 |

---

## 驗證清單

- [ ] Python AST 語法驗證通過
- [ ] Hook 不影響其他 Hook 的運作
- [ ] settings.json 中的 Hook 註冊已更新（如適用）
- [ ] 修改原因已記錄在 Ticket 或 commit 訊息中

---

## 相關文件

- .claude/rules/core/quality-baseline.md - 品質基線（規則 4：Hook 失敗必須可見）
- .claude/pm-rules/incident-response.md - 事件回應流程

---

**Last Updated**: 2026-03-27
**Version**: 1.0.0 - 初始版本，定義 Hook 修改審核流程（0.2.1-W1-008）
