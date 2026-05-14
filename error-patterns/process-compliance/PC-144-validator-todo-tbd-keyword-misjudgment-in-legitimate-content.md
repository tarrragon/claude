---
id: PC-144
title: Validator `\bTODO\b` 將合法內容中的 TODO/TBD 字面誤判為 placeholder（PC-138 同家族延伸）
category: process-compliance
severity: medium
created: 2026-05-13
related:
 - PC-113
 - PC-138
 - W17-094
 - W10-119
---

# PC-144: Validator `\bTODO\b` / `\bTBD\b` 將合法內容中的關鍵字誤判為 placeholder

## 症狀

`ticket track complete <id>` 阻擋通過 body schema 驗證，stderr 顯示「未填寫的必填章節：Solution」。但 Solution 章節實際含完整內容（如 W10-119 的 WRAP 四階段、Spawn 規劃表、自檢結果），唯一問題是內文多處提及「TODO trigger」「TODO 註解」描述程式碼中的實際 TODO 註解。

## 觸發情境

| 條件 | 說明 |
|------|------|
| Ticket Solution / Test Results 章節含實質內容 | 章節並非空殼 |
| 內文用 TODO / TBD 描述既有程式碼或概念 | 例如「加 TODO trigger 註解」「未來的 TBD 項目」 |
| 字面 TODO/TBD 出現位置為 word boundary 命中 | 前後是空白或標點，正好符合 `\bTODO\b` |

## 根因

### 根因一：PC-138 / PC-113 同家族 — substring 命中即判 placeholder

`ticket_validator.py:_is_placeholder` 使用：

```python
if re.search(r"\(pending\)|\bTBD\b|\bTODO\b|\bN/A\b", content_no_separator, re.IGNORECASE):
    return True
```

任一 keyword 命中即 `return True`，整個 section 被判 placeholder。雖然 W17-094 加 `\b` 字邊界，但合法內容中的 TODO（作為實際單字）仍會命中。

### 根因二：placeholder 偵測無「整段判定」vs「局部出現」分層

與 PC-138 同根因：邏輯把「整段只是 placeholder」與「內容偶爾提及 keyword」混為一談。

### 根因三：作者規避只能事後發現

作者撰寫 Solution 時不會預期描述程式碼 TODO 註解會被視為「Section 未填寫」。撞牆後解法是改用「trigger 標記」「待辦」等替代字串。這違反「validator 應符合作者直覺」原則。

## 防護措施

### Layer A：作者端（規避，已驗證可行）

| 規避 | 替代 |
|------|------|
| 「加 TODO 註解」 | 「加 trigger 註解」/「加待辦註解」/「加標記註解」 |
| 「TODO trigger」 | 「trigger 標記」 |
| 「TBD 項目」 | 「待定項目」 |

### Layer B：validator 修復（治本，待落地）

兩種改法可選：

1. **加 `^[\s\S]*$` 區隔判定**：若 section 內 keyword 屬唯一文字（剝除空白/註解後就只剩它）才判 placeholder。
2. **加表格 / code-block 豁免**：keyword 在表格 cell 或 backtick `` ` `` 內出現時不視為 placeholder（與 PC-138 共用治本方案）。

## 歷史案例

- 2026-05-13 W10-119（首例）：Solution 含 6 處「TODO trigger / TODO 註解」描述既有程式碼 TODO，被 validator 全段判 placeholder；改寫為「trigger 標記」後通過。

## 與相關 error-pattern 的差異

| Pattern | 觸發詞 | 場景 |
|---------|--------|------|
| PC-113 | 短英文標記字邊界缺失 | 「TodoList」中的 「Todo」被當 TODO |
| PC-138 | `\bN/A\b` | trade-off 表格 cell `N/A` |
| **PC-144（本）** | `\bTODO\b` / `\bTBD\b` | Solution 內描述程式碼 TODO 註解或概念性「TBD」 |

三者共同根因：`_is_placeholder` 全段 substring 搜尋無法區分「整段就是 placeholder」vs「合法內容偶爾出現 keyword」。

## Action

| 情境 | 建議動作 |
|------|---------|
| 撞到本模式 | 套用 Layer A 替代字串，記下 PC-144 防護成本 |
| 系統性根除 | 推進 PC-138 / PC-144 共用治本方案（validator 改為「全段 keyword 才判 placeholder」或加表格 / code-block 豁免） |

---

**Last Updated**: 2026-05-13
**Version**: 1.0.0 - 初次記錄（W10-119 首例觸發 + 與 PC-113 / PC-138 共構關係明確化）
