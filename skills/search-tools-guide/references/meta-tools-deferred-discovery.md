# Claude Code Meta-Tools（平台能力發現）完整版

> **定位**：本檔為 `search-tools-guide` 主檔「Claude Code Meta-Tools（平台能力發現）」節的完整版，收錄常見 deferred tools 用途對照表、發現工作流程、反模式清單與相關規則。
>
> **何時讀本檔**：主檔的核心規則與 `ToolSearch` 呼叫語法已足夠應付單次載入；需要完整 deferred tools 對照表決定該搜哪個關鍵字、或需要工作流程圖 / 反模式清單核對自己的判斷路徑時，讀本檔。
>
> **同目錄**：無。本節內容單獨外移，`search-tools-guide/references/` 下無其他 meta-tools 相關檔案。
>
> 溯源：v5.2.0 拆分自 `SKILL.md`「Claude Code Meta-Tools（平台能力發現）」節（體量收斂：全檔 6,723 tokens 超出 5,000 門檻 1.34 倍）。

---

## 常見 Deferred Tools 用途對照

| 需求 | Deferred Tool | 典型場景 | 注意事項 |
|------|---------------|---------|---------|
| 查背景代理人 runtime 狀態 | `TaskOutput` | PC-050 模式 D 補救；失敗判斷前置步驟 Step 0.5 | **只讀 `<status>` 標籤**，禁讀 `<output>` body（PC-050） |
| 派發背景代理人 | `TaskCreate` | 需要 run_in_background 長任務 | 搭配 Agent tool 更常用 |
| 停止失控代理人 | `TaskStop` | 代理人 loop、超時、錯誤方向 | 先 TaskOutput 確認狀態再停 |
| 向代理人發送指令 | `SendMessage` | 代理人執行中需要補充資訊 | 非同步發送，代理人下次 tool call 收 |
| 列出所有任務 | `TaskList` | 總覽 CC 任務（非 TodoList） | 注意：**不是 TodoList 系統** |
| 用戶做決策 | `AskUserQuestion` | 路由 / 多選 / 二元確認 | 詳見 askuserquestion-rules.md |
| 抓取指定網頁 | `WebFetch` | 精準讀取 URL 內容 | 網頁搜尋用 WebSearch |
| 網頁搜尋 | `WebSearch` | 技術文件 / API 查詢 | 詳見主檔 WebSearch 章節 |
| 排程定期任務 | `CronCreate` / `CronList` / `CronDelete` | 週期性自動執行 | |
| 建立 / 管理多代理人團隊 | `TeamCreate` / `TeamDelete` | 代理人間即時協商 | 詳見 agent-team skill |
| 進入 / 離開計畫模式 | `EnterPlanMode` / `ExitPlanMode` | 提出計畫給用戶核准 | |
| 進入 / 離開 worktree | `EnterWorktree` / `ExitWorktree` | 分支隔離 | |
| 監控背景 process stdout | `Monitor` | 追蹤 log 流 | |
| 修改 Jupyter Notebook | `NotebookEdit` | 專案少用 | |
| MCP resources 查詢 | `ListMcpResourcesTool` / `ReadMcpResourceTool` | 跨 MCP server 資源 | |

> Session 當下可用的 deferred tools 清單以 system-reminder 為準，實際載入請以 `ToolSearch` 返回為依據。

## 工作流程

```
情境：「我想做 X 但不知道有什麼工具」
    |
    v
Step 1：對照本檔「用途對照表」是否有直接匹配
    |
    +-- 有 --> ToolSearch(query="select:<tool_name>") 載入 → 呼叫
    |
    +-- 無 --> Step 2
    |
    v
Step 2：用關鍵字 ToolSearch 探索
    ToolSearch(query="keyword1 keyword2", max_results=5)
    |
    +-- 找到 --> 載入 → 呼叫
    |
    +-- 找不到 --> Step 3
    |
    v
Step 3：五問窮盡檢查
    (1) Hook 能推送嗎？
    (2) 檔案系統能追蹤嗎？
    (3) 流程能繞過嗎？
    (4) 既有模組有 API 但沒接線嗎？
    (5) CC runtime 有 deferred tool 嗎？（已在 Step 1-2 執行）
    |
    v
五問皆否才能結論「做不到」
```

## 反模式（必須避免）

| 反模式 | 症狀 | 正確做法 |
|-------|------|---------|
| 框架為「XX 專用前置步驟」 | 把 ToolSearch 當成特定工具的鑰匙，不當成通用發現機制 | 理解為「發現 CC runtime deferred tools 的通用入口」 |
| 忽略 session system-reminder | 把 deferred tools 清單當背景資訊 | 每 session 首次遇到「找工具」需求時掃一次 |
| 採限制性解法（禁止 / 防護） | 問題框架為「如何防止 X」 | 改框架為「如何正確做 X」再問五問 |
| 跳過第五問 | 只檢查 Hook/檔案/流程/既有 API，未問 CC runtime 能力 | 必須執行 ToolSearch 搜尋 deferred tool |
| 宣告「平台不支援」未窮盡 | 代理人或 PM 直接下結論 | 先完成五問（規則 1），最後才下結論 |
| 讀 transcript 推論代理人狀態 | 違反 PC-050 模式 D | 用 TaskOutput 讀 `<status>` 標籤 |

## 相關規則與錯誤模式

- `.claude/pm-rules/askuserquestion-rules.md` — AskUserQuestion 的具體用例
- `.claude/references/pm-agent-observability.md` — TaskOutput 安全使用範本
- `.claude/error-patterns/process-compliance/PC-050-premature-agent-completion-judgment.md` — 模式 D 禁讀 output body
- Memory `feedback_exhaust_indirect_before_impossible.md` — 五問檢查清單
