"""ticket_completed_verifier：時間窗、舊票、讀票失敗三條路徑。"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lib.ticket_completed_verifier import (  # noqa: E402
    COMPLETED_AT_WINDOW_SECONDS,
    VerifierUnavailable,
    make_completed_verifier,
)

NOW = datetime(2026, 10, 15, 12, 0, 0)
TID = "0.5.0-W1-900"


def _write_ticket(root, ticket_id, status, completed_at):
    d = root / "docs" / "work-logs" / "v0.5.0" / "tickets"
    d.mkdir(parents=True, exist_ok=True)
    stamp = "null" if completed_at is None else "'{}'".format(completed_at.isoformat())
    (d / "{}.md".format(ticket_id)).write_text(
        "---\nid: {}\nstatus: {}\ncompleted_at: {}\n---\n# body\n".format(
            ticket_id, status, stamp),
        encoding="utf-8",
    )


def _verifier(root, command):
    return make_completed_verifier(command, now=lambda: NOW, project_root=root)


MASKED = [
    "ticket track finish {} > log 2>&1; echo rc=$?",
    "out=$(ticket track complete {} 2>&1); rc=$?",
]


@pytest.mark.parametrize("template", MASKED)
def test_just_completed_is_true(tmp_path, template):
    _write_ticket(tmp_path, TID, "completed", NOW - timedelta(seconds=3))
    assert _verifier(tmp_path, template.format(TID))() is True


@pytest.mark.parametrize("template", MASKED)
def test_recomplete_of_old_ticket_is_false(tmp_path, template):
    old = NOW - timedelta(seconds=COMPLETED_AT_WINDOW_SECONDS + 60)
    _write_ticket(tmp_path, TID, "completed", old)
    assert _verifier(tmp_path, template.format(TID))() is False


def test_not_completed_status_is_false(tmp_path):
    _write_ticket(tmp_path, TID, "in_progress", None)
    assert _verifier(tmp_path, MASKED[0].format(TID))() is False


def test_batch_requires_every_ticket(tmp_path):
    other = "0.5.0-W1-901"
    _write_ticket(tmp_path, TID, "completed", NOW)
    _write_ticket(tmp_path, other, "in_progress", None)
    command = "ticket track batch-complete {} {}; echo rc=$?".format(TID, other)
    assert _verifier(tmp_path, command)() is False


@pytest.mark.parametrize("command", [
    "ticket track complete {}; echo rc=$?".format("0.5.0-W1-999"),  # 票不存在
    "ticket track complete X-NONE; echo rc=$?",  # 無可辨識票號
])
def test_read_failure_raises_not_false_or_true(tmp_path, command):
    with pytest.raises(VerifierUnavailable):
        _verifier(tmp_path, command)()


def test_transition_unmasked_old_ticket_false_recent_true(tmp_path):
    from lib.ticket_completed_verifier import is_complete_transition_success

    cmd = "ticket track complete {}".format(TID)
    resp = {"stdout": "{} 已完成於 2026-10-15T11:52:55".format(TID)}
    _write_ticket(tmp_path, TID, "completed", NOW - timedelta(hours=1))
    assert is_complete_transition_success(
        resp, ["已完成"], cmd, _verifier(tmp_path, cmd)) is False
    _write_ticket(tmp_path, TID, "completed", NOW - timedelta(seconds=2))
    assert is_complete_transition_success(
        resp, ["已完成"], cmd, _verifier(tmp_path, cmd)) is True


def test_transition_unavailable_falls_back_to_layered(tmp_path):
    from lib.ticket_completed_verifier import is_complete_transition_success

    cmd = "ticket track complete {}".format("0.5.0-W1-999")
    assert is_complete_transition_success(
        {"stdout": ""}, ["已完成"], cmd, _verifier(tmp_path, cmd)) is True  # 未遮蔽
    masked = cmd + "; echo rc=$?"
    assert is_complete_transition_success(
        {"stdout": ""}, ["已完成"], masked, _verifier(tmp_path, masked)) is False  # 退回標記


def test_missing_completed_at_raises(tmp_path):
    _write_ticket(tmp_path, TID, "completed", None)
    with pytest.raises(VerifierUnavailable):
        _verifier(tmp_path, MASKED[0].format(TID))()
