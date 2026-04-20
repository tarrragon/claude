# PC-060: 未使用 ToolSearch 發現 Claude Code deferred tools 導致採限制性解法

## 錯誤症狀

PM 或代理人在遇到「我想做 X 但不知道怎麼做」的情境時：

1. 搜尋範圍**只限於專案 `.claude/` 內既有的 Hook、API、規則**
2. 未檢查 Claude Code runtime 在每個 session 的 system-reminder 中列出的 **deferred tools 清單**
3. 未執行 `ToolSearch` 搜尋是否有對應工具
4. 結論為：
   - 「平台不支援」「做不到」（直接放棄）
   - 或採用**限制性解法**：禁止 X、防護 X、規避 X（封閉可能誤判的路徑，而非找能正確判斷的工具）
5. 後續其他 session 偶然發現 deferred tool 後，才驚覺根本解法早已存在

## 根因分析

### 成因 1：ToolSearch 被框架為「特定工具的專用前置步驟」

專案文件（如 `.claude/pm-rules/askuserquestion-rules.md` 原版）將 ToolSearch 描述為「使用 AskUserQuestion 前必須執行」，**框架化為單一用途鑰匙**。PM 的心智模型因此把它當成 AskUserQuestion 的附屬工具，而非**通用 deferred tools 發現機制**。

### 成因 2：搜尋工具指南未涵蓋 CC Meta-Tools

`search-tools-guide` skill 原本只覆蓋程式碼搜尋（Grep/Serena/WebSearch/Dart MCP/Glob）。PM 遇到「觀察代理人」「發送指令給代理人」「排程任務」等 CC runtime 能力需求時，腦中對應的 skill 是「找工具 = 找程式碼」，不會聯想到「找 CC runtime 的能力」。

### 成因 3：System-reminder 的 deferred tools 清單被當背景資訊

每個 session 啟動時，CC runtime 在 system-reminder 中列出所有可用的 deferred tools（TaskOutput / TaskList / TaskStop / SendMessage / WebFetch / WebSearch / Cron* / Team* 等）。但此訊息**沒有互動性**（不是主動提示 PM 去用），PM 傾向當成系統雜訊跳過。

### 成因 4：問題框架錯誤（限制性 vs 探索性）

PM 遇到「讀 transcript 誤判」時，自然反應是**「禁止讀 transcript」（限制性解法）**。這個框架下，搜尋目標是「如何強制不讀」，而不是「是否有工具可正確判斷狀態」。

如果問題框架改為「如何正確取得代理人的 runtime 狀態」，才會自然觸發「找查詢工具」的思路，ToolSearch 才可能進入視野。

### 成因 5：原則建立當下未擴充檢查清單

PM 在遇到本模式後常會記下 memory（如 `feedback_exhaust_indirect_before_impossible.md`），但原始清單未涵蓋 CC runtime 能力。**原則正確但覆蓋不全**，下次同一 session 內遇到新類型的「找工具」需求時仍會踩雷。

## 實際案例

### 案例 1：PC-050 模式 D（觸發本 error pattern 建立）

**背景**：PM 派發代理人後讀取 transcript 檔案中間狀態誤判為失敗。

**錯誤路徑**（兩天前 session）：
1. 搜尋專案內 Hook → 只找到事後觸發的 `agent-commit-verification-hook`
2. 讀 transcript 推論狀態 → 被中間狀態誤導
3. **未執行 ToolSearch** → 未發現 TaskOutput 可讀 `<status>` 標籤
4. 結論：「缺乏主動查詢代理人狀態的工具」→ 採「禁止讀 transcript」限制性解法
5. 記錄為 PC-050 模式 D 防護規則

**正確路徑**（今天 session）：
1. 重新思考「如何正確取得代理人狀態」
2. 執行 `ToolSearch(select:TaskList,TaskGet,TaskOutput,TaskStop,...)` 載入 schema
3. 實證 TaskOutput `<status>` 標籤可用
4. PC-050 模式 D 防護規則從「禁止讀 transcript」升級為「允許讀 `<status>`，禁止讀 `<output>` body」

**代價**：兩個 session 之間的「限制性解法」期間，PM 失去 runtime 狀態查詢能力，依賴不完全的檔案系統證據間接推論。

## 防護措施

### 措施 1：自動載入的 tool-discovery 規則

新建 `.claude/rules/core/tool-discovery.md`（auto-load），定義：
- **規則 1**：宣告「做不到」前必須完成五問檢查（含第五問：執行 ToolSearch）
- **規則 2**：採限制性解法前必須先問探索性解法
- **規則 3**：ToolSearch 是通用發現機制，禁止框架為單一用途
- **規則 4**：System-reminder 的 deferred tools 清單必須主動檢視

### 措施 2：搜尋工具指南涵蓋 CC Meta-Tools

`.claude/skills/search-tools-guide/SKILL.md` 新增「Claude Code Meta-Tools」章節，包含：
- ToolSearch 使用方式（select 精確載入 + 關鍵字探索）
- 14 項 deferred tools 用途對照表
- 三步工作流程
- 反模式清單

### 措施 3：五問檢查清單（來源：memory）

`feedback_exhaust_indirect_before_impossible.md` 擴充為五問：

1. Hook 能推送嗎？
2. 檔案系統能追蹤嗎？
3. 流程能繞過嗎？
4. 既有模組有 API 但沒接線嗎？
5. **CC runtime 有 deferred tool 嗎？（執行 ToolSearch 搜尋）**

五問都回答「否」才能結論「做不到」。

### 措施 4：具體 deferred tool 使用指南引用通用規則

個別工具的使用指南（如 askuserquestion-rules.md、pm-agent-observability.md）不再自行定義「ToolSearch 前置載入」，改為引用 `.claude/rules/core/tool-discovery.md` 的通用規則，保持抽象與具體的分離。

## 自我檢查清單

遇到「找工具」情境時，依序自問：

- [ ] 我的問題框架是「如何防止 X」還是「如何正確做 X」？（限制性則改探索性）
- [ ] 我是否查過 system-reminder 的 deferred tools 清單？
- [ ] 我是否執行過 `ToolSearch(query="關鍵字", max_results=5)` 探索？
- [ ] 我是否對照過 search-tools-guide 的「Claude Code Meta-Tools」章節？
- [ ] 五問檢查是否完整？

任一答「否」都不可結論「做不到」或採限制性解法。

## 關聯

- **相關模式**：PC-050（誤判代理人狀態）— 本模式的下游表現
- **相關 feedback**：`feedback_exhaust_indirect_before_impossible.md`（五問檢查清單）
- **相關規則**：`.claude/rules/core/tool-discovery.md`、`.claude/pm-rules/askuserquestion-rules.md`
- **相關指南**：`.claude/skills/search-tools-guide/SKILL.md`（Claude Code Meta-Tools 章節）
- **相關參考**：`.claude/references/pm-agent-observability.md`（TaskOutput 作為具體用例）

---

**Created**: 2026-04-13
**Last Updated**: 2026-04-13
**Category**: process-compliance
**Severity**: P2（導致採用次佳解法，非立即錯誤，但累積成本顯著）
**Key Lesson**: ToolSearch 是通用 deferred tools 發現機制；採「限制性解法」之前必須先以「探索性解法」框架搜尋一次 CC runtime 能力
