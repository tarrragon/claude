---
id: PC-GPD-038
title: 並行代理人共用父 session 的 scratchpad，中介內容檔用通用檔名時互相覆蓋，寫入他票卻回報成功
severity: 中
---

# PC-GPD-038: 並行代理人共用父 session 的 scratchpad，中介內容檔用通用檔名時互相覆蓋，寫入他票卻回報成功

## 基本資訊

| 項目 | 內容 |
|------|------|
| 風險等級 | 中 |
| 分類 | process-compliance |
| 來源版本 | 0.5.0 |
| 來源事件 | worktree 派發骨架把多行票面內容改走「scratchpad 內容檔 + `append-log --content-file`」時的實地派發 |
| 首次觀測 | 2026-10-20 |

## 症狀

以 worktree 隔離派發的代理人，拿到的 scratchpad 路徑是**父 session 的 scratchpad**，不是代理人自己的目錄。實地派發時，代理人回報的內容檔路徑落在父 session 的 scratchpad 目錄下。

同一 session 並行派發多位代理人時，它們共用同一個目錄。若代理人都替中介內容檔取通用檔名（例：`content.md`、`solution.md`），會發生：

1. 代理人 A 寫入 `content.md`，尚未執行 `append-log --content-file`
2. 代理人 B 寫入同名 `content.md`，覆蓋 A 的內容
3. A 執行 `append-log <A 的票> --content-file .../content.md`，把 B 的內容寫進 A 的票

第 3 步 rc=0、輸出 `[OK] 已追加日誌`，`[verify]` 行數也正常增加。目前沒有發生事故，這是以機制推得的失效路徑，在檔名規則上線前即由審查方指出。

## 根因

| 層級 | 機制 |
|------|------|
| L1 載體共用不可見 | 「scratchpad」在代理人的指令裡讀起來像私有暫存區，實際是父 session 的目錄。代理人無從得知同目錄有其他執行體 |
| L2 中介檔無命名空間 | 派發指令只要求「寫入 scratchpad 內容檔」，沒有規定檔名。通用檔名是最自然的選擇，因此碰撞機率隨並行度上升 |
| L3 寫入端無內容歸屬校驗 | `append-log --content-file` 逐字讀檔，不校驗內容是否屬於目標票。寫錯票與寫對票在輸出上同形 |

三層共振：內容層面是錯的，所有可觀測面卻是對的。這和 PC-GPD-003（寫入成功但結構受損）同屬「寫入看似成功」族，差別在本模式連結構都完好，只有歸屬錯。

## 處置

| 角色 | 動作 |
|------|------|
| 派發骨架 | 多行內容句明寫「scratchpad 內容檔（檔名含票號，非票檔）」，由 `dispatch_skeleton.py` 的 `WORKTREE_MULTILINE_LINE` 承載，並以字面斷言（句含「票號」）防止日後壓縮時被刪 |
| 代理人 | 內容檔檔名以票號開頭（例：`<ticket-id>-solution.md`）；同一張票寫多個章節時再加章節名 |
| PM 自寫 prompt | 要求代理人寫 scratchpad 檔時，同樣指定檔名含票號；骨架尚未含此規則的空窗期，以 prompt 補述 |

## 預防

- 任何要求代理人「寫入共用暫存區再由另一條命令讀取」的指令，都要指定含唯一識別（票號）的檔名，不只限 append-log
- 懷疑已命中時的檢查：比對票面最新一段內容是否提到本票的改動物；內容描述的是其他票的檔案或驗收項，即為命中
- 寫入端歸屬校驗（例：內容檔首行須含目標票號，否則拒收）可把 L3 補上，但會讓 `--content-file` 多一道格式要求；本模式記錄時尚未評估

## 邊界

- PC-BAL-008、PC-092：並行代理人共用 git index。同屬「並行執行體共用狀態」族，載體不同（git index 對比暫存目錄）
- PC-GPD-028：context 壓縮後接手在飛代理人並污染其共用器材。觸發者是主線程誤判，本模式是並行代理人彼此碰撞，無人誤判
- PC-GPD-003：worktree 守衛拒收含換行參數。本模式是它的修法（改走 `--content-file`）引入的新失效面

## 相關

- `.claude/skills/ticket/ticket_system/lib/dispatch_skeleton.py`（`WORKTREE_MULTILINE_LINE`）
- `.claude/error-patterns/process-compliance/PC-GPD-003-worktree-guard-rejects-newline-args-flattens-markdown-sections.md`
- `.claude/error-patterns/process-compliance/PC-BAL-008-shared-git-index-sweeps-parallel-agent-staged-files.md`
- `.claude/error-patterns/process-compliance/PC-GPD-028-compact-resume-hijacks-inflight-agent-shared-fixtures.md`
- `.claude/references/tool-selection-details.md`（規則 2 例外：拆分後中間結果寫 scratchpad 檔）
