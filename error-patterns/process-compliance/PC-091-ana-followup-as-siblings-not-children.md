---
id: PC-091
title: ANA Ticket 落地下游用兄弟而非子任務（血緣斷裂）
category: process-compliance
severity: medium
status: active
created: 2026-04-18
related:
- PC-040
- PC-058
---

# PC-091: ANA Ticket 落地下游用兄弟而非子任務（血緣斷裂）

> **2026-05-03 升格**：W17-120 多視角審查共識——本規則為「ANA 落地下游關係選擇」**唯一權威**。PC-073 對 ANA 衍生 IMP 用 spawned 的指引已 deprecated，由本規則取代。權威語意彙總：`.claude/skills/ticket/references/field-semantics.md`。

## 問題描述

PM 將 ANA Ticket 的「落地行動」（Solution 中提出的 IMP/DOC Ticket）建立為**兄弟 Ticket**（同 Wave 獨立編號）或**衍生 Ticket**（spawned_tickets），而非 ANA 的**子任務**（children），導致：

1. 血緣關係斷裂：`tree` / `chain` 命令看不到 ANA → 落地的延伸鏈
2. 編號語意誤導：W5-009（ANA）與 W5-043~046（落地）編號相距大，看似無關
3. 概念混淆：把 ANA 結論的「落地責任」誤當「衍生副產品」

## 觸發案例

**事件**（2026-04-18，0.18.0-W5-009）：

PM 完成 ANA Ticket 0.18.0-W5-009「檢討 PM 派發職責邊界」後，AC-4 要求「將結論落地為後續 IMP Ticket」。PM 執行：

```bash
ticket create --version 0.18.0 --wave 5 --action ... --type IMP ...
# (4 次，建立 W5-043, W5-044, W5-045, W5-046)
```

並把這 4 個 ID 寫入 W5-009 的 `spawned_tickets` 欄位。

用戶指出：「應建立為子任務而非兄弟任務」。

## 根本原因

### 表層原因
PM 沒使用 `--parent 0.18.0-W5-009` 參數。

### 深層原因
1. **概念混淆**：把「執行獨立性」（4 個 IMP 可獨立執行）誤當「血緣獨立性」（4 個 IMP 與 ANA 無關）
2. **語意邊界不明**：`spawned_tickets` 與 `children` / `parent_id` 的使用時機在規則中未明確區分
3. **規則缺失**：PM 規則中沒有明確指引「ANA 落地的 IMP/DOC Ticket 必為 children」

## 正確做法

| 場景 | 血緣選擇 | 命令 |
|------|---------|------|
| **ANA 結論的執行延伸（IMP/DOC 落地）** | **children**（直系後代，唯一選項） | `--parent <ANA-ID>` |
| 執行 Ticket 過程中發現獨立 bug / 技術債（與當前 ticket 無因果） | spawned_tickets（衍生副產品） | `--source-ticket <CURRENT-ID>` |
| 完全獨立的新需求 | sibling（同 Wave 獨立） | 不指定 parent / source |

> **重要**：ANA 落地不再有 spawned 選項。ANA 結論的 IMP/DOC 一律用 children（PC-091 路線）。spawned 保留給「執行 IMP / DOC 過程中發現獨立技術債」的場景（PC-073 殘存範圍）。
>
> **框架終局佐證**：`field-semantics.md` L115——「ANA spawned 阻擋是 children 路徑收斂前的過渡補丁，hook 重構後 ANA 落地統一走 children 路徑，spawned 對 ANA 回到不阻擋設計」。即 spawned 終將只表達「真衍生副產品」，不表達 ANA 落地。

> **盤點/規劃型 ANA 釐清（W8-025 Option A，2026-06-13）**：「交付物是計畫/盤點表」**不等於**「問題已解決」。盤點型 ANA（產出分類處置計畫，問題需後續清理才算解決）**仍是防護性 → 落地用 children，ANA 保持 in_progress 直到清理 children 完成**。
>
> **反模式（本 session W8-009 實證）**：盤點 ANA 用 children 撞 acceptance-gate「子任務未完成不可 complete」後，**誤改用 `spawned_tickets + --yes-spawned` 強制完成**——這繞過了「只診斷不開藥」保護，且牴觸 L115。正確處置：盤點 ANA 維持 in_progress，等清理 children 完成才 complete（清理延後則 ANA 跨 round 開著，由 `stuck-anas` + session-start「Spawned 推進清單」追蹤，不強制本輪 complete）。
>
> **禁止**：用 `spawned + --yes-spawned` 表達 ANA 落地以繞過 acceptance-gate。

### 判別問題（建立 Ticket 前自問）

> 這個 Ticket 的存在是因為「上游 ANA Ticket 的結論要求落地」嗎？
>
> - 是 → children（用 `--parent <ANA-ID>`）— **適用所有 ANA 衍生 IMP / DOC，含盤點/規劃型 ANA 的清理落地**
> - 否，但發現於執行中（與當前 ticket 無因果）→ spawned_tickets（用 `--source-ticket`）
> - 否，是獨立發現 / 規劃 → sibling
>
> **陷阱**：別把盤點 ANA 的清理當成「衍生副產品」（spawned）——清理是盤點結論的**執行延伸（落地）**，必為 children。spawned 只給「執行中意外發現、與當前 ticket 無因果」的工作（如 W8-013 審查中發現的 W8-015/016 新需求）。

## 補救措施（觸發案例）

1. 編輯 W5-009 frontmatter：`children: [W5-043, W5-044, W5-045, W5-046]`，`spawned_tickets: []`
2. 編輯 W5-043~046 frontmatter：`parent_id: 0.18.0-W5-009`，`source_ticket: 0.18.0-W5-009`
3. `ticket track tree 0.18.0-W5-009` 驗證血緣鏈顯示正確

## 預防措施

### Hook 防護建議
- ANA Ticket complete 時，檢查 Solution 區段是否提及「落地 / 後續 Ticket / 建立 IMP」等關鍵字
- 若有，且 children 為空且 spawned_tickets 也為空 → 警告「ANA 落地 Ticket 應為 children」

### 規則更新
- `.claude/pm-rules/plan-to-ticket-flow.md` 或 `ticket-lifecycle.md`：增加「ANA 落地下游用 children」明示
- ticket SKILL.md create 範例：補強「ANA Solution → IMP 落地」場景的 `--parent` 用法

## 相關規則 / 經驗

- `.claude/skills/ticket/references/field-semantics.md` — 六欄位語意 SSOT（含用戶情境對照表與決策樹）
- PC-073 — `spawned_tickets` 對「執行中發現獨立技術債」的殘存指引（ANA 衍生段落已 deprecated）
- PC-040 — Context 存 Ticket 不存 Prompt（Ticket Context Bundle）
- PC-058 — ANA created Ticket metadata drift（ANA 建立的 Ticket 派發前必查 metadata）
- ticket SKILL.md — `--parent` 參數說明
- `feedback_ana_followup_completeness` — 分析結論落地必須逐項對照

---

**Last Updated**: 2026-06-13
**Version**: 1.2.0 — W8-025 Option A 釐清（非改規則，補邊界）：盤點/規劃型 ANA「交付物是計畫」不等於「問題已解決」，仍是防護性 → children + 保持 in_progress 至清理完成；補反模式「禁用 spawned + --yes-spawned 表達 ANA 落地繞 gate」（本 session W8-009 實證）+ field-semantics L115 框架終局佐證。children 唯一路線不變
**Version**: 1.1.0 — W17-120 多視角審查升格為 ANA 落地唯一權威，PC-073 對 ANA 衍生 IMP 的指引已併入 deprecated；範圍確立、引用 field-semantics.md SSOT
**Version**: 1.0.0 — 2026-04-18 W5-009 觸發案例首發
