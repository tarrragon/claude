# Ticket 收束配方

把一群本地 ticket 的分析與方案 context 壓成 framework issue 的當前結論，然後關掉這些 ticket。目的是讓 ticket 池回到「本專案這一階段要做什麼」的執行紀錄，而問題知識住在跨 consumer 可見的地方。

- [前提與分工](#前提與分工)
- [步驟一：分群](#步驟一分群)
- [步驟二：查重與落點](#步驟二查重與落點)
- [步驟三：時序改狀態](#步驟三時序改狀態)
- [步驟四：區段範本](#步驟四區段範本)
- [步驟五：ticket 處置](#步驟五ticket-處置)
- [步驟六：驗證與交接](#步驟六驗證與交接)
- [派發 curator](#派發-curator)

## 前提與分工

**為什麼要做**：ticket 池單調增長而增長不對應框架品質提升。三種已實證的失效形態：已解決而後續票不知情（答案票與提問票在同一池共存 16 天）、同一根因散為三張票（三個來源在不同時間各自建立）、防護只擋一種情境（風險被預見過，防的是另一條軸）。三者共同根因是分析 context 記在單一 consumer 的 ticket，跨專案不可見。

**收束的產物是狀態，不是搬運**。ticket 的 Problem Analysis 是時序累積（每輪發現寫一段，後段修正前段），issue 區段是狀態呈現（只含現在成立的）。兩者無機械對應，逐段判斷不能自動化。第一個外部 consumer 實測：一張 453 行、六輪累積的分析票，整理成四則區段的成本約為重寫的七成，省下的是材料蒐集。這是協定的直接後果：要讓後來的讀者先看到結論，就得有人把時序整理成狀態，差別只在作者做一次或每位讀者各做一次。

**分工先於動手**。並行 session 常各自對同一主題收束。開始前：

1. `ListAgents` 列出同機器活躍 session，對每一位發訊問三件事：在改哪些檔案、claim 了哪些票、在框架 repo 開或更新了哪些 issue。
2. 對方認領的主題，本方只加 `observe`，不 init、不 close 對方列出的票。
3. 對方尚未回覆的主題，先做分工無爭議的主題；訊息視為可能不返回，不循序等待。

## 步驟一：分群

以主題為單位，主題來源是 ticket 系統的主題中央清單（每張票建立時指派）。一主題一 issue；主題內票數超過 30 或明顯含兩個不同層級（體系層對單一工具層）時切成子領域，每子領域一 issue，雙方 body 互標。

分群輸出是一張表，之後每步都用它：

| 主題 | 票數 | ANA／IMP／DOC | 候選落點（既有 issue 或新開） | 認領者 |
|------|------|--------------|------------------------------|-------|

同主題內以 `blockedBy` 互鎖的票要列出：被鎖的票在鎖它的票 close 後即失去前提，兩張一起收束，不留單邊。

## 步驟二：查重與落點

對每個主題跑 `dedup`，關鍵字用單詞（含空白的組會被拆詞聯集，但雜訊隨之增加，一開始就給單詞可控制範圍）：

```bash
python3 .claude/skills/framework-issue/scripts/section_comment.py dedup \
  --keywords "hook" "fail-open" "exit" "靜默"
```

命中清單逐一判關係（重複／切分／引用，判準見 `references/comment-as-section-protocol.md` 的〈init 前查重：三種關係處置〉），落點四選一：

| 命中狀況 | 落點 | 動作 |
|---------|------|------|
| 主題已有 open issue、無區段、body 無任何索引表（舊 body-only issue） | 該 issue | `init`（對既有 issue 可執行，追加區段並回填索引；body 缺 `fw-issue-schema` 標記時同一次 PATCH 內自動補上首行，不需再手動 `gh issue edit`） |
| 主題已有 open issue 且已被他方 `init` | 該 issue | `add --owner <本方識別>` 建本方擁有的區段（每個區段一次 `add`），既有索引列不受影響；不 `init`（會覆寫工具建立的索引） |
| 主題已有 open issue，body 有手寫索引表（無工具標記） | 該 issue | `observe` 附加；`init`／`add` 都會多出第二張索引表，不用 |
| 命中的是同領域不同層級 | 新 issue | `create` 後 `init`，分工邊界寫入雙方各自「當前結論」末段 |
| 無命中 | 新 issue | `create` 後 `init` |

**主題已有 open issue 一律附加、不新開**。既有 open issue 已覆蓋多數框架主題，新開等於製造「同領域第二張」，正是 `check` 抓不到的失效。

## 步驟三：時序改狀態

讀完主題內全部票（含 Problem Analysis、Solution、NeedsContext），對每一段問：**這是現在成立的結論，還是通往結論的過程？**

| 段落性質 | 判別訊號 | 處置 |
|---------|---------|------|
| 現在成立的結論 | 後續段落未修正它；或它是最後一次修正的版本 | 進「當前結論」 |
| 通往結論的過程 | 實驗記錄、候選方案比較、量測數字 | 濃縮進「問題清單與根因」或「方案評估」，保留數字與量測條件 |
| 被推翻的中間版本 | 後段寫「實測為 X，已更正」「原判 A 不成立」 | 刪除，只留一句撤回記錄：「原判 A（票 ID），經 B 推翻」 |
| 尚未執行的實作內容 | IMP 票的 what／how／acceptance | 進「待調整清單」，一張票一列 |
| 對其他 consumer 無意義的本地細節 | 本專案專屬路徑、本地環境數字 | 不進 issue；若為實測記錄保留原值並標註量測環境 |

同一段常兩者都有（先陳述舊判斷再說明為何錯），切點在段落中間。切完後讀一次「當前結論」，問：**一個沒讀過任何來源票的人，只讀這一段，知道現在該相信什麼嗎？** 不知道就是還留著過程。

**不做的事**：不把票的 Problem Analysis 原樣貼進區段。貼入時序敘事會把「先看到結論」這個協定唯一的讀者收益還回去。

## 步驟四：區段範本

區段數由內容決定，不寫空殼：「當前結論」必有，其餘只在有內容時建立。空區段會稀釋 comment 流並拉高 comment 數警訊，且給讀者一則沒有資訊的入口。

| 區段 | 內容 | 何時建 |
|------|------|-------|
| 當前結論（讀者入口） | 現在成立的判斷，含已修正的高估與撤回記錄；與切分 issue 的分工邊界寫在末段；最後一行寫狀態（協定已定／工具已建／待接線） | 一律 |
| 問題與方案 | 每個徵狀一列（徵狀、根因、實證來源）；候選方案、選定理由、已知代價、未驗證假設。票數 ≥ 5 且兩者都長時可拆為「問題清單與根因」「方案評估」兩則 | 主題有徵狀或方案取捨時 |
| 待辦與來源（本 consumer） | IMP 票的執行內容一張一列：來源票、做什麼、acceptance 條數、優先級、階段（本版／下版／待條件）、狀態；末尾一行指回本 consumer 的派發票 ID（完整來源票對照住在那裡，其他 consumer 讀不到本地票，不在 issue 重抄） | 主題有 IMP 票時 |

sections.json 骨架：

```json
[
  {"name": "當前結論", "content": "## 當前結論\n\n（狀態呈現，不含被推翻的版本）\n\n**狀態**：..."},
  {"name": "問題與方案", "content": "## 問題與方案\n\n| 徵狀 | 根因 | 實證 |\n|------|------|------|\n...\n\n### 方案\n\n..."},
  {"name": "待辦與來源（flutter-balance）", "content": "## 待辦與來源（flutter-balance）\n\n| 來源票 | 做什麼 | acceptance 條數 | 優先級 | 階段 | 狀態 |\n|--------|--------|----------------|--------|------|------|\n...\n\n來源票對照：本 consumer 派發票 <ticket-id> 的 Solution。"}
]
```

區段名須與索引表逐字一致；「當前結論」必須是第一則，`check` 的主警訊只以此名稱定位，少其他區段不影響工具。

**以 `add` 加進他方已 init 的 issue 時**，區段名加後綴 `（<consumer>：<主題>）`，如「當前結論（flutter-balance：規則 8 引用清理與執法）」，避免與既有「當前結論」同名時字串相等定位落在兩者之間不確定。`check` 的主警訊已改採前綴比對（名稱以「當前結論」開頭者皆涵蓋），後綴區段與既有「當前結論」各自獨立輸出並標明 owner，不再缺主警訊涵蓋；分工邊界仍寫入本方「當前結論（…）」末段，既有 owner 的區段以 `observe` 提醒。

## 步驟五：ticket 處置

close 宣告的是「這張票的知識已有更好的住址」，問題本身是否解決由 issue 的當前結論說。先定範圍，再執行：

| 票的狀態 | 處置 |
|---------|------|
| ANA／DOC，pending | close |
| IMP，pending | close；執行內容進「待辦與來源」 |
| 被範圍票以 `blockedBy` 依賴、且不在範圍內的票 | 不動該票，但以 `set-why` 在其 `why` 末尾補一句 issue ref，讓接手者知道前置知識的住址。runqueue 與派發就緒判定把 closed 視為已解除（`is_fully_unblocked` 以 `include_closed_as_resolved=True` 呼叫），依賴方不會因此卡住；只有 complete 後的「已解鎖建議清單」不列它們，不影響可執行性 |
| in_progress、已 claim、同儕明示保留 | 不動 |
| 父票有 children | children 先處理，父票最後 |

```bash
ticket track close <ticket-id> \
  --resolved-by none \
  --reason not_executable_knowledge_captured \
  --reason-note "分析 context 已遷至 tarrragon/claude#<N>（區段：當前結論）"
```

| 約束 | 說明 |
|------|------|
| `--resolved-by` 只收 ticket ID 或 `none` | issue ref 不是合法值。本 reason 對 resolved-by 與 reason-note 皆不驗證（留空也過），本配方仍要求 note 必含 issue ref，否則 close 後無人能從票面找到知識住址；`version-tracking-consistency-guard-hook.py` 接受 `none` |
| reason-note 禁詞（本節為權威，他處只引用） | 「延後」「移到」「後續」三詞以子字串比對，命中即被拒。「後續」最易在自由填寫「（區段：…）」時寫出；升級流程的路徑名「延後接手」也不可抄進 note；寫「遷至」「已收進」 |
| reason 語意 | `not_executable_knowledge_captured` 原註解指知識轉移至 error-pattern；本配方把落點延伸至 framework issue，以 reason-note 的 issue ref 區分 |

IMP 票被 close 後，執行內容住在「待辦與來源」；之後依階段性設計裁實作票時，以 `ticket track query <closed-id>` 取回原票的 acceptance 與 `where.files`，不重寫；新票 `--source-ticket` 指向收束時的派發票，`why` 引用 issue ref 與區段。

## 步驟六：驗證與交接

1. `show <issue-ref>`：建立的區段全部在索引內、「當前結論」第一則。
2. `check <issue-ref>`：三項警訊皆未命中（剛 init 的 issue 索引一致、無觀測落後）。
3. 本地擁有登記檔 `.claude/state/framework-issue-owned.json` 含此 issue（區段建立成功即寫入）；缺失時 SessionStart 檢查會退回前綴推導。
4. 來源票對照（票 ID、型別、標題、處置、落點區段）以 `ticket track append-log <派發票> --section "Test Results"` 寫入派發票——它是「每張票已依範圍規則處置」的驗證證據；**不寫進 Solution**：acceptance gate 的 spawn 落地檢查把 Solution 內帶型別欄的票表判為 spawn 規劃並擋 complete（實測一個 curator 被擋，補 16 列豁免宣告才過）。查重關係判定表與分群「實際落點」欄仍寫 Solution。同機器並行 session 各發一份對照表。
5. 對他方認領主題本方只做了 `observe` 的，觀測內容第一行寫「來自 <session>，對照表在 <派發票 ID>」（首行標記由工具寫入，不重複）。

## 派發 curator

一個主題一個 `framework-issue-curator`（opus、effort medium），並行派發。派發前 context 寫進派發票，不塞 prompt；prompt 本體 30 行內：

```
任務：把主題「<主題名>」的 <N> 張 pending 票收束為 tarrragon/claude#<M> 的區段（或新 issue）。
範圍票：<ID 清單>（只對這些票 close，其他票不動）。
落點：<既有 issue 編號 / 新開，關係判定結果>。
owner 識別：<專案 kebab>-<session 序號>。
步驟：讀票 → 依 references/ticket-intake.md〈步驟三：時序改狀態〉改寫 → sections.json 寫 scratchpad → init／add／observe（依〈步驟二：查重與落點〉）→ 依〈步驟五：ticket 處置〉範圍規則 close → show/check → 來源票對照以 append-log 寫回派發票 Test Results、關係判定寫 Solution。
禁止：貼入時序敘事、對已有索引的 issue 再 init、close 範圍外或被依賴的票、更新他方 owner 的區段、寫專案內任何檔案、對 ticket md 裸 commit（`git commit` 讀共用 index，會把並行 session 暫存的檔案一併帶走，實測三個 curator 兩個命中）。
提交：`append-log` 逐命令 auto-commit；`close` 不會——它只由 Stop 事件的兜底 hook 提交，而該 hook 在有背景代理人時跳過。範圍票全部 close 後，由 curator 以隔離索引 CAS 提交這批 ticket md（配方見 Bash 工具使用規則參考文件的〈規則七詳細〉隔離索引 CAS：`GIT_INDEX_FILE` 指臨時 index → `read-tree HEAD` → `add` 精確檔案 → `write-tree` → `commit-tree` → `diff --name-only` 自驗範圍 → `update-ref HEAD <new> <old>`）。**提交後對同一批檔執行 `git restore --staged -- <檔…>`**：`ticket track complete` 預設會把票檔 stage 進共用 index，CAS 提交不經共用 index，舊 entry 會留下成為「過期快照」，他人任一次裸 commit 都會把這批票回滾且 `git log` 外觀正常；三平面（index／HEAD／工作區）一致後才算收尾。規範在執行期間可能被更新（本次收束中兩份規範各改了三次），收尾前重讀 `references/ticket-intake.md` 與代理人定義，以當下版本核對 acceptance。
scratchpad 檔名帶派發票 ID（如 sections-<ticket-id>.json）：scratchpad 由同 session 全部代理人共用，同名檔會被並行 curator 覆寫。
驗收：show 顯示「當前結論」為第一則且全部區段在索引內、check 三項未命中、範圍票依範圍規則處置完畢且 reason-note 含 issue ref、git status 無專案檔變更。
```

curator 回報後 PM 只做兩件事：讀「當前結論」判斷是否能作為下一階段裁票依據；抽一張來源票比對「來源票對照」的處置是否與票面一致。
