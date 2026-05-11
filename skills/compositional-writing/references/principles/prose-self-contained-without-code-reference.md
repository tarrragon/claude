# 概念類論述要 self-contained：不依賴 code 才能被理解

> **角色**：本卡是 `compositional-writing` 的支撐型原則（principle）、被 `references/writing-articles.md` 規則二（商業邏輯先於 CASE）+ multi-pass review 輪 5（反例 / 邊界）的 reader simulation 子場景引用。
>
> **何時讀**：寫概念說明 / 架構決策 / 設計檢討類文章時、用本卡判斷論述段是否依賴 code 看過——尤其在 multi-pass review 跑「拿掉 code block 還讀得通嗎」的 reader simulation 自測。

---

## 論述基礎與限制

本卡的論述基於 **1 個 case** 的 review 觀察抽出。具體限制：

- **Scope 限縮在概念說明 / 架構決策 / 設計檢討類文章**：教學類、tutorial 類、code walkthrough 類文章的讀者本來就會逐行對映 code、本卡不適用——這幾類文章的論述跟 code 緊密交織是合理 narrative
- **「翻譯成業務角色」也有讀者熟悉度的邊界**：用業務角色名詞替代代詞、對熟悉領域的讀者通順、對不熟的讀者仍是空名詞。修法是「換 reference 類型」、不是「徹底解決 self-contained」
- **跟規則二（商業邏輯先於 CASE）的關係要精準**：規則二講「層次順序」、本卡講「論述自包含」。兩者有重疊但不完全相同——本卡是規則二在「字句層 reference 處理」的子場景、不是規則二的全面延伸

讀者使用本卡時、先判斷文章類型——概念說明 / 架構決策 / 設計檢討 → 套用；教學 / tutorial → 評估「跟 code 交織」是否合理 narrative。

---

## 核心原則

概念說明 / 架構決策 / 設計檢討類文章的論述段（不放 code 的段落）要 **self-contained**——用名詞 / 角色 / 條件描述業務邏輯、不依賴讀者去翻附近的 code block。讀者跳過所有 code block 仍能理解論述、是「商業邏輯先於 CASE」的延伸實踐。

| 維度     | 依賴 code 的論述                           | Self-contained 論述                                |
| -------- | ------------------------------------------ | -------------------------------------------------- |
| 引用方式 | 「事件 payload 第二段帶了那個欄位」        | 「事件 payload 包含『當前列表』+『最後變動』兩段」 |
| 主詞     | 「那個 controller」「剛才的 service」      | 「鏡像 controller」「狀態變更 service」            |
| 讀者前提 | 已經看過 code、記得結構                    | 不需要看 code、只看論述                            |
| 失敗模式 | 讀者翻不到 reference 對應位置 → 卡住或誤讀 | 讀者直接 parse 論述、不被 code 結構綁住            |
| 修補擴散 | code 改了、論述自動 outdated               | code 改了、論述仍然有效                            |

self-contained 論述的價值在於**論述本身就是完整的、code 是 case 補充而非依賴**。讀者用論述就能 reproduce 思考過程、code 提供具體驗證。

---

## 為什麼依賴 code 的論述會出現

### 來源 1：寫的人有 code 在腦中、預設讀者也有

寫作者通常已經看過或寫過 code、所以在論述段用「那個 payload 第二段」這類 reference 對自己沒負擔。但讀者可能：

- 跳過 code 直接讀論述（多數讀者習慣）
- 看了 code 但沒記住具體結構
- 不熟該語言 / 該專案、看 code 也 parse 不出結構

依賴 code 的論述把這些讀者擋在門外、強迫他們翻 code 對映、認知負擔顯著上升。

### 來源 2：把對話風格搬進文章

「現在只要有人訂閱、把它記錄下來、UI 就能用」——這是對話風格、預設聽者跟說話者共享 context。寫成文章時要把 context 補進去。

### 來源 3：論述跟 code 段過於緊密交織

文章在寫「先給 code、然後論述、然後再給 code」的交織結構時、論述容易自然 reference 上面 code 的具體行。讀者跳過 code 就斷掉。

### 來源 4：誤把「業務邏輯」當成「code 行為」

「業務邏輯」是「為什麼這件事存在 / 服務什麼需求」、「code 行為」是「具體怎麼跑」。依賴 code 的論述把兩者混在一起、讀者難以分離兩個層次。

---

## Keyword bank（依賴 code 的訊號）

```text
代詞主詞：
  那個 / 這個 / 剛才的 / 上面的 / 上述 / 前面提到的

Code 結構描述：
  第 X 段 / 第 Y 行 / 那個欄位 / 上面 method / return 的那個 / 對應到 line N

時序連接（綁 code 順序）：
  先 X 再 Y / 接著 / 然後 / 最後 / 緊接著（若對應 code 執行順序）

省略條件結尾：
  就好 / 就能 / 就行 / 就解決了 / 直接 X 即可 / 一行就搞定
```

review 時跑這些 grep、把 hit 列出來、確認是否真的依賴 code。

---

## 識別訊號

### 訊號 1：論述用「那個 / 這個 / 剛才的 / 上面的」當主詞

「那個 service」「這個 payload」「剛才的 controller」——這類代詞依賴讀者剛才看過 code。

修法：把代詞換成具體名詞 + 角色描述。

### 訊號 2：用 code 結構描述（「第 X 段」「那個欄位」）

「payload 第二段」「那個 nullable 欄位」「上面 method 的 return value」——依賴讀者看過 code 的具體結構。

修法：把 code 結構描述翻譯成業務角色描述。

### 訊號 3：時序連接詞依賴 code 順序

「先...然後...接著...」如果這個時序對應上面 code 的執行順序、論述跟 code 綁太緊。

修法：把時序敘述為「在 X 條件下、Y 動作觸發 Z 結果」、不依賴 code 的具體順序。

### 訊號 4：論述只有「就好」「就能」「就行」

「現在只要有人訂閱、UI 就能用」「修改一行就好」——這類「就」字句通常省略了重要的背景條件、依賴讀者用 code 補足。

修法：把省略的條件補回去。

### 訊號 5：跳過 code block 後段落讀不通

最直接的測試方法：把所有 code block 拿掉、再讀一次論述、看是否仍能理解。

讀不通 → 論述依賴 code、要修補。

---

## 修法：把 reference 翻成 self-contained 描述

### 修法 1：用名詞替代代詞

修補前：「那個 service 對外發送事件、payload 第二段帶了這次變動是哪筆。」

修補後：「狀態變更 service 對外發送的事件 payload 包含兩段：當前完整列表、最後變動的具體品項。第二段是『最後變動品項』。」

### 修法 2：用角色替代「位置」

修補前：「上面 code 第三行那個 listener 拿到的是 nullable。」

修補後：「鏡像訂閱者收到的 payload 第二段（最後變動品項）可能為 null（移除或清空操作的情境）。」

### 修法 3：用條件替代時序

修補前：「先建立 controller、然後 listen、接著 add 事件、再 cancel。」

修補後：「在 controller 建立後、訂閱者可呼叫 `.listen()` 註冊；註冊完成後、controller 才能 `.add()` 事件給訂閱者；訂閱者呼叫 `.cancel()` 解除註冊後、後續 `.listen()` 對 single-subscription 仍然違反契約。」

### 修法 4：把「就好」展開成具體條件

修補前：「現在只要有人訂閱、把它記錄下來、UI 就能用。」

修補後：「需求只要新增一個訂閱者讀這段資訊、再把它對應到 UI 上的視覺標記即可——介面不需要變動、payload 結構不需要調整、實作範圍只限於新增訂閱端。」

---

## Reader simulation 自測

加一輪 reader simulation 自測——強迫換視角、catch reviewer 的「fill in 上下文」盲點：

- **拿掉所有 code block 後重讀**：論述是否 self-contained？
- **跳到段落中間直接讀**：不依賴前文、能不能 parse？
- **隨機抽段給陌生讀者讀**：cold-read 能不能拿到關鍵資訊？

讀不通 → 整段重寫成 self-contained。

---

## 何時論述可以依賴 code

| 情境                            | 為什麼可以依賴 code                                                   |
| ------------------------------- | --------------------------------------------------------------------- |
| Code walkthrough / line-by-line | 文章本身就是 code 解說、讀者預設會逐行對映                            |
| 簡短 inline 引用 specific 行為  | 「`stream.listen()` 第一個參數是 callback」這類引用本身就是 code 字面 |
| Tutorial 教學步驟               | 「跑這個指令、你會看到 X 輸出、接著做 Y」是 hands-on 教學風格         |
| Code review 評論                | 評論本身就是針對某行 code、上下文是 inline 共享的                     |

判讀：寫之前自問「我的文章是『教讀者怎麼讀這份 code』還是『教讀者一個概念 / 框架』？」——前者可依賴 code、後者要 self-contained。

---

## 跟其他原則的關係

| 原則                                                                                                | 跟本卡的關係                                                               |
| --------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| Compositional-writing 規則二：商業邏輯先於 CASE                                                     | 本卡是規則二的「字句層」延伸——商業邏輯論述要先存在、且不依賴 CASE 才能讀懂 |
| [ease-of-writing-vs-intent-alignment](ease-of-writing-vs-intent-alignment.md)                       | 用「那個 payload」是寫作便利、self-contained 論述需要刻意翻譯——同骨展現    |
| [colloquial-rhetoric-erodes-technical-precision](colloquial-rhetoric-erodes-technical-precision.md) | 「就好」「就能」這類字句既是口語也是依賴 code、兩卡在這層重疊              |

---

## 判讀徵兆

| 訊號                                       | 該做的行動                            |
| ------------------------------------------ | ------------------------------------- |
| 論述用「那個 / 這個 / 剛才」當主詞         | 換成具體名詞 + 角色描述               |
| 論述提到「第 X 段 / 第 Y 行 / 那個欄位」   | 翻譯成業務角色描述                    |
| 段落用「就好 / 就能 / 就行」結尾           | 把省略的條件補回去                    |
| 把 code block 拿掉後論述讀不通             | 整段重寫成 self-contained             |
| 寫的時候有 code 在記憶中、覺得「不用解釋」 | 預設讀者跳過 code、強迫自己用文字描述 |

**核心原則**：技術文章的論述要 self-contained——讀者跳過所有 code block 仍能理解論述。寫完後跑一次「拿掉 code block 還讀得通嗎」自測、讀不通 → 翻譯成 self-contained 描述。
