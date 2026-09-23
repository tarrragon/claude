# version-release 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 2.5.0 - 新增 `ensure_version_activated`：版本啟用的三項副作用（todolist status active、worklog 主檔存在、版本檔版號一致）加 CHANGELOG In Development 骨架，抽成單一冪等常式，逐項檢查只補缺項並印 `[OK]`／`[補]`。`start` 對已 active／planned／pending 版本改呼叫此常式補齊，不再對 active 版本 FAIL；`finish` 的 `activate_next_planned_version` 改呼叫同一常式（取代原本只翻 todolist status 的 `_apply_version_activation`），避免副作用集合與執行路徑不對齊（與 `finish` 收尾 add 清單缺陷同型）
**Last Updated**: 2026-09-23

**Version**: 2.4.0 - `check`／`finish` 新增發版前置關卡：目標版本須於 `docs/todolist.yaml` 標 `scope: frozen`，否則 exit 非 0 並印「版本未凍結，契約 blocker 在凍結前恆為 0，本判定無鑑別力」；`finish` 的此關卡在 Step 0（migrate overflow tickets）之前，未凍結不產生 migrate 副作用。修復 0.2.0 剛啟用即實測 `check` 恆判可發布（scope_blocker 只在凍結後才存在，未凍結時 blocker 恆 0 對判定無鑑別力）
**Last Updated**: 2026-09-23

**Version**: 2.3.0 - finish 收尾提交改以「執行前後 git status 差集」定 staged 範圍（過濾 docs/ 與 CHANGELOG.md），取代舊版寫死清單 `git add docs/todolist.yaml CHANGELOG.md`——寫死清單在 Step 0 前移產生 ticket rename 等副作用時必然落後；Mark Version Completed / Activate Next Version 之後新增第二次收尾提交涵蓋其變更；finish 流程結尾加入 exit 前殘留守衛，工作區有非本次產生的殘留即列清單並以非 0 退出（不自動 add）
**Last Updated**: 2026-09-23

**Version**: 2.2.0 - 改寫發版判準：pending Ticket 不再以「池清空」為門檻，改為帶 scope_blocker（依賴 ticket skill 的版本範圍凍結硬閘門欄位）者阻擋、其餘列為前移清單不阻擋；新增 `finish` 子命令，成功前移全部清單後接續既有 `release` 流程；目標版本未在 todolist.yaml 登記時整批阻擋且不自動登記
**Last Updated**: 2026-09-23

**Version**: 2.1.0 - 使用流程檢查清單新增「三分流語意分類人工抽查」勾選項，銜接 `pm-quality-baseline.md` 規則 7 Action 層的落地要求（原 Action 指向此清單但清單無對應項，屬空落點；本次為同一次變更中補齊）
**Last Updated**: 2026-08-10

**Version**: 2.0.0 - 新增多專案類型支援文件（chrome-ext/flutter/go/php/python/npm/monorepo）、.version-release.yaml schema 文件化、自動偵測 fallback 說明
