---
id: PC-115
title: subagent 對 .claude/ Edit 被 runtime 拒絕且無 hook 訊息
category: process-compliance
severity: high
created: 2026-05-02
source_ticket: 0.18.0-W17-097
related_pc:
  - PC-040
  - PC-114
related_arch:
  - ARCH-015
---

## 症狀

subagent 派發後嘗試 Edit/Write 主 repo `.claude/` 下檔案：

- Edit 工具回傳「Permission to use Edit has been denied」
- 無 hook stderr 訊息（非 exit 2 deny）
- `.claude/hook-logs/` 全目錄無相關紀錄
- 同 session 同檔案，PM 主線程 Edit 立即成功

## 根因（**已收斂**：候選 1 transient runtime 強支持；Hypothesis K 強形式已否證 / 候選 5、2 已否證 / 候選 3 弱否證）

**狀態：已收斂為候選 1 transient runtime fluctuation**（W17-110 ANA + 4 子實驗閉環，2026-05-07）。Hypothesis K（session 級 prefix-based 權限快取需 PM 暖機）於 2026-05-02 21:00 新 session 三階段對照實驗中被決定性否證；後續 W17-110 規劃 4 子實驗（W17-110.1/.2/.3/.4）按 ROI 順序執行，累計 18/18 Edit success，候選 5/2 強否證、候選 3 弱否證、候選 1（transient runtime）強支持（base rate 0% < 5% 門檻）。W17-097.1-.4 DENY 4/4 真實根因 = transient runtime fluctuation。歷史對照詳見 `docs/work-logs/v0/v0.18/v0.18.0/tickets/0.18.0-W17-108.md`、`0.18.0-W17-109.md` 與 `0.18.0-W17-110.md`。

### Hypothesis K（已否證的工作假設，保留作歷史紀錄）

原推論：CC v2.1.126 對 subagent `.claude/` Edit 有「session 級 prefix-based 權限快取」：

- session 內**首次** subagent `.claude/` Edit 觸發互動式 permission prompt
- 在 subagent 無 UI 環境下，prompt 自動 deny
- **PM 互動式 Edit 過 `.claude/` 任一檔**會在 session 中快取「`.claude/` 已授權」
- 之後 subagent `.claude/` Edit 都繼承快取 → success（即使是不同檔，因為 prefix-based 涵蓋整個 `.claude/`）

**否證證據**（W17-108 Phase A）：本 session PM 從未 Edit `.claude/`，subagent 對 `.claude/methodologies/atomic-ticket-methodology.md` 兩次 Edit 皆 success。預測為 deny，實測為 success。

### 新 session 三階段對照實驗矩陣（W17-108/109，2026-05-02 21:00）

| 階段 | PM 已 Edit `.claude/` | Subagent 目標檔 | Subagent Edit 結果 | 對 Hypothesis K |
|------|--------------------|---------------|------------------|----------------|
| A (W17-108) | 否（冷快取）| atomic-ticket-methodology.md | success x2 | **否證強形式** |
| B | PM 自己 Edit + revert atomic-ticket-methodology.md | — | — | 觸發暖機 |
| C (W17-109) | 是（不同檔） | comment-writing-methodology.md | success x2 | 與 A 相同無差異 |

A=success 否決強形式 K（「需 PM 暖機」）；C=success 證實「暖機後對不同檔也 success」但因 A 已 success，C 無法獨立支持任何假設。

### 五輪歷史實驗矩陣（W17-097～W17-103，與 Hypothesis K 預測相符但已被新 session 反例推翻）

| 實驗 | 並行 | Edit 內容 | PM 已 Edit `.claude/` 任一檔 | 結果 |
|-----|----|----|----|----|
| W17-097.1-.4 | 4 | 複雜（import + 8 替換）| 否 | DENY 4/4 |
| W17-099 | 1 | 簡單 | 是 | success |
| W17-100 (E1) | 1 | 複雜 | 是 | success |
| W17-101.1-.4 (E2) | 4 | 簡單 | 是 | success 4/4 |
| W17-102 (Test G) | 1 | 簡單（PM 未碰過該檔）| 是（其他檔已 Edit）| success |

並行/Edit 複雜度/prompt 結構/PM 接觸該檔（檔案層級）四個變因被獨立否證。剩下 prefix 層級 PM 接觸史與五實驗結果**全相符且零反例**——但 2026-05-02 21:00 新 session Phase A 提供反例：冷快取下 subagent Edit 兩次皆 success，五輪結果並非「Hypothesis K 唯一解釋」。

### 驗證對照（同一 session, 19:33:49 同一時點）

| Actor | Path | Branch | Hooks 結果 | permissionMode | Result |
|-------|------|--------|----------|----------------|--------|
| PM 主線程 | .claude/skills/ticket/lifecycle.py | main | 全 exit 0 | n/a | SUCCESS |
| thyme subagent | 同上 | main | 全 exit 0 | bypassPermissions | DENIED |

唯一差異 = `agentId`（subagent vs PM）。

### 不可覆蓋的三層

| 機制 | 是否影響 deny | 證據 |
|------|------------|------|
| Hook 系統（PreToolUse Edit）| 否 | 5 個 hook（main-thread-edit-restriction / branch-verify / file-type-permission / ticket-path-guard / ticket-file-access-guard）全 exit 0 allow |
| settings.json `permissions.allow` | 否 | 含 `Edit`/`Write` 但 subagent 仍拒 |
| agent frontmatter `permissionMode: bypassPermissions` | 否 | thyme 已設 bypassPermissions 仍拒 |

### 機制推論

CC runtime 設計層保護「框架資產自我修改」：subagent 若能任意改 `.claude/hooks/`、`.claude/agents/`、`.claude/skills/`，可繞過用戶授權系統。`permissionMode: bypassPermissions` 只覆蓋 hook 層 + settings 層，不覆蓋 runtime hardcoded protection。

### 診斷不可見性

deny 訊息為標準 CC 模板「Permission to use Edit has been denied. IMPORTANT: ...」，無 hook stderr 訊息，無 `.claude/hook-logs/` 紀錄。所有 PreToolUse hook 顯示 allow，故診斷時容易誤判為 hook 問題。

### 歷史軌跡

- 2026-04-13 ARCH-015 原結論：「.claude/ 一律被擋」
- 2026-04-18 重驗（v2.1.114）：「主 repo 樹內 .claude/ 可寫」（feedback_arch015_boundary_refinement）
- 2026-05-02 19:33 W17-097.1-.4（v2.1.126）：4 並行 thyme 全 deny（PM 該 session 從未 Edit `.claude/`）
- 2026-05-02 20:21 W17-099 重測（同 session 50 分鐘後）：1 個 thyme 成功 Edit + revert（PM 該 session 已多次 Edit `.claude/`）
- 2026-05-02 20:35-20:55 E1/E2/Test G 三組對照實驗，五輪結果與 Hypothesis K 全相符
- 2026-05-02 W17-103 整合：提出 prefix-based session cache 推論 + 新 session 驗證 prompt
- **2026-05-02 21:00 W17-108/109（新 session，v2.1.126）三階段對照**：
  - Phase A 冷快取（PM 從未 Edit `.claude/`，目標 atomic-ticket-methodology.md）：subagent Edit 兩次皆 success
  - Phase B PM 自己 Edit + revert atomic-ticket-methodology.md
  - Phase C 暖機後不同檔（comment-writing-methodology.md）：subagent Edit 兩次皆 success
  - **結論**：Hypothesis K 強形式被決定性否證；W17-097.1-.4 DENY 4/4 的真實根因仍未識別

## 候選假設驗證結果（W17-110 收斂，2026-05-05 ~ 05-07）

W17-110 ANA 規劃 4 子實驗按 ROI 順序執行，全部 success，結論收斂為候選 1（transient runtime）強支持。

| 候選 | ROI 排序 | 描述 | 區辨設計 | 驗證 ticket | 結果 | 結論 |
|------|---------|------|---------|-----------|------|------|
| 5 | #1 | prompt 內容觸發特殊 audit | 單派 thyme 用 W17-097.1 完整 prompt 風格複刻（import 修改 + commit/pytest 提及） | W17-110.1 | 2/2 success | **否證**：相同 prompt 風格冷快取單派可成功 |
| 2 | #2 | 並行 + 複雜 Edit 組合 | 4 thyme 並行各對不同檔案做 import 替換 + revert | W17-110.2 | 8/8 success（4×2） | **否證**：並行 + 複雜 + 冷三維組合不觸發 deny |
| 3 | #3 | session 累積狀態（commit + pytest） | 累積 2 commit + pytest 後測單發 marker Edit | W17-110.3 | 2/2 success | **弱否證**：當前累積（2 commit）不及 W17-097 baseline（5 commit），需更高累積樣本才能強否證 |
| 1 | #4 | transient runtime base rate | 連續多 cold session 重複 Phase A，計算 deny 比率 | W17-110.4 | 6/6 success（3 session × 2） | **強支持**：base rate 0%（< 5% 門檻），W17-097.1-.4 deny 為罕見 transient runtime |
| 4 | trigger | CC 版本內部變化（同版號波動） | 記錄各 deny 案例 CC build；CC 升級後在 PC-115 補新版本 Phase A 重測 | 觸發條件式 | 待 CC 升級 | 開放等待 |

**收斂說明**：W17-097.1-.4 DENY 4/4 真實根因 = transient runtime fluctuation（候選 1）。後續若 `.claude/` Edit 再 deny，視為 transient；累積 ≥ 3 次新 deny 才重啟調查（候選 3 / 4 需更高樣本驗證時的 trigger）。

**Trigger 機制**（W17-154 落地）：

| 步驟 | 動作 |
|------|------|
| 記錄方式 | PM 觀察到 subagent 對 `.claude/` Edit deny 時，手動寫入下方「Deny 事件累積」表（hook 對 runtime deny 是盲的，僅手動可行） |
| 門檻動作 | 寫入第 3 行時必須同時建立 ANA ticket（標題：「重啟調查 PC-115 / ARCH-015 subagent .claude/ Edit deny 真因（trigger ≥3 達標）」），並在「處理動作」欄填入 ticket ID |
| 計數歸零 | trigger 觸發 + 對應 ANA ticket 進入 in_progress 後，計數歸零重新累積（避免單一研究循環反覆觸發） |

## Base Rate 觀察（W17-110.4 多 session 累積中）

**目的**：累積 ≥3 個獨立冷快取 session 資料點，計算 subagent `.claude/` Edit deny 的 base rate，區辨 W17-097.1-.4 的 4/4 deny 是「真 transient runtime」（候選 1）還是「未識別系統性變因」。

**Phase A 標準操作**（每 session 重複）：
1. 全新 session 啟動（/clear 後）
2. PM 從未 Edit/Write `.claude/`（僅 Read/Bash/CLI tool 不破壞冷快取）
3. 派發單發 thyme 對 `.claude/methodologies/atomic-ticket-methodology.md` 做 2 次 Edit（append marker `<!-- experiment-w17-110-4-marker -->` + revert）
4. 紀錄結果與環境變因

**資料點累積表**：

| # | 日期 | Session 起始 | CC 版本 | PM Edit `.claude/` | Subagent 先前 Edit `.claude/` | Commit 數 | pytest | Edit 1 | Edit 2 | 來源 ticket |
|---|------|-------------|---------|--------------------|------------------------------|-----------|--------|--------|--------|-----------|
| 1 | 2026-05-05 | T17:44 | Opus 4.7 (claude-opus-4-7[1m]) | 否 | 否（首次） | 0 | 否 | success | success | W17-110.4 |
| 2 | 2026-05-05 | 新 session（/clear 後） | Opus 4.7 (claude-opus-4-7[1m]) | 否 | 否 | 0 | 否 | success | success | W17-110.4 |
| 3 | 2026-05-05 | 新 session（/clear 後）| 2.1.128 | 否 | 否 | 0 | 否 | success | success | W17-110.4 |

**目前累積**：3 / 3+ 資料點；當前 deny 比率 = 0/6 = 0%（達結論門檻 < 5%）

**結論（Session 3 後達門檻）**：候選 1（transient runtime）強支持。PC-115 結論：W17-097.1-.4 deny 為罕見 transient runtime 事件，不需深查。三個獨立 session（含 /clear 冷快取）共 6 次 Edit 全部 success，0 deny，base rate 為 0%，遠低於 5% 門檻。後續若再次出現 `.claude/` Edit deny，仍視為 transient 而非系統性問題；累積 ≥ 3 次新 deny 才重啟調查。

**判定門檻**（W17-110.4 ticket 規定）：

| Deny 比率 | 結論 |
|-----------|------|
| < 5% | 候選 1（transient runtime）強支持 — PC-115 結論為「罕見 transient，不需深查」 |
| 5-20% | 仍可能有未識別變因，需重啟 widen 找其他候選 |
| > 20% | 必有系統性變因未識別，反模式 2 警告生效 |

**反模式自查**（W17-104 + W17-110）：

- 反模式 2（偶發標籤化）：累積 < 3 資料點不可標籤化「transient」
- 反模式 4（推翻後仍 anchor）：每個資料點獨立解讀，不立即下「transient」結論

## 候選假設新增：並行派發 + `.claude/` Edit interaction（W17-177 ANA 落地）

**證據**（saffron ANA 統計，2026-05-10）：

| 場景 | 案例 | Edit 數 | success | deny |
|------|------|---------|---------|------|
| 並行派發（2+ subagent 同時對 `.claude/` Edit） | W17-097.1-.4（4 並行 thyme） + W17-174.2.1/.3/.4（3 並行 thyme） | 7 | 0 | **7** |
| 非並行（單發或非同時 subagent） | W17-108/109/110.1-.4 全部 + 其他歷史 | 18 | **18** | 0 |

**Why（中等證據）**：7/7 deny vs 18/18 success 的對比強烈指向「並行派發 + `.claude/` Edit interaction」為主導變因。並非「冷快取」「session 累積」「frontmatter」「MCP 工具誤選」等既有候選。

**未否證項**：對照組實驗（新 cold session 執行非並行單發 thyme 對 `.claude/` 真實任務 Edit）尚未執行（W17-177 AC5 deferred）。若該實驗 success → 強化並行假設；若 deny → 否證並行假設並 widen 重啟。

**即時防護（W17-177.1 落地）**：`.claude/pm-rules/parallel-dispatch.md` §`.claude/` 修改類並行數限 ≤ 2 — 禁止 3+ 並行派發 `.claude/` 修改類 ticket。

## Deny 事件累積（trigger ≥3 重啟調查 — W17-154 落地）

**目的**：累計 base rate 觀察結論之後新出現的 `.claude/` Edit deny 案例。寫入第 3 行時 PM 必須建立 ANA ticket 重啟調查（trigger 機制詳見上方收斂說明）。

**累積表**（W17-154 設計，計數從 W17-097.1-.4 收斂後新出現的 deny 開始）：

| # | 日期 | Session 起始 | 案例 ticket | 檔案路徑 | cwd | CC 版本 | 處理動作 |
|---|------|-------------|------------|---------|-----|---------|---------|
| 1 | 2026-05-09 | （session 起始時點待補） | 0.18.0-W17-174.2.1 | `.claude/hooks/*.py` | 主 repo | （CC 版本待補） | 並入 W17-177 ANA |
| 2 | 2026-05-09 | （session 起始時點待補） | 0.18.0-W17-174.3 | `.claude/pm-rules/*.md` | 主 repo | （CC 版本待補） | 並入 W17-177 ANA |
| 3 | 2026-05-09 | （session 起始時點待補） | 0.18.0-W17-174.4 | `.claude/pm-rules/` + `.claude/error-patterns/` | 主 repo | （CC 版本待補） | 觸發 trigger → 建立 W17-177（重啟調查） |

**目前累計**：3（已達 trigger 門檻 → W17-177 已建立 → 計數待 W17-177 進入 in_progress 後歸零）

**注意**：W17-097.1-.4 的 4 次 deny 屬於 base rate 觀察前的 baseline 案例，不計入本表（已由 Base Rate 觀察段落分析）。本表僅紀錄收斂結論之後新出現的 deny。

## 防護（**已下調**：Hypothesis K 暖機建議撤回）

| 層級 | 機制 |
|------|------|
| 派發策略 | subagent 對主 repo 樹內 `.claude/` Edit **可預期 success**（W17-099 / 100 / 101 / 102 / 108 / 109 共 9 次連續 success）。例外只剩 W17-097.1-.4 那 4 次未解 deny |
| 失敗回應 | 若實際遭遇 deny（罕見），PM 立即接手 Edit 即可——同時修復本任務 + 為記錄收集資料 |
| 暖機建議 | **撤回**（Phase A 已否證需要暖機） |
| 記憶更新 | feedback_arch015_boundary_refinement.md 同步否證結論 |

## 觸發案例

W17-097：ANA 規劃 5 個 IMP children，前 4 個並行派發 thyme-python-developer 修改 `.claude/skills/ticket/`，全部 Edit deny。PM 接手 W17-097.3 即時成功（commit d357fefd）。

## 鑑別診斷

| 訊號 | 對應 PC |
|------|---------|
| 主 repo `.claude/` Edit 被 runtime 拒絕（無 hook 訊息） | **本 PC-115** |
| 派發前 hook 阻擋（agent-dispatch-validation） | PC-114 |
| MCP write tool 對 text file 被擋 | PC-112 |
| Edit 成功但 prompt 缺 context | PC-040 |

## 重啟調查鏈案例

PC-115 結論收斂後，「累積 ≥ 3 次新 deny 才重啟調查」屬於「ANA 結論被後續實驗推翻」的元模式。本節記錄此模式在其他主題上的觸發案例，作為 retrospective 學習素材（W17-182 ANA 將分析「ANA 宣稱已修妥的驗證義務」方法論缺口）。

### 案例 1：W17-179 → W17-181（handoff stale GC，2026-05-10）

| 階段 | Ticket | 結論 | 事後驗證 |
|------|--------|------|---------|
| 初次 ANA | W17-179 | stop hook 行為正確，false alarm（saffron-system-analyst）| **被推翻** |
| 重啟調查 | W17-181 | lib `handoff_utils` L49/L102 走舊路徑，子進程環境 100% 重現 false negative | 確認為真根因（ARCH-020 延伸案例）|

**重啟觸發**：W17-179 complete 後手動清除 `.stop-blocked` flag 觸發 stop hook，發現兩筆已 completed ticket（W17-174 / W17-178.1）的 handoff JSON 仍未被 GC，與 W17-179 結論矛盾。

**方法論缺口**：W17-179 saffron 只 grep stop hook 自定義函式（W17-165 / W17-176.2.1 已修），未掃 lib 層 callers，導致誤判「已修妥」。屬 PC-115 描述的「結論狀態不可僅憑單點驗證」更廣模式。

**承接學習**：W17-182 retrospective ANA 將提煉為獨立 PC pattern（「ANA 宣稱已修妥的驗證義務」）；ARCH-020 v1.1 已升級「同名 predicate 多處實作即高風險訊號」判別準則（W17-181.3 落地）。

## W1-068 三方 Deadlock 變體（2026-05-25 實證）

PC-115 transient runtime fluctuation 與 `.claude/` 修改場景的派發流程 hook 互動，形成可預測的 deadlock 模式：

| 約束 | 來源 | 行為 |
|------|------|------|
| 實作代理人強制 isolation:worktree | `agent-dispatch-validation-hook` | 派發實作 agent（thyme-* / parsley-*）必須加 `isolation: "worktree"` |
| `.claude/` Edit 在 isolation:worktree 下可能 deny | PC-115 主結論 transient runtime fluctuation | 某些時段 subagent 對 `.claude/` Edit 被 runtime deny（無 hook 訊息） |
| worktree 派發前 main 不可有未 commit 變更 | `worktree-commit-before-dispatch-hook` | 違反 PC-019 阻擋派發 |

**Why（為何此三約束組合形成必然 deadlock）**：三約束各自合理（worktree 隔離保護 main 工作區 / PC-115 transient 可恢復 / commit-before-dispatch 防 stash 遺失），但組合場景下無單一層可獨立解除——PM 主線程是唯一不受三約束的角色。

**Consequence（不認知此模式的成本）**：若無此認知，PM 遇到 worktree subagent `.claude/` Edit deny 會反覆重派（PC-115 transient 重派仍可能 deny），消耗 token 與 wave 時間後才回到 fallback；最壞情境是誤判為 agent 能力缺陷而拆 ticket 或重設計範圍。

**三約束疊加 → Deadlock**：

當 IMP ticket 需要修改 `.claude/` 時：

1. 派發 agent 必須加 `isolation: "worktree"`（強制）
2. 但 worktree subagent 對 `.claude/` Edit 可能被 runtime deny（PC-115 機率事件）
3. 若預先 PM 自己 Edit `.claude/` 又會被 worktree-commit-before-dispatch-hook 阻擋（除非先 commit）
4. 即使 commit 後派發，subagent 仍可能因 PC-115 transient deny 失敗

**唯一可靠突破口**：**PM 主線程 fallback 接手執行** — PM 主線程無 isolation 限制，可直接 Edit `.claude/`。Subagent 在 needs_context 狀態回報完整補料指引後，PM 接手 N 步驟（Edit + 測試 + pytest + reinstall + 文件同步）即可完成。

### W1-068 實證案例

| 階段 | 結果 |
|------|------|
| 派發 thyme-python-developer + isolation:worktree | hook 強制 worktree 通過 |
| Subagent 嘗試 Edit `track_acceptance.py` | runtime deny（PC-115 transient） |
| Subagent 回報 needs_context + 完整補料指引 | success（agent 知道自己無法完成並提供精確指引） |
| PM 主線程 fallback：Edit + pytest 27/27 全綠 + uv reinstall + 文件同步 | success |
| W1-068 acceptance 4/4 通過、commit f4aade8a | success |

此案例驗證兩點：(a) Subagent 在 needs_context 狀態能完整回報補料指引，自我認知失敗邊界準確（不會硬撐造成更大破壞）；(b) PM 主線程 fallback 為 PC-115 transient + worktree 約束疊加場景的可靠突破口。後續同模式案例應沿此流程處理：派發失敗 → 接收 needs_context + 補料指引 → PM 直接執行（不重派）。

### 衍生方法論建議（待 W17-182 retrospective 評估）

**核心原則**：派發決策應依 `.claude/` 修改佔比與 deadlock 風險權衡；佔比越高、worktree 安全範圍越窄，越偏向 PM 直接執行。下表為此原則的場景化展開：

| 場景 | 預設策略 |
|------|---------|
| IMP ticket 範圍純 `.claude/` 修改且小規模（< 10 步驟） | 評估直接 PM 主線程執行（跳過派發 agent） |
| IMP ticket 範圍含 `.claude/` 與其他 worktree 安全範圍 | 派發 agent 嘗試；失敗回報 needs_context 即由 PM fallback |
| Agent 回報 needs_context 對 `.claude/` Edit 失敗 | 立即 PM fallback，不重派（PC-115 transient 重派仍可能 deny） |

## 後續觀察

- CC 升級或 setting 變更後重驗（記錄版本號 + 日期）
- 若用戶 setting 可關閉此限制，補充至本 PC
- 重啟調查鏈案例累積 ≥ 3 次同模式（ANA 結論被後續實驗推翻）時，獨立提煉為 PC pattern（W17-182 retrospective 啟動）
- W1-068 deadlock 變體再次出現時，評估是否升級為獨立 PC（目前合併於本 PC-115 末章節）
