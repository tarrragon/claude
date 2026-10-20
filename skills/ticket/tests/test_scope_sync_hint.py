"""範圍欄位變更後的同步提示測試（0.5.0-W1-401）

範圍欄位：title / what / acceptance / where.files / how.strategy。
任一被 set- 改動後，stdout 列出其餘非空範圍欄位現值與對應 set- 指令；
首次填寫（原值為空）不印；只印不擋，exit code 不變。
"""

from unittest.mock import Mock, patch

from ticket_system.commands.fields import execute_set_what, execute_set_title
from ticket_system.commands.track_set_acceptance import execute_set_acceptance

TID = "0.5.0-W1-900"
HINT_MARK = "範圍欄位同步提示"


def _args(**kw):
    args = Mock()
    args.ticket_id = TID
    args.value = kw.pop("value", None)
    args.version = "0.5.0"
    for k, v in kw.items():
        setattr(args, k, v)
    return args


def _full_ticket(**over):
    ticket = {
        "id": TID,
        "type": "IMP",
        "status": "in_progress",
        "title": "舊標題",
        "what": "舊敘述",
        "acceptance": ["[ ] 條目甲", "[ ] 條目乙"],
        "where": {"layer": "Infra", "files": ["a/b.py"]},
        "how": {"task_type": "Implementation", "strategy": "舊策略"},
    }
    ticket.update(over)
    return ticket


def _run_set_what(ticket, value="新敘述"):
    with patch("ticket_system.commands.fields.load_and_validate_ticket") as ld, patch(
        "ticket_system.commands.fields.ticket_loader.save_ticket"
    ), patch(
        "ticket_system.commands.fields.git_utils.commit_ticket_md_reporting", return_value=False
    ):
        ld.return_value = (ticket, None)
        return execute_set_what(_args(value=value), "0.5.0")


class TestScopeSyncHint:
    def test_set_what_lists_other_scope_fields(self, capsys):
        rc = _run_set_what(_full_ticket())
        out = capsys.readouterr().out
        assert rc == 0
        assert HINT_MARK in out
        for cmd in ("set-title", "set-acceptance", "set-where", "set-how"):
            assert cmd in out
        assert "舊標題" in out and "舊策略" in out and "a/b.py" in out
        # 被改欄位本身不列入
        assert "ticket track set-what" not in out

    def test_first_fill_prints_no_hint_and_differs_from_populated(self, capsys):
        """E1：同批 fixture，原值為空（首次填寫）不印；已有值才印。"""
        populated = _full_ticket()
        first_fill = _full_ticket(what="")
        rc_a = _run_set_what(populated)
        out_populated = capsys.readouterr().out
        rc_b = _run_set_what(first_fill)
        out_first = capsys.readouterr().out
        assert rc_a == 0 and rc_b == 0
        assert HINT_MARK in out_populated
        assert HINT_MARK not in out_first
        assert out_populated != out_first

    def test_no_hint_when_other_fields_all_empty(self, capsys):
        ticket = {"id": TID, "type": "IMP", "status": "in_progress", "what": "舊"}
        _run_set_what(ticket)
        assert HINT_MARK not in capsys.readouterr().out

    def test_set_title_hint(self, capsys):
        ticket = _full_ticket()
        with patch("ticket_system.commands.fields.load_and_validate_ticket") as ld, patch(
            "ticket_system.commands.fields.ticket_loader.save_ticket"
        ), patch(
            "ticket_system.commands.fields.git_utils.commit_ticket_md_reporting", return_value=False
        ):
            ld.return_value = (ticket, None)
            rc = execute_set_title(_args(value="新標題"), "0.5.0")
        out = capsys.readouterr().out
        assert rc == 0
        assert HINT_MARK in out and "set-what" in out

    def test_set_acceptance_edit_hint(self, capsys):
        ticket = _full_ticket()
        args = _args(
            edit=[["1", "改寫後條目"]], check=None, uncheck=None, add=None,
            remove=None, all_check=None, all_uncheck=None, force=False, as_agent=None,
        )
        with patch("ticket_system.commands.track_set_acceptance.load_and_validate_ticket") as ld, patch(
            "ticket_system.commands.track_set_acceptance.save_ticket"
        ), patch(
            "ticket_system.lib.identity_guard.check_identity", return_value=None
        ), patch(
            "ticket_system.lib.git_utils.commit_ticket_md_reporting", return_value=False
        ):
            ld.return_value = (ticket, None)
            rc = execute_set_acceptance(args, "0.5.0")
        out = capsys.readouterr().out
        assert rc == 0
        assert HINT_MARK in out and "set-title" in out and "set-what" in out
