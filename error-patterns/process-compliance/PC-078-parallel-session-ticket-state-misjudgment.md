# PC-078: 並行 terminal/session 的 Ticket 狀態異動被誤判為前 session 遺留

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-078 |
| 類別 | process-compliance |
| 風險等級 | 高 |
| 首發時間 | 2026-04-17（W13-003 commit 後誤 release W12-006 事件） |
| 姊妹模式 | PC-076（前 session 未 commit 遺留）、ARCH-015（worktree 隔離） |

---

## 症狀

PM 在 `git status` 或 `ticket track query` 看到非本 session 主動操作的 Ticket 狀態變化（例如某 Ticket 從 pending 變 in_progress、started_at 填入新時間戳），PM 可能：

1. 假設是「前 session 未 commit 遺留」
2. 假設是「Hook / commit 副作用」
3. 自作主張 release 或修改該 Ticket 狀態
4. 實際上是**另一個 terminal / session 正在活躍處理** 該 Ticket

後果：PM 的「修正」動作等同打斷並行 session 的工作，對方 session 會遇到狀態與自身期望不符的混亂。

---

## 實例（2026-04-17 W13-003 commit 後誤 release W12-006）

- PM 在本 session 完成 W13-003 commit 後執行 `git status`
- 發現 `docs/work-logs/.../0.18.0-W12-006.md` 變更：status `pending → in_progress`、`started_at` 填入新時間戳
- PM 誤判來源：「可能是 commit B ticket CLI 變更副作用或其他工作流觸發」
- PM 動作：`ticket track release 0.18.0-W12-006`，然後 commit 訊息寫「意外被 claim（非主動認領），已 release」
- 用戶立即指出：**是另一個 terminal 在處理**
- 實際情況：並行 terminal 剛 claim W12-006 正準備實作，被 PM 打斷
- 補救：PM 重新 claim W12-006 還原 in_progress，建 PC-078 記錄教訓

---

## 根本原因

### 真根因（三層判斷缺失）

1. **並行 session 可見性缺失**
   - `git worktree list` 只能看 worktree 層 session，同一工作樹裡開兩個終端機各跑一個 Claude Code 不會顯示
   - 沒有中心化「active-sessions 清單」可供 PM 即時查詢
   - 本例發生時未執行任何並行判斷指令

2. **狀態變化的語意誤判**
   - `started_at` 被填入新時間戳**幾乎不可能**是 commit 副作用或自動化工具所為
   - 那是顯性 claim 動作的產物（`ticket track claim` 指令）
   - PM 未識別此訊號

3. **處理策略過於主動**
   - 面對不明狀態變化，PM 預設策略是「還原乾淨」而非「先詢問用戶或並行 session」
   - 不符合「不改變不是自己 claim 的 Ticket」原則

---

## 常見陷阱模式

| 陷阱表述 | 為何錯誤 |
|---------|--------|
| 「git status 冒出不認識的變更應該 release 清理」 | 可能是並行 session 的活躍工作，不可擅動 |
| 「started_at 填入是 Hook 自動觸發」 | started_at 只由 `ticket track claim` 填入，必為顯性動作 |
| 「PC-076 前 session 遺留原則適用」 | PC-076 適用靜態遺留；本例是動態並行，需用 PC-078 判斷 |

---

## 與 PC-076 的區別

| 維度 | PC-076 前 session 遺留 | PC-078 並行 session 活躍 |
|------|------------------------|-------------------------|
| 時間性 | 前 session 已結束未 commit | 另一 session 正在活躍操作 |
| 訊號特徵 | 檔案 modified 但 Ticket status 無新變動 | Ticket status 從 pending → in_progress 或其他 |
| started_at | 通常為 null 或舊時間戳 | 填入新時間戳 |
| 正確處理 | commit 整合並歸類為遺留 | **不動**；先詢問用戶或等並行 session 完成 |
| 錯誤處理 | 混入主題 commit 造成混淆 | **release 打斷並行 session** |

---

## 防護措施

| 層級 | 措施 | 狀態 |
|------|------|------|
| 檢查清單 | PM 遇到 Ticket 狀態異動前先問：started_at 是否新？是否可能有並行 terminal？ | 已實施（本檔） |
| 規則 | 「非本 session claim 的 Ticket 狀態不可修改」原則寫入 pm-role.md | 建議實施 |
| 工具 | ticket CLI 新增 `track active` 列出當前 active session / claim 來源（需 session ID 追蹤） | 建議評估 |
| 行為 | 面對非主動引起的狀態變化，預設動作改為「先詢問用戶」而非「還原清理」 | 行為準則 |

---

## 檢查清單（PM 遇非主動狀態變化時）

遇 `git status` 或 `ticket track query` 顯示非本 session 操作引起的變化時：

- [ ] 識別變化類型：檔案內容 modified / Ticket status change / frontmatter 欄位填入？
- [ ] 若有 `started_at` 填入新時間戳 → **必為顯性 claim 動作**，極可能是並行 session
- [ ] 若僅檔案 modified 無 Ticket CLI 痕跡 → 較可能是 PC-076 前 session 遺留
- [ ] 不確定時 → **停手，先詢問用戶**，禁止自行 release / 狀態還原
- [ ] 確認是並行 session → 不干預，繼續自己任務；將變更排除於自己 commit 範圍外（必要時 git stash --keep-index）
- [ ] 確認是前 session 遺留 → 依 PC-076 流程拆 commit 處理

---

## 教訓

1. **started_at 是顯性訊號**：它的填入只來自 `ticket track claim`，任何其他解讀（Hook 副作用、commit 觸發）都是錯誤假設
2. **預設策略要從「還原」改為「暫停詢問」**：不明狀態變化的第一反應應該是「先問」不是「先清」
3. **並行 session 有 invisible blast radius**：PM 在主 session 的動作會影響不可見的並行 session，謹慎優先於效率
4. **PC-076 和 PC-078 要搭配使用**：兩者判斷維度不同，混用會導致錯誤處理
5. **錯誤復原要誠實記錄**：本事件 PM 誤 release 後立即 reclaim 並建 PC-078，用戶學習曲線才能累積

---

## 相關文件

- `.claude/error-patterns/process-compliance/PC-076-cross-session-uncommitted-legacy.md` — 姊妹模式（靜態遺留）
- `.claude/error-patterns/architecture/ARCH-015-subagent-claude-dir-hardcoded-protection.md` — worktree 隔離（只防 subagent，不防並行 terminal）
- `.claude/rules/core/pm-role.md` — PM 職責邊界
- `.claude/skills/ticket/ticket_system/commands/` — ticket CLI 來源

---

**Last Updated**: 2026-04-17
**Version**: 1.0.0 — 首發記錄（誤 release W12-006 事件，commit c07bc00b 訊息含錯誤歸因）
**Source**: 2026-04-17 W13-003 完結 session，PM 發現 W12-006 status 從 pending 變 in_progress 後誤判為「意外 claim」並 release；用戶即時指出為並行 terminal 活躍操作；PM reclaim 還原並建本錯誤模式
