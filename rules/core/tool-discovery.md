# 工具發現規則（Tool Discovery）

> **核心理念**：在宣告「做不到」或選擇「限制性解法」（禁止、防護、規避）之前，必須先窮盡平台能力發現路徑。ToolSearch 是 Claude Code runtime 提供的通用 deferred tools 發現機制，非單一工具的專用鑰匙。

## 適用對象

- **PM（主線程）**：派發、觀察、路由、決策等所有情境
- **代理人**：遇到任務未覆蓋的能力需求時，先檢查後回報，禁止自行結論「平台不支援」

## 強制規則

### 規則 1：宣告「做不到」前必須完成五問檢查

準備告訴用戶「無法」「做不到」「目前不支援」，或採用「限制性解法」（禁止 X、防護 X、規避 X）時，必須先依序回答以下五問：

| 問題 | 檢查內容 |
|------|---------|
| (1) Hook 能推送嗎？ | `.claude/hooks/` 是否已有或可新增 Hook 處理此情境？ |
| (2) 檔案系統能追蹤嗎？ | 是否有既有持久化檔案（如 dispatch-active.json、worklog）可查？ |
| (3) 流程能繞過嗎？ | 是否可調整 Ticket/Wave/Phase 順序避免此需求？ |
| (4) 既有模組有 API 但沒接線嗎？ | `.claude/skills/` 或專案程式碼是否已有 API，只差接線？ |
| (5) CC runtime 有 deferred tool 嗎？ | **執行 `ToolSearch` 搜尋是否有對應的 deferred tool** |

**五個問題都回答「否」才能下結論「做不到」。**

### 規則 2：採「限制性解法」前必須先問探索性解法

問題框架會決定搜尋範圍。以下兩種框架會導向不同搜尋路徑：

| 限制性框架（傾向禁止） | 探索性框架（傾向找工具） |
|----------------------|------------------------|
| 「如何防止誤判 transcript？」 | 「如何正確取得代理人狀態？」 |
| 「如何阻止用戶輸入中文？」 | 「如何讓用戶選擇預定義選項？」 |
| 「如何避免併發衝突？」 | 「如何協調多個代理人？」 |

**採「禁止 X」解法之前，必須先嘗試「如何正確做 X」的框架，再執行五問。**

### 規則 3：ToolSearch 是通用發現機制，非單一用途

ToolSearch 是 Claude Code runtime 的**通用 deferred tools 發現入口**。禁止將其框架為「特定工具的專用前置步驟」（例如「AskUserQuestion 前置載入」）。具體工具的使用指南可引用此通用機制，但規則定義必須保持抽象。

### 規則 4：System-reminder 的 deferred tools 清單必須主動檢視

每 session 啟動時 runtime 在 system-reminder 列出可用 deferred tools 名稱。遇到「找工具」需求時主動檢視，禁止當背景資訊忽略。

> 完整使用方式、deferred tools 對照表、工作流程、反模式清單：`.claude/skills/search-tools-guide/SKILL.md`（Claude Code Meta-Tools 章節）

---

**Last Updated**: 2026-04-16
**Version**: 1.1.0 — 瘦身執行層到 search-tools-guide skill（W10-078.1）
