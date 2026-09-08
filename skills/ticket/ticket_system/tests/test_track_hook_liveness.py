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


def test_resolve_hook_name_from_source_run_hook_safely_literal(tmp_path):
    """實測涵蓋 82/122 個 .claude/hooks/*.py 的主要寫法：無 HOOK_NAME 常數，
    字面名稱直接傳給 run_hook_safely。此為 liveness "hook" 欄位的真正權威
    來源（見 .claude/lib/hook_logging.py:run_hook_safely）。"""
    hook_file = tmp_path / "bare-commit-guard-hook.py"
    hook_file.write_text(
        "import sys\n"
        "from lib import run_hook_safely\n\n"
        "def main():\n"
        "    return 0\n\n"
        'sys.exit(run_hook_safely(main, "bare-commit-guard"))\n',
        encoding="utf-8",
    )

    result = resolve_hook_name(str(hook_file))

    assert result["name"] == "bare-commit-guard"
    assert result["source"] == "run_hook_safely_literal"
    assert result["resolved_from_path"] == str(hook_file)


def test_resolve_hook_name_run_hook_safely_literal_takes_priority_over_const(tmp_path):
    """兩種寫法同時出現時（罕見），以實際傳給 run_hook_safely 的字面值為準
    ——那才是 liveness 記錄真正寫入的值，HOOK_NAME 常數若未被使用則是
    誤導。"""
    hook_file = tmp_path / "mixed-hook.py"
    hook_file.write_text(
        'HOOK_NAME = "unused-const"\n'
        "import sys\n"
        "from lib import run_hook_safely\n\n"
        "def main():\n"
        "    return 0\n\n"
        'sys.exit(run_hook_safely(main, "actually-used-name"))\n',
        encoding="utf-8",
    )

    result = resolve_hook_name(str(hook_file))

    assert result["name"] == "actually-used-name"
    assert result["source"] == "run_hook_safely_literal"


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
    assert result["attempted"]  # 已嘗試過的解析形式須非空，供查無記錄時展示


def test_resolve_hook_name_appends_py_for_bare_stem_with_hook_suffix(tmp_path):
    """acceptance 案例一：檔名 stem 僅差 -hook 後綴（如 bare-commit-guard-hook
    -> bare-commit-guard）。使用者以檔名 stem（不含 .py）查詢時，須能解析
    到 .claude/hooks/<stem>.py 並讀出實際內部名稱。"""
    hooks_dir = tmp_path / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True)
    hook_file = hooks_dir / "bare-commit-guard-hook.py"
    hook_file.write_text(
        "import sys\n"
        "from lib import run_hook_safely\n\n"
        "def main():\n"
        "    return 0\n\n"
        'sys.exit(run_hook_safely(main, "bare-commit-guard"))\n',
        encoding="utf-8",
    )

    result = resolve_hook_name("bare-commit-guard-hook", search_root=tmp_path)

    assert result["name"] == "bare-commit-guard"
    assert result["source"] == "run_hook_safely_literal"
    assert result["resolved_from_path"] == str(hook_file)


def test_resolve_hook_name_appends_py_for_structurally_different_name(tmp_path):
    """acceptance 案例二：結構性不同，非單純去後綴（
    task-dispatch-readiness-check -> agent-dispatch-check）。"""
    hooks_dir = tmp_path / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True)
    hook_file = hooks_dir / "task-dispatch-readiness-check.py"
    hook_file.write_text(
        "import sys\n"
        "from lib import run_hook_safely\n\n"
        "def main():\n"
        "    return 0\n\n"
        'sys.exit(run_hook_safely(main, "agent-dispatch-check"))\n',
        encoding="utf-8",
    )

    result = resolve_hook_name("task-dispatch-readiness-check", search_root=tmp_path)

    assert result["name"] == "agent-dispatch-check"
    assert result["source"] == "run_hook_safely_literal"
    assert result["resolved_from_path"] == str(hook_file)


def test_resolve_hook_name_literal_records_attempted_forms(tmp_path):
    """完全找不到對應檔案時，attempted 須含「補 .py 於 .claude/hooks/」
    這個解析形式，供 0 筆訊息明示已嘗試過哪些方式（不得靜默回 0）。"""
    result = resolve_hook_name("never-heard-of-this-hook", search_root=tmp_path)

    assert result["source"] == "literal"
    assert any(
        a.endswith(str(Path(".claude") / "hooks" / "never-heard-of-this-hook.py"))
        for a in result["attempted"]
    )


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


def test_execute_zero_records_unresolved_name_does_not_claim_untriggered(fake_project_root):
    """未經確認的名稱（literal）0 筆時，訊息不得把「hook 未觸發」列為候選
    解釋，須明示已嘗試過哪些解析形式——查詢工具的失敗形態不可與它要偵測
    的失敗形態同形。"""
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = execute_hook_liveness(_args(hook="never-seen-hook"))

    output = buf.getvalue()
    assert rc == 0
    assert "名稱未經確認" in output
    assert "已嘗試以下解析形式" in output
    assert "0 筆不代表 hook 未觸發" in output
    assert "名稱輸入錯誤或 hook 確實未觸發" not in output  # 舊版並列候選的措辭不得再出現


def test_execute_zero_records_filename_stem_source_is_also_unconfirmed(fake_project_root):
    """找到檔案但無法從原始碼解析出宣告名稱（無 run_hook_safely 字面呼叫、
    無 HOOK_NAME 常數）時，檔名 stem 仍只是猜測，須與 literal 同等謹慎，
    不可宣稱「hook 確實未觸發」。"""
    hook_file = fake_project_root / "never-triggered-hook.py"
    hook_file.write_text("# no HOOK_NAME const, no run_hook_safely call\n", encoding="utf-8")

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = execute_hook_liveness(_args(hook=str(hook_file)))

    output = buf.getvalue()
    assert rc == 0
    assert "名稱未經確認" in output
    assert "已找到檔案" in output
    assert "hook 確實未觸發" not in output


def test_execute_zero_records_confirmed_source_says_no_record(fake_project_root):
    """名稱已由原始碼確認（run_hook_safely 字面呼叫）時，0 筆才可合理陳述
    為「hook 可能確實未觸發」——此時名稱本身已無疑義。"""
    hook_file = fake_project_root / "never-triggered-hook.py"
    hook_file.write_text(
        "import sys\n"
        "from lib import run_hook_safely\n\n"
        "def main():\n"
        "    return 0\n\n"
        'sys.exit(run_hook_safely(main, "never-triggered"))\n',
        encoding="utf-8",
    )

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = execute_hook_liveness(_args(hook=str(hook_file)))

    output = buf.getvalue()
    assert rc == 0
    assert "名稱已由原始碼確認" in output
    assert "無任何記錄" in output
    assert "可能代表 hook 確實未觸發" in output


def test_execute_bare_stem_resolves_hook_suffix_difference(fake_project_root):
    """acceptance 案例一端到端：以檔名 stem（bare-commit-guard-hook，不含
    .py）查詢，須解析到內部名稱 bare-commit-guard 並回傳其記錄。"""
    hooks_dir = fake_project_root / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    (hooks_dir / "bare-commit-guard-hook.py").write_text(
        "import sys\n"
        "from lib import run_hook_safely\n\n"
        "def main():\n"
        "    return 0\n\n"
        'sys.exit(run_hook_safely(main, "bare-commit-guard"))\n',
        encoding="utf-8",
    )
    _write_liveness(
        fake_project_root,
        "session-b",
        [{"hook": "bare-commit-guard", "session_id": "session-b", "pid": 9, "ts": "2026-08-21T09:00:00"}],
    )

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = execute_hook_liveness(_args(hook="bare-commit-guard-hook"))

    output = buf.getvalue()
    assert rc == 0
    assert "解析名稱: bare-commit-guard" in output
    assert "來源: run_hook_safely_literal" in output
    assert "總筆數: 1" in output


def test_execute_bare_stem_resolves_structural_name_difference(fake_project_root):
    """acceptance 案例二端到端：以檔名 stem（task-dispatch-readiness-check）
    查詢，須解析到結構性不同的內部名稱 agent-dispatch-check 並回傳其記錄。"""
    hooks_dir = fake_project_root / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    (hooks_dir / "task-dispatch-readiness-check.py").write_text(
        "import sys\n"
        "from lib import run_hook_safely\n\n"
        "def main():\n"
        "    return 0\n\n"
        'sys.exit(run_hook_safely(main, "agent-dispatch-check"))\n',
        encoding="utf-8",
    )
    _write_liveness(
        fake_project_root,
        "session-c",
        [{"hook": "agent-dispatch-check", "session_id": "session-c", "pid": 10, "ts": "2026-08-21T09:30:00"}],
    )

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = execute_hook_liveness(_args(hook="task-dispatch-readiness-check"))

    output = buf.getvalue()
    assert rc == 0
    assert "解析名稱: agent-dispatch-check" in output
    assert "來源: run_hook_safely_literal" in output
    assert "總筆數: 1" in output


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
