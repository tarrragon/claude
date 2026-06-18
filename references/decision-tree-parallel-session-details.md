# 並行 Session/Terminal 判斷層（PC-076 / PC-078 詳細）

本檔為 `pm-rules/decision-tree.md`「並行 Session/Terminal 判斷層」的按需讀取詳細版。依「決策閘門預算原則」（`rules/README.md`）外移：本層屬條件觸發（偵測到非本 session 狀態變化時才適用），非每回合必經，故 substance 降級至此，routing 留一行指標。

> 核心原則：PM 偵測到「非本 session 造成的狀態變化」時，預設路徑是**先停手問用戶**，而不是「還原」或「歸因為自己行為」。

## 觸發訊號

| 訊號類型 | 動態識別特徵 | 靜態 vs 動態 |
|---------|------------|------------|
| Ticket started_at 是新時間戳但非本 session claim | `ticket track query` 顯示 `started_at: 2026-XX-XX TXX:XX:XX` 比本 session 啟動時間晚 | 動態（PC-078） |
| Ticket status 從 pending 變 in_progress 但不是本 session 認領 | session 內未執行 `ticket track claim` 但狀態已變 | 動態（PC-078） |
| git status 顯示不熟悉的修改檔案 | `session-start` Hook 未列出的修改 | 兩者均可能 |
| Ticket 檔案內容被改動但不是本 session 寫入 | 本 session 未編輯但 git diff 有內容 | 動態（PC-078）|
| Session-start Hook 列出遺留變更 | Hook 訊息明示「cross-session uncommitted」 | 靜態（PC-076）|

## 靜態遺留 vs 動態並行：訊號對照

| 維度 | 靜態遺留（PC-076） | 動態並行（PC-078） |
|------|-------------------|-------------------|
| 來源 session | 已結束的過去 session | 正在運行的其他 terminal |
| 時間戳特徵 | 舊於本 session 啟動時間 | 新於本 session 啟動時間 |
| 處理策略 | PM 可主動 commit 整理（全量清點後拆主題） | PM **禁止自行處理**，先問用戶 |
| 正確反應 | 全量 git status → 拆主題 commit | 停手 → AUQ 確認 → 按用戶指示 |

## PM 預設路徑（非主動狀態變化時）

```
偵測到異常狀態變化
    ├── Session-start Hook 已明示為遺留（舊時間戳）
    │   → 走 PC-076 流程：全量清點 + 拆主題 commit
    │
    └── 其他（新時間戳 / 不確定來源）
        → 預設：停手 + AUQ 問用戶「這是平行 terminal 動作嗎？」
            ├── 是並行：尊重並行 session 的工作，只 commit 本 session 變更
            ├── 是 Hook 自動動作：確認 Hook 身份後評估
            └── 不確定：繼續等用戶指示，禁止自行 release / complete / 還原
```

## 禁止行為

- **禁止自行 release** started_at 是新時間戳的 Ticket（可能是並行 terminal 正在處理）
- **禁止自行 complete** 狀態異常的 Ticket（不知道異常來源）
- **禁止還原** 未知來源的檔案修改（除非確認是遺留 commit）
- **禁止歸因為自己行為問題**（PC-078 明示：先考慮並行，再考慮自己）

## 相關錯誤模式

- PC-076：cross-session uncommitted 遺留（靜態）
- PC-078：parallel-session ticket state 誤判（動態）

---

**Last Updated**: 2026-06-18 | **Version**: 1.0.0 — 從 `pm-rules/decision-tree.md` 外移（1.2.0-W1-010，決策閘門預算原則 pilot）。內容語意不變，僅載入層改變。
