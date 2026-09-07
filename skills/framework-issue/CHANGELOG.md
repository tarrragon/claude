# framework-issue 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 2.0.0 — 依 skill-design-guide 重整：入口檔由 407 行／5756 tokens 收斂為定位（ticket 記執行、issue 記問題）、決策入口（一問判框架問題 + 動作路由 + 三種查重關係）、命令總表、收束流程速覽、owner 與派發、按需讀取路由表；細節外移五份 reference——`comment-as-section-protocol.md`（六操作／CLI／標記格式／查重處置／check 警訊／close 語意／新增〈已知限制〉：init 單次、無 add 區段命令、舊 issue 不補標記、關鍵字過期）、`fix-matrix-commands.md`、`escalation-flow.md`（補「已修事實對下游不可達」實例）、`ticket-intake.md`（新增：分群、查重落點四選一、時序改狀態判準表、五區段模板與 sections.json 骨架、ticket close 命令與 reason-note 禁詞、驗證交接、curator 派發 prompt 骨架）、`worked-example.md`（新增：從 dedup 到 check 的完整走查）。owner 識別格式定為 `<專案 kebab>-<session 序號>`。description 由 330 字元縮至 250 內。配套 `framework-issue-curator` 代理人升 2.0.0（收束職責、opus／medium、Write 限 scratchpad）

**Version**: 1.5.0 — 補記 1.4.0 之後累積但未 bump 版號的變更（版號未動使發佈庫與本庫的內容分歧無法由版號察覺）。三項：(1) 新增 `scripts/owned_issues_registry.py`——`init` / `update` 成功寫入 GitHub 後，把 `(issue number, owner, updated_at)` 落地到 `.claude/state/framework-issue-owned.json`（per-worktree、不入版控），供 SessionStart 端跳過「目錄名 heuristic 推 owner 前綴 → `gh search issues` 粗篩 → 逐張讀 comments 驗證」的固定往返成本；讀取失敗回傳 None（無法判定，呼叫端 fail-open 退回舊路徑），空清單則代表已確認無擁有區段，兩者語意不可合併。(2) `search_issues_by_keyword` 把關鍵字移到全部旗標之後、以 `--` 分隔——查重 token 可能以 `-` 開頭（`-a`、`--force`），排在旗標前會被 `gh` 的 flag parser 判為未知旗標。(3) `search_duplicates` 改回傳 `(results, skipped_count)`，`render_dedup_report` 末行固定重述查詢失敗略過的 token 數，使查重涵蓋範圍縮小成為報告本身可見的宣告，不只依賴 stderr 單行警告

**Version**: 1.4.0 — `section_comment.py` 六個子命令（init/update/observe/show/check/dedup）落地，取代 1.3.0 記載的介面規格。init 前查重必填 `--dedup-keywords`（跨 comment 分佈詞彙以 token 聯集查詢後回顯命中清單，人工標註重複／切分／引用關係，不自動判定不阻擋）；`--sections-file` 為 JSON 陣列 `[{"name": "區段名", "content": "內容"}, ...]`；update 以 comment id 精準 PATCH 單一區段；observe 附加觀測 comment 不需 owner；show 依區段標記區分「當前結論區段」與「觀測流」；check 唯讀輸出當前結論時效（主警訊）、comment 數閾值（輔助）、body 區段索引一致性三項警訊，exit 0 不阻擋；dedup 唯讀，共用 init 查重邏輯供獨立核對關鍵字涵蓋範圍

**Version**: 1.3.0 — 新增「Comment-as-Section 協作協定」章節：五操作（init/update/observe/show/check）用法、區段與觀測標記格式、init 前查重三種關係處置（併入／建新張互標分工／單向指向）、check 三項警訊、增長與 close 語意。與既有 fix-matrix 命令集（軸 C/D）並存，不取代。命令實作另行進行中，本章節為介面規格

**Version**: 1.2.0 — 新增「框架問題升級流程」章節：介入判斷、兩條路徑（延後接手 / 當下接手）、issue 關閉協議（sync-push → fix-version → close）、回報前查重 SOP（承接既有命令實作）

**Version**: 1.1.0 — 新增 fix-version（軸 D：修復版本號註記）與 close（包裝 `gh issue close`，前置檢查版本號註記存在）命令
