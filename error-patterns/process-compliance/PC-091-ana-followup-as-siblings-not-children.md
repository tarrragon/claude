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

### 判別問題（建立 Ticket 前自問）

> 這個 Ticket 的存在是因為「上游 ANA Ticket 的結論要求落地」嗎？
>
> - 是 → children（用 `--parent <ANA-ID>`）— 適用所有 ANA 衍生 IMP / DOC
> - 否，但發現於執行中（與當前 ticket 無因果）→ spawned_tickets（用 `--source-ticket`）
> - 否，是獨立發現 / 規劃 → sibling

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

**Last Updated**: 2026-05-03
**Version**: 1.1.0 — W17-120 多視角審查升格為 ANA 落地唯一權威，PC-073 對 ANA 衍生 IMP 的指引已併入 deprecated；範圍確立、引用 field-semantics.md SSOT
**Version**: 1.0.0 — 2026-04-18 W5-009 觸發案例首發
