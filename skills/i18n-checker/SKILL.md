---
name: i18n-checker
description: "全量掃描硬編碼中文字串並生成 i18n 修正建議。檢測所有層（Model/Service/Domain/UI）中文硬編碼，生成 ARB 鍵值建議，支援批量替換工作流程。Use for: (1) 檢查專案全部硬編碼中文（不只 UI 層）, (2) 進行大規模 i18n 修復, (3) 生成 ARB 鍵值建議, (4) i18n 技術債務評估"
---

# i18n Checker

深度掃描專案中所有硬編碼中文字串，生成 i18n 修正建議。

## 基本使用

### 快速檢查

```bash
uv run scripts/i18n_hardcode_checker.py
```

### 輸出格式

| 選項 | 說明 | 範例 |
|------|------|------|
| （無選項） | 摘要統計 | `總計: 11918, lib/: 1966, test/: 9952` |
| `--report` | Markdown 詳細報告 | `uv run scripts/i18n_hardcode_checker.py --report > docs/i18n-report.md` |
| `--arb` | JSON ARB 鍵值建議 | `uv run scripts/i18n_hardcode_checker.py --arb` |
| `--json` | 結構化 JSON 輸出 | `uv run scripts/i18n_hardcode_checker.py --json` |

詳細參數和工作流程見 `references/mixed-processing-guide.md` 和 `references/scanner-rules.md`。

## 典型工作流程

```bash
# 1. 執行檢查，生成詳細報告
uv run scripts/i18n_hardcode_checker.py --report > docs/i18n-report.md

# 2. 根據報告分類硬編碼（見 references/mixed-processing-guide.md）

# 3. 生成 ARB 鍵值建議
uv run scripts/i18n_hardcode_checker.py --arb > arb_suggestions.json

# 4. 手動審核 + 添加到 ARB + flutter gen-l10n

# 5. 使用批量替換腳本
uv run scripts/i18n_batch_replace.py --target lib/presentation --apply

# 6. 再次驗證
uv run scripts/i18n_hardcode_checker.py
```

詳細的複雜度分級判斷、等級決策、Ticket 派生策略見 `references/mixed-processing-guide.md`。

## 與其他工具的差異

與 **style-guardian** 的互補關係：

| 工具 | 檢查範圍 | 用途 |
|------|---------|------|
| style-guardian | UI 層（Text、AppBar、labelText） | 快速日常檢查 |
| i18n-checker | 全層（Model/Service/Domain/UI） | 深度技術債務清理 |

## 參考資源

詳細的複雜度分級、工作流程、Ticket 派生策略：
- `references/mixed-processing-guide.md` - 等級 A/B/C/D 判斷標準和實戰案例
- `references/scanner-rules.md` - 掃描規則和鍵名建議邏輯

## 相關方法論

- 分層 i18n 管理：`.claude/methodologies/business-layer-i18n-management-methodology.md`
- Style Guardian：`.claude/skills/style-guardian/`
