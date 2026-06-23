# Hook sys.path 標準模板

新增或修改 hook 的 sys.path 設定時，依位置選用對應模板。

## Main hooks（`.claude/hooks/*.py`）

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))         # .claude/hooks/ (hook_utils)
sys.path.insert(0, str(Path(__file__).parent.parent))   # .claude/       (lib.*)
```

**解釋**：`parent` 指向 `.claude/hooks/`（含 `hook_utils/` package），`parent.parent` 指向 `.claude/`（含 `lib/` package）。兩行順序不影響功能但建議保持一致。

## Skill hooks（`.claude/skills/<name>/hooks/*.py`）

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))              # .claude/       (lib.*)
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))    # .claude/hooks/ (hook_utils)
```

**解釋**：skill hooks 位於 `.claude/skills/<name>/hooks/`，需向上 4 層（parents[3]）到 `.claude/`。`resolve()` 處理 symlink 場景。

## 需要額外路徑的 hook

若 hook 需要 `.claude/config/` 或 skill 內部模組，在標準兩行後追加：

```python
sys.path.insert(0, str(Path(__file__).parent.parent / "config"))  # .claude/config/
```

## 驗證

修改後執行 `bash .claude/scripts/test-hook-imports.sh --verbose` 確認無 import 失敗。

---

**Last Updated**: 2026-06-23
**Version**: 1.0.0 — Framework issue #10 建議 2 落地（W2-005）
