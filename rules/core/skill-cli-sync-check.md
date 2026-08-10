# Skill CLI 行為變更同步檢查（路由 stub）

> **完整規則**：`.claude/references/skill-cli-sync-check-rules.md`（按需讀取）。本檔僅保留觸發條件與路由。
> **涵蓋範圍**：專案內 7 個具 CLI 入口點的 skill——ticket / doc / skill-sync / worktree / version-release / project-init / mermaid-ascii。

## 何時讀完整規則

| 情境 | 必讀 |
|------|------|
| 修改任一 CLI skill 的 src（如 `.claude/skills/ticket/ticket_system/*.py`、`.claude/skills/doc/doc_system/*.py` 等） | 是 |
| `skill-cli-sync-check-hook.py` 觸發 INFO 提示 | 是 |
| 反向同步：修改 SKILL.md / pm-rules/ 涉及某 CLI skill 的行為描述 | 是 |
| 純測試碼 / 輸出格式調整（命令語意不變） | 否 |

## 行為變更速判

| 改動類型 | 屬行為變更？ |
|---------|------------|
| 新增 / 移除 / 重命名子命令 | 是 |
| 變更 flag 必填性 / 預設值 / 語意 | 是 |
| 修改 `complete` / `claim` 條件（ticket）等核心動作條件 | 是 |
| 改變命令副作用（隱式前提） | 是 |
| 純 bug fix / 輸出格式 / 測試碼 | 否 |

## 強制動作（行為變更時）

1. 完成 src 改動後、commit 前執行（依變更的 skill 代入對應 SKILL.md 路徑）：
   ```bash
   grep -rln "<skill 相關關鍵字>" .claude/skills/<skill>/SKILL.md .claude/pm-rules/
   ```
   ticket 範例：`grep -rln "ticket track\|/ticket" .claude/skills/ticket/SKILL.md .claude/pm-rules/`
2. 對每個含該 skill CLI 引用的文件，逐一確認是否與現行行為一致；不一致即更新並納入同一 commit。
3. 同步範圍過大時建立獨立 DOC Ticket 追蹤（禁止口頭延後，違反 quality-baseline 規則 5）。

## 雙層防護

| 層級 | 機制 |
|------|------|
| 自律層 | 本 stub + `.claude/references/skill-cli-sync-check-rules.md` |
| 強制層 | `.claude/hooks/skill-cli-sync-check-hook.py`（commit-level INFO 提示，含 7-skill registry，不阻擋） |

---

**Last Updated**: 2026-08-04 | **Version**: 3.0.0 — 泛化涵蓋範圍由 ticket 單一 skill 擴至 7 個具 CLI 入口點的 skill（改名 + hook 搬遷至 `.claude/hooks/`）
**Version**: 2.0.0 — 主文外移至 references/，本檔保留路由 stub
