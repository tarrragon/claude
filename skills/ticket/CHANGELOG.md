# ticket 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 2.23.0
**Last Updated**: 2026-09-07
**Status**: Completed

**Change Log**:

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
