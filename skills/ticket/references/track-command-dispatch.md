# track 子命令（dispatch、dispatch-validate、dispatch-readiness、dispatch-check）

> **用途**：`track` 子命令詳解之一：dispatch、dispatch-validate、dispatch-readiness、dispatch-check。
>
> **同族檔**：`track-command-commit.md`、`track-command-update.md`、`track-command-dispatch.md`、`track-command-session.md`、`track-command-query.md`、`track-command-health.md`。原檔 `track-command.md` 保留檔頭與保留段落，並為各被移走段標保留路由，被移走段標在原檔以同名標題加一行路由保留，既有〈段標〉引用不需改寫。

---

## track dispatch 子命令

派發即落票：輸出可直接貼進 Agent prompt 的骨架文字（`normal`／`review` 兩變體），並視旗標同步寫入票面的暫態記錄與冪等 Commit 規範子節。

### 用法

```bash
ticket track dispatch <ticket_id> --as <agent_name> --task-summary "一句話動作描述（≤ 40 字）"
ticket track dispatch <ticket_id> --as <agent_name> --note "並行派發，commit policy = agent commit"
ticket track dispatch <ticket_id> --kind review \
  --review-perspective "架構一致性" --decision-question "是否符合單一權威決策？"
ticket track dispatch <ticket_id> --as <agent_name> --dry-run   # 只看骨架，不落票
```

### Flag 說明

| Flag | 預設 | 說明 |
|------|------|------|
| `--as` | 無 | 派發對象 agent 名稱，代入骨架 claim/complete 的 `--as` |
| `--note` | 無 | 派發瞬間的暫態約束/步驟，帶時間戳寫入票的「派發日誌」子章節（`## Problem Analysis` 下 `### 派發日誌`）；**不進 Context Bundle** |
| `--kind` | `normal` | `normal`（含 claim/收尾協議完整骨架）／`review`（審查派發，不含 claim/收尾） |
| `--task-summary` | 無 | 一句話動作描述（≤ 40 字），代入骨架任務段 |
| `--review-perspective` | 無 | `--kind review` 專用：審查視角 |
| `--decision-question` | 無 | `--kind review` 專用：裁決問題 |
| `--commit-policy` | `agent` | `agent`（骨架嵌入精準 staging 制式句權威版全文，冪等寫入**票面 body**的「Commit 規範」子章節，非本檔章節）／`pm`（PM 統一 commit，agent 不執行）／`none`（本次派發不涉及 commit） |
| `--isolation` | 無 | `worktree`（normal 骨架收尾句為 `ticket track commit <id> -m "..." --worktree <路徑> -- <檔案>`，只提交產品檔，收尾到 commit 為止並回報 PM；不含 complete 與 finish，complete 由 PM 於合併後在主 checkout 執行，權威為 `CLOSING_BY_ISOLATION`）／`none`（收尾 `complete`，與不帶逐字相同）。未帶且 where.files 寫入路徑含非豁免路徑（豁免清單同 `branch-verify-hook.py`：`.claude/`、`docs/`、`scripts/experiments/` 前綴與頂層檔）時 stderr 印 WARNING、照常輸出、exit 0；帶任一值視為 PM 已明示，不警告。判準見 `.claude/pm-rules/parallel-dispatch.md`〈派發位置判準（強制）〉 |
| `--dry-run` | 關閉 | 只輸出骨架，不寫入票面（不落 `--note`、不冪等寫入「Commit 規範」子節、不呼叫派發前檢查）；輸出首行加浮水印 `[DRY-RUN 未落票]`；預設行為（非 dry-run）不變 |
| `--version` | 無 | 指定版本（預設自動偵測 active 版本） |

### 骨架去向

輸出的骨架文字**直接貼進 Agent prompt**，不需另行改寫。骨架文字的權威來源是 `ticket_system/lib/dispatch_skeleton.py` 的 `SKELETON_TEMPLATE_NORMAL` / `SKELETON_TEMPLATE_REVIEW`，`.claude/references/agent-dispatch-template.md`「骨架（3 段）」節引用其輸出，不手動同步逐字模板。

### 閘門逐檔檢查併入收尾句

normal 骨架會讀 checkout 根的 `.claude/project-integration/merge-gate.yaml`。宣告中帶 `changed_files` 的套件，若有 where.files 命中其範圍（`prefixes` 前綴或 `files` 精確路徑）且符合 `changed_files` 正規式，命令與命中檔就會併入收尾句的 commit 之前：`提交前跑閘門逐檔檢查（結束碼須為 0）：<命令> <檔案>`。

- Why：這類套件只對本次改動檔執行，結果完全由代理人自己的改動決定，提交前在本機即可重現；不轉成本機要求，紅燈要到合併閘門才出現，多佔一輪閘門名額
- 併入既有收尾句而不新增行：骨架最長組合已達 PM 填寫空間的上限（守衛見 `test_agent_prompt_length_guard_hook.py`）
- 不產生命令的情形：宣告不存在、無 `changed_files` 套件、where.files 無命中。此時骨架與未加此功能前逐字相同。全套件型套件（無 `changed_files`）刻意不產生命令，因為命令不帶路徑會跑全套件，與「代理人只跑相關測試檔」的分工衝突
- 宣告無法解析時，stderr 印 `[WARNING]`，骨架照常輸出（不含逐檔檢查），exit 0
- 權威：`GATE_CHECK_CLAUSE`、`gate_check_commands`；範圍判定以 worktree skill 的 `merge_gate.py` 為準

### `--dry-run` 與正常呼叫的差異

| 項目 | 正常呼叫 | `--dry-run` |
|------|---------|-------------|
| 骨架輸出 | 骨架本體逐字相同（組裝不依賴票面寫入結果） | 首行加浮水印 `[DRY-RUN 未落票]`，其餘骨架本體逐字與正常呼叫相同——貼入 prompt 後可辨識是否曾落票 |
| 內部呼叫 `dispatch-readiness`／`dispatch-validate`，exit code 落「派發日誌」（`readiness=N validate=N`） | 執行（診斷文字靜音，僅取 exit code） | 略過 |
| `--note` 寫入「派發日誌」 | 執行（與上列 exit code 同一則 entry） | 略過 |
| `--kind normal` 且 `--commit-policy agent` 時冪等寫入「Commit 規範」子節 | 執行 | 略過 |
| 票存在性檢查 | 執行（唯讀） | 執行（唯讀） |
| 適用情境 | 正式派發 | PM 量測骨架行數、預覽 prompt，可重複執行不需事後 checkout 還原票面 |

**派發日誌 entry 恆定寫入**：不論是否帶 `--note`，正常呼叫（非 dry-run）一律在「派發日誌」新增一則帶時間戳的 entry，格式為 `[時間戳] {--note 文字（若有）｜}readiness=N validate=N`——使「認真跑過派發前檢查」與「完全沒做」在票面產生可辨識差異，取代原本兩者骨架逐字相同、無從辨識是否曾落票的狀態。

### 設計約束

`where.files` 含未帶 `::read` 的目錄級寫入宣告時，`dispatch` 拒絕輸出骨架（`[BLOCKED]` 訊息列出受影響的同目錄活躍票）；`--note` 的暫態內容不可進 Context Bundle——Context Bundle 承載跨派發可重用的穩定任務脈絡，`--note` 只承載派發瞬間才出現、不需沉澱的約束/步驟，兩者定位不同不可互相取代。目錄型宣告判定與各階段（建立僅 WARNING、dispatch 硬擋、commit 展開）完整對照見 `field-semantics.md`〈where.files 宣告語意〉。

### 派發前檢查順序

六個派發前命令各自只回答單一問題，無單一命令涵蓋全部派發前檢查；建議順序：`dispatch-readiness`（單票認知負擔軟性拆分閾值是否過大）→ `dispatch-validate`（Context Bundle 自動填料是否可信）→ `parallel-check`（與其他候選票是否有 `where.files` 交集）→ `dispatch`（輸出骨架並落票）。`dispatch-check`（協調狀態檔案是否有其他活躍派發）與 `conflicts --among`（跨票交集的另一角度）為正交的輔助檢查，可在上述順序任一時點插入，不佔固定位置。外部 `.claude/pm-rules/parallel-dispatch.md`〈並行安全檢查〉的檢查項目僅 `conflicts` 有具名 CLI 對映，其餘多為判斷式描述；`.claude/pm-rules/task-splitting.md`〈3b 派發前檢查〉僅點名 `dispatch-readiness`。**Action**：兩份外部文件與本節六命令順序不一致時，以本節命令排序為準，外部文件視為對應子集的摘要。

**`dispatch` 已內部呼叫前兩項並落痕**：`dispatch`（非 `--dry-run`）執行時會內部呼叫 `dispatch-readiness`／`dispatch-validate`（診斷文字靜音，僅取 exit code），將兩者結果記入「派發日誌」（見上節）。這使得就算 PM 跳過手動先跑這兩個命令、直接呼叫 `dispatch`，票面仍留下「派發前檢查曾經跑過、結果是什麼」的痕跡——取代原本兩者完全不跑也無法從骨架/票面辨識的狀態。**仍建議** PM 派發前手動先跑 `dispatch-readiness`／`dispatch-validate`，因為手動呼叫才有完整診斷文字（各項細目與建議）；`dispatch` 內部呼叫只留 exit code 數字，用於稽核「是否曾檢查」而非取代診斷閱讀。

## track dispatch-validate 子命令

> 來源：W17-003 <!-- rule8-exempt: relocation:自 .claude/skills/ticket/references/track-command.md 逐字搬移 -->

對 target ticket 的 Context Bundle 自動填料結果做合理性檢查，作為 C 方案
（`context_bundle_extractor` 自動抽取）的第二道防線。**與 W10-017.2 的 <!-- rule8-exempt: relocation:自 .claude/skills/ticket/references/track-command.md 逐字搬移 -->
`dispatch-check`（活躍派發狀態查詢）職責正交**，獨立子命令不互相干擾。

**Why**：C 方案自動抽取可能產出「填料成功但內容空殼」的失敗模式（規則 1 hard fail / 規則 2-4 soft warn 即為此設計），需要 lightweight 檢查層攔截，避免空殼 Context Bundle 派發給 agent。

### 用法

```bash
ticket track dispatch-validate <ticket_id>
```

### 合理性檢查規則

| 規則 | 內容 | 違反後果 |
|------|------|---------|
| 1 | Context Bundle section 存在且 content 非全空白 | 硬性失敗 → exit 2 |
| 2 | Context Bundle content 長度 ≥ 50 字元（避免空殼填料） | 軟性警告 → exit 1 |
| 3 | frontmatter `where.files` 列出的檔案在檔案系統存在 | 軟性警告 → exit 1 |
| 4 | acceptance ≥ 3 項（4V 原則） | 軟性警告 → exit 1 |
| 5 | （保留）LLM 審查 Context Bundle 是否真能讓 agent 上手 | 本 ticket 不實作 |

> **規則 4「≥ 3」非逐一對應 4V 各原則的推導**：`track_dispatch_validate.py` 原始碼註解僅載「4V 原則，少於 3 項視為規格不足」，未進一步說明為何門檻是 3 而非 4（4V 四原則的字面數）或其他值；此為經驗閾值（「至少 3 項通常代表跨面向覆蓋」的粗略啟發），非由 4V 定義逐條推導所得，讀者不應假設每項 acceptance 對應唯一一個 V。

### Exit code

| code | 意義 |
|------|------|
| 0 | 全部規則通過 |
| 1 | 軟性警告（規則 2/3/4 至少一項違反） |
| 2 | 硬性失敗（規則 1 違反、ticket 不存在、IO/YAML 錯誤） |

### 設計約束

- **不**修改 ticket，僅輸出診斷
- **不**取代 hook / scheduler 的執行控制
- **不**負責產生 dispatch-plan、也**不**實作 batch dispatch CLI（與 W17-029 邊界） <!-- rule8-exempt: relocation:自 .claude/skills/ticket/references/track-command.md 逐字搬移 -->
- where.files 為空時規則 3 視為通過（DOC 類 ticket 常見情形）

### 範例

```bash
$ ticket track dispatch-validate 0.18.0-W17-003
dispatch-validate 0.18.0-W17-003:
  [PASS] 規則 1 欄位非空: Context Bundle section 存在且非空
  [PASS] 規則 2 內容長度: Context Bundle 內容長度 596 >= 50
  [PASS] 規則 3 檔案存在: where.files 3 個檔案皆存在
  [PASS] 規則 4 acceptance 項數: acceptance 5 項 >= 3
[PASS] 全部規則通過
```

---

## track dispatch-readiness 子命令

> 來源：W17-053 <!-- rule8-exempt: relocation:自 .claude/skills/ticket/references/track-command.md 逐字搬移 -->

派發前認知負擔閾值與綜合就緒度檢查。讀取 ticket frontmatter `where.files`
與 `acceptance` 及 Context Bundle section，自動計算三項核心閾值並加跑三項
一致性啟發式檢查（共六項），輸出 pass/warn/fail 與建議。**與 `dispatch-check`
（活躍派發狀態，W10-017.2）和 `dispatch-validate`（CB 合理性，W17-003） <!-- rule8-exempt: relocation:自 .claude/skills/ticket/references/track-command.md 逐字搬移 -->
職責正交**，獨立子命令不互相干擾。

**Why**：派發前缺乏統一 CLI 入口檢查 ticket 是否符合認知負擔閾值、以及
acceptance 與寫入集（`where.files`）是否宣告一致，PM 需手動對照
`.claude/rules/core/cognitive-load.md` 與 `cognitive-load-execution-details.md`
判斷拆分需求，違反摩擦力方法論執行階段減摩擦原則（W17-049 ANA linux 視角）； <!-- rule8-exempt: relocation:自 .claude/skills/ticket/references/track-command.md 逐字搬移 -->
acceptance 明文點名的檔案未列入 `where.files` 時，代理人依 acceptance 動了
該檔，commit 時會被 bare-commit-guard 攔下（見檢查 6）。

**Consequence**：缺少自動化檢查會讓 PM 偶爾遺漏拆分判斷，將過大任務派
給代理人；3b 派發後常見症狀包含代理人 commit 遺漏部分職責、回合耗盡前
只完成一半、跨檔不一致導致測試失敗，或 acceptance 與宣告範圍矛盾迫使代理人
在「守寫入集」與「滿足 acceptance」間二選一。

**Action**：派發 3b 實作 ticket 前以本命令自檢；exit 0 直接派發、exit 1
評估是否豁免（如跨進程同步修復條款）、exit 2 依 fail 來源分流處置（見下方
Exit code 表與各檢查說明）——**不可一律視為「須拆票」**，檢查 6 未過時拆票
無效，正確處置是補 `where.files` 或改寫 acceptance（文件給的處置對新 fail
來源無效的舊 pattern：任何檢查新增後，本節的處置對照表都必須同批更新）。

### 用法

```bash
ticket track dispatch-readiness <ticket_id>
```

### 閾值 1-3（認知負擔軟性拆分閾值）

| 閾值 | 取得方式 | 軟上限 | 強制拆分 |
|------|---------|-------|---------|
| 1. 功能職責數（以 acceptance 條目近似） | `acceptance` 欄位計數 | > 2 | > 4 |
| 2. 修改檔案數 | `where.files` 欄位計數 | > 5 | > 10 |
| 3. Context Bundle tokens（以 chars/4 近似） | Context Bundle section 字元數 | > 3000 | > 5000 |

> **閾值來源**：軟上限（`> 2`／`> 5`／`> 3000`）源自 `.claude/references/cognitive-load-execution-details.md`「3b
> 派發前閾值」三項核心指標；強制拆分門檻（`> 4`／`> 10`／`> 5000`）該文件僅載
> tokens 一項（`> 5000`），閾值 1、2 的強制門檻（`4`、`10`）**不出現**於該文件，
> 僅見於 `track_dispatch_readiness.py` 原始碼常數 `_RESPONSIBILITY_HARD_MAX` /
> `_FILES_HARD_MAX` 的行內註解：`4` 有推導依據（「依據 7±2 取下限保守」，即
> Miller's Law 認知負擔上限的保守下界）；`10` 僅為軟上限 `5` 的兩倍，註解未
> 附加推導理由。閾值 1「功能職責數」CLI 無法精確自動推導，
> 沿用 acceptance 條目作為近似訊號，最終由 PM 判定。
>
> **近似性警告（W17-213）**：acceptance 若含「跑測試」「補文件」「執行驗證」 <!-- rule8-exempt: relocation:自 .claude/skills/ticket/references/track-command.md 逐字搬移 -->
> 等驗證類條目，會讓 acceptance 條目數高於實際功能職責數（高估）；反之，若
> 多個職責被合併寫成單一 acceptance（低估），也會偏離真值。CLI 僅作近似訊號，
> 達 WARN/FAIL 時 PM 應手動覆核 acceptance 是否反映真實職責數，再決定是否拆分。

### 檢查 4-6（acceptance 與寫入集一致性啟發式）

| 檢查 | 判定內容 | 命中條件 | 上限 status |
|------|---------|---------|------------|
| 4. acceptance 與寫入集一致性 | 兩種訊號來源：(a) acceptance 含測試類關鍵詞（測試/test/覆蓋/回歸/regression/涵蓋）但 `where.files` 無任何測試型態路徑；(b) acceptance 提及含萬用字元 `*` 的 glob 路徑樣式（如 `app_localizations*.dart`）但 `where.files` 無檔案可被該樣式 fnmatch 涵蓋 | (a) 關鍵詞命中且無測試路徑，或 (b) glob token 未被 where.files 涵蓋 | warn（不產生 fail） |
| 5. where.files 路徑存在性 | `where.files` 含不存在路徑，且 acceptance 無新建語意（建立/新增/新檔/create/add） | 路徑不存在且無新建關鍵詞 | warn（不產生 fail） |
| 6. acceptance 提及路徑涵蓋性（唯一強制 fail 的啟發式） | acceptance 文字中具備已知副檔名的路徑樣式 token，未被 `where.files` 前綴或檔名比對涵蓋 | 任一提及路徑未涵蓋 | **fail（強制）** |

> 檢查 4、5 皆為啟發式，語意判定有邊界（未命中不代表無矛盾，關鍵詞比對
> 亦可能對非測試語境產生 false positive），故上限為 warn，PM 保留覆核空間。
> 檢查 6 抽取的是「acceptance 明文點名的具體檔案路徑」，誤判成本已由已知
> 副檔名 + ASCII 邊界收斂，故為全套件唯一產生 fail 的啟發式檢查。
>
> 閾值 2、檢查 5、檢查 6 讀取的 `where.files` 計數/存在性/涵蓋性皆以剝除
> `::read`／`::write` 後綴後的純路徑計算；後綴語法與目錄型宣告展開規則見
> `field-semantics.md`〈where.files 宣告語意〉。

### Exit code

| code | 意義 |
|------|------|
| 0 | 六項檢查全數通過 |
| 1 | 軟性警告（閾值 1-3 任一超軟上限，或檢查 4/5 命中矛盾，但未達下列任一強制失敗條件） |
| 2 | 硬性失敗（閾值 1-3 任一超強制拆分閾值 / 檢查 6 未過（acceptance 提及路徑未被 `where.files` 涵蓋）/ ticket 不存在 / IO／YAML 錯誤） |

**重要**：本命令 exit code 語意**不與** `dispatch-check`（W10-017.2，exit <!-- rule8-exempt: relocation:自 .claude/skills/ticket/references/track-command.md 逐字搬移 -->
1 = 有活躍派發）和 `dispatch-validate`（W17-003，exit 1 = CB 軟警告）共享； <!-- rule8-exempt: relocation:自 .claude/skills/ticket/references/track-command.md 逐字搬移 -->
呼叫端必須以命令名稱判別語意，禁止以 exit code 跨命令解讀。

**exit 2 的處置依 fail 來源分流，禁止一律拆票**：

| fail 來源 | 正確處置 | 錯誤處置（無效） |
|-----------|---------|-----------------|
| 閾值 1-3 任一超強制拆分閾值 | 拆分為多個 ticket 後重新派發 | — |
| 檢查 6 未過（acceptance 提及路徑未被 `where.files` 涵蓋） | 把該路徑加進 `where.files`，或改寫 acceptance 移除該路徑點名 | 拆票——拆分不會改變 acceptance 與 `where.files` 的宣告落差 |
| ticket 不存在 / IO／YAML 錯誤 | 修正呼叫參數（ticket ID、`--version`）或檢查 ticket 檔案完整性 | 拆票 |

### 設計約束

- **不**修改 ticket，僅輸出診斷
- **不**取代 hook / scheduler 的執行控制
- **不**觸碰既有 `dispatch-check`（W10-017.2）與 `dispatch-validate`（W17-003） <!-- rule8-exempt: relocation:自 .claude/skills/ticket/references/track-command.md 逐字搬移 -->
- 閾值 1 為近似訊號（acceptance 條目 ≠ 功能職責數），最終拆分判斷由 PM 決定
- Context Bundle section 不存在時閾值 3 視為 0 tokens 通過
- 檢查 4、5 為 warn-only 啟發式，未命中不代表無矛盾，PM 保留覆核空間
- 檢查 6 僅比對具備已知副檔名的路徑樣式 token，純數字版本號或 ticket ID 不會誤判為路徑

### 跨進程同步修復豁免

若 ticket 符合「跨進程同步修復」全部 5 特徵（見 `cognitive-load-execution-details.md`
「跨進程同步修復豁免條款」），可豁免閾值 1，本命令僅供 PM 參考，不應視
為強制阻擋訊號。此豁免僅適用閾值 1，不適用檢查 6（路徑涵蓋性與認知負擔
豁免條款無關）。

### 範例

```bash
$ ticket track dispatch-readiness 0.18.0-W17-053
dispatch-readiness 0.18.0-W17-053:
  [WARN] 閾值 1 功能職責數（acceptance 近似）: acceptance 條目 3 > 2（軟警告；建議拆分為多個 ticket）
  [PASS] 閾值 2 修改檔案數（where.files）: where.files 3 ≤ 5
  [PASS] 閾值 3 Context Bundle tokens: Context Bundle ~250 tokens ≤ 3000
  [PASS] 檢查 4 acceptance 與寫入集一致性（啟發式）: acceptance 無測試類關鍵詞命中，亦無未涵蓋的 glob 路徑提及
  [PASS] 檢查 5 where.files 路徑存在性（啟發式）: where.files 路徑全數存在
  [PASS] 檢查 6 acceptance 提及路徑涵蓋性（強制）: acceptance 未偵測到路徑樣式 token
[WARN] 軟性警告：建議審視拆分必要性
```

```bash
$ ticket track dispatch-readiness <ticket_id>
dispatch-readiness <ticket_id>:
  [PASS] 閾值 1 功能職責數（acceptance 近似）: acceptance 條目 2 ≤ 2
  [PASS] 閾值 2 修改檔案數（where.files）: where.files 2 ≤ 5
  [PASS] 閾值 3 Context Bundle tokens: Context Bundle ~600 tokens ≤ 3000
  [PASS] 檢查 4 acceptance 與寫入集一致性（啟發式）: acceptance 無測試類關鍵詞命中，亦無未涵蓋的 glob 路徑提及
  [PASS] 檢查 5 where.files 路徑存在性（啟發式）: where.files 路徑全數存在
  [FAIL] 檢查 6 acceptance 提及路徑涵蓋性（強制）: acceptance 提及 1 項路徑未被 where.files 涵蓋，請把該路徑加進 where.files 或改寫 acceptance
      - SKILL.md
[FAIL] 至少一項超強制拆分閾值，建議拆 ticket 後重新派發
```

> 上例 CLI 輸出文字仍沿用「建議拆 ticket 後重新派發」（來自
> `execute_dispatch_readiness` 的統一提示行），但此提示對檢查 6 觸發的
> fail 不適用——**判斷處置時以上方「exit 2 的處置依 fail 來源分流」表為準，
> 不依 CLI 輸出的統一提示行字面行事**。

---

## track dispatch-check 子命令

檢查 `.claude/dispatch-active.json` 是否有活躍派發，取代人工手動讀檔判讀。

### 用法

```bash
ticket track dispatch-check
```

不帶任何參數；讀取當下（依「Ticket 狀態與程式碼提交的 root 分離」節同一套 root 解析規則，統一指向主倉庫）的 `.claude/dispatch-active.json`。

### 判定規則

| 情境 | 輸出 | Exit code |
|------|------|-----------|
| 檔案不存在，或存在但 `dispatches` 為空陣列 | `[PASS] 無活躍派發，可繼續` | 0 |
| `dispatches` 非空 | `[WARN] 有 N 個活躍派發：` + 逐筆列出 `agent_description` / `ticket_id` / `dispatched_at` + 新鮮度標註（見下） | 1 |
| 檔案讀取失敗、JSON 格式錯誤、或 root/`dispatches` 結構不符 | `[FAIL] ...`（stderr） | 2 |

**新鮮度標註**：逐筆條目末尾附年齡標記，沿用 `track_dashboard.DEFAULT_STALE_THRESHOLD_MIN`（60 分鐘）同一新鮮度慣例——距今未逾 60 分鐘標 `(Nmin)`，逾閾值標 `[STALE Nmin]`。`dispatched_at` 缺失、格式錯誤或為未來時間時不猜測、不標記（fail-safe，年齡欄留空）。`[STALE]` 筆數 > 0 時，`[WARN]` 清單後另加一行彙總：`[WARN] 其中 N 筆逾 60 分鐘未見更新（[STALE] 標記），可能為遺留記錄，建議對照 track sessions 或執行 dispatch-check --prune（僅清理 session 確認不存在的條目）`。

**WARN 後下一步**：收到 `[WARN]` 時對照每筆條目的新鮮度標註與 `ticket track sessions` 的存活 session：`(Nmin)` 未逾閾值（該 agent 尚有機會回報）則暫緩新派發；`[STALE Nmin]` 且對應 session 已不存在，屬正常應由 `subagent-stop-dispatch-cleanup-hook.py`（SubagentStop 觸發）清除的殘留條目未被清除，改執行 `ticket track dispatch-check --prune` 交叉比對 pm-registry 清理，不再逕自手動改 `.claude/dispatch-active.json`（見下節）；不逕自視為「有活躍派發」而延後派發。

### `--prune`：清理「[STALE] 且 session 不存在」的條目

```bash
ticket track dispatch-check --prune
```

取代原「見 `[STALE]` 手動清理 `.claude/dispatch-active.json`」的無痕跡做法。判定條件為 AND：(1) 條目已標 `[STALE]`（見上方新鮮度標註）；(2) 條目 `session_id` 非空、且不在 `pm-registry.json`（`ticket track sessions` 同一來源）的 session 集合內。

| `session_id` 狀態 | 處置 |
|------|------|
| 非空，且不在 registry 內 | 判定為「不存在」，清理 |
| 非空，且仍在 registry 內（即使 registry 內該 session 本身標 STALE） | 保留——heartbeat 慢但仍存活的 agent，不可誤判為不存在 |
| 空字串（無 session_id，舊格式條目） | 保留——無法歸戶，不可判定 |
| registry 讀取失敗（git 不可用 / 檔案缺失 / 解析失敗） | 保留全部條目——無法判定時保守不清理，輸出 `[INFO] --prune：pm-registry 不可用，無法判定 session 是否存在，本次不清理` |

清理結果雙通道輸出：stderr 逐筆列出 `agent`／`ticket`／`session_id`／`dispatched_at`，同時寫入 `.claude/hook-logs/dispatch-check-prune/dispatch-check-prune-{YYYYMMDD}.log`（`INFO` 級別，供事後稽核，符合可觀測性規則 4）。無符合條件的條目時輸出 `[INFO] --prune：無符合「[STALE] 且 session 不存在」條件的條目`，不誤報為已清理。清理後若 `dispatches` 歸零，回傳 `[PASS]`（exit 0）；仍有剩餘活躍派發則照常輸出 `[WARN]`（exit 1）。

### 與 track dispatch-validate 的差異

`dispatch-check` 檢查的是**協調狀態檔案**（是否有其他派發正在進行，用於避免同時派發衝突）；`dispatch-validate`（見上節）檢查的是**單一 ticket 的派發合理性**（Context Bundle 自動填料是否可信）。兩者職責正交，可能同時需要在派發前執行。

### 設計約束

Exit code 2（IO 或 JSON 格式錯誤）刻意保守判定為 NO-GO，供 Hook 程式化判定；本命令只加格式化輸出與 exit code，不改變既有的「讀檔 + 判斷 dispatches 陣列空/非空」判定規則。

---
