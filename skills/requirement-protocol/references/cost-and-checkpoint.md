# Cost Transparency & Revert Checkpoint

兩個情境的協議合併：**對抗多層的覆寫成本告知** + **「先還原 / 先重來」類退出指令處理**。共同主軸 = 把成本攤開、讓使用者參與決策、保留可逆性。

適用：

- 客製需求要對抗多層（vendor CSS、framework reconciliation、browser default、UA stylesheet）
- 收到「先還原」「先重來」「換個方向」「我們重新開始」這類指令

不適用：純 greenfield 開發（沒有舊代碼要對抗、沒有探索成果要保留）。

> **自包含聲明**：閱讀本文件不需要先讀其他 reference。本文件涵蓋成本告知模板、checkpoint 命名慣例、reset 前的確認協議。

---

## 何時參閱本文件

| 訊號                                                  | 該做的第一件事                                     |
| ----------------------------------------------------- | -------------------------------------------------- |
| 客製需求看似簡單但要打到 vendor / framework / UA 多層 | 在寫第一條規則前先報成本                           |
| 即將連寫 ≥ 3 條 `!important` / 複雜 selector          | 停 — 寫成本報告、問使用者意願                      |
| 使用者說「先還原」「先重來」「思路不對、換」          | 確認還原目標 + 是否要 commit 當前進度              |
| 探索了一個方向、最後沒採用                            | commit 一個 checkpoint 標「explored, not adopted」 |
| 即將執行 `git reset --hard` / `git checkout .`        | 先確認哪些工作要保留、哪些要丟                     |

---

## 為什麼成本要攤開、為什麼 revert 要 checkpoint

### 成本攤開的價值

當客製要對抗多層、執行者沉默地堆疊 `!important` + specificity hack + polyfill — 結果使用者：

1. 看到「能用」的成果、以為成本低
2. 升級 vendor / 換 browser 後壞掉、驚訝於維護負擔
3. 不知道有沒有更便宜的替代方案（換 vendor、放棄該客製、改設計）

把成本攤開 = 使用者**在執行前**就決定值不值、不在事後後悔。

### Revert 含 checkpoint 的價值

探索的成果即使沒採用、仍然是「為什麼不採用」的證據。直接清空：

1. 下次遇到類似需求、可能再走一遍同樣的死路
2. 失去 A 跟 B 兩條路的對比基礎
3. 部分技術選擇（命名、結構）可能仍有用、被連帶丟掉

Checkpoint 把「探索」與「採用」分開記錄、保留比較與恢復的可能。

---

## 成本告知協議

### 步驟 1：列出對抗的層

寫第一條規則前、列出將打到哪幾層：

| 層                | 對抗代價                                   |
| ----------------- | ------------------------------------------ |
| Browser UA 樣式   | 低 — UA 變動慢、跨瀏覽器差異是固定問題     |
| Vendor library    | 中 — 升級時可能變、需追蹤 vendor changelog |
| Framework runtime | 高 — reconciliation 會清掉、需在邊界外操作 |
| 自家舊 CSS        | 低 — 完全可控                              |

### 步驟 2：估規則數量與風險

```text
這個客製需要打到：
- Vendor CSS（pagefind 主題色）：寫 3-4 條規則覆蓋預設色
- Framework reconciliation（drawer 內容會被重渲染）：把客製 UI 放邊界外
- 升級風險：pagefind 升級 minor 版本、選擇器改名 → 客製樣式失效

建議方案：
A. 完整客製（如上）— 工時 1 hr、升級時要重檢
B. 只改 CSS variable（如果 vendor 提供）— 工時 5 min、升級安全
C. 放棄客製、用 vendor 預設 — 工時 0、視覺差異使用者要接受

推薦 B（如果 vendor 有提供 var）、否則 A。哪一個？
```

### 步驟 3：使用者選擇後再開始

不管選 A / B / C、選擇本身已經被攤開。使用者後續看到維護負擔、不會驚訝。

---

## Revert / Checkpoint 協議

### 步驟 1：確認還原目標

使用者說「先還原」時、回問：

```text
「還原」是指：

(a) 丟掉所有未 commit 的修改、回到 HEAD
(b) 回到某個特定 commit（哪一個？）
(c) 部分還原（哪些檔案 / 哪些功能）
(d) 換思路、但保留結構（命名、檔案組織保留、實作換掉）

我建議先做 commit 把當前進度保存、再 reset — 您是哪一種？
```

### 步驟 2：commit 當前進度當 checkpoint

不管是哪種還原、先 commit：

```bash
git add -A
git commit -m "checkpoint: explored [方向 X], not adopted

- 嘗試了 [做法 A]、結果 [現象]
- 假設 [Z] 驗證後不成立
- 保留供未來對比、不採用為最終解
"
```

Checkpoint commit 的特徵：

- 主題明確含「checkpoint」「explored」「not adopted」字樣
- body 寫「為什麼不採用」、不只寫「做了什麼」
- 在後續 main branch 上不會被 merge 進去（用 branch 隔離或日後 rebase 丟）

### 步驟 3：執行 reset

確認 checkpoint commit 完成後、執行使用者要的還原：

```bash
# 視類型而定
git reset --hard <target>      # 完全還原
git checkout <commit> -- <file> # 部分還原
git revert <commit>             # 保留歷史的還原
```

危險動作（`git reset --hard`、`git checkout .`、`git clean -fd`）執行前再次跟使用者確認 — 即使有 checkpoint commit、也要避免把 checkpoint 自己 reset 掉。

---

## Wrong vs Right 對照

### 範例 1：覆寫成本

> 使用者：「pagefind 搜尋框的顏色改成我們的品牌色」

**錯**（直接做、沒攤成本）：

```css
.pagefind-ui__form { background: var(--brand) !important; }
.pagefind-ui__search-input { background: var(--brand) !important; color: white !important; }
.pagefind-ui__button { background: var(--brand-dark) !important; }
/* ... 8 條 !important 後、終於看起來對 */
```

兩週後 pagefind 升級、class 名稱改了一個 — 全壞。使用者驚訝。

**對**（先報成本）：

```text
顏色客製有兩條路：

A. Pagefind 提供的 CSS variables（看了 docs：--pagefind-ui-primary、--pagefind-ui-text 等）
   → 改 4 個 var、升級安全、5 min

B. 直接覆寫 class 規則（要 8 條 !important）
   → 升級可能壞、需要追蹤 vendor changelog、1 hr

推薦 A、除非您要的視覺超出 var 能控制的範圍。哪個？
```

### 範例 2：「先還原」處理

> 使用者：「等等先還原、這個方向不對」

**錯**：

```bash
git checkout .  # 直接清空、丟掉 30 分鐘探索成果
# 之後想對比「為什麼方向 A 不行」時、什麼都沒留下
```

**對**：

```text
我把當前進度先 commit 成 checkpoint、再還原 — 還原的目標是：

(a) 回到開始這個方向之前的 commit（HEAD~3）
(b) 回到 main 最新
(c) 換個 branch、保留這個 branch 供以後參考

通常 (c) 最安全、(a) 最常見。您要哪個？
```

確認後：

```bash
git add -A
git commit -m "checkpoint: explored grid-row layout, not adopted (drawer is form's child, grid invalid)"
git reset --hard HEAD~4  # 或使用者指定的 target
```

---

## Checkpoint commit 的命名慣例

| 前綴          | 用途                           | 範例                                           |
| ------------- | ------------------------------ | ---------------------------------------------- |
| `checkpoint:` | 探索成果、未採用、保留參考     | `checkpoint: explored A approach, not adopted` |
| `wip:`        | 進行中、之後會 rebase / squash | `wip: trying scope toggle with regex`          |
| `spike:`      | 純探索、無意採用、純驗證可行性 | `spike: pagefind perf with 5000 docs`          |

`checkpoint:` 是本文件主推 — 比 `wip:` 多了「不採用」的明確標記、未來 grep `git log --grep=checkpoint` 能快速找到「曾經試過但放棄的方向」。

---

## 自檢清單（dogfooding）

收到客製需求或 revert 指令時：

- [ ] 寫第一條覆寫規則前、有沒有列出「對抗哪幾層、規則數量、升級風險」？
- [ ] 有沒有給使用者 ≥ 2 個選項（含「不做」或「降級客製」）？
- [ ] revert 前有沒有確認還原目標的精確意圖？
- [ ] revert 前有沒有 commit 一個 checkpoint？
- [ ] checkpoint 的 commit message 有沒有寫「為什麼不採用」、不只寫「做了什麼」？

成本沒攤、checkpoint 沒 commit → 退回去補。

---

**Last Updated**: 2026-04-26
**Version**: 0.1.0
