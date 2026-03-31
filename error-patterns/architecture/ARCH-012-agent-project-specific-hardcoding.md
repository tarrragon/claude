---
id: ARCH-012
title: 通用代理人硬編碼專案特定引用
category: architecture
severity: medium
first_seen: 2026-03-31
source_ticket: 0.31.1-W8-005
---

# ARCH-012: 通用代理人硬編碼專案特定引用

## 症狀

在跨專案共用的通用代理人定義（如 `sage-test-architect`）中，出現特定專案的代理人名稱或檔案路徑引用（如 `Read parsley-flutter-developer.md`）。其他專案使用同一代理人時看到不相關的語言/框架引用。

## 根因

混淆了「專案設定」和「代理人知識」的職責邊界：

| 歸屬 | 位置 | 內容 |
|------|------|------|
| **專案設定** | `CLAUDE.md` | 專案使用的測試工具、自訂元件、框架選擇 |
| **代理人知識** | `.claude/agents/` | 通用的技術最佳實踐、框架寫法 |

`.claude/rules/README.md` 已有明確的「專案設定與代理人知識的職責分離」規則，但在 W8-005 中未遵循。

## 錯誤範例

```markdown
# sage-test-architect.md（通用代理人）

## 測試環境設置規劃階段
設計 Widget 測試前，**必須先讀取** parsley-flutter-developer 的知識：
Read .claude/agents/parsley-flutter-developer.md
  → 章節：「Widget 測試核心策略」
```

問題：`parsley-flutter-developer` 是 Flutter 專案特定的代理人，Python 或 Go 專案不存在此代理人。

## 正確做法

```markdown
# sage-test-architect.md（通用代理人）

## 測試環境設置規劃階段
設計 UI 層測試前，必須查閱專案 CLAUDE.md 中的測試注意事項和測試規範章節。
```

通用代理人引導查閱 CLAUDE.md（每個專案都有），不直接引用其他代理人。專案特定的測試知識放在 CLAUDE.md 7.5 節。

## 防護措施

1. **代理人定義只放通用知識**：適用於所有語言/框架的最佳實踐
2. **專案特定規範放 CLAUDE.md**：測試工具、自訂元件、框架選擇
3. **代理人引導查閱 CLAUDE.md**：而非直接引用其他代理人
4. **Code Review 檢查**：代理人定義中出現 `parsley`、`thyme`、`fennel` 等語言代理人名稱時，質疑是否應放在 CLAUDE.md

## 相關規則

- `.claude/rules/README.md`「專案設定與代理人知識的職責分離」章節
- `CLAUDE.md` 第 1 節「專案身份」中的「實作代理人」欄位
