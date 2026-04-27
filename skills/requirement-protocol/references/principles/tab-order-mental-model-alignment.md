# Tab Order = DOM Order = Mental Model 三者對齊

> **角色**：本卡是 `requirement-protocol` 的支撐型原則（principle）、被相關抽象層原則段引用、是 [`verification-timeline-checkpoints.md`](./verification-timeline-checkpoints.md) 中 Checkpoint 1「列使用者意圖完整集」A11y 維度的展開。
>
> **何時讀**：設計或審視互動式 UI 的 tab 順序前、或想用 `tabindex` 強制改變順序時、用本卡判斷該重排 DOM 還是用 tabindex（後者是反模式）。

---

## 核心原則

**Tab 順序 = DOM 順序 = 使用者 mental model 的互動順序、三者該對齊。**

| 軸                | 由什麼決定                         | 該對齊到什麼            |
| ----------------- | ---------------------------------- | ----------------------- |
| DOM 順序          | HTML / template 結構               | Mental model 的互動順序 |
| Tab 順序          | DOM 順序（除非 tabindex 強制覆寫） | DOM 順序                |
| Mental model 順序 | 使用者預期「先做 X 再做 Y」的流程  | UI 設計意圖             |

三者偏差的後果：

- DOM ≠ mental model：視覺 / tab 順序跟使用者期望不一致、a11y 體驗差
- DOM ≠ tab order（用 `tabindex > 0`）：DOM 改變時 tab 順序維護成本爆炸（反模式）
- 全對齊：DOM 簡單、tab 自然、a11y 預設正確

要解決不對齊、**優先重排 DOM**、不要用 `tabindex` 強制覆寫。

---

## 為什麼三者該對齊到 DOM 順序

### Tab 順序跟 DOM 順序綁定是 spec 規定

HTML5 spec：tabbable elements 預設依 source order（DOM 順序）navigate。要改變只能用 `tabindex` 覆寫。

`tabindex` 三種值：

| tabindex             | 行為                                               |
| -------------------- | -------------------------------------------------- |
| `0` 或不寫           | 跟 DOM 順序、可 tab 到（依元素本身的 tabbability） |
| `-1`                 | 不能 tab 到、但可被 `.focus()` 程式 focus          |
| `> 0`（如 `1`、`2`） | 強制覆寫順序、所有 `> 0` 的元素先 tab、按數值升序  |

`tabindex > 0` 反模式：

- 全頁面只要有任何元素用 `tabindex > 0`、整個 tab 順序變混亂（其他 `0` / 不寫的元素都被推到後面）
- 維護成本：DOM 改了、所有 `tabindex > 0` 的數值都要重排
- A11y：screen reader 跟視覺使用者體驗到不同順序

唯一合法用法：要把元素「移出 tab cycle」用 `tabindex="-1"`（例如 modal 開啟時鎖住背景）。

### Mental model 順序由 UI 設計決定

互動式 UI 隱含一個流程：使用者預期「先做 X 再做 Y」。例如：

| UI 類型  | 預期 mental model 順序                                 |
| -------- | ------------------------------------------------------ |
| 搜尋頁   | 1. 打 query → 2. 篩選範圍 → 3. 看結果 → 4. 載入更多    |
| 表單     | 從上到下、必填欄位先、subtmit 在最後                   |
| Wizard   | Step 1 → Step 2 → Step 3 → Submit                      |
| 商品列表 | 1. Sort / filter → 2. 看商品 → 3. 加入購物車           |
| Modal    | Modal 內容 → primary action → secondary action → close |

設計者腦中有這個順序、寫 HTML 時要把它具體化成 DOM 順序。**DOM 順序就是把 mental model 寫進 code 的方式**。

---

## 多面向：常見不對齊 case

### 面向 1：Filter 在 search input 之前

```html
<!-- DOM 順序：scope 先 → search input 後 -->
<div class="search-scope">...</div>
<div id="search"></div>  <!-- search input 在裡面 -->
```

Tab 順序：scope radios → search input。但 mental model 是「先打字再篩選」、Tab 應該先到 input。

**修法**：DOM 重排、把 scope 移到 search input 之後。視覺位置由 CSS `position: absolute` 控制、不受 DOM 順序影響。

### 面向 2：Submit 按鈕在 form 中間

```html
<form>
  <input name="email">
  <button type="submit">送出</button>  <!-- ❌ 太早 -->
  <textarea name="message"></textarea>
</form>
```

Tab 順序：email → submit → textarea。使用者打完 email 按 Enter 就送出、textarea 還沒填。

**修法**：submit 移到所有 input 之後。

### 面向 3：Logo / nav 在主要 CTA 之前

```html
<header>
  <a href="/">Logo</a>
  <nav>... 5 個 links ...</nav>
</header>
<main>
  <button>主要 CTA</button>  <!-- 使用者要按這個 -->
</main>
```

Tab 順序：6 個 nav links → CTA。使用者要 tab 6 次才到 CTA。

**修法**：考慮加 「skip to main content」link（A11y 標準做法）— `<a href="#main-content" class="skip-link">`。第一個 tab 就跳過 nav 到 main。

### 面向 4：Modal 開啟時 background 仍 tabbable

```html
<div class="background-content">
  <a href="...">某連結</a>  <!-- 仍可 tab 到 -->
</div>
<div role="dialog">
  <input>
  <button>確認</button>
</div>
```

Tab 順序：背景連結 → modal input → confirm。使用者 tab 出 modal 跑回背景。

**修法**：modal 開啟時、用 `inert` attribute（modern）或所有背景元素設 `tabindex="-1"`（傳統）把它們踢出 cycle。`<dialog>` native 自動處理。

---

## 不對齊的修法：優先重排 DOM

### 第一順位：重排 DOM

把元素照 mental model 順序排在 HTML / template 裡。視覺位置如果跟 DOM 順序不同、用 CSS `order`（flex / grid）、`position: absolute`、`grid-template-areas` 控制。

```html
<!-- DOM 順序對齊 mental model：input → scope → drawer -->
<div id="search"></div>
<div class="search-scope">...</div>
```

```css
/* 視覺：scope 浮在 input 跟 drawer 之間（跟 DOM 順序無關） */
.search-shell { position: relative; }
.search-scope {
  position: absolute;
  top: calc(var(--input-h) + 8px);
}
```

**Tab 順序自然對齊 DOM、視覺位置由 CSS 獨立控制** — 兩個維度解耦、不互相影響。

### 第二順位：JS 動態移動 DOM

如果元素因為 framework 限制無法 hard-coded 在對的位置（例如某 vendor library 強制 mount 點）、用 JS 在 mount 後 reparent 元素到對的位置。

```js
// 某元件 mount 後、把 scope 移到 input 跟 drawer 之間（如果 framework 允許）
const scope = document.querySelector('.search-scope');
const drawer = document.querySelector('.ui-drawer');
drawer.parentElement.insertBefore(scope, drawer);
```

風險：framework 重渲染可能 reparent 回去。要驗證穩定性。

### 第三順位（不推薦）：tabindex 強制

```html
<input tabindex="1" name="search">  <!-- ❌ tabindex > 0 -->
<div tabindex="2" class="search-scope">...</div>
```

只在前兩種都做不到時用。維護成本高、a11y 跟設計工具支援差。

---

## 不該套用本原則的情境

「DOM = tab = mental model 三者對齊」原則在多數情境成立、但有合理例外：

| 情境                 | 為什麼不該強制對齊                                   |
| -------------------- | ---------------------------------------------------- |
| 純展示頁面（無互動） | 沒 mental model 順序可言、預設 DOM 順序就好          |
| 動態生成 list 元素   | List 元素數量不固定、tab order 跟著 DOM 自然走是對的 |
| 模糊的 mental model  | 當 UI 設計沒明確流程、DOM 自然順序通常已經夠用       |
| Framework 不允許重排 | 接受次優、加 explicit hint 告知使用者                |

四類共同特徵：**沒有清楚的「使用者該先做 X 再做 Y」流程** — 本原則建立在「有 mental model 可對齊」上、沒有時自然不適用。

---

## 跟其他抽象層原則的關係

| 原則                                                                                             | 跟本卡的關係                                                            |
| ------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------- |
| 「鍵盤可達性」                                                                                   | 本卡是「邏輯 tab 順序」要素的展開、含 tabindex > 0 反模式詳解           |
| [`ease-of-writing-vs-intent-alignment.md`](./ease-of-writing-vs-intent-alignment.md)             | DOM 順序便利（先寫先 render）、mental model 對齊需要刻意設計 — 反相關   |
| [`minimum-necessary-scope-is-sanity-defense.md`](./minimum-necessary-scope-is-sanity-defense.md) | tabindex > 0 是「擴張範圍」反模式 — 一個 tabindex > 0 影響整頁 tab 順序 |
| 「native HTML > ARIA」                                                                           | Native HTML 元素自帶正確 tab 行為、不需要 ARIA tabindex 補              |

---

## 判讀徵兆

| 訊號                                         | 該做的事                                       |
| -------------------------------------------- | ---------------------------------------------- |
| 寫了 `tabindex="1"` 或更大的數字             | 換重排 DOM、避免 tabindex > 0                  |
| Tab 順序跟「使用者會先做什麼」感覺反         | 列 mental model 流程、檢查 DOM 順序            |
| 做 a11y review 才發現 tab 順序怪             | Checkpoint 1 沒列鍵盤使用 case、補進開工前清單 |
| 用 JS reparent 元素改順序、framework 改回來  | 重新評估架構、把元素放在 framework 邊界外      |
| 內心 OS：「視覺位置是 X、所以 DOM 也該在 X」 | 視覺跟 DOM 解耦才是對的設計                    |
| 看到 `tabindex="-1"` 在不該被 tab 的元素上   | 合理使用（modal 背景 / 先 focus 後 reveal）    |

**核心原則**：DOM 順序是寫進 code 的 mental model、tab 順序是使用者體驗的 mental model — 兩者該由「重排 DOM」對齊、不該由「tabindex」強制。視覺位置跟 DOM 順序解耦（用 CSS 控制）、讓兩者各自獨立優化。
