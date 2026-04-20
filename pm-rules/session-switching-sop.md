# 工作階段切換 SOP

> **核心理念**：PM 管理的是整個專案的流動，不是單一 Ticket 的完成。切換工作階段時必須重新掌握全局進度。

---

## 切換前：確認背景任務狀態

每次切換工作焦點（包括 `/clear` 清除 session）前，執行進度快照：

```bash
# 一條命令掌握全局（含版本進度、in_progress、pending、git status）
ticket track snapshot
```

---

## 切換時：記錄當前進度到 worklog

在 worklog 記錄：
- 目前正在進行的 Ticket 和進度
- 背景代理人各自在處理哪個 Ticket
- 下一步預期動作（等代理人回來做什麼）

---

## /clear 前的強制確認

`/clear` 會清除 session context。執行前必須確認：

| 確認項 | 原因 |
|-------|------|
| 背景代理人是否還在運行 | 完成通知會到新 session，但 context 已丟失 |
| 未提交的變更是否已 commit | /clear 不影響檔案，但記憶會丟失 |
| 當前 Ticket 進度是否已寫入 worklog | 新 session 靠 worklog 恢復 context |
| 待驗收的代理人結果是否已處理 | 避免結果被遺忘 |
| Session 中產生的原則 / 洞察是否已持久化 | Context 中的決策經驗不會自動記錄，/clear 後永久消失 |

**禁止行為**：

| 禁止 | 原因 |
|------|------|
| 未確認經驗持久化就主動建議 /clear | Session 中的隱性知識（決策理由、流程洞察、踩坑紀錄）一旦清除即永久消失 |
| 以「context 太多」為由先建議 /clear 再補文件 | 應反過來：先持久化（memory / ticket / worklog），確認完整後才考慮 /clear |
| Session 中有待後續審查的工作時 /clear | Context 本身是審查的重要輸入；審查必須在當前 session 執行 |

---

## 新 session 開始時：重建全局視野

```bash
# 快速掌握全局進度
ticket track snapshot
```

然後根據 worklog 記錄決定從哪個 Ticket 繼續。

**Context 隔離**：一個 session 只做一件事，做完 commit → handoff。

---

## 相關文件

- .claude/rules/core/pm-role.md — 核心禁令與情境路由
- .claude/pm-rules/decision-tree.md — Re-center Protocol 詳細步驟
- .claude/skills/strategic-compact/ — 策略性 Context 壓縮工具

---

**Last Updated**: 2026-04-16
**Version**: 1.0.0 — 從 rules/core/pm-role.md 拆出（W10-076.2 拆分；原檔 v3.7.0 L109-L160）
