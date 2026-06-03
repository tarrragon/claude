"""
Parallel Claim Audit Hook (PostToolUse:Bash) 測試

涵蓋三情境（acceptance 4）：
1. 正常 claim：寫入 audit log，含同 wave in_progress 快照
2. claim 失敗：不寫入 audit log
3. 同 wave 多 ticket：快照含多筆且過濾跨 wave / 非 in_progress

額外驗證：
- 非 claim 命令跳過
- 任何內部失敗仍 exit 0（純 observability）
"""

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest


_HOOKS_DIR = Path(__file__).parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

_spec = importlib.util.spec_from_file_location(
    "parallel_claim_audit_hook",
    _HOOKS_DIR / "parallel-claim-audit-hook.py",
)
_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hook)


# ---------------------------------------------------------------------------
# helper
# ---------------------------------------------------------------------------


def _make_input(command, stdout="claimed", stderr=""):
    return {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_result": {"stdout": stdout, "stderr": stderr},
    }


def _write_ticket(tickets_dir: Path, ticket_id: str, status: str, who="pm"):
    content = (
        "---\n"
        "id: {id}\n"
        "status: {status}\n"
        "started_at: '2026-06-02T16:00:00'\n"
        "who:\n"
        "  current: {who}\n"
        "---\n\n# {id}\n"
    ).format(id=ticket_id, status=status, who=who)
    (tickets_dir / "{}.md".format(ticket_id)).write_text(content, encoding="utf-8")


@pytest.fixture
def project_tree(tmp_path):
    """建立 docs/work-logs/v0/v0.19/v0.19.0/tickets/ 三層結構。"""
    tickets_dir = (
        tmp_path / "docs" / "work-logs" / "v0" / "v0.19" / "v0.19.0" / "tickets"
    )
    tickets_dir.mkdir(parents=True)
    return tmp_path, tickets_dir


def _run_main(monkeypatch, project_root, input_data):
    """注入 stdin + get_project_root，執行 main()，回傳 (exit_code, stderr)。"""
    monkeypatch.setattr(_hook, "get_project_root", lambda: project_root)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(input_data)))
    err = io.StringIO()
    monkeypatch.setattr("sys.stderr", err)
    code = _hook.main()
    return code, err.getvalue()


def _read_audit(project_root: Path):
    audit_path = project_root / ".claude" / "hook-logs" / "parallel-claim-audit.log"
    if not audit_path.exists():
        return []
    return [
        json.loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


# ---------------------------------------------------------------------------
# 情境 1：正常 claim
# ---------------------------------------------------------------------------


def test_normal_claim_writes_audit_with_snapshot(monkeypatch, project_tree):
    project_root, tickets_dir = project_tree
    _write_ticket(tickets_dir, "0.19.0-W3-048", "in_progress")

    code, _ = _run_main(
        monkeypatch,
        project_root,
        _make_input("ticket track claim 0.19.0-W3-048"),
    )

    assert code == 0
    entries = _read_audit(project_root)
    assert len(entries) == 1
    entry = entries[0]
    assert entry["ticket_id"] == "0.19.0-W3-048"
    assert entry["wave"] == 3
    assert "timestamp" in entry
    ids = [t["id"] for t in entry["same_wave_in_progress"]]
    assert "0.19.0-W3-048" in ids


# ---------------------------------------------------------------------------
# 情境 2：claim 失敗
# ---------------------------------------------------------------------------


def test_failed_claim_does_not_write_audit(monkeypatch, project_tree):
    project_root, tickets_dir = project_tree
    _write_ticket(tickets_dir, "0.19.0-W3-048", "pending")

    code, _ = _run_main(
        monkeypatch,
        project_root,
        _make_input(
            "ticket track claim 0.19.0-W3-048",
            stdout="",
            stderr="Error: ticket already claimed by another agent",
        ),
    )

    assert code == 0
    assert _read_audit(project_root) == []


# ---------------------------------------------------------------------------
# 情境 3：同 wave 多 ticket（含跨 wave / 非 in_progress 過濾）
# ---------------------------------------------------------------------------


def test_multiple_same_wave_tickets_snapshot(monkeypatch, project_tree):
    project_root, tickets_dir = project_tree
    _write_ticket(tickets_dir, "0.19.0-W3-046", "in_progress")
    _write_ticket(tickets_dir, "0.19.0-W3-047", "in_progress")
    _write_ticket(tickets_dir, "0.19.0-W3-048", "in_progress")
    # 跨 wave：不應納入
    _write_ticket(tickets_dir, "0.19.0-W1-001", "in_progress")
    # 同 wave 但非 in_progress：不應納入
    _write_ticket(tickets_dir, "0.19.0-W3-050", "pending")

    code, _ = _run_main(
        monkeypatch,
        project_root,
        _make_input("ticket track claim 0.19.0-W3-048"),
    )

    assert code == 0
    entries = _read_audit(project_root)
    assert len(entries) == 1
    snapshot_ids = {t["id"] for t in entries[0]["same_wave_in_progress"]}
    assert snapshot_ids == {"0.19.0-W3-046", "0.19.0-W3-047", "0.19.0-W3-048"}
    assert entries[0]["same_wave_in_progress_count"] == 3


# ---------------------------------------------------------------------------
# 附加：非 claim 命令跳過
# ---------------------------------------------------------------------------


def test_non_claim_command_skipped(monkeypatch, project_tree):
    project_root, _ = project_tree
    code, _ = _run_main(
        monkeypatch, project_root, _make_input("git commit -m 'x'")
    )
    assert code == 0
    assert _read_audit(project_root) == []


def test_claim_help_option_not_misparsed(monkeypatch, project_tree):
    project_root, _ = project_tree
    code, _ = _run_main(
        monkeypatch, project_root, _make_input("ticket track claim --help")
    )
    assert code == 0
    assert _read_audit(project_root) == []


# ---------------------------------------------------------------------------
# 附加：內部失敗仍 exit 0 + 雙通道輸出（規則 4）
# ---------------------------------------------------------------------------


def test_internal_failure_still_exits_zero(monkeypatch, project_tree):
    project_root, _ = project_tree

    def _boom(*a, **k):
        raise RuntimeError("snapshot boom")

    monkeypatch.setattr(_hook, "build_same_wave_snapshot", _boom)

    code, stderr = _run_main(
        monkeypatch,
        project_root,
        _make_input("ticket track claim 0.19.0-W3-048"),
    )

    assert code == 0
    assert "不影響 claim" in stderr  # 雙通道之 stderr
    assert _read_audit(project_root) == []


# ---------------------------------------------------------------------------
# parse_claim_command 單元測試
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command,expected",
    [
        ("ticket track claim 0.19.0-W3-048", "0.19.0-W3-048"),
        ("cd x && ticket track claim 1.0.0-W2-003", "1.0.0-W2-003"),
        ("ticket track list", None),
        ("ticket track claim --help", None),
        ("", None),
    ],
)
def test_parse_claim_command(command, expected):
    assert _hook.parse_claim_command(command) == expected
