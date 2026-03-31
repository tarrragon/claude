# 規則系統

> **平台機制**：Claude Code 啟動時自動載入 `CLAUDE.md` + `.claude/rules/**/*.md`。其他 `.claude/` 子目錄不會自動載入，必須主動 Read。

本目錄只放**所有角色通用**的品質規則（7 檔）。PM 流程規則在 `pm-rules/`，技術參考在 `references/`。

| 目錄 | 載入方式 | 內容 |
|------|---------|------|
| `rules/core/` | 自動載入 | 通用品質基線、Bash 規則、認知負擔、文件格式、語言約束 |
| `pm-rules/` | PM 按需讀取 | 決策樹、TDD、Ticket、事件回應、Skip-gate |
| `references/` | 代理人按需讀取 | 語言品質（dart/go/python）、Ticket ID 規範 |
| `agents/` | 派發時讀取 | 代理人定義（含技術知識庫） |

## 專案設定與代理人知識的職責分離

| 歸屬 | 位置 | 內容 | 範例 |
|------|------|------|------|
| **專案設定** | `CLAUDE.md` | 技術選型、架構決策、測試指令 | 「本專案用 Riverpod 3.0 + MVVM」 |
| **代理人知識** | `.claude/agents/` | 技術最佳實踐、框架寫法 | 「Riverpod 3.0 Notifier 怎麼寫」 |
| **品質規則** | `.claude/rules/` | 跨專案通用品質標準 | 「函式長度上限 30 行」 |

代理人帶著多種技術的知識（如 Riverpod 2.0、3.0、BLoC），根據 CLAUDE.md 的專案設定選擇適用方案。

**禁止**：建立獨立的語言設定檔（如 FLUTTER.md、PYTHON.md）。所有專案設定統一在 CLAUDE.md。

---

**Last Updated**: 2026-03-31
**Version**: 8.0.0 - 新增專案設定與代理人知識職責分離說明（0.31.1-W1-018）
