# Framework Coexistence

跟 framework-managed DOM 共處：把 framework 子樹當禁區、客製 UI 注入到 boundary 外、JS 操作邊界由穩定性梯度決定、外部組件客製優先用公共介面。

適用：跟 vendor library / framework component（pagefind、Vue widget、React component、jQuery plugin）共存的客製、注入客製 UI、覆寫 vendor 樣式。
不適用：完全自家寫的元件（沒有 framework 介入）。

> **自包含聲明**：閱讀本文件不需要先讀其他 reference。本文件涵蓋 framework 邊界辨識、JS 操作的四級安全度、外部組件客製的四層合作。

---

## 何時參閱本文件

| 訊號                                                     | 該做的第一件事                                 |
| -------------------------------------------------------- | ---------------------------------------------- |
| 客製 UI 注入到 framework 子樹後被還原                    | 移到 framework 邊界外、用 CSS 控制視覺位置     |
| Vendor library 升級後客製樣式失效                        | 改用公共介面（CSS var / API）                  |
| 不確定 reparent / 改 attribute / 改 textContent 哪個安全 | 看下方「JS 操作四級安全度」                    |
| 客製需求看似簡單但要動 framework 內部結構                | 評估「值不值得」、把成本攤開（見 cost report） |
| 寫了 MutationObserver 補 framework reconcile 後元素還原  | 換思路：注入到邊界外、不需要 observer          |

---

## 為什麼 framework-managed DOM 要當禁區

Framework（React / Vue / vendor JS widget）對它管的 DOM 子樹有**所有權**：

- State 變動觸發 reconciliation、子樹重建
- 我們改的 attribute / textContent / 子節點被還原
- innerHTML 改動可能觸發 Vue / React 的 dev mode 警告
- Event listener 失效（節點被替換）

把客製 UI **注入到 framework 邊界外**（vendor root 的 sibling、或上一層 container 的另一個 child）→ framework 不管它 → 不會被還原。

---

## Framework 邊界的識別

### 邊界的可見訊號

| 訊號                                            | 含義                             |
| ----------------------------------------------- | -------------------------------- |
| `<div id="app">` / `data-vue-component`         | Vue / 自家 framework 的 root     |
| `<div data-reactroot>` / React Fiber 結構       | React 的 root                    |
| `.pagefind-ui` / `.algolia-search` 等命名空間   | Vendor library 的 root           |
| 子節點 attribute 含 `__data` `__key` 等內部標記 | Framework 內部結構、子節點被管理 |

邊界外的 sibling / parent 通常是「自家 HTML」、安全。

### 範例：Pagefind 的邊界

```html
<div class="search-page">           ← 自家 (邊界外、可控)
  <h1>Search</h1>                   ← 自家
  <div class="custom-filter">       ← 自家、客製 UI 放這裡
  </div>
  <div class="pagefind-ui">          ← Vendor root (邊界、入內就是禁區)
    <form class="pagefind-ui__form"> ← Pagefind 管
      <input ...>
      <div class="pagefind-ui__drawer">  ← Pagefind 管（重渲染時清空）
      </div>
    </form>
  </div>
</div>
```

`.custom-filter` 跟 `.pagefind-ui` 是 sibling、不在 vendor 子樹內 → 用 CSS grid / absolute 定位讓它看起來在 search 流程內、但實際 framework 不管它。

---

## JS 操作的四級安全度

對 framework-managed 元素的操作、按穩定性排序：

| 操作                | 安全度 | 為什麼                                          | 補救                     |
| ------------------- | ------ | ----------------------------------------------- | ------------------------ |
| Reparent 整節點     | 高     | 整節點搬遷、framework 通常不會還原              | -                        |
| 改 inline style     | 中-高  | Style 通常不被 reconcile（除非 framework 重設） | 用 CSS class 取代        |
| 改 attribute        | 中     | 部分 framework 會 reconcile attribute           | 用 MutationObserver 補回 |
| 改 textContent      | 中-低  | 多數 framework 會 reconcile text                | 改注入新節點到邊界外     |
| 改 innerHTML        | 低     | 子節點全重建、event listener 失效               | 不要改、用其他方法       |
| 改 framework 子節點 | 極低   | reconcile 還原、可能 dev warning                | 不要動                   |

選擇規則：**從最高安全度起步、不行才升級**。

---

## 客製 UI 注入的兩種模式

### 模式 1：注入到 framework 邊界外（推薦）

```js
const customEl = document.createElement('div');
customEl.className = 'custom-filter';
customEl.textContent = 'Filter: All / Title / Content';
document.querySelector('.search-page').appendChild(customEl);
// 注意：appendChild 到 .search-page、不是 .pagefind-ui
```

```css
.search-page {
  display: grid;
  grid-template:
    "h1"
    "form"
    "custom-filter"
    "results";
}
.pagefind-ui { grid-area: form / form / results / results; }
.custom-filter { grid-area: custom-filter; }
```

CSS grid 把客製 UI 排到 search 流程的某個位置、framework 不知情、不還原。

### 模式 2：reparent framework 內節點（次優）

如果客製需要把 framework 內的某個元素移到別處 — reparent 整節點而不是改內部：

```js
const filter = document.querySelector('.pagefind-ui__filters');
const target = document.querySelector('.sidebar');
target.appendChild(filter);  // 整節點搬到 sidebar、不複製
```

整節點搬遷通常 framework 不會「還原」、因為 vDOM diff 看到 node 還在（只是 parent 變了）。

但有 case 例外（部分 framework 用 portal pattern、reparent 會被視為 unmount）→ 第 1 次嘗試後用 playwright 驗證行為、第 2 次失敗就停（見 requirement-protocol/failure-pivot-protocol）。

---

## 外部組件客製的四層合作（穩定性梯度）

跟外部組件合作時、選哪一層客製、決定升級時會不會壞。

| 層          | 範例                                  | 升級穩定性 |
| ----------- | ------------------------------------- | ---------- |
| 公共介面層  | CLI 參數、CSS variable、option 物件   | 最高       |
| 邊界層      | 注入 root 的 sibling、用 CSS 包邊界外 | 高         |
| 邊界 DOM 層 | querySelector vendor 的 root 節點     | 中         |
| 內部結構層  | 改 vendor 子節點 attribute / 樣式     | 最低       |

**選擇順序**：先看公共介面有沒有提供（讀 docs）、沒有再用邊界層、再不行才碰邊界 DOM。內部結構層幾乎不要碰 — 升級時 minor version 都會壞。

### 範例：Pagefind 的客製優先順序

| 需求               | 優先做法                                                          | 次選                                |
| ------------------ | ----------------------------------------------------------------- | ----------------------------------- |
| 改主題色           | 公共：`--pagefind-ui-primary` CSS var                             | 邊界 DOM：覆寫 `.pagefind-ui__form` |
| 加 filter UI       | 邊界：在 `.pagefind-ui` sibling 注入                              | 內部：塞進 `.pagefind-ui__form` 內  |
| 限定 search scope  | 公共：`pagefindOptions.scope: 'main'`                             | 內部：MutationObserver 過濾結果     |
| 改 result 卡片排版 | 邊界 DOM：覆寫 `.pagefind-ui__result` CSS（接受升級時可能要重檢） | -                                   |

---

## Wrong vs Right 對照

### 範例 1：客製 filter UI

**錯**（注入到 vendor 子樹內）：

```js
const filter = document.createElement('div');
filter.textContent = 'Filter: ...';
document.querySelector('.pagefind-ui__form').appendChild(filter);
// → search 觸發 → form 重渲染 → filter 消失
```

**對**（注入到邊界外）：

```js
const filter = document.createElement('div');
filter.className = 'custom-filter';
filter.textContent = 'Filter: ...';
document.querySelector('.search-page').appendChild(filter);
```

```css
.search-page { display: grid; grid-template-areas: "h1" "form" "filter" "results"; }
.pagefind-ui { grid-area: form / form / results / results; }
.custom-filter { grid-area: filter; }
```

### 範例 2：改 vendor 主題色

**錯**：

```css
.pagefind-ui__form { background: blue !important; }
.pagefind-ui__search-input { color: white !important; }
.pagefind-ui__button { background: darkblue !important; }
/* ... 8 條 important */
```

升級後 class 改名 → 全壞。

**對**：

```css
:root {
  --pagefind-ui-primary: #2c5282;
  --pagefind-ui-text: #fff;
  --pagefind-ui-background: #1a202c;
}
```

讀 vendor docs、用提供的 CSS var。升級安全、5 行解決。

### 範例 3：把 vendor filter 移到 sidebar

**錯**（複製 + 同步）：

```js
const original = document.querySelector('.pagefind-ui__filters');
const clone = original.cloneNode(true);
sidebar.appendChild(clone);
// → 兩份、state 不同步、click 事件 listener 沒複製
```

**對**（reparent 整節點）：

```js
const filter = document.querySelector('.pagefind-ui__filters');
sidebar.appendChild(filter);  // 整節點搬遷、event listener 跟著、state 唯一
```

整節點搬遷通常安全 — vDOM 看到 node 還在、不會 reconcile。寫完先用 playwright 驗證行為（dispatch input / click 看 filter 是否還工作）。

---

## 自檢清單（dogfooding）

跟 framework / vendor library 共處時：

- [ ] 我有沒有先看 vendor docs、確認有沒有公共介面（CSS var / API）？
- [ ] 客製 UI 是注入到 framework 邊界外、還是內部？
- [ ] JS 操作的元素是 framework 管的子節點嗎？如果是、有沒有用「四級安全度」最高的操作？
- [ ] reparent / 改 attribute 後、有沒有用 playwright 驗證 framework 沒還原？
- [ ] 升級風險有攤給使用者嗎？（見 requirement-protocol/cost-and-checkpoint）

---


**Last Updated**: 2026-04-26
**Version**: 0.1.0
