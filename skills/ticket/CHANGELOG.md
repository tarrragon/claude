# ticket 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。frontmatter 版號同步由後續收尾票統一處理，本檔先行遞增記錄。

**Version**: 2.33.0
**Last Updated**: 2026-09-08
**Status**: Completed

**Change Log**:

- v2.33.0 (2026-09-08): 派發記錄的清除改由事件觸發，不再只靠逾時。既有的 `cleanup_expired`（`turn_ended_at` 已設者 TTL 24 小時、未設者以 `dispatched_at` 起算 1 小時）會把記錄清光，但清光之前的窗口內，共用 git index 的並行守衛把已完成票的宣告當現行範圍，落在該範圍內的提交被誤擋且訊息指向早已結束的票（實測一次提交被迫拆成三次）
  - `complete()` 成功路徑呼叫 `_clear_dispatch_for_completed_ticket(ticket_id)`，fail-open（模組不可用或例外皆寫 stderr，不阻擋 complete）
  - `dispatch-check --prune` 新增獨立的票終態判準（`_is_ticket_terminal`），與既有「`[STALE]` 且 session 確認不存在」判準為 OR、互不依賴，且不受 registry 可用性影響
  - 驗收採反事實形式而非「全量記錄清空」：後者在不修任何東西的情況下等滿 TTL 也會成立，分不出修法生效與時間到了。落地的兩則測試各自構造距 TTL 邊界甚遠的記錄（`turn_ended_at` 設為呼叫當下；空 `ticket_id` + `dispatched_at` 65 分鐘前），斷言事件觸發後立即消失，全程不呼叫 `cleanup_expired`
  - 新增 `tests/test_complete_dispatch_cleanup.py`；`test_track_dispatch_check.py` 增 `TestIsTicketTerminal`／`TestPruneTerminalTicket`
  - 配套的 `clear_dispatch_by_ticket_id` 在框架 lib（非本 skill），空字串一律無操作以保護無票派發記錄那一類

- v2.32.1 (2026-09-08): `fields.py`／`test_fields_set_where.py`／`test_identity_guard.py` 隨框架 canonical 更新（由另一 consumer 撰寫並經 canonical 傳入）；本專案取回後補號，前一版兩側同號而內容不同

- v2.32.0 (2026-09-08): PM 先 claim 再派發時的身份死結補上自動出口。**本批由另一個 consumer 專案撰寫並經框架 canonical 傳入**，本專案取回後補號——兩側先前同標 2.31.1 而內容不同，依版號無從察覺
  - `complete`／`finish` 在身份對照之前，若 `who.current` 仍是 PM 且 `--as` 申報為具名非 PM 執行者，自動把 `who.current` 讓給該執行者再走既有比對（`reassign_who_from_pm_if_takeover`）。原本兩條路都不通：帶 `--as` 被判身份不符，不帶 `--as` 被要求必須提供，而 `who` 是權責歸屬欄位不該由執行者自行 `set-who` 繞過
  - 派發時另有一道事前防線（`dispatch-identity-bind-hook`），把 `who.current` 由 PM 改綁為實際派發的 subagent；本批的 complete 前置讓出是 worktree 隔離派發等前者未觸發時的保底
  - deny 訊息改為直接印出 `who.current` 當前值而非占位符——該值因票而異，派發者無法預知，沿用經驗寫死 `--as rosemary-project-manager` 反而會撞上身份不符
  - 新增 `tests/test_pm_takeover_reassignment.py`

- v2.31.1 (2026-09-08): `track-command.md` 兩處跨檔指涉隨 worktree skill 的內容外移同步更新——原指 `worktree/SKILL.md` 的節與行號，改指其 `references/agent-isolation-worktree.md` 的具名章節。內容變更本身發生於 2.31.0 推送之後而版號未動，兩側同號異容，本版補號使分歧可由版號察覺

- v2.31.0 (2026-09-08): 異源交換掃描的修法群——由另一個並行 session 拿同一份判準重掃本 skill，回報漏抓 8 則、誤判 6 則、已報未修 10 則，本版落地其可執行部分
  - **CLI**：`dispatch --dry-run` 輸出首行加 `[DRY-RUN 未落票]` 浮水印（正式骨架逐字不變），使貼進 prompt 的骨架可辨識是否曾落票；`dispatch` 不論有無 `--note` 一律把 `dispatch-readiness`／`dispatch-validate` 的 exit code 寫入派發日誌，取代原本無痕跡的分支；`dispatch-check` 新增 `--prune`，僅清理「`[STALE]` 且 `session_id` 確認不在 registry 內」的條目，`session_id` 為空或 registry 不可用一律保守保留，結果雙通道寫 stderr 與 hook 日誌。三者的共同形態是「認真做過與完全沒做，產物無差別」
  - **文件與實作對齊**：`architecture.md`〈術語〉鑑識三查改為第 3 查（缺 Exit Status）為 soft warning 不計入拒絕（對齊 `lease.py` 的 `GhostReport.clean`）；`complete` 對 pending／blocked 的 exit code 三檔統一為 2（對齊 `lifecycle.py`）；子任務未全完成為阻擋（exit 1、`--force` 可旁路），非原文的「交接流程」
  - **接手身份規則**：原文「接手時不改寫 `who.current`」與 `complete` 強制 `--as` 合成後，把非原持有者逼向冒用他人身份這條唯一省力路徑。改為明訂兩條路——PM 接手走既有豁免；代理人接手先 `set-who --current <self>` 再 `--as <self>`，並註明 `set-who` 不寫 `who.history`，接手事實須自行留痕
  - **同檔邊界**：〈track commit 子命令〉新增一節說明隔離索引只隔離共用 index、不隔離同一檔案的工作區內容——兩票宣告同一檔案時仍整檔取用，會吸入他票未提交的編輯（本批實測命中一次）；含偵測法與處置，並與框架的檔案內夾帶邊界互指
  - **指涉閉合**：`resume-command.md` 兩處不存在的 `ticket track handoff` 改頂層 `ticket handoff`；`--as` 支援清單訂正為六命令；`depth` 兩套基數（frontmatter `chain.depth` 根為 0、`track depth` 根為 1）各補互指與誤用後果；`create` 的 `--when` 必填補進文件；`migrate` 訊號表主詞、`handoff` 歷史值具名、`create`／`workflow-create` 的數量縮略等九處修正

- v2.30.1 (2026-09-08): `batch-create` 的版本自動偵測改與 `create` 同源——原先只讀 `--version` 未給即報「無法偵測版本」，現改呼叫 `lib/version.py` 的 `resolve_version()`，同一專案結構下兩命令行為一致；明確指定 `--version` 時仍以指定值為準
- v2.30.0 (2026-09-08): 拆分後續兩批修法（冷讀審查與 CLI 缺陷群）；SKILL.md 全檔 4,992 tokens、167 行，路由表雙向零命中
  - **CLI**：`set-blocked-by`／`set-related-to` 多值位置參數 help 明示引號包裹並附 epilog 範例；`track dashboard` 的 `[Handoff Target]` 改走 `resolve_target` 與 `resume --list` 一致，`is_handoff_stale` 補 closed 判定（`--gc`／`--from-worklog`／`resume --list` 共用），`create` 新增 `--dry-run`；`track list` 對 in_progress 列渲染與 dashboard 同源的 lease 標記（`lease.format_lease_tag`），`complete`／`finish` 的 `--as` help 改為強制 deny 語意；`AuditReport` 新增 `artifact_who`／`artifact_updated` 並於 `track audit` 輸出「執行者｜最後更新」行；dashboard auto-GC 歸檔寫持久日誌（`hook-logs/handoff-gc/`），Stop hook 的 stale handoff 由刪除改為歸檔並處理同名碰撞
  - **文件**：入口檔補五詞術語路由、路由表 field-semantics 用途欄與 root 分離節條件語意修正、裸 `complete` 範例補 `--as`；`architecture.md`〈術語〉鑑識三查第 3 查改為 soft warning（對齊 `lease.py`）並補三詞；三檔 `complete` 對 pending／blocked 的 exit code 統一為 2（對齊 `lifecycle.py`）；`track-command.md` 新增〈子命令總覽（全量對照 --help）〉涵蓋 89 個子命令，1-E 斷言支撐 F4–F17 補來源，`--as` 支援清單訂正為六命令；`resume-command.md` 兩處 `ticket track handoff` 改頂層 `ticket handoff`；`migrate`／`handoff`／`create`／`workflow-create` 指涉閉合與計數縮略修正；`create-command.md` 量測值補方法與環境
- **拆分總結**（依 skill-design-guide 重整，issue tarrragon/claude#94；來源：拆分系列，跨 v2.22.0–v2.29.0；before 取自重構前快照 `8f634fa43`，after 為本輪收尾實測）：入口檔 `SKILL.md` 全檔（含 frontmatter）14,347 → 4,971 tokens、body 14,133 → 4,875 tokens（框架分段估算公式：非 ASCII 1.3 字元/token、ASCII 4 字元/token；Progressive Disclosure 第 2 層門檻對象為全檔，< 5,000）、593 → 167 行、frontmatter `description` 596 → 224 字元、`##` 節數 12 → 5、`references/` 檔數 15 → 14；子命令路由表〈涵蓋章節〉欄與各 `references/*.md` 的 `##` 標題逐字雙向比對零命中（fenced block 排除）。逐版異動見下列各條目。
- v2.29.0 (2026-09-08): 同步 Round 3 CLI 缺陷修復群六項行為變更至文件（skill-cli-sync-check）
  - **track commit 目錄展開排除他票宣告檔案**（3-B B1）：〈track commit 子命令〉「files 子集規則」補「目錄展開的並行過濾」段，說明展開時讀取 `.claude/dispatch-active.json` 排除其他活躍派發宣告路徑的變更檔（並行防護加強層，非安全邊界本身；registry 讀取失敗 fail-open）
  - **track commit 空 tree 短路提示 --worktree**（3-H 案 3）：同節「Exit code」表的 exit 0 說明句更新為與實際 stdout 字面對齊，含「若變更實際發生在 linked worktree 但未帶 --worktree……」提示句
  - **track set-exit-status 加 --as／who.current 身份檢查**（3-F F3）：〈track set-exit-status 子命令〉Flag 說明表補 `--as` 列，並新增「`--as` 身份檢查與 `--force` 的邊界」段，說明未帶 `--as` 維持 warn-only、`--force` 不可旁路身份不符的 deny
  - **track reclaim --confirm 落地鑑識報告**（3-F 共用原則項目 5）：〈track reclaim 子命令〉「Exit code」後新增〈`--confirm` 落地：鑑識報告寫入 Solution〉子節，說明三查全過且 `--confirm` 落地後 append-log 進票面 Solution，落票失敗不影響 reclaim 本身狀態轉換
  - **track dispatch-check 新鮮度維度**（3-H 個案 1／2）：〈track dispatch-check 子命令〉「判定規則」表補新鮮度標註欄位，新增「新鮮度標註」段（沿用 `DEFAULT_STALE_THRESHOLD_MIN` 60 分鐘慣例，`(Nmin)`／`[STALE Nmin]` 兩態，逾時彙總行），「WARN 後下一步」段同步改寫（原「本命令不判斷條目是否逾時」已被新行為取代）
  - 逐項以 `ticket track <子命令> --help` 實跑核對旗標與字面；SKILL.md 路由表對應列摘要層級未含受影響細節，未發現需同步的不一致，本次不變更
- v2.28.0 (2026-09-08): 零住址前提承接章節（3-G G1／G4／G5、3-D P4）
  - **G1 where.files 宣告語意**：`field-semantics.md`〈適用範圍〉新增〈where.files 宣告語意〉子節作唯一住址（`::read`／`::write` 後綴、type 預設意圖、目錄型宣告展開／WARNING／dispatch 硬擋，來源 `ticket_system/lib/file_conflict.py`）；`track-command.md` 六處（`track commit`／`track dispatch`／`track runqueue --groups`／`track conflicts` 判定規則 4／`track onboard` 髒檔歸屬／`track dispatch-readiness` 閾值 2 檢查 5-6）與 `create-command.md`〈多值參數格式〉各追加一句指回新住址，各自角度不變
  - **G4 registry 契約住址**：`track-command.md`〈track sessions 子命令〉〈Registry 位置與 Schema〉補「契約住址」條目，明指 `.claude/lib/pm_registry.py` 檔頭 docstring 自稱「Registry Schema 契約 v2（單一來源）」為 schema 唯一權威
  - **G5 Exit Status→handoff JSON 橋**：`resume-command.md`〈handoff JSON 格式〉新增〈`exit_status` 欄位〉子節，說明 `ticket track handoff` 建立 JSON 當下讀來源 ticket body `## Exit Status` 章節（`handoff.py:_extract_exit_status_for_handoff`）並抽取寫入，列出寫入端／橋接端／兩個讀取端（`runqueue --context=resume` 讀 JSON；`reclaim` 第 3 查直接讀票面，不經橋接）四角色分工表
  - **P4 並行協調入口**：`SKILL.md`〈子命令路由表〉「（跨子命令）」列補一句指名 `.claude/pm-rules/parallel-dispatch.md`〈並行安全檢查〉與 `.claude/references/cross-session-coordination-details.md`
  - 反證方法：四項各先 `rg` 全站（pm-rules／references／methodologies／rules／hooks docstring）確認無既有住址後再建章／改路由

- v2.27.0 (2026-09-08): multi-round-review Round 3 修法（群 D-3：resume/generate 槽位名、三檔 footer 清理、acceptance-gate 表改實作分支、handoff 狀態表統一載體、workflow-query/execute 亦由此進入、4V/建立範本欄名對齊；併吞範圍重疊的驗收表覆核票，已標記 superseded 並 close）
  - **槽位名統一**（R-8）：`resume-command.md`／`generate-command.md`〈參數說明〉→〈Flag 說明〉，與其餘檔案一致；`SKILL.md` 路由表 `resume`／`generate` 兩列涵蓋章節欄同步
  - **Footer 清理**（3-A R5）：`field-semantics.md`／`handoff-command.md`／`ticket-lifecycle-details.md` 三檔尾 Last Updated／Version footer 整段刪除（歷史已在本檔 v2.22-2.25 條目載明）；`field-semantics.md` 初版 Source（ANA 多視角審查衍生的 SSOT 建立票，見該檔〈溯源〉段）移入該檔檔頭〈溯源〉段保留
  - **acceptance-gate-hook 技術細節改為實作分支**（3-H 必修 2）：`ticket-lifecycle-details.md`〈acceptance-gate-hook 技術細節〉檢查邏輯表改依 `check_acceptance_status()` 實際 5 個阻止情境（children 未完成、防護類 hook 票缺必含項、ANA spawn 規劃不一致、`multi_view_status` 值非法、實驗器材殘留）與 2 個警告情境（驗收記錄缺失、ANA 缺後續 ticket）改寫；舊「根任務／子任務分列」「所有子任務是否驗收」判準與程式碼無對應函式，已移除；阻止／警告場景固定文字範例（與實際訊息不符）改為指向對應 checker 模組；補「驗收方式判準」段說明僅 priority P0 且非 DOC/ANA 才提醒派 acceptance-auditor、subagent 呼叫一律略過提醒改由 PM 於 complete 後補派；〈驗證結果對應表〉更正為 `lifecycle.py complete()` CLI 層級（非 hook 層）之驗證結果，`pending`／`blocked` 狀態 Exit Code 由誤植的 1 修正為 2（`precondition.require_in_progress()` 實際回傳值）；〈驗收提示訊息模板〉三段固定文字模板（暗示驗收為前置關卡）改為條件分支表（對齊 `AskUserQuestionReminders.COMPLETE_REMINDER`／`COMPLETE_NEXT_STEP_REMINDER` 實際觸發條件）
  - **handoff 狀態→旗標兩表統一載體**（3-G D）：`handoff-command.md`〈按 Ticket 狀態選擇命令〉6 列表為載體，補回原缺的「`in_progress` 使用 `--to-sibling`／`--to-parent` CLI 拒絕」禁止行為列；`workflow-handoff.md`〈狀態-命令映射規則〉節內容改為一行指回 `handoff-command.md`，決策樹本身不動
  - **workflow-query／workflow-execute「亦由此進入：無」改寫**（3-A）：grep 反證顯示 `workflow-create.md` 首段引言句實際把讀者送到兩檔（任務已存在時改讀），兩檔檔頭改列此指標
  - **4V 節與建立範本欄名對齊**（3-G 小型）：〈驗收條件 4V 格式要求〉「標準格式」改為 frontmatter `acceptance` 清單示例（`set-acceptance --add`／`check-acceptance`，全 skill CLI 實際操作對象），原 body 表格式改標「報告格式（僅供人工呈現，CLI 不讀取）」；〈Ticket 建立格式範本〉frontmatter `assignee: pending` 改為 `who: {current: pending, history: {}}`，對齊 `track-command.md`〈CLI 可修改欄位〉與實際 ticket frontmatter 結構
- v2.26.0 (2026-09-08): multi-round-review Round 3 修法（群 D-1：SKILL.md 空殼節、reclaim 拒絕處置句、SessionStart hook 入口對齊、architecture.md 類比與術語指標）
  - **空殼節降級**（PM 通讀 R-1）：`## 系統模型（設計自我描述）`、`## Ticket Body Schema（type-aware）` 兩個僅剩一行路由的空殼節整節刪除，內容已分別由〈子命令路由表〉「（跨子命令）」列與表後既有一句涵蓋，不重複維護；入口檔 `##` 節數由 7 降為 5
  - **執行方式節首**（R-2）：去除與標題同名的粗體標籤「**執行方式**：」
  - **孤立來源句改寫**（R-3；3-D P1）：`> 來源：v2.7.0` 改為說明句，明寫 `track onboard`／`track runqueue` 為輔助／除錯入口、裸 `/ticket` 一律先走本節 dashboard-first 流程，版本沿革改指本檔 v2.7.0 條目
  - **他專案殘留措辭**（R-4）：`batch-create`〈使用情境〉的「W28 場景」改為通用措辭
  - **reclaim 拒絕處置句**（R-5；3-F F3；用戶裁決 D2）：刪除「補 `set-exit-status`」SOP（該動作等同接手者為他人票製造第 3 查通過條件，與實作第 3 查為 soft warning 不符），改為「拒絕：即停手回報 PM」
  - **身份句可執行化**（R-6）：「身份仍為 who.current」改為「接手時不改寫 `who.current`，依票面既有身份繼續操作」
  - **SessionStart hook 入口對齊**（3-B B3）：`:79` 除錯查詢句改寫為「兩支 SessionStart hook 會在用戶輸入前先印出此類提示作為歷史入口，PM 實際接手流程仍以 dashboard-first 為主」，不再宣稱「不再呼叫」（與 hook 實際輸出相符）
  - **track 子族選列判準**（3-B (1)）：路由表引言補一句宣告子族獨立成列的判準（具獨立 exit code 語意或需額外理解流程分支者才獨立成列，其餘於 track-command.md 以 `##` 子節呈現）
  - **選樹閘門**（3-G G3）：路由表後補一行「依處境選樹」對照（新任務／已認領／查現況／交接恢復／改 ID 各自對應的 workflow-*.md）
  - **路由表用途欄補齊**（重組後遺症可改）：create-command／workflow-query／track-command／handoff-command／migrate-command 5 列的第二列用途欄補回差異化「何時讀」句
  - **術語節指標前移**（3-A R4）：檔頭引言句補系統模型與術語指標，確保 `票面`／`接手`／`鑑識三查`／`落票`／`隔離索引` 等詞在 SKILL.md 內首見前已有 `references/architecture.md`〈術語〉指標（原指標隨系統模型節刪除而移除，改置於檔頭引言）
  - `references/architecture.md`〈系統模型〉補「類比邊界」說明（3-B (4)）：CI runner 類比僅在「身份晚綁定」「type/instance 一對多」成立，「共享工作區」為本系統相對 CI runner 隔離慣例的反向自身選擇，不在類比射程內；同節「named agent 生命週期三態」下「idle 態」段原「工作區仍隔離」與此矛盾，同步修正為「工作區仍為預設 2 的共享語意」
  - `references/architecture.md` `### named agent 生命週期三態` 標題後綴 `（v2.9.0 擴展）` 移除，溯源改節首「> 來源：」句（3-A R5 種子後綴殘留第 3 處）；檔頭「亦由此進入」對 SKILL.md 系統模型節末的指涉同步改為「SKILL.md 檔頭引言」（原節已刪除）
- v2.25.0 (2026-09-07): multi-round-review Round 2 修法（群 C2b：`track-command.md` 九個子命令節設計敘事後置、共用旗標節、槽位名統一、五檔 H2/H3 段標溯源後綴刪除、`messages.py` 落地 `architecture.md`）
  - **段標溯源後綴刪除**（17 處，決策：後綴對讀者零價值，溯源移各節首行「> 來源：……」）：`track-command.md` 11 個子命令 H2；`resume-command.md`〈恢復機制〉；`handoff-command.md`〈指向語意：source vs target〉+ `--from-worklog` 子命令 + `--next` 子旗標；`migrate-command.md`〈Collision Detection〉；`SKILL.md`〈無子命令時的預設行為（dashboard-first）〉。三面同步（各檔本檔章節行、`SKILL.md` 路由表涵蓋章節欄、`SKILL.md` 正文逐字引用）已以 fenced 外雙向 awk 比對驗證零命中
  - **九子命令節設計敘事後置**（`track-command.md`，2-D finding F8-F17）：`runqueue`（第二層加權改寫為 PM 手動判斷規則、`--groups` 演算法段後置為〈判定機制〉子節、實作沿革行移本檔）；`UPDATE 操作補充`（complete 副作用自辯句刪、title/what 量測移本檔、claim 半成功歷史背景移本檔）；`board`（`--group-by topic` 選型論證改選用對映表）；`dashboard`（tool call 量測移本檔，節首壓一句）；`reclaim`（判準句提前粗體、差異溯源句壓縮）；`activity`（父子票邊界演算法敘事壓成判準句，機制指向 `track_activity.py` 註解）；`conflicts`（lead 動作先行、Python 測試路徑推導演算法壓成規則句）；`onboard`（lead 動作先行、髒檔歸屬設計改輸出判讀對映表）；`hook-liveness`（〈動機〉子節名改〈0 筆結果的判讀〉）
  - **共用旗標語意（track 系列命令通用）**：新增章節統一定義 `--all`（無作用旗標）與 version-agnostic 註冊機制，六個掃描全部 active 版本的命令原逐段重複說明改為指標；「復用 X，不重 Y」7 處僅首例保留完整句，其餘只留「復用 X」
  - **槽位名統一**：`track-command.md`〈track board〉`選項說明`→`Flag 說明`、兩處`設計邊界`→`設計約束`（與本檔其餘 9 處一致）；`migrate-command.md`〈選項說明〉→〈Flag 說明〉；`handoff-command.md`〈基本用法〉（僅一句）併入〈用法〉首句。`resume-command.md`／`generate-command.md` 的〈參數說明〉槽位維持原名——後者不在本批修改範圍，單改前者會製造新的不一致，留待涵蓋該檔的後續修法一併處理
  - **`messages.py` 落地**：`track-command.md`〈統一錯誤訊息格式〉〈CLI 錯誤分類〉112 行全文併入 `architecture.md`〈共用模組設計〉### messages.py，新增「統一錯誤訊息格式」「CLI 錯誤分類」兩子節（CLI 錯誤分類新增「訊息形態→處置對映」句，設計理由三條 bullet 標為「依據，非動作」）；`track-command.md` 原位改一句路由
  - **Footer 清理**：`workflow-handoff.md` 檔尾 Last Updated／Version／Source 三行整段刪除（`SKILL.md` 已宣告版本紀錄在本檔，內容與下方保留摘要重複）；`handoff-command.md` 檔尾歷史版本壓縮為單行 Version 摘要，歷史保留於下方
  - `handoff-command.md` 原檔尾歷史版本（供查閱）：

    > **Version**: 1.4.0 — multi-round-review Round 2 修法：〈Session 結束時的使用方式〉步驟 0 命令改 `--gc --dry-run`（`--status` 不列 pending handoff 檔，命令與宣稱目的不符）並補「殘留」判準；〈任務鏈結束時的替代流程〉重述〈設計意圖〉首句的粗體段改一句指標；〈同目錄〉移除跨檔重複公式，只留角色標籤
    > **Version**: 1.3.0 — 檔頭「亦由此進入」改指實際節內段落（〈交接流程決策樹〉節內「讀取端」段）；〈任務鏈結束時的替代流程〉粗體段標問句改直述；〈五種情境〉表補 `--next`（絕對指向）歸屬說明
    > **Version**: 1.2.0 — 設計意圖段補「設計原則」引用指向 `handoff-design-principle-methodology.md`
    > **Version**: 1.1.0 — 同步落地：新增「指向語意：source vs target」章節（含 target_ticket_id 欄位 + resolve_target 優先序）、`--next` 子旗標說明、`--next` vs `--auto` 對比表

  - `workflow-handoff.md` 原檔尾（供查閱）：

    > **Last Updated**: 2026-05-08
    > **Version**: 1.1.0 — 同步落地：交接決策樹新增「絕對指向（target_ticket_id）」分支，加入 `--next` 模式對比表與覆蓋指令

  - `track dashboard`〈設計目的〉原量測（供查閱）：

    > ANA 量測：原 `/ticket` 裸命令流程從入口到顯示待辦需 **7 個 tool call**（含 1 次 `--format` 試錯與 5 次可消除的重複呼叫）。Dashboard 將此降至 **3 個 tool call**（dashboard + claim by number + 後續動作），符合 `/ticket` 與 resume 系統「加速 PM 接手」的原始設計目的。

  - `track runqueue`〈實作現況〉原「典範」行（供查閱）：

    > 基礎 runqueue 實作；三視角審查（Evidence/Alternatives/linux）收斂結論；軸 C 補強 spawned 加權規則。

  - `track UPDATE 操作補充`〈title 與 what 是兩個獨立欄位〉原量測（供查閱）：

    > 2026-08-18 量測 741 張票，124 張（17%）兩者刻意不同。

  - `track UPDATE 操作補充`〈claim 推薦用法〉原「半成功歷史背景」（供查閱）：

    > 早期 `claim --yes` 在 subagent 無 TTY 環境曾因互動受限出現 metadata 部分寫入、需 `--skip-verify` 二次嘗試確認的半成功狀態。此 root cause 已由「claim 預設不驗證」+「移除 `--skip-verify`」兩階段修正消除；現行裸 `claim` 路徑無此問題。
- v2.24.0 (2026-09-07): multi-round-review Round 2 修法（群 C3：`create-command.md`／`field-semantics.md`／`handoff-command.md`／`resume-command.md`）。
  - `create-command.md`〈基本用法〉五則範例原皆缺必填的 `--acceptance`，四則另缺 `--where-files`——`ticket_builder.py` 的 `validate_create_checklist` 要求至少一項兩者皆備，缺任一項於持久化前 `exit 1`；五則範例已全部補齊。〈重複偵測（兩層防護）〉的 Tier 2 設計用途與 birth time 判定兩段教材，原置於 `--allow-duplicate` 旁路命令之前，改為被擋時判準句（先問「是同 turn 重複 spawn 嗎」）置於旁路子節首，教材壓成依據句。〈必填條件〉「必須提供」兩條列表項原分列，實為 AND 關係（讀者易誤讀成各自獨立充分條件），改為單句「建立根任務且 type 不是 DOC 時」；「可省略」（OR 關係）維持清單並註明任一成立即可省略
  - `field-semantics.md`〈阻擋語意對照表〉:145 `spawned_tickets`（ANA 類型 source）表格格原寫「過渡狀態，IMP 收斂後將移除」，與同檔 :150 現況分層說明（hook 層舊機制已退場為 warn-only，但 `lifecycle.py`／`acceptance_auditor.py` 兩獨立機制仍實際阻擋）矛盾——前次修法只改了說明段、表格格殘留舊字。表格格改為「是（`lifecycle.py` 確認關卡＋`acceptance_auditor.py` 稽核，已定案）」。blockedBy 節內 Action 三條原置於量測論證段之後，資訊優先序倒置，改為 Action 在前、量測壓成一句「依據：既有量測（2285 票語料，精準度上限 25%），見本檔」。relatedTo 節兩則「裁決（2026-08 定案）」決策紀錄原為完整論證段，壓成一句保留裁決本身，論證移入本則
    - blockedBy 量測完整論證（原文保留供查閱）：2285 票語料、913 筆「When 含 ID 且 blockedBy 空」母體、61 筆系統抽樣；43% 的提及屬出處／並行標記／反向依賴而非依賴；依賴語意組中 32/35 於建立當日前置已完成（follow-up 慣例，warn 無效益）；即使限定「提及票尚未 terminal 才警」，精準度仍僅 25%（3 真漏標對 9 誤警——母票 umbrella in_progress、並行標記、反向依賴為結構性誤警源，散文層無法可靠排除）。真實漏標率約 5%，已有接手端補償 SOP
    - relatedTo 裁決一（儲存方向）完整論證：維持儲存單向 + 消費端 1-hop symmetric union，避免下游工具漏失多數未回填關聯（實測 1246 票語料，僅 13.3% 對稱率，改無向儲存需回填既有邊成本），同時不承擔改為無向儲存所需的既有邊回填成本；反向索引工具實作為獨立追蹤項目
    - relatedTo 裁決二（context bundle 消費）完整論證：relatedTo 是 context bundle 的合法消費來源，非規範外行為。本裁決取代先前「relatedTo 不作為任何流程訊號」中隱含的「不被任何工具消費」推論——流程訊號（排程、阻擋、血緣）與 context 供給是兩件事，前者維持無，後者已由既有實作（`context_bundle_extractor.py` 的 `SourceKind` 含 `related_to`）承擔
  - `handoff-command.md`〈Session 結束時的使用方式〉步驟 0 原命令 `ticket handoff --status`，但 `--status` 顯示的是任務鏈與建議下一步，不列 pending handoff 檔，命令與宣稱目的（確認無殘留 pending handoff）不符；改為 `ticket handoff --gc --dry-run`（實測輸出「無 stale handoff，pending 目錄已清潔」正是此目的），並補「殘留」判準：僅指已完成票的 stale JSON，不含待接手者的合法 pending。〈任務鏈結束時的替代流程〉原有一段粗體「理由」重述〈設計意圖〉首句，改為一句指標「理由見〈設計意圖〉」
  - 四檔〈同目錄〉欄原用跨檔重複公式「與本檔互補：決策樹在那份、細節在本檔」，改為僅留檔名＋簡短角色標籤；`resume-command.md`〈溯源〉原長句「本機 git log 對本檔僅見這一筆……」（14 檔中 7 檔逐字重複的模具句，本檔無實質拆分點內容）改短記號「匯入時已存在（`f375ae675`），無拆分點」；`resume-command.md`〈恢復流程〉與〈用法〉內三處逐字相同的 dashboard-first 路由句，保留〈三個入口的分工〉（原〈設計原則〉，改名以符實際內容為三入口→行為對映而非教材框架）節內一處完整路由，另兩處改短指「走 dashboard-first」
- v2.23.0 (2026-09-07): `resume-command.md` 的〈歷史變更〉章節（v1.0→v2.0 顯式觸發變更敘事）遷入本檔，該檔內同段刪除；同批修正 `resume-command.md` 三處誤稱裸 `/ticket` 為「自動偵測 pending handoff」，改指 `SKILL.md`〈無子命令時的預設行為（dashboard-first）〉；`track-command.md` 修正片假名中點 `IO・YAML`（2 處）為 `IO／YAML`、〈runqueue 排序規則〉第二層 `spawned_from_completed_ana` 加權標明僅為規則面設計、CLI 尚未實作（`track_runqueue.py` 零命中）、Priority tier 表補上缺漏的 `P0` 層級、`dashboard` 子命令節補齊 `[LIVE]`／`[RECLAIMABLE]` 標記語意與輸出範例、統一「三章節」與實際「四區塊（含 Handoff Target）」的描述落差、`reclaim`〈設計取捨〉與 `onboard` 首段的否定起手定義句改寫為正面先立、口語「真的」3 處刪除（含 `field-semantics.md` 1 處）、`list` 子命令排序規則的括號並列形態統一；`field-semantics.md` 檔頭「亦由此進入」兩條指涉修正為實際節名（`create-command.md`〈--source-ticket 參數（衍生關係）〉、`track-command.md`〈UPDATE 操作補充：commit 副作用與欄位語意〉### 六欄位語意 SSOT）、〈相關文件〉的 `SKILL.md` 死指涉改指 `track-command.md`〈READ 操作〉〈track deps / depth 子命令〉；`field-semantics.md` 與 `create-command.md` 對稱兩處「阻擋為過渡狀態、後續 hook 收斂後將回到不阻擋」改寫為現況分層說明——hook 層舊版 spawned 檢查已退場為 warn-only，但 `lifecycle.py` 的完成前確認關卡與 `acceptance_auditor.py` 的 spawned 全完成稽核 FAIL 判定仍實際阻擋，此為已定案現行設計，非等待收斂的過渡態
  - `resume-command.md` 原〈歷史變更〉內容（供查閱）：v1.0 使用 `handoff-prompt-reminder-hook.py`（UserPromptSubmit）自動注入 Ticket 完整內容；v2.0 改為顯式觸發，理由是 Hook 自動注入會劫持用戶意圖（任何第一條訊息都被覆蓋），因此停用
- v2.22.0 (2026-09-07): `ticket-lifecycle-details.md` 的〈變更日誌〉章節（一次性歷史敘事，v2.0.0-v4.0.0）遷入本檔，該檔內僅留指標句；同批修正該檔 P0 節否定起手定義句、檔頭重複舊引言、驗收提示訊息模板的死名節引用、驗收條件來源範例改節名形式、建立範本 `type` 欄位對齊正典 4 型（IMP/ADJ/ANA/DOC，原列 RES/INV 兩型已移出正典）、與 `field-semantics.md` 同目錄互引不對稱；`handoff-command.md` 檔頭「亦由此進入」指涉段落改實際節內段落、任務鏈結束替代流程的粗體段標問句改直述、〈五種情境〉表補充 `--next`（絕對指向）不列入該表的歸屬說明
  - `ticket-lifecycle-details.md` 原 v2.0.0-v4.0.0 版本歷史（供查閱）：v4.0.0 瘦身重構移出至 details 參考文件（從 ticket-lifecycle.md 移出格式規範、訊息模板、Hook 技術細節，精簡版保留核心決策規則）；v3.1.0 統一驗收派發規則移除 PM 直接驗收；v3.0.0 將驗收流程從 complete 之後改為 complete 之前；v2.9.0 新增執行日誌驗證機制；v2.8.0 取消驗收豁免機制改為契約式驗收；v2.7.0 強化驗收代理人派發要求；v2.6.0 新增任務層級判斷規則；v2.5.0 新增階段-標準流程對照表和任務鏈後續步驟建議；v2.4.0 新增建議追蹤流程整合章節；v2.3.0 新增驗收條件格式要求章節；v2.2.0 新增任務鏈 ID 格式章節；v2.1.0 新增 Ticket 有效性驗證章節；v2.0.0 重構為 TDD 含 SA 前置審查流程版本
- v2.21.0 (2026-09-07): 補記 2.20.0 之後累積但未 bump 版號的變更。版號未動使發佈庫與本庫的內容分歧無法由版號察覺——版號相同時它主動宣稱兩邊一致，分歧因此不會被例行同步檢查發現，故補此一版號涵蓋下列各項
  - `track commit` 新增 `--worktree <path>`：把 read-tree / add / diff 等 git 操作綁定到檔案實際變更所在的 linked worktree。未指定時行為不變（沿用 `resolve_project_cwd()`）；指定但非合法 git 目錄時拒絕提交
  - `paths.py` 新增 `get_ticket_state_root()`：linked worktree 內執行的 ticket 狀態操作（`claim` / `append-log` / `check-acceptance` / `set-*` 等 md 讀寫與其 auto-commit）反向回推主倉庫根目錄，統一寫入主倉庫。`track commit`（程式碼提交）維持 worktree 感知不變，兩者是不同的 root 解析路徑。SKILL.md 新增「Ticket 狀態與程式碼提交的 root 分離」章節說明此差異，避免被誤判為 cwd 解析缺陷
  - `track dispatch-readiness` 由三項認知負擔閾值擴為六項檢查：新增檢查 4（acceptance 與寫入集一致性）、檢查 5（`where.files` 路徑存在性）為 warn-only 啟發式，檢查 6（acceptance 提及路徑須被 `where.files` 涵蓋）為強制 fail。exit 2 的處置依 fail 來源分流（閾值 1-3 超標為拆票，檢查 6 為補 `where.files` 或改寫 acceptance），不依 CLI 統一提示行字面行事
  - `track conflicts` 新增 `--for <id>` 與 `--among <id1,id2,...>` 針對性查詢（`file_conflict.compute_targeted_conflicts`），並行派發前不必人工 grep 全量輸出。同時提供時 `--among` 優先
  - `fields set-where` 的範圍宣告變更改為獨立 auto-commit（與 `set-acceptance` / `append-log` 同保護等級）；`where.files` 路徑不存在時只警告不阻擋（新檔案的 where 宣告合法）
  - `parser.py` 新增 frontmatter 磁碟快取：以 `(mtime, size)` 為失效鍵，`save_ticket` 寫入時同步失效。僅生產路徑啟用，`TICKET_SYSTEM_TEST_ISOLATION` 存在時完全略過，避免 tmp_path 快速覆寫下 mtime 精度不足的假命中
  - `track dispatch` 的骨架組裝抽出至 `lib/dispatch_skeleton.py`；ANA ticket metadata 品質警告（who 代理人分工 / acceptance 長度分號 / tdd_phase 合理性）由 hook 遷入 CLI 的 `lib/ana_ticket_metadata_validator.py` 與 `lib/command_lifecycle_messages.py`
- v2.20.0 (2026-08-24): 新增子命令 `set-parent`：修正 `parent_id`（改寫或清除），並同步維護上游票 `children` 的雙向一致性；補上 `add-child` 一直缺少的反向修正路徑（誤用 `--parent` 建錯關係後的合法修正途徑）
- v2.19.0 (2026-08-24): `runqueue` callout 補一則語意提醒：輸出的 `blockedBy=[...]` 為未解除阻擋清單，與 ticket frontmatter 同名欄位的原值可能不同（後者保留宣告時完整清單，不隨 blocker 解除而改寫）；血緣或狀態對帳應以 frontmatter 為準
- v2.18.0 (2026-08-24): `create` 新增 `--discovered-during` 旗標，區分規劃衍生與發現衍生的建票語意
  - 與 `--source-ticket` 互斥：發現衍生（執行中撞到跨主題問題）的上游主題與新票內容無關，S1 判準在此情境下短路不觸發主題繼承
  - frontmatter 新增 `discovered_during` 欄位記錄血緣，但不驅動任何主題指派；S2 檔案叢集判準不受影響，仍依新票自身 `--where` 運作
  - create 章節新增「`--discovered-during` vs `--source-ticket`」對比表，體例比照既有 S1/S2/S3 判準表
- v2.17.0 (2026-08-21): `complete` 章節補兩則說明：(1) ticket metadata 自動提交時機改為呼叫當下的隔離索引提交後，metadata 與對應程式碼變更恆分屬兩個 commit，追溯下游流程（含 sync 本框架的其他 consumer 專案）須知情此語意；(2) 確認 `--no-stage` 已足夠覆蓋「想連同程式碼一起提交」的情境，並記錄選用該旗標放棄的保護與對應風險
- v2.16.0 (2026-08-21): 新增「覆核測試指令（skill 自身測試套件）」章節：明訂裸 `pytest`（不帶路徑參數）為唯一標準覆核指令，`pyproject.toml` 的 `testpaths` 已統一收斂 `tests/` 與 `ticket_system/tests/`；禁止以顯式路徑指令作為覆核依據（顯式路徑會覆蓋 testpaths，使另一目錄測試被靜默漏跑）
- v2.15.0 (2026-08-21): 彙整上次 canonical 同步後累積、未隨個別 commit 遞增版本號的多筆行為變更（分歧判定時發現，共 28 個 commit，僅列使用者可感知的介面差異）
  - 新增子命令 `set-closed-by`：修正已 closed 票的 `closed_by` 欄位
  - `append-log` 新增 `--replace` 旗標：整段覆寫指定章節內容，取代累積式 append
  - `create` 的 auto-commit 時點移至 Context Bundle 寫入之後（原本先 commit 後寫入 Context Bundle，導致該次寫入未隨 commit 一併留存）
  - `check-acceptance` 補上 auto-commit，對齊 `set-acceptance` 既有的保護等級
  - `create` 新增 when-blockedBy 一致性 WARNING：`--when` 語意與 `--blockedBy` 指定的前置票狀態衝突時提示
  - `create` 版本未註冊時，錯誤訊息新增 `--version` 繞過指令的 fallback hint
  - 修正 `set-blocked-by` / `set-related-to` 誤用逗號分隔時的提示文字：改回兩個子命令各自專屬的提示，不再共用易混淆的通用訊息
  - 修正 precondition 對已 completed 票的建議文案：原指向不存在的 `reopen` 命令，已修正為實際可用的操作
  - `audit_version` 新增 `detect_orphan_references` 雙向一致性檢查
  - `onboard` 新增「無主髒檔」小節
  - 修正 Context Bundle 讀取端 `blockedBy`/`relatedTo` 欄位雙態鍵名不相容導致的恆失效
- v2.14.0 (2026-08-20): `create` 新增 `--no-topic` 與過渡期 WARNING
  - 主題 callout 補 warn-only 語意：三判準未命中印 WARNING 但不改 rc，理由為避免代理人誤判建票失敗
  - 補 `--no-topic` 說明：明示不指派、與 `--topic` / `--new-topic` 互斥、衝突時於持久化前 exit 1

- v2.13.0 (2026-08-20): `create` 主題自動推導上線
  - create 章節新增「主題歸屬（自動推導）」callout：S1 上游繼承 / S2 檔案叢集 / S3 ANA 標記三判準與各自成本
  - 明示顯式 `--topic` / `--new-topic` 優先，推導僅在兩者皆未給時啟動（既有呼叫端行為不變）
  - 記錄 S2 的 3 段特異性門檻依據（淺層路徑會使單一主題成為所有新票的推導結果）

- v2.12.0 (2026-08-20): `board` 新增 `--group-by {wave,topic}` 分組軸
  - 新增「Board 分組軸 — `board --group-by`」callout：預設 `wave` 輸出逐字不變、`topic` 依主題分組
  - 主題節標題格式、排序雙鍵（最高優先級 → 票數降冪）、未歸屬節置底規則
  - 主題歸屬來源明示為 `lib/topic_assignments` 中央清單（非 frontmatter 欄位）
  - `references/track-command.md`「track board 子命令」同步補選項表與分組軸章節

- v2.11.0 (2026-08-18): dashboard-first 流程接手選項加入 lease 存活過濾（framework issue tarrragon/claude#78）
  - [In Progress] 條目帶 `[LIVE]` / `[RECLAIMABLE]` lease 狀態標記說明（CLI 同日落地，判準同 registry heartbeat）
  - `[LIVE]`（FRESH session 持有）票禁止列入 AUQ 接手選項，僅資訊性提及——防止跨 session 重複處理
  - `[RECLAIMABLE]` 票列入選項但路由至 `ticket track reclaim`（鑑識三查），非直接 resume

- v2.10.0 (2026-08-04): 系統模型章節新增第三條「type 與 instance 一對多」反直覺預設（列表由二條擴為三條，標題同步改「三個」）：明示 agent 類型與執行體非一對一、同類型可同時 spawn 多個獨立執行體；緊接帶出反向風險——並行上限來自共享 git index 寫入競爭、主線程序列化的驗收與建票工作、執行體 context 累積三項約束，而非類型數
- v2.9.0 (2026-07-08): 系統模型章節新增「named agent 生命週期三態」——擴展 agent=CI runner 類比從二態（running/stopped）為三態（新增 idle=warm runner），路由 PM 回收 SOP 到 parallel-dispatch.md
- v2.8.0 (2026-07-04): 新增「系統模型（設計自我描述）」章節——issue tracker + CI runner 為主類比、batch job queue 為輔，明示身份晚綁定與共享工作區兩個與 process 直覺相反的預設（設計回顧落地）；修正 stale 描述「priority 等欄位無 CLI 命令」（`set-priority` 已存在且完整接線，描述與 code 對齊）
- v2.7.0 (2026-05-27): `/ticket` 裸指令預設行為改為 dashboard-first 流程（源於 ANA 結論方向 a）
  - 步驟 1 從 `ticket track runqueue --context=resume --top 3` 改為 `ticket track dashboard --top 5`
  - AskUserQuestion 選項對齊 dashboard `[1] [2] [N]` 編號 + priority 標籤（用戶可直接說編號選擇）
  - in_progress 任務優先列出（label 加 `[ip]` 前綴），用戶選擇後走 `resume` 而非 `claim`
  - dashboard 無結果時 fallback 到原 `list --status pending in_progress` 路徑（向後相容）
  - `ticket resume --list` 與 `ticket track runqueue --context=resume` 子命令保留作除錯/腳本用途
  - 量測收益：baseline 7 tool call → dashboard-first 2-3 tool call（改善 57-71%）
- v2.6.0 (2026-05-13): 補 dashboard 命令與 list 預設行為文件
  - 子命令總覽表新增 `track dashboard` 與 `track list` 兩列
  - track 章節 READ 操作清單補 `dashboard` / `stale-list` / `td-status`，並註明 list `--top`/`--all` 預設行為
  - 新增 `Dashboard — dashboard` callout 說明聚合視圖、編號 claim、降低 7→3 tool call
  - 新增 `List 預設行為 — list --top / --all` callout 說明預設 top 10 排序與 `--format` 三選值
- v2.5.2 (2026-05-12): 子命令總覽表新增 `track td-status`；track 章節新增 td-status callout（PC-094 落地）
- v2.5.1 (2026-05-10): handoff 章節新增「設計原則」引用指向 `handoff-design-principle-methodology.md`
- v2.5.0 (2026-05-08): handoff 章節同步新增的 `--next` CLI 與 `target_ticket_id` 欄位
  - 新增 `--next <target-ticket-id>` 用法說明（絕對指向語意）
  - 註明與 `--auto` 互斥、direction 預設 `context-refresh`
  - 註明讀取端優先序：target_ticket_id > direction fallback（向後相容）
- v2.4.0 (2026-04-21): `/ticket` 裸指令入口切換為 scheduler 接手建議
  - 流程步驟 1 從 `ticket resume --list` 改為 `ticket track runqueue --context=resume --top 3`
  - AskUserQuestion 選項順序改反映 runqueue scheduler 排序
  - `ticket resume --list` 子命令保留，作為完整待恢復清單與除錯入口
- v2.3.0 (2026-03-11): `/ticket` 裸指令新增待辦任務檢查步驟
  - 流程調整為三層：(1) 檢查 handoff → (2) 檢查 pending/in_progress 待辦 → (3) 顯示子命令
  - 待辦任務以 AskUserQuestion 列出，含「建立新 Ticket」選項
- v2.2.0 (2026-03-02): `/ticket` 裸指令自動檢查 handoff 待恢復任務
  - 新增「無子命令時的預設行為」章節
  - `/ticket` → 檢查 pending handoff → AskUserQuestion 選擇 → resume
  - 搭配 handoff-prompt-reminder-hook v2.0.0 停用自動接手
- v2.1.0 (2026-03-02): 決策樹拆分為 5 個 workflow 檔案（Progressive Disclosure）
  - `decision-trees.md`（327 行）拆分為 5 個按工作流分組的檔案
  - 各子命令說明新增對應決策樹引用
  - 參考資料表更新為 5 個 workflow 檔案
- v2.0.0 (2026-02-10): SKILL.md 拆分為入口 + references
  - 從 1273 行精簡為 ~170 行入口文件
  - 9 個子命令/架構/決策樹/完整性驗證移至 references/ 目錄
  - 遵循官方 Supporting Files 模式（SKILL.md < 500 行）
  - 保留執行方式和命令總覽作為入口必讀資訊
- v1.9.0 (2026-02-06): 語意化重命名 commands_messages_a/b
- v1.8.0 (2026-02-06): 變更後文件一致性同步
- v1.7.0 (2026-02-06): 文件同步更新 - 新增 generate/board/audit 文件
