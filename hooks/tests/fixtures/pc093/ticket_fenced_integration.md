---
id: test-fenced-integration
---

# AC12 整合測試：fenced + Schema placeholder + REF + 真實命中共存

## Problem Analysis
<!-- Schema[IMP/Problem Analysis]: 範例：填入根因，例如 Phase 5 再決定的問題 -->
<!-- PC-093-exempt: cat:reason -->

---

## Solution

fenced block 內範例:

```
Phase 5 再決定 fenced-example
<!-- PC-093-exempt: bad:format -->
```

- [ref] [ ] Phase 4 評估結論明確（禁止 Phase 5 再決定）  # from upstream

實際命中（必擋）: 之後再決定 real-hit

實際豁免: <!-- PC-093-exempt: ticket-tracked:W11-018 真實豁免 -->
Phase 5 再決定 real-exempt
