# Ticket 欄位語意對照（六欄位 SSOT）

本文件為 ticket frontmatter 中六個血緣/依賴/關聯欄位的權威語意定義。其他規則、方法論、error-pattern、SKILL 文件涉及這些欄位時應引用本檔，不重複定義。

> **何時讀**：設定或釐清 `parent_id`/`children`/`source_ticket`/`spawned_tickets`/`blockedBy`/`relatedTo` 六欄位語意、判斷阻擋情境、決定該填哪個血緣欄位時；或需查 `where.files`（`::read`/`::write` 後綴、type 預設意圖、目錄型宣告展開與阻擋）的完整語意時（見〈where.files 宣告語意〉節，該欄位非血緣/依賴/關聯欄位，因七處分散對照收斂於此，不計入六欄位範疇）。**亦由此進入**：`create-command.md`〈--source-ticket 參數（衍生關係）〉節（欄位選擇決策樹指標）、`track-command.md`〈UPDATE 操作補充：commit 副作用與欄位語意〉### 六欄位語意 SSOT（六欄位權威定義指標）、`ticket_system/lib/depth.py` 原始碼註解（world-plane SSOT 指標）。
>
> **同目錄**：`create-command.md`（`--parent` vs `--source-ticket` 建立時的 CLI 副作用）、`track-command.md`（`set-blocked-by` / `set-related-to` 操作說明）。
>
> **溯源**：本檔於本專案匯入 commit `f375ae675` 時即已存在；此後累積增修（如 relatedTo 方向性裁決、context bundle 作為 relatedTo 合法消費端的承認），未見單次外移原始拆分點（可用 `git log --oneline -- references/field-semantics.md` 查證）。初版（1.0.0）提煉自 0.18.0-W17-120 ANA 多視角審查共識（linux + saffron-system-analyst + basil-hook-architect）→ W17-120.1（DOC）建立本 SSOT，PC-091 路線（ANA 落地用 children）取代 PC-073；後續版本歷史見 `CHANGELOG.md`。

本檔章節：〈適用範圍〉〈六欄位定義〉〈阻擋語意對照表〉〈用戶情境對照表〉〈欄位選擇決策樹〉〈反模式速查〉〈相關文件〉。

---

## 適用範圍

本檔涵蓋 **六個血緣/依賴/關聯欄位**：

| 類別 | 欄位 | 雙向欄位 |
|------|------|---------|
| 血緣 | `parent_id` ↔ `children` | 是（CLI 自動維護） |
| 衍生 | `source_ticket` ↔ `spawned_tickets` | 是（CLI 自動維護） |
| 阻擋 | `blockedBy` | 否（單向） |
| 關聯 | `relatedTo` | 否（單向） |

**不涵蓋**：

| 欄位 | 角色 | 應另查 |
|------|------|------|
| `dispatch_reason` | 派發原因記錄（決策溯源） | 本檔不討論；參考 `agent-dispatch-template.md` |
| `decision_tree_path` | 決策樹路徑記錄（決策溯源） | 本檔不討論；參考 `pm-rules/decision-tree.md` |
| `chain` | 任務鏈聚合視圖（衍生欄位） | 本檔不討論；參考 `atomic-ticket-methodology.md`「子任務建立指引」 |
| `where.files` | 派發/提交/衝突判定用的檔案宣告（非血緣/依賴/關聯） | 本檔另闢〈where.files 宣告語意〉小節收斂七處分散對照（見下） |

> **判別準則**：本檔聚焦「ticket 之間的關係欄位」（影響阻擋/排程/驗收 hook 行為）；決策溯源欄位（記錄為何建立此 ticket）不在本檔範圍。`where.files` 亦非關係欄位，因七處消費端各執一角而無完整住址，例外收斂於本節（非六欄位定義的一部分，故獨立為本節子標題，不計入下方六欄位）。

### where.files 宣告語意

> **唯一住址**：`where.files` 的後綴標記、type 預設意圖、目錄型宣告展開與阻擋規則此前只存在於原始碼 docstring（`ticket_system/lib/file_conflict.py`），文件層七處消費端各自僅描述單一命令情境下的局部行為，無一處完整。本節統整完整規則作唯一住址，七處消費端維持各自的情境角度不變，僅追加指回本節。

**後綴標記語意（`::read` / `::write`）**：`where.files` 逐檔路徑可在結尾附加 `::read` 或 `::write` 覆寫該檔的讀寫意圖；未附加標記時套用 type 預設意圖（見下表）。標記僅辨識**字串結尾**且**未被反斜線跳脫**的形式；路徑本身需要以 `::read`／`::write` 字面結尾時，票面寫 `\::read`／`\::write`（反斜線 + 標記）跳脫，還原為字面路徑並套用預設意圖。無法辨識的後綴（如 `::readonly`）一律視為路徑本身的一部分，不當作標記剝離——fail-safe 方向為寧可誤留路徑片段，不可誤丟。

**type 預設意圖**：

| type | 預設意圖 | 理由 |
|------|---------|------|
| `ANA` | `read` | ANA 型票的產出是分析報告，非程式碼變更 |
| 其餘（`IMP`／`DOC`／`ADJ`／無 type） | `write` | 無 type 或非 ANA 一律預設 `write`（保守）：判為 `write` 誤攔的代價僅犧牲一點並行效率（false positive）；判為 `read` 漏放的代價是真實寫入衝突未被攔下（false negative，可能資料遺失或互相覆寫）。兩者代價不對稱，不可為求並行效率改判成 `read` |

**目錄型宣告：展開、WARNING、dispatch 硬擋**（判定依據 PC-BAL-040：路徑結尾為 `/`，或指向 repo 內既有目錄，即為目錄型宣告）：

| 時機 | 行為 | 理由 |
|------|------|------|
| `create` / `set-where` 建立或修改階段 | 僅發 WARNING，不阻擋 | 建票當下實際變更檔案未必可知 |
| `track dispatch` 派發階段 | 對**無 `::read` 標記**的目錄型寫入宣告拒絕輸出骨架（`[BLOCKED]`，列出受影響的同目錄活躍票） | dispatch 是派發鏈最晚且 PM 在場的攔截點，此時具體路徑已知，應硬擋而非僅警告 |
| `track commit` 提交階段 | 展開為該目錄下實際變更（`git status --porcelain`）的具體檔案再提交 | 目錄本身非可提交單位，須先落實為檔案集合 |

目錄型宣告若帶 `::read` 標記，視為刻意唯讀範圍聲明，不觸發 dispatch 硬擋（建立階段的 WARNING 仍照發，因該階段不分讀寫一律提示）。

**七處消費端速查**（各消費端僅描述該命令情境下的局部角度，完整規則以本節為準）：

| 消費端 | 使用角度 |
|--------|---------|
| `track-command.md`〈track commit 子命令〉files 子集規則 | 提交檔案須落在寫入子集內；目錄型宣告於提交時展開為實際變更檔案 |
| `track-command.md`〈track dispatch 子命令〉設計約束 | 目錄型寫入宣告未帶 `::read` 時硬擋，拒絕輸出骨架 |
| `track-command.md`〈track runqueue〉`--groups` 安全性條件 2 | ANA 預設 `read` 不建衝突邊（約 19.3%／57 個 ANA 宣告樣本中 11 個為假陰性，已知取捨，非本次修復範圍） |
| `track-command.md`〈track conflicts 子命令〉判定規則第 4 項 | 與 pm-registry 交叉比對時僅採 `write` 集合 |
| `track-command.md`〈track onboard 子命令〉髒檔歸屬設計 | 髒檔命中依最長匹配前綴特異度歸屬；泛目錄宣告（路徑段數 <= 2）無鑑別力 |
| `track-command.md`〈track dispatch-readiness 子命令〉閾值 2／檢查 5／6 | 修改檔案數計數、路徑存在性、acceptance 路徑涵蓋性三項啟發式皆讀 `where.files` |
| `create-command.md`〈多值參數格式〉`--where` | `--where` CLI 參數僅支援逗號分隔多值語法；後綴標記語法不在 CLI 建立階段輸入範圍內，須另以 frontmatter 直接編輯或 `set-where` 系操作附加 |

原始碼權威：`ticket_system/lib/file_conflict.py`（`parse_file_intent` / `_default_intent` / `is_directory_declaration`）、`ticket_system/commands/track_dispatch.py`（`_directory_declaration_block_message`）。

---

## 六欄位定義

### parent_id（單值，string）

**語意**：直系父任務（血緣關係）。

| 屬性 | 值 |
|------|---|
| 雙向欄位 | `parent.children[]`（CLI 自動維護） |
| 阻擋語意 | 父 ticket 被未完成 children 阻擋 complete |
| Runqueue 影響 | 子 ticket 受 blockedBy 機制間接影響（本欄位本身不直接過濾） |
| 序號規則 | 自動子序號（如 `W17-001.1`） |
| CLI 寫入 | `--parent <PARENT-ID>` |
| CLI 互斥 | 與 `--source-ticket` 互斥 |

### children（陣列，array of IDs）

**語意**：`parent_id` 的反向欄位，所有以本 ticket 為 parent 的子任務 ID 清單。

| 屬性 | 值 |
|------|---|
| 維護方式 | CLI 自動維護（建立子 ticket 時自動追加） |
| 阻擋語意 | 父端被阻：父 complete 須等所有 children 進入 terminal 狀態（completed/closed） |
| 業務語意 | 「必須一起交付完整功能」 |

### source_ticket（單值，string）

**語意**：衍生來源（非血緣）。本 ticket 因哪個來源 ticket 的執行而衍生。

| 屬性 | 值 |
|------|---|
| 雙向欄位 | `source.spawned_tickets[]`（CLI 自動維護） |
| 阻擋語意 | 視 source ticket type 而定（見「阻擋語意對照表」） |
| Runqueue 影響 | 無 |
| 序號規則 | 獨立 ID（不繼承序號） |
| CLI 寫入 | `--source-ticket <SOURCE-ID>` |
| CLI 互斥 | 與 `--parent` 互斥 |

### spawned_tickets（陣列，array of IDs）

**語意**：`source_ticket` 的反向欄位，本 ticket 衍生出的後續 ticket ID 清單。

| 屬性 | 值 |
|------|---|
| 維護方式 | CLI 自動維護（建立衍生 ticket 時自動追加） |
| 阻擋語意 | 視本 ticket type 而定（見「阻擋語意對照表」） |
| 業務語意 | 「衍生副產品，獨立排程」 |

### blockedBy（陣列，array of IDs）

**語意**：阻擋依賴（單向時序）。本 ticket 必須等清單內的 ticket 全部進入 terminal 狀態才能執行。

| 屬性 | 值 |
|------|---|
| 雙向欄位 | 無（純單向） |
| 阻擋語意 | 不阻擋 complete；影響 runqueue 排程過濾 |
| Runqueue 影響 | `blockedBy` 非空 → 不在 runqueue 列表 |
| CLI 寫入 | `--blocked-by`、`set-blocked-by --add/--remove` |

> **When 散文與 blockedBy 的邊界（零機制慣例，W5-005 F4/D5 量測定案）**：When 是給人讀的時機敘事，提及 ticket ID 不構成依賴宣告；任何工具（warn / auto-populate / runqueue）不得從 When 散文推斷依賴。
>
> **Action**：(1) 真依賴（需等 X 進 terminal）於建立時顯性 `--blocked-by`，禁只寫進 When 散文；(2) 出處敘事用 `--source-ticket`、弱關聯用 `--related-to`；(3) 接手 ticket 時發現 When 語意前提未被 blockedBy 編碼，人工 `set-blocked-by` 補齊（blockedBy 滿足不等於 When 意圖滿足）。
>
> 依據：W5-005 量測（2285 票語料，精準度上限 25%），見 `CHANGELOG.md`。

### relatedTo（陣列，array of IDs）

**語意**：相關引用（弱關聯 metadata）。語意對稱、資料單向——A 與 B 互為關聯是雙向事實，但欄位只在單側寫入（不對稱起源見檔尾〈設計沿革〉）。

| 屬性 | 值 |
|------|---|
| 雙向欄位 | 無（儲存純單向；消費端須做 1-hop symmetric union，見下方「消費端讀取規則」） |
| 阻擋語意 | 不阻擋任何流程 |
| Runqueue 影響 | 無（不影響排程過濾；context 供給影響見下方「context bundle 合法消費端」） |
| 業務語意 | 純 metadata 引用（類似 markdown 的 see-also），同時是 context bundle 的合法抽取來源（見下方） |
| CLI 寫入 | `--related-to`、`set-related-to --add/--remove` |

> **重要**：`relatedTo` 不影響排程與阻擋（非時序訊號、非血緣訊號），但作為 context bundle 的合法抽取來源會影響 context 供給（見下方「context bundle 合法消費端」）。「兄弟 A 的 relatedTo 引用兄弟 B → B 應為 A 的父」這種「升格訊號」推論仍舊棄用——弱關聯就是弱關聯，不從中推論結構意圖。

#### 消費端讀取規則：1-hop symmetric union（強制）

任何工具或流程讀取某票的 relatedTo 關聯集合時，必須同時查詢兩個方向：

1. 該票 frontmatter 的 `relatedTo` 清單（正向邊）
2. 全庫中 `relatedTo` 引用了該票 ID 的其他票（反向邊）

兩者聯集才是完整關聯集合。只讀正向邊會漏失單向未回填的關聯——實測 1246 票語料，167 票使用 relatedTo、226 條有向邊，僅 15 對互指對稱（30 條有向邊，對稱率 13.3%），196 條為單向；若消費端只讀正向邊，約 87% 的關聯不會被發現。

**禁止遞移**：union 僅取 1-hop（直接引用/被引用），不可沿 relatedTo 鏈遞移展開——A relatedTo B、B relatedTo C，不得推論 A 與 C 相關。relatedTo 是逐對宣告的弱關聯，遞移會把「A、B 同屬一批兄弟票」誤推成「A 與 C 也相關」，引入原本不存在的關聯。

> 裁決一（儲存方向）：見檔尾〈設計沿革〉與 `CHANGELOG.md`。

#### context bundle 合法消費端

`ticket_system/lib/context_bundle_extractor.py` 的 `SourceKind = Literal["source_ticket", "blocked_by", "related_to"]` 將 relatedTo 納入 context bundle 抽取來源；抽取時透過 `_collect_related_to_symmetric` 呼叫 `relatedto_index.get_symmetric_related_to`，落實上方「消費端讀取規則」的 1-hop symmetric union。

此消費不影響排程與阻擋——Runqueue 過濾與 complete 阻擋皆與 relatedTo 無關，見上方「阻擋語意」「Runqueue 影響」——僅影響 context 供給：被 relatedTo 引用的票，其 what/why 摘要可能被抽入引用方的 context bundle。

> 裁決二（context bundle 消費）：見檔尾〈設計沿革〉與 `CHANGELOG.md`。

---

## 阻擋語意對照表

| 欄位組合 | 阻擋父 / source complete? | 阻擋 runqueue? |
|---------|------------------------|--------------|
| `children`（任意 parent type） | 是（永遠） | 子 ticket 受 blockedBy 影響，不直接受本欄位影響 |
| `spawned_tickets`（ANA 類型 source） | 是（`lifecycle.py` 確認關卡＋`acceptance_auditor.py` 稽核，已定案） | 否 |
| `spawned_tickets`（非 ANA 類型 source） | 否（獨立排程） | 否 |
| `blockedBy` | 否（不影響 complete） | 是（過濾本 ticket） |
| `relatedTo` | 否 | 否 |

> **現況分層說明**：`acceptance-gate-hook.py` 的 `ana_spawned_checker`（hook 層舊機制）已於 W17-120.2 退場，僅保留 `check_ana_has_spawned_tickets` 作為「無後續 ticket」的 missing 警告（不阻擋）。但 ANA complete 阻擋本身**未**隨之移除，仍由另外兩個獨立機制實際執行：`lifecycle.py` 的 `_handle_ana_spawned_confirmation`（complete 時的互動/CLI 確認關卡）與 `acceptance_auditor.py` 的 `validate_spawned_tickets_completed`（W15-003，acceptance 稽核階段的 FAIL 判定）。此為目前已定案的現行設計，非等待收斂的過渡態；若日後確有移除計畫，應另建 ticket 並在此標註其 ID。

---

## 用戶情境對照表

| 情境 | 應用欄位 | CLI 命令 | 判別問題 |
|------|---------|---------|---------|
| 拆分功能成 atomic sub-tasks（必同時交付完整功能） | `parent_id` / `children` | `--parent <PARENT-ID>` | 「上游必須等子任務完成才能 complete？」是 → children |
| **ANA 結論的執行延伸（IMP/DOC 落地）** | **`parent_id` / `children`** | **`--parent <ANA-ID>`** | 「ANA 結論要求落地？」是 → children（PC-091 路線） |
| 執行過程中發現獨立 bug / 技術債（與當前 ticket 無因果） | `source_ticket` / `spawned_tickets` | `--source-ticket <SOURCE-ID>` | 「上游 ticket 結論要求？」否，但發現於執行中 → spawned |
| 兄弟單向時序依賴（規格→實作） | `blockedBy` | `set-blocked-by` 或建立時 `--blocked-by` | 「需要血緣？」否；「需要時序等待？」是 → blockedBy（須滿足串行 4 條件，定義見 `atomic-ticket-methodology.md`〈串行兄弟合法 4 條件〉，否則回歸 ARCH-017 重組） |
| 同 wave 內彼此引用、無時序依賴 | `relatedTo` | `set-related-to` 或建立時 `--related-to` | 「需要等待？」否；「想記錄關聯？」是 → relatedTo |
| 完全獨立的新需求 | （無欄位）sibling | （三皆否，不指定上述任一） | 「上游觸發？時序依賴？關聯？」三皆否 → sibling |

---

## 欄位選擇決策樹

```
建立新 ticket 前自問：
    |
    v
Q1: 上游 ticket 的結論「要求」此 ticket 落地嗎？
   （含 ANA 衍生 IMP / DOC、功能拆分子任務）
    |
    +-- 是 → parent_id（--parent）
    |
    +-- 否 → Q2
         |
         v
    Q2: 此 ticket 是「執行上游 ticket 過程中發現」的獨立技術債 / bug 嗎？
        |
        +-- 是 → source_ticket（--source-ticket）
        |
        +-- 否 → Q3
             |
             v
        Q3: 此 ticket 需要等待其他 ticket 完成才能執行（單向時序）嗎？
            |
            +-- 是 → blockedBy（建立後或建立時 --blocked-by）
            |
            +-- 否 → Q4
                 |
                 v
            Q4: 此 ticket 與其他 ticket 有引用關係但無等待需求嗎？
                |
                +-- 是 → relatedTo（弱關聯 metadata）
                |
                +-- 否 → sibling（不指定上述任一）
```

---

## 反模式速查

| 反模式 | 為何錯誤 | 修正方向 |
|-------|---------|---------|
| ANA 衍生 IMP 用 `--source-ticket` 建為 spawned | 違反 PC-091（ANA 落地統一用 children） | 改用 `--parent <ANA-ID>` |
| 兄弟 A 的 `relatedTo` 引用 B → 推論「B 應為 A 的父」 | `relatedTo` 是弱關聯，不應反推結構 | 結構決策獨立評估，不從 relatedTo 反推 |
| 多個 spawned 但每個都阻擋 source（非 ANA） | `spawned_tickets` 對非 ANA 不阻擋（設計獨立排程） | 若需阻擋改用 children；若獨立排程 spawned 即可 |
| 執行 IMP 時發現獨立 bug，建為 children | children 用於「必同時交付」，獨立 bug 應為 spawned | 改用 `--source-ticket <CURRENT-TICKET>` |
| 兄弟 A 與 B 有依賴但 B 無 `blockedBy` | 隱式依賴難以追蹤（ARCH-017） | 顯式設定 `blockedBy`，或重組為父子（升格） |

---

## 設計沿革

- **relatedTo 不對稱起源**：後建的票能引用先建的票，先建票建立當下對方尚不存在，非語意上只有一方相關。
- **裁決一（儲存方向，2026-08 定案）**：維持儲存單向 + 消費端 1-hop symmetric union，反向索引工具實作為獨立追蹤項目，不在本檔範圍；完整論證見 `CHANGELOG.md`。
- **裁決二（context bundle 消費，2026-08 定案）**：relatedTo 是 context bundle 的合法消費來源，非規範外行為；流程訊號（排程、阻擋、血緣）與 context 供給是兩件事，前者維持無、後者已由既有實作承擔；完整論證見 `CHANGELOG.md`。

---

## 相關文件

- `.claude/error-patterns/process-compliance/PC-091-ana-followup-as-siblings-not-children.md` — ANA 落地用 children 規則來源
- `.claude/error-patterns/process-compliance/PC-073-ana-spawned-misused-as-children.md` — 早期 spawned 使用情境（狀態：已 deprecated 部分內容，現定位於「執行中發現獨立技術債」）
- `.claude/pm-rules/ticket-lifecycle.md` — Ticket 生命週期完整規則（章節：含「ANA Ticket 落地下游血緣選擇」）
- `.claude/methodologies/atomic-ticket-methodology.md` — 任務鏈方法論（內容：兄弟協調模式、聚合父重組範式）
- `.claude/skills/ticket/references/create-command.md` —`--parent` vs `--source-ticket` CLI 副作用對比
- `.claude/skills/ticket/references/track-command.md` — `set-blocked-by` / `set-related-to` 操作說明
- `.claude/skills/ticket/references/track-command.md`〈READ 操作〉〈track deps / depth 子命令〉— `tree`/`chain`/`deps` 命令對血緣與衍生的視覺化分流
- `.claude/error-patterns/architecture/ARCH-017-sibling-hidden-dependency.md` — 兄弟任務隱藏依賴反模式
- `.claude/skills/ticket/ticket_system/lib/context_bundle_extractor.py` — relatedTo 的 context bundle 消費端實作（`SourceKind` / `_collect_related_to_symmetric`）
- `.claude/skills/ticket/ticket_system/lib/file_conflict.py` — `where.files` 讀寫意圖解析與目錄型宣告判定的原始碼權威（〈where.files 宣告語意〉節來源）
