"""測試 ticket track hook-liveness 命令。

覆蓋 acceptance：以檔路徑與名稱兩種輸入皆正確回報 hook 筆數，輸出含解析到
的名稱；並涵蓋名稱解析三層、0 筆的兩種區分訊息、--since/--session 篩選。
"""

from __future__ import annotations

import argparse
import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from ticket_system.commands.track_hook_liveness import (
    execute_hook_liveness,
    resolve_hook_name,
    scan_liveness,
)


def _args(**overrides) -> argparse.Namespace:
    defaults = dict(
        operation="hook-liveness",
        hook=None,
        since=None,
        session=None,
        format="table",
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _write_liveness(tmp_path: Path, session_id: str, records: list) -> Path:
    liveness_dir = tmp_path / ".claude" / "hook-logs" / "_liveness"
    liveness_dir.mkdir(parents=True, exist_ok=True)
    path = liveness_dir / f"{session_id}.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")
    return path


# ---------------------------------------------------------------------------
# resolve_hook_name（三層解析）
# ---------------------------------------------------------------------------


def test_resolve_hook_name_from_source_const(tmp_path):
    hook_file = tmp_path / "foo-guard-hook.py"
    hook_file.write_text('HOOK_NAME = "foo-guard"\n', encoding="utf-8")

    result = resolve_hook_name(str(hook_file))

    assert result["name"] == "foo-guard"
    assert result["source"] == "hook_name_const"
    assert result["resolved_from_path"] == str(hook_file)


def test_resolve_hook_name_fallback_to_filename_stem(tmp_path):
    hook_file = tmp_path / "bar-check-hook.py"
    hook_file.write_text("# no HOOK_NAME const here\n", encoding="utf-8")

    result = resolve_hook_name(str(hook_file))

    assert result["name"] == "bar-check-hook"
    assert result["source"] == "filename_stem"


def test_resolve_hook_name_literal_for_nonexistent_path():
    result = resolve_hook_name("some-hook-name")

    assert result["name"] == "some-hook-name"
    assert result["source"] == "literal"
    assert result["resolved_from_path"] is None


# ---------------------------------------------------------------------------
# scan_liveness
# ---------------------------------------------------------------------------


def test_scan_liveness_aggregates_by_session(tmp_path):
    _write_liveness(
        tmp_path,
        "session-a",
        [
            {"hook": "foo-guard", "session_id": "session-a", "pid": 1, "ts": "2026-08-21T10:00:00"},
            {"hook": "foo-guard", "session_id": "session-a", "pid": 2, "ts": "2026-08-21T11:00:00"},
            {"hook": "other-hook", "session_id": "session-a", "pid": 3, "ts": "2026-08-21T12:00:00"},
        ],
    )
    _write_liveness(
        tmp_path,
        "session-b",
        [
            {"hook": "foo-guard", "session_id": "session-b", "pid": 4, "ts": "2026-08-20T09:00:00"},
        ],
    )
    liveness_dir = tmp_path / ".claude" / "hook-logs" / "_liveness"

    result = scan_liveness("foo-guard", liveness_dir)

    assert result["total"] == 3
    assert result["by_session"] == {"session-a": 2, "session-b": 1}
    assert result["latest_ts"] == "2026-08-21T11:00:00"


def test_scan_liveness_session_filter(tmp_path):
    _write_liveness(
        tmp_path,
        "session-a",
        [{"hook": "foo-guard", "session_id": "session-a", "pid": 1, "ts": "2026-08-21T10:00:00"}],
    )
    _write_liveness(
        tmp_path,
        "session-b",
        [{"hook": "foo-guard", "session_id": "session-b", "pid": 2, "ts": "2026-08-21T10:00:00"}],
    )
    liveness_dir = tmp_path / ".claude" / "hook-logs" / "_liveness"

    result = scan_liveness("foo-guard", liveness_dir, session_filter="session-a")

    assert result["total"] == 1
    assert result["by_session"] == {"session-a": 1}


def test_scan_liveness_no_match_returns_zero(tmp_path):
    _write_liveness(
        tmp_path,
        "session-a",
        [{"hook": "other-hook", "session_id": "session-a", "pid": 1, "ts": "2026-08-21T10:00:00"}],
    )
    liveness_dir = tmp_path / ".claude" / "hook-logs" / "_liveness"

    result = scan_liveness("foo-guard", liveness_dir)

    assert result["total"] == 0
    assert result["by_session"] == {}
    assert result["latest_ts"] is None


# ---------------------------------------------------------------------------
# execute_hook_liveness（CLI 層，含檔路徑與名稱兩種輸入）
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_project_root(tmp_path, monkeypatch):
    _write_liveness(
        tmp_path,
        "session-a",
        [{"hook": "foo-guard", "session_id": "session-a", "pid": 1, "ts": "2026-08-21T10:00:00"}],
    )
    monkeypatch.setattr(
        "ticket_system.commands.track_hook_liveness.current_project_root",
        lambda: str(tmp_path),
    )
    return tmp_path


def test_execute_with_literal_name_reports_resolved_name_and_count(fake_project_root):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = execute_hook_liveness(_args(hook="foo-guard"))

    output = buf.getvalue()
    assert rc == 0
    assert "解析名稱: foo-guard" in output
    assert "來源: literal" in output
    assert "總筆數: 1" in output


def test_execute_with_file_path_resolves_hook_name_const(fake_project_root):
    hook_file = fake_project_root / "foo-guard-hook.py"
    hook_file.write_text('HOOK_NAME = "foo-guard"\n', encoding="utf-8")

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = execute_hook_liveness(_args(hook=str(hook_file)))

    output = buf.getvalue()
    assert rc == 0
    assert "解析名稱: foo-guard" in output
    assert "來源: hook_name_const" in output
    assert "總筆數: 1" in output


def test_execute_zero_records_literal_source_explains_ambiguity(fake_project_root):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = execute_hook_liveness(_args(hook="never-seen-hook"))

    output = buf.getvalue()
    assert rc == 0
    assert "名稱輸入錯誤或 hook 確實未觸發" in output


def test_execute_zero_records_resolved_source_says_no_record(fake_project_root):
    hook_file = fake_project_root / "never-triggered-hook.py"
    hook_file.write_text("# no HOOK_NAME const\n", encoding="utf-8")

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = execute_hook_liveness(_args(hook=str(hook_file)))

    output = buf.getvalue()
    assert rc == 0
    assert "名稱已解析為" in output
    assert "無任何記錄" in output


def test_execute_json_format(fake_project_root):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = execute_hook_liveness(_args(hook="foo-guard", format="json"))

    payload = json.loads(buf.getvalue())
    assert rc == 0
    assert payload["resolution"]["name"] == "foo-guard"
    assert payload["total"] == 1


def test_execute_missing_hook_input_returns_error():
    rc = execute_hook_liveness(_args(hook=""))
    assert rc == 2


def test_execute_invalid_since_format_returns_error(fake_project_root):
    rc = execute_hook_liveness(_args(hook="foo-guard", since="not-a-date"))
    assert rc == 2
