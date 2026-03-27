# PC-031: error-pattern SKILL.md 引用錯誤的知識庫路徑（docs/ vs .claude/）

**發現日期**: 2026-03-27
**相關 Ticket**: 0.2.0-W7-011（執行中偶然發現）

## 症狀

- 執行 `/error-pattern add` 時，SKILL.md 指示將錯誤模式寫入 `docs/error-patterns/categories/`
- 實際的錯誤模式知識庫位於 `.claude/error-patterns/`（按分類子目錄組織）
- PM 依 SKILL 指示寫入 `docs/error-patterns/` 被 Hook 攔截（非允許路徑），才發現路徑不對
- `docs/error-patterns/` 中有舊的 PC-001~016 記錄，但 `.claude/error-patterns/` 才是目前維護的正確位置（PC-001~029）

## 根因

1. **SKILL.md 未同步更新**：error-pattern SKILL 在知識庫搬遷後未更新路徑引用
2. **雙位置並存造成混淆**：`docs/error-patterns/` 和 `.claude/error-patterns/` 都存在，且內容不同步（docs 停在 PC-016，.claude 到 PC-029）
3. **無路徑驗證機制**：SKILL 引用的路徑未經驗證是否與實際檔案系統一致

## 解決方案

1. 修正 error-pattern SKILL.md 中的路徑引用為 `.claude/error-patterns/`
2. 評估 `docs/error-patterns/` 是否應清理或標記為已棄用
3. 確認所有引用 error-pattern 路徑的文件一致

## 預防措施

1. **搬遷後必須更新所有引用**：任何目錄搬遷操作後，grep 搜尋舊路徑並全部更新
2. **SKILL 路徑驗證**：SKILL 中引用的路徑應定期或在編輯時驗證是否存在

## 行為模式分析

此錯誤屬於「文件搬遷後引用殘留」模式：

| 時間點 | 狀態 |
|--------|------|
| 搬遷前 | `docs/error-patterns/` 為正確路徑 |
| 搬遷後 | `.claude/error-patterns/` 為正確路徑，但 SKILL.md 未更新 |
| 發現時 | 兩個位置都存在，內容不同步，SKILL 指向舊位置 |

> **核心教訓**：搬遷目錄不是「移動檔案」一步完成的操作，還必須包含「更新所有引用」和「清理舊位置」兩個步驟。
