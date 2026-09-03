---
id: PC-GPD-004
title: 派發前工具清單核對只查 Bash，漏查寫檔工具
category: process-compliance
severity: medium
source_case: 2026-09-02 元件契約 skill 撰寫票的多輪審查 downstream frame
created: 2026-09-02
---

# PC-GPD-004: 派發前工具清單核對只查 Bash，漏查寫檔工具

## 症狀

DOC 型 ticket 派給工具清單只有 Read / Grep / Glob / LS 與符號級 MCP 寫入工具的代理人。該代理人無 Write / Edit，符號級工具對 `.md` 的寫入又被工具選擇 guard 阻擋，等於無法產出票面要求的文件。缺口在派發階段不可見，要到執行者開工才撞牆，或由審查者在旁路徑發現。

## 根因

| 層級 | 機制 |
|------|------|
| L1 規則覆蓋面 | 既有派發前核對只有一條「工具清單不含 Bash → 不派 ANA 型 ticket」（quality-baseline 規則 5 情境表），針對的是「無法呼叫 ticket CLI 落地 spawn」；「不含寫檔工具 → 不派 DOC 型 ticket」沒有對應條文 |
| L2 職責與工具脫節 | 代理人定義以職責命名（UI/UX 系統規範專家），PM 依職責選人；工具清單在 frontmatter 另一處，選人時不在視線內 |
| L3 歷史成功遮蔽 | 同一代理人先前完成過審查型 DOC 票（產出寫進 ticket body 由 CLI 承載），使「它能做 DOC」被泛化為「它能寫檔」 |

## 案例

一張元件契約 spec 票派給 UI/UX 系統規範代理人。多輪審查的 downstream frame 拿該票套用新 skill 的執行者表時發現：該代理人工具清單無 Write / Edit / Bash，無法寫 spec 檔也無法建票；skill 當時只處理了「不含 Bash」這一道牆。改派具 Write / Edit / Bash 的介面設計代理人，理由記入票面 NeedsContext。

## 防護

**Why**：代理人能不能完成一張票，取決於它的工具清單能不能觸及票面 where.files 列出的路徑，職責名稱只是選人的第一道篩選。

**Consequence**：漏查寫檔工具的派發會在執行者開工時才失敗，代價是一次派發的 context 與一次重派；若執行者改用符號級工具硬寫，會被 guard 拒絕後自行早停（PC-112 形態）。

**Action**：

| 派發前核對 | 通過條件 |
|-----------|---------|
| 票面 where.files 含 `.md` / `.yaml` 等非程式碼檔的產出或修改 | 代理人工具清單含 Write 或 Edit；只有 `mcp__serena__*` 寫入工具者不算（對非程式碼檔會被 guard 拒絕） |
| 票面 acceptance 含建票、回填他票、spawn 落地 | 代理人工具清單含 Bash；無者於派發階段把該步驟移出 acceptance，改為 NeedsContext 列出由 PM 代做 |
| 票面 where.files 含程式碼檔 | 代理人工具清單含 Edit / Write，或該語言的 MCP 寫入工具 |

核對位置：派發前讀代理人定義的 frontmatter `tools` 欄，與票面 where.files 逐一對照；不以「它做過同型票」代替核對。

## 相關

- `.claude/rules/core/quality-baseline.md` 規則 5 情境表「工具清單不含 Bash」列（本模式是其寫檔工具的對偶）
- `.claude/rules/core/tool-selection.md`（符號級寫入工具對非程式碼檔被拒的機制）
- `.claude/error-patterns/process-compliance/PC-112-subagent-mcp-write-tool-misselection-on-text-files.md`
- `.claude/skills/component-contract-design/SKILL.md`〈執行者與簽核者〉（本模式在該 skill 的落地）
