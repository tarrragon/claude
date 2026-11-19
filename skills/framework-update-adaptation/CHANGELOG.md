# framework-update-adaptation 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 1.1.0（2026-11-19）— Step 3 第 4 類「consumer 產物要重驗」補待辦票：範圍加「流程、命令或路徑被刪除、改名或改變語意」，判別問句加「pending 或 in_progress 票的 how.strategy 或 where.files 是否依賴這些流程」，動作加「列出票號並改寫策略」；查證表新增一列 grep 待辦票的指令；範例新增一表示範流程變更命中待辦票（tarrragon/claude#140）。第 1 類範圍欄補「本地特化」權威定義的路由（`references/sync-mechanism-guide.md`〈本地特化的定義〉）。

**Version**: 1.0.0（2026-11-05）— 新建（tarrragon/claude#127 提案，用戶要求）。sync-pull 之後的語意對齊固定為五步：讀狀態檔、列 delta（canonical 版本紀錄加檔案清單，兩者都取）、逐項分類（五類，依序判別、命中後繼續判，附判別問句與查證指令）、各類建票（ANA 紀錄票加每類一張子票；命中但已完成的記分類不建票）、更新狀態檔。狀態檔放 `.claude/project-integration/framework-update-adaptation/last-adapted.md`，沿用類型 E 的雙向排除，每個 consumer 各一份；`tests/test_state_sync_exclusion.py` 守住排除。以 2.86.0 → 2.87.0 實跑一次驗證。
