# Agent Dispatch Template（收尾政策）

> **用途**：派發 prompt 情境與政策詳解之一：收尾政策（持久化驗證、衝突裁決回票面、--as 全覆蓋、收尾義務標準段）。
>
> **同族檔**：`agent-dispatch-closeout.md`、`agent-dispatch-testing.md`、`agent-dispatch-worktree.md`、`agent-dispatch-pm-edit.md`、`agent-dispatch-variants.md`。原檔 `agent-dispatch-template.md` 保留檔頭與保留段落，並為各被移走段標保留路由，被移走段標在原檔以同名標題加一行路由保留，既有〈段標〉引用不需改寫。

---

## append-log 收尾持久化驗證

被派發 agent 在 prompt 收尾段須附此驗證準則，避免 malformed heredoc 使 `ticket track append-log` 未真正執行卻被誤判為「CLI bug」。

**Why/Consequence**：append-log 內容若以 heredoc 傳入而指令 malformed（delimiter 不符、未正確 pipe 到 `ticket`），shell 會把 heredoc 內容自己 echo 出來、ticket CLI 根本未執行，ticket md 無變更。agent 若把這段 shell echo 誤讀為 CLI 回應，會誤歸因為「append-log 失效」並放棄收尾章節（如 Exit Status），造成可觀測性資訊靜默遺失（實證：W1-008 ANA，subagent Exit Status 殘留 placeholder；PM 同 section 重現逐字持久化）。 <!-- rule8-exempt: relocation:自 .claude/references/agent-dispatch-template.md 逐字搬移 -->

**Action**（收尾自律）：

- 唯有 CLI 回 `[OK] 已追加日誌到 '<section>'` 才算寫入成功；輸出僅見 heredoc 內容被 echo 出來代表指令 malformed、CLI 未執行，須修正 Bash 指令重發。
- 收尾關鍵 section（Test Results / Exit Status）後以 `grep -c "<唯一片語>" <ticket-md-path>` 確認實際持久化（固定值驗證，不信 CLI 旁白）。
- 派發 prompt 要求被派發 agent 寫入含子章節（`###`）的 ticket body 時，須明示「多行內容以 scratchpad 內容檔加 --content-file 傳入，不得壓成單行」（PC-GPD-003 預防節主條文）。
- worktree 內多行內容被守衛拒收時，首選 Write 寫入 scratchpad 內容檔後以 `append-log --content-file <路徑>` 傳入；`--content-file` 不可用時才分次 append（每次一個章節或段落），不得把 Markdown 章節壓成單行：壓成單行後 `###` 不在行首，寫入看似成功，但 complete gate 判定必填章節缺失而擋下。
- 偵測是否已壓平：`grep -n '^### <本次寫入的子章節名>' <ticket-md-path>`（例：子章節為「自檢結果」時用 `grep -n '^### 自檢結果' <ticket-md-path>`）；ticket 內已有該章節內容卻無行首命中，即為壓平，須重新分次 append。無此子章節的票不會命中，不可據此判定未壓平。
- 引用既有規則不重複定義：heredoc 傳長文字見 `bash-tool-usage-rules` 規則 5；「只信 raw stdout、帶旁白視為自身雜訊」見 `tool-output-trust-rules` 規則 2；CLI args 跳脫見 PC-079。

---

## 衝突裁決回票面（PM 端）

**衝突裁決以 append-log 寫回票面，票面記錄優先於原 prompt 指示（原 prompt 可能因客製或誤寫而與正本不一致）——不得只存在於重發 prompt 或對話，prompt 不進交接鏈，下個執行者只看得到票面。**（agent 何時觸發此流程見「骨架（權威版）」段停手上報規則）

**Action**：PM 收到 agent 於 ticket NeedsContext 章節寫入的衝突上報後，執行：

```
ticket track append-log {ticket_id} --section "<section>" "<裁決內容>"
```

裁決紀錄最小欄位：

| 欄位 | 內容 |
|------|------|
| 衝突項 | prompt 位置 / ticket 正本位置 / 框架正本檔案路徑，具體指出三者中實際衝突的兩者 |
| 判定 | 採信何者為準（prompt 修正 / ticket 正本修正 / 框架正本修正） |
| 後續 | 後續派發 prompt 是否需同步修正，需修正則指出修正內容 |

`<section>` 依 ticket type 而定：優先寫入 `Solution`（ANA 必填、IMP 選填）；DOC 型 `Solution` 免填，改寫入 `Completion Info`。完整必填/選填/免填對照見 `.claude/pm-rules/ticket-body-schema.md`「Schema 對照表」。

---

<!-- rule8-exempt: relocation:自 .claude/references/agent-dispatch-template.md 逐字搬移 -->
## 收尾 --as 全覆蓋與建票 who 對齊（W1-049 裁決前置）

**核心原則**：派發 prompt 的收尾指引必須教 agent 對 `check-acceptance` / `set-acceptance` / `complete` 三命令**一律帶 `--as <自身 agent 名稱>`**；PM 建票（尤其子票）必須以 `--who` 設定預期執行代理人。

**Why**：identity-guard telemetry 首輪 13 筆樣本（W1-049）顯示兩個資料品質缺口——92% warn 噪音來自 check-acceptance 未帶 --as（SOP 過去只教 complete）；唯一 deny 是 false positive（子票 who.current 繼承 parent 而非實際執行者，誠實申報的 agent 被誤擋後學會拿掉 --as 繞過）。 <!-- rule8-exempt: relocation:自 .claude/references/agent-dispatch-template.md 逐字搬移 -->

**Consequence**：兩缺口不補，warn-only 轉強制的評估資料永遠失真，且誤傷會訓練 agent 繞過申報（與防護目標反向）。

**Action**：

| 角色 | 義務 |
|------|------|
| PM 建票 | `ticket create --parent <id>` 建子票時必帶 `--who <預期執行代理人>`（子票預設繼承 parent who，是誤傷源）；派發前發現 who.current 與將派發的 agent 不符時先 `set-who` 對齊 |
| PM 寫 prompt | 收尾步驟範本三命令均含 `--as <agent-name>`（prompt 骨架見 `agent-dispatch-template.md`「骨架（權威版）」，收尾段直接套用同檔「與 /goal 的邊界」章節的範例命令） |
| Agent | 依 AGENT_PRELOAD 規則 2.4「--as 全覆蓋」執行；--as 被 deny 時禁拿掉 --as 繞過，回報 PM 裁決 |

---

<!-- rule8-exempt: relocation:自 .claude/references/agent-dispatch-template.md 逐字搬移 -->
## 收尾義務標準段（W2-003）

> **用途**：派發 prompt 收尾段的標準模板，把「勾選 acceptance」與「填寫 ticket body」兩項收尾義務明文寫入指令，取代僅靠代理人自律（AGENT_PRELOAD 規則 2.4）記得執行。
>
> **設計依據**：代理人在回覆文字中勾選 acceptance 項目，但未實際執行 `ticket track set-acceptance` 寫入 frontmatter，導致 complete 被二度擋下的摩擦；PM 改在 prompt 明示指令後已有效收斂。
>
> **範圍擴充（0.4.1-W2-008）**：W17-064 的「Solution 缺 `### 自檢結果`」warning 對 PM 於 complete 時發出，0.4.0 十八票 + 0.4.1-W1-001 皆被忽略——受眾與時點雙錯，warning 送到 PM 手上時代理人工作已結束，PM 補寫是事後貼標籤，不是自檢本身。W2-008 決策：正確供給側是代理人執行期的 template 義務，故本標準段一併納入「### 4. Solution 自檢結果子章節義務」。 <!-- rule8-exempt: relocation:自 .claude/references/agent-dispatch-template.md 逐字搬移 -->

**Why**：agent 的最終回覆文字（final message）屬記錄平面，與 ticket frontmatter 的世界平面語意不對稱（見 `tool-output-trust-rules` 規則 5）。回覆裡寫「acceptance 已勾選」不代表 frontmatter 真的被改，acceptance-gate-hook 只讀 frontmatter，兩者不同步時 complete 必被擋；同理，自檢的產出者是執行期的代理人，事後對 PM 的 warning 無法讓已完成的工作補回自檢過程，只能在派發時把自檢寫入代理人的收尾動作才有效。

**Consequence**：prompt 若只寫「完成後 complete」，代理人容易把「口頭確認完成」當作收尾終點，遺漏實際 CLI 呼叫；PM 需二次回頭補派同一 ticket 才能收斂，浪費一個派發回合。同理，若收尾段不明示自檢子章節義務，`### 自檢結果` warning 會持續在 complete 時對 PM 發出且被忽略（實證忽略率：18/18 + 本 ticket 前身），acceptance 與證據的對應關係也無從追溯。

**Action**：收尾段固定納入以下五塊，不可只留其一：

### 1. set-acceptance 指令範例

依驗收項目是否逐項確認分兩型：

```bash
# 型一：一次勾選全部（agent 已逐項自我確認完成）
ticket track set-acceptance <ticket-id> --all-check --as <自身 agent 名稱>

# 型二：僅勾選特定 index（部分驗收項尚未達成，只勾已完成者）
ticket track set-acceptance <ticket-id> --check 1 2 --as <自身 agent 名稱>
```

型一與型二互斥，依 acceptance 實際完成狀況擇一；未完成的 acceptance 項一律不勾，並在 NeedsContext 記錄缺口（見 AGENT_PRELOAD 規則 2.4 例外情境表）。

### 2. ticket body 填寫義務

`set-acceptance` 只更新 frontmatter 勾選狀態，不等於 body 章節已填寫完整。收尾段須同時要求：

| 章節 | 填寫內容 |
|------|---------|
| Solution | 實際變更摘要（新增/修改的方法、檔案） |
| Test Results | 測試執行結果（通過數/總數，或 DOC 類型免填時明示原因） |
| Exit Status | W17-010 schema（status/reason/confidence/acceptance_met 等） | <!-- rule8-exempt: relocation:自 .claude/references/agent-dispatch-template.md 逐字搬移 -->

### 3. 建票血緣回填義務

**Why**：執行中發現需建票的議題時，若以裸 `ticket create` 只標 `--related-to` 建票，`relatedTo` 是弱關聯 metadata（不維護雙向欄位，語意見 `.claude/skills/ticket/references/field-semantics.md`），衍生血緣（`source_ticket` / `spawned_tickets`）會留空——同型缺漏短期內重複發生，PM 驗收時須逐票手動補齊。

**Consequence**：血緣缺漏使 `ticket tree` / `chain` 等血緣視覺化指令無法呈現真實衍生關係，「這個 ticket 是哪個 ticket 執行中發現的」須回頭翻工作日誌或對話記錄才能重建，逐票補齊亦累積成 PM 的額外驗收負擔。

**Action**：收尾段須明示代理人依下表二擇一，禁止裸 `create` 只標 `--related-to`：

| 通道 | 使用時機 | 指令 |
|------|---------|------|
| `--source-ticket` | 已確定要建票，且內容足以直接成票（例外：ANA 結論要求的落地改用 `--parent`，PC-091） | `ticket create --source-ticket <自身 ticket id> --action <動詞> --target <對象> --type <IMP\|ADJ\|ANA\|DOC> --why <依據>` |
| `add-spawn-request` | 發現議題但尚未確定是否成票、或範疇 / 優先級需 PM 裁決 | `ticket track add-spawn-request <自身 ticket id> --what ... --why ... --type ... --priority ...` |

兩通道皆由 CLI 自動回填血緣欄位：`create --source-ticket` 在建立當下即回填 `source_ticket` / `spawned_tickets` 雙向欄位；`add-spawn-request` 於 PM 執行 `resolve-spawn-request <id> SR-N --status processed --spawned-ticket <ticket-id>` 時回填。`--related-to` 不具備此機制，僅供無血緣意圖的弱關聯引用（見 field-semantics.md「用戶情境對照表」）。欄位定義以 `.claude/skills/ticket/references/field-semantics.md` 為唯一權威來源，本節不重複定義。

<!-- rule8-exempt: relocation:自 .claude/references/agent-dispatch-template.md 逐字搬移 -->
### 4. Solution 自檢結果子章節義務（W2-008）

收尾段須明示：`complete` 前，Solution 章節必須含 `### 自檢結果` 子章節，依 `.claude/references/agent-self-check-template.md` 執行，且**對照 acceptance 逐項附證據**（非泛稱「已自檢」）。

```markdown
complete 前，Solution 章節須補 `### 自檢結果` 子章節：依
.claude/references/agent-self-check-template.md 執行 Layer 1 自檢
（A 文字品質 / B 禁用字 / C Schema 結構），並對照本 ticket 每項
acceptance 逐一附證據（如「acceptance N：已於 X 檔案 Y 行落實，見 Z」）。
```

| 適用 | 說明 |
|------|------|
| IMP / ANA ticket | 強制 |
| DOC ticket | 沿用 `agent-self-check-template.md`「自檢無發現可省略子章節」的免填規則，但仍需執行掃描 |
| 純機械任務（格式修正、路徑替換） | 可省略（同 Layer 1 自檢觸發指引既有豁免條件） |

> **與既有「Layer 1 自檢觸發指引」章節的差異**：該章節是通用的文字品質/禁用字/Schema 掃描指令；本項額外要求自檢結果**逐一對照 acceptance 編號**，讓 PM 與 acceptance-gate-hook 可直接核對「每項 acceptance 有無對應證據」，而非僅有一段籠統的自檢摘要。

> **元件票／畫面票的票型專屬必含項**：見 `.claude/skills/component-contract-design/references/step-5-write-tickets.md`〈派發語言：四種票〉的「派發 prompt 必含」列與〈派發 prompt 的三項固定句〉節——內容即本節的自檢結果子章節義務套用到元件契約欄位表投影／import 邊界斷言的具體對照，不重複展開。

### 5. 明示：回覆勾選不算數，frontmatter 才是 SOT

收尾段結尾固定附加一句提醒，防止代理人以為「在回覆文字描述完成」等同「已收尾」：

```markdown
最終回覆中描述「已完成」不等於收尾完成；只有 set-acceptance 指令
真正寫入 frontmatter、body 章節確實填寫，acceptance-gate-hook 驗證通過
後才算收尾完整。
```

### 適用範圍

| 情境 | 是否插入本標準段 |
|------|----------------|
| IMP / DOC / ANA 等需 complete 的實作類派發 | 強制 |
| 唯讀探針、純諮詢派發（無 ticket 寫入義務） | 不適用（見「唯讀探針派發 SOP」章節） |
| 嵌套派發 child prompt | 適用，套用「嵌套派發（descend）派發端指引」的 child prompt 骨架收尾段 |

---
