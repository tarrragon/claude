---
id: test-distance
---

# Section A - same line suffix (DIST-1)

Phase 4 再決定 foo。<!-- PC-093-exempt: baseline-gated:baseline>80ms 才啟用 -->

# Section B - prev 1 line (DIST-2)

<!-- PC-093-exempt: baseline-gated:baseline>80ms 才啟用 -->
Phase 4 再決定 bar。

# Section C - prev 2 lines, should NOT exempt (DIST-3)

<!-- PC-093-exempt: baseline-gated:baseline>80ms 才啟用 -->

Phase 4 再決定 baz。

# Section D - marker AFTER phrase, should NOT exempt (DIST-4)

Phase 4 再決定 qux。
<!-- PC-093-exempt: baseline-gated:baseline>80ms 才啟用 -->
