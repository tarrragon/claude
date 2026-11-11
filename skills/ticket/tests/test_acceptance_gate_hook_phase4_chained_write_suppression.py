"""acceptance-gate-hook：同命令鏈 append-log 補寫 Phase 4 後 complete，不再報缺 Phase 4。

PreToolUse 在整條命令執行前讀檔一次，同鏈前段 append-log 寫入的 Phase 4 段落
尚未落檔。步驟 9（Phase 4 審查證據）比照步驟 6／8 於同鏈偵測時略過判定，
清單第 8、9 項標 [--]。正向對照：非同鏈且 Phase 4 真缺時仍報缺。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_TICKET_ID = "0.0.0-W1-997"


def _load_hook_module():
    hook_path = Path(__file__).resolve().parents[1] / "hooks" / "acceptance-gate-hook.py"
    spec = importlib.util.spec_from_file_location("acceptance_gate_hook_p4", hook_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_imp_ticket_without_phase4(tmp_path: Path) -> None:
    ticket_dir = tmp_path / "docs" / "work-logs" / "v0.0.0" / "tickets"
    ticket_dir.mkdir(parents=True, exist_ok=True)
    (ticket_dir / f"{_TICKET_ID}.md").write_text(
        f"""---
id: {_TICKET_ID}
title: dummy
type: IMP
status: in_progress
children: []
---

## Solution

### 修復摘要
做了 X。

## Test Results
通過。
""",
        encoding="utf-8",
    )


class _FakeLogger:
    def info(self, *a, **k):
        pass

    debug = warning = error = info


_CHAINED = (
    f'ticket track append-log {_TICKET_ID} --section "Solution" '
    '"### Phase 4 評估\\n- 重構需要：否" && '
    f"ticket track complete {_TICKET_ID}"
)


def _check(tmp_path, command):
    module = _load_hook_module()
    _write_imp_ticket_without_phase4(tmp_path)
    result = module.check_acceptance_status(
        _TICKET_ID, tmp_path, _FakeLogger(), command=command
    )
    return module, result


def test_unchained_missing_phase4_still_warns(tmp_path):
    """正向對照：非同鏈、Phase 4 真缺 → 仍報缺。"""
    module, result = _check(tmp_path, f"ticket track complete {_TICKET_ID}")
    assert result.phase4_review_warning is not None
    output = module.generate_hook_output(_TICKET_ID, result, tmp_path, _FakeLogger())
    context = output["hookSpecificOutput"].get("additionalContext", "")
    assert "[WARNING] 9. Solution 缺 Phase 4 審查證據" in context


def test_chained_append_log_suppresses_phase4_warning(tmp_path):
    module, result = _check(tmp_path, _CHAINED)
    assert result.phase4_review_warning is None
    output = module.generate_hook_output(_TICKET_ID, result, tmp_path, _FakeLogger())
    context = output["hookSpecificOutput"].get("additionalContext", "")
    assert "缺 Phase 4" not in context
    assert "[--] 9. Phase 4 審查證據（同命令鏈偵測" in context
    assert "[--] 8. Layer 1 自檢（同命令鏈偵測" in context
