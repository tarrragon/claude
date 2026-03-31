# 版本發布前檢討流程（Version Retrospective）

本文件定義版本發布前的標準化開發經驗回收機制。

---

## 目的

每個版本開發過程中累積的經驗教訓（error patterns、工作流程改善、規範缺漏）應在發布前結構化地整合回專案規範和代理人設定，避免同類問題反覆出現。

---

## 觸發時機

在 `/version-release check`（Pre-flight 檢查）之前執行。具體觸發條件：

| 條件 | 說明 |
|------|------|
| 所有功能 Ticket 完成 | Wave 的功能開發全部 completed |
| 準備進入發布流程 | PM 判斷版本功能已達標 |
| 明確的版本里程碑 | 如 v0.x.0 的大版本更新 |

---

## 檢討流程（4 步驟）

### Step 1: 收集經驗素材

| 素材來源 | 收集方式 | 重點 |
|---------|---------|------|
| Error Patterns | `ls .claude/error-patterns/` | 本版本新增的模式 |
| Ticket 執行日誌 | `ticket track list --version X.Y.Z` | 失敗、阻擋、重試記錄 |
| Session 教訓 | Memory 系統 | 跨 session 累積的教訓 |
| 測試結果 | 區塊測試記錄 | 重複失敗的測試類型 |

### Step 2: 分類和評估

將收集到的經驗分為三類：

| 分類 | 目標文件 | 範例 |
|------|---------|------|
| **專案規範** | CLAUDE.md | 技術選型、測試指令、架構決策 |
| **代理人設定** | `.claude/agents/` 定義 | 代理人觸發條件調整、職責釐清 |
| **流程規則** | `.claude/pm-rules/`、`.claude/rules/` | 新增防護規則、檢查清單 |

**評估原則**：
- 發生 2 次以上的問題 → 必須寫入規範
- 發生 1 次但影響大（阻擋 > 1 小時）→ 建議寫入規範
- 純一次性問題 → 記錄在 error-pattern 即可

### Step 3: 產出改善 Ticket

對每個需要更新的項目建立 DOC 類型 Ticket：

```bash
ticket create --version {current} --wave {next_wave} \
  --action "更新" --target "{具體規範文件名}" --type DOC
```

### Step 4: 執行和驗證

- 改善 Ticket 應在版本發布前完成（如果範圍小）
- 或排入下一版本的第一個 Wave（如果範圍大）

---

## 檢討檢查清單

每次版本檢討時確認：

- [ ] 本版本新增的 error-patterns 是否都有對應的防護規則？
- [ ] 本版本重複出現的問題是否已寫入規範？
- [ ] 代理人定義是否需要調整（觸發條件、職責邊界）？
- [ ] CLAUDE.md 是否反映最新的技術選型？
- [ ] 測試策略是否需要根據失敗模式調整？

---

## 與現有流程的關係

```
所有功能 Ticket 完成
    |
    v
[Version Retrospective] ← 本文件定義的流程
    |
    v
/version-release check（Pre-flight 檢查）
    |
    v
文件更新 → Git 操作 → 發布
```

---

## 相關文件

- .claude/skills/version-release/SKILL.md - 版本發布流程
- .claude/pm-rules/version-progression.md - 版本進程規劃
- .claude/error-patterns/ - 錯誤模式知識庫
- .claude/rules/core/quality-baseline.md - 品質基線（規則 5：所有發現必須追蹤）

---

**Last Updated**: 2026-03-31
**Version**: 1.0.0 - 初版（0.31.1-W1-016）
