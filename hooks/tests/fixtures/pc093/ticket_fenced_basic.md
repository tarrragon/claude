---
id: test-fenced-basic
---

# Section A - fenced block 內含 M1 反模式範例（EDGE-12, AC1）

以下為反模式範例（必須豁免）:

```
Phase 5 再決定是否保留 use_cache
```

# Section B - fenced block 內含 M2/M3 範例（AC1）

```text
之後再決定處理方式
保留 use_cache 以防萬一
```

# Section C - fenced block 內含 PC-093-exempt 範例 marker（EDGE-11, AC4）

```markdown
<!-- PC-093-exempt: cat:reason -->
<!-- PC-093-exempt: <category>:<reason> -->
```

# Section D - 區塊外的實際命中（AC10 regression）

Phase 5 再決定真實命中

# Section E - 區塊外的實際 exempt marker（AC11 regression）

<!-- PC-093-exempt: ticket-tracked:W11-018 fenced block 測試 -->
Phase 5 再決定真實豁免
