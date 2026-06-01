# IMP-075: ticket set-acceptance --check 多個 index 參數可能只勾選最後一個

## 基本資訊

- **Pattern ID**: IMP-075
- **分類**: 實作 bug（implementation）
- **來源版本**: v0.19.0
- **發現日期**: 2026-05-25
- **風險等級**: 低（功能正確性受影響但有 workaround）
- **影響範圍**: `ticket track set-acceptance <id> --check <index>` 與 `--uncheck <index>` 多次傳參的行為

---

## 問題描述

### 症狀

執行 `ticket track set-acceptance <id> --check 1 --check 2` 預期同時勾選 index 1 與 2，實際只勾選了 index 2（最後一個傳入值），index 1 保持原狀。

可觀察訊號：

```
$ ticket track set-acceptance 0.19.0-W1-002.2 --check 1 --check 2
[INFO] 0.19.0-W1-002.2 勾選 index [2]：變更 1 項

$ grep -E "^- '?\[[ x]\]" docs/work-logs/.../0.19.0-W1-002.2.md | head -2
- '[ ] 在 1 個 clean Chrome profile 下...'    # index 1 未勾
- '[x] 本 ticket Test Results 章節...'        # index 2 已勾
```

訊息提示「勾選 index [2]」（單一值），確認 argparse 只取最後一個。

### 表現形式

| 預期行為 | 實際行為 |
|---------|---------|
| `--check 1 --check 2` 同時勾選兩個 | 只勾選最後一個（index 2） |
| 顯示「勾選 index [1, 2]」 | 顯示「勾選 index [2]」 |

### Workaround

分次呼叫：

```bash
ticket track set-acceptance <id> --check 1
ticket track set-acceptance <id> --check 2
```

或使用 `check-acceptance` 命令（語意可能不同，需查 help 確認）。

---

## 根因（待驗證）

`--check` 參數可能在 argparse 中宣告為 `action='store'`（單值覆蓋）而非 `action='append'` / `nargs='+'`（累積或多值）。SKILL.md 描述：

> `set-acceptance --check <index> / --uncheck <index>`（可多個）

文件說「可多個」但實作可能未支援多次傳參累積。

### 待確認問題

1. 是 argparse 宣告問題還是業務邏輯只取 args 最後值？
2. `--uncheck` 是否有相同問題？
3. `--all-check` / `--all-uncheck` 行為是否一致？

---

## 防護機制

| 層級 | 防護動作 |
|------|---------|
| 文件層 | SKILL.md 補充明示「目前需分次呼叫」直到 CLI 修復 |
| 用戶端 workaround | PM/agent 多 index 勾選時分次呼叫，不依賴單一命令累積 |
| 待開 Ticket | 修復 argparse 宣告為 `action='append'` 或 `nargs='+'`，並補 CLI 測試 |

---

## 案例

### Case 1: 2026-05-25 W1-002.2 收尾

PM 執行 `ticket track set-acceptance 0.19.0-W1-002.2 --check 1 --check 2`，預期同時勾兩項。實際只勾選 index 2，PM 補執行 `--check 1` 才完成兩項勾選。

---

## 抽象層級分析（必填）

| 欄位 | 內容 |
|------|------|
| 症狀層級 | 工具層（`ticket track set-acceptance --check` CLI 行為與 SKILL.md 文件描述不符） |
| 根因層級 | 實作層（argparse 參數宣告為 `action='store'` 單值覆蓋，未設為 `action='append'` 多值累積） |
| 跨層路徑 | N/A；症狀與根因同層（工具層 / 實作層高度重疊，CLI 行為即為實作直接表現） |
| 防護層級 | 實作層：修復 argparse 宣告；工具層：SKILL.md 補充「目前需分次呼叫」明示說明，直到 CLI 修復為止 |
| 跨層警示 | 禁止提升至協作層（非 PM/agent 協作設計問題）；禁止提升至認知層（非使用者誤解，是純 CLI 實作 bug，根因在實作不在使用者行為） |

---

## 相關文件

- `.claude/skills/ticket/SKILL.md`「驗收條件操作詳解」章節
- `.claude/skills/ticket/references/track-command.md`
- `.claude/skills/ticket/ticket_system/track_acceptance.py`（實作位置，待驗證）

---

**Last Updated**: 2026-05-25
