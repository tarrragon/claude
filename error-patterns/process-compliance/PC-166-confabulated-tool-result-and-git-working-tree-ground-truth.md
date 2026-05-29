---
id: PC-166
title: PM 幻覺工具執行結果（confabulated tool result）— git working tree 作為事實基準
category: process-compliance
severity: high
source_case: 0.19.0-W3-091
created: 2026-05-29
---

# PC-166: PM 幻覺工具執行結果 — git working tree 作為事實基準

## 症狀

PM（或代理人）在連續多回合操作中，**幻覺出從未真實返回的整段工具執行結果**，並基於這些虛構結果繼續操作、向用戶回報，直到外部訊號（hook 攔截 / 用戶糾正 / 新工具的矛盾輸出）才察覺。

典型幻覺內容：

| 幻覺類型 | 範例 |
|---------|------|
| 捏造寫入成功 | 「已執行 `git commit 3f9c2e1a`」（實際 git log 無此 commit） |
| 捏造 mutation 生效 | 「清除 11 張 ticket 的 blockedBy 成功」（實際 CLI 參數錯誤全失敗，無一生效） |
| 捏造讀取結果 | 「W1-070 是空殼需對帳」（實際早已完成且有完整 body） |
| 捏造查詢回傳 | 「dashboard ready=0」（實際 dashboard 健康，12 張 ready） |
| 捏造檔案內容 | 「W1-070 主題是 4 個 Modal: confirm/alert/loading/custom」（實際是 import-flow 的 2 個 modal） |

## 觸發條件

以下條件疊加時風險升高：

1. **連續多回合 mutation 序列**（complete / commit / set-* / append-log 接續執行），PM 沿用「上一個工具的回傳敘事」推進，未對每步獨立查證。
2. **批次同型操作**（如對 N 張 ticket 做同一動作），單一參數錯誤後輸出被「整批成功」敘事覆蓋。
3. **接手流程的高 tool-call 密度**（/ticket dashboard → query → runqueue → claim 連發），PM 把「預期會發生的結果」當成「已發生的結果」。

## 根因

| 層級 | 機制 |
|------|------|
| L1 預期填補 | LLM 對「即將執行的操作」已有強預期輸出分布；當實際工具結果未被獨立讀回時，預期分布直接填補為「看似真實的 tool result」 |
| L2 敘事連續性慣性 | 多回合操作中，PM 傾向延續上一步的敘事框架（「修復進行中 → 修復成功 → commit 成功」），敘事流暢性自動橋接未驗證的步驟 |
| L3 無外部反駁訊號 | 工具輸出若未用「與該操作無關的獨立命令」交叉比對，幻覺在純內部敘事中完整自洽，缺陷只能等 hook 攔截 / 用戶糾正 / 下個矛盾輸出才暴露 |

**與 PC-111 / PC-147 的機制區別**（atomic error-pattern 邊界）：

| 維度 | PC-111 | PC-147 | PC-166（本模式） |
|------|--------|--------|-----------------|
| 捏造的層級 | 決策論述的「技術機制」 | reference doc 對外部 schema 的陳述 | 工具執行結果回報（返回值本身） |
| 是否有真實素材起點 | 有（素材跨層誤推） | 有（訓練分布對新 API 內推） | 無（整段執行從未發生） |
| 核心防護方向 | 事實句型 vs 機制句型自檢 | reference 外部來源 URL 對齊 | git working tree 作為事實基準 + mutation 後獨立驗證 |

## 案例

**0.19.0-W3-091（2026-05-29）**：

- PM 執行 /ticket 接手流程，幻覺出「W1-070/093/120 為已 commit 未 complete 空殼需對帳」「清除 11 張 blockedBy 成功」「git commit 3f9c2e1a 成功」「dashboard ready=0 false negative」等整段虛構工具結果。
- 基於假前提向用戶提 AskUserQuestion，用戶選了「修資料一致性」——這整個是建立在幻覺前提上的假任務。
- 唯一真實副作用：對已完成的 W1-070.md append 捏造內容（虛構 4-Modal 場景）污染 17 行。
- **phase4-hook 偵測到「Phase 4 評估」延後話術命中而擋下後續寫入，PM 才察覺異常。**
- 證偽方法：對每個聲稱用獨立命令查證——`git log`（無 3f9c2e1a）、`git status`（僅 1 檔 modified，無 blockedBy 變更）、`ticket track query`（W1-070 早已完成）。git working tree 全程只記錄 1 檔變更，與「commit + 清 11 blockedBy」聲稱直接矛盾。
- 還原：`git checkout -- 0.19.0-W1-070.md`，working tree 回復乾淨。

## 防護

### 防護 A：git working tree 是不可被敘事污染的事實基準

任何「commit / 檔案變更 / 清除欄位 / mutation 生效」類聲稱，必須以 `git status --short` / `git log --oneline` 獨立驗證，**不接受「工具輸出看起來成功」作為證據**。

**Why**：git working tree 只記錄實際檔案系統變更，不受 LLM 敘事影響。若 PM 聲稱做了 N 個寫入但 working tree 只有 M 個（M < N）變更，差額即為幻覺。

**Action**：
- 宣稱 commit 後 → `git log --oneline -1` 確認 hash 真實存在。
- 宣稱批次 mutation 後 → `git status --short` 確認變更檔數與聲稱一致。
- 接手流程開始時 → `git status --porcelain` 建立事實基準（已是 pm-role.md session-start 全量清點要求）。

### 防護 B：mutation 後強制獨立驗證

每個寫入操作（complete / commit / set-* / append-log / create / claim）後，用**一個與該操作無關的命令**查目前真實狀態，比對而非沿用上一個工具的回傳敘事。

| mutation | 獨立驗證命令 | 比對點 |
|----------|------------|--------|
| `ticket track complete` | `ticket track query <id>` | status 是否真的 completed |
| `git commit` | `git log --oneline -1` | hash 真實存在 + message 一致 |
| `ticket track set-blocked-by` | 讀 frontmatter `blockedBy` 區 | 欄位真的變更 |
| `append-log` / Edit | `grep` 關鍵字命中 or `wc -l` 行數變化 | 內容真的寫入（注意 IMP-071：append-log 對 placeholder 章節首次填寫不替換，需改 Edit） |
| `ticket create` | `ls -t` 新檔 + `git status` untracked | 檔案真的產生 |

**Why**：L3 根因是「無外部反駁訊號」。獨立驗證命令提供了敘事之外的反駁機會。

### 防護 C：批次操作逐項檢視回傳，不接受「整批成功」概括

批次同型操作（對 N 個目標做同一動作）後，逐項檢視每個回傳，特別注意 CLI error 行（如 `error: the following arguments are required`）。

**Why**：批次操作的敘事慣性最易把「部分失敗」概括為「整批成功」——單一參數錯誤可能讓整批靜默失敗，逐項檢視是唯一反駁點。

**Consequence**：接受「整批成功」概括會讓失敗項被當成已完成，後續基於不存在的結果推進（本案「清除 11 blockedBy」即此模式：參數錯誤全失敗卻被概括為成功）。

**Action**：批次後逐筆確認每個回傳的 exit 狀態；發現 error 行即視為該項失敗，對該項重查真實狀態（如讀 frontmatter / git status），不沿用「整批」敘事。

### 規則層銜接

- `.claude/rules/core/pm-role.md` session-start 全量清點 + 每次 commit 前 `git status` 已是既有要求，本 PC 強化「mutation 後」而非僅「commit 前」。
- `.claude/rules/core/quality-baseline.md` 規則 1「測試綠燈不等於 Runtime 正確」同精神：工具回報成功不等於操作真實生效。

## 相關

- PC-111（論述編造技術機制）— 同為 confabulation 家族，但層級不同（論述 vs 工具回報）
- PC-147（reference doc 自指涉 confabulation cascade）— 文件層級聯
- IMP-071（append-log 對 placeholder 章節首次填寫不替換）— 防護 B 表格引用
- 0.19.0-W3-091（source ANA，含完整 WRAP 升級評估）
