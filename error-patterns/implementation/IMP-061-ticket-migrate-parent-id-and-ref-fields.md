---
id: IMP-061
title: ticket migrate 產生 parent_id typo 且依賴欄位未同步更新
category: implementation
severity: medium
first_seen: 2026-04-14
---

# IMP-061: ticket migrate 產生 parent_id typo 且依賴欄位未同步更新

## 症狀

執行 `ticket migrate <from> <to>` 後，目標 Ticket 檔案的 YAML frontmatter 出現兩類問題：

1. **parent_id typo**：格式中的 wave 編號前導 0 被剝除
   - 原：`<version>-W<wave>-036` → 遷移後：`<version>-W<wave>-36`（序號少一個 0）
2. **依賴欄位未同步**：原本指向舊 ID 的 `blockedBy` / `relatedTo` / 父的 `children` 欄位未更新
   - 遷移 `.4 → .2` 後，`.2` 的 `blockedBy` 仍包含舊 `.1/.2/.3/.5`，其中 `.2` 是自己的 ID（自環）
   - 父 Ticket 的 `children: [.1, .2, .3, .4, .5]` 未更新為新 ID

## 根因（初始推測，已由〈修正記錄〉取代）

初次記錄時未進入原始碼驗證，根據觀察推測：

1. **parent_id typo**：migrate 邏輯中可能用正則表達式解析 wave 編號，regex 未保留前導 0。可能類似 `r"W(\d+)"` 匹配後直接用 `str(int("10"))` 產生字串，丟失 "010" 或 "10" 的固定寬度格式
2. **依賴欄位未同步**：CLI 只處理 ID 本身和 `parent_id` 欄位，忽略 `blockedBy` / `relatedTo` / 父的 `children`

## 影響範圍

- 大規模結構重組（如一次遷移 5 個子 Ticket）會觸發
- 手動修正成本 = 被遷移檔案數 × 3（每檔需檢查 parent_id、blockedBy、relatedTo）
- 若 PM 未發現，`ticket track chain` 會顯示結構斷鏈（因 parent_id 指向不存在的 ID）

## 實際觸發案例（一次 5 子 Ticket 的結構重組）

執行（`<base>` 代表 `<version>-W<wave>-036`）：
```
ticket migrate <base>.5 <base>.1.4
ticket migrate <base>.3 <base>.1.3
ticket migrate <base>.2 <base>.1.2
ticket migrate <base>.4 <base>.2
ticket migrate <base>.1 <base>.1.1
```

遷移後檢查（`<bad>` 代表序號少一個 0 的 `<version>-W<wave>-36`）：
```
grep parent_id *.md
# <base>.1.1.md: parent_id: <bad>.1  ← typo
# <base>.1.2.md: parent_id: <bad>.1  ← typo
# <base>.2.md:   parent_id: <bad>    ← typo
# <base>.2.md:   blockedBy: [<base>.1, <base>.2, ...]  ← 未更新，含自環
```

## 防護措施

### 修復方向

1. **parent_id 產生**：保留原始字串格式，不走「解析 → 轉整數 → 格式化」路徑
2. **依賴欄位 sync**：migrate 時掃描所有其他 Ticket 檔案的 `blockedBy` / `relatedTo`，凡指向被遷移 ID 者全部更新；父 Ticket 的 `children` 欄位同步替換
3. **自環檢查**：若 `blockedBy` 或 `relatedTo` 包含自己的 ID，遷移時移除
4. **驗證工具**：建議新增 `ticket validate` 命令，檢查整個 Ticket 樹的 parent_id/children/blockedBy 是否形成合法有向圖（無斷鏈、無自環、無循環依賴）

### 使用者防護（歷史手動流程，現況見〈修正記錄〉，兩項症狀已修，不再必要）

修復前，執行 migrate 後需檢查：

```bash
# 檢查 parent_id 格式
grep -r "parent_id:" docs/work-logs/v*/tickets/<version>-W<wave>-*.md | grep -v "W<wave>-0"

# 檢查父 Ticket children
grep -A5 "children:" docs/work-logs/v*/tickets/<parent>.md

# 檢查依賴欄位是否含舊 ID
grep -A3 "blockedBy:\|relatedTo:" docs/work-logs/v*/tickets/<migrated>.md
```

發現異常 → 手動編輯 frontmatter 修正。

## 修正記錄

兩項症狀在現行 CLI 皆已修復。

| 症狀 | 現況 | 證據 |
|------|------|------|
| 1 parent_id 前導 0 被剝除 | 已修：`calculate_chain_info` 以原始字串 split 組回 root 與 parent，保留各層前導 0；`_migrate_ticket_files` 以其 `parent` 寫入 `parent_id`。實測 `<version>-W<wave>-036.1` 的 parent 為 `<version>-W<wave>-036`。該函式目前無專屬單元測試 | `.claude/skills/ticket/ticket_system/lib/id_parser.py` 的 `calculate_chain_info`；`.claude/skills/ticket/ticket_system/commands/migrate.py` 的 `_migrate_ticket_files` |
| 2 依賴欄位未同步 | 已修：migrate 把指向舊 ID 的 blockedBy、relatedTo、children、source_ticket、parent_id 改成新 ID，並同步新舊父票 children | `migrate.py` 的 `_update_ticket_id_references`、`_update_cross_references_collecting`、`_sync_parent_children`；測試 `.claude/skills/ticket/ticket_system/tests/test_migrate_reverse_refs.py` |

〈根因〉的推測（regex 轉整數、CLI 只處理 ID 與 parent_id）已由上述修復取代。〈修復方向〉第 4 點（`ticket validate`）是獨立的新功能，不屬本記錄的修復範圍。

---

**Last Updated**: 2026-04-14
**Version**: 1.0.0 — 初始記錄（首次觀察於一次子 Ticket 結構重組）
