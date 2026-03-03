# Skill Patterns, Testing & Troubleshooting

詳細的 Skill 設計模式、測試方法和常見問題排除指引。

> 來源：Anthropic 官方 Skills 文件 (platform.claude.com) + 《The Complete Guide to Building Skills for Claude》(2026-01)

---

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

| 層級 | 方法 | 說明 |
|------|------|------|
| Manual | 在 Claude.ai 直接執行 | 快速迭代，無需設定 |
| Scripted | 在 Claude Code 自動化測試案例 | 跨版本的可重複驗證 |
| Programmatic | 透過 Skills API 建立評估套件 | 對定義的測試集系統化執行 |

### Pro Tip

先對單一困難任務迭代直到 Claude 成功，再將成功方法提取為 Skill。這比廣泛測試提供更快的訊號。

### 1. 觸發測試

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

### 2. 功能測試

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

### 3. 效能比較

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
- 在 X 次工具呼叫內完成工作流
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
1. SKILL.md 保持低於 5,000 字，詳細文件移到 references/
2. 評估是否同時啟用太多 Skill（20-50 個以上需考慮精簡）
3. 考慮將相關 Skill 打包為 "packs"

---

*Last Updated: 2026-02-11*
*Source: Anthropic Official "The Complete Guide to Building Skills for Claude" (2026-01)*
