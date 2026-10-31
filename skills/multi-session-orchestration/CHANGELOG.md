# multi-session-orchestration 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 1.19.0（2026-10-31）— `references/line-continuity.md` §3：`line_status` 每條未收線的線多一段 context，新增〈context 段的判讀〉表，逐一列出各寫法（用量、待 compact、待 clear、恢復開工徽章、phase compacted／resumed、未量測、無用量檔、解析失敗）的意義與主控接續動作。

**Version**: 1.18.2（2026-10-31）— `references/line-continuity.md` §4〈線 session 的恢復開工通知〉：主管道標為預設關閉；〈已知限制〉補一條「auto mode 下主管道不可用，以用量檔 phase、看板徽章、`line_status` 為準」，附實測紀錄（classifier 不給判定）與不自動重送、不設法讓 classifier 放行的理由。

**Version**: 1.18.1（2026-10-31）— `references/line-continuity.md` §4〈線 session 的恢復開工通知〉補〈送出紀錄檔〉：主管道沒收到通知時讀 `.claude/hook-logs/line-board/resume-notice.log`，列出每行欄位、各步驟（sent、skipped、config-unavailable、state-unavailable、error、send-disabled）的意義與結果欄位，並寫明沒有對應行代表恢復開工未被判定到。

**Version**: 1.18.0（2026-10-31）— `references/line-continuity.md` §4 新增〈線 session 的恢復開工通知〉：一般的線在 `/compact` 或 `/clear` 後重新開工時，line-board 自動通知主控（主管道為一行跨 session 訊息，輔管道為用量檔的 `phase`）。寫明判定時點、不通知的情況、主控收到後只核對不回覆，以及三項已知限制：熱重載遺失待通知狀態（不補救）、`/clear` 後狀態檔尚未更新時比對不到名稱、權限模式不同時訊息被暫扣。

**Version**: 1.17.0（2026-10-31）— 主控寫給用戶的待辦：

- SKILL.md 核心原則表新增「要用戶處理的事項寫成待辦行，回覆只引用」：主控在協調票 Solution 寫帶鍵的待辦行 `**用戶待辦**（<鍵>）：<事項>`，處理完寫完成行 `**用戶待辦完成**（<鍵>）：<結果>`；回覆中只引用不重列。
- `references/line-continuity.md` §2 新增〈用戶待辦〉：格式、鍵的選法、配對規則（同鍵以最後一行為準、配不到不影響其他項、不帶鍵的舊行以全文配對）、看板「用戶待辦」群組的顯示（U1 待辦行在前、U2 各線等用戶在後）。
- SKILL.md〈按需讀取〉與〈檢查清單〉同步。

起因：用戶回報主控要用戶處理的事項散在回覆裡，被 Stop hook 回應與各線訊息淹沒，找不到（2026-10-31）。

**Version**: 1.16.0（2026-10-31）— 線停在等用戶的偵測與規則：

- SKILL.md 核心原則表新增「停下等用戶時同一步寫標記並傳訊」：線停下來等用戶時，同一步於所持票的 Solution 寫等用戶標記並傳訊主控，用戶回應後寫解除行。
- `references/line-continuity.md` §2 新增〈等用戶〉：三種訊號（S1 票面標記 `**等用戶**：`／`**等用戶解除**：`、S2 session `status=waiting`、S3 現行佇列行含「等用戶」）、不算訊號的寫法、漏報邊界、`line_status` 的「等用戶（N）」輸出、主控依訊號的接續動作；§3 工具輸出補「等用戶」一項。
- SKILL.md〈按需讀取〉與〈檢查清單〉同步。

起因：一條線把待用戶實測的事項寫在票面卻沒有傳訊，主控沒讀到，直到用戶問起才發現；用戶裁定 `line_status` 加入等用戶偵測（2026-10-31）。

**Version**: 1.15.0（2026-10-31）— 主控 session 長駐的定位：

- SKILL.md 工作流 §6 與 `references/line-continuity.md` §4 寫明主控不例行 `/clear` 或 `/compact`，§4 的自我接續改定位為例外時的程序。
- `line-continuity.md` §4 新增〈Stop hook 保護提醒的判讀〉：主控的判讀問題是「本輪協調事項是否已寫進協調票」，不以「可否清除」作結論，也不向用戶建議清除主控。
- `references/session-naming.md` 主控命名列補「長駐」，並註明「線完結就換 session」不適用於主控。
- SKILL.md〈檢查清單〉與〈按需讀取〉同步。

起因：用戶裁定主控是框架通用設計、主控 session 長駐（2026-10-31）；主控曾把 Stop hook 提醒讀成「隨時可以清除主控」。

**Version**: 1.14.0（2026-10-31）— 新增 SessionStart hook `scripts/master_resume_hint.py`：名為「主控」的 session 以 `source=clear` 或 `compact` 啟動時，以 additionalContext 提示先呼叫 `line_status`、讀協調票、依 `references/line-continuity.md` §4 完成自我接續。其他名稱或 `startup`／`resume` 不輸出。consumer 專案需在自己的 `settings.json` 的 SessionStart 註冊：`uv run --quiet $CLAUDE_PROJECT_DIR/.claude/skills/multi-session-orchestration/scripts/master_resume_hint.py`。`line-continuity.md` §4 補〈自動提示〉段。

起因：主控 `/clear` 後要等第一則訊息才想起要接續；plugin 的 `session.start` 拿不到 source、不能回傳 additionalContext，所以用 shell hook 實作（2026-10-31）。

**Version**: 1.13.0（2026-10-31）— `references/line-continuity.md` §3 改以 line-board 的 `line_status` 工具為判讀主路徑：

- 工具一次完成 §3 步驟 1、3、4、5，並列出過期項；時間比對與 `ListAgents` 名稱核對仍由主控做。
- 原步驟改為工具不可用時的備援；python 查詢註明只讀主 checkout 的 log。
- §4 自我接續步驟 2 改為先呼叫工具。

起因：判讀手動步驟改由工具提供，判讀規則只在 line-board 實作一份（2026-10-31）。

**Version**: 1.12.0（2026-10-31）— `references/line-continuity.md` 新增 §5〈用戶說「繼續工作」時：開線計畫表〉：

- 順序：自我接續 → 整理工作內容 → 列開線計畫表 → 用戶確認後才開線。
- 表格固定八欄：線、動作、session 名稱、用戶要做的事、目標、佇列、名額、注意。
- 動作分五種：新開、/clear 後接續、/compact 後接續、沿用、改名接續。
- 表格下方另列「未分派的票」與「待用戶裁定」。

原 §5 改為 §6。SKILL.md 工作流 §6 與〈檢查清單〉同步更新。

起因：用戶裁定，「繼續工作」的意思是先確認工作內容與要開哪些線，開線計畫的表達格式要標準化（2026-10-31）。

**Version**: 1.11.0（2026-10-31）— 新增 `references/line-continuity.md`，涵蓋：

- 判讀四種接續狀態：已收線、`/clear` 後繼續、`/compact` 後繼續、新 session 接手。判讀依據是現行佇列行、session 檔的 `sessionId`，以及 `hook-logs/session-source-diagnostic/diagnostic.log` 中 SessionStart 的 `source`。實測：`/clear` 會換新 `sessionId`，名稱不變；`/compact` 沿用原本的 `sessionId`。
- 主控在 `/clear` 或 `/compact` 後的自我接續：收到第一則訊息時先完成接續，不等用戶提示。
- 主控線的認定：名稱為「主控」的 session 就是主控。沒有這樣的 session 時，請用戶指定一個並改名。
- 名稱與線不一致時，主控要提醒用戶改名或告知新 session 的名稱。

其他檔案的連動修改：

- SKILL.md 新增工作流 §6，〈按需讀取〉與〈檢查清單〉同步更新。
- `session-naming.md` 的規則表新增兩列，§2 補上 `/clear` 保留 user 名稱的實測。
- `wrap-up-and-handoff.md` §5 新增第 0 步。

起因：主控換 session 後要靠用戶提示接續點，並把剛 `/clear` 過的線誤判為未換手的舊 session（用戶裁定，2026-10-31）。

**Version**: 1.10.0（2026-10-28）— 〈按需讀取〉加一列路由到 `line-board` skill（啟用或關閉看板、設定協調票、看板顯示異常）；`references/session-naming.md` §6 狀態列補：`--coord-ticket` 未給時預設讀專案設定檔 `.claude/project-integration/multi-session.json` 的 `coordinationTicket`，與看板同源。起因：看板改為所有專案預設開啟，使用說明住在 `line-board` skill（用戶裁定，2026-10-21）。

**Version**: 1.9.0（2026-10-21）— 〈開線與分線〉新增「佇列變動時同一步寫現行佇列行」一列：排定、改派、開新線、結線時，主控在同一步於協調票 `## Solution` 段追加現行佇列行（獨立成段、行首即 `**L`），新線另寫目標行，結線票序寫 `（無）`。〈檢查清單〉加一項。格式原本只定義在 `references/session-naming.md`〈用語〉，工作流沒有要求何時寫。起因：主控在 context 壓縮後改用條列文字記錄佇列，看板與狀態列對不到線，用戶在看板上看到某線的派發落入「其他」群組（用戶裁定，2026-10-21）。

**Version**: 1.8.0（2026-10-20）— 〈核心原則〉新增「專案進度優先於框架修補」：分線先排推進專案工作的線，修框架或工具的線不超過兩條；新發現的框架問題只有 P0／P1 bug 或用戶要求才排進佇列，其餘觀測進 issue 後關票。〈開線與分線〉「新發現的票」一列改為先判斷要不要排，並新增「開框架清理線」一列（產品線先行、未達兩條、範圍固定）。〈檢查清單〉加一項。清理線的觸發條件與護欄住在 `framework-issue` 的 `escalation-flow.md`，本檔只路由。起因：多條協調線同時運作時，絕大多數票在修框架與工具，修補每次都衍生新票，沒有線推進產品（用戶裁定，2026-10-20）。

**Version**: 1.7.1（2026-10-20）— `references/session-naming.md` §1〈平台對字元的處理〉的中文與空白名稱段，從「尚未實測」改為實測結論：中文名稱可以設定，`ListAgents` 以原字面顯示；含中文與空白的名稱可以用原字面 SendMessage；舊名失效另得一例。依 binary 字串、未實測的部分另列，與實測分開。

**Version**: 1.7.0（2026-10-20）— 新增 `scripts/statusline_lane.py`（狀態列 wrapper，在內層狀態列前加一行 `L<n> │ <名稱>`，線號依協調票現行佇列行解析，解析失敗只省略前綴）與 `tests/test_statusline_lane.py`；`references/session-naming.md` 新增〈6. 狀態列〉寫明啟用方式。起因：用戶切換終端機時需辨認 session 所屬的線。

**Version**: 1.6.0（2026-10-20）— 新增 `references/session-naming.md`：一個 session 一條線、以線主題命名、線完結或轉階段就換 session（開新行程用 `claude -n`）；命名格式只規定三條底線（以線主題命名、本機唯一、不含全形右括號與換行），線號與語言由命名者自定（用戶經 WRAP 裁定）；兩個改名入口（`claude -n` 與只能由用戶輸入的 `/rename`）；改名後舊名立即無法定址、錯誤訊息也不提示新名，所以改名的 session 要告知主控，主控同一步追加現行佇列行；換 session 的步驟與升版後的確認方式。SKILL.md〈開線與分線〉、〈按需讀取〉、〈檢查清單〉各加一列。起因：各線以衍生名稱互稱，終端機不顯示該名稱，用戶切換終端機時分不清哪個 session 是哪條線（用戶裁定，2026-10-20）。

**Version**: 1.5.1（2026-10-20）— `references/wrap-up-and-handoff.md` §1 收尾指示新增第 5 步：收尾時記下的技術債或其他發現，結束前先建票，回報摘要列出新建的票號；另補「PM 查證線的收尾」一段：讀該線的收尾段，看到尚未開票的發現就由 PM 代建。起因：某條線結束時在收尾段寫下一筆技術債，註明「未開票」，直到主控查證才補建。線結束後，記下這筆發現的 session 已經不在，這類發現只剩票面上的一行字。

**Version**: 1.5.0（2026-10-20）— 補三條協調規則，皆出自主控 PM 當日實際做過的判斷。(1) `references/review-flags-and-verification.md` §1 新增「已知回歸暫留 main（分兩輪合併）」：PM 接受的三條件（補修入 acceptance 且第二輪前不 complete、票面預寫〈已知回歸狀態〉、做不成即 revert 第一輪），以及閘門剛開始時改為單輪修正的較佳做法；兩例佐證。(2) 同檔 §1 步驟 2 補「守衛收斂後，轉送審查標記前先比對殘留風險分類表，並附觸發審查的 commit」。(3) SKILL.md〈開線與分線〉「線空出時移票」列補挑票判準：只挑沒有依賴、改動檔案不與原線剩餘票重疊的票。

**Version**: 1.4.0（2026-10-20）— 〈行為變更的判準與分級〉收緊列補一步：合併前在框架文件 grep 會被新判準擋下的例行步驟範例，同票改為等效 CLI 或註明執行限制。來源：守衛收緊後會擋下某 SKILL 步驟記載的 python 片段，由執行者自行 grep 發現；原條文的轉知只送達現有各線，不涵蓋日後照 SKILL 操作的讀者。

**Version**: 1.3.0（2026-10-19）— 補六條協調規則，皆出自主控 PM 當日實際做過的判斷。〈每則來訊的處理迴圈〉第 3 步改為「行為變更依下表分級」，並新增「行為變更的判準與分級」：判準為改動共用資源的對外可觀測面（結束碼、日誌結果字面、參數、建議指令、放行或阻擋結果）；依放行方向分三級——不改放行結果由 PM 直接放行、收緊則放行後轉知、放寬須附正向對照並追到共用函式確認判定失敗時落在保守一側。原第 3 步把所有行為變更都交用戶，與分級後「不改放行結果由 PM 放行」衝突，一併改寫；〈核心原則〉「可預見的裁決提前問」的觸發條件同步收窄為「依分級須交用戶的變更」，否則收緊一級在該原則下交用戶、在分級表下由 PM 放行，兩處判準不一。〈核心原則〉新增「有程式讀者的段落與日誌是介面」：須約定格式、各情況下的欄位語意、記錄間時序。〈開線與分線〉新增兩列：以他線操作作實地驗收證據時比對啟動時刻與 base HEAD；線正在交接時，轉知寫入接手票面。

**Version**: 1.2.1（2026-10-19）— `references/shared-resources.md` §1「閘門驗證期間在主 checkout 提交」一列的處置欄補指向 §4：閘門空出後同樣不在主 checkout 提交，非票面修改一律在 worktree 提交、經閘門合併。原列只講提交時機，讀者照該列處置時看不到 §4 的提交位置，曾在閘門空出後直接於主 checkout 提交並推送 `.claude/` 修改。

**Version**: 1.2.0（2026-10-19）— `references/shared-resources.md` 新增 §6「讀取各線 session 的狀態」：`~/.claude/sessions/<pid>.json` 的位置、欄位、四個狀態值（busy／shell／idle／waiting，waiting 附 waitingFor）、只讀 `*.json` 不讀 `*.key`、以 `TZ=UTC ps -o lstart=` 對 `procStart` 的存活判定（pid 可能被重複使用），以及升版後的三步確認方式；標明量測版本為 Claude Code 2.1.303、屬內部格式無相容承諾。SKILL.md〈按需讀取〉加一列路由。主控原本只能逐一傳訊詢問，而停在等用戶的線要到下一輪工具呼叫才讀得到訊息。

**Version**: 1.1.0（2026-10-19）— 補兩條協調規則。〈核心原則〉新增「可預見的裁決提前問」：某線預告影響全線的行為變更、或其結果會定案一項待裁議題時，PM 在該線回報可合併前先取得用戶裁定，否則該線要多等一輪用戶回覆才能合併。〈開線與分線〉新增「驗收需要他線的分支先合併」：由分支所屬的線自行合併、結果直傳驗收方，驗收方與 PM 不代合，因為代合者不清楚該分支的狀態，合併後出問題無人能接手。兩條皆出自主控 PM 實際做過的判斷，原條文無對應，下一個主控 session 會重新判斷一次。

**Version**: 1.0.1（2026-10-19）— `references/wrap-up-and-handoff.md` §3 補「PM 本身換 session 時，總表要能被 handoff 機制讀到」：交接段標題以「下個 Session 接手 Context」開頭、段內列完整票號、以最後完成的票 `--next` 指向第一張接手票、手動跑排程提示 hook 驗證。原流程只要求寫進工作日誌，交接段標題不符解析器時，CLI handoff 與 Stop hook 的同步檢查都看不到。另補建本檔。

**Version**: 1.0.0（2026-10-15）— 初始建立：主控 PM 統籌多條 session 線的操作手冊（分線、每則來訊的處理迴圈、共用資源協調、只送達標題的審查標記查證、階段收尾與交接），三份 reference 分管共用資源、審查標記與驗證、收尾與交接。
