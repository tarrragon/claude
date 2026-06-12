# 寫作 Review 是多軸完整性、不是單軸深度

> **角色**：本卡是 `multi-round-review` 的支撐型原則、被「Round N 停止訊號」段引用。
>
> **何時讀**：判斷 review 完整性時、用七軸 checklist 對齊覆蓋。

## 結論

Review 完整性是七軸交集、缺軸不缺深度。單軸越做越深會 systematic miss 對應軸盲點。設計 review 流程時 enumerate 七軸覆蓋狀況、不是加輪數。

## 七軸

| 軸          | 切換方式                                              | 主要 catch 目標                                                           |
| ----------- | ----------------------------------------------------- | ------------------------------------------------------------------------- |
| Frame       | Compliance / cadence / steelman / self-application 等 | 不同 frame 抓不同類問題                                                   |
| Instance    | 不同 reviewer agent / 不同 LLM / 不同人               | 同 frame 但不同 instance 偶有差異                                         |
| Surface     | 章節 body / title / frontmatter / index / report card | 不同 surface 有獨立違反模式                                               |
| Scope       | 單章 / 跨章 / 跨模組 / 跨 batch                       | 不同 scope 抓不同層級問題                                                 |
| Cadence     | 字句 / 句型 / 段落結構                                | Cadence 層問題（per [cadence-homogenization](cadence-homogenization.md)） |
| Timing      | 寫作前 / 寫作中 / 寫完當下 / 寫完一週後               | 不同 timing reviewer 看到不同問題                                         |
| Granularity | 字句 / 段落 / 章節 / 模組                             | 粒度差會 catch 不同類問題                                                 |

## 套用方式

規劃 multi-round review 時、按七軸列出 Round 1 到 Round N 各動了哪幾軸、找出未動的軸 — 那就是 Round N+1 的價值來源。

## 反模式

- 「再來一輪」沒指定軸切換、把多輪當成單軸加深
- 把 instance 當主要變量（換一個 reviewer agent 跑同 frame）、忽略 frame / surface 才是主要 catch 維度
- 把七軸當 checklist 填空、不檢查每軸是否真的有 substantive 切換
