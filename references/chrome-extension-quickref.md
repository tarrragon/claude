# Chrome Extension 開發規範速查

> **用途**：本檔案從 CLAUDE.md §7.3 lazy-load 引入，載入時機為寫 Chrome Extension 程式碼前。關鍵限制與測試環境差異速查表。
>
> **完整規範**：`docs/chrome-extension-dev-guide.md`

---

## 關鍵限制速查

Chrome Extension 環境有多項與 Node.js 不同的限制，開發和修改程式碼前**必須閱讀**：

| 限制 | 說明 | 解法 |
|------|------|------|
| 禁用 `require()` | Content Script 不支援 CJS | esbuild IIFE bundle |
| 禁用 bare specifier | `import x from 'src/...'` 無效 | 相對路徑或 esbuild alias |
| 禁用 `global` | 非 Node.js 環境 | 使用 `globalThis` |
| `window` 限制 | Service Worker 無 `window` | 使用 `self` 或 `globalThis` |
| Storage API | keys 必須是陣列 `['key']` | 非 `'key'` 字串 |
| 事件監聽器 | 必須在 SW 頂層註冊 | 禁止 async 延遲註冊 |
| Build 必須 bundle | 不能只複製檔案 | esbuild 三入口點 bundle |

---

## 測試環境差異（常見測試失敗根因）

| 問題 | 說明 |
|------|------|
| Jest 用 jsdom，非真實 Chrome 環境 | Chrome API（storage/runtime/tabs）需 mock |
| CJS/ESM 雙模式 | 模組需同時支援 `module.exports` 和 `export` |
| `performance.now` mock | 遞增值需手動管理，否則 OOM |
| DOM 選擇器 | Readmoo 頁面結構會變更，選擇器需多層 fallback |

---

**來源**：從 CLAUDE.md §7.3 外移（W10-077.1 實施 W10-073.3 骨架設計）
