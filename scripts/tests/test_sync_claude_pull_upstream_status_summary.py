"""sync-pull 結束摘要列出待回報 error-pattern（3.6.0-W1-352.2）。"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location("sync_claude_pull_upstream_status", _SCRIPT)
assert _spec and _spec.loader
pull = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_upstream_status"] = pull
_spec.loader.exec_module(pull)  # type: ignore[union-attr]

_REAL_LIB = (
    Path(__file__).resolve().parent.parent.parent
    / "skills" / "error-pattern" / "lib" / "upstream_status.py"
)


def _project(tmp_path):
    root = tmp_path / "proj"
    lib = root / ".claude" / "skills" / "error-pattern" / "lib"
    lib.mkdir(parents=True)
    (lib / "upstream_status.py").write_text(_REAL_LIB.read_text(encoding="utf-8"), encoding="utf-8")
    pat = root / ".claude" / "error-patterns" / "implementation"
    pat.mkdir(parents=True)
    (pat / "IMP-ZZZ-009-a.md").write_text("---\nid: x\n---\n本地獨有\n", encoding="utf-8")
    upstream = tmp_path / "upstream" / ".claude" / "error-patterns"
    upstream.mkdir(parents=True)
    return root, tmp_path / "upstream"


def test_summary_collected_then_printed(tmp_path, capsys):
    root, upstream = _project(tmp_path)
    pull.collect_upstream_status_summary(upstream, root)
    pull.report_upstream_status_summary()
    err = capsys.readouterr().err
    assert "IMP-ZZZ-009" in err
    assert "intake_draft.py" in err


def test_no_output_when_nothing_pending(tmp_path, capsys):
    root, upstream = _project(tmp_path)
    for f in (root / ".claude" / "error-patterns").rglob("IMP-*.md"):
        f.unlink()
    pull.collect_upstream_status_summary(upstream, root)
    pull.report_upstream_status_summary()
    assert capsys.readouterr().err == ""
