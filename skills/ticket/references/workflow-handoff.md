# 交接與恢復流程決策樹

`/ticket handoff` 與 `/ticket resume` 共用本樹：交接方向判斷、狀態對應旗標、任務鏈結束後的替代流程、恢復時的載入方式。

> **理論基礎**：交接對應「任務鏈三種移動方向」（父↔子、兄弟↔兄弟），見 `.claude/methodologies/atomic-ticket-methodology.md` 的「任務鏈核心哲學」章節。

> **何時讀**：需要判斷任務鏈交接方向（子→父/父→子/兄弟→兄弟/絕對指向）、狀態與命令映射、任務鏈結束時的替代流程，或恢復流程時查閱。**亦由此進入**：`SKILL.md` 子命令路由表 `resume` 列（該列註明「交接/恢復決策樹與 `handoff` 共用 `references/workflow-handoff.md`，見上列」，是 `resume` 命令讀者被送到本檔的入口）。
>
> **同目錄**：`handoff-command.md`（`source` vs `target` 指向語意、五種自動判向情境）、`resume-command.md`（`resume` 用法、參數與 handoff JSON 格式）。
>
> **溯源**：匯入時已存在，無拆分點。

本檔章節：〈交接流程決策樹〉〈狀態-命令映射規則〉〈任務鏈結束決策樹〉〈恢復流程決策樹〉。

## 交接流程決策樹

```
[交接流程]
    |
    v
┌─ 已知下個 target ticket id? ─┐
│                              │
是（絕對指向，W17-164）         否
│                              │
v                              v
/ticket handoff                ┌─ 知道方向? ─┐
  --next <target-id>           │             │
  --from-ticket-id <src>       否            是
       │                       │             │
       │                       v             v
       │                   /ticket           ┌─ 交接方向? ────────────────┐
       │                   handoff           │                            │
       │                   (自動判斷)        父任務        子任務        兄弟任務
       │                                     │             │             │
       │                                     v             v             v
       │                                /ticket        /ticket       /ticket
       │                                handoff        handoff       handoff
       │                                --to-parent    --to-child    --to-sibling
       │                                               <id>          <id>
       │                                                                  │
       └──────────────────────────────────────────────────────────────────┤
                                                                          v
                                                                   [產生 Handoff 檔案]
                                                                          │
                                                                          v
                                                                   [等待恢復]
```

**絕對指向 vs 相對方向**（W17-164 / L2-A）：

| 模式 | 旗標 | 寫入欄位 | 適用情境 |
|------|------|---------|---------|
| 絕對指向 | `--next <target-id>` | `target_ticket_id` 直填 | PM 已知下 session 該做的 ticket id（含跨任務鏈、跨 Wave） |
| 相對方向 | `--to-parent` / `--to-child <id>` / `--to-sibling <id>` | `direction` 欄位 + (可選) `target_ticket_id` 後綴 | 仍在任務鏈內，依血緣關係指向 |
| 自動判斷 | 無旗標 | 由 CLI 推導 | 任務鏈線性繼續 |

讀取端（GC / SessionStart hint / Stop hook / resume）統一透過 `handoff_utils.resolve_target(record)` 解析：優先 `target_ticket_id` > fallback `direction` 後綴。詳見 `references/handoff-command.md`「指向語意：source vs target」。

**本樹涵蓋的命令**：

- `/ticket handoff` - 自動判斷交接
- `/ticket handoff --to-parent` - 返回父任務
- `/ticket handoff --to-child <id>` - 切換到子任務
- `/ticket handoff --to-sibling <id>` - 切換到兄弟任務
- `/ticket handoff --next <target-id>` - 絕對指向下 session 該做的 ticket（W17-164）
- `/ticket handoff --status` - 查看交接狀態

## 狀態-命令映射規則

完整表（含 `completed` 狀態下 `--to-child` 分支、wave-level 交接、兩條禁止行為）以 `handoff-command.md`〈按 Ticket 狀態選擇命令〉為準；本節僅為前置決策路徑，交接方向判斷見上方〈交接流程決策樹〉。

## 任務鏈結束決策樹

當 completed ticket 無有效 handoff 目標時：

```
[Ticket completed]
    |
    v
有子任務/兄弟待處理?
    |
    +── 是 → /ticket handoff <id> --to-child/--to-sibling <target>
    |
    +── 否（任務鏈結束）
         |
         v
    /ticket（回到任務入口，查看所有待辦）
         |
         +── 同 Wave 有 pending → 選擇任務認領
         +── Wave 全部完成 → Wave 收尾流程
```

**核心原則**：見 `handoff-command.md`〈移動方向與旗標對照〉首句。任務鏈結束後，使用 `/ticket` 重新選擇下一個任務。

## 恢復流程決策樹

```
[恢復流程]
    |
    v
┌─ 知道 ID? ─┐
│            │
否           是
│            │
v            v
/ticket      /ticket
resume       resume <id>
--list           │
│                v
v           [載入 Context]
[顯示待恢復]     │
     │           v
     └──────► [繼續執行流程]
```

**本樹涵蓋的命令**：

- `/ticket resume <id>` - 恢復特定任務
- `/ticket resume --list` - 列出待恢復任務
