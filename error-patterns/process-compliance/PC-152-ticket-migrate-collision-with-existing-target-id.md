---
id: PC-152
title: ticket migrate 撞既有目標 ID 後靜默覆寫
category: process-compliance
severity: high
source_case: 0.18.0-W14-047
created: 2026-05-19
---

# PC-152: ticket migrate 撞既有目標 ID 靜默覆寫

## 症狀

PM 配置 `ticket migrate` 批量遷移（或單一遷移）時，目標 ID 範圍與目標版本既有 ticket 撞號，工具預設靜默覆寫既有檔案。可能的觀察訊號：

- `ticket migrate --dry-run` 回報 11/11 成功，但**未提及**任何目標檔案存在性檢查
- `ticket migrate` 實際執行回報全部成功
- `git status` 顯示部分目標路徑為 **modified** 而非 untracked
- `git diff <target>` 證實既有 ticket 內容（title/type/frontmatter）被完全替換

**Why**：tool 設計時未把「目標路徑既有檔案」列為錯誤狀態。第一次跨版本遷移到非空版本目錄時必然踩到。

**Consequence**：若 commit 前未 git status 檢查直接 push，既有 ticket 內容會永久丟失（除非 backup 目錄保留遷移前快照）。本次事件覆寫 v0.19.0 W1-001~W1-003 為 v1.0 路線圖父級 ticket，靠 commit 前 git status 才得以 rollback。

**Action**：

| 階段 | 防護動作 |
|------|---------|
| 配置遷移前（PM） | `ls docs/work-logs/v<目標版本>/tickets/` 確認既有 ID 範圍，配置目標 ID 避開 |
| dry-run 後 | 觀察 git status 模擬（或工具修復後的 collision warning） |
| 實際執行後（commit 前） | `git status` 必看，任何 modified（非 deleted/untracked）都是 collision 訊號 |
| 萬一 commit 後 | 從 `.claude/migration-backups/<timestamp>/` 還原；既有 ticket 用 `git restore <path>` 從 HEAD 還原 |

## 觸發條件

以下兩條件同時成立：

1. **使用 `ticket migrate` 或 `ticket migrate --config <yaml>`**
2. **目標 ID 範圍與目標版本既有 ticket 撞號**（典型情境：跨版本遷移到非空版本目錄，PM 未先檢查既有 ID 而直接從 W1-001 開始分配）

## 根因

### L1（規則層缺口）

`.claude/skills/ticket/references/migrate-command.md` 無「前置檢查」條款。對比 `handoff-command.md:120` 有「前置檢查（強制）」條款（要求檢查殘留 pending handoff），migrate 規則層缺對等的目標既有檢查要求。

### L2（工具層缺陷）

`.claude/skills/ticket/ticket_system/commands/migrate.py:_migrate_single_ticket` 兩處缺 collision check：

**Bug A** — dry_run 區塊（line 295-299）：

```python
if dry_run:
    print(format_info(MigrateMessages.DRY_RUN_HEADER, ...))
    print(f"...DRY_RUN_TITLE_PREFIX... {ticket.get('title', 'N/A')}")
    print(f"...DRY_RUN_STATUS_PREFIX... {ticket.get('status', 'N/A')}")
    return 0
```

未呼叫 `target_path.exists()` 檢查，dry-run 完全無法預警 collision。

**Bug B** — 實際執行區塊（line 338-345）：

```python
target_path = get_ticket_path(target_version, target_id)
target_path.parent.mkdir(parents=True, exist_ok=True)
try:
    save_ticket(ticket, target_path)  # 直接覆寫，無 collision check
```

`save_ticket` 對既有路徑預設 overwrite，無 `os.path.exists` 守門。

### L3（學習層缺口）

memory IMP-061 已警告 migrate 工具其他 bug（parent_id typo / 依賴欄位不同步），但本類型（target collision）未獨立記錄。

## 案例

### 案例 1: W14-047（2026-05-19）

完整鏈：

1. PM 配置 `migrate-observation.yaml` 把 11 個待觀察 ticket 從 v0.18.0 遷移至 v0.19.0 W1-001~W1-011
2. dry-run 全部成功（無預警）
3. 實際執行全部成功（無預警）
4. commit 前 `git status` 顯示 W1-001/W1-002/W1-003 為 modified 而非 untracked
5. `git diff` 證實覆寫了 v0.19.0 既有 v1.0 路線圖父級 ticket（W1-001 從 IMP 變 ANA、title 完全替換）
6. 緊急 rollback：`git restore` W1-001~003 + `rm` W1-004~011 + `git restore` v0.18.0 deleted
7. 重做：改用 W3-001~W3-011 dry-run + execute → 11/11 成功無覆寫（commit d1780ccb）

## 防護機制

### 雙層防護方案

| 層級 | 防護內容 | 落地 ticket |
|------|---------|------------|
| L1（規則） | migrate-command.md 加入「前置檢查（強制）」章節 | 0.18.0-W14-049 DOC |
| L2（工具） | dry-run 加 collision 警告 + 實際執行預設拒絕 + `--force-overwrite` 旗標 | 0.18.0-W14-048 IMP |
| L3（學習） | 本 PC-152 文件 + memory feedback 條目 | 本檔 + auto-memory |

### 識別模板（未來同類失誤辨識）

| 訊號 | 判別 |
|------|------|
| `ticket migrate --dry-run` 預覽成功 | 不充分——dry-run 不檢 collision |
| 工具實際執行成功 | 不充分——工具預設覆寫 |
| `git status` 顯示目標路徑 modified | **強訊號**——既有檔案被覆寫 |
| `git status` 顯示目標路徑 deleted | 正常——來源被刪除 |
| `git status` 顯示目標路徑 untracked | 正常——目標版本之前無此 ID |

## 相關連結

- 動機案例：0.18.0-W14-047 ANA
- 防護 ticket：0.18.0-W14-048 IMP（工具修復）、0.18.0-W14-049 DOC（規則更新）
- 相關 bug：memory IMP-061（migrate parent_id typo + 依賴欄位不同步，不同類型）
- 對比規則：`.claude/skills/ticket/references/handoff-command.md:120`（handoff 已有前置檢查條款，migrate 對應規則缺）
- 反 autopilot 原則：PC-066

---

**Last Updated**: 2026-05-19 | **Source**: W14-047 / v0.19.0 W1-001~W1-003 覆寫事件
