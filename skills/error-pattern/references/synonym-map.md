# Error-Pattern 同義詞對照表

> **用途**：`/error-pattern query` 的關鍵字擴展。查詢前先比對本表，將用戶輸入的關鍵字擴展為同根家族的所有變體，以 multi-term OR grep 取代單一關鍵字 grep，解決同根異名漂移導致的去重死角。
>
> **維護原則**：只維護已觀察到零字串重疊的高頻根因家族。不追求完美覆蓋——低頻 / 單篇的 PC 不需要同義詞擴展。新增家族時附來源 PC 編號。
>
> **來源**：tarrragon/claude issue #14 選項 A（1.5.0-W3-001）。

## 同義詞家族

| 家族 ID | 核心概念 | 同義詞清單（grep OR 展開用） | 來源 PC |
|---------|---------|--------------------------|---------|
| FAM-001 | confabulation（虛構工具結果） | `confabul`, `fabricat`, `conflate`, `幻覺`, `虛構`, `腦補`, `編造`, `捏造` | PC-166, PC-147, PC-111, PC-V1-003, PC-V1-010 |
| FAM-002 | scope creep（範圍蔓延） | `scope`, `範圍蔓延`, `越界`, `超出範圍`, `scope creep`, `scope expansion` | PC-042, PC-047 |
| FAM-003 | silent failure（靜默失敗） | `silent`, `靜默`, `吞掉`, `swallow`, `無聲`, `不可見` | IMP-003, IMP-013 |
| FAM-004 | stale state（過時狀態） | `stale`, `過時`, `陳舊`, `outdated`, `obsolete`, `drift`, `漂移` | PC-055, PC-078, PC-094 |
| FAM-005 | tool selection bias（工具選擇偏誤） | `tool select`, `工具選擇`, `偏誤`, `bias`, `early stop`, `提前停止`, `self-imposed` | PC-088, PC-112 |

## grep 展開範例

用戶查詢 `幻覺` 時，比對到 FAM-001，展開為：

```bash
grep -rli "confabul\|fabricat\|conflate\|幻覺\|虛構\|腦補\|編造\|捏造" .claude/error-patterns/
```

用戶查詢 `stale` 時，比對到 FAM-004，展開為：

```bash
grep -rli "stale\|過時\|陳舊\|outdated\|obsolete\|drift\|漂移" .claude/error-patterns/
```

## 新增家族 SOP

1. 觀察到同根因 PC/IMP 使用不同用詞（grep 互不命中）
2. 在本表新增一列，列出所有觀察到的變體
3. 附來源 PC 編號
4. 驗證：對每個變體執行 `grep -rli "<變體>" .claude/error-patterns/`，確認命中數 >= 1

---

**Last Updated**: 2026-07-01
**Version**: 1.0.0 — 初始建立，5 個高頻家族（confabulation / scope creep / silent failure / stale state / tool selection bias）
