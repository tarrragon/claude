---
id: PC-138
title: Validator 將 trade-off 表格的 N/A cell 誤判為 placeholder（PC-113 延伸 false positive）
category: process-compliance
severity: medium
created: 2026-05-11
related:
 - PC-113
 - W17-094
 - W17-190
---

# PC-138: Validator 將 trade-off 表格的 N/A cell 誤判為 placeholder

## 症狀

`ticket track complete <id>` 阻擋通過 body schema 驗證，stderr 顯示「未填寫的必填章節：Solution」。但 Solution 章節實際含完整內容：

- 三方案優劣對照表（A / B / C 三列）
- 推薦方案章節（Why / Consequence / Action 三明示）
- ARCH-020 同步策略
- multi_view_status + 自檢結果

唯一被誤判點：trade-off 表格中「方案 C 不可行」一列的 cell 寫了合法不適用標記 `| N/A | N/A | N/A | N/A | 不可行 |`。

## 觸發情境

| 條件 | 說明 |
|------|------|
| Ticket 為 ANA 類型且 Solution 含三方案優劣對照 | trade-off table 結構常見 |
| 表格中某方案不可行 / 不適用 | cell 內容寫 `N/A`（universal 縮寫） |
| Solution 章節除此外無其他 placeholder | 章節本身已有實質內容 |

## 根因

### 根因一：PC-113 加 `\b` 字邊界後仍誤判合法 `N/A`

W17-094 修復 PC-113 加入 `\bN/A\b` 字邊界（避免 `Na/A`、`xN/Ax` 等 substring 命中）。但 trade-off 表格 cell 內的 `| N/A |` 正好是 word boundary 命中（前後 ` ` 空白屬非單字字元），仍觸發 placeholder 判定。

`.claude/skills/ticket/ticket_system/lib/ticket_validator.py:_is_placeholder` 當前邏輯：

```python
if re.search(r"\(pending\)|\bTBD\b|\bTODO\b|\bN/A\b", content_no_separator, re.IGNORECASE):
    return True
```

任一 `\bN/A\b` 命中即 `return True`，整個 section 被判 placeholder。

### 根因二：placeholder 偵測無「整段判定」vs「局部出現」分層

`_is_placeholder` 將整段 section content 傳入並用 substring 搜尋。對於：

- 場景 A：Solution 整段只有 `N/A`（合法 placeholder） → 應判 placeholder
- 場景 B：Solution 含 trade-off 表格其中一個 cell 是 `N/A`（合法不適用標記） → **不應**判 placeholder

當前邏輯把兩個場景混為一談，產生 PC-138 模式。

### 根因三：作者端規避只能事後發現

作者撰寫 Solution 時不會預期 `N/A` 觸發 placeholder。撞牆後唯一明示解法是改用 `不適用` / `—` 等替代字串。這違反「validator 應符合作者直覺，不應要求作者繞路」原則。

## 案例

### W17-190 ANA Solution（2026-05-11）

PM 在 Solution 寫三方案對照表，方案 C「測試檔 UV script header 補 deps」標 N/A 表示不適用：

```markdown
| 方案 | 範圍 | 認知負擔 | 風險 | 同步策略契合度 | 可行性 |
|------|------|---------|------|--------------|------|
| A. 中央化 deps | 1 新建檔案 + 開發者執行指南 | 低 | 低 | 高 | 高 |
| B. 移除 frontmatter_parser yaml | lib + 15 hook 使用者 | 中 | 中-高 | 中 | 中 |
| C. 測試檔 UV script header | N/A（技術不可行） | N/A | N/A | N/A | 不可行 |
```

`ticket track complete` 報「Solution 未填寫」。逐行 grep `\bN/A\b` 命中 5 處（C 列五個 cell）。改 `N/A` → `不適用` 後通過。

## 防護

### Layer 1：作者端（短期）

- ANA Solution 內 trade-off 表格不可行/不適用 cell 改用 `不適用` 或 `—` 代替 `N/A`
- 文件層面新增規範：固定填充標記（不適用/未測量/不可行）的詞彙統一用中文
- 在 `.claude/rules/core/document-format-rules.md` 補例：N/A 屬 validator placeholder 預留字，作者表格應避用

### Layer 2：Validator 端（根本，需 spawn IMP）

修改 `_is_placeholder` 增加 markdown 表格情境感知：

```python
# 排除 markdown 表格 cell 內的 N/A（與 pipe 相鄰）
content_no_table_na = re.sub(r"\|\s*N/A\s*\|", "| __TABLE_NA__ |", content_no_separator)
if re.search(r"\(pending\)|\bTBD\b|\bTODO\b|\bN/A\b", content_no_table_na, re.IGNORECASE):
    return True
```

或更通用：placeholder 只在「整段除去 markdown 表格後仍含 placeholder」時觸發。

### Layer 3：規則層（書面教學）

於 `.claude/rules/core/document-format-rules.md`（或新建 `.claude/rules/core/ticket-body-style.md`）補：

- 不適用標記詞彙統一原則：固定填充內容用「不適用」「未測量」「不可行」
- 英文 `N/A` 保留給「整段為空 / 待填」的真實 placeholder 場景

## 相關規則 / 文件

- PC-113：原始 word boundary 修復（W17-094）
- W17-190 / W17-191：本 PC 觸發案例
- ticket_validator.py:_is_placeholder（line 312-383）

## 範本：發現後的處理

1. 撞牆當下：將表格 `N/A` cell 改 `不適用`
2. 記錄 PC-138（本文）+ 用戶 memory（雙通道）
3. spawn IMP 修 validator 表格情境感知（trigger：本 PC 累積 ≥ 3 案例，或 PM 評估優先級後立即 spawn）
4. 補規則層（trigger：本 PC 累積 ≥ 2 案例，或 spawn IMP 同 commit 一併處理）

## 預估影響

- 同樣模式可能出現在：技術選型比較、競品分析、優劣對照、不同方案 trade-off
- ANA / IMP / DOC 都可能撞此 false positive
- 影響範圍：所有寫含「不適用」cell 的 trade-off 表格場景
