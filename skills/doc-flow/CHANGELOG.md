# doc-flow 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 1.1.0
**Last Updated**: 2026-09-07 — 新增 `hooks/worklog-format-check.py`（由 compositional-writing 遷入）：檢測 worklog markdown 表格單元格內導致 Claude Code CLI crash 的問題 emoji。作用域由寫死 `docs/work-logs/` 改為可用環境變數 `WORKLOG_FORMAT_CHECK_SCOPE` 設定（預設值不變），`.claude/settings.json` 的 Edit/Write 兩處註冊同步指向新位置。

**Version**: 1.0.0
**Last Updated**: 2026-04-01
