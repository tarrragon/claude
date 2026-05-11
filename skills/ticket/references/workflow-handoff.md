# 交接與恢復流程決策樹

此決策樹描述 Ticket 交接和恢復的完整流程。

> **理論基礎**：交接對應「任務鏈三種移動方向」（父↔子、兄弟↔兄弟），見 `.claude/methodologies/atomic-ticket-methodology.md` 的「任務鏈核心哲學」章節。

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

**覆蓋指令**：

- [x] `/ticket handoff` - 自動判斷交接
- [x] `/ticket handoff --to-parent` - 返回父任務
- [x] `/ticket handoff --to-child <id>` - 切換到子任務
- [x] `/ticket handoff --to-sibling <id>` - 切換到兄弟任務
- [x] `/ticket handoff --next <target-id>` - 絕對指向下 session 該做的 ticket（W17-164）
- [x] `/ticket handoff --status` - 查看交接狀態

## 狀態-命令映射規則

**根據 Ticket 當前狀態選擇旗標**：

| Ticket 狀態 | 適用旗標 | 說明 |
|-------------|---------|------|
| `completed` | 不加旗標（或 `--to-parent` / `--to-sibling <id>`） | 任務已完成，切換到下一個任務 |
| `in_progress` | `--context-refresh` | 任務未完成，在新 session 以乾淨 context 繼續 |
| `in_progress`（被子任務阻塞） | `--to-child <id>` | 先切換到子任務，解除阻塞 |

**禁止行為**：

| 禁止 | 說明 |
|------|------|
| 在 `completed` ticket 使用 `--context-refresh` | `--context-refresh` 僅適用 `in_progress` 狀態，在 completed 上會直接報錯 |
| 在 `in_progress` ticket 使用 `--to-sibling` / `--to-parent` | 任務未完成不可切換，CLI 會拒絕 |

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

**核心原則**：handoff 是任務鏈內的 context 交接工具，不是通用任務路由器。任務鏈結束後，使用 `/ticket` 重新選擇下一個任務。

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

**覆蓋指令**：

- [x] `/ticket resume <id>` - 恢復特定任務
- [x] `/ticket resume --list` - 列出待恢復任務

---

**Last Updated**: 2026-05-08
**Version**: 1.1.0 — 同步 W17-164：交接決策樹新增「絕對指向（target_ticket_id）」分支，加入 `--next` 模式對比表與覆蓋指令
**Source**: 0.18.0-W17-164
