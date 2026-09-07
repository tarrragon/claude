# 跨輪 Review 停止訊號是 Frame 涵蓋、不是 Finding 數遞減

> **角色**：本卡是 `multi-round-review` 的支撐型原則、被「Round N 規劃判讀」段引用。
>
> **何時讀**：判斷「該不該再跑 Round N+1」時。

## 結論

判斷「該不該再來一輪 review」的訊號是「frame 軸是否還有未動」、不是「上一輪 finding 變少」。

## 為什麼 finding 數不是停止訊號

三個原因讓「finding 遞減」誤導：

1. **每輪修法會 surface 下一輪問題**：修 cadence 1.0 把 cadence 從位置 X 漂到位置 Y、變成 cadence 2.0；修 enumeration 不窮盡會 surface 反向引用斷裂。修 = 暴露 new surface。
2. **frame 切換等於進入新的問題空間**：不同 frame catch 不同 finding、跨輪不重疊、自然不會遞減
3. **finding 深度遞增、不是寬度遞減**：Round N 需要 frame 更精緻才能 catch、但 catch 到的問題更接近本質

## 質性 Transition 模式

跨輪 review 的 finding 內容會走以下 transition：

| 階段       | 主要 frame              | finding 性質                             |
| ---------- | ----------------------- | ---------------------------------------- |
| Surface    | Compliance / fact-check | 編號、連結、案例對應、規範違反           |
| Cadence    | 字句層 / 模板偵測       | 句型骨架同骨、廢話前綴、地區漂移         |
| Structural | Steelman / 讀者旅程     | enumeration 不窮盡、稻草人、反向引用斷裂 |
| Meta       | Self-application        | 規則自審、同義變體、frame 切換規劃       |

每個階段內、frame 用完就遞減；跨階段、新 frame 上線就重新進入「不遞減」狀態。

## 停止訊號的判讀

1. **七軸 frame 全動完**：frame / instance / surface / scope / cadence / timing / granularity 七軸都用過
2. **Finding 性質回到 surface**：新 frame catch 到的 finding 又退回 surface 層
3. **修法成本反轉**：修一個 finding 的成本超過讀者實際感受價值
4. **新 frame 想不出來**（最弱的一條，不作必要條件）：腦力激盪後想不出能 catch 新東西的新 frame

任二齊備、停的判讀是 evidence-based 而非 finding 數驅動。分母是前三條。

**第四條量的是判斷者，不是稿件。** 想得出多少 frame 由執行者的經驗決定，跑過越多輪的人庫存越大，所以它隨經驗反向移動、在最需要一條停止訊號的位置上永遠不成立——四次實跑零次成立，第四次停在四輪時仍想得出術語探針。把它與前三條並列會造成兩個代價：quorum 的分母悄悄從四縮到三（沒有人做過這個決定），以及執行者以為自己還沒做完。判別新增訊號時問一句——**這一條量的是被判斷的對象，還是判斷者自己**；答案是一個以能力為條件的否定式（想不出、找不到、看不出）就多半量的是判斷者。
