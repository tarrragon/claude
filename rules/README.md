# 規則系統

> **平台機制**：Claude Code 啟動時自動載入 `CLAUDE.md` + `.claude/rules/**/*.md`。其他 `.claude/` 子目錄不會自動載入，必須主動 Read。

本目錄只放**所有角色通用**的品質規則（6 檔）。PM 流程規則在 `pm-rules/`，語言專屬規則在 `references/`。

| 目錄 | 載入方式 | 內容 |
|------|---------|------|
| `rules/core/` | 自動載入 | 通用品質基線、Bash 規則、認知負擔、文件格式、語言約束 |
| `pm-rules/` | PM 按需讀取 | 決策樹、TDD、Ticket、事件回應、Skip-gate |
| `references/` | 代理人按需讀取 | 語言品質（dart/go/python）、Ticket ID 規範 |
| `agents/` | 派發時讀取 | 代理人定義 |

---

**Last Updated**: 2026-03-26
**Version**: 7.0.0 - README 回歸目錄說明，PM 約束移至 pm-rules/（0.2.0-W5-012.2）
