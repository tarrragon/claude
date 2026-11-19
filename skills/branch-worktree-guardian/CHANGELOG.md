# branch-worktree-guardian 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 1.0.3（2026-11-19）— 對齊版號住址：`pyproject.toml` 的 `version` 由 0.1.0 改為與 `metadata.version` 相同。功能不變。

**Version**: 1.0.2（2026-11-13）— 〈修改 source 後必須重新安裝〉改為〈修改 source 後不需安裝〉：本 skill 沒有 CLI 入口，不經 `uv tool` 安裝，`scripts/` 一律從原始碼直接執行。原段落要求修改後執行 `uv tool install . --force --reinstall`，照做只會在 uv tool 環境多一份用不到的副本。

**Version**: 1.0.0
**Last Updated**: 2026-03-18
