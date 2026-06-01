---
id: IMP-078
title: CE-Node 環境前提誤判 — Jest 測試綠燈但 CE Runtime 崩潰
category: implementation
severity: high
status: active
created: 2026-05-30
related:
- PC-165
- ARCH-013
---

# IMP-078: CE-Node 環境前提誤判 — Jest 測試綠燈但 CE Runtime 崩潰

`src/` 程式碼直接使用 Node.js 專屬 API（`global` / `process.*` / `require('crypto')` 等），在 Jest + jsdom（Node.js 環境）測試全綠，但部署至 Chrome Extension runtime（esbuild IIFE bundle + 瀏覽器，無 Node.js polyfill）時立即 `ReferenceError` 崩潰。開發者基於「acceptance 全勾 + commit = 修復已生效」假設推進後續 ticket，但實機 100% 不可用，導致多 ticket 連鎖回溯。

**Why**：Jest 在 Node.js + jsdom 執行，`global`/`process`/`require` 天然可用，差異對測試套件完全透明；esbuild `platform: browser, format: iife` 不 polyfill Node.js API，CE runtime 立即拋出 `ReferenceError`。

**Consequence**：CE runtime 功能 100% 不可用；測試「全綠 = 可發布」承諾被打破；單一根因引發 8+ ticket 連鎖回溯（W1-047.1~.5 → W1-001.2.1 → W1-050 → W1-050.1~.6），阻塞版本里程碑。

**Action**：三層防護（見「防護方向」）：ESLint 靜態檢查 + esbuild define + bundle scan。

---

## 基本資訊

- **Pattern ID**: IMP-078
- **分類**: 實作（implementation）
- **來源版本**: v0.19.0
- **發現日期**: 2026-05-23（W1-050 ANA 全 src 盤點）
- **風險等級**: 高
- **標籤**: `chrome-extension` `nodejs-api` `esbuild` `runtime-mismatch` `jest-false-positive` `eslint` `ce-runtime`

---

## 與其他 error-pattern 的關係

| Error Pattern | 關聯性 | 說明 |
|--------------|--------|------|
| PC-165（false-positive-fix-chain） | 並列關係（共通表層症狀）| 共享「測試綠燈但 runtime 失效」表層症狀，但根因領域正交：PC-165 聚焦「修復鏈 + mock 替代 + 後續信任」三層共振（流程層）；IMP-078 聚焦「Jest jsdom Node globals vs 瀏覽器 esbuild bundle API 可用性差異」（實作層）。交集案例為 W1-047.1~.5（既觸發 IMP-078 API 誤用，也具備 PC-165 acceptance 全勾 + commit + 後續推進的修復鏈特徵）|
| ARCH-013（ESM/CJS 混合匯出）| 弱相關（同屬建置環境差異類） | ARCH-013 聚焦 ESM/CJS 模組格式差異；IMP-078 聚焦 Node.js API 與瀏覽器 API 可用性差異；兩者共同根因是「建置環境差異未被靜態防護」|
| ARCH-021（模組組裝遺漏靜默斷裂） | 弱相關（同屬靜默失效類） | 共通機制：問題在 unit test 層不可見，只在端到端執行時暴露；觸發維度不同（ARCH-021 是組裝遺漏，IMP-078 是 API 環境差異）|

**分類說明**：歸 `implementation/`（IMP）而非 `process-compliance/`（PC），觸發點與防護機制均位於程式碼實作層（`src/` API 選擇 + ESLint + esbuild + bundle scan），非流程協作層。

---

## 問題分析

### 症狀

- `npm test` 全套件通過 → acceptance 勾選 → `ticket track complete`
- 實機載入 CE 後 DevTools 顯示 `ReferenceError: global is not defined` 或 `process is not defined`
- 受影響的 CE runtime 頁面（overview / popup / SW / content script）完全不可用

### 根本原因（5 Why）

1. CE runtime 出現 `ReferenceError: global is not defined` — `src/` 使用了 `global.FileReader` 等 Node.js 全域變數
2. 為何 `src/` 使用 Node.js 全域？— Jest 測試下一切正常，開發者未意識到 CE runtime 差異
3. 為何 Jest 無法偵測？— Jest 在 Node.js + jsdom 執行，`global`/`process`/`require` 天然可用；斷言聚焦邏輯正確性，不覆蓋「API 是否在目標環境存在」維度
4. 為何 esbuild bundle 不自動解決？— esbuild `platform: browser, format: iife` 設計上不 polyfill Node.js runtime API；`global`/`process` 等 runtime 物件不在預設 define 範圍
5. **根本原因**：測試環境（Node.js + jsdom）與部署環境（瀏覽器 + IIFE bundle）的 API 可用性存在根本性差異，但專案缺乏靜態防護（ESLint）和建置期驗證（bundle scan），使差異對開發流程完全透明，「測試通過 = 可部署」假設在此情境不成立。

### 觸發 API SSOT

以下 API 在 `src/` 中使用必然觸發此 pattern（CE bundle 中使用致命）：

| API | 類別 | CE 替代方案 | Runtime 影響 |
|-----|------|-----------|-------------|
| `global` 裸用 | Node.js 全域 | `globalThis`（ES2020+，CE 安全）| ReferenceError，IIFE 中斷 |
| `process.env.NODE_ENV` | Node.js 環境變數 | esbuild `define` 在 build 時替換為字串常量 | ReferenceError |
| `process.hrtime()` | Node.js 計時 | `performance.now()`（Web API）| ReferenceError |
| `process.nextTick()` | Node.js 事件循環 | `queueMicrotask()` 或 `setTimeout(fn, 0)` | ReferenceError |
| `process.memoryUsage()` | Node.js 記憶體 | `performance.memory`（Chrome-only）或移除 | ReferenceError |
| `process.on('uncaughtException')` | Node.js 事件 | `self.addEventListener('error')` | ReferenceError |
| `require('crypto').randomBytes()` | Node.js 模組 | `crypto.getRandomValues()`（Web Crypto API）| ReferenceError |
| `require('crypto').createHash()` | Node.js 模組 | `crypto.subtle.digest()`（Web Crypto API）| ReferenceError |
| `global.gc()` | Node.js debugging | 不可用（CE runtime 無 V8 GC 暴露，移除或改用 `FinalizationRegistry`）| ReferenceError |

觸發條件聯集：`src/` 使用上表 API + 無 `typeof` guard + esbuild 未配置 polyfill/define + 測試斷言不覆蓋環境前提。

---

## 防護方向

### 防護一：ESLint `no-restricted-globals` 靜態檢查（短期，優先實施）

在 `.eslintrc` 或 `eslint.config.js` 加入禁用規則，阻止 `src/` 直接引用 Node.js 全域：

```json
{
  "rules": {
    "no-restricted-globals": [
      "error",
      {
        "name": "global",
        "message": "CE runtime 無 Node.js global，請改用 globalThis"
      },
      {
        "name": "process",
        "message": "CE runtime 無 process，env 請用 esbuild define，計時請用 performance.now()"
      },
      {
        "name": "Buffer",
        "message": "CE runtime 無 Node.js Buffer，請改用 Uint8Array 或 TextEncoder"
      },
      {
        "name": "__dirname",
        "message": "CE runtime 無 __dirname，此為 Node.js 模組 API"
      },
      {
        "name": "__filename",
        "message": "CE runtime 無 __filename，此為 Node.js 模組 API"
      }
    ],
    "no-restricted-imports": [
      "error",
      {
        "paths": [
          {
            "name": "crypto",
            "message": "CE runtime 無 Node.js crypto 模組，請改用 Web Crypto API (globalThis.crypto)"
          },
          {
            "name": "fs",
            "message": "CE runtime 無 Node.js fs 模組"
          },
          {
            "name": "path",
            "message": "CE runtime 無 Node.js path 模組"
          }
        ]
      }
    ]
  }
}
```

**注意**：`src/core/migration/` 為 dev-only，可用 `/* eslint-disable no-restricted-globals */` 豁免或移至 `scripts/`。

**Why**：撰寫程式碼時即攔截，成本最低、防護最早（IDE 即時提示）。

### 防護二：esbuild `define` 配置（中期，消除 process.env 致命點）

在 `scripts/build.js` esbuild 配置加入 `define`：

```javascript
define: {
  'process.env.NODE_ENV': JSON.stringify(mode),  // 'development' | 'production'
  'process.env.JEST_WORKER_ID': 'undefined',
},
```

**驗證**：`grep -c 'process\.env\.NODE_ENV' dist/*.js` 應回傳 0。**Why**：本專案 13 處使用，影響全 4 個 CE runtime；esbuild define 零侵入性，build 時一次消除。

### 防護三：Bundle scan 腳本（長期，建置期驗證）

`scripts/verify-bundle-ce-compat.sh` — 掃描 `dist/` 不含已知危險 API：

```bash
#!/bin/bash
DIST_DIR="dist"; ERRORS=0
grep -rn '\bglobal\.' "$DIST_DIR" --include="*.js" | grep -v 'globalThis' \
  && { echo "[ERROR] global.* 裸用"; ERRORS=$((ERRORS+1)); }
grep -rn 'process\.\(hrtime\|nextTick\|memoryUsage\|on\)' "$DIST_DIR" --include="*.js" \
  && { echo "[ERROR] process.* Node.js API"; ERRORS=$((ERRORS+1)); }
grep -rn 'process\.env\.NODE_ENV' "$DIST_DIR" --include="*.js" \
  && { echo "[ERROR] process.env.NODE_ENV 未被 define 替換"; ERRORS=$((ERRORS+1)); }
grep -rn "require\(['\"]crypto['\"]\)\|\.randomBytes\b\|\.createHash\b" "$DIST_DIR" --include="*.js" \
  && { echo "[ERROR] Node.js crypto 殘留"; ERRORS=$((ERRORS+1)); }
[ $ERRORS -eq 0 ] && echo "[PASS] CE bundle 相容性檢查通過" || { echo "[FAIL] $ERRORS 項問題"; exit 1; }
```

加入 `package.json` scripts：`"verify:ce-compat": "bash scripts/verify-bundle-ce-compat.sh"`，並在 `build:dev` / `build:prod` 末段串接 `&& npm run verify:ce-compat`。

**Why**：ESLint 防護 src/ 層；bundle scan 防護「esbuild define 是否實際生效」和「API 從依賴鏈滲入」，兩層互補。

---

<!-- PC-093-exempt: history:W1-050 + W1-001.2.1 + W1-047.1~.5 為已完成歷史錨點，非延後決策 -->
## 動機案例

### W1-050 ANA + W1-047.1~.5（2026-05-23，v0.19.0）

W1-047.1~.5（BookFileImporter 五個連鎖修復）acceptance 全勾 + npm test 通過 + commit 完成 → W1-001.2.1 實機驗證：UC-04 JSON 匯入，overview runtime 立即崩潰（`ReferenceError: global is not defined` at `file-reader-factory.js:24`）→ W1-050 全域盤點 ANA：致命 21 處（`global` 裸用 6、`process.env.NODE_ENV` 13、`process.*` 多、`require('crypto')` 6）→ W1-050.1~.4 修復 IMP → W1-050.5 本 error-pattern。

**代價量化**：單一根因（CE-Node 環境前提未防護）引發 8+ ticket 連鎖，阻塞版本里程碑。

### W1-001.2.1 觸發細節（`src/utils/file-reader-factory.js` L24）

```javascript
const FileReader = global.FileReader || window.FileReader; // 錯誤：global 裸用，CE runtime ReferenceError
const FileReader = globalThis.FileReader;                  // 正確：globalThis 跨 CE context 安全
```

---

## 正確做法

### 自查清單（新寫 CE src/ 程式碼前）

對照§問題分析「觸發 API SSOT」表逐項自查。高頻項：

- [ ] `global` → `globalThis`
- [ ] `process.env.NODE_ENV` → 確認 `build.js` 有 `define` 配置
- [ ] `process.hrtime/nextTick/memoryUsage` → `performance.now()` / `queueMicrotask()` / `performance.memory`
- [ ] `require('crypto')` → `globalThis.crypto.getRandomValues()` / `crypto.subtle.digest()`
- [ ] `global.gc()` → 移除（CE runtime 無 V8 GC 暴露）
- [ ] SW context `window.*` → `self.*`

### 正反程式碼對照（最致命範例）

```javascript
// 錯誤：CE bundle 致命（全部 ReferenceError）
const reader = global.FileReader;             // global 裸用
const env = process.env.NODE_ENV;             // process.env 未 define
const bytes = require('crypto').randomBytes(16); // Node.js 模組
process.nextTick(() => { ... });              // Node.js 事件循環

// 正確：CE 安全等效替換
const reader = globalThis.FileReader;         // globalThis 跨 context 安全
const env = 'production';                     // esbuild define 替換後的字串常量
const bytes = new Uint8Array(16);            // Web API
globalThis.crypto.getRandomValues(bytes);    // Web Crypto API
queueMicrotask(() => { ... });               // Web API
```

---

## 抽象層級分析（必填）

| 欄位 | 內容 |
|------|------|
| 症狀層級 | 工具層（CE DevTools ReferenceError）/ 實作層（`src/` 使用 Node.js API）|
| 根因層級 | 架構層（測試環境與部署環境 API 可用性差異未被靜態防護）|
| 跨層路徑 | 實作層（API 使用）→ 工具層（Jest 通過）→ 架構層（環境差異無防護閘）|
| 防護層級 | 實作層：ESLint（撰寫期）；工具層：esbuild define（build 時）；架構層：bundle scan（建置驗證）|
| 跨層警示 | 禁止提升至認知層（「開發者不細心」）；根因是架構防護機制缺失，非個人失誤 |

### 相關資源

<!-- PC-093-exempt: history:W1-050 + W1-001.2.1 + W1-047.1~.5 為已完成歷史錨點，非延後決策 -->
- `docs/work-logs/v0/v0.19/v0.19.0/tickets/0.19.0-W1-050.md` — W1-050 ANA 全 src 盤點（致命 21 處完整表格 + 修復 IMP 拆分）
- `docs/work-logs/v0/v0.19/v0.19.0/tickets/0.19.0-W1-001.2.1.md` — 觸發案例（file-reader-factory global 裸用實機崩潰）
- `docs/chrome-extension-dev-guide.md` — CE 開發規範（含 Manifest V3 API 限制完整說明）
- `.claude/error-patterns/process-compliance/PC-165-false-positive-fix-chain.md` — 上位 pattern（測試綠燈不等於 runtime 正確）

---

**Last Updated**: 2026-05-30
**Version**: 1.1.0 — W1-122 認知負擔重構（363→≤270 行 / 10→7 H2 / §觸發條件+§問題描述+§根本原因合併為§問題分析 / API 對照表 SSOT 整併 / §標籤+§相關資源併入相關章節）
