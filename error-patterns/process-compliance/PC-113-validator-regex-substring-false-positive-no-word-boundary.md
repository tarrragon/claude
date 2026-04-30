---
id: PC-113
title: Validator regex 缺字邊界導致 substring 誤判 placeholder
category: process-compliance
severity: medium
created: 2026-04-30
related:
 - W17-072
 - W17-074
 - W17-094
---

# PC-113: Validator regex 缺字邊界導致 substring 誤判 placeholder

## 症狀

`ticket track complete <id>` 阻擋通過 body schema 驗證，stderr 顯示「未填寫的必填章節：Problem Analysis / Solution / Test Results」，但實際 body 章節含大量實質內容（表格、文字段落、無佔位符標記）。

## 觸發情境

| 條件 | 說明 |
|------|------|
| Ticket body 章節含 `Todo` / `TBD` / `N/A` 字樣的單字 | 例如 `TodoList`、`TBDay`、合理英文詞彙 |
| 章節內容完整實質但用戶看不出問題 | 表格 + 段落 + 程式碼區塊都正常 |
| 驗證器 regex 用 IGNORECASE 但無 `\b` 字邊界 | substring 命中觸發 placeholder 判定 |

## 根因

### 根因一：regex pattern 過寬（substring 命中）

`.claude/skills/ticket/ticket_system/lib/ticket_validator.py:_is_placeholder` 原 pattern：

```python
r"\(pending\)|TBD|TODO|N/A"
```

加上 `re.IGNORECASE`，`TODO` 會命中 `TodoList`、`TodoMVC`、`Todorewrite` 等任何含 t-o-d-o 序列的 substring。

### 根因二：placeholder 判定一旦觸發，整個 section 視為未填

`_is_placeholder` 任一 pattern 匹配即 `return True`，且 `validate_execution_log_by_type` 把整個 section content 傳入；只要有一處 substring 命中，整個 2K+ 字元 section 都被判為 unfilled。

### 根因三：同家族 false positive 累積暴露

| 家族 | 觸發機制 | 處理 |
|------|---------|------|
| W17-072 | agent 自定義 H2 切斷 schema section | 已修（`_find_next_schema_section_boundary` 限定 schema 名單） |
| W17-074 | backtick 內 `## Test Results` 引用被誤判章節 | 已修（line-anchored regex） |
| W17-094 / PC-113 | substring TODO/TBD/N/A 誤判 placeholder | 已修（加 `\b` 字邊界） |

三者共同病因：validator 的 pattern 過寬，未考慮 markdown content 的 substring / 引用上下文。

## 案例

### 案例 1：W17-007 ANA complete 失敗（2026-04-30）

W17-007 Problem Analysis 含字串「列所有 CC tasks（非 TodoList）」描述 `TaskList()` runtime tool。

```bash
$ ticket track complete 0.18.0-W17-007
[Error] body 未依 ANA schema 填寫必填章節
   未填寫的必填章節：
   - Problem Analysis
```

PM 實際 debug 路徑：

1. 確認 body 章節皆有實質內容（grep `待填寫` / `<!-- ` 皆無命中）
2. 直接 import validator 在 Python REPL 執行 `validate_execution_log_by_type('ANA', body)` → 仍 False
3. 對章節內容跑 `re.findall(r'TODO', content, re.IGNORECASE)` → 命中 `Todo`
4. 確認元凶為 `TodoList` 內 substring

PM 當下 fallback 是把字眼改為「task 待辦清單」繞開，再回頭建 W17-094 修 regex。

## 修復方式

### 直接修復

`.claude/skills/ticket/ticket_system/lib/ticket_validator.py` line 369：

```python
# 修前
if re.search(r"\(pending\)|TBD|TODO|N/A", content_no_separator, re.IGNORECASE):

# 修後
if re.search(r"\(pending\)|\bTBD\b|\bTODO\b|\bN/A\b", content_no_separator, re.IGNORECASE):
```

`\(pending\)` 已含括號邊界保留；`TBD` / `TODO` / `N/A` 加 `\b`。

### 回歸測試補充

`tests/test_ticket_validator.py` 新增至少 3 條：

1. `TodoList` substring 不誤判 placeholder
2. 真正 `# TODO: implement` 仍判 placeholder
3. `TBD` / `N/A` 加字邊界後 substring 不誤判但本字仍判

### 還原驗證

修復後還原 PM 當下繞開的字眼（如 W17-007 line 77 的 `TodoList`），重跑驗證確認通過。

## 防護

### Pattern 規範

設計 placeholder / 違規偵測 regex 時：

| 規則 | 理由 |
|------|------|
| 短英文標記（≤4 字元）必加 `\b` | TODO / TBD / N/A / WIP 等易被 substring 命中 |
| 中文佔位符可省略字邊界 | 中文無 word boundary 概念，但需具體括號上下文（如 `（待填寫：...）`）約束 |
| IGNORECASE 必須與字邊界搭配 | 大小寫不敏感擴大命中範圍，沒字邊界易超出意圖 |

### Code Review checklist

審查 regex 時自問：

- 此 pattern 在自然 markdown / 一般文字內是否可能 substring 命中？
- 是否有對應反例測試（substring 不誤判）？
- IGNORECASE 是否擴大誤判風險？

## 相關文件

- `.claude/skills/ticket/ticket_system/lib/ticket_validator.py` `_is_placeholder` — 修復主體
- W17-072 / W17-074 / W17-094 — 同家族 false positive 修補歷史
- `.claude/error-patterns/process-compliance/PC-110-...` — body schema 範本驗證家族

---

**Last Updated**: 2026-04-30
**Source**: W17-007 ANA complete 期間 PM 實證踩到（commit 75ef9fd8 → W17-094 ticket → fix commit a47ffb14）
