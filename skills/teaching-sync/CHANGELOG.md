# teaching-sync 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 2.0.1 — 第 8 步的 git 命令與 walkthrough 範例改用 `<blog repo 絕對路徑>` 佔位符，並註明執行前先展開成字面路徑。原因：PreToolUse 守衛無法判定 `git -C "$BLOG_REPO"`、`cd "$BLOG_REPO"` 這類變數路徑作用在哪個 repo，commit 等寫入類命令會被擋下。walkthrough 原本的裸 `cd` 加 `checkout -b`，改為另建 worktree。

**Version**: 2.0.0 — 與下方 1.0.0 於同一次初始匯入寫入，frontmatter 與檔尾（現已外移至本檔）各自標記版號，無先後之分。frontmatter 的 `metadata.version` 為 sync 工具實際讀取來源，本次外移採其為準；本版無獨立變更說明可考證。

**Version**: 1.0.0 — 初版，原檔尾光禿版號行，無變更說明。
