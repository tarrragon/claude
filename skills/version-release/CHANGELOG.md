# version-release 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 2.10.0 - 本地變更，指向 tarrragon/claude#55：`finish` 的 Commit Version Activation 在裝有 git 層 reference-transaction 守衛的 repo 內不再被擋。`.claude/lib/commit_content_guards.py` 的 `_check_branch_verify` 新增純版本號變動放行：版本檔（`pubspec.yaml`、`package.json`、`pyproject.toml`，含 monorepo 子目錄）且前後差異只有版本欄位那一行時放行並寫 info 日誌（含前後版本值），依賴或其他行的變動（含版本行與依賴行同改）維持 deny，不使用環境變數旁路。新增整合測試，fixture repo 安裝真實 reference-transaction hook 後在 main 上跑啟用與提交。修復根因：守衛對保護分支上的非豁免檔案一律 deny，未區分版本欄位變動與其他變動，而前一版把版本檔併入啟用提交時的測試 fixture 未安裝該 hook，沒測到此路徑。
**Last Updated**: 2026-09-30

**Version**: 2.9.0 - 本地變更，指向 tarrragon/claude#55：`finish` 的 Commit Version Activation 提交納入本次啟用步驟 bump 的版本檔（Flutter 為 `pubspec.yaml`，含 config 指定的 monorepo 子目錄版本檔）。`commit_changes` 新增 `extra_paths` 參數，路徑須同時在 baseline 差集內才 stage，非版本檔的非 docs 變更仍不納入；新增 `resolve_activation_version_paths` 取得版本檔集合（與 `ensure_version_activated` 同源）。修復根因：stage 範圍只收 `CHANGELOG.md` 與 `docs/`，版本檔殘留於工作區使 exit 前殘留守衛 rc=1。
**Last Updated**: 2026-09-30

**Version**: 2.8.0 - 本地變更，指向 tarrragon/claude#55：`check` 通過後的結尾建議依前移清單切換（非空建議 `finish` 並說明前移張數，空則維持 `release`）；`release` 遇前移清單非空拒絕執行（exit 1、列清單、提示改用 `finish`），`--force` 不覆蓋此判定（前移是資料正確性，非可略過的警告）。修復根因：`release` 不做前移，照 `check` 舊建議發版會把 pending 票留在已 completed 的版本下成為懸空票。新增 `collect_overflow_tickets`
**Last Updated**: 2026-09-30

**Version**: 2.7.1 - 本地變更，指向 tarrragon/claude#111：`snapshot_git_status_paths` 改讀 `git status --porcelain -z`（NUL 分隔、不做 quotepath 跳脫，rename 兩側皆納入），修復 CJK 檔名被 git 加引號並八進位跳脫後，差集比對與 `docs/` 前綴判斷失效、CJK 文件被靜默排除在 `finish` 收尾提交之外；`commit_changes` 逐檔 `git add` 補檢查回傳值，失敗時輸出 warning 含路徑與 stderr（原本忽略回傳值，漏檔無任何訊號）
**Last Updated**: 2026-09-30

**Version**: 2.7.0 - `migrate_overflow_tickets`（`finish` Step 0）改為原樣轉印 `ticket migrate` child process 的 stdout，不再自行以固定字串組「已前移」訊息——上游 `migrate` 對碰撞行為改為 dry-run 判 FAIL 並印改號預覽、正式執行自動改號完成，改號後的實際目標 ID 只存在於 child process 輸出中，沿用固定字串會誤報一個未實際使用的目標 ID。配套 ticket skill 2.42.0（碰撞改號機制）。
**Last Updated**: 2026-09-24

**Version**: 2.6.0 - `compute_overflow_target_version` 補「開放後繼」分支：凍結版本有已在 `docs/todolist.yaml` 登記且未凍結（`status` 為 `planned`/`active`、`scope` 非 `frozen`）的最近後繼版本時，前移目標一律為該後繼版本，不再套動詞分類（IMP 新功能動詞 → minor+1／其餘 → patch+1 僅在無開放後繼時回退）。新增 `find_open_successor`（鏡射 ticket skill 內部 lib 的同名函式語意，不跨 skill import）與對照測試（同 fixture 下與 ticket lib `suggest_overflow_version` 逐案結果相等）。修復根因：本函式為 ticket lib 的鏡射複本，缺此分支導致 0.2.1 凍結後 6 張溢出票被算成未登記的 v0.2.2 而非已登記的 v0.3.0
**Last Updated**: 2026-09-24

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
