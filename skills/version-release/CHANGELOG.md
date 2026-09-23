# version-release 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 2.2.0 - 改寫發版判準：pending Ticket 不再以「池清空」為門檻，改為帶 scope_blocker（依賴 ticket skill 的版本範圍凍結硬閘門欄位）者阻擋、其餘列為前移清單不阻擋；新增 `finish` 子命令，成功前移全部清單後接續既有 `release` 流程；目標版本未在 todolist.yaml 登記時整批阻擋且不自動登記
**Last Updated**: 2026-09-23

**Version**: 2.1.0 - 使用流程檢查清單新增「三分流語意分類人工抽查」勾選項，銜接 `pm-quality-baseline.md` 規則 7 Action 層的落地要求（原 Action 指向此清單但清單無對應項，屬空落點；本次為同一次變更中補齊）
**Last Updated**: 2026-08-10

**Version**: 2.0.0 - 新增多專案類型支援文件（chrome-ext/flutter/go/php/python/npm/monorepo）、.version-release.yaml schema 文件化、自動偵測 fallback 說明
