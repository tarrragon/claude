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

## 派發前檢查：worktree base 同步（W1-035）

PM 用 `isolation: "worktree"` 派發 agent 前，先執行 `git status --porcelain` 確認有無 pending changes，有則先 commit 到 main 再派發。

**Why**：cc runtime 的 `isolation: "worktree"` 在 `git worktree add` 瞬間快照當下 main HEAD 作為 worktree base，之後不再同步。派發後 PM 若繼續 commit，worktree base 與 main 的落差只增不減。

**Consequence**：base 落後會讓 agent 讀不到派發後新增的 ticket 檔、ticket create 因掃描不到新 ticket 而誤分配碰撞 ID、worktree 分支因歷史分叉無法 fast-forward 回 main（W1-035 症狀 1/2/3）。落差越大，收尾時手動整合的成本越高。

**Action**：派發 `isolation:worktree` agent 前執行一次 `git status --porcelain`，非空則先 commit。此防護成本為一次狀態檢查，與 agent 端的執行中防護（見 `.claude/references/agent-dispatch-template.md`「worktree 派發 base 同步指引」）互補——派發前 commit 縮小初始落差，agent 端 merge 補平殘餘落差。

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

### PM 對話回覆前自檢 checklist（三明示版）

> **來源**：W17-174.4 落地。W17-174.1 L1 審計證實本 session PM 5 次列選項違規 AUQ，通用 4 條 checklist 在 context 高壓場景失效。本節為三明示版自檢題，對齊 W17-170 體例，與 hook 強制層（W17-174.2.1）形成自律 + 強制雙層防護。

撰寫每則對話回覆前，依下列 4 題自檢：

#### Q1：本回覆是否含 S1-S6 任一表面 pattern？

**Why**：W17-174.1 F5 證實 hook 偵測盲區在觸發條件層；表面 pattern（Markdown 列表 / 表格 / Recommended 標記 / 隱性推薦 / 問句結尾 / 純文字 A./B.）即為 AUQ 觸發訊號，無論呈現形式。

**Consequence**：若以「我用的是表格不是列表」「這是隱性建議不是顯式選項」豁免，會在 hook 強制層擴充前持續累積違規。

**Action**：對照 askuserquestion-rules.md §具體觸發訊號 S1-S6 表格自檢；命中任一即進入 Q2。

#### Q2：候選項是否 ≥ 2 個（含「不做」也算一個）？

**Why**：≥2 候選項即構成「向用戶呈現選擇」的本質條件；單一選項屬資訊提供而非決策提問。

**Consequence**：若候選項只有 1 個但仍以問句結尾（「要這樣做嗎？」），實質為二元確認（隱含「做 vs 不做」），仍 ≥ 2 候選項。

**Action**：候選項計數時將「不做 / 暫緩 / 等等」算為一個獨立選項；≥2 進入 Q3。

#### Q3：是否傾向用「快速確認」「stakes 低」「選項顯而易見」豁免？

**Why**：W17-174.1 F3 證實低 stakes 感知是 PM 主要違規藉口（PC-064 陷阱模式第一條）。AUQ 觸發條件不區分 stakes 高低。

**Consequence**：低 stakes 豁免會讓 AUQ 規則的實際覆蓋率遠低於名義覆蓋率，且訓練 PM 把列選項變成預設行為。

**Action**：感受到「快速確認比較方便」念頭時，**反向強制呼叫 AUQ**；豁免理由不是合法考量。

#### Q4：是否剛收到代理人完成回報？

**Why**：W17-174.1 F1 證實 5/5 違規均發生在「代理人完成回報後」的 PM 回覆，此為 PM 最高頻決策點與工作記憶切換點。

**Consequence**：若此場景系統性繞過 AUQ，AUQ 規則在 PM 最常用情境形同失效；context 越沉重越易觸發（F2 工作記憶遞減訊號）。

**Action**：每次代理人完成通知後，撰寫第一回覆前**強制重跑 Q1-Q3**；命中任一即必呼叫 AUQ。本題為 F1 場景的硬觸發點，不可省。

#### 自檢通過條件

Q1-Q4 任一為「是」 → 必須執行 `ToolSearch("select:AskUserQuestion")` 載入 schema 後使用 AUQ。**禁止用 Markdown 列表 / 表格 / 純文字問句替代**。

---

## 相關文件

- .claude/rules/core/pm-role.md — 核心禁令與情境路由表
- .claude/pm-rules/agent-failure-sop.md — 派發後代理人失敗處理
- .claude/pm-rules/askuserquestion-rules.md — AUQ 完整規則（規則 1、3、4）
- .claude/pm-rules/worktree-operations.md — .claude/ 路徑限制
- .claude/pm-rules/parallel-dispatch.md — 並行派發策略

---

**Last Updated**: 2026-05-09
**Version**: 1.1.0 — 新增「PM 對話回覆前自檢 checklist（三明示版）」章節 Q1-Q4，引用 W17-174.1 共同特徵 F1/F3/F5 + askuserquestion-rules.md S1-S6 訊號表（W17-174.4 落地）
**Version**: 1.0.0 — 從 rules/core/pm-role.md 拆出（W10-076.2 拆分；原檔 v3.7.0 L41-L107）
