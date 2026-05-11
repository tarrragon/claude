# Metadata surface 要納入寫作 review 範圍

> **角色**：本卡是 `compositional-writing` 的支撐型原則（principle）、被 SKILL.md 第 6 原則「Multi-pass Review」與 `references/writing-articles.md` 的 surface enumeration 段引用。
>
> **何時讀**：正文已經完成 review，但 title、description、heading、link label、MOC / index entry 仍可能沿用第一版 wording 時，讀本卡確認 review coverage。

---

## 結論

寫作 review 的 coverage 由 **frame × surface** 決定。Frame 回答「用什麼眼睛看」，surface 回答「哪些文字都要被看」。正文通過 multi-pass review 只代表 body surface 收斂；metadata / navigation surface 仍要跑同一套意圖、語氣、grep-ability 與索引一致性檢查。

常見 surface：

| Surface            | 典型位置                                     | Review 責任                          |
| ------------------ | -------------------------------------------- | ------------------------------------ |
| Body surface       | 段落、表格、範例、判讀徵兆                   | 完整論證、段首核心、案例補足         |
| Metadata surface   | title、description、tags、sidebar label      | 讀者第一眼、搜尋摘要、排序與分類     |
| Navigation surface | MOC hook、index entry、TOC label、link label | 跨篇路由、下一步判斷、概念入口一致性 |
| Identity surface   | filename、slug、canonical identifier         | 可回溯識別、跨工具定位、單次 grep    |

判別問題：「讀者看到正文之前，會先看到哪些文字？這些文字有沒有跟正文跑同一輪 review？」

---

## 為什麼需要 surface enumeration

寫作時容易把 review scope 心算成「正文段落」。這會讓 title、description、MOC hook、link label 成為未驗證區。讀者入口一旦保留第一版 wording，正文即使已經改成更清楚的概念錨點，入口仍會先傳遞舊 frame。

Surface enumeration 把「已 review」改成可驗證動作：

1. 先列出本次產出的所有文字位置。
2. 每輪 multi-pass frame 都掃同一份 surface 清單。
3. 對照正文第一段、title、description、MOC hook 是否指向同一個核心責任。

這是 [writing-multi-pass-review](./writing-multi-pass-review.md) 的補強：multi-pass 原本定義 frame 軸，本卡補 surface 軸。

---

## Review 流程

### 第一步：列 surface

每次寫 production 內容前，先列出本次會產生或修改的文字位置：

```text
article.md
- title
- description
- body headings
- body paragraphs
- link labels

collection index / MOC
- index entry label
- one-line hook
- route description
```

這份清單是 review 的 surface inventory。

### 第二步：每輪 frame 都掃所有 surface

| Frame                   | Body surface                 | Metadata / navigation surface          |
| ----------------------- | ---------------------------- | -------------------------------------- |
| 對意圖                  | 段落是否回到核心責任         | Title / description 是否承接同一個責任 |
| 正向陳述 / 機會成本語氣 | 段落是否先建立概念，再補對照 | Title / MOC hook 是否先給正向錨點      |
| Grep-ability / 命名     | 段首關鍵字是否可搜尋         | Title、slug、link label 是否可單次命中 |
| Cross-link 健康度       | 引用是否指向正確卡片         | Index entry 是否導向同一個概念入口     |
| 反例 / 邊界             | 對照段是否保留原因與範圍     | 對照型 title 是否有正文立即承接原因    |

### 第三步：用 grep 補字面候選

語氣判斷是語意 review，但候選可以先用 grep 找出：

```bash
rg -n "不行|不可以|不是|不要|無法|不能" <changed-documents>
```

Grep 命中代表需要判讀，並不自動代表違規。合法對照要同時具備正向錨點、對照原因與適用情境。

---

## 跟其他原則的關係

| 原則                                                                                                | 關係                                           |
| --------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| [writing-multi-pass-review](./writing-multi-pass-review.md)                                         | 該卡定義 frame 軸，本卡補 surface 軸           |
| [naming-as-iterated-artifact](./naming-as-iterated-artifact.md)                                     | Title、slug、link label 都是命名，需要多輪迭代 |
| [literal-interception-vs-behavioral-refinement](./literal-interception-vs-behavioral-refinement.md) | Grep 是字面候選，是否合格仍要靠語意 review     |

---

## 判讀徵兆

| 訊號                                   | 該做的事                                 |
| -------------------------------------- | ---------------------------------------- |
| 正文改過，title 保留第一版 hook        | 把 title 加進 surface enumeration        |
| Index entry 只是沿用第一版標題         | 跑 navigation surface 的對意圖 review    |
| Description 比正文更像行銷標語         | 重寫成概念責任與讀者路由                 |
| Review 紀錄只寫「已檢查文章」          | 補 surface inventory，標出實際掃過的位置 |
| 搜尋結果命中舊句型，但正文已改成新概念 | Grep scope 沒包含 metadata / navigation  |

---

## 適用範圍

- **適用**：技術文章、知識卡片、README、spec、skill reference、MOC、collection index
- **特別適用**：有 title、description、sidebar label、SEO summary、MOC hook、link label 的內容系統
- **邊界**：Surface enumeration 是寫作 review；grep 只提出候選，最後仍由語意判讀決定
- **可省**：一次性 scratch note 可以只保留 title / body 的最小 surface；production 內容需要全 surface review
