# framework-update-adaptation 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 1.0.0（2026-11-05）— 新建（tarrragon/claude#127 提案，用戶要求）。sync-pull 之後的語意對齊固定為五步：讀狀態檔、列 delta（canonical 版本紀錄加檔案清單，兩者都取）、逐項分類（五類，依序判別、命中後繼續判，附判別問句與查證指令）、各類建票（ANA 紀錄票加每類一張子票；命中但已完成的記分類不建票）、更新狀態檔。狀態檔放 `.claude/project-integration/framework-update-adaptation/last-adapted.md`，沿用類型 E 的雙向排除，每個 consumer 各一份；`tests/test_state_sync_exclusion.py` 守住排除。以 2.86.0 → 2.87.0 實跑一次驗證。
