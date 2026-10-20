# cognitive-load-assessment 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 2.1.1（2026-10-19）— `references/file-split-by-contention.md` §3.3 新增一列：拆分 portable skill 時，新模組的 docstring 不寫搬移來源的路徑與票號，來源改記在 commit 訊息（本地守衛的搬移豁免標記，不被推發佈庫時的可攜性檢查接受）。

**Version**: 2.1.0（2026-10-19）— 新增 `references/file-split-by-contention.md`：以「不同票樹反覆改同一檔」判斷何時拆分（門檻、同票樹與聚合檔的反例），附文字規則與 Python 的拆分流程（先鎖行為、分辨鎖位置的測試、patch 看呼叫端在哪裡查名稱、拆後比對兄弟模組）與驗收；SKILL.md 相關文件補路由。

**Version**: 2.0.0 - 合併 cognitive-load-review，新增 Code Review 模式和 references/
**Last Updated**: 2026-03-02
