# 框架資產與專案產物職責分離

本文件定義 `.claude/` 框架資產與專案產物之間的職責分離原則。設計新規則、建立 Skill、規劃文件系統時應讀取本文件。

> **載入方式**：按需讀取。非每 session 自動載入。從 `.claude/rules/README.md` 的索引指向此檔案。

---

## 1. 專案設定與代理人知識的職責分離

| 歸屬 | 位置 | 內容 | 範例 |
|------|------|------|------|
| **專案設定** | `CLAUDE.md` | 技術選型、架構決策、測試指令 | 「本專案用 Riverpod 3.0 + MVVM」 |
| **代理人知識** | `.claude/agents/` | 技術最佳實踐、框架寫法 | 「Riverpod 3.0 Notifier 怎麼寫」 |
| **品質規則** | `.claude/rules/` | 跨專案通用品質標準 | 「函式長度上限 30 行」 |

代理人帶著多種技術的知識（如 Riverpod 2.0、3.0、BLoC），根據 CLAUDE.md 的專案設定選擇適用方案。

**禁止**：建立獨立的語言設定檔（如 FLUTTER.md、PYTHON.md）。所有專案設定統一在 CLAUDE.md。

---

## 2. 框架資產與專案產物的職責分離

框架與專案是兩個獨立生命週期，必須在目錄上嚴格分離。

| 類別 | 位置 | 典型內容 | 判斷標準 |
|------|------|---------|---------|
| **框架資產** | `.claude/` | 模板、規範、Skill、Hook、CLI、規則、方法論 | 會 sync 到其他專案共用 |
| **專案產物** | `docs/`、`src/`、`tests/` | 需求文件、設計稿、程式碼、工作日誌 | 僅屬本專案 |

**強制規則**：

| 禁止 | 原因 |
|------|------|
| 將模板 / 規範放在 `docs/` 下 | 模板屬於框架資產，應放在 `.claude/skills/` 或 `.claude/methodologies/` |
| 在 `docs/` 產物中加註解指向 Skill | 以「指向」彌補目錄混放是錯誤的修正；應直接搬遷到正確位置 |
| 在 `.claude/` 內放專案特定 ticket ID / commit hash / worklog 路徑 | 跨專案 sync 會產生死連結（見 `.claude/references/reference-stability-rules.md` 規則 8） |

**建立新文件系統或 Skill 時**：先問「這是模板/規範還是產物？」
- 模板 / 規範 → 放 `.claude/skills/` 或 `.claude/methodologies/`
- 產物 → 放 `docs/` 或專案目錄

---

## 相關規則

- `.claude/rules/README.md` - 規則系統導航（含本文件索引）
- `.claude/references/reference-stability-rules.md` - 規格引用穩定性規則（規則 8）
- `.claude/error-patterns/architecture/ARCH-012-agent-project-specific-hardcoding.md` - 代理人定義硬編碼專案特定內容的錯誤模式
- `.claude/error-patterns/process-compliance/PC-061-memory-upgrade-blindness.md` - Memory 跨專案原則升級遺漏的錯誤模式

---

**Last Updated**: 2026-04-16
**Version**: 1.0.0 — 從 `.claude/rules/README.md` 拆出（W10-078.3）。原因：本章節屬情境觸發型知識（設計新規則/Skill/文件時才需），不符合 auto-load 原則。
