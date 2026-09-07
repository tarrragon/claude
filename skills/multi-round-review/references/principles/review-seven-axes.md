# 寫作 Review 是多軸完整性、不是單軸深度

> **角色**：本卡是 `multi-round-review` 的支撐型原則、被「Round N 停止訊號」段引用。
>
> **何時讀**：判斷 review 完整性時、用七軸 checklist 對齊覆蓋。

## 結論

Review 完整性是七軸交集、缺軸不缺深度。單軸越做越深會 systematic miss 對應軸盲點。設計 review 流程時 enumerate 七軸覆蓋狀況、不是加輪數。

## 七軸

| 軸          | 切換方式                                              | 靠什麼補上   | 主要 catch 目標                                                           |
| ----------- | ----------------------------------------------------- | ------------ | ------------------------------------------------------------------------- |
| Frame       | Compliance / cadence / steelman / self-application 等 | 下一輪       | 不同 frame 抓不同類問題                                                   |
| Instance    | 不同 reviewer agent / 不同 LLM / 不同人               | 另一個執行者 | 同 frame 但不同 instance 偶有差異                                         |
| Surface     | 章節 body / title / frontmatter / index / report card | 下一輪       | 不同 surface 有獨立違反模式                                               |
| Scope       | 單章 / 跨章 / 跨模組 / 跨 batch                       | 下一輪       | 不同 scope 抓不同層級問題                                                 |
| Cadence     | 字句 / 句型 / 段落結構                                | 下一輪       | Cadence 層問題（per [cadence-homogenization](cadence-homogenization.md)） |
| Timing      | 寫作前 / 寫作中 / 寫完當下 / 寫完一週後               | 時間         | 不同 timing reviewer 看到不同問題                                         |
| Granularity | 字句 / 段落 / 章節 / 模組                             | 下一輪       | 粒度差會 catch 不同類問題                                                 |

## 套用方式

規劃 multi-round review 時、按七軸列出 Round 1 到 Round N 各動了哪幾軸，然後走兩步：**找出未動的軸，再問它靠什麼補得到。**「靠什麼補上」那一欄填「下一輪」的，未動就是 Round N+1 的價值來源；填時間或另一個執行者的，處置是建票綁觸發條件而不是加輪——第五輪在七軸上補不了那兩格，產出只能來自把 frame 軸再細分，正是下方反模式的第一列。推導見 [缺口的處置看它需要哪一種資源](gap-remedy-depends-on-the-resource-it-needs.md)。

停止判定因此要寫成兩句話，分開記哪幾軸判定為已覆蓋、哪幾軸判定為取不到，否則「停在資源用完」與「停在證據齊備」在文字上同形。

## 盤點怎麼填才算數

七格有答案不等於盤點成立。一次四輪、二十餘個 reviewer 的實跑暴露三個執行細節：

**憑印象填與逐 reviewer 對帳填會得到不同答案，而兩份表外觀相同。** 那次盤點的第一版有兩處錯——一個軸被判為未動而它審過兩次，另一個軸被一刀切判為「名義動、實質未動」。改成逐 reviewer 對帳（每個 reviewer 的 prompt 對到它實際切了哪幾軸）之後才對。填表的動作要有來源，而來源是 reviewer 清單。

**「不適用」與「未動」分開記。** 某軸的切換方式在本次的審查對象上不存在時，它與「有這種表面而沒有審」是兩件事——審查一支 skill 時，surface 軸列的 report card 這一種表面並不存在。quorum 數的是軸，兩者混在一起會算錯，所以不適用不計入未動、也不計入已動。

**切換強度要對齊該軸的 catch 目標。** Instance 軸列的三種切換（不同 reviewer agent / 不同 LLM / 不同人）強度差很多。判準是問這次切換換掉的是不是該軸要 catch 的那個來源：instance 軸要 catch 的是異源視角，而同一個 session 派出的 reviewer 共用一份 prompt 與一個框架，換掉執行體取得的是採樣噪音——這一種記為未動、不進 quorum 的分子。下方反模式的第二列說的正是這件事，而它只寫了別這樣做、沒有回答做了算不算。

## 一份填好的盤點（四輪、審查對象是一支 skill）

| 軸          | 動過的輪次        | 判定       | 靠什麼補上   | 處置             |
| ----------- | ----------------- | ---------- | ------------ | ---------------- |
| Frame       | R1 / R2 / R3 / R4 | 已動       | 下一輪       | —                |
| Surface     | R1（body / frontmatter）、R3（標題） | 已動 | 下一輪  | —                |
| Scope       | R2（跨檔）、R4（全庫） | 已動  | 下一輪       | —                |
| Cadence     | R2                | 已動       | 下一輪       | —                |
| Granularity | R1（字句）、R3（結構） | 已動  | 下一輪       | —                |
| Instance    | R1-R4 皆同一 session 派出 | 未動（僅最弱切換） | 另一個執行者 | 建票：異源交換掃描 |
| Timing      | R1-R4 皆「寫完當下」 | 未動    | 時間         | 建票：隔時間後冷讀 |

Surface 軸的 report card 這一格標「不適用」（審查對象是 skill、沒有這種表面），不計入分母。

**這張表的第一版有兩處錯**，兩處都出在憑印象填：Surface 軸被判為未動（R1 與 R3 各審過一次），Instance 軸被判為「名義動、實質未動」而沒有分出強度。逐 reviewer 對帳之後才成為上表。範例包含這次修正，因為兩個版本的外觀相同——差別只在填表時手上有沒有 reviewer 清單。

## 反模式

- 「再來一輪」沒指定軸切換、把多輪當成單軸加深
- 把 instance 當主要變量（換一個 reviewer agent 跑同 frame）、忽略 frame / surface 才是主要 catch 維度
- 把七軸當 checklist 填空、不檢查每軸是否真的有 substantive 切換
