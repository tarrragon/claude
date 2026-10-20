# Agent Dispatch Template（PM 自做 framework 規則編輯與共用 lib 修復派發提醒）

> **用途**：派發 prompt 情境與政策詳解之一：PM 自做 framework 規則編輯與共用 lib 修復派發提醒。
>
> **同族檔**：`agent-dispatch-closeout.md`、`agent-dispatch-testing.md`、`agent-dispatch-worktree.md`、`agent-dispatch-pm-edit.md`、`agent-dispatch-variants.md`。原檔 `agent-dispatch-template.md` 保留檔頭與保留段落，並為各被移走段標保留路由，被移走段標在原檔以同名標題加一行路由保留，既有〈段標〉引用不需改寫。

---

## PM 自做 framework 規則編輯流程

> **用途**：PM 直接編輯 framework 規則檔（`.claude/rules/`、`pm-rules/`、`references/`、`skills/`、`methodologies/`、`agents/`）的標準流程，含 Layer 1 自檢 + Layer 2 委員審查。
>
> **設計依據**：Layer C 落地（與 Layer A Hook + Layer B Claim 提示三層協同）。實證來源：框架層 SKILL 檢查與 Layer 2 委員審查缺口暴露，規則 6 條款違反 compositional-writing 原則 3。

### 標準步驟（6 步，跳過項需評估成本）

| 步驟 | 動作 | 跳過此步的成本 vs 執行此步的成本 |
|------|------|----------------------------|
| 1. Read SKILL | claim 後、Edit 前 Read `.claude/skills/compositional-writing/SKILL.md`（與該情境對應的 reference）。同 session 已 Read 過時可省略 | 跳過：違反原則 3 機率高（W17-060 實證），事後 Layer 2 補做約 5-10K token；執行：先讀 SKILL 約 2-3K token 換取首次撰寫品質 | <!-- rule8-exempt: relocation:自 .claude/references/agent-dispatch-template.md 逐字搬移 -->
| 2. 撰寫 | 依 SKILL 原則撰寫，重點：原則 3（機會成本語氣）+ 原則 6 第 3 輪 review（絕對主義詞翻 trade-off） | 規範性文字（template / hook 訊息 / claim 提示）以機會成本示範；事實陳述（描述歷史違規）可保留絕對語氣；兩者明確分區 |
| 3. 派 Layer 2 | 派 `basil-writing-critic` 等獨立委員審查文字品質，明示審「絕對主義 vs 機會成本 / 正向 vs 負向表述」 | 規範性文字場景：PM 自做 Layer 1 + Layer 4 同主體失去獨立性風險高（PC-081），獨立委員約 3-5K token 換取盲區發現（W17-051 多視角審查盲區案例）；事實陳述場景：風險較低，可視範圍決定是否派發 | <!-- rule8-exempt: relocation:自 .claude/references/agent-dispatch-template.md 逐字搬移 -->
| 4. 收報告 | 接收 Layer 2 報告，按 P0/P1/P2 分級判斷修正幅度 | P0 阻擋級值得修正；P1 視成本決定修正或建 follow-up；P2 可建 follow-up 批次處理 |
| 5. 修正 | 依報告修正內容 | 修正幅度大時可選擇性再派一輪委員 |
| 6. commit（建議） | commit msg 含「Layer 2 by [agent-name]」標記，便於後續追蹤 | 缺標記時 commit-msg hook 警告（依 W17-126 落地後生效）；標記讓後人快速判斷 commit 是否經獨立審查 | <!-- rule8-exempt: relocation:自 .claude/references/agent-dispatch-template.md 逐字搬移 -->

### Commit msg 標記規範

```
docs(<ticket-id>): <summary>

<body>

Layer 2 by <agent-name> (audit <agentId 或 ticket ID>)
```

實際範例（取自 W17-060 落地）： <!-- rule8-exempt: relocation:自 .claude/references/agent-dispatch-template.md 逐字搬移 -->
```
docs(0.18.0-W17-060): 新增 ai-communication-rules 規則 6

Layer 2 by basil-writing-critic (agent ad93c61e88f1ff6e8)
```

Layer 2 不適用情境（如 typo 修正、純結構重組）標：
```
Layer 2 不適用 by <理由>
```

上述兩類以外，預設走 Layer 2；模糊場景偏向走 Layer 2 換取盲區發現（事後補做成本高於事前審查）。

### 適用範圍

| 情境 | 走完整 6 步驟的成本對比 | 可省略條件 |
|------|---------------------|----------|
| 新增規則條款 | 完整 6 步驟成本約 10-15K token；省略 Layer 2 風險高（規則條款是後續引用基礎，違規累積成本高） | 規則條款屬內部草案/實驗條款且後續會強制走 Layer 2 收斂時可暫省（草案標記必須明示） |
| 修正既有規則文字 | 完整 6 步驟成本約 8-12K token；視修正範圍與既有規則重要性 | 修正屬純語句通順化（未改規範強度、未改適用邊界）時可省略 |
| 新增 / 修改 SKILL.md 主文 | 完整 6 步驟（SKILL 主文影響面廣） | SKILL 主文無「適用情境/觸發條件/禁止行為」段落變更時可省略 |
| typo 或 link 修正 | 可省略 Layer 2，commit msg 標「Layer 2 不適用 by typo」 | 預設可省略 |
| 純結構重組（不改文字） | 可省略 Layer 2，標「Layer 2 不適用 by 結構重組」 | 預設可省略 |

<!-- rule8-exempt: relocation:自 .claude/references/agent-dispatch-template.md 逐字搬移 -->
### 三層協同（W17-122 ANA Solution 落地後生效）

本流程是三層防護的 Layer C（紙本約束）。Layer A（hook 自動偵測）與 Layer B（claim 提示）為事前提醒，本 Layer 為事中規範與事後追蹤的紙本依據：

| 時點 | 機制 | 落地 ticket |
|------|------|-----------|
| 事前 | Hook 偵測 Edit framework 路徑時若無 SKILL 呼叫即警告 | W17-127（未來落地） | <!-- rule8-exempt: relocation:自 .claude/references/agent-dispatch-template.md 逐字搬移 -->
| 事前 | claim 時若 ticket where.files 含 framework 路徑即新增 S 問提示 | W17-125（未來落地） | <!-- rule8-exempt: relocation:自 .claude/references/agent-dispatch-template.md 逐字搬移 -->
| 事中 / 事後 | 本流程 + commit msg 標記規範 | W17-124（本 ticket） | <!-- rule8-exempt: relocation:自 .claude/references/agent-dispatch-template.md 逐字搬移 -->
| 事後追蹤 | commit-msg hook 偵測 framework commit 是否含 Layer 2 標記 | W17-126（未來落地） | <!-- rule8-exempt: relocation:自 .claude/references/agent-dispatch-template.md 逐字搬移 -->

四個 ticket 落地完成後，三層防護完整協同；任一層失效時其他層提供備援。

---

## Layer 1 自檢觸發指引

> **用途**：PM 派發代理人時，在 prompt 末段插入自檢指令，使代理人在 complete 前執行一輪 Layer 1 自律審查。
>
> **設計依據**：實驗驗證發現第二步修正成本遠低於第一步生成，Layer 1 是最低成本的品質防護層。

### 觸發條件

| 情境 | 是否插入自檢指令 |
|------|----------------|
| IMP / ANA / DOC ticket（產出包含規則、方法論、長段說明） | 建議插入 |
| 純機械任務（格式修正、路徑替換等） | 可省略 |
| 代理人回報已執行 Layer 1 的情境（同 session 剛跑完） | 可省略 |

### prompt 末段插入範本

在任意派發 prompt 的最後一段，加入以下指令（可選一種）：

**標準版**（適合 IMP/ANA 規則類產出）：

```markdown
完成後 complete 前，依 .claude/references/agent-self-check-template.md 執行 Layer 1 自檢
（A 文字品質 / B 禁用字 / C Schema 結構），發現違規立即修正，結果寫入 Solution ### 自檢結果。
```

**精簡版**（適合小型 DOC 或純文件修正）：

```markdown
commit 前快速掃描禁用字（數據/代碼/默認/文檔/軟件/硬件/信息）和 emoji，確認無誤後 complete。
```

### 為何放末段而非開頭

自檢是「完成後」的動作，放末段對代理人的指令順序更自然：先執行任務，再回頭自檢，符合「生成 → 審查」的認知流程。放開頭會讓代理人在任務未完成時提前分心。

---

## 共用 lib 修復派發提醒（PC-136 強制）

> **用途**：派發共用 lib / predicate / shared utility bug 修復 IMP 時，在 prompt 加註此提醒，使代理人在修復前主動 grep all callers，防止「只修觸發 bug 的單一 caller」反模式。
>
> **設計依據**：PC-136（多次重爆軌跡證實）— 未 grep all callers 的修復會在數週內從另一處重爆。

### 觸發條件

| 情境 | 是否插入提醒 |
|------|------------|
| IMP 修復共用函式 / predicate / shared utility bug | 強制 |
| ANA 驗證共用函式正確性 | 強制（指向 operational-error-root-cause-methodology.md PC-136 章節） |
| 純單檔內部函式修復（無 caller 散佈） | 可省略 |
| 純機械任務（格式 / 路徑替換） | 可省略 |

### prompt 插入範本

在共用 lib 修復派發 prompt 中，加入以下段落（接在「## 任務」之後）：

```markdown
## 修復前必執行（PC-136）

執行 `grep -rn "<函式名>" .claude/ src/ lib/ tests/` 列出：
- 所有同名實作位置（lib + hook 雙副本可能存在）
- 所有 caller 位置

在 ticket Problem Analysis append 完整清單後再開始修復。修復後對每處逐一確認已同步修正，禁止只修觸發 bug 的單一 caller。

依據：.claude/references/quality-common.md §1.2.6
```

### 為何強制

| 防護層 | 失效模式 |
|-------|---------|
| 代理人自律（quality-common §1.2.6） | 高壓 / 急迫情境下易跳過 grep |
| **派發 prompt 提醒** | **派發時即明示，代理人執行前有檢查依據** |
| ANA 方法論（callees 追蹤） | 屬 ANA 階段，IMP 階段需另有提醒 |

三層協同，prompt 提醒是 IMP 階段的最後防線。

---
