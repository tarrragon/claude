# 代理人範本 (Agent Template)

本文件為建立新代理人的標準範本，確保所有代理人具有一致的結構和完整的資訊。

---

## 範本使用說明

1. 複製「完整範本」部分到新檔案
2. 將 `{placeholder}` 替換為實際內容
3. 根據代理人類型選擇適當的章節
4. 刪除不適用的章節
5. 確保通過「範本檢查清單」

---

## 完整範本

```markdown
---
name: {agent-name-kebab-case}
description: {一句話描述核心職責和觸發條件，50-100 字}
tools: {工具列表，逗號分隔}
color: {顏色名稱}
model: {haiku|sonnet|opus|claude-opus-4-6[1m]|inherit}
permissionMode: {bypassPermissions|acceptEdits|auto|dontAsk|plan}
# 以下欄位選填，依代理人需求決定是否保留
# effort: {low|medium|high}         # 預設 low；複雜架構決策用 medium/high
# maxTurns: {整數}                   # 安全網，防止輪數截斷；建議值：機械任務 20-30、實作 50-80、分析 30-40
# background: {true|false}          # true = 派發後立刻釋放主線程；長任務建議設 true
# initialPrompt: {啟動時自動提交的首輪文字}  # 例："Read .claude/agents/AGENT_PRELOAD.md 後開始執行"
# disallowedTools: {禁用工具列表}    # 唯讀/安全型代理人用：disallowedTools: Edit, Write
# hooks:
#   Stop:
#     - matcher: ""
#       hooks:
#         - type: command
#           command: {停止時執行的命令}
---

# {代理人中文名稱} ({Agent English Name})

You are a {role description in English}. Your core mission is {mission statement}.

**定位**：{一句話中文定位}

---

## 觸發條件

{代理人名稱} 在以下情況下**應該被觸發**：

| 觸發情境 | 說明 | 強制性 |
|---------|------|--------|
| {情境1} | {說明} | 強制/建議 |
| {情境2} | {說明} | 強制/建議 |
| {情境3} | {說明} | 強制/建議 |

---

## 適用情境

<!-- 規範強制段（精確標題，勿改名）：對齊 .claude/references/agent-definition-standard-details.md 區塊 3。AgentDefCheck 驗證式 grep -E "^## (允許產出|禁止行為|適用情境)" 預期命中 3。 -->

明列何時應派發此代理人，必含三要素：

| 必含元素 | 內容 |
|---------|------|
| TDD Phase 標註 | Phase 0/1/2/3a/3b/4 之一或多個；獨立任務類型標 N/A |
| 觸發條件 | {任務特徵，例「測試紅燈時」「需要多視角分析時」} |
| 排除情境 | {何時不該派發此代理人，建議改派發誰} |

---

## 核心職責

### 1. {職責1名稱}

**目標**：{目標描述}

**執行步驟**：
1. {步驟1}
2. {步驟2}
3. {步驟3}

### 2. {職責2名稱}

**目標**：{目標描述}

**執行步驟**：
1. {步驟1}
2. {步驟2}
3. {步驟3}

### 3. {職責3名稱}（如適用）

**目標**：{目標描述}

---

## 允許產出

<!-- 規範強制段（精確標題，勿改名）：對齊 .claude/references/agent-definition-standard-details.md 區塊 1。 -->

明列此代理人可產生的產出類型，必含三要素：

| 必含元素 | 內容 |
|---------|------|
| 檔案類別 | {例 `.py` / `.md` / `tests/` 下測試檔} |
| 操作類型 | {例 Edit / Write / 執行測試 / 產出分析報告} |
| 路徑範圍 | {與 frontmatter 的 tools / permissionMode 對應} |

> 實作類代理人須在此段或通用責任段引用「Ticket body 填寫責任」與「Ticket 完成（收尾）責任」（見 `.claude/references/agent-definition-standard-details.md`「執行責任」兩章）。

---

## 禁止行為

<!-- 規範強制段（精確標題，勿改名）：對齊 .claude/references/agent-definition-standard-details.md 區塊 2。 -->

明列此代理人不可做的事，必含下列各類元素：

| 必含元素 | 內容 |
|---------|------|
| 禁止檔案類別 | {例「禁止修改 `src/` 下產品程式碼」} |
| 禁止操作類型 | {例「禁止 git commit」「禁止跨 ticket 範圍編輯程式碼」} |
| 禁止職責越界 | {例「禁止替代 PM 進行派發決策」} |
| 禁止跨 ticket 物件操作 | 禁止對非派發範圍的 ticket 執行 `ticket track close` / `set-status` / 編輯他人 ticket md（即使發現重複或衝突，應透過審查報告 / Exit Status / NeedsContext 上報 PM）。即使 frontmatter 無 Edit/Write 工具，此純文字禁令仍必含——代理人仍可透過 Bash 執行 `ticket track close`。 |

### 絕對禁止

1. **禁止 {行為1}**：{說明}
2. **禁止 {行為2}**：{說明}
3. **禁止 {行為3}**：{說明}

---

## 輸出格式

### {報告/輸出名稱} 模板

```markdown
# {報告標題}

## 摘要
- **{欄位1}**: [{值}]
- **{欄位2}**: [{值}]

## {章節1}
[內容]

## {章節2}
[內容]

## 建議
[建議內容]
```

---

## 與其他代理人的邊界

| 代理人 | {本代理人} 負責 | 其他代理人負責 |
|--------|----------------|---------------|
| {代理人1} | {本代理人職責} | {其他代理人職責} |
| {代理人2} | {本代理人職責} | {其他代理人職責} |
| {代理人3} | {本代理人職責} | {其他代理人職責} |

### 明確邊界

| 負責 | 不負責 |
|------|-------|
| {職責1} | {排除1} |
| {職責2} | {排除2} |
| {職責3} | {排除3} |

---

## 升級機制

### 升級觸發條件

- {條件1}
- {條件2}
- {條件3}

### 升級流程

1. 記錄當前進度到輸出文件
2. 標記為「需要升級」
3. 向 rosemary-project-manager 提供：
   - 已完成的工作
   - 遇到的問題
   - 需要的協助

---

## 工作流程整合

### 在整體流程中的位置

```
{前一步驟}
    |
    v
[{本代理人}] <-- 你的位置
    |
    +-- {結果1} --> {下一步1}
    +-- {結果2} --> {下一步2}
```

### 與相關代理人的協作

{描述與其他代理人的協作方式}

---

## 成功指標

### 品質指標
- {指標1} > {目標值}
- {指標2} > {目標值}

### 流程遵循
- {遵循項目1}
- {遵循項目2}

---

**Last Updated**: {日期}
**Version**: 1.0.0
**Specialization**: {專業領域}
```

---

## 必要章節說明

### Frontmatter（必要欄位 + 選填欄位）

**必填欄位**：

| 欄位 | 說明 | 範例 |
|------|------|------|
| `name` | 代理人識別名稱（kebab-case） | `incident-responder` |
| `description` | 核心職責描述（50-100 字） | 見下方說明 |
| `tools` | 允許使用的工具 | `Read, Grep, Glob, LS, Bash` |
| `color` | 代理人顏色標記 | `orange`, `gold`, `green` |
| `model` | 使用的模型 | `haiku`, `sonnet`, `opus` |
| `permissionMode` | 代理人含 Edit/Write 時必填 | `bypassPermissions`（實作類）、`acceptEdits`（cwd 限定） |

**選填欄位**（依代理人需求決定）：

| 欄位 | 說明 | 建議使用時機 |
|------|------|------------|
| `effort` | 推理深度（low/medium/high） | 預設 low；複雜架構決策或系統設計用 medium/high |
| `maxTurns` | 最大工具呼叫輪數（整數） | 機械性任務 20-30；複雜實作 50-80；分析型 30-40 |
| `background` | 強制背景執行（true/false） | 長時間任務（> 30 秒）、並行派發時設 true |
| `initialPrompt` | 啟動時自動提交的首輪文字 | 代理人有固定前置讀取需求時（如必讀規格文件） |
| `disallowedTools` | 明確禁用工具（優先於 tools 清單） | 唯讀代理人（禁 Edit/Write）、安全審查類（防意外寫入） |
| `hooks` | 代理人生命週期 Hook | 需要自動觸發 complete ticket、寫 worklog 等 Stop 動作時 |

### Description 撰寫指南

**格式**：`{角色名稱}。{核心職責}。{觸發條件或特殊說明}。`

**範例**：
- `事件回應專家。測試失敗或問題發生時的第一線評估者，分析錯誤狀況和上下文，判斷是設計問題還是實作問題，開錯誤處理 Ticket，避免衝動決策。Skip-gate 核心解決方案。`
- `TDD 前置審查專家。在 TDD 開始前審查系統一致性、檢視/撰寫需求文件、防止重複造輪子、確保 ticket 與大系統設計一致。負責系統級審查，不負責單一功能設計。`

### 規範強制三區塊（必要，精確標題不可改名）

`.claude/agents/*.md` 主文必須含以下三個精確標題的 `##` 區塊，使 PM 派發前可查表確認職責邊界，並為 Hook 解析職責提供穩定錨點。權威來源 `.claude/references/agent-definition-standard-details.md` 區塊 1/2/3。

| 精確標題 | 必含元素 | 對應規範 |
|---------|---------|---------|
| `## 允許產出` | 檔案類別 / 操作類型 / 路徑範圍 | 區塊 1 |
| `## 禁止行為` | 禁止檔案類別 / 禁止操作類型 / 禁止職責越界 / 禁止跨 ticket 物件操作 | 區塊 2 |
| `## 適用情境` | TDD Phase 標註 / 觸發條件 / 排除情境 | 區塊 3 |

驗證式：`grep -E "^## (允許產出|禁止行為|適用情境)" .claude/agents/<agent>.md | wc -l`，預期輸出 `3`。

> 概念對應的 `## 核心職責` / `## 觸發條件` 為豐富補充段，不取代上述精確標題；W8-016 執法 hook 驗三區塊存在性，本範本確保內容到位。

### 觸發條件（補充）

`## 觸發條件` 為 `## 適用情境` 的豐富補充段，可包含：
- 強制觸發情境
- 建議觸發情境
- 觸發關鍵字（如適用）

### 核心職責（補充）

`## 核心職責` 為 `## 允許產出` 的豐富補充段，描述代理人的主要職責，每個職責包含：
- 目標說明
- 執行步驟或流程
- 產出物（如適用）

### 輸出格式（建議）

如果代理人需要產出特定格式的報告或文件，提供模板。

### 與其他代理人的邊界（必要）

明確定義職責邊界，避免職責重疊或遺漏。

### 升級機制（必要）

定義何時需要升級到 rosemary-project-manager，以及升級流程。

---

## 範本檢查清單

建立新代理人時，確保通過以下檢查：

### Frontmatter 檢查
- [ ] name 使用 kebab-case
- [ ] description 在 50-100 字之間
- [ ] tools 使用標準格式（非 allowed-tools）
- [ ] model 選擇適當（haiku/sonnet/opus/claude-opus-4-6[1m]）
- [ ] permissionMode 設定：代理人含 Edit/Write 時必填（建議 bypassPermissions）
- [ ] effort 已評估（預設 low 是否足夠；複雜任務考慮 medium/high）
- [ ] maxTurns 已評估（長任務或複雜任務是否需要設安全網）
- [ ] background 已評估（長時間任務是否需要設 true）
- [ ] disallowedTools 已評估（唯讀/安全類代理人是否需要明確禁用寫入工具）

### 內容檢查
- [ ] 有英文角色定義
- [ ] 有中文定位說明
- [ ] 規範強制三區塊精確標題齊全（`grep -E "^## (允許產出|禁止行為|適用情境)" <agent>.md | wc -l` 輸出 3）
- [ ] `## 允許產出` 含檔案類別 / 操作類型 / 路徑範圍
- [ ] `## 禁止行為` 含禁止跨 ticket 物件操作（即使無 Edit/Write 工具）
- [ ] `## 適用情境` 含 TDD Phase 標註 / 觸發條件 / 排除情境
- [ ] 觸發條件表格完整
- [ ] 核心職責有明確步驟
- [ ] 與其他代理人邊界明確

### 流程檢查
- [ ] 升級機制有定義
- [ ] 工作流程位置清楚
- [ ] 成功指標可量化

### 格式檢查
- [ ] 使用繁體中文
- [ ] 無 emoji
- [ ] 表格格式正確
- [ ] 程式碼區塊使用正確語法標記

---

## 代理人類型參考

### 系統級代理人
- incident-responder（事件回應）
- saffron-system-analyst（系統分析）
- star-anise-system-designer（系統設計）
- sumac-system-engineer（系統工程）
- sassafras-data-administrator（資料管理）

### TDD 階段代理人
- lavender-interface-designer（Phase 1）
- sage-test-architect（Phase 2）
- pepper-test-implementer（Phase 3a）
- parsley-flutter-developer（Phase 3b）
- cinnamon-refactor-owl（Phase 4）

### 專業任務代理人
- clove-security-reviewer（安全審查）
- basil-hook-architect（Hook 開發）
- thyme-documentation-integrator（文件整合）
- mint-format-specialist（格式化）
- ginger-performance-tuner（效能優化）

---

## 命名規範

### 代理人命名
- 使用香料/植物名稱 + 職責描述
- 範例：`saffron-system-analyst`, `basil-hook-architect`

### 檔案命名
- 使用與 name 相同的 kebab-case
- 範例：`saffron-system-analyst.md`

### 觸發條件規則
- 位置：代理人定義主文（`.claude/agents/{name}.md`）的「適用情境」區塊
- 說明：派發觸發條件併入單一代理人定義檔，不再使用獨立的派發規則目錄

---

## 關聯文件

建立新代理人時，**必須**同步建立以下文件：

| 文件 | 說明 | 位置 |
|------|------|------|
| 代理人定義 | 完整的代理人定義（含三區塊：允許產出/禁止行為/適用情境） | `.claude/agents/{name}.md` |
| CLAUDE.md | 更新代理人列表（如適用） | `CLAUDE.md` |
| 決策流程 | 更新派發規則（如適用） | `.claude/pm-rules/decision-tree.md` |

### 建立檢查

- [ ] `.claude/agents/{name}.md` 已建立（含三區塊：允許產出/禁止行為/適用情境）
- [ ] CLAUDE.md 代理人列表已更新（如適用）
- [ ] `.claude/pm-rules/decision-tree.md` 派發規則已更新（如適用）

---

**Last Updated**: 2026-05-13
**Version**: 1.2.0 — 新增 8 個 CC 2.1.x frontmatter 欄位（permissionMode/effort/maxTurns/background/initialPrompt/disallowedTools/hooks/memory），範本 frontmatter 補入選填欄位佔位符；Frontmatter 必要章節說明拆為「必填/選填」雙表；範本檢查清單補入新欄位檢查項目（0.18.0-W6-005）
**Version**: 1.1.0
