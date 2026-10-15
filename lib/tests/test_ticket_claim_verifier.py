"""ticket_claim_verifier：新認領、重複認領（started_at 舊值）、非 in_progress、讀票失敗。"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lib.ticket_claim_verifier import (  # noqa: E402
    CLAIMED_AT_WINDOW_SECONDS,
    extract_claim_ticket_ids,
    make_claim_verifier,
)
from lib.ticket_completed_verifier import VerifierUnavailable  # noqa: E402

NOW = datetime(2026, 10, 15, 12, 0, 0)
TID = "0.5.0-W1-900"


def _write_ticket(root, ticket_id, status, started_at):
    d = root / "docs" / "work-logs" / "v0.5.0" / "tickets"
    d.mkdir(parents=True, exist_ok=True)
    stamp = "null" if started_at is None else "'{}'".format(started_at.isoformat())
    (d / "{}.md".format(ticket_id)).write_text(
        "---\nid: {}\nstatus: {}\nstarted_at: {}\n---\n# body\n".format(
            ticket_id, status, stamp),
        encoding="utf-8",
    )


def _verifier(root, command):
    return make_claim_verifier(command, now=lambda: NOW, project_root=root)


COMMANDS = [
    "ticket track claim {}",
    "ticket track claim {} > log 2>&1; echo rc=$?",
    "out=$(ticket track claim {} --as pm 2>&1); rc=$?",
]


@pytest.mark.parametrize("template", COMMANDS)
def test_just_claimed_is_true(tmp_path, template):
    _write_ticket(tmp_path, TID, "in_progress", NOW - timedelta(seconds=3))
    assert _verifier(tmp_path, template.format(TID))() is True


@pytest.mark.parametrize("template", COMMANDS)
def test_repeat_claim_keeps_old_started_at_is_false(tmp_path, template):
    """E1 對照：同一張 in_progress 的票，started_at 在窗內為真、在窗外為假。"""
    old = NOW - timedelta(seconds=CLAIMED_AT_WINDOW_SECONDS + 60)
    _write_ticket(tmp_path, TID, "in_progress", old)
    assert _verifier(tmp_path, template.format(TID))() is False


def test_not_in_progress_is_false(tmp_path):
    _write_ticket(tmp_path, TID, "pending", None)
    assert _verifier(tmp_path, COMMANDS[0].format(TID))() is False


def test_missing_ticket_is_unavailable(tmp_path):
    with pytest.raises(VerifierUnavailable):
        _verifier(tmp_path, COMMANDS[0].format(TID))()


def test_missing_started_at_is_unavailable(tmp_path):
    _write_ticket(tmp_path, TID, "in_progress", None)
    with pytest.raises(VerifierUnavailable):
        _verifier(tmp_path, COMMANDS[0].format(TID))()


def test_no_ticket_id_in_command_is_unavailable(tmp_path):
    with pytest.raises(VerifierUnavailable):
        _verifier(tmp_path, "ticket track claim --help")()


def test_extract_ignores_non_claim_verbs():
    assert extract_claim_ticket_ids("ticket track complete {}".format(TID)) == []
    assert extract_claim_ticket_ids("ticket track claim {}".format(TID)) == [TID]
