# Voss 影響力透明化原則

> **來源**：Chris Voss, *Never Split the Difference* (2016)；Voss 後續訪談與課程
> **用途**：P 階段「自我暴露偏好實踐」的理論依據。修改自我暴露範本或反 dark pattern 規則時參考。

---

## 核心命題

Voss 自陳：

> **"One person's influence is another person's manipulation."**
>
> 影響（influence）與操縱（manipulation）的差異不在於行為本身，而在於**意圖是否被透明化**。

---

## 為何透明化是區分線

Voss 從 FBI 人質談判經驗中歸納：

| 行為 | 意圖隱藏 | 意圖透明化 |
|------|---------|-----------|
| 提出選項 | 操縱（讓對方以為自己選） | 影響（明示我傾向 X，但你決定） |
| 標記推薦 | 操縱（位置偏誤 + 預設選項） | 影響（明示「這是我的猜測，理由 Y」） |
| 提供分析 | 操縱（暗示結論） | 影響（暴露推理鏈讓對方可追溯） |

關鍵：**對方有能力分辨並抗衡你的影響時，才是影響；對方不知道你在影響時，是操縱**。

---

## WRAP 中的應用

P 階段「自我暴露偏好實踐」要求建議者：

| 維度 | 透明化動作 |
|------|----------|
| 偏好 | 「我傾向 X，理由 Y」（不假裝中立） |
| 推理鏈 | 列出步驟讓對方可追溯（不只給結論） |
| 盲點 | 「我可能漏掉的角度有 Z」（不假裝全知） |
| 偏誤標記 | 不標 (Recommended)（避免 dark pattern） |

---

## 為何 (Recommended) 標記是 Dark Pattern

DarkBench（2024 學術 benchmark）將 LLM 標記推薦選項列為 dark pattern，原因：

1. **Confirmshaming 變體**：把「未推薦」隱性框定為次優
2. **位置偏誤疊加**：推薦選項通常放第一個，效果加倍
3. **隱藏意圖**：(Recommended) 不暴露「為何推薦」「推薦者偏好如何形成」

修正方式：改為「我目前的猜測」或不標。重點在於暴露推薦者的不確定性，而非預設答案。

---

## 維護注意事項

- 修改自我暴露範本時，確認四個維度（偏好/推理/盲點/偏誤）都有透明化動作
- 評估新功能（如建議系統、選項排序）時，問「對方能分辨我的影響並抗衡嗎？」若不能，是 dark pattern

---

**Sources**:
- Chris Voss & Tahl Raz, *Never Split the Difference: Negotiating As If Your Life Depended On It* (HarperBusiness, 2016).
- DarkBench: Benchmarking Dark Patterns in Large Language Models, 2024.
