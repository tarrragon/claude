# Ticket 接手考古 SOP

本文件規範 PM 接手既有 Ticket 時，若 Ticket 描述與當下環境不符的釐清流程。

> **核心理念**：Ticket 是過去某時點的快照，環境會持續演進。接手第一動作應是**驗證 ticket 引用的環境前提仍成立**，而非直接相信描述並派發。
> **動機案例**：W3-041 接手暴露 PM 缺少正規化的考古流程（PM 第一反應假設 hook 被移除，未先 git log 釐清為何 / 邏輯實際在哪 / 原需求是否仍有效）。詳見 PC-162。
> **規則層級**：PM 自律規則。Hook 層僅作 advisory（acceptance-gate 不阻擋未做考古的 ticket）；本規則靠 PM 主動觸發。

---

## 適用範圍

| 角色 | 是否適用 |
|------|---------|
| PM（主線程）認領既有 Ticket | 是 |
| PM 接手 handoff / resume 任務 | 是 |
| Subagent 收到派發後第一步檢查 | 是（受 prompt 引導） |
| 新建 Ticket（PM 自寫 5W1H） | 否（無「環境前提」可考古） |
| 即時 incident（測試紅燈、編譯錯誤） | 否（走 `pm-rules/incident-response.md`） |

---

## 強制流程

### 階段 0：觸發識別（接手即執行）

PM claim Ticket 後立即自問下列 4 個問題，**任一成立**即進入 SOP 階段 1：

| 問題 | 識別訊號 |
|------|---------|
| Q1 | `where.files` 是目錄級（如 `.claude/hooks`）而非具體檔案？ |
| Q2 | Ticket 描述包含具體 hook / 模組 / 檔案名（且該名稱可獨立驗證存在）？ |
| Q3 | Ticket `created` 距今 > 30 天，且引用既有環境狀態？ |
| Q4 | 接手第一次 `ls` / `grep` 驗證 `where.files` 發現不存在或不一致？ |

**Why**：Ticket 描述被寫下時為當時環境真實狀態，但 hook 合併（如 W10-001）/ 重構 / 重新命名都會在 ticket 等待期間發生。任一訊號代表「環境可能已演進」，必須進入考古而非盲信描述。

**Consequence**：跳過觸發識別會在描述失準時誤派代理人或關錯 ticket，常見後果包含修改不存在的檔案、實作已被刪除的 hook、依過時 acceptance 完成不符當下需求的工作。

**Action**：claim 後第一個 tool call 即執行 Q1-Q4 對應驗證指令（`ls` / `grep` / `find`）；任一答「不確定」也視同「是」進入階段 1。

---

### 階段 1：考古（最多 5 個指令）

驗證 ticket 引用的環境前提是否仍成立。建議按順序執行：

```bash
# 1.1 驗證 where.files 實際存在
ls -la <ticket where.files 列出的每個路徑>

# 1.2 若描述含 hook 名稱，驗證註冊狀態
grep "<hook-name>" .claude/settings.json .claude/settings.local.json

# 1.3 不存在 → git log 考古檔案歷史
git log --all --diff-filter=D --name-only --pretty=format:"%h %ad %s" --date=short -- <檔名>

# 1.4 找出邏輯實際位置（grep 內容關鍵字）
grep -rln "<關鍵字>" .claude/ --include="*.py"

# 1.5 看相關 commit 完整訊息（理解 root cause）
git show <commit-sha> -- <檔名>
```

**Why**：5 個指令覆蓋「檔案是否存在 / 是否註冊 / 是否曾被刪除 / 內容遷移到哪 / 為何遷移」五個維度，足以重建環境演進歷史。命令數量上限避免無止盡考古吞噬時間。

**Consequence**：跳過或僅做部分考古會在「邏輯實際在哪」上產生誤判，導致修改錯誤位置或修改無人引用的孤兒檔案；過度考古（> 5 指令）則屬於 YAGNI，應該已能下結論。

**Action**：在 ticket Problem Analysis 章節記錄每個指令輸出（commit SHA / 檔名清單 / 邏輯新位置），作為釐清三問的證據鏈。

---

### 階段 2：釐清三問

| 問題 | 行動 | 證據來源 |
|------|------|---------|
| 何時改變？ | 確認 commit 日期 + 對應 ticket ID | git log 結果（1.3） |
| 為何改變？ | 讀 commit message + 對應 ticket 結論 | git show 結果（1.5） |
| 邏輯實際在哪？ | 新位置（檔案 + 行範圍 + 註解標記） | grep 結果（1.4） |

**Why**：三問對應三個彼此獨立的判斷維度——時間軸（何時）、決策依據（為何）、現址（在哪）。少了任一問都會在「需求重評」階段缺證據。

**Consequence**：只答「邏輯實際在哪」而跳過「為何改變」的後果是 PM 可能逆向把已合併的邏輯再拆回原檔（不知道合併的設計意圖），形成倒退式修復。

**Action**：三問答案各寫一行進 ticket Problem Analysis「考古結果」段；不要僅口頭推論。

---

### 階段 3：需求重評

依考古結果判斷原 ticket 是否仍有效：

| 評估維度 | 判定 | 落地動作 |
|---------|------|---------|
| 原需求是否仍有效？ | 是 | 修正 `where.files` 指向新位置 → 進階段 4 派發 |
| 原需求是否已被解？ | 是 | 補 Problem Analysis 說明 + `ticket track complete`（注明已解原因） |
| 原需求是否需重寫？ | 是 | `set-acceptance` 重寫 + 補 `set-how` 新 strategy + 進階段 4 派發 |

**Why**：考古結果可能指向三種完全不同的後續動作。直接派發是「需求仍有效」假設下的子集；若實際是「已被解」或「需重寫」而誤派，會浪費 agent 工時並產生回歸風險。

**Consequence**：跳過需求重評直接修 `where.files` 後派發，是 PC-162 案例 A（描述與環境不符仍盲派）的典型再現。

**Action**：在 ticket Problem Analysis「需求重評」子段明示三維度判定結果與選定的落地動作。

---

### 階段 4：落地

| 動作 | 工具 / 命令 |
|------|------------|
| 修 `where.files`（具體檔案路徑非目錄） | `ticket track set-where` 或直接 Edit ticket frontmatter |
| Ticket Problem Analysis 補考古段（含三問答案 + git log 證據） | `ticket track append-log <id> --section "Problem Analysis"` |
| 派發或關閉 | `ticket track release` + `Agent(...)` / `ticket track complete` |

**Why**：考古結論必須留在 ticket md，否則下次再有人接手相同 ticket 會重做考古；落地動作必須可被後人 review，不能僅在 PM working memory。

**Consequence**：考古做完但未落地到 ticket md，下次接手 PM 仍會再走一次全流程，違反「失敗案例學習原則」（quality-baseline 規則 6）。

**Action**：階段 4 不可省略；考古完不寫 ticket = 等於沒做。

---

## 強制四問（PM 自我約束最低要求）

即使階段 0 觸發識別未明確命中，PM 接手任一 ticket 仍必須自問：

1. Ticket `where.files` 列出的所有路徑當下都存在嗎？（`ls` 驗證）
2. Ticket 描述提到的具體名稱（hook / 檔案 / 模組）當下還在嗎？（`grep` / `find` 驗證）
3. Ticket `created` 距今超過 30 天嗎？若是，引用的環境是否仍一致？
4. 我是否依「過去經驗 / memory 中既有引用」而非當下驗證在判斷？

**任一答「否」或「不確定」→ 進入階段 1 考古**。

**Why**：階段 0 觸發識別的 4 OR 問題聚焦「ticket 描述」內部訊號，強制四問則聚焦「PM 自身判斷依據」是否經當下驗證。兩者形成互補防護，避免 PM 在描述看似完整時仍以記憶代驗證。

**Consequence**：跳過強制四問會在「ticket 描述看起來與環境一致但 PM 引用的是 stale memory」情境下產生靜默誤判，這類錯誤難由外部 review 偵測，靠 PM 自律守住。

**Action**：將四問印在認領後第一個檢視步驟；任一不確定即明示進入 SOP 階段 1。

---

## 與其他規則的邊界

| 規則 / Skill | 聚焦 | 與本規則差異 |
|-------------|------|------------|
| `pm-rules/incident-response.md` | **新發生的錯誤**（測試紅燈、編譯錯誤、執行時 crash、用戶 bug report） | 本規則處理「**接手既有 ticket** 時環境已變」，源頭是 ticket queue 而非 incident |
| `skills/evidence-driven-bugfix/SKILL.md` | **已知 bug 的修復流程**（最小重現 → failing test → 根因 → 最小修復 → 回歸防護） | 本規則是 bug 修復前的「ticket 描述驗證」步驟，可作為 evidence-driven-bugfix 的前置；若考古發現 bug 已被解，根本不進入 bugfix 流程 |
| `error-patterns/process-compliance/PC-162` | **錯誤模式記錄**：Ticket 撰寫時間晚於環境變動 + Schema 模板 PC 引用錯誤 | 本規則是 PC-162 的**正向 SOP**——PC-162 描述「會出什麼錯」，本規則描述「應該怎麼做」 |
| `error-patterns/process-compliance/PC-111` | **PM 論述編造 + 淺層歸因** | 本規則的強制四問是 PC-111 的具體執行細則：「我是否依 memory 而非當下驗證在判斷」即為避免論述編造 |
| `error-patterns/process-compliance/PC-007` | **Command 引導與腳本實作行為不符** | 與本規則語意不同（PC-007 處理 command vs script，本規則處理 ticket 描述 vs 環境）；歷史上 schema 模板曾誤引用 PC-007 → 應引用 PC-162 |

---

## 檢查清單

PM claim ticket 後對照：

- [ ] 已執行階段 0 觸發識別 4 OR 問題
- [ ] 觸發 SOP 時已執行階段 1 考古（最多 5 指令）
- [ ] 階段 2 釐清三問答案已寫入 ticket Problem Analysis
- [ ] 階段 3 需求重評三維度判定結果已明示
- [ ] 階段 4 落地動作（修 `where.files` / 補考古段 / 派發或關閉）已執行
- [ ] 即使未觸發 SOP，強制四問已自答（任一不確定即升級）

---

## 反模式速查

| 反模式 | 症狀 | 正確做法 |
|-------|------|---------|
| 假設失敗即解 | PM 第一反應「hook 一定是被移除了」 | 先 git log 考古確認，再下結論 |
| 跳過階段 4 落地 | 考古做完只口頭講結論，不寫 ticket | 必寫 Problem Analysis 考古段 |
| 把考古當 incident 處理 | 用 incident-responder 處理「接手 ticket 環境不符」 | 走本規則，incident-responder 用於新發生錯誤 |
| 記憶代驗證 | 「我記得這個 hook 還在」直接派發 | 強制四問 Q4 已明示禁止，必須當下 `grep` 驗證 |
| 過度考古 | 5 指令外仍持續挖 | 已達指令上限應直接下結論進階段 2；可能屬 YAGNI |

---

## 相關文件

- `.claude/pm-rules/incident-response.md` — 新發生錯誤的事件回應流程（互補）
- `.claude/skills/evidence-driven-bugfix/SKILL.md` — Bug 修復證據驅動流程（後續銜接）
- `.claude/rules/core/quality-baseline.md` 規則 6 — 失敗案例學習原則（本規則的上游品質承諾）
- `.claude/rules/core/document-writing-style.md` — 三明示原則（本規則撰寫遵循）
- `.claude/error-patterns/process-compliance/PC-162-ticket-description-stale-environment-and-schema-citation-mismatch.md` — 動機案例
- `.claude/error-patterns/process-compliance/PC-111-pm-narrative-fabrication-and-shallow-attribution.md` — 強制四問 Q4 的根源
- `.claude/error-patterns/process-compliance/PC-007-command-guidance-implementation-mismatch.md` — 邊界說明（與本規則語意不同）

---

**Last Updated**: 2026-05-26 | **Version**: 1.0.0 — 初版建立（W3-068 落地 W3-067 ANA Solution）。**Source**: 0.19.0-W3-067（ANA：接手考古 SOP 設計）+ PC-162（錯誤模式記錄）。
