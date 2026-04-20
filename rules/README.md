# 規則系統

> **平台機制**：Claude Code 啟動時自動載入 `CLAUDE.md` + `.claude/rules/**/*.md`。其他 `.claude/` 子目錄不會自動載入，必須主動 Read。

本目錄只放**所有角色通用**的品質規則（7 檔）。PM 流程規則在 `pm-rules/`，技術參考在 `references/`。

| 目錄 | 載入方式 | 內容 |
|------|---------|------|
| `rules/core/` | 自動載入 | 通用品質基線、Bash 規則、認知負擔、文件格式、語言約束、AI 對話品質 |
| `pm-rules/` | PM 按需讀取 | 決策樹、TDD、Ticket、事件回應、Skip-gate |
| `references/` | 代理人按需讀取 | 語言品質（dart/go/python）、Ticket ID 規範、職責分離原則 |
| `agents/` | 派發時讀取 | 代理人定義（含技術知識庫） |

**職責分離原則**（設計新規則 / Skill / 文件系統前請讀）：

- 專案設定 vs 代理人知識分離、框架資產 vs 專案產物分離 → `.claude/references/framework-asset-separation.md`

**環境管理原則**（安裝 / 審查 / 卸載 Claude Code plugin 前請讀）：

- Plugin 注入成本、安裝前評估清單、審查週期、卸載流程 → `.claude/references/plugin-management.md`

---

**Last Updated**: 2026-04-20
**Version**: 10.1.0 — 新增「環境管理原則」導航，指向 `references/plugin-management.md`（避免 plugin 誤裝膨脹 context）
