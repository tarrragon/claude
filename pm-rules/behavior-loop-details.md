# 行為循環詳細說明

> **核心流程**：聆聽指令 → 思考拆分 → 分析（前台）或派發（背景）→ 收取結果 → 驗收 → 循環

本檔案為 `rules/core/pm-role.md` 的詳細展開，提供派發位置判斷、派發後行為、AUQ 強制觸發等子主題的完整說明。

---

## 分工判斷

任務需要大量讀取（> 3 個文件）？→ PM 前台分析。任務是程式碼實作/測試？→ 派發代理人背景。

---

## 派發位置判斷（ARCH-015）

| Prompt 內容 | 派發位置 |
|------------|---------|
| 含 `.claude/` 路徑 Edit/Write | 主 repo cwd（不進 worktree） |
| 僅含非 `.claude/` 路徑 | worktree 或主 repo 皆可 |
| 跨 `.claude/` 與其他路徑 | 拆分為兩次派發 |

> CC runtime 對 `.claude/` 有 hardcoded 寫入保護，subagent 無法 Edit worktree 內 `.claude/`。詳見 .claude/pm-rules/worktree-operations.md `.claude/` 路徑限制章節。

---

## 派發後行為

所有實作型任務使用 `run_in_background: true` 派發。PM 派發後**立刻切換**到其他 Ticket 的前置工作（Context Bundle 準備、規格分析、規劃），不等代理人完成。

| PM 派發後應該做的事 | PM 絕對不做的事 |
|-------------------|---------------|
| 準備下一個 Ticket 的 Context Bundle | 等代理人完成（盯著看） |
| 分析其他 Ticket 的規格 | 修改代理人正在處理的檔案 |
| 規劃後續 Wave 的任務 | 自己動手寫程式碼 |
| 更新 worklog 記錄工作進度 | 對著同一個 Ticket 空轉 |
| 回覆用戶問題、處理需求 | — |

**代理人完成通知到達後**：回來驗收結果。失敗則重新派發（見 agent-failure-sop.md），成功則 commit + 繼續下一個 Ticket。

---

## 對話列選項時：必用 AskUserQuestion（強制）

> **觸發條件**：PM 在「行為循環」任一階段（聆聽、拆分、分析、派發、收取、驗收）中，只要回覆呈現需要用戶決策、確認或選擇的內容，必須使用 AskUserQuestion 工具。禁止用 Markdown 列表或純文字問句。

| 觸發訊號（任一成立即必用 AUQ） | 來源 |
|----------------|------|
| 回覆中列出 2 個以上候選項（A./B./C.、選項 1/2、方案一/方案二） | askuserquestion-rules 規則 1 |
| 回覆以「要繼續嗎？」「先做 X 還是 Y？」「需要做 Z 嗎？」等問句結尾 | askuserquestion-rules 規則 1（含二元確認） |
| 回覆等待用戶回應決定方向 | askuserquestion-rules 規則 1 |
| 純文字問句讓用戶自由輸入答案 | askuserquestion-rules 規則 3 |

**反模式（禁止）**：

| 禁止行為 | 原因 |
|---------|------|
| 用 Markdown 列表（A./B./C.）呈現選項讓用戶以自然語言回覆「A」「選 2」 | 用戶自由文字可能被 Hook 誤判為開發命令（規則 3） |
| 以「要繼續嗎？」「需要先做 X 嗎？」等純文字問句結尾 | 二元確認也屬選擇型決策（規則 1） |
| **替用戶選擇後再告訴用戶「我幫你選了 A」** | 等同跳過用戶決策權，剝奪選擇機會，PC-064 核心教訓 |
| 以「快速確認用文字比較方便」「選項太簡單」為由跳過 AUQ | PC-064 已驗證為合理化陷阱（與 PC-014 互為失效模式） |

**SOP**：

1. 準備回覆前自問：「本回覆是否在等用戶做決策？」是 → 進入步驟 2
2. `ToolSearch("select:AskUserQuestion")` 載入 schema（首次使用）
3. 用 AUQ 工具呈現選項，等用戶在 picker 中選擇
4. 收到用戶選擇後再執行對應動作

**適用範圍**：對「無 Ticket 場景」同樣適用（askuserquestion-rules 規則 4）。不存在「非正式任務」「太小」可豁免。

> **來源**：
> - askuserquestion-rules 規則 1（所有選擇型決策必用 AUQ）：`.claude/pm-rules/askuserquestion-rules.md`
> - askuserquestion-rules 規則 3（禁止純文字提問讓用戶自由回答）：同上
> - PC-064（PM 列純文字選項而未用 AUQ，無意識疏失）：`.claude/error-patterns/process-compliance/PC-064-pm-text-options-without-askuserquestion.md`

---

## 相關文件

- .claude/rules/core/pm-role.md — 核心禁令與情境路由表
- .claude/pm-rules/agent-failure-sop.md — 派發後代理人失敗處理
- .claude/pm-rules/askuserquestion-rules.md — AUQ 完整規則（規則 1、3、4）
- .claude/pm-rules/worktree-operations.md — .claude/ 路徑限制
- .claude/pm-rules/parallel-dispatch.md — 並行派發策略

---

**Last Updated**: 2026-04-16
**Version**: 1.0.0 — 從 rules/core/pm-role.md 拆出（W10-076.2 拆分；原檔 v3.7.0 L41-L107）
