# ARCH-014: 跨執行環境共享可變常數物件

## 基本資訊

- **Pattern ID**: ARCH-014
- **分類**: 架構設計
- **來源版本**: v0.17.3
- **發現日期**: 2026-04-09
- **風險等級**: 中

## 問題描述

### 症狀

常數物件在某個模組中被意外修改（如 `COLORS.primary = '#000'`），導致所有引用該常數的模組都看到被修改後的值。在 Chrome Extension 等多執行環境（content script / popup / background）共享 bundle 的場景中，一處修改影響全局，且 bug 難以追蹤 — 因為修改方和受害方在不同的程式碼區域。

### 根本原因 (5 Why 分析)

1. Why 1: 其他模組看到的常數值不是預期值
2. Why 2: 某個模組執行了 `CONSTANT.key = newValue`
3. Why 3: JavaScript 的 `const` 只保護變數綁定，不保護物件內容
4. Why 4: 常數物件定義時未套用 `Object.freeze()`
5. Why 5 (根本原因): **JavaScript 的 `const` 語意與「不可變」不同**。`const obj = {}` 只防止 `obj = other`，不防止 `obj.key = value`。需要額外的 `Object.freeze()` 才能達到真正的常數語意。

### 受影響模式

```javascript
// 錯誤：const 不保護物件內容
const COLORS = {
  primary: '#2196F3',
  secondary: '#FF9800',
};

// 在某個模組中意外修改
COLORS.primary = '#000000';  // 不會拋錯，靜默成功

// 所有其他引用 COLORS 的模組都受影響
console.log(COLORS.primary);  // '#000000' — 不是預期值
```

```javascript
// 錯誤：只 freeze 頂層，巢狀物件仍可變
const STATUS_COLORS = Object.freeze({
  reading: { fg: '#2196F3', bg: 'rgba(33,150,243,0.15)' },
});

STATUS_COLORS.reading.fg = '#000';  // 不會拋錯！內層物件未 freeze
```

### 觸發條件

- 常數物件被多個模組引用（`import` 或 `require`）
- 應用程式有多個執行環境共享同一份 bundle（Chrome Extension、微前端）
- 物件有巢狀結構（需要 deep freeze）

## 正確做法

### 基本保護：Object.freeze()

```javascript
const COLORS = Object.freeze({
  primary: '#2196F3',
  secondary: '#FF9800',
});

COLORS.primary = '#000';  // strict mode 下拋 TypeError，非 strict mode 靜默失敗
```

### 巢狀物件：逐層 freeze

```javascript
const STATUS_COLORS = Object.freeze({
  reading: Object.freeze({ fg: '#2196F3', bg: 'rgba(33,150,243,0.15)' }),
  finished: Object.freeze({ fg: '#4CAF50', bg: 'rgba(76,175,80,0.15)' }),
});
```

### 何時需要 Object.freeze

| 場景 | 需要 freeze | 原因 |
|------|------------|------|
| 跨模組共享常數 | 是 | 防止某模組意外修改影響全局 |
| 模組內部常數（不匯出） | 否 | 作用域有限，風險低 |
| 設定物件（需要動態修改） | 否 | 本意就是可變的 |
| 列舉值（enums） | 是 | 語意上為固定集合 |

### 何時不需要

- 效能敏感的熱路徑（freeze 有微小開銷，但通常可忽略）
- 模組內部的臨時物件
- 明確標記為可變的 config 物件

## 防護措施

### 開發時

- 匯出的常數物件（`module.exports` / `export`）預設套用 `Object.freeze()`
- 巢狀物件逐層 freeze，或使用 deep freeze utility

### 審查時

- 發現匯出的常數物件無 `Object.freeze()` → 標記為需修正
- 特別注意多執行環境共享 bundle 的專案（Chrome Extension、Electron）

### 適用範圍

本模式不限於 Chrome Extension，適用於所有「多模組共享常數」的 JavaScript 專案。但在以下場景風險更高：

| 環境 | 風險 | 原因 |
|------|------|------|
| Chrome Extension | 高 | content script / popup / background 共享常數 |
| Electron | 高 | main process / renderer 可能共享模組 |
| 單頁應用（SPA） | 中 | 所有元件共享同一份 bundle |
| Node.js 微服務 | 低 | 每個 process 獨立，影響範圍有限 |

## 相關 Pattern

- IMP-002: 魔法數字（常數管理的另一面）

---

**Last Updated**: 2026-04-09
