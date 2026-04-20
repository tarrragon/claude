# Writing Prompts

## 檔案定位

本檔案為 **`.claude/rules/core/ai-communication-rules.md` 的詳細版庫**（portability-allow: 本 skill 架構性橋接至框架 auto-load 規則，非可攜性違規）。

框架級 auto-load 規則保留 90 行骨架（核心原則、強制規則、檢查清單），本檔提供完整 Agent Prompt / Context Bundle 骨架、Token 節省深度策略、情境範例與反模式解析。

**閱讀決策**：

| 需求 | 讀哪份 |
|------|-------|
| 快速對照對話規範（預設每次 session auto-load） | `.claude/rules/core/ai-communication-rules.md` (portability-allow) |
| 寫大型 Agent Prompt / Ticket Context Bundle | 本檔（完整骨架範例） |
| 深度理解 Token 節省取捨 | 本檔「Token 節省策略」章節 |
| 新增或修改 Skill reference 的撰寫品質規範 | `references/reference-authoring-standards.md` |

---

## 情境定位

本 reference 為 `compositional-writing` skill 的情境應用：撰寫 prompt。

Prompt 的讀者是 AI 模型，但維護者是人類。寫作目標是在**最少 token 內傳遞最精準的意圖**，同時維持人類可讀性（prompt 需要被維護和迭代）。與其他寫作情境不同，prompt 的每一個冗詞都是直接成本——但過度精簡又會讓意圖模糊，導致 AI 輸出偏離目標。本文件說明如何平衡 token 成本與意圖清晰度。

---

## 為什麼 Prompt 寫作需要獨立指引

| 差異點 | 一般文件 | Prompt |
|-------|---------|--------|
| 主要讀者 | 人類 | AI 模型 |
| 次要讀者 | 無 | 維護者（人類） |
| 冗餘成本 | 低（只佔螢幕） | 高（直接 token 費用） |
| 語氣偏差代價 | 讀者重讀 | AI 執行失敗、產出錯誤 |
| 結構化標記 | 錦上添花 | 必要（AI 靠標記定位） |

核心結論：**Prompt 必須在 token 預算內達成「意圖無歧義 + AI 可快速定位關鍵段落」兩個目標**。

---

## 五大原則在 Prompt 情境的應用

### 1. 原子化（Atomization）× Prompt

**核心**：一個 prompt 一個任務目標。

Prompt 的「原子單位」不是「一句話」，而是「一個可被驗收的任務」。一個 prompt 同時要求多個不相關任務（例如「幫我寫測試 + 順便重構 + 檢查安全性」）會導致 AI 分散注意力，每個子任務都做得不完整。

**判斷標準**：

| 問題 | 若答「是」 | 行動 |
|------|-----------|------|
| Prompt 目標是否可用單一動詞 + 單一受詞描述？ | 是 | 原子 |
| 是否存在兩個以上的「和」連接不同動作？ | 是 | 拆分 |
| 驗收條件是否可並列表達而非混合？ | 是 | 可能不原子 |

**反例**：

```
# 違反原子化：三個任務混在一起
請閱讀檔案 X，找出函式 Y 的測試覆蓋缺口，
補上缺失的測試，並順便重構重複的 setup 程式碼，
最後把所有 console.log 改成 logger。
```

**正確**（拆為 3 個獨立 prompt 或 3 個明確分段）：

```
# 任務 1：分析測試覆蓋缺口
輸入：檔案 X 的函式 Y
輸出：未被測試覆蓋的分支清單

# 任務 2：補缺測試
輸入：任務 1 的缺口清單
輸出：新增的測試案例

# 任務 3：清理（獨立 ticket）
輸入：console.log 位置清單
輸出：logger 替換後的 diff
```

---

### 2. 索引建立（Indexing）× Prompt

**核心**：結構化標記讓 AI 快速定位關鍵段落。

AI 讀 prompt 時會建立「段落角色模型」——哪段是目標、哪段是約束、哪段是輸出格式。如果 prompt 是純散文，AI 必須從頭讀到尾才能判斷每段角色，token 和注意力都被浪費。結構化標記（章節標題、列表、表格、標籤）讓 AI 跳讀定位。

**結構化標記工具箱**：

| 標記 | 用途 | AI 解讀 |
|------|------|---------|
| `## 標題` | 大段角色分隔（任務 / 約束 / 輸出格式） | 跳讀定位 |
| `### 子標題` | 同一大段內的細分 | 細節索引 |
| Markdown 表格 | 對照型資訊（選項、規則、映射） | 一次載入多維度 |
| 有序列表 `1./2./3.` | 步驟順序 | 執行序列 |
| 無序列表 `- ` | 條件集合 | 平行規則 |
| XML 標籤 `<task></task>` | 明確邊界（用於需要嚴格分隔的區塊） | 強制邊界 |
| 程式碼圍欄 ` ``` ` | 字面值保護（AI 不會誤解為指令） | 不執行區域 |

**建議章節骨架**（大型 prompt）：

```markdown
## 任務目標
（1-2 句話）

## 輸入
- 檔案路徑 / 資料內容 / 前置條件

## 約束
- 禁止項
- 必要項

## 輸出格式
- 預期產出的結構

## 驗收條件
- [ ] 可勾選的具體條件
```

小型 prompt 可壓縮為單段，但仍要保留「任務—約束—輸出」三段訊號。

---

### 3. 意圖顯性與商業邏輯（Explicit Intent & Business Logic）× Prompt

**核心**：開頭直述任務目標，明確預期輸出格式，告訴 AI 為什麼。

#### 3.1 開頭即表達意圖

Prompt 第一句就說清楚「要 AI 做什麼」。AI 讀 prompt 時會根據前幾句建立初始任務模型——如果前段是背景鋪陳，AI 可能在建立錯誤假設後才讀到真正目標，導致輸出偏差。

**反例**：

```
# 意圖埋在後段
我們的系統最近遇到一些效能問題，昨天 profile 發現
BookRepository 的 getAll() 呼叫量暴增，估計是 cache 失效。
我之前試過加 memoization 但沒效果，可能是 key 設計問題。
所以，請幫我重寫 getAll() 的快取層。
```

**正確**：

```
# 開頭直述目標
任務：重寫 BookRepository.getAll() 的快取層。

背景（供參考，非必讀）：
- 現有 memoization 的 key 設計有問題
- profile 顯示 getAll() 被大量呼叫
```

#### 3.2 明確輸出格式

告訴 AI 預期產出結構，而非期待它自行推斷。

**反例**：「幫我分析一下這段程式碼」
**正確**：「分析下列程式碼，以 Markdown 表格列出：問題 | 影響 | 建議修正。每個問題另附 3-5 行說明。」

#### 3.3 告訴 AI 「為什麼」

當約束或做法不直觀時，補上理由，避免 AI 基於「合理預設」覆寫規則。

**反例**：「不要使用 async/await」
**正確**：「不要使用 async/await（本專案目標環境不支援 ES2017+，只能用 Promise.then）」

沒有理由的禁令，AI 可能在重構時基於「現代寫法更好」的預設還原。

---

### 4. 可查詢性（Searchability）× Prompt

**核心**：模板設計讓維護者能 grep；變數佔位符命名規範讓 AI 和人類都清楚。

Prompt 不是一次性文字，會被反覆維護和調整。未來 6 個月後，維護者需要 grep 找到「所有派發 engineer 代理人的 prompt」「所有包含 context bundle 的 prompt」。如果 prompt 沒有可搜尋的穩定關鍵字，維護成本會爆炸。

#### 4.1 穩定關鍵字

在 prompt 模板的關鍵位置保留穩定詞彙，讓 grep 能一次命中所有同類 prompt。

| 查詢需求 | 穩定關鍵字範例 |
|---------|-------------|
| 找所有 ticket 派發 prompt | 在開頭統一寫 `Ticket: {id}` |
| 找所有驗收條件區段 | 統一用 `## 驗收條件` 標題 |
| 找所有需要 ticket track complete 的 prompt | 統一包含 `ticket track complete` 字串 |

#### 4.2 變數佔位符命名規範

模板中的變數必須用明確且可 grep 的佔位符，避免 `{x}` `{var}` 這類模糊名稱。

| 反例 | 正確 |
|------|------|
| `{x}` | `{ticket_id}` |
| `{name}` | `{agent_name}` 或 `{file_path}` |
| `{content}` | `{context_bundle_text}` |

佔位符規則：
- 全小寫 + 底線分隔（snake_case）
- 名詞片語，描述「這個變數代表什麼」
- 避免縮寫（用 `file_path` 而非 `fp`）

#### 4.3 區塊邊界標記

大型 prompt 內部若有可重用區塊（例如「約束」「輸出格式」），用標記界定邊界方便剪貼和 diff。

```markdown
<!-- BEGIN: 通用代理人約束 -->
- 不修改 src/ 以外的檔案
- commit 訊息格式：`<type>({ticket_id}): <summary>`
<!-- END: 通用代理人約束 -->
```

---

### 5. 欄位設計（Field Design）× Prompt

**核心**：Context bundle 的每個欄位獨立角度，避免混淆。

Prompt 常見的欄位污染：把「做什麼」「為什麼」「如何驗收」「禁止事項」混在一段。AI 讀這種段落時必須反覆解析每句角色，容易漏掉約束。

**標準欄位骨架**（適用 ticket context bundle 或任何結構化派發 prompt）：

| 欄位 | 角度 | 內容類型 |
|------|------|---------|
| `任務` / `Task` | 動作 | 動詞 + 受詞，一句話 |
| `輸入` / `Inputs` | 材料 | 檔案 / 資料 / 前置條件 |
| `約束` / `Constraints` | 邊界 | 禁止項 + 必要項 |
| `驗收` / `Acceptance` | 終點判定 | 可勾選的條件 |
| `背景` / `Context` | 理由（可選） | 為什麼選此方案 |
| `參考` / `References` | 延伸資料 | 相關文件路徑 |

每個欄位**只**寫該角度的內容，禁止跨欄位混合。

**反例**：

```
任務：重寫快取層，不要使用 memoization，因為 key 設計有問題，完成後要跑 npm test。
```

（動作 + 約束 + 理由 + 驗收全擠在一行）

**正確**：

```
任務：重寫 BookRepository.getAll() 的快取層。
約束：不使用現有 memoization 機制。
背景：memoization 的 key 設計失效，profile 確認大量重複計算。
驗收：npm test 通過；profile 顯示 getAll() 呼叫量下降 > 50%。
```

---

## Token 節省策略

Prompt 的每個 token 都是成本。以下策略在**不傷害意圖清晰度**的前提下節省 token。

### 策略 1：用符號取代連接詞

**前**：

```
如果使用者已經登入並且擁有管理員權限，那麼允許存取，否則回傳 403 錯誤。
```

**後**：

```
已登入 AND 管理員 → 允許存取；否則 → 403。
```

**節省**：約 40% token。符號（`AND`、`→`、`;`）是 AI 可無歧義解讀的通用邏輯標記。

---

### 策略 2：表格取代重複句型

**前**：

```
當輸入是 JSON 時，回傳 JSON；當輸入是 YAML 時，回傳 YAML；
當輸入是 CSV 時，回傳 CSV；當輸入格式無法辨識時，回傳錯誤訊息。
```

**後**：

```
| 輸入格式 | 輸出 |
|---------|------|
| JSON | JSON |
| YAML | YAML |
| CSV | CSV |
| 未知 | 錯誤訊息 |
```

**節省**：約 35% token。表格消除重複的句型骨架（「當 X 時，回傳 Y」），AI 解析更快。

---

### 策略 3：引用路徑取代完整內容貼入

**前**：

```
根據以下規則處理：
（貼入 500 行規則文件全文）
```

**後**：

```
規則：docs/quality-baseline.md（請閱讀後套用）
```

**節省**：依文件大小，通常 > 90% token。前提是 AI 能存取該路徑（檔案必須存在於執行環境）。

**適用判斷**：

| 場景 | 應貼內容？ |
|------|-----------|
| 規則文件已存在於專案 | 否，引用路徑 |
| 只用文件中一小段 | 否，精確引用章節（`file.md#section`） |
| 臨時性規則，不存在於檔案 | 是，需貼入 |
| AI 無法存取該路徑（跨 session / 跨環境） | 是，需貼入 |

---

### 策略 4：刪除客套與鋪陳

**前**：

```
您好，我希望您能幫我處理一個問題。最近我們在開發一個新功能，
遇到了一些挑戰。我想請您幫我看看下列程式碼有什麼問題。謝謝！
```

**後**：

```
任務：找出下列程式碼的問題。
```

**節省**：約 70% token。AI 不需要客套語境——直接給任務比「禮貌請求」更有效。

---

### 策略 5：用預設約定取代顯式枚舉

**前**：

```
輸出格式：請用 Markdown 格式，標題使用 # 開頭，列表使用 - 開頭，
程式碼使用三個反引號包起來，表格使用 | 分隔。
```

**後**：

```
輸出格式：Markdown。
```

**節省**：約 80% token。Markdown 的語法細節是通用知識，不需要重新定義。

**適用原則**：若約定是通用知識（JSON、Markdown、YAML、常見技術術語），直接用名稱；若是專案特定約定，必須顯式說明。

---

## 結構化標記範例

### 範例 A：Agent Prompt（派發代理人）

完整 agent prompt 骨架：

```markdown
Ticket: {ticket_id}
任務: {short_task_description}
Ticket 路徑: {ticket_file_path}

請 Read Ticket 取得完整 Context Bundle 和驗收條件（位於 Problem Analysis section）。

## 輸入
- 目標檔案：{target_files}
- 依賴 ticket：{dependency_ticket_ids}

## 約束
- 不修改 .claude/ 以外的 rules/ 目錄
- 保留既有測試不動
- commit 訊息格式：`<type>({ticket_id}): <summary>`

## 執行步驟
1. `ticket track claim {ticket_id}`
2. 依 Context Bundle 執行實作
3. `ticket track append-log {ticket_id} --section "Solution" "..."`
4. `ticket track complete {ticket_id}`

## 驗收
- [ ] {acceptance_1}
- [ ] {acceptance_2}

## 一行摘要回報
格式：「{file_name}:{lines}行 {metric_1}:{N} {metric_2}:{N} 狀態:{status}」
```

**設計要點**：

| 區塊 | 功能 | 可搜尋性 |
|------|------|---------|
| `Ticket: {id}` | 穩定關鍵字，grep 能找到所有派發 prompt | 高 |
| `## 輸入` / `## 約束` / `## 執行步驟` / `## 驗收` | 標準化章節，AI 快速定位 | 高 |
| 變數佔位符 `{ticket_id}` 等 | snake_case 自說明 | 高 |
| 一行摘要回報格式 | 統一回報格式，PM 可 grep 聚合 | 高 |

---

### 範例 B：Ticket Context Bundle

Ticket YAML frontmatter 的 Problem Analysis 區塊作為 context bundle：

```markdown
## Problem Analysis

### Context Bundle

**執行步驟**:
1. `ticket track claim {ticket_id}`
2. Read {dependency_ticket_solution_path} 取得 {needed_info}
3. 撰寫 `{target_file_path}`
4. {integration_step}
5. 可攜性自檢後 `ticket track complete`

**關鍵參考**:
- {reference_1_description}: `{reference_1_path}`
- {reference_2_description}: `{reference_2_path}`

**約束**:
- {constraint_1}
- {constraint_2}
- 一行摘要回報：「{field_1}:{X} {field_2}:{N} 狀態:{status}」

### 問題根因

{root_cause_description}

### 影響範圍

{impact_scope}

### 相關 Error Pattern

{error_pattern_reference_or_none}
```

**設計要點**：

| 欄位 | 角度 | 避免混淆規則 |
|------|------|------------|
| 執行步驟 | How | 具體命令，不寫理由 |
| 關鍵參考 | Where | 檔案路徑 + 用途，不貼內容 |
| 約束 | Must not / Must | 可驗證的邊界條件 |
| 問題根因 | Why | 因果陳述，不寫解法 |
| 影響範圍 | What | 檔案 / 模組清單 |

**Context Bundle 的 DRY 原則**：YAML frontmatter 的 `what` / `why` / `how` 已分角度填寫，Context Bundle 不重複這些欄位的內容，只補「執行細節」與「關鍵參考」。

---

### 範例 C：小型內聯 Prompt（對話中）

適用於對話中快速派發單一任務：

```markdown
任務：檢查 {file} 是否有 {pattern}。
輸出：匹配行數列表（檔案:行號）。
若無匹配：回報「無匹配」。
```

**設計要點**：不需要完整章節，但仍保留「任務—輸出—邊界」三層訊號。

---

## 自檢清單

撰寫 prompt 完成後，逐項檢查：

### 原子化
- [ ] Prompt 目標可用單一動詞 + 單一受詞描述
- [ ] 無多個不相關任務混合

### 索引建立
- [ ] 有結構化標記（章節 / 表格 / 列表）
- [ ] 大型 prompt 有「任務 / 輸入 / 約束 / 輸出 / 驗收」骨架

### 意圖顯性
- [ ] 第一句即表達任務目標
- [ ] 明確指定輸出格式
- [ ] 不直觀的約束有附理由

### 可查詢性
- [ ] 有穩定關鍵字供 grep（ticket ID / 章節名 / 工具名）
- [ ] 變數佔位符為 snake_case 且自說明
- [ ] 可重用區塊有邊界標記（如適用）

### 欄位設計
- [ ] 每個欄位只寫該角度內容
- [ ] 無「動作 + 約束 + 理由 + 驗收」擠在一起
- [ ] Context Bundle 不重複 YAML frontmatter 已有欄位

### Token 節省
- [ ] 無多餘客套與鋪陳
- [ ] 重複句型已用表格取代
- [ ] 規則以路徑引用取代全文貼入（如適用）
- [ ] 邏輯關係用符號（`AND` / `→` / `;`）取代連接詞（如適用）
- [ ] 通用知識（Markdown / JSON）用名稱指定，不枚舉語法

---

## 反模式速查

| 反模式 | 症狀 | 正確做法 |
|-------|------|---------|
| 多任務混合 prompt | 「幫我做 A 和 B 和 C」 | 拆為獨立 prompt |
| 意圖埋在後段 | 前三段背景鋪陳，任務在第四段 | 第一句即任務 |
| 無輸出格式 | 「分析一下」 | 指定結構（表格 / 列表 / JSON） |
| 無理由禁令 | 「不要用 X」無理由 | 補「因為 Y」 |
| 模糊佔位符 | `{x}`、`{var}` | snake_case 自說明名 |
| 客套語氣 | 「您好，希望您能幫我...」 | 直接下指令 |
| 重複句型 | 「當 X 時 Y，當 X2 時 Y2...」 | 表格 |
| 全文貼入規則 | 把 500 行規則複製進 prompt | 引用路徑 |
| 欄位混合 | 任務 + 約束 + 驗收擠一行 | 分欄位列出 |
| 無結構化標記 | 純散文 | 章節 / 列表 / 表格 |

---

## 延伸閱讀

- Anthropic 官方 Prompt Engineering 文件（platform.claude.com）
- Zettelkasten 原子化原則（本 skill `writing-documents.md` 的原子化章節）
- 結構化 output（JSON Schema / XML tags）在 AI 工具呼叫的應用
