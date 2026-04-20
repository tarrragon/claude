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
   - 原：`0.18.0-W10-036` → 遷移後：`0.18.0-W10-36`（少一個 0）
2. **依賴欄位未同步**：原本指向舊 ID 的 `blockedBy` / `relatedTo` / 父的 `children` 欄位未更新
   - 遷移 `.4 → .2` 後，`.2` 的 `blockedBy` 仍包含舊 `.1/.2/.3/.5`，其中 `.2` 是自己的 ID（自環）
   - 父 Ticket 的 `children: [.1, .2, .3, .4, .5]` 未更新為新 ID

## 根因（待確認）

未進入原始碼驗證，根據觀察推測：

1. **parent_id typo**：migrate 邏輯中可能用正則表達式解析 wave 編號，regex 未保留前導 0。可能類似 `r"W(\d+)"` 匹配後直接用 `str(int("10"))` 產生字串，丟失 "010" 或 "10" 的固定寬度格式
2. **依賴欄位未同步**：CLI 只處理 ID 本身和 `parent_id` 欄位，忽略 `blockedBy` / `relatedTo` / 父的 `children`

## 影響範圍

- 大規模結構重組（如本 session 的 W10-036 5 子 Ticket 遷移）會觸發
- 手動修正成本 = 被遷移檔案數 × 3（每檔需檢查 parent_id、blockedBy、relatedTo）
- 若 PM 未發現，`ticket track chain` 會顯示結構斷鏈（因 parent_id 指向不存在的 ID）

## 實際觸發案例（W10-036 重組）

執行：
```
ticket migrate 0.18.0-W10-036.5 0.18.0-W10-036.1.4
ticket migrate 0.18.0-W10-036.3 0.18.0-W10-036.1.3
ticket migrate 0.18.0-W10-036.2 0.18.0-W10-036.1.2
ticket migrate 0.18.0-W10-036.4 0.18.0-W10-036.2
ticket migrate 0.18.0-W10-036.1 0.18.0-W10-036.1.1
```

遷移後檢查：
```
grep parent_id *.md
# 0.18.0-W10-036.1.1.md: parent_id: 0.18.0-W10-36.1  ← typo
# 0.18.0-W10-036.1.2.md: parent_id: 0.18.0-W10-36.1  ← typo
# 0.18.0-W10-036.2.md:   parent_id: 0.18.0-W10-36    ← typo
# 0.18.0-W10-036.2.md:   blockedBy: [0.18.0-W10-036.1, 0.18.0-W10-036.2, ...]  ← 未更新，含自環
```

## 防護措施

### 修復方向（對應 W10-037 Ticket）

1. **parent_id 產生**：保留原始字串格式，不走「解析 → 轉整數 → 格式化」路徑
2. **依賴欄位 sync**：migrate 時掃描所有其他 Ticket 檔案的 `blockedBy` / `relatedTo`，凡指向被遷移 ID 者全部更新；父 Ticket 的 `children` 欄位同步替換
3. **自環檢查**：若 `blockedBy` 或 `relatedTo` 包含自己的 ID，遷移時移除
4. **驗證工具**：建議新增 `ticket validate` 命令，檢查整個 Ticket 樹的 parent_id/children/blockedBy 是否形成合法有向圖（無斷鏈、無自環、無循環依賴）

### 使用者防護（修復前的手動流程）

執行 migrate 後必須檢查：

```bash
# 檢查 parent_id 格式
grep -r "parent_id:" docs/work-logs/v*/tickets/0.18.0-W10-*.md | grep -v "W10-0"

# 檢查父 Ticket children
grep -A5 "children:" docs/work-logs/v*/tickets/<parent>.md

# 檢查依賴欄位是否含舊 ID
grep -A3 "blockedBy:\|relatedTo:" docs/work-logs/v*/tickets/<migrated>.md
```

發現異常 → 手動編輯 frontmatter 修正。

## 相關 Ticket

- 0.18.0-W10-037: ADJ 修復 ticket migrate CLI bug

## 修正記錄

（待 W10-037 完成後更新）

---

**Last Updated**: 2026-04-14
**Version**: 1.0.0 — 初始記錄（首次觀察於 W10-036 結構重組）
