# skill-design-guide 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 1.2.0 — 新增 §6.4「外部引用：指名身分，不用檔案路徑」（skill 用名字走 Skill 工具載入、方法論與規則用標題檢索），含判別問句「讀者是要去讀它學東西，還是要寫進它讓別的東西動起來」與兩類正當例外（框架綁定工具講自己的主題、介面規格）。§6.3 補一行界定其適用範圍為 skill 目錄內的相對路徑。§12 Body 檢查清單補對應機械檢查。實證：框架改版移動 hook 位置使舊路徑註冊全數失效；skill-sync 可攜性閘門把兩份 skill 的 25 處路徑判為指名他專案的檔案而中止 push
**Last Updated**: 2026-04-30

**Version**: 1.1.0 — §1.4 新增 Opinionated Defaults 設計心法（通用原則路由 `rules/core/opinionated-default-design.md`）

**Source**: Anthropic 官方 skill-creator（`~/.claude/plugins/marketplaces/anthropic-agent-skills/skills/skill-creator/`）+ 官方平台文件 + Claude Code 擴展規範 + 本專案實踐
