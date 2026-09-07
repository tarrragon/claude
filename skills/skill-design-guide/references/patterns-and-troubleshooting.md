# Skill Patterns, Testing & Troubleshooting

> 何時讀：決定工作流該給多少自由度、要不要設預設值、設計多步驟或條件式工作流、需要進階範本模式、要規劃 skill 的測試方法、或 skill 行為不如預期（未觸發／過度觸發／指令未被遵循／context 過大）時。**亦由此進入**——`SKILL.md`〈發布前檢查清單〉的觸發測試組指向本檔的〈測試方法〉與〈迭代回饋指引〉；`SKILL.md`〈核心心法〉把要決定表達方式的讀者送到本檔前兩節。
>
> 同目錄：frontmatter 與 description 在 `frontmatter-and-description.md`，正文寫法在 `writing-the-body.md`，新建流程與三類 bundled resource 的分工在 `creating-and-adopting-skills.md`，拆分程序在 `splitting-an-existing-skill.md`，設計哲學在 `seeing-like-an-agent.md`；〈核心心法〉的其餘兩則與〈發布前檢查清單〉留在 `SKILL.md`。
>
> 溯源：本檔為 skill-design-guide 的 reference，v1.6.0 拆分時補上檔頭三段式（此前缺）；〈Degrees of Freedom〉〈Opinionated Defaults〉於 v1.9.0 自 `SKILL.md` 搬入。內容來源為 Anthropic 官方 Skills 文件（platform.claude.com）與《The Complete Guide to Building Skills for Claude》。

本檔章節：〈Degrees of Freedom — 自由度匹配脆弱性〉〈Opinionated Defaults — 預設路徑引導正確做法〉〈Skill 設計模式〉〈選擇方法：Problem-first vs Tool-first〉〈測試方法〉〈迭代回饋指引〉〈常見問題排除〉。

---

## Degrees of Freedom — 自由度匹配脆弱性

| 自由度 | 任務特徵 | 表達方式 | 範例 |
|--------|---------|---------|------|
| 高 | 多種解法皆可、依情境決定 | 文字指引 + 啟發式 | 「分析使用者需求並建議方向」 |
| 中 | 有偏好模式、容許變化 | 虛擬碼 / 帶參數腳本 | 「依照範本但可調整章節順序」 |
| 低 | 操作脆弱、一致性關鍵 | 具體腳本、固定步驟 | 「執行 `scripts/validate.py`，不可改寫」 |

**判準是兩問，依序問**：

1. **產物有機械消費者，或動作不可逆嗎？** 機械消費者指腳本 parse、hook 檢查、另一支 skill 的輸入欄位；不可逆指寫檔、commit、刪除。有 → 低自由度。
2. 都沒有的話，**多次執行的產物要互相比對或彙總嗎？** 要 → 中自由度（給骨架、明示可調）；不要 → 高自由度。

**「壞掉」是消費端拿不到它要的東西，不是產物長得不一樣。** 兩者必須分開，三級表才有三格：形態不一致只有在存在消費者時才構成損害；把不一致本身算成壞，每個有偏好形態的任務都會落到低自由度，中與高一起併入低，三級表塌成一格。第一問可外部驗證——指得出那個消費者是誰（哪支腳本、哪個 hook、哪一欄）才算「有」，指不出就是沒有。

**同一個任務寫成三種自由度**（任務：讓 skill 產出一份審查報告）：

```markdown
高：整理審查發現，依嚴重度分組，附位置與建議修法。

中：用下列骨架，欄位可增減：
    | 位置 | 問題 | 嚴重度 | 建議修法 |
    嚴重度用「嚴重必修／建議可改」兩級；需要第三級時說明理由。

低：逐項填滿下表，欄位不可增減、不可留空：
    | 位置 | 問題 | 嚴重度 | 全部命中位置 | 建議修法 |
    嚴重度只能填「嚴重必修」或「建議可改」。
    「全部命中位置」不可寫「多處」，須逐一列出或註明抽樣方式。
```

差別不在字數，在**偏離的空間**：高只給目標，中給骨架並明示可調，低把每個欄位的合法值也定死。

**把〈同一個任務寫成三種自由度〉的三段套進〈判準是兩問，依序問〉**：低那一段的「全部命中位置」有消費者——`splitting-an-existing-skill.md`〈收尾〉要拿它逐項對照實例數與已修數，欄位缺了就核不了——故低正確；中那一段的嚴重度兩級是為了讓多份報告可彙總，指不出機械消費者，故中；高那一段的產出只給人讀，故高。舊判準對這三段問「欄位少一格會壞掉嗎」，三段都答不出來，因為「壞掉」沒有定義。

選錯的代價不對稱：該低而給高，消費端拿不到必要欄位；該高而給低，執行者會在不適用的情境硬填。

## Opinionated Defaults — 預設路徑引導正確做法

**預設假設**：使用者（尤其 AI agent）走預設路徑。如果預設路徑不引導正確做法，文件規範再完整也無效。

| 設計問題 | 判準 | 行動 |
|---------|------|------|
| Skill 工作流有分支選擇？ | 有「多數情況下正確」的路徑嗎？ | 有 → 預設走該路徑，允許覆蓋 |
| 需要使用者提供參數？ | 有合理預設值嗎？ | 有 → 設預設值，使用者可覆蓋 |
| 前置條件可能不滿足？ | 能自動修正嗎？ | 能 → 自動修正 + 通知；不能 → 明確報錯，不靜默跳過 |
| 需寫「請先做 X」提醒？ | 能改成自動檢查？ | 能 → 改 Hook / pre-flight check；每個「請先」都是設計改善信號 |

**Why**：AI agent 沒有跨 session 記憶，工具即時引導是唯一可靠防線。文件說的和工具做的不一致時，工具會贏。

## Skill 設計模式

### Pattern 1: Sequential Workflow Orchestration

**適用場景**：需要按特定順序執行的多步驟流程。

```markdown
## Workflow: Onboard New Customer

### Step 1: Create Account
Call MCP tool: `create_customer`
Parameters: name, email, company

### Step 2: Setup Payment
Call MCP tool: `setup_payment_method`
Wait for: payment method verification

### Step 3: Create Subscription
Call MCP tool: `create_subscription`
Parameters: plan_id, customer_id (from Step 1)

### Step 4: Send Welcome Email
Call MCP tool: `send_email`
Template: welcome_email_template
```

**關鍵技巧**：明確步驟順序、步驟間依賴關係、每個階段驗證、失敗時的回滾指令。

---

### Pattern 2: Multi-MCP Coordination

**適用場景**：工作流跨多個服務。

```markdown
### Phase 1: Design Export (Figma MCP)
1. Export design assets from Figma
2. Generate design specifications
3. Create asset manifest

### Phase 2: Asset Storage (Drive MCP)
1. Create project folder in Drive
2. Upload all assets
3. Generate shareable links

### Phase 3: Task Creation (Linear MCP)
1. Create development tasks
2. Attach asset links to tasks
3. Assign to engineering team
```

**關鍵技巧**：清楚的階段分隔、MCP 之間的資料傳遞、進入下一階段前驗證、集中式錯誤處理。

---

### Pattern 3: Iterative Refinement

**適用場景**：輸出品質透過迭代改善。

```markdown
## Iterative Report Creation

### Initial Draft
1. Fetch data via MCP
2. Generate first draft report
3. Save to temporary file

### Quality Check
1. Run validation script: `scripts/check_report.py`
2. Identify issues:
   - Missing sections
   - Inconsistent formatting
   - Data validation errors

### Refinement Loop
1. Address each identified issue
2. Regenerate affected sections
3. Re-validate
4. Repeat until quality threshold met

### Finalization
1. Apply final formatting
2. Generate summary
3. Save final version
```

**關鍵技巧**：明確的品質標準、迭代改善流程、驗證腳本、知道何時停止迭代。

---

### Pattern 4: Context-Aware Tool Selection

**適用場景**：相同目標，依上下文選擇不同工具。

```markdown
## Smart File Storage

### Decision Tree
1. Check file type and size
2. Determine best storage location:
   - Large files (>10MB): Use cloud storage MCP
   - Collaborative docs: Use Notion/Docs MCP
   - Code files: Use GitHub MCP
   - Temporary files: Use local storage

### Execute Storage
Based on decision:
- Call appropriate MCP tool
- Apply service-specific metadata
- Generate access link

### Provide Context to User
Explain why that storage was chosen
```

**關鍵技巧**：清楚的決策標準、備選方案、對選擇的透明解釋。

---

### Pattern 5: Domain-Specific Intelligence

**適用場景**：Skill 提供超越工具存取的專業知識。

```markdown
## Payment Processing with Compliance

### Before Processing (Compliance Check)
1. Fetch transaction details via MCP
2. Apply compliance rules:
   - Check sanctions lists
   - Verify jurisdiction allowances
   - Assess risk level
3. Document compliance decision

### Processing
IF compliance passed:
    - Call payment processing MCP tool
    - Apply appropriate fraud checks
    - Process transaction
ELSE:
    - Flag for review
    - Create compliance case

### Audit Trail
- Log all compliance checks
- Record processing decisions
- Generate audit report
```

**關鍵技巧**：嵌入領域專業、先合規後執行、完整文件記錄、清楚治理機制。

---

## 選擇方法：Problem-first vs Tool-first

| 方法 | 說明 | 適用場景 |
|------|------|---------|
| **Problem-first** | 使用者描述目標，Skill 編排對應的工具呼叫 | "我需要建立專案工作區" |
| **Tool-first** | 使用者有工具存取，Skill 提供最佳工作流指引 | "我已連接 Notion MCP" |

多數 Skill 偏向其中一個方向。了解你的使用案例有助選擇正確的 Pattern。

---

## 測試方法

### 測試層級

**不涵蓋**：本節與下方〈常見問題排除〉的第一張表（上傳錯誤）預設 skill 經**上傳與打包**分發。走 git 同步的專案（本庫即是，見 `creating-and-adopting-skills.md`〈Step 5：打包〉）沒有上傳這個環節，因此三層測試中 Manual 與 Programmatic 兩層無管道、上傳錯誤那張表的三個訊息永遠不會出現。這類專案可執行的只有 Scripted 一層，而本檔未給它程序。

| 層級 | 方法 | 說明 | 走 git 同步的專案 |
|------|------|------|-----------------|
| Manual | 在 Claude.ai 直接執行 | 快速迭代，無需設定 | 無管道 |
| Scripted | 在 Claude Code 自動化測試案例 | 跨版本的可重複驗證 | **唯一可用，本檔未給程序** |
| Programmatic | 透過 Skills API 建立評估套件 | 對定義的測試集系統化執行 | 無管道 |

### Pro Tip

先對單一困難任務迭代直到 Claude 成功，再將成功方法提取為 Skill。這比廣泛測試提供更快的訊號。

### 觸發測試

確保 Skill 在正確時機載入。

```
Should trigger:
- "Help me set up a new ProjectHub workspace"
- "I need to create a project in ProjectHub"
- "Initialize a ProjectHub project for Q4 planning"

Should NOT trigger:
- "What's the weather in San Francisco?"
- "Help me write Python code"
- "Create a spreadsheet"
```

### 功能測試

確保 Skill 產出正確的輸出。

```
Test: Create project with 5 tasks
Given: Project name "Q4 Planning", 5 task descriptions
When: Skill executes workflow
Then:
  - Project created in ProjectHub
  - 5 tasks created with correct properties
  - All tasks linked to project
  - No API errors
```

### 效能比較

證明 Skill 改善了結果。

```
Without skill:
- User provides instructions each time
- 15 back-and-forth messages
- 3 failed API calls requiring retry
- 12,000 tokens consumed

With skill:
- Automatic workflow execution
- 2 clarifying questions only
- 0 failed API calls
- 6,000 tokens consumed
```

### 成功標準（參考目標）

**量化指標**：
- Skill 在 90% 相關查詢中觸發
- 工具呼叫次數不超過該工作流的步驟數（每步一次，無重試）
- 每次工作流 0 個失敗 API 呼叫

**質化指標**：
- 使用者不需要提示 Claude 下一步
- 工作流完成不需要使用者修正
- 跨 session 結果一致

---

## 迭代回饋指引

### 未觸發（Undertriggering）

**症狀**：Skill 不會自動載入

**解決**：在 description 加入更多細節、關鍵字（特別是技術術語）

### 過度觸發（Overtriggering）

**症狀**：Skill 在無關查詢時載入

**解決**：
1. 加入負面觸發："Do NOT use for simple data exploration"
2. 更具體："Processes PDF legal documents for contract review"（而非 "Processes documents"）
3. 限縮範圍："PayFlow payment processing for e-commerce. Use specifically for online payment workflows, not for general financial queries."

### 執行問題

**症狀**：Skill 載入但結果不一致

**解決**：改善指令清晰度、加入錯誤處理、對關鍵驗證考慮用腳本取代語言指令

---

## 常見問題排除

### Skill 無法上傳

**不涵蓋**：本表只在經上傳分發時適用；走 git 同步的專案不會遇到這三個訊息（同〈測試方法〉那則）。

| 錯誤訊息 | 原因 | 解決 |
|---------|------|------|
| "Could not find SKILL.md in uploaded folder" | 檔名不是 `SKILL.md` | 重命名為 `SKILL.md`（大小寫敏感） |
| "Invalid frontmatter" | YAML 格式問題 | 確認有 `---` 分隔符、引號閉合 |
| "Invalid skill name" | name 有空格或大寫 | 改為 kebab-case |

### Skill 未觸發

**快速檢查清單**：
- description 是否太籠統？（"Helps with projects" 不會觸發）
- 是否包含使用者會說的觸發短語？
- 是否提到相關的檔案類型？

**驗證方法**：問 Claude "When would you use the [skill name] skill?" 根據回答調整。

### Skill 過度觸發

見「迭代回饋指引」中的 Overtriggering 解決方案。

### MCP 連線問題

**症狀**：Skill 載入但 MCP 呼叫失敗

**檢查清單**：
1. 確認 MCP server 已連線
2. 確認 API key 有效且未過期
3. 獨立測試 MCP（不用 Skill 直接呼叫）
4. 確認 Skill 中引用的工具名稱正確（大小寫敏感）

### 指令未被遵循

**常見原因**：
1. **指令太冗長**：保持精簡，用列點和編號。詳細內容移到 references/
2. **指令被埋沒**：重要指令放最上面，用 `## Important` 標題
3. **語言模糊**：用具體條件取代模糊描述
4. **模型懶惰**：加入明確鼓勵（「Take your time to do this thoroughly」），但這在 user prompt 中比在 SKILL.md 中更有效

### Context 過大

**症狀**：Skill 變慢或回應品質下降

**解決**：
1. SKILL.md body 保持在兩個門檻內——門檻值、量測指令與分段估算表見 `SKILL.md`〈Progressive Disclosure — 三層載入〉；詳細文件移到 references/
2. 評估是否同時啟用太多 Skill（20-50 個以上需考慮精簡）
3. 考慮將相關 Skill 打包為 "packs"
