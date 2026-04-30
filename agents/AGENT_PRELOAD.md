# 代理人前置載入規範 (Agent Preload Standards)

本文件定義**所有代理人**在開始執行任務前**必須**遵守的核心規則。

> **重要**：本文件透過 `@` 引用機制被載入到每個代理人的上下文中。

---

## 強制規則

### 1. 語言規範（最高優先）

**所有輸出必須使用繁體中文 (zh-TW)**

#### 常見禁用詞彙（摘要）

| 禁用 | 正確 |
|------|------|
| 文檔 | 文件 |
| 數據 | 資料 |
| 代碼 | 程式碼 |

> 完整禁用詞彙清單見 `.claude/rules/core/language-constraints.md`

#### 技術術語保留英文

程式碼識別符、技術專有名詞（Flutter, Dart, TDD 等）、指令（`/ticket`）保留英文。

---

### 2. Ticket 操作規範

#### 2.1 讀取（必須用 CLI，禁止 Read 工具）

```bash
ticket track query 0.17.3-W1-001    # 查詢特定 Ticket
ticket track list                     # 列表
ticket track summary                  # 摘要
```

禁止 `Read(docs/work-logs/.../tickets/xxx.md)`。CLI 會解析 frontmatter 和驗證格式。

#### 2.2 進度更新（執行過程中必須更新）

代理人在執行任務過程中**必須**更新 Ticket 進度，讓 PM 查 Ticket 即可知道代理人進度。

```bash
# 更新 Problem Analysis（分析完成時）
ticket track append-log <id> --section "Problem Analysis" "分析內容"

# 更新 Solution（實作完成時）
ticket track append-log <id> --section "Solution" "實作內容"

# 更新 Test Results（測試完成時）
ticket track append-log <id> --section "Test Results" "測試結果"
```

> **注意**：`ticket` 是全域安裝的 CLI 工具，直接呼叫即可。**禁止** `(cd .claude/skills/ticket && uv run ...)`。

#### 2.3 更新時機

| 時機 | 更新什麼 | 範例 |
|------|---------|------|
| 分析完成 | Problem Analysis | 「根因是 X，影響 Y 個檔案」 |
| 實作完成 | Solution | 「新增方法 A、修改檔案 B」 |
| 測試完成 | Test Results | 「40/40 通過，無回歸」 |
| 遇到阻塞 | Problem Analysis | 「發現 X 問題，需 PM 決策」 |
| **任務完成（收尾）** | check-acceptance + complete | `ticket track check-acceptance --all <id>` 後 `ticket track complete <id>` |

#### 2.4 收尾責任：自律 complete（W17-033）

**Why**：歷史設計將 complete 視為 PM 專屬，導致 PM 每次需額外執行 check-acceptance + complete（W17-020、W17-016.3 實證）。**Consequence**：違反代理人自律主責原則，PM 處理 N 個 ticket 即多 N 次 tool call 浪費。**Action**：實作類 agent 在 commit + body 填寫完成後，主動執行：

```bash
# 1. 勾選所有 acceptance（agent 已逐項確認完成）
ticket track check-acceptance --all <ticket-id>

# 2. acceptance 全數通過時 complete
ticket track complete <ticket-id>
```

**例外情境**：

| 狀況 | 處理 |
|------|------|
| 部分 acceptance 未達成 | 在 NeedsContext 章節記錄缺口，**不 complete**，回報 PM |
| acceptance-gate-hook 阻擋 | 依 hook 訊息修補後重試（hook 是安全網，非懲罰） |
| ANA 類 ticket（純分析）由 PM 派發者 | PM 在 prompt 明確指示時才執行 |

> **安全網**：acceptance-gate-hook 在 complete 觸發前自動驗證，無論由 agent 或 PM 執行，故 agent 自律 complete 無安全風險。

#### 2.5 為什麼代理人必須更新 Ticket

PM 和代理人透過 **Ticket** 溝通，不直接溝通。PM 查 Ticket 進度而非代理人 output。只有異常時才用 SendMessage 直接聯繫。這降低 PM-代理人的依賴，讓 PM 可以同時管理多個任務線。

> 完整規範：@.claude/skills/ticket/SKILL.md

---

### 3. 文件格式規範

- 所有交接文件禁止使用 emoji
- 使用純文字狀態標記（`[x]` / `[ ]`）
- 優先級使用「P0/P1/P2」或「高/中/低」

> 完整規範：@.claude/rules/core/document-format-rules.md

---

### 4. 5W1H 回應格式

代理人的報告和輸出應遵循結構化格式，包含：
- Who（執行者）
- What（任務內容）
- When（觸發時機）
- Where（執行位置）
- Why（執行理由）
- How（實作方式）

---

### 5. 實作代理人查詢範圍限制（Phase 3b 強制）

> **來源**：PC-047 — PM prompt 誘導代理人大量讀取，回合耗盡未進入寫入。

#### 核心原則

**實作基於測試，不基於探索。** 代理人收到任務後，查詢範圍嚴格限縮在以下四類：

| 允許查詢 | 目的 | 範例 |
|---------|------|------|
| 測試程式碼 | 了解要通過什麼 | Read 測試檔案中的 TC 案例 |
| 目標 model/DTO | 了解資料結構 | Read 要修改的 class/struct 定義 |
| Domain 邏輯 | 了解業務規則 | Read 相關 domain service |
| 介面定義 | 了解呼叫契約 | Read interface/abstract class |

#### 禁止查詢

| 禁止 | 原因 | 正確做法 |
|------|------|---------|
| 「參考 X 檔案的模式」式的大範圍讀取 | 這是探索，不是實作 | PM 應在 Context Bundle 中 inline 必要資訊 |
| grep 搜尋「其他地方怎麼做」 | 消耗 tool call 預算 | PM 應預先提取模式並寫入 Ticket |
| 讀取完整設計文件（Phase 1/2/3a） | context 浪費 | PM 已提取摘要到 Context Bundle |
| 讀取與任務無直接關係的程式碼 | 超出實作範圍 | 聚焦測試要求的最小修改集 |

#### 資訊不足時的處理

如果 Ticket 的 Context Bundle 不足以完成實作（缺少 API 簽名、常數定義、介面資訊等），代理人**不應自行大量查詢**，而應：

1. 在 Ticket 記錄缺少什麼：`ticket track append-log <id> "資訊不足：缺少 X 介面定義和 Y 常數"`
2. 回報 PM 補充資訊後再繼續

**判斷標準**：如果實作需要超過 5 次 Read/Grep 才能開始寫入，代表 Context Bundle 不完整，應停止查詢並回報。

---

### 6. Git 操作限制（強制）

> 代理人禁止修改主倉庫的 git 狀態。

| 操作 | 規則 | 原因 |
|------|------|------|
| `git checkout` | 禁止 | 修改 .git/HEAD，污染主線程工作目錄 |
| `git branch` | 禁止 | 在主倉庫建立分支 |
| `git switch` | 禁止 | 同 checkout |
| `git commit`（Phase 3b+） | 禁止 | PM 負責提交（PC-024） |
| `git commit`（Phase 1-3a） | 允許 | 代理人可自行提交，但禁止 push |
| `git push` | 禁止 | PM 負責推送 |

如需在獨立分支工作，PM 會使用 `Agent(isolation: "worktree")` 派發，代理人無需自行建立分支。

---

### 7. 工具選擇規則（MCP 寫入工具優先序）

> **Why**：LLM 傾向選擇「單步高精度」工具（如 serena MCP 寫入工具），即使一般文字修改用 Edit / Write 即可完成。此偏誤（PC-088）加上 MCP 寫入工具在背景派發環境常不在 allow list，會導致代理人被拒後錯誤泛化為「所有寫入工具都被拒」而 early stop（W17-088 根因）。

> **Consequence**：未遵循優先序時，代理人在 MCP 工具被拒後停止工作，未嘗試可行的 Edit / Write，造成任務失敗且 PM 無法察覺根本可執行。

> **Action**：依下表選工具；MCP 寫入工具被拒時必須嘗試 Edit / Write 降級，不可自行宣告任務失敗。

#### 工具選擇優先序

| 任務類型 | 優先工具 | 禁止/不建議 |
|---------|---------|------------|
| 一般 Markdown / 文字檔修改 | **Edit**（首選）/ Write | 不應先選 MCP 寫入工具 |
| 新建檔案 | **Write** | — |
| 符號級重構（跨檔 rename、函式移動） | mcp__serena__rename_symbol 等 | 非符號重構不用 serena |
| 讀取 / 查找特定符號 | mcp__serena__find_symbol | — |
| 背景派發環境的 .md 檔修改 | **Edit 唯一首選** | mcp__serena__replace_content / replace_symbol_body 等寫入工具在 subagent 環境常不在 allow list |

#### Fallback 規則（MCP 工具被拒時）

1. MCP 寫入工具（`mcp__serena__replace_content`、`replace_symbol_body` 等）被拒時：
   - **必須嘗試 Edit 工具降級**完成同一修改
   - Edit 成功後繼續任務，不需回報 MCP 被拒
   - Edit 也被拒時，才在 Ticket Problem Analysis 記錄並回報 PM
2. **禁止 self-imposed early stop**：看到 MCP 工具一個被拒，不可推論「Edit 也會被拒」，必須實際嘗試
3. 判別準則：`mcp__serena__*` 寫入工具屬 MCP 層限制；Edit / Write 屬 Claude Code 內建工具層，兩者限制機制完全不同

> **來源**：PC-088（LLM 工具選擇偏誤）；W17-088（thyme early stop 失敗案例：serena 被拒 → 錯誤泛化 → Edit 未嘗試）

---

## 執行檢查清單

代理人在開始任務前，自我確認：

- [ ] 所有輸出使用繁體中文
- [ ] 無禁用詞彙（文檔→文件、數據→資料...）
- [ ] 讀取 Ticket 使用 `ticket track query`
- [ ] 執行過程中更新 Ticket 進度（`append-log`）
- [ ] 文件無 emoji
- [ ] 未執行 git checkout/branch/switch/commit
- [ ] （Phase 3b）查詢限於測試碼/model/domain/介面，無大範圍探索
- [ ] （Phase 3b）若資訊不足，已回報 PM 而非自行大量查詢
- [ ] 報告結構清晰（5W1H）
- [ ] .md 修改使用 Edit / Write，非 mcp__serena__replace_content 等 MCP 寫入工具（規則 7）
- [ ] MCP 工具被拒時已嘗試 Edit 降級，未 self-imposed early stop（規則 7 Fallback）
- [ ] **任務完成後執行 `ticket track check-acceptance --all <id>` + `ticket track complete <id>`（規則 2.4）**

---

## 違規處理

| 違規類型 | 處理方式 |
|---------|---------|
| 使用禁用詞彙 | 立即修正輸出 |
| 直接 Read Ticket 檔案 | 改用 `ticket` 指令重新讀取 |
| 完成任務但未更新 Ticket 進度 | 補上 append-log 再回報完成 |
| 使用簡體中文 | 重新輸出繁體中文版本 |

---

## 角色與規則適用性

> **你是執行者（Executor），不是 PM。** `.claude/pm-rules/skip-gate.md` 和 `.claude/pm-rules/decision-tree.md` 中「主線程禁止」類限制僅適用於 rosemary-project-manager（主線程），不約束被派發的 subagent 開發代理人。你的職責是完成被指派的任務。

---

**Last Updated**: 2026-04-30
**Version**: 1.7.0 - 新增規則 2.4「收尾責任：自律 complete」+ 2.3 表格「任務完成」列 + 檢查清單 complete 項：實作類 agent commit/body 填寫完成後主動執行 check-acceptance --all + complete，acceptance-gate-hook 為安全網（W17-033 / 源 W17-022）
**Version**: 1.6.0 - 新增規則 7「工具選擇規則（MCP 寫入工具優先序）」：一般 .md 修改用 Edit/Write，serena MCP 限於符號級重構；MCP 被拒時必須 fallback Edit，禁 self-imposed early stop（PC-088 / W17-088）
**Purpose**: 確保所有代理人遵守核心規則
