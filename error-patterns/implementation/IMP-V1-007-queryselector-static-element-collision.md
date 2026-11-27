---
id: IMP-V1-007
title: querySelector 在多同類元素 DOM 中命中靜態錨點而非動態目標
severity: medium
category: implementation
created: 2026-07-13
source_ticket: V1 分域的 E2E 選擇器修正票
---

# IMP-V1-007: querySelector 在多同類元素 DOM 中命中靜態錨點而非動態目標

## 基本資訊

| 項目 | 值 |
|------|------|
| 風險等級 | 中 |
| 來源版本 | 1.5.0 |

## 症狀

E2E 測試中 `document.querySelector('.modal-overlay')` 永遠命中靜態 HTML 元素（`display: none`、無 click handler），導致：
- `waitForFunction` 檢查 `display === 'flex'` 永遠不成立 → timeout
- `evaluate` 點擊靜態按鈕（同文字但無 handler）→ 無效果、測試 hang

## 根因

`querySelector` 回傳 **document order 第一個匹配**。當 DOM 同時包含：
1. 靜態 HTML 元素（有 ID，如 `#importModeOverlay`，排在前面）
2. 動態建立的元素（無 ID，由 factory 函式 append 到 body，排在後面）

兩者共享相同 CSS class（`.modal-overlay`），`querySelector` 總是命中靜態元素。

**加劇因素**：靜態元素內的按鈕文字與動態元素完全相同（設計遷移保留了文字），使 text-based 二次查詢也靜默命中錯誤目標——點擊無 handler 的按鈕不拋錯，只是無效果。

## 觸發條件

- UI 框架遷移：靜態 HTML 元素降級為「存在性防禦錨點」，互動轉移至 factory 動態建立的元素
- E2E 測試選擇器未同步更新，仍用共享 class 查詢
- 靜態元素保留了相同的 class 和文字內容（向後相容設計）

## 解決方案

使用區分選擇器精確命中動態元素：

```javascript
// 靜態元素有 ID，動態元素無 ID → :not([id]) 精確區分
document.querySelector('.modal-overlay:not([id])')
```

其他可用區分策略：

| 策略 | 適用場景 |
|------|---------|
| `:not([id])` | 動態元素無 ID、靜態有 ID |
| `[data-dynamic]` | factory 可加 data attribute |
| `querySelectorAll` + `.find(el => el.style.display === 'flex')` | 以可見性篩選 |

## 預防措施

1. UI 遷移後同步更新所有消費端選擇器（unit/integration/E2E）
2. E2E 選擇器審查：當 DOM 有多個同 class 元素時，`querySelector` 需加限定條件
3. factory 動態元素建議加 `data-*` attribute 或保證唯一 class，避免與靜態元素共享選擇器

## 相關

- V1 分域的 createDialog 遷移票（產生靜態/動態元素共存的 DOM 結構）
- V1 分域的 E2E 選擇器修正票（本修正 commit 34148dad0）
