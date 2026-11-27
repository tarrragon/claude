# frontend-with-playwright 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 0.7.0 — `refactor-without-visual-change.md`〈基準：計算後樣式快照與截圖，各量得到什麼〉表的「不在畫面上的元素」那一列改正機制並補但書：未展開的 `<details>` 的內容是 `content-visibility: hidden`，不是 `display: none`（`display: none` 的例子改成未開的 `<dialog>`）；快照抓得到這些元素的計算值，但寬高這類排版屬性沒有排版可依，差異要在展開的狀態下量。原句會讓執行者以為未展開區塊的寬高差異也比得到。

**Version**: 0.6.0 — `css-js-boundary.md`〈模式 3：CSS Variable 單一定義位置〉的例外從「刻意的局部覆寫」一種擴成三種設計好的第二個定義位置：同一個選擇器在 media query、偏好查詢或根元素主題屬性底下重新對應一組 token；局部主題的子樹；定義元素外面取不到繼承的元素。並寫出跟重複定義的分別（值不同、改的是一組 token、規則旁註明對應哪一組與原因；同值重新宣告與只為一個元件改值的 class 照重複處理），局部主題的失效另給「直接改 semantic token 的對應」這種不會觸發失效的寫法。缺口：0.5.0 只寫了局部主題一種例外，照字面讀，把手機字級與觸控命中區放在 media query 裡重新定義的寫法（`references/design-system-token-layer.md`〈分層〉推薦的手機字級寫法）也會被判成重複定義而刪掉。

**Version**: 0.5.0 — 新增 reference `refactor-without-visual-change.md`（重構 CSS 而不改外觀）與 SKILL.md 原則 7。權威位置為新 reference；SKILL.md 補原則 7、三列觸發路由、目錄索引一列與 description 的觸發詞，`css-js-boundary.md`〈何時參閱本文件〉的 `!important` 那一列補一句指向新 reference。

- **缺口**：skill 寫了量 computed style 的寫法與「`!important` 是訊號」，沒有寫整理既有 CSS 時怎麼確認畫面沒變。常見的做法是先截圖當基準、整理完比對、有差就退回；實測一次把一個練習題網站的 CSS 全部改成引用 token 時，這個做法有三處不夠：截圖分不出字級收斂批次裡哪些差異是預期的；逐元素比對計算後樣式抓得到 2px 的行高差、依屬性分組，卻看不到兩版共有的整頁溢出；「有差就退回」套在刻意改值的批次上每次都會退回。另外，只替七條規則加 id 加權，另外插入 `<a>` 形式的主要按鈕後量到 hover 時變成白底白字，「只改目標元件」的限制擋不住這種跨元件的層疊影響。
- **判斷標準**：兩階段（先做對並提交當基準，再一批一種改動、開始前寫下預期屬性）；快照與截圖各量得到什麼、比對範圍（狀態、寬度、瀏覽器、走不到的元素）寫下來；差異三種歸類與「來自量測／來自改動」兩層判讀（含 `currentColor`、`var()`、繼承與規範等價）；退回規則只對只換寫法的批次整批退回；`!important` 與加權依要贏過的規則屬於誰選替代寫法（七種情形），加權是否必要直接量，並寫出結論成立的範圍；擋寫死值的檢查要印出讀到的宣告數並跑正對照；派 agent 時 prompt 寫改動種類、禁止與例外、整頁比對的驗收，agent 自述不算驗收。
- **審查之後補上的條件**：快照依 DOM 位置配對、class 記成欄位（合併 class 的批次用 class 配對會量不到差異）；比對印出元素數、屬性數與配對不上的鍵數，比對腳本跑正對照；比對範圍加變體與輸入的版本（token 來源、宿主 CSS）；「來自量測」與「等價」要附證據；一批的大小以追得到每一組差異的來源為限；沒有設計稿的舊專案以目前版本當基準；檢查在第一批之前建好、擋帶 id 的選擇器、既有違規記成 baseline、正對照的計數寫進 commit message；派 agent 時寫明基準的 commit SHA；宿主主題升級要有重跑的觸發點；替代表依「宿主 CSS 的載入方式管不管得到」分列。
- **同一支 skill 的其他檔**：`css-js-boundary.md`〈模式 2〉的對例改成 `@import url(...) layer(vendor);`（原寫法把 `@import` 包在 `@layer` 區塊裡，依 CSS 規格 `@import` 只能寫在樣式表最前面），並註明 vendor 帶 `!important` 的宣告在 layer 裡反而更強；〈模式 3〉補上局部覆寫 token 的例外；`playwright-in-loop.md`〈何時參閱本文件〉補一列指向新 reference。
- **審查**：三輪的 finding 與處置記在 blog repo 這次的 commit message。
- **SKILL.md 的計數**：「六大原則」三處改成指向〈Principles（原則速查）〉與〈Core Pillars（支柱）〉的段名，原則數之後再增減不必回頭改。

**Version**: 0.4.0 — 內文的優化、在線、補丁依所指換成台灣用語（最佳化、強化、改善；線上、在線上、同時執行；修補、修補檔、更新檔）。

**Version**: 0.3.4 — 正文與 principle 卡的否定起手句（「不是 X、是 Y」）改成重點先行，核心概念移到句首、被否定的一半留作句尾對照；同步 blog 對應 report 卡的同一批改寫，語意不變

**Version**: 0.3.3 — 清理 5 處 language-constraints.md 規則 2 禁用詞基線債務（`代碼` → 程式碼，`references/principles/` 下三個 principle 檔案），純用語修正，指令內容與判準未改。

**Version**: 0.3.2 — 版本紀錄搬到同目錄的 `CHANGELOG.md`。skill 是 runtime 整份載入的檔案，而沒有任何規則要求任何人讀版本紀錄，留在 SKILL.md 等於每次叫用都付一次無效讀取。SKILL.md 末尾留一行指過去，版號的兩個住址改成「CHANGELOG.md 最上面那一條 + frontmatter 的 metadata.version」。skill 的指令內容一個字都沒改。

**Version**: 0.3.1 — 術語校正：判準全數改為判斷標準（動作修飾語縮為「X 標準」、狀態義改為「X 條件」）。判準的語域在哲學與教育評量、工程讀者解析不了——五份低階模型探針一致回報非通用

**Version**: 0.3.0 — 接入 #79 決策對話五維度（對應 #74-#78 系列）；協助前端設計取捨段落的呈現格式對齊 user-facing 決策協議
**Version**: 0.2.0 — 接入 #55-#68 系列：新增第 7 份 reference `data-flow-and-filter-composition`（涵蓋 Filter × Source 層錯位 + 五策略 + 跨前端 / 後端 / 演算法 / DB 領域範例）；description 補跨領域 stream 操作觸發詞；SKILL.md 加「相關抽象層原則」段（#42-45 + #64 + #67-68）；強調「不只前端、stream 操作通用」
**Version**: 0.1.0 — 從 50+ 篇事後檢討萃取「前端網頁開發 + Playwright 驗證」這條主軸；六份 references 對應「DOM topology / CSS-JS 邊界 / Playwright 三位置 / framework 共處 / Reactive 效能 / A11y」六個情境
