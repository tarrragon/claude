# Agent Authoring Guide

本文件定義撰寫 Claude Code subagent（`.claude/agents/*.md`）時的規範，涵蓋所有可用 frontmatter 欄位的選擇原則與場景範例。

> **核心教訓來源**：PC-059（retry5 模式）與 worktree 絕對路徑權限教訓

---

## 完整 Frontmatter 欄位總覽

| 欄位 | 必填 | 類型 | 說明 |
|------|------|------|------|
| `name` | 是 | string | 代理人識別名稱（kebab-case） |
| `description` | 是 | string | 核心職責描述（50-100 字），含觸發條件 |
| `tools` / `allowed-tools` | 是 | string | 允許使用的工具清單，逗號分隔 |
| `model` | 建議 | string | 使用的模型（haiku/sonnet/opus/inherit） |
| `color` | 建議 | string | 代理人顏色標記（UI 識別用） |
| `permissionMode` | 條件必填 | string | Runtime 權限模式；含 Edit/Write 的代理人必填 |
| `effort` | 建議 | string | 推理深度（low/medium/high）；已有的代理人多設 low |
| `maxTurns` | 選填 | integer | 代理人最大輪數上限 |
| `background` | 選填 | boolean | 是否強制以背景模式執行 |
| `initialPrompt` | 選填 | string | 代理人啟動時自動提交的首輪 prompt |
| `disallowedTools` | 選填 | string | 明確禁用的工具清單，覆蓋 tools 允許清單 |
| `hooks` | 選填 | object | 代理人生命週期 Hook（PreToolUse/PostToolUse/Stop） |

---

## 新增欄位詳細說明

### initialPrompt — 自動首輪 Prompt

代理人啟動時無需 PM 額外說明，自動提交的第一輪文字。適用於有固定開頭工作流程的代理人（如必讀特定檔案、必先查詢 Ticket 狀態）。

**使用場景**：

| 場景 | 範例 |
|------|------|
| 實作代理人啟動時強制讀取 AGENT_PRELOAD | `Read .claude/agents/AGENT_PRELOAD.md 以取得工作規範` |
| 監控代理人啟動時先查詢當前 in_progress tickets | `ticket track list --status in_progress` |
| 格式化代理人啟動時先確認 lint 設定 | `Read .eslintrc.json 確認格式規則` |

**範例**：

```yaml
---
name: mint-format-specialist
initialPrompt: "Read docs/project-conventions.md 確認本專案格式規範後，再開始執行格式化任務。"
---
```

**Why**：代理人在派發 prompt 之外無法主動讀取規範，若首輪就進入任務執行，前置準備步驟容易被跳過。`initialPrompt` 強制代理人在接收任務前完成前置準備，確保工作規範已讀取。

**注意**：`initialPrompt` 在 PM 派發 prompt 之前執行；若 PM 的 prompt 本身已包含前置指令，`initialPrompt` 仍會先執行一次，需避免重複動作。

---

### memory — 記憶範圍控制

控制代理人可存取的 memory 層級，分三個範圍。

| 值 | 範圍 | 適用場景 |
|----|------|---------|
| `user` | 全用戶跨專案記憶（`~/.claude/` 下） | 記錄用戶偏好、通用規則；只讀建議 |
| `project` | 當前專案記憶（`.claude/` 下） | 專案特定規則、error-pattern；大多數代理人 |
| `local` | 僅工作階段記憶（不持久化） | 一次性任務、安全考量高的代理人 |

**範例**：

```yaml
---
name: clove-security-reviewer
memory: local
---
```

**Why**：不同 memory scope 影響代理人能讀寫的記憶範圍。`user` scope 跨專案可見，若代理人記入敏感路徑或專案特定資訊，會污染其他專案的記憶上下文。`local` scope 僅限當前 session，任務結束後自動清除，適合安全敏感或一次性任務。

**Consequence**：未明確設定 memory scope 時，代理人繼承主 session 的 scope（通常為 `project`）；若代理人工作涉及敏感路徑或外部系統認證，建議顯性設為 `local` 防止意外持久化。

安全審查代理人設 `local` 防止敏感路徑資訊洩漏到跨 session 記憶。

---

### permissionMode — Runtime 授權模式

（本節為現有規範，補充確認說明）

`frontmatter.tools` 宣告的是代理人可使用的工具清單，不是 runtime 實際授權。兩者語義不同：

| 層級 | 作用 |
|------|------|
| `tools` frontmatter | 限制代理人能呼叫哪些工具（工具白名單） |
| `permissionMode` frontmatter | 決定被呼叫的工具如何通過權限檢查（runtime 授權模式） |
| `settings.local.json` `permissions.allow` | 對 subagent 無效，僅控制主線程權限 |

---

### hooks — 代理人生命週期 Hook

代理人可在自身的 frontmatter 內宣告 Hook，不依賴全域 `settings.json`。支援三個觸發點：

| Hook 類型 | 觸發時機 | 適用場景 |
|----------|---------|---------|
| `PreToolUse` | 代理人呼叫任何工具之前 | 驗證呼叫參數、記錄工具使用意圖 |
| `PostToolUse` | 代理人工具呼叫返回之後 | 驗證工具輸出、自動觸發後續動作 |
| `Stop` | 代理人任務結束時 | 清理資源、自動 complete ticket、寫 worklog |

**範例（Stop Hook 自動 complete ticket）**：

```yaml
---
name: thyme-python-developer
hooks:
  Stop:
    - matcher: ""
      hooks:
        - type: command
          command: "python3 .claude/hooks/auto-complete-on-stop.py"
---
```

**注意**：Agent-level hooks 與全域 `settings.json` hooks 共存，不互相覆蓋。代理人層 hooks 僅在該代理人執行期間生效。

---

### background — 強制背景執行

設為 `true` 時，代理人一律以背景模式執行，PM 派發後立刻釋放主線程。

**使用場景**：

| 場景 | 是否建議 background: true |
|------|--------------------------|
| 長時間編譯/測試任務（> 30 秒） | 是 |
| 需要 PM 等待結果再決策的短任務 | 否 |
| 並行派發多個代理人 | 是（每個設 true 或 PM 用 background flag 派發） |
| 互動式確認型任務（需 PM 回應） | 否 |

**範例**：

```yaml
---
name: coriander-integration-tester
background: true
---
```

---

### effort — 推理深度

控制代理人使用的推理計算資源，影響輸出品質與速度/成本的取捨。

| 值 | 推理深度 | 適用場景 |
|----|---------|---------|
| `low` | 標準推理（預設） | 大多數任務；當前 40+ 代理人多設此值 |
| `medium` | 增強推理 | 複雜架構決策、多步驟分析 |
| `high` | 最深推理 | 需要最大思考深度的系統設計、根因分析 |

**判斷原則**：`effort` 與 `model` 獨立控制。高難度任務先考慮升級 `model`（opus/opus-1m），`effort: high` 用於同 model 下需要更深思考的場景。

**範例**：

```yaml
---
name: saffron-system-analyst
model: claude-opus-4-6[1m]
effort: low
---
```

注意：XL 閱讀量任務（saffron/bay）使用 1m model，`effort` 仍設 `low` — 讀取量問題用 model 解決，推理深度問題才用 effort 解決。

---

### maxTurns — 最大輪數限制

設定代理人在單次派發中可執行的最大工具呼叫輪數。超過後代理人自動停止並回報現況。

**使用場景**：

| 場景 | 建議值 |
|------|--------|
| 格式化、重命名等機械性任務 | 20-30（防止迴圈） |
| 複雜實作（多檔案修改 + 測試） | 50-80 |
| 分析型代理人（只讀） | 30-40 |
| 無限制（依賴 CC 預設） | 不設此欄位 |

**範例**：

```yaml
---
name: mint-format-specialist
maxTurns: 25
---
```

**注意**：`maxTurns` 是安全網，不是執行保證。任務拆分仍是降低回合耗盡的根本解法（見 `cognitive-load.md`）。

---

### disallowedTools — 明確禁用工具

與 `tools`（允許清單）相反，`disallowedTools` 明確列出即使 `tools` 允許也不可使用的工具。用於在高層框架已授權、但特定代理人應受限的場景。

**使用場景**：

| 場景 | 禁用工具 |
|------|---------|
| 唯讀分析代理人（防止意外寫入） | `Edit, Write, mcp__serena__replace_content` |
| 安全審查代理人（防止修改被審查檔案） | `Edit, Write` |
| 策略規劃代理人（只產出建議不改程式碼） | `Edit, Write, Bash` |

**範例**：

```yaml
---
name: clove-security-reviewer
tools: Read, Grep, Glob, Bash
disallowedTools: Edit, Write
---
```

**注意**：`disallowedTools` 比 `tools` 優先；若 `tools: Edit, Write` 同時有 `disallowedTools: Edit`，Edit 仍被禁用。

---

## permissionMode 為何重要

`frontmatter.tools` 宣告的是**代理人可使用的工具清單**，不是**runtime 實際授權**。兩者語義不同：

| 層級 | 作用 |
|------|------|
| `tools` frontmatter | 限制代理人能呼叫哪些工具（工具白名單） |
| `permissionMode` frontmatter | 決定被呼叫的工具如何通過權限檢查（runtime 授權模式） |
| `settings.local.json` `permissions.allow` | **對 subagent 無效**，僅控制主線程權限 |

派發背景代理人時若無正確的 `permissionMode`，工具權限提示無人互動批准，自動拒絕，代理人降級為規劃模式。

---

## permissionMode 合法值

| 值 | 行為 | 適用場景 |
|----|------|---------|
| `default`（預設） | 標準檢查含提示；背景派發自動拒 | 避免用於實作類代理人 |
| `acceptEdits` | 自動接受 **cwd 或 `additionalDirectories`** 內的 Edit/Write | 主 repo cwd 內編輯的代理人 |
| `auto` | 由分類器評估批准與否 | 中等信任度 |
| `dontAsk` | 自動拒（`permissions.allow` 仍有效） | 僅讀取類代理人 |
| `bypassPermissions` | 跳過大部分提示；`.claude/commands`、`.claude/agents`、`.claude/skills` 在此模式下允許；`.git`、其他 `.claude/` 子目錄仍提示 | 實作類代理人的慣例值（但見下方 worktree 陷阱） |
| `plan` | 唯讀探索模式 | Phase 1/3a 規劃類代理人 |

官方參考：https://code.claude.com/docs/en/sub-agents#permission-modes

---

## 選擇矩陣

| 代理人類型 | 典型工具 | 建議 permissionMode |
|-----------|---------|---------------------|
| 實作代理人（thyme/parsley/fennel/cinnamon 等） | Edit、Write、Bash | `bypassPermissions` |
| 策略規劃代理人（pepper/sage） | Edit、Write、Read | `bypassPermissions`（會寫策略 `.md`） |
| 規格設計代理人（lavender） | Write、Edit、Read | `bypassPermissions`（會寫 spec `.md`） |
| Hook 開發代理人（basil-hook-architect） | Write、Edit | `bypassPermissions` |
| 審查／稽核代理人（linux、bay-quality-auditor、clove-security-reviewer） | Read、Grep、Bash | 不設定（預設 default），純讀取不需寫權限 |
| 派發／分析代理人（rosemary、incident-responder、saffron） | Read、Grep、Bash | 不設定（預設 default） |

**判斷原則**：代理人 `tools` 清單含 `Edit` 或 `Write` 時，**必須**加 `permissionMode: bypassPermissions`。純讀取代理人不需要。

---

## 標準 Frontmatter 範例

實作代理人：

```yaml
---
name: thyme-python-developer
description: Python 開發專家...
tools: Edit, Write, Read, Bash, Grep, LS, Glob
permissionMode: bypassPermissions
color: green
model: opus
effort: low
---
```

插入位置：`tools:` 之後、`color:` 之前。

---

## Worktree 陷阱（歷史教訓）

`permissionMode` 不是萬靈丹，它受 **subagent cwd** 限制：

### 根因

- subagent 繼承主 session 的 cwd（通常是主 repo）
- 若 PM 派發時指定 **worktree 的絕對路徑**（例如 `/Users/xxx/project-feature-branch/.claude/agents/`），subagent 視這個路徑為「cwd 外部」
- `acceptEdits` 只認 cwd 或 `additionalDirectories`，worktree 外部編輯被拒
- `bypassPermissions` 的「`.claude/agents` 允許」判斷也可能基於 cwd 相對路徑識別，worktree 絕對路徑可能無法觸發例外

### 症狀

代理人回報 `Permission to use Edit has been denied.`，即使 frontmatter 已有 `permissionMode: bypassPermissions`。

### 解法（依優先序）

1. **PM 在主 repo 的 feature branch 直接執行框架配置修改**（`.claude/agents/`、`.claude/rules/` 等屬於框架層，不是產品程式碼）。
2. **將 worktree 路徑加入 `settings.local.json` 的 `permissions.additionalDirectories`**，配合 `acceptEdits`。缺點是每個 worktree 都要手動維護。
3. **派發代理人時避免使用 worktree 絕對路徑**——讓代理人在主 repo cwd 下操作，完成後由 PM checkout 到 feature branch 合併。

### 禁止

| 禁止行為 | 原因 |
|---------|------|
| prompt 中要求代理人 `cd` 到 worktree | 環境的 `chpwd` shell hook 會觸發 `ls` 淹沒代理人輸出（IMP-056） |
| 相信「frontmatter 設了 `bypassPermissions` 就沒問題」 | 經驗證在 worktree 外部絕對路徑仍可能被拒 |

---

## 錯誤嘗試（已驗證無效）

| 嘗試 | 為何無效 |
|------|---------|
| `settings.local.json` 加 `permissions.allow: ["Edit"]` | 僅對主線程生效，subagent 獨立由 `permissionMode` 控制 |
| `settings.local.json` 加 `permissions.allow: ["Edit(**)"]` 或路徑 pattern | 同上，對 subagent 無效 |
| 僅依賴 `tools: Edit, Write` 宣告 | 只授予「工具可呼叫權」，不是 runtime 批准權 |

---

## 檢查清單（新增／修改代理人時）

- [ ] 代理人 `tools` 含 `Edit` 或 `Write`？→ 必須加 `permissionMode: bypassPermissions`
- [ ] 代理人會被背景派發？→ 必須有 `permissionMode`（避免預設 `default` 自動拒）
- [ ] 派發時目標路徑是否在主 repo cwd 內？→ 若否，改走 PM 直接執行或設 `additionalDirectories`
- [ ] `name`、`description`、`tools` 三欄必填？
- [ ] 引用 `AGENT_PRELOAD.md`？
- [ ] **唯讀分析型代理人**（不需 Ticket ID 即可派發，如 Explore/code-explorer/Plan 類型）？→ 確認是否需加入 `.claude/hooks/agent-ticket-validation-hook.py` 的 `TICKET_EXEMPT_AGENT_TYPES` 白名單，否則該代理人會因 prompt 不含 Ticket ID 被 deny（W10-043.1 audit P2 風險）

---

## Model 選擇指南

### 歷史教訓（2026-04-16 更新）

早期誤以為代理人失敗主因是「context 不足」，將所有代理人 model 統一升級至 opus 1m。後來確認真正原因是**代理人的回合限制（tool call ~20）**，非 context。統一升級造成簡單任務也用 opus 1m，浪費成本與速度。

**提醒**：model 選擇解決的是「決策品質 / 成本」問題；回合限制問題需另行處理（任務拆分、cognitive load 降低等）。

### 4 維度評分

新增代理人時，先就以下 4 維度評估該代理人的典型任務：

| 維度 | 評估問題 | 等級 |
|------|---------|------|
| **閱讀量** | 每次呼叫需讀取的檔案規模 | S(單檔) / M(數檔) / L(整模組) / XL(跨模組或整 codebase) |
| **決策複雜度** | 任務本質是機械執行還是設計判斷 | 低(機械) / 中(規則推理) / 高(設計判斷) / 極高(架構決策) |
| **輸出量** | 典型輸出長度 | 短(摘要/清單) / 中(結構化分析) / 長(完整程式碼/規格) |
| **對話深度** | subagent 內部輪數 | 單輪 / 2-3 輪 / 多輪 |

### Model 分類標準

| 類別 | model 值 | 適用條件 |
|------|---------|---------|
| **D - 1M Context** | `claude-opus-4-6[1m]` | 閱讀量 = XL，系統級審查，需跨模組累積上下文 |
| **C - Opus** | `opus` | 決策複雜度 ≥ 高，或實作代理人（品質關鍵） |
| **B - Sonnet** | `sonnet` | 決策複雜度 = 中（規則推理），結構化任務 |
| **A - Haiku** | `haiku` | 決策複雜度 = 低（機械執行），單檔格式修復類 |
| **Main** | `inherit` | 主線程代理人（如 rosemary-project-manager） |

### Model 選擇 checklist

- [ ] 代理人是否需要讀取 > 200k tokens 的上下文？→ **D (opus 1m)**
- [ ] 代理人是否做架構/設計判斷或生產程式碼？→ **C (opus)**
- [ ] 代理人是否基於明確規則做結構化產出？→ **B (sonnet)**
- [ ] 代理人是否純機械執行（格式、重命名等）？→ **A (haiku)**
- [ ] 代理人是主線程 PM？→ **inherit**

### 當前代理人分類（2026-04-16 W9-005 執行結果）

| 類別 | 數量 | 代表代理人 |
|------|------|-----------|
| D (1m) | 2 | saffron-system-analyst, bay-quality-auditor |
| C (opus) | 15 | linux, cinnamon, parsley, fennel, thyme-extension 等實作/設計類 |
| B (sonnet) | 7 | acceptance-auditor, coriander, project-compliance 等規則驗證類 |
| A (haiku) | 1 | mint-format-specialist |
| inherit | 1 | rosemary-project-manager |

---

## 代理人升級建議清單

以下為現有代理人透過補充 CC 2.1.x frontmatter 欄位可獲益的評估結果。建議作為後續獨立 Ticket 的規劃線索，本清單不執行升級。

| 代理人 | 建議新增欄位 | 理由 | 預期效益 |
|--------|-----------|------|---------|
| `thyme-extension-engineer` | `permissionMode: bypassPermissions` | 目前無 permissionMode，且 `allowed-tools` 格式非標準 `tools`；若背景派發規劃類任務，缺少授權模式會自動拒絕 | 背景派發不卡權限提示；`allowed-tools` 應改為 `tools` 對齊格式規範 |
| `acceptance-auditor` | `maxTurns: 40` | 驗收流程須逐一讀取多個章節並比對，易達到回合限制；設上限可讓代理人提前回報缺口而非無聲停止 | 超出 ticket 體積時能提前回報而非靜默截斷 |
| `coriander-integration-tester` | `background: true`、`maxTurns: 50` | 整合測試執行時間長，PM 等待結果浪費前台；`allowed-tools` 應改為標準 `tools` | PM 可並行進行下個 ticket 規劃；測試輪數多時不提前截斷 |
| `bay-quality-auditor` | `maxTurns: 60` | 跨模組審計需讀取大量檔案，`model: claude-opus-4-6[1m]` 可處理 context 但輪數限制仍可能截斷大型 codebase 審計 | 大型審計不被輪數截斷；`allowed-tools` 應改為標準 `tools` |
| `ginger-performance-tuner` | `maxTurns: 40`，`allowed-tools` 改 `tools` | 效能分析需讀取多個效能相關檔案；`allowed-tools` 為非標準格式 | 格式標準化；複雜效能分析輪數不截斷 |
| `clove-security-reviewer` | `disallowedTools: Edit, Write`，`allowed-tools` 改 `tools` | 安全審查代理人不應修改被審查的程式碼；目前只靠職責說明約束，缺乏 frontmatter 強制層 | 從框架層防止意外寫入，比規則說明更可靠；`allowed-tools` 格式對齊 |
| `rosemary-project-manager` | `maxTurns: 80` | PM 主線程在複雜 Wave 規劃（多 ticket 分析 + AUQ 決策循環）中可能達到輪數上限；設明確值讓截斷可預期 | 長 session 規劃不無聲截斷；超限時能提前提示用戶 |
| `oregano-data-miner` | `effort: medium` | 資料提取策略規劃需深度分析 DOM 結構和資料驗證規則，目前 `sonnet` + `low` 組合可能對複雜策略輸出品質不足 | 複雜 DOM 分析策略品質提升；`effort: medium` 在同 model 下加深推理 |
| `incident-responder` | `maxTurns: 35` | 事件回應需讀取 error log、相關 ticket、error-pattern；任務體積可控但若不設限當遇複雜 incident 可能截斷 | 複雜 incident 分析不截斷；超出預設輪數能提前警告 |
| `basil-writing-critic` | `maxTurns: 40` | 文字審查需逐段讀取長文件並對照規則；大型 rules/methodology 文件審查易超出預設輪數 | 長文件審查不截斷；提前知曉輪數預算可分段派發 |
| `saffron-system-analyst` | `maxTurns: 70` | XL 閱讀量系統分析需讀取整個 codebase + 多份規格文件；1m context 足夠但輪數仍可能截斷多步驟分析流程 | 大型系統分析不被輪數截斷；分析結論完整輸出 |
| `thyme-documentation-integrator` | `maxTurns: 40` | 文件整合任務需讀取多份方法論 + 目標文件 + 驗證引用；`acceptEdits` 模式下跨多文件操作輪數消耗快 | 跨多文件整合任務不截斷；對照本任務觸發場景可驗證 |

### 升級優先序建議

| 優先級 | 代理人群組 | 原因 |
|--------|-----------|------|
| 高 | `thyme-extension-engineer`、`coriander-integration-tester`、`clove-security-reviewer`、`bay-quality-auditor`、`ginger-performance-tuner` | `allowed-tools` 非標準格式需改為 `tools`；格式問題影響 frontmatter 解析正確性 |
| 中 | `acceptance-auditor`、`incident-responder`、`basil-writing-critic`、`thyme-documentation-integrator` | 加 `maxTurns` 防截斷；對高頻使用代理人效果顯著 |
| 低 | `rosemary-project-manager`、`oregano-data-miner`、`saffron-system-analyst` | 優化但非緊急；主線程 `maxTurns` 改動需審慎驗證 |

---

## 相關文件

- `.claude/error-patterns/process-compliance/PC-059-agent-tools-vs-runtime-permission.md` — 完整錯誤模式
- `.claude/agents/AGENT_PRELOAD.md` — 代理人共用前置知識
- `.claude/rules/core/pm-role.md` — PM 派發角色邊界
- permissionMode 與 worktree 路徑的歷史修復紀錄（詳見 PC-059）
- 代理人 model 重新評估歷史：W9-005（2026-04-16）

---

**Last Updated**: 2026-05-13
**Version**: 1.2.0 — 新增 CC 2.1.x 完整 frontmatter 欄位說明（8 欄位：initialPrompt/memory/permissionMode 確認/hooks/background/effort/maxTurns/disallowedTools，每欄位含場景範例）+ 代理人升級建議清單（13 個代理人，含優先序分級）（0.18.0-W6-005）
**Version**: 1.1.0 — 新增 Model 選擇指南（W9-005 落地）
**Source**: PC-059 retry5 模式調查結論 + W9-005 代理人 model 重新評估
