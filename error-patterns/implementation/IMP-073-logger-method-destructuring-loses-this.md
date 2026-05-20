# IMP-073: Logger 方法解構導致 this 遺失 + Promise hang

## 基本資訊

- **Pattern ID**: IMP-073
- **分類**: 實作 bug（implementation）
- **來源版本**: v0.18.0
- **發現日期**: 2026-05-17
- **風險等級**: 中
- **影響範圍**: class-based logger 呼叫端（任何把 `logger.info` 等方法當值傳遞 / 解構 / 賦值的情境）

---

## 問題描述

### 症狀

呼叫端把 class-based logger 的方法解構或賦值給變數（`const fn = logger.info` / `const { info } = logger`）後再呼叫，方法執行時拋出 `TypeError: Cannot read properties of undefined (reading '<some-field>')`。若呼叫發生在 `setTimeout` / `setInterval` / `microtask` 等 async context，錯誤被吞掉，外層 `Promise` 既不 resolve 也不 reject，造成測試或代理人 timeout（典型 30s hang）。

### 表現形式

| 階段 | 行為 |
|------|------|
| 解構 | `const fn = logger.info` —— 此時尚無錯誤 |
| 呼叫 | `fn('msg')` —— 內部存取 `this.currentLevel` / `this.formatter` 等實例欄位 |
| this 綁定 | 方法以一般函式呼叫，`this` 為 `undefined`（strict mode）或 `globalThis`（非 strict）|
| 拋錯 | `TypeError: Cannot read properties of undefined (reading 'currentLevel')` |
| async 吞錯 | 若在 `setTimeout` callback 內拋出，錯誤進入 host 的 unhandled exception 通道，不會被外層 try/catch 或 Promise reject 接住 |
| 結果 | 外層 Promise 永遠 pending；測試 / agent 等到 timeout（30s）|

---

## W6-012.9.1 案例（歷史證據）

### 時序

1. W6-012.9.1 修復 readmoo-adapter logger 級別（commit `909865a5`）
2. 代理人實作期間呼叫端透過解構方式取得 logger 方法
3. setTimeout callback 中呼叫解構方法 → `TypeError: this.currentLevel` undefined
4. 錯誤被 setTimeout 吞掉，外層 Promise 既未 resolve 也未 reject
5. 測試 / 代理人 hang 30s 直至 timeout

### 證據

- W6-012.9.1 commit `909865a5`
- 代理人回報「promise hang 30s」現象與 logger 級別修復同 commit 視窗內出現
- 重現範例見下方「重現步驟」

---

## 根因分析

### 直接原因

JavaScript class 方法依賴 `this` 綁定。透過「方法呼叫語法」`obj.method()` 才會把 `obj` 自動綁為 `this`；一旦把方法本身賦值給變數，呼叫時的 `this` 由呼叫方式決定，而非定義時的 owner：

```js
class Logger {
  constructor() { this.currentLevel = 'info'; }
  info(msg) { if (this.currentLevel === 'info') console.log(msg); }
}

const logger = new Logger();
logger.info('ok');           // OK：this = logger
const fn = logger.info;
fn('boom');                  // TypeError：this = undefined
```

### 為何 async context 會吞錯

`setTimeout` callback 由 host scheduler 呼叫，不在任何 Promise chain 上：

```js
function run() {
  return new Promise((resolve, reject) => {
    const fn = logger.info;
    setTimeout(() => {
      fn('msg');               // 在這裡 throw
      resolve();               // 永遠不會執行
    }, 10);
  });
}
```

- `setTimeout` callback 拋的錯不會傳到外層 `try/catch`
- 不在 Promise executor 同步階段，`reject` 不會被自動呼叫
- 外層 `await run()` 永遠 pending

### 深層原因

| 動機類型 | 表面說法 | 深層動機 |
|---------|---------|---------|
| A 呼叫端便利 | 「解構簡潔，少打字」 | 忽視 class 方法 vs 純函式語意差異 |
| B 缺綁定保護 | 「Logger 簡單沒必要 bind」 | 假設呼叫端永遠用 `logger.info()` 完整語法 |
| C async 隱蔽 | 「await 應該抓到所有錯」 | 未理解 timer callback 與 Promise chain 分離 |

---

## 重現步驟

最小重現範例（10 行）：

```js
class Logger {
  constructor() { this.currentLevel = 'info'; }
  info(msg) { if (this.currentLevel === 'info') console.log(msg); }
}

async function reproduce() {
  const logger = new Logger();
  await new Promise((resolve) => {
    const fn = logger.info;        // 解構丟失 this
    setTimeout(() => { fn('hi'); resolve(); }, 10); // throw 被吞，resolve 永不執行
  });
}

reproduce(); // hang forever
```

預期觀察：行程不退出（或外層 timeout 才中斷）。

---

## 防護機制

### 修補方向

| 方案 | 描述 | 成本 |
|------|------|------|
| A. constructor 內 bind | `this.info = this.info.bind(this)` 等逐方法綁定 | 低 |
| B. 用 arrow class field | `info = (msg) => { ... }` 讓方法天生綁定實例 | 低（需 class field 支援）|
| C. 呼叫端禁止解構 | code review / lint 規則禁止 `const { info } = logger` 與 `const fn = logger.info` | 中（靠規範）|
| D. 包裝 Promise + try/catch | setTimeout callback 內 try/catch 後 reject 外層 Promise | 中（治標：暴露錯誤但不修綁定）|

推薦：**A 或 B**（生產端綁定）+ **D**（async 邊界補捕捉），雙層防護。

### Logger.js 補強建議（不在本 ticket 範圍）

可建立後續 ticket 評估在 `src/Logger.js` constructor 加：

```js
constructor() {
  // ...
  for (const m of ['debug', 'info', 'warn', 'error']) {
    this[m] = this[m].bind(this);
  }
}
```

或改寫為 arrow class fields。

### 呼叫端 workaround

在 Logger.js 修補前，呼叫端應：

- 一律使用 `logger.info('msg')` 完整方法呼叫語法
- 必須傳方法當值時包 closure：`const fn = (msg) => logger.info(msg)`
- async / timer callback 內加 try/catch 並 reject 外層 Promise，避免 hang

---

## 與其他 this-loss 場景的差異

| 場景 | this 是否丟失 | 是否 hang |
|------|--------------|----------|
| `obj.method()` 直接呼叫 | 否 | 否 |
| `const fn = obj.method; fn()` 同步呼叫 | **是** | 否（立即 throw）|
| `setTimeout(obj.method, 0)` | **是** | **是**（callback 內 throw 被吞）|
| `setTimeout(() => obj.method(), 0)` | 否（closure 保留）| 否 |
| `Promise.then(obj.method)` | **是** | 否（Promise 會 reject）|

---

**Last Updated**: 2026-05-17
**Version**: 1.0.0
**Source**: W6-012.9.1（commit `909865a5`）修復 readmoo-adapter logger 級別期間，代理人遇 30s promise hang，根因為 `const fn = logger.info` 解構丟失 this 綁定 + setTimeout 吞掉 TypeError 導致外層 Promise 永不 reject
