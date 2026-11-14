# strategic-compact 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 1.1.1（2026-11-14）— `suggest-compact.py` 在 linked worktree 內改用主 checkout 的位置：計數檔的根改由框架 lib 的 `get_shared_state_root` 取得，worktree 內不再另建 hook-state；fail-open 日誌目錄改經 `get_hook_log_dir("suggest-compact")` 解析。提醒門檻、計數鍵與輸出管道不變。`tests/test_suggest_compact.py` 補 linked worktree 下日誌落在主 repo 的對照測試。

**Version**: 1.1.0（2026-10-19）— 提醒改走 `additionalContext`；suggest-compact 計數鍵改用 session_id、計數檔移至 hook-state（原以 pid 命名，計數恆為 1 且暫存檔無限累積）。

**Version**: 1.0.0
**Last Updated**: 2026-03-02
