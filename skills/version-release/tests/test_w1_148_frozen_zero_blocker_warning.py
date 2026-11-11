"""3.2.0-W1-148: 已凍結版本零張 scope_blocker 票的警告測試。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import version_release as vr  # noqa: E402


def _ticket(tid: str, status: str, blocker: str | None = None) -> str:
    blocker_line = f"scope_blocker: '{blocker}'" if blocker else "scope_blocker: null"
    return f"---\nid: {tid}\ntype: IMP\nstatus: {status}\n{blocker_line}\n---\n\n# body\n"


def _make(tmp_path: Path, tickets: dict) -> Path:
    tickets_dir = tmp_path / "tickets"
    tickets_dir.mkdir()
    for tid, content in tickets.items():
        (tickets_dir / f"{tid}.md").write_text(content, encoding="utf-8")
    return tickets_dir


class TestDetectFrozenWithoutBlockers:
    def test_zero_blocker_with_pending_warns(self, tmp_path):
        d = _make(tmp_path, {"1.0.0-W1-001": _ticket("1.0.0-W1-001", "pending"),
                             "1.0.0-W1-002": _ticket("1.0.0-W1-002", "pending")})
        msg = vr.detect_frozen_without_blockers(d, "1.0.0")
        assert msg is not None
        assert "set-scope-blocker" in msg
        assert "2 張" in msg

    def test_one_blocker_ticket_no_warning(self, tmp_path):
        d = _make(tmp_path, {"1.0.0-W1-001": _ticket("1.0.0-W1-001", "pending", "契約項"),
                             "1.0.0-W1-002": _ticket("1.0.0-W1-002", "pending")})
        assert vr.detect_frozen_without_blockers(d, "1.0.0") is None

    def test_completed_ticket_with_blocker_counts(self, tmp_path):
        d = _make(tmp_path, {"1.0.0-W1-001": _ticket("1.0.0-W1-001", "completed", "契約項"),
                             "1.0.0-W1-002": _ticket("1.0.0-W1-002", "pending")})
        assert vr.detect_frozen_without_blockers(d, "1.0.0") is None

    def test_no_pending_no_warning(self, tmp_path):
        d = _make(tmp_path, {"1.0.0-W1-001": _ticket("1.0.0-W1-001", "completed")})
        assert vr.detect_frozen_without_blockers(d, "1.0.0") is None

    def test_missing_dir_no_warning(self, tmp_path):
        assert vr.detect_frozen_without_blockers(tmp_path / "none", "1.0.0") is None


class TestWarnWrapper:
    def test_prints_warning_only_for_zero_blocker(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(vr, "get_project_root", lambda: tmp_path)
        tickets_dir = vr.resolve_worklog_dir(
            tmp_path, "1.0.0", vr.DEFAULT_VERSION_RELEASE_CONFIG["worklog_path_pattern"]
        ) / "tickets"
        tickets_dir.mkdir(parents=True)
        path = tickets_dir / "1.0.0-W1-001.md"
        path.write_text(_ticket("1.0.0-W1-001", "pending"), encoding="utf-8")
        vr.warn_if_frozen_without_blockers("1.0.0")
        out = capsys.readouterr()
        assert "set-scope-blocker" in out.out + out.err
        path.write_text(_ticket("1.0.0-W1-001", "pending", "契約項"), encoding="utf-8")
        vr.warn_if_frozen_without_blockers("1.0.0")
        out = capsys.readouterr()
        assert "set-scope-blocker" not in out.out + out.err
