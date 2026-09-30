# impeccable 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 3.5.1 - 本地變更，指向 tarrragon/claude#111：`scripts/context-signals.mjs` 的 `gitSignals` 之 `git diff --name-only` 加 `-c core.quotepath=false`，對齊同檔 `git status --porcelain` 已有的做法；修復非 ASCII 檔名在 `changedFiles` 中以加引號、八進位跳脫形式出現
