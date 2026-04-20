# 通用品質基線（指標）

> **完整規則**：`.claude/references/quality-common.md`（按需讀取）。本檔僅保留觸發指標。

## 何時載入

| 情境 | 必讀 |
|------|------|
| 代理人寫產品程式碼 / Phase 4 重構 / 修 bug | 是 |
| PM 派發、決策、分析 / 寫 RED 測試 | 否 |

## 載入方式

- 代理人：透過 `@.claude/references/quality-common.md` 強制載入（thyme/parsley/cinnamon/fennel/bay）
- PM 前台：遇品質審查需求時 Read `.claude/references/quality-common.md`

## 內容索引

| 章節 | 用途 |
|------|------|
| 1.1 命名規範 / 1.2 函式設計（含 1.2.1~1.2.5 防護） | 命名 + 函式結構 + 重構/修 bug 防護 |
| 1.3 常數管理 / 1.4 DRY / 1.6 註解標準（含業務情境聚焦、抽象層級貼合） | 硬編碼、重複、註解規範 |
| 1.5 認知負擔閾值 | 詳見 `.claude/rules/core/cognitive-load.md` |
| 2. 檢查清單 | 提交前對照 |

---

**Last Updated**: 2026-04-19 | **Version**: 2.1.0 - 1.6 註解標準索引補列「業務情境聚焦」與「抽象層級貼合」兩條款（substance 在 references/quality-common.md §1.6 與 methodologies/comment-writing-methodology.md）

**Version**: 2.0.0 - 完全外移至 references/（W10-076.1）
