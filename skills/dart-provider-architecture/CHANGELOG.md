# dart-provider-architecture 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 2.0.0 — 復活自 canonical 刪除版 1.0.0（刪除原因：綁定不存在專案的路徑與 error-pattern 編號）。回收架構層四原則與檢查清單；新增「配對規則：必接線 provider 與 wiring test 閉環」（源自一次實證：fail-fast 契約 + 全 mock 測試使漏接線在 303 個綠燈測試下潛伏至實機啟動才暴露）；新增反漂移維護約束。
**Last Updated**: 2026-08-11

**Version**: 1.0.0 — 初版（UC 整合測試修復經驗總結，2026-01-13）
