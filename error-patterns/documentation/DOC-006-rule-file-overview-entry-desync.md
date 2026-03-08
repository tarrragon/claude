# DOC-006: 規則文件局部更新後，同檔案總覽圖與入口文件未同步

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | DOC-006 |
| 類別 | documentation |
| 嚴重度 | 中 |
| 發現版本 | 0.1.1 |
| 發現日期 | 2026-03-07 |
| 來源 | /parallel-evaluation G 審查 TDD Phase 4 三步驟重設計後發現（0.1.1-W2-003 follow-up） |

### 症狀

更新規則文件的「詳細說明」章節後，同一文件頂部的「流程總覽圖」和入口文件的摘要仍顯示舊格式。具體案例：

- `tdd-flow.md` 的 Phase 4 詳細章節已更新為 4a/4b/4c 三步驟
- 但同檔案第 9-35 行的流程總覽圖仍寫 `[Phase 4] 重構優化 → cinnamon-refactor-owl`
- `CLAUDE.md` TDD 流程摘要仍寫 `Phase 4: 重構評估 (cinnamon-refactor-owl)`
- `cinnamon-refactor-owl.md` 代理人描述仍寫「對應 TDD Phase 4」（應為「Phase 4b」）

### 根因

**行為模式**：更新規則文件的「詳細說明」時，假設頂部的「總覽圖/摘要」是次要的，或預設它會被讀者自動以詳細說明為準。

具體原因：
1. **同檔案 Overview 是隱性文件面**：作者聚焦在「Phase 4 詳細說明」章節，未意識到文件頂部的流程圖也是一個需要同步更新的文件面
2. **入口文件被視為「衍生摘要」**：CLAUDE.md 的 TDD 摘要和代理人 description 欄位被視為「不重要的摘要」，未列入更新範圍
3. **責任邊界模糊**：更新規則文件時，未定義「哪些其他地方也需要同步更新」的明確清單

**與 DOC-005 的區別**：
- DOC-005：新增原則 → 語義相關的其他文件未同步（語義依賴，跨文件）
- DOC-006：重設計既有規則 → 同文件的總覽圖 + 入口/摘要文件未同步（範疇更新，含同檔案內）

### 影響範圍

| 影響 | 說明 |
|------|------|
| 同一文件自相矛盾 | 讀者看到頂部總覽圖與下方詳細說明衝突 |
| 入口文件失準 | 第一次看 CLAUDE.md 的人獲得過時資訊 |
| 代理人角色混淆 | cinnamon 的 description 仍宣稱負責整個 Phase 4，實際只負責 4b |

### 解決方案

本次修正（parallel-evaluation G 捕獲後修正）：
1. `tdd-flow.md` 流程總覽圖更新為 Phase 4a/4b/4c 三步驟
2. `CLAUDE.md` TDD 摘要更新為三步驟格式
3. `cinnamon-refactor-owl.md` description 明確為「Phase 4b（重構執行）」

### 預防措施

**重設計既有規則時的強制更新清單**：

| 步驟 | 動作 | 驗證方式 |
|------|------|---------|
| 1 | 確認更新的主文件頂部是否有流程圖/總覽 | 讀文件頭部 |
| 2 | 搜尋關鍵字確認 CLAUDE.md 是否有該規則的摘要 | `grep "Phase 4" CLAUDE.md` |
| 3 | 搜尋相關代理人定義，確認 description 是否需要更新 | `grep -r "Phase 4" .claude/agents/` |
| 4 | 更新所有受影響面，同一 commit 提交 | git diff 確認 |

**建議防護機制**：
- 規則文件重設計後，派發 `/parallel-evaluation G`（系統設計審查）驗證跨文件一致性
- parallel-evaluation G 的 Consistency 視角應明確把「入口文件（CLAUDE.md）」和「代理人 description」列為掃描目標

### 關聯

- 修復 commit: 1400688（tdd-flow.md 總覽圖 + CLAUDE.md + cinnamon 代理人）
- 觸發 Ticket: 0.1.1-W2-003（TDD Phase 4 三步驟重設計）
- 相關模式: DOC-005（跨文件原則未同步）、ARCH-005（代理人定義衝突）

---

**Last Updated**: 2026-03-07
**Version**: 1.0.0
