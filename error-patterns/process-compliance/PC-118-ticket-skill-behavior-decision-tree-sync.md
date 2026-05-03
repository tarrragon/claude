---
id: PC-118
title: ticket skill 行為變更未同步決策層（行為層 ↔ 決策層耦合鬆散）
category: process-compliance
severity: medium
status: active
created: 2026-05-03
related:
- PC-066
- PC-091
- PC-093
- PC-099
- PC-110
---

# PC-118: ticket skill 行為變更未同步決策層（行為層 ↔ 決策層耦合鬆散）

## 問題描述

修改 ticket skill 程式邏輯（`.claude/skills/ticket/ticket_system/`）後，相關決策層文件（`.claude/pm-rules/decision-tree.md`、`pm-rules/*.md`、`skills/ticket/SKILL.md`）未同步更新，導致 PM 依據過時路由做決策。

行為層（ticket CLI 程式邏輯）與決策層（PM 規則、決策樹）的耦合鬆散是根本問題——程式碼可直接修改，但決策文件需要人類事後同步思考。當前無自動化或強制性機制連結兩者，僅靠 PM 自律，而自律在壓力情境下系統性失效（PC-066）。

**Why**：ticket skill 是 PM 日常執行最頻繁使用的工具，行為語意的任何變更都直接影響 PM 的決策路由。若決策層文件落後，PM 使用過時 SOP 執行任務，輕則指令失效，重則產生不一致的 ticket 血緣關係或流程狀態。

**Consequence**：行為層與決策層分歧累積後，PM 在新 session 啟動時讀到的規則與 CLI 實際行為不一致，導致隱性錯誤——不會立刻報錯，但決策路由靜默偏差，只在驗收或事後 audit 時才被發現。

**Action**：ticket skill src 每次行為性改動後，在同一 commit 或衍生 DOC ticket 中同步掃描並更新決策層文件（掃描指令：`grep -rln 'ticket track' .claude/pm-rules/`）。三層防護（PC-118 描述 + W17-115.2 規則 + W17-115.3 hook）組合使用，不依賴單一機制。

---

## 觸發案例

### 案例 1：W17-113（禁用無 trigger 延後決策原則）

**事件**（2026-05-03，0.18.0-W17）：

ticket skill 多次行為變更（runqueue 取代 next/schedule/resume-hint、append-log `--section` 必填、type-aware body schema 影響 complete 條件）後，PM 於 W17-113 才補強「禁用無 ticket trigger 延後決策」原則至 `decision-tree.md`。

此原則的必要性在 ticket skill 行為確立時即已存在，但決策層文件未跟上行為層演進。W17-113 是典型的**事後補償**：原則本應在相關 CLI 行為設計階段同步建立，而非在多個 Wave 後才補入。

### 案例 2：W17-114（決策樹閉環流程）

**事件**（2026-05-03，0.18.0-W17）：

`execution-discovery-rules.md`「遇到問題的閉環流程」（識別 → 建 ANA/DOC ticket → 規劃分析/驗證/實驗 → 執行 → 釐清結案）同樣是在 ticket skill CLI 行為趨於穩定後，才由 W17-114 補入決策樹。

決策樹的「遇到問題時的合法 5 步」依賴 ticket CLI 子命令（`ticket track check-acceptance`、`ticket track complete` 等）的具體行為，但兩者的更新週期完全分離。

### 共同特徵

兩案例均出現於 0.18.0-W17，由 W17-115 ANA 分析確認為同類事後補償模式。ticket skill 近 50 個 commit 中，重大行為變更（CLI 子命令介面、body schema、runqueue 邏輯）多次發生，但 `decision-tree.md` 同期 30 個 commit 中，事後補償性更新佔可見比例，決策樹對 `ticket track` / `/ticket` 引用僅 4 次（量化結果來源：W17-115 ANA 實驗）。

---

## 根本原因

### 表層原因

ticket skill src 改動時，沒有強制機制要求同步掃描 `.claude/pm-rules/` 下引用 `ticket track` 的段落；依賴 PM 事後察覺，而事後察覺在 context 沉重時系統性失效（PC-066）。

### 深層原因

| 原因類型 | 說明 |
|---------|------|
| 耦合鬆散 | 行為層（程式邏輯）與決策層（PM 規則）屬不同維護路徑，無共同生命週期機制 |
| 自律負相關 | Context 使用率高時，PM 主動觸發同步掃描的機率系統性下降（PC-066 根因） |
| 缺乏可見邊界 | 「行為變更」與「文件變更」之間無明確邊界提示，PM 容易誤以為程式 commit 即完成 |
| Memory 沉澱滯後 | Memory feedback 雖已記錄原則（ticket skill 行為變更需同步檢查決策樹），但缺結構化落地，無強制觸發 |

---

## 正確做法

三層組合防護（W17-115 ANA 結論「採 A+B+C」）：

| 層次 | 機制 | 觸發時機 |
|------|------|---------|
| **A. PC 描述層**（本文件） | 提供反模式依據，供 PM 回顧與平行評估引用 | PM 閱讀 PC 索引 / parallel-evaluation 強制對照 |
| **B. 規則層**（W17-115.2） | `rules/core/` 或 `pm-rules/` 中增加「ticket skill 行為變更同步檢查」清單 | ticket skill src 每次 commit 前自律掃描 |
| **C. hook 自動化層**（W17-115.3） | PostToolUse Bash hook：`git commit` 完成且 commit 含 `.claude/skills/ticket/ticket_system/**` 改動時，輸出提示（掃描清單 + 指令） | 每次 ticket skill src 被 commit 時自動觸發 |

### 掃描清單（行為變更後須核對的決策層文件）

| 文件 | 核對重點 |
|------|---------|
| `.claude/skills/ticket/SKILL.md` | 子命令對外契約是否仍準確 |
| `.claude/pm-rules/decision-tree.md` | 決策路由中引用的 `ticket track` 子命令是否存在 |
| `.claude/pm-rules/ticket-lifecycle.md` | Ticket 狀態流轉步驟是否對應 CLI 行為 |
| `.claude/pm-rules/session-switching-sop.md` | Resume / handoff 流程的 CLI 指令是否仍有效 |
| `.claude/pm-rules/parallel-dispatch.md` | 並行派發的 commit 策略是否對應 CLI 行為 |

### 判別準則（何謂「行為變更性質」commit）

| commit type | 是否需同步掃描決策層 |
|------------|------------------|
| `feat: 新增子命令或 flag` | 是 |
| `refactor: 重命名子命令或改變語意` | 是 |
| `fix: bug 修正但 CLI 介面不變` | 否（建議仍快速確認） |
| `test: 測試案例` | 否 |
| `docs: 文件修正` | 否 |

---

## 相關規則與 Pattern

| 相關 | 關聯角度 |
|------|---------|
| PC-066 | 自律機制與壓力負相關——rule 層單獨使用的局限性，hook 需作兜底 |
| PC-091 | ANA followup 必為 children——W17-115.1/2/3 均為 W17-115 ANA 的子任務（正確血緣示範） |
| PC-093 | 無 trigger 延後決策——W17-113 / W17-114 的事後補償屬 PC-093 的延後決策變體 |
| PC-099 | meta hook 自我引用誤報——W17-115.3 hook 設計必考量 meta 防護 |
| PC-110 | body-check false negative via schema separator——hook 偵測邏輯需防止誤判 |
| `rules/core/decision-trigger-binding.md` | 決策必綁 ticket trigger；W17-113 / W17-114 補償即違反此規則的具體案例 |

---

**Last Updated**: 2026-05-03
**Version**: 1.0.0
**Source**: W17-115 ANA（三路徑 ROI 評估）+ W17-113 / W17-114 事後補償案例 + PC-066 自律壓力負相關
