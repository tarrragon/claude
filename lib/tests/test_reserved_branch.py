"""reserved_branch 保留分支判定測試。

正反對照：
- 票 pending（直接命中、previous_ids 命中）→ 保留
- 票 in_progress、查無票、分支名非 feat/<票號>、查票例外 → 非保留（fail-safe）
- 查票例外時 stderr 有訊息
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib import reserved_branch  # noqa: E402
from lib.reserved_branch import find_reservation, format_reserved_lines, split_reserved  # noqa: E402

_LOGGER = logging.getLogger("test_reserved_branch")


def _write_ticket(root: Path, ticket_id: str, status: str, previous_ids=()) -> None:
    version = ticket_id.split("-W")[0]
    major, minor, _ = version.split(".")
    ticket_dir = (
        root / "docs" / "work-logs" / f"v{major}" / f"v{major}.{minor}"
        / f"v{version}" / "tickets"
    )
    ticket_dir.mkdir(parents=True, exist_ok=True)
    prev = "".join(f"\n- {p}" for p in previous_ids)
    prev_block = f"previous_ids:{prev}\n" if prev else ""
    (ticket_dir / f"{ticket_id}.md").write_text(
        f"---\nid: {ticket_id}\nstatus: {status}\n{prev_block}---\n\nbody\n",
        encoding="utf-8",
    )


def test_direct_hit_pending_ticket_stays_mandatory(tmp_path):
    """正向對照：release 回 pending 的進行中票，分支直接命中，不得列為保留。"""
    _write_ticket(tmp_path, "3.4.0-W1-214", "pending")
    assert find_reservation("feat/3.4.0-W1-214", tmp_path, _LOGGER) is None


def test_previous_id_of_pending_ticket_is_reserved(tmp_path):
    _write_ticket(tmp_path, "3.4.0-W1-214", "pending", previous_ids=["3.3.0-W1-007"])
    assert find_reservation("feat/3.3.0-W1-007", tmp_path, _LOGGER) == "3.4.0-W1-214"


def test_in_progress_ticket_branch_not_reserved(tmp_path):
    _write_ticket(tmp_path, "3.4.0-W1-214", "in_progress", previous_ids=["3.3.0-W1-007"])
    assert find_reservation("feat/3.4.0-W1-214", tmp_path, _LOGGER) is None
    assert find_reservation("feat/3.3.0-W1-007", tmp_path, _LOGGER) is None


def test_unknown_ticket_and_non_ticket_branch_not_reserved(tmp_path):
    assert find_reservation("feat/3.4.0-W1-999", tmp_path, _LOGGER) is None
    assert find_reservation("feat/some-topic", tmp_path, _LOGGER) is None


def test_lookup_failure_falls_back_and_writes_stderr(tmp_path, monkeypatch, capsys):
    def _boom(*args, **kwargs):
        raise OSError("disk gone")

    monkeypatch.setattr(reserved_branch, "find_ticket_file", _boom)
    assert find_reservation("feat/3.4.0-W1-214", tmp_path, _LOGGER) is None
    assert "保留分支查票失敗" in capsys.readouterr().err


def test_split_reserved_separates_and_info_line_has_no_mandatory_wording(tmp_path):
    _write_ticket(tmp_path, "3.4.0-W1-214", "pending", previous_ids=["3.3.0-W1-007"])
    _write_ticket(tmp_path, "3.4.0-W1-300", "in_progress")
    active, reserved = split_reserved(
        ["feat/3.3.0-W1-007", "feat/3.4.0-W1-300"], tmp_path, _LOGGER
    )
    assert active == ["feat/3.4.0-W1-300"]
    assert reserved == {"feat/3.3.0-W1-007": "3.4.0-W1-214"}
    text = "\n".join(format_reserved_lines(reserved))
    assert "強制" not in text and "git merge" not in text
