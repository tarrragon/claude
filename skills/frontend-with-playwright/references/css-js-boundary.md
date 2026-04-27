# CSS / JS Boundary

CSS 跟 JS 各自負責什麼、邊界由「值能不能 build-time 定下來」決定。`!important` / inline style / specificity 戰是訊號、不是工具。

適用：寫 / 改 CSS 規則、決定 styling 該放 CSS 還是 JS、跟 vendor CSS 共存、檔案組織。
不適用：純 logic JS（沒涉及 styling）。

> **自包含聲明**：閱讀本文件不需要先讀其他 reference。本文件涵蓋 CSS-only vs JS-assisted 判準、class toggle 模式、CSS layers、variable 單一位置、檔案拆分。

---

## 何時參閱本文件

| 訊號                                                | 該做的第一件事                              |
| --------------------------------------------------- | ------------------------------------------- |
| 不確定值該寫進 CSS 還是 JS                          | 問「能 build-time 定下來嗎」                |
| 即將寫 `!important`                                 | 停 — 換 CSS layers 思路                     |
| 即將寫 `el.style.setProperty(..., 'important')`     | 停 — 換 class toggle                        |
| Inline `<style>` / `<script>` 超過 30 行            | 拆出獨立檔案、讓 Hugo / build pipeline 處理 |
| CSS variable 在 3 個地方定義                        | 集中到單一定義位置、其他地方只引用          |
| Vendor CSS 跟自家 CSS 打 specificity 戰             | `@layer` 包 vendor、自家 unlayered 自動贏   |
| Runtime 量測值跟 hardcoded 值在同一個對齊基準上混用 | 全選一邊、不要混搭                          |

---

## 為什麼 CSS / JS 邊界要清楚

樣式邏輯散落在 inline style + CSS file + JS setProperty + `!important` 的後果：

1. 改一個顏色要 grep 三個地方、其中一個改不到
2. DevTools 看不出「為什麼這個值在這裡」（inline style 沒 class hint、important 是核武）
3. 升級 vendor 後 specificity 戰失敗、自家規則失效

清楚的邊界 = **CSS 描述「在某狀態下長什麼樣」、JS 切換狀態（toggle class / 寫 var）**。樣式定義集中在 CSS、JS 不直接操作 inline style。

---

## 邊界判準：值能不能 build-time 定下來

### CSS-only：值能 build-time 定下來

- Design token（`--brand-color`、`--gap-base`）
- 固定 breakpoint / aspect ratio
- 元件預設尺寸
- 跨狀態的視覺差異（`.expanded`、`.loading`）

寫成 CSS variable + class toggle、JS 只負責加減 class。

### JS-assisted：必須 runtime 才能知道

- Form 高度（隨字型 / line-height 變動）
- Container 寬度（隨 viewport / sidebar 變動）
- Scroll position
- 元素的 bounding rect

JS 量測後**寫回 CSS variable**、CSS 仍然只讀變數：

```js
const formHeight = form.getBoundingClientRect().height;
document.documentElement.style.setProperty('--form-height', `${formHeight}px`);
```

```css
.scope { top: calc(var(--form-height) + var(--gap)); }
```

CSS 不知道值怎麼來的、只知道讀 var — 換 framework / 換量測方式時、CSS 不動。

---

## 模式 1：Class toggle 取代 inline style

### 反例

```js
// JS 直接設 inline style + important
function showScope() {
  scope.style.setProperty('display', 'block', 'important');
}
function hideScope() {
  scope.style.setProperty('display', 'none', 'important');
}
```

DevTools 看到 inline style + important、不知道為什麼、難 debug。

### 對例

```js
function setScope(visible) {
  scope.classList.toggle('is-visible', visible);
}
```

```css
.scope { display: none; }
.scope.is-visible { display: block; }
```

樣式留在 CSS、JS 只 toggle state。改視覺只動 CSS、改 logic 只動 JS。

---

## 模式 2：CSS Layers 取代 specificity 戰

### 反例

自家規則被 vendor 的 `.pagefind-ui .target` 蓋過、寫 `.parent .container .target` 加 specificity、再不行加 `!important`。

### 對例

```css
@layer vendor {
  @import url('vendor/pagefind.css');
}

/* 自家規則 unlayered → 自動贏所有 layered 規則 */
.target { color: var(--brand); }
```

`@layer vendor` 把 vendor CSS 放進低優先級的 layer、自家 unlayered 規則自動贏。再也不用打 specificity 戰。

`@layer` 在 Chrome 99+ / Firefox 97+ / Safari 15.4+ 全部支援（2022+）。

---

## 模式 3：CSS Variable 單一定義位置

### 反例

```css
:root { --gap: 16px; }
.results { --gap: 16px; padding: var(--gap); }
.scope { --gap: 16px; margin-top: var(--gap); }
/* 三處定義、改一個地方漏改 */
```

### 對例

```css
:root { --gap: 16px; }
.results { padding: var(--gap); }
.scope { margin-top: var(--gap); }
```

定義集中 `:root`（global）、`.page-search`（page-scoped）、或 `.pagefind-ui`（component-scoped）— **挑最窄能涵蓋所有用途的 selector**。其他地方只引用、不重新定義。

JS 寫 variable 也寫到同個 selector：

```js
document.documentElement.style.setProperty('--form-height', '...');
// 而不是 form.style.setProperty(...) 在 form 上設
```

---

## 模式 4：Inline 程式碼超過 30 行就拆檔

### 反例

```html
<style>
  .scope { ... }
  .results { ... }
  /* ... 50 行 */
</style>
<script>
  function decorate() { ... }
  /* ... 80 行 */
</script>
```

問題：沒 syntax highlight、沒 minify、沒 fingerprint cache-bust、改一行整個 HTML reload。

### 對例

```html
{{ $css := resources.Get "css/search.css" | minify | fingerprint }}
<link rel="stylesheet" href="{{ $css.RelPermalink }}">

{{ $js := resources.Get "js/search.js" | minify | fingerprint }}
<script src="{{ $js.RelPermalink }}" defer></script>
```

獨立檔案 → IDE 支援、build pipeline 處理 minify / fingerprint、cache-bust 自動。

---

## 模式 5：Runtime 量測模式統一

對齊基準上的尺寸值要嘛全寫死、要嘛全量測、不要混搭。

### 反例

```css
/* form 高度寫死、gap 寫死、scope 用 measured 值 */
.scope {
  top: calc(72px + 16px + var(--scope-measured));
}
```

Form 高度其實會隨字型變動 → 70px 或 76px → scope 跑位。

### 對例 A：全寫死

```css
.form { height: 72px; }  /* 強制固定高度 */
.scope { top: calc(var(--form-h) + var(--gap)); }
```

Form 強制固定高度、所有變數都是已知。

### 對例 B：全量測

```js
function recalc() {
  const fH = form.getBoundingClientRect().height;
  const gap = parseFloat(getComputedStyle(form).marginBottom);
  document.documentElement.style.setProperty('--form-h', `${fH}px`);
  document.documentElement.style.setProperty('--gap', `${gap}px`);
}
new ResizeObserver(recalc).observe(form);
```

```css
.scope { top: calc(var(--form-h) + var(--gap)); }
```

全部 runtime 算、CSS 只讀變數。

---

## Wrong vs Right 對照

### 範例 1：搜尋框背景色客製

**錯**：

```js
input.style.setProperty('background', '#fff', 'important');
input.style.setProperty('color', '#000', 'important');
```

**對**：

```css
@layer vendor { @import 'pagefind.css'; }

.pagefind-ui__search-input { background: var(--bg); color: var(--text); }
```

JS 不需要參與、純 CSS 解。

### 範例 2：跨 viewport 的 sidebar 切換

**錯**：

```js
window.addEventListener('resize', () => {
  if (window.innerWidth >= 1400) {
    sidebar.style.display = 'block';
  } else {
    sidebar.style.display = 'none';
  }
});
```

**對**：

```css
.sidebar { display: none; }
@media (min-width: 1400px) {
  .sidebar { display: block; }
}
```

值（1400）能 build-time 定下來 → CSS media query 直接寫、不需要 JS resize listener。

---

## 自檢清單（dogfooding）

寫樣式相關 code 前：

- [ ] 我有沒有問「這個值能不能 build-time 定下來」？
- [ ] 我有沒有用 `!important` / inline `setProperty(..., 'important')`？（如果有 → 換成 class toggle）
- [ ] 我有沒有跟 vendor CSS 打 specificity 戰？（如果有 → 用 `@layer`）
- [ ] CSS variable 是不是只在一個地方定義？
- [ ] Inline `<style>` / `<script>` 是不是 < 30 行？（超過就拆檔）
- [ ] Runtime 量測跟 hardcoded 值在同一個對齊基準上、是不是只用了一邊？

---


**Last Updated**: 2026-04-26
**Version**: 0.1.0
