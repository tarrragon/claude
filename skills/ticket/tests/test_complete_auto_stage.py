"""
W11-035 ticket complete 自動 git add + commit 提示測試

來源：W11-034 ANA 推薦方案 D（自動 add + stdout 提示）

驗證情境：
1. 正常 complete：ticket md + worklog md 被 git add
2. cascade complete：unblocked children md 也被 git add
3. --no-stage flag：跳過自動 staging
4. stdout 含建議 commit 指令 `chore(<id>): metadata sync`
5. 不誤觸 git add 範圍外的 WIP 檔案（僅 add 已知 modified 路徑）
"""

from unittest.mock import patch

import pytest

TEMPLATE_BODY = """## Completion Info

**Completion Time**: (pending)
**Executing Agent**: thyme-python-developer
**Review Status**: pending
"""


def _build_ticket(ticket_id="0.18.0-W17-998", children=None):
    return {
        "id": ticket_id,
        "status": "in_progress",
        "title": "Test auto stage",
        "type": "IMP",
        "who": {"current": "thyme-python-developer"},
        "acceptance": [{"text": "x", "completed": True}],
        "children": children or [],
        "_body": TEMPLATE_BODY,
        "_path": f"/tmp/{ticket_id}.md",
    }


def _run_complete(
    *,
    ticket,
    no_stage=False,
    cascade_unblocked=None,
):
    """共用 patch 結構，回傳 (result, captured_subprocess_calls)"""
    from ticket_system.commands.lifecycle import TicketLifecycle

    lifecycle = TicketLifecycle("0.18.0")

    captured_calls = []

    def fake_git_add(paths):
        captured_calls.append(["git", "add", *paths])

    # cascade fake：模擬 _post_complete_cascade 解鎖 children
    def fake_cascade(parent_ticket, version, ticket_map):
        unblocked = []
        if cascade_unblocked:
            for child_id in cascade_unblocked:
                if child_id in ticket_map:
                    ticket_map[child_id]["status"] = "pending"
                unblocked.append({"id": child_id, "title": ""})
        return unblocked

    def fake_resolve_path(t, version, tid):
        return f"/tmp/{tid}.md"

    # 模擬 worklog appender 寫入後路徑可推導
    fake_worklog_path = "/tmp/worklog-0.18.0.md"

    with patch(
        "ticket_system.commands.lifecycle.load_and_validate_ticket",
        return_value=(ticket, None),
    ), patch(
        "ticket_system.commands.lifecycle.validate_completable_status",
        return_value=(True, "", False),
    ), patch(
        "ticket_system.commands.lifecycle.validate_acceptance_criteria",
        return_value=(True, []),
    ), patch(
        "ticket_system.commands.lifecycle.validate_execution_log",
        return_value=(True, []),
    ), patch(
        "ticket_system.commands.lifecycle.validate_execution_log_by_type",
        return_value=(True, []),
    ), patch(
        "ticket_system.commands.lifecycle.save_ticket"
    ), patch(
        "ticket_system.commands.lifecycle.resolve_ticket_path",
        side_effect=fake_resolve_path,
    ), patch(
        "ticket_system.commands.lifecycle.append_worklog_progress"
    ), patch(
        "ticket_system.commands.lifecycle._build_worklog_path_for_stage",
        return_value=fake_worklog_path,
    ), patch(
        "ticket_system.commands.lifecycle.list_tickets",
        return_value=[
            {"id": cid} for cid in (cascade_unblocked or [])
        ],
    ), patch(
        "ticket_system.commands.lifecycle._analyze_next_steps",
        return_value={},
    ), patch(
        "ticket_system.commands.lifecycle._print_next_steps"
    ), patch(
        "ticket_system.commands.lifecycle._auto_handoff_if_needed"
    ), patch(
        "ticket_system.commands.lifecycle._handle_ana_spawned_confirmation",
        return_value=None,
    ), patch(
        "ticket_system.commands.lifecycle._handle_pending_children_block",
        return_value=None,
    ), patch(
        "ticket_system.commands.lifecycle._post_complete_cascade",
        side_effect=fake_cascade,
    ), patch(
        "ticket_system.commands.lifecycle._auto_stage_git_add",
        side_effect=fake_git_add,
    ):
        result = lifecycle.complete(ticket["id"], no_stage=no_stage)

    return result, captured_calls


class TestCompleteAutoStage:
    def test_complete_auto_stages_ticket_and_worklog(self, capsys):
        ticket = _build_ticket()
        result, calls = _run_complete(ticket=ticket)

        assert result == 0
        # 應有一筆 git add 呼叫
        add_calls = [c for c in calls if c[:2] == ["git", "add"]]
        assert len(add_calls) == 1, f"expected 1 git add call, got {calls}"
        staged = add_calls[0][2:]
        assert any("0.18.0-W17-998.md" in p for p in staged), staged
        assert any("worklog" in p for p in staged), staged

    def test_complete_cascade_stages_children(self, capsys):
        ticket = _build_ticket(children=["0.18.0-W17-998.1"])
        result, calls = _run_complete(
            ticket=ticket,
            cascade_unblocked=["0.18.0-W17-998.1"],
        )

        assert result == 0
        add_calls = [c for c in calls if c[:2] == ["git", "add"]]
        assert len(add_calls) == 1
        staged = add_calls[0][2:]
        assert any("0.18.0-W17-998.1.md" in p for p in staged), staged

    def test_no_stage_flag_skips_staging(self, capsys):
        ticket = _build_ticket()
        result, calls = _run_complete(ticket=ticket, no_stage=True)

        assert result == 0
        add_calls = [c for c in calls if c[:2] == ["git", "add"]]
        assert len(add_calls) == 0, f"--no-stage should skip git add, got {calls}"

    def test_stdout_prints_commit_command(self, capsys):
        ticket = _build_ticket(ticket_id="0.18.0-W17-997")
        result, _ = _run_complete(ticket=ticket)
        captured = capsys.readouterr()

        assert result == 0
        assert "chore(0.18.0-W17-997): metadata sync" in captured.out

    def test_auto_stage_only_passes_known_paths(self, capsys):
        """git add 參數須為精確路徑，不包含 './' 或 '-A'"""
        ticket = _build_ticket()
        _, calls = _run_complete(ticket=ticket)

        add_calls = [c for c in calls if c[:2] == ["git", "add"]]
        assert add_calls
        staged = add_calls[0][2:]
        # 禁止寬範圍參數
        for arg in staged:
            assert arg not in (".", "./", "-A", "--all"), (
                f"auto-stage must use precise paths, got {staged}"
            )
        # 所有 staged 路徑都應是 .md 結尾
        for arg in staged:
            assert arg.endswith(".md"), f"unexpected staged path: {arg}"
