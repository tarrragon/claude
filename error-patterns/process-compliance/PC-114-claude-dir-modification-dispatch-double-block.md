---
id: PC-114
title: .claude/ 修改任務派發雙重阻擋（hook worktree 強制 + ARCH-015 runtime 阻擋）
category: process-compliance
severity: medium
created: 2026-04-30
related:
 - ARCH-015
 - W10-053
 - W10-072
 - W10-043
---

# PC-114: .claude/ 修改任務派發雙重阻擋

## 症狀

PM 派發實作代理人（thyme / parsley / fennel）執行純 `.claude/` 修改任務（rule / hook / skill / validator 等框架檔），無論在主 repo 或 worktree 派發都被擋：

| 派發方式 | 結果 |
|---------|------|
| 主 repo cwd 派發（無 isolation） | `agent-dispatch-validation-hook` 阻擋：「實作代理人 thyme-python-developer 必須使用 isolation: \"worktree\" 派發」 |
| worktree 派發 | CC runtime 阻擋 subagent Edit `.claude/` 路徑（ARCH-015 runtime 級限制） |

最終 PM 只能前台直接執行，但 PCB / dispatch prompt 已沉沒成本。

## 觸發情境

| 條件 | 說明 |
|------|------|
| 任務 target 路徑全部位於 `.claude/` 之下 | 例如修 hook、validator、rule、skill |
| 派發代理人類型為「實作代理人」 | hook 1 將 thyme / parsley / fennel / cinnamon 等列為實作代理人 |
| 任務需執行 git commit | hook 1 認定實作代理人會 commit 必須隔離 |

## 根因

### 根因一：hook 1 以「代理人 type」單維度判斷強制 worktree

`agent-dispatch-validation-hook` 設計時假設「實作代理人 = 修產品碼」，未做 path 感知例外：

- 產品碼修改（`src/`）：worktree 隔離保護主 repo `.git/HEAD`，合理
- 框架碼修改（`.claude/`）：worktree 內 runtime 擋寫，hook 強制反而**讓任務不可能完成**

### 根因二：ARCH-015 是 CC runtime hardcoded 限制

CC runtime 對 worktree 內的 `.claude/` 路徑有硬編碼保護：subagent 不可 Write / Edit。理由是 `.claude/` 屬框架元層，不該被分支隔離（worktree 內外 `.claude/` 視為同一份）。此限制無法在 hook / config 層覆蓋。

### 根因三：兩個合理規則疊加 = 不可解集合

| 規則 | 單獨評估 | 疊加效應 |
|------|---------|---------|
| hook 1 | 合理（保護 main `.git/HEAD`） | — |
| ARCH-015 | 合理（保護框架元層） | — |
| hook 1 ∧ ARCH-015 | — | `.claude/` 修改任務無路徑可派發 |

## 案例

### 案例 1：W17-094 派發 thyme 失敗（2026-04-30）

W17-094 任務範圍：

- Edit `.claude/skills/ticket/ticket_system/lib/ticket_validator.py`（regex 加字邊界）
- Edit `.claude/skills/ticket/ticket_system/tests/test_ticket_validator.py`（新增 3 條測試）
- Edit `docs/work-logs/v0/v0.18/v0.18.0/tickets/0.18.0-W17-007.md:77`（還原一行）

PM 派發 `Agent(subagent_type="thyme-python-developer", ...)` 沒帶 `isolation: "worktree"` → hook 1 擋。改加 worktree → 預期 ARCH-015 擋。

PM 後續走 fallback：直接前台執行（10 分鐘完成），同時 commit 成 PC-114 / PC-113 沉澱。

## 既有追蹤

本 PC **不另開新 ANA ticket**，事件附 trigger case 證據至既有追蹤：

| Ticket | 狀態 | 用途 |
|--------|------|------|
| 0.18.0-W10-053 | pending | 診斷 subagent .claude/ Edit 受阻 + Bash sed/awk 攔截雙向阻塞 |
| 0.18.0-W10-072 | pending | 審查 IMP/DOC 類 Hook 對純文件編輯任務的識別與訊息 |
| 0.18.0-W10-043 | pending | 審查所有 75+ hooks 單維度強制邏輯與 ARCH-018 風險 |

## 修復方式

### PM 當下 fallback（已採用）

`.claude/` 任務範圍小（< 30 分鐘工作量）時，PM 前台直接執行：

1. 跳過 dispatch（接受 PCB 沉沒成本）
2. PM 在主 repo cwd 完成 Edit + 測試
3. 一個 commit 含完整變更
4. ticket complete

此 fallback 符合 pm-role.md 既有授權（PM 可改 `.claude/` 框架檔，禁止改 `src/` 產品碼）。

### 中長期修復方向（待評估）

| 選項 | 描述 | ROI |
|------|------|-----|
| A | hook 1 加 path 感知例外：prompt target 全在 `.claude/` 時豁免 worktree 強制 | 中（小範圍 hook 改造） |
| B | 新增「框架代理人」type，主 repo cwd 派發，與「產品代理人」分離 | 高（需設計 + agent 定義變更） |
| C | 兩階段派發：worktree 派改 tests/non-`.claude/`，PM 主 repo 改 `.claude/` | 低（程序複雜，PCB 拆分成本高） |
| D | 維持現狀，累積 3-5 次同類事件再評估 | 低投入，長觀察 |

當前選 D（維持現狀），事件案例累積至 W10-043 / W10-053 / W10-072 ANA 進場時統一決策。

## 防護

### PM 派發前自檢

派發實作代理人前確認：

- [ ] task 是否含 `.claude/` Edit？若是 → 兩條路都會擋
- [ ] task 範圍是否 < 30 分鐘？若是 → PM 前台執行更高效
- [ ] task 範圍是否 > 30 分鐘？若是 → 拆分（`.claude/` 部分 PM 做、其餘派發）

### Trigger case 累積規則

每次踩到此雙重阻擋：

1. append trigger case 至 W10-043 / W10-053 / W10-072 之一的 Problem Analysis
2. 不另開新 ticket（避免追蹤膨脹）
3. 累積到 5 個 trigger case 後評估是否升級為框架修改

## 相關文件

- ARCH-015 — runtime 限制原則
- ARCH-018 — Hook × 架構規則衝突偵測
- 0.18.0-W10-043 / W10-053 / W10-072 — 既有追蹤 ticket
- `.claude/methodologies/friction-management-methodology.md` — 摩擦力管理（PM 前台 vs 派發 trade-off）

---

**Last Updated**: 2026-04-30
**Source**: W17-094 派發 thyme 失敗事件（2026-04-30）— PM 改用 fallback 直接執行，事件提煉為 PC-114 沉澱
