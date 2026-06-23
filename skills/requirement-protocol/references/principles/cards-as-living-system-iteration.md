# 卡片系統的迭代浮現：原子卡 → meta-卡 → reference 三層展開

> **角色**：本卡是 `requirement-protocol` 的支撐型原則（principle）、被 SKILL.md「相關抽象層原則」段（#81）與 reference `decision-dialogue.md` 引用、是 skill 結構（reference + dogfood + self-check）作為 multi-pass 設計的 process-level 元原則。
>
> **何時讀**：設計 / 維護 skill 或知識卡片系統時、判斷該寫原子卡還是 meta-卡、何時抽 reference；或察覺自己想「一次想清楚再寫」、想釐清 spiral 浮現的合理形狀。

---

## 結論

知識卡片系統的成型不是「想清楚再寫」、是**多輪迭代浮現**：

```text
原始對話素材
   ↓ 識別重複結構
原子卡（每張一個小現象）
   ↓ 串連、識別共同骨架
meta-卡（抽上層原則）
   ↓ 沉澱成可重複使用的 protocol
reference（可直接套用的 checklist + 模板）
   ↓ L3 觸發機制
SKILL（自動觸發 reference）
```

每層都解上一層的限制、不是替代。**原子卡保留具體 case 的細節**（被反例反駁時可保留）、**meta-卡提供跨情境的判讀框架**（避免每次重新推理）、**reference 沉澱成可直接套用的步驟**（消除「知道但忘記用」的鴻溝）。

---

## 為什麼一次寫不完

第一次接觸現象時、看到的是**具體 case 的表面**：

- 看到「使用者說『我再想想』」 → 先寫成原子卡「延後是合法選項」
- 看到「使用者說『1+2』」 → 先寫成原子卡「反省題複選」
- 看到「使用者反駁推薦」 → 先寫成原子卡「決策呈現格式」

每張原子卡解 1 個情境、自包含可讀。但**串連在一起時才浮現的結構**（例：「五個獨立維度」）需要看到 ≥ 3-5 張原子卡之後才看得出。**第一次寫不出來、不是因為沒想清楚、是因為原料不夠**。

催熟原子卡之前先寫 meta-卡 = 從少數 case 過度推論、產生 over-fit 結構、後續發現新 case 不符就要重寫。

---

## 三層的職責分工

### Layer 1：原子卡

**範圍**：單一現象 / 單一錯誤 / 單一情境。

**特徵**：

- 從具體事件浮現（事後檢討）
- 自包含、不依賴其他卡也能讀
- 含「反模式 / 修法 / 何時不適用」三段
- 給未來自己看：「啊我再次遇到這個」

**例**：[decide-later-as-valid-option](./decide-later-as-valid-option.md) 是從一次具體對話中「使用者說『不用現在決策』、agent 加壓」浮現。

### Layer 2：Meta-卡

**範圍**：N 張原子卡的共同骨架。

**特徵**：

- 不是新原則、是把已存在的原則上抽
- 通常出現在「寫 N 張原子卡之後、發現他們其實同一件事」
- 提供跨情境判讀（"這個情境屬於哪一維度?"）
- 給「已有 mental model 的讀者」加深、不取代原子卡

**例**：[decision-dialogue-dimensions](./decision-dialogue-dimensions.md) 是寫完幾張決策呈現原子卡後、發現他們各對應一個獨立維度。沒寫上層 meta 之前是平行卡、寫完後形成有結構的網。

### Layer 3：Reference

**範圍**：把 N 張卡的判讀流程沉澱成可直接套用的 step-by-step。

**特徵**：

- 不是教學、是 lookup table + checklist
- 在實作中被翻開、不是讀爽的
- 結尾有 self-check 讓使用者驗證自己沒漏
- 跟一張具體任務 / 觸發情境對應

**例**：skill 的 `references/decision-dialogue.md` — 把多張決策卡翻譯成「五步判讀 + 完整模板 + self-check」、agent 寫 decision 之前看一遍就夠了。

---

## 多層迭代的訊號：什麼時候該往上抽？

### 訊號 1：寫第 N 張卡時、發現大段內容跟前一張重複

→ 兩張卡共用某個結構、抽出 meta-卡。例：寫反省題複選卡時、引用推薦格式 = 暗示有上層共骨。

### 訊號 2：跨卡 cross-link 變密、單張卡的「跟其他卡的關係」段持續長

→ 知識網密度足夠、可抽 meta-卡作為樞紐。

### 訊號 3：實作中要回查多張卡才能完整 apply

→ 沉澱成 reference、減少回查成本。

### 訊號 4：「我之前是不是寫過類似的」第 3 次出現

→ 不是「沒寫過」、是 meta-結構模糊、無法用既有卡 frame 新情境。需要 meta-卡。

---

## 反模式：跳層的代價

| 反模式                               | 為什麼不好                                                           |
| ------------------------------------ | -------------------------------------------------------------------- |
| 直接從對話寫 meta-卡（沒原子卡支撐） | over-fit 少數 case、新 case 不符就要重寫                             |
| 只寫 reference 不寫卡片              | reference 是「怎麼做」、原子卡是「為什麼」、缺少 why 後續難 maintain |
| 卡片寫完不抽 meta                    | 知識散落、跨情境無法判讀、實作中要回查多張                           |
| Meta-卡寫太早（寫第 1-2 張就抽）     | 沒足夠 N 看出共骨、結構強加                                          |
| 一張卡裡塞多個現象                   | 卡片該原子、混合會干擾 cross-link                                    |
| Reference 沒對應觸發情境             | 寫了沒人看、變另一份未來才會被翻的文件                               |
| 卡片寫完不回頭 cross-link            | 知識網不形成、留下孤兒卡                                             |

---

## 觀察：多層迭代不是線性、是 spiral

實際上的迭代不是「Layer 1 全寫完才寫 Layer 2」、而是：

```text
寫卡 A → 寫卡 B → (浮現 meta) → 草稿 meta-卡 →
寫卡 C → (補 meta-卡) → 寫卡 D → (補 meta-卡) →
寫卡 E → 完成 meta-卡 → 寫 reference → SKILL 整合
```

每次新卡可能反過來修改 meta-卡、reference 也可能反過來指出原子卡缺角。**Spiral 結構接受迭代修正、線性結構假裝一次寫對**。

---

## 跟其他抽象層原則的關係

| 原則                                                                                                | 關係                                                                                                                        |
| --------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| [two-occurrence-threshold](./two-occurrence-threshold.md)                                           | 寫 meta-卡的訊號：第 2 次看到類似結構、抽出來                                                                               |
| [minimum-necessary-scope-is-sanity-defense](./minimum-necessary-scope-is-sanity-defense.md)         | 先寫原子卡、有證據再抽 meta、跟「先窄後寬」同構                                                                             |
| [single-source-of-truth](./single-source-of-truth.md)                                               | meta-卡是上層 SSOT、原子卡保留 case-specific 細節、各層分工                                                                 |
| [ease-of-writing-vs-intent-alignment](./ease-of-writing-vs-intent-alignment.md)                     | 「直接寫 meta」容易但會 over-fit、迭代浮現難寫但對齊真實結構                                                                |
| [external-trigger-for-high-roi-work](./external-trigger-for-high-roi-work.md)                       | 「回頭抽 meta + 寫 reference」是高 ROI 但無觸發、需要協議 / pair / 對話結構驅動                                             |
| [decision-dialogue-dimensions](./decision-dialogue-dimensions.md)                                   | 本卡的 spiral 過程剛好就是該卡浮現的實例 — meta-卡 + reference 都是後寫                                                     |
| [literal-interception-vs-behavioral-refinement](./literal-interception-vs-behavioral-refinement.md) | spiral 是 multi-pass refinement 的具體實現 — 卡片內容對不對、抽 meta 抽得對不對都是行為錯誤、靠 spiral 收斂、不靠 hook 攔截 |

---

## 判讀徵兆

| 訊號                                  | 該做的事                               |
| ------------------------------------- | -------------------------------------- |
| 寫第 N 張卡、結構大段重複前卡         | 抽 meta-卡                             |
| 卡片網的 cross-link 變密              | 加 meta-卡作為樞紐                     |
| 實作中要翻 ≥ 3 張卡                   | 沉澱 reference                         |
| 「之前好像寫過類似的」第 3 次         | 缺 meta-frame、補上                    |
| Reference 寫完沒人翻                  | 沒接到觸發情境、補 SKILL trigger route |
| Meta-卡寫太早、後續新 case 一直破壞   | 退回原子卡層、累積到 ≥ 3-5 張再抽      |
| 原子卡卡得很細、單張看完不知道幹嘛    | 缺 meta-上下文、補 meta-卡或 reference |
| Cross-link 偏單向（只引用、沒被引用） | 孤兒卡、反向 link 補回                 |

**核心**：知識卡片系統不是寫一次的文件、是長期 spiral 迭代的 living system。**接受「第一次寫不對、會迭代」這個前提**、就會在每次接觸新現象時先寫原子、累積到一定 N 後抽 meta、最後沉澱 reference。**反過來的「想清楚再寫」是模仿線性開發、跟知識浮現的真實結構不對齊**。
