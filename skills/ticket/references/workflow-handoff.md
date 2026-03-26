# 交接與恢復流程決策樹

此決策樹描述 Ticket 交接和恢復的完整流程。

## 交接流程決策樹

```
[交接流程]
    |
    v
┌─ 知道方向? ─┐
│             │
否            是
│             │
v             v
/ticket       ┌─ 交接方向? ────────────────┐
handoff       │                            │
(自動判斷)    父任務        子任務        兄弟任務
              │             │             │
              v             v             v
         /ticket        /ticket       /ticket
         handoff        handoff       handoff
         --to-parent    --to-child    --to-sibling
                        <id>          <id>
                            │
                            v
                     [產生 Handoff 檔案]
                            │
                            v
                     [等待恢復]
```

**覆蓋指令**：

- [x] `/ticket handoff` - 自動判斷交接
- [x] `/ticket handoff --to-parent` - 返回父任務
- [x] `/ticket handoff --to-child <id>` - 切換到子任務
- [x] `/ticket handoff --to-sibling <id>` - 切換到兄弟任務
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
