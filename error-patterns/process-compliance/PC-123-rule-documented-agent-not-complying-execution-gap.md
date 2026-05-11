---
id: PC-123
title: 規則存在但 agent 行為層未遵守 — agent-definition-standard 規範與實際輸出落差
category: process-compliance
severity: medium
status: active
created: 2026-05-05
related:
- PC-110
- agent-definition-standard
- W17-072
---

# PC-123: 規則存在但 agent 行為層未遵守 — agent-definition-standard 規範與實際輸出落差

## 問題描述

`.claude/rules/core/agent-definition-standard.md` 已定義「章節結構規則」（W17-072）：實作類 agent 完成 ticket 時禁止寫自定義 H2，實作內容必須寫在 Schema 章節（如 `## Solution`）下用 H3 子章節組織。但 dispatch 後 agent 仍會出現違規模式；**進一步發現 PM 用 ticket CLI append-log 寫長段內容時也會犯同樣錯誤**（案例 2，2026-05-05 W17-110.2），規則 scope 應從「agent 行為層」擴為「ticket body content writer 行為層」。常見違規模式：

- 將實作內容包裝在自定義 H2（例：`## 變更摘要`、`## 修復摘要`、`## 驗證指令與結果`）
- Schema 章節（`## Solution`）保持空白或只剩原始 placeholder comment
- 結構上違反 W17-072，與 PC-110 root cause B（agent 自定義 H2 切斷 Schema section）形成共振

**Why**：規則寫入 agent-definition-standard 後，agent 在 prompt-time 不會主動載入該規則全文。若 dispatch prompt 未顯式提示 W17-072，agent 默認沿用「自定義 H2 較直觀」的習慣寫法，規則遞延效應失效。框架設計假設「規則寫到 agent definition 即生效」，但實際生效需 PM dispatch prompt 或 hook 雙通道強制。

**Consequence**：違規累積後 ticket body 無法被 type-aware schema 工具正確解析（PC-110 false negative 共振）；後人審查時 Schema 章節空白但實作內容散落自定義 H2，需手動重組。每個 W10-098 系列的剩餘子 ticket（10 個）都會重蹈覆轍，PM 需逐個 fix commit，成本是「每 ticket 多 1 commit + 多 1 兩 token 重組」。

**Action**：

PM 在派發實作類 agent 時，必於 prompt 末段顯式加入以下提示：

```
注意 ticket body 章節結構（W17-072）：
- 實作摘要寫在 ## Solution 下的 H3 子章節（### 變更摘要 / ### 設計決策 等）
- 禁止自創 ## 變更摘要 / ## 修復摘要 等 H2 標題
- Schema 章節間用 --- 分隔符隔開
```

**禁止**：派發 prompt 只寫 ticket id 與步驟而不提結構約束；假設 agent-definition-standard 自動載入。

**Hook 兜底**：W17-072 違規偵測寫在 acceptance-gate-hook，但屬 warning 級不阻擋 complete。若想強制阻擋（升 critical），須在 hook 規則層補強。本 PC 不主張立即升級為 blocking——agent 自律 + PM 提示應為主路徑，hook 為備援。

---

## 觸發案例

### 案例：W10-098.2 thyme dispatch（2026-05-05）

W10-098.2 派發 thyme-documentation-integrator 補 PROP-001 frontmatter evaluation_level=light。Thyme commit 59fa3dd5 完成功能（hook 通過、acceptance 全通過、complete 成功），但 ticket body 含違規結構：

#### 違規結構

```markdown
## Solution
<!-- Schema[DOC/Solution]: 免填（DOC 類型以變更摘要取代） -->

<!-- To be filled by executing agent -->

---

## 變更摘要        ← 違規：自定義 H2

### 修改檔案
...

### 變更內容
...

### 設計決策
...

### Hook 通過理由
...
## Test Results    ← 接續 H2，無 --- 分隔符
```

#### 修正後結構（commit b66494bb）

```markdown
## Solution
<!-- Schema[DOC/Solution]: 免填 -->

### 變更摘要
...

### 設計決策
...

### Hook 通過理由
...

---

## Test Results
```

#### 根因分析

- agent-definition-standard.md 含 W17-072 規則，但 thyme 在 dispatch prompt 中未被顯式提示
- thyme prompt-time 載入的是 AGENT_PRELOAD.md，未載入 W17-072 主文
- Dispatch prompt 內容只寫 ticket id 與步驟（claim → Edit → check-acceptance → commit → complete），未提結構約束
- Agent 默認用直觀寫法（H2 章節「變更摘要」），結構違規但功能正確

#### 影響範圍

W10-098 系列剩餘 10 子 ticket（W10-098.3/.4/.5/.6/.7/.8/.9/.10/.11 + W10-099 ANA）若不更新 dispatch prompt，會重複此模式。

---

### 案例 2：PM append-log 違反 W17-072（W17-110.2 / 2026-05-05）

PM（rosemary-project-manager）在 W17-110.2 ticket 寫 PM 協調紀錄、dispatch-plan、實驗結果矩陣時，使用 `ticket track append-log <id> --section "..."` 寫入內容，但內容開頭標題用 `## 標題` 而非 `### 標題`。

#### 違規結構（commit 前）

```markdown
## Problem Analysis
（原有內容）
---
## PM 協調紀錄（2026-05-05 session）  ← 違規：自定義 H2

### 預設執行條件檢查（已驗證）
...

## Solution
<!-- To be filled -->
---
## Dispatch Plan（PC-040 / agent-dispatch-template）  ← 違規：自定義 H2
...

## Test Results
<!-- To be filled -->
---
## 4 並行實驗結果矩陣（2026-05-05 session）  ← 違規：自定義 H2
...
```

#### 修正後結構

3 個自定義 H2 全降為 `### `（H3），讓內容歸屬正確 Schema section。complete hook 從 warning 轉為 pass。

#### 根因分析

- **Why**：W17-072 規則寫在 `agent-definition-standard.md`，rule scope 寫成 「agent 行為層」。PM 不會自動載入 agent definition（PM 自己讀 `pm-rules/`），規則對 PM 場景在認知上「不適用」。實質上 W17-072 的約束是「ticket body 章節結構」，actor 為 agent 還是 PM 屬同規則兩實例。
- **Consequence**：PM 違規會被 hook 偵測（同 W17-072 偵測機制覆蓋），但 PM 認知上不視為自己的規則範圍，第一次撰寫時就會犯。
- **Action**：見下方「修正方向」段（PC-123 scope 擴充 / W17-072 規則位置升級 / PM 自查）。

#### 修正方向

1. **PC-123 scope 擴充**（本次落地）：rule scope 從「agent 行為層」擴為「ticket body content writer 行為層」（agent + PM）。
2. **W17-072 規則位置升級**（建議 follow-up）：將「ticket body 章節結構規則」從 `agent-definition-standard.md`（agent 專屬）抽出為獨立規則檔（如 `rules/core/ticket-body-structure-rules.md`），PM 與 agent 雙方 auto-load。當前 hook 已偵測，補規則檔可降低首次違規率。
3. **PM 自查**：PM 用 append-log 寫長段內容時，先想「這段內容歸屬哪個 Schema section？」用 H3 子章節組織，避免 H2 切斷 Schema section。

#### 影響範圍

PM 用 ticket CLI append-log 寫內容的所有場景（W10-098 系列 PM 主動操作 ticket、W17-110 系列實驗協調、未來所有 PM 寫 dispatch-plan / coordination notes 的場景）。

---

## 與其他 PC 的關係

| PC | 相關性 |
|------|------|
| PC-110 root cause B | agent 自定義 H2 切斷 Schema section validator |
| PC-088 LLM tool selection bias | 同源：rule 寫了但 LLM 默認偏好直觀路徑 |
| PC-066 decision quality autopilot | 同源：規則自律機制與最需要它的場景負相關 |

---

## 預防措施

| 機制 | 角色 |
|------|------|
| Dispatch prompt template 加 W17-072 提示段 | 主路徑（agent 行為層約束） |
| acceptance-gate-hook warning | 備援（complete 前提示，不阻擋）|
| agent-definition-standard 加例題與 anti-pattern 範例 | 強化 agent 訓練資料 |
| PM 主動審 body 結構（commit 後快速檢） | 補救（已違規時手動修）|

**長期方向**：研究是否可在 prompt 載入機制做改善，讓 W17-072 等行為規範自動進入實作類 agent 的 prompt-time context，減少 PM dispatch prompt 重複貼提示的成本。
