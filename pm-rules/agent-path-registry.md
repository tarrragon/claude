# 技術實作代理人路徑權限表

> 本文件定義**有檔案路徑限制的技術實作代理人**的可編輯範圍。分析型代理人（system-analyst、incident-responder、oregano-data-miner 等）無路徑限制，其能力定義見 `.claude/agents/` 目錄。
>
> 其他檔案（skip-gate.md、parallel-dispatch.md 等）引用本表，不自行維護路徑清單。
>
> 路由入口：.claude/pm-rules/decision-tree.md

---

## 核心原則：派發即授權

PM 派發任務時已驗證路徑權限。subagent 被派發後應放心執行，無需預先評估風險。被阻擋時上報 PM 即可。

---

## 代理人可編輯路徑對照表

| 代理人 | 可編輯路徑（glob） | 說明 |
|--------|-------------------|------|
| thyme-extension-engineer | `src/**/*.js`、`tests/**/*.js` | Chrome Extension 程式碼和測試（本專案主要實作代理人） |
| thyme-python-developer | `.claude/hooks/*.py`、`.claude/skills/**/*.py`、`.claude/lib/*.py` | Hook 優化/修正、Skill 程式碼、共用程式庫 |
| parsley-flutter-developer | `ui/lib/**/*.dart`、`ui/test/**/*.dart`、`ui/pubspec.yaml` | Flutter 應用程式碼和測試 |
| basil-hook-architect | `.claude/hooks/*.py`、`.claude/lib/*.py` | Hook 新增/設計、共用程式庫設計 |
| fennel-go-developer | `server/**/*.go` | Go 後端程式碼 |
| sage-test-architect | `ui/test/**/*.dart`、`tests/**/*.js` | 測試設計（不修改實作碼） |

---

## 檔案類型 → 代理人對應

| 檔案類型 | 派發代理人 |
|---------|-----------|
| `src/**/*.js`、`tests/**/*.js` | thyme-extension-engineer（本專案主要實作） |
| `.claude/hooks/*.py` 新增/設計 | basil-hook-architect |
| `.claude/hooks/*.py` 優化/修正 | thyme-python-developer |
| `*.py`（其他） | thyme-python-developer |
| `*.dart`（lib/ 或 test/） | parsley-flutter-developer |
| `.md`（.claude/rules/ 或 docs/） | 主線程允許編輯 |

> Hook 派發原則：「Hook 該怎麼運作」→ basil；「Hook 程式碼該怎麼寫」→ thyme

---

## 相關文件

- .claude/pm-rules/decision-tree.md - 路由索引（本表的入口）
- .claude/pm-rules/parallel-dispatch.md - 派發前檢查清單
- .claude/pm-rules/skip-gate.md - 安全防護機制

---

**Last Updated**: 2026-04-09
**Version**: 1.0.0 - 從 decision-tree.md 獨立（決策樹二元化拆分）
