# ARCH-013: ESM/CJS 混合匯出導致 Dead Code

## 基本資訊

- **Pattern ID**: ARCH-013
- **分類**: 架構設計
- **來源版本**: v0.17.3
- **發現日期**: 2026-04-09
- **風險等級**: 中
- **來源 Ticket**: 0.17.3-W1-002（多視角審查發現）

## 問題描述

### 症狀

模組同時包含 ESM `export` 語句和 CJS `module.exports` 相容區塊，但其中一種匯出模式在實際執行環境中永遠不會被觸發，成為 dead code。開發者以為兩種環境都能正常引用，實際上只有一種能工作。

### 根本原因 (5 Why 分析)

1. Why 1: CJS 相容區塊（`if (typeof module !== 'undefined')`）永遠不執行
2. Why 2: Bundler（esbuild）以頂層 `export` 語句判定模組為 ESM，不追蹤 ESM 模組內的 `require()` 呼叫
3. Why 3: 開發者假設「加了條件判斷就能同時支援兩種環境」
4. Why 4: 缺乏對 bundler 模組類型判定機制的認知
5. Why 5 (根本原因): **模組類型由 bundler/runtime 在解析階段決定，不是由執行期條件判斷決定**。一個檔案只能是 ESM 或 CJS，不能用 `if` 在兩者之間切換。

### 受影響模式

```javascript
// 錯誤：混合模式 — CJS 區塊為 dead code
const COLORS = { primary: '#2196F3' };

export { COLORS };  // ← bundler 判定此檔為 ESM

// 以下區塊永遠不執行：ESM 環境中 module 未定義
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { COLORS };
}
```

```javascript
// 錯誤：index.js re-export 混合 — require 不被追蹤
export { COLORS } from './colors.js';  // ← ESM re-export

// 以下區塊永遠不執行
if (typeof module !== 'undefined' && module.exports) {
  const colors = require('./colors.js');  // ← bundler 不追蹤此 require
  module.exports = { ...colors };
}
```

### 觸發條件

- 專案使用 bundler（esbuild/webpack/rollup）打包
- 同一檔案同時包含 `export` 和 `module.exports`
- 開發者意圖同時支援 ESM（瀏覽器/bundler）和 CJS（Node.js/Jest）

## 正確做法

### 方案 A：統一為純 CJS（推薦，bundler 專案）

```javascript
// bundler 能正確處理 CJS require，且 Jest 也能直接引用
const COLORS = { primary: '#2196F3' };
module.exports = { COLORS };
```

### 方案 B：統一為純 ESM + Jest 配置 transform

```javascript
// 純 ESM
export const COLORS = { primary: '#2196F3' };
```

搭配 Jest 配置 `transform` 或 `extensionsToTreatAsEsm` 處理 ESM。

### 選擇原則

| 專案狀態 | 推薦方案 | 原因 |
|---------|---------|------|
| 既有模組大多是 CJS | 方案 A | 一致性優先 |
| 新專案或已全面 ESM | 方案 B | 原生 ESM 是未來方向 |
| Chrome Extension + esbuild | 方案 A | esbuild IIFE 打包對 CJS 支援最穩定 |

## 防護措施

### 開發時

- 建立新模組前，先確認專案其他模組的匯出風格（`grep 'module.exports' src/` vs `grep '^export' src/`）
- 新模組匯出風格必須與既有模組一致

### 審查時

- 發現同一檔案同時有 `export` 和 `module.exports` → 必定有一種是 dead code
- 確認 bundler 類型和模組判定機制

### 測試時

- 純 CJS 模組：`const { X } = require('./module')` 在 Jest 中可直接驗證
- 純 ESM 模組：需配置 Jest transform

## 相關 Pattern

- IMP-005: 不完整的 import 遷移（部分檔案遷移 ESM，部分仍為 CJS）

---

**Last Updated**: 2026-04-09
