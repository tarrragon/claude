"""
W11-035 ticket complete 自動 git add + commit 提示測試

來源：W11-034 ANA 推薦方案 D（自動 add + stdout 提示）
0.2.1-W3-246 更新：auto-stage 範圍收斂為本票 md + worklog index 兩類，
children / siblings 路徑改為「落盤但不 stage」，見 0.2.1-W3-238 ANA。

驗證情境：
1. 正常 complete：ticket md + worklog md 被 git add
2. cascade complete：unblocked children 正確落盤，但不進入 git add（0.2.1-W3-246）
3. blockedBy 反向解鎖的 siblings 正確落盤，但不進入 git add（0.2.1-W3-246）
4. --no-stage flag：跳過自動 staging
5. stdout 含建議 commit 指令 `chore(<id>): metadata sync`
6. 不誤觸 git add 範圍外的 WIP 檔案（僅 add 已知 modified 路徑）
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
    reverse_unblock_tickets=None,
    captured_saves=None,
):
    """共用 patch 結構，回傳 (result, captured_subprocess_calls)。

    reverse_unblock_tickets: 額外併入 list_tickets 回傳值的 ticket dict
        清單，供真實 _reverse_unblock_blockedby（未 mock）掃描 blockedBy
        反向解鎖（0.2.1-W3-246 siblings 測試用）。
    captured_saves: 若傳入 list，save_ticket 每次呼叫的 {id, status}
        會被記錄進去，供驗證「落盤仍發生」（0.2.1-W3-246）。
    """
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

    def fake_save(t, path):
        if captured_saves is not None:
            captured_saves.append({"id": t.get("id"), "status": t.get("status")})

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
        "ticket_system.commands.lifecycle.validate_self_check_subsection",
        return_value=(True, None),
    ), patch(
        "ticket_system.commands.lifecycle.save_ticket",
        side_effect=fake_save,
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
        return_value=(
            [{"id": cid} for cid in (cascade_unblocked or [])]
            + (reverse_unblock_tickets or [])
        ),
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

    def test_complete_cascade_does_not_stage_children(self, capsys):
        """0.2.1-W3-246：children 解鎖仍落盤（save_ticket 被呼叫），但不進入 staging。"""
        captured_saves = []
        ticket = _build_ticket(children=["0.18.0-W17-998.1"])
        result, calls = _run_complete(
            ticket=ticket,
            cascade_unblocked=["0.18.0-W17-998.1"],
            captured_saves=captured_saves,
        )

        assert result == 0
        add_calls = [c for c in calls if c[:2] == ["git", "add"]]
        assert len(add_calls) == 1
        staged = add_calls[0][2:]
        assert not any("0.18.0-W17-998.1.md" in p for p in staged), staged
        # cascade fake 不經 save_ticket（本測試用 fake_cascade 直接模擬解鎖，
        # 落盤驗證見 test_complete_reverse_unblock_does_not_stage_siblings
        # 的真實 _reverse_unblock_blockedby 路徑）

    def test_complete_reverse_unblock_does_not_stage_siblings(self, capsys):
        """0.2.1-W3-246：blockedBy 反向解鎖的兄弟 Ticket 正確落盤，但不進入 staging。"""
        parent_id = "0.18.0-W17-994"
        sibling_id = "0.18.0-W17-993"
        ticket = _build_ticket(ticket_id=parent_id)
        # ticket_map 需含已完成的 parent 自身，供 is_fully_unblocked 判定通過
        completed_parent_snapshot = {"id": parent_id, "status": "completed"}
        sibling = {
            "id": sibling_id,
            "status": "blocked",
            "blockedBy": [parent_id],
            "title": "sibling blocked by parent",
        }
        captured_saves = []

        result, calls = _run_complete(
            ticket=ticket,
            reverse_unblock_tickets=[completed_parent_snapshot, sibling],
            captured_saves=captured_saves,
        )

        assert result == 0
        # 落盤仍發生：save_ticket 被呼叫且 sibling 狀態已改為 pending
        sibling_saves = [s for s in captured_saves if s["id"] == sibling_id]
        assert len(sibling_saves) == 1, captured_saves
        assert sibling_saves[0]["status"] == "pending", captured_saves
        # 但不進入 staging
        add_calls = [c for c in calls if c[:2] == ["git", "add"]]
        assert len(add_calls) == 1
        staged = add_calls[0][2:]
        assert not any(sibling_id in p for p in staged), staged

    def test_no_stage_flag_skips_staging(self, capsys):
        ticket = _build_ticket()
        result, calls = _run_complete(ticket=ticket, no_stage=True)

        assert result == 0
        add_calls = [c for c in calls if c[:2] == ["git", "add"]]
        assert len(add_calls) == 0, f"--no-stage should skip git add, got {calls}"

    def test_stdout_prints_commit_command(self, capsys):
        ticket = _build_ticket(ticket_id="0.18.0-W17-997")
        result, calls = _run_complete(ticket=ticket)
        captured = capsys.readouterr()

        assert result == 0
        assert "chore(0.18.0-W17-997): metadata sync" in captured.out

    def test_commit_suggestion_is_path_limited_and_matches_staged_range(self, capsys):
        """0.2.1-W3-246：建議 commit 指令需 path-limited，路徑與實際 staged 範圍一致。"""
        ticket = _build_ticket(ticket_id="0.18.0-W17-996")
        result, calls = _run_complete(ticket=ticket)
        captured = capsys.readouterr()

        assert result == 0
        add_calls = [c for c in calls if c[:2] == ["git", "add"]]
        assert len(add_calls) == 1
        staged = add_calls[0][2:]

        assert "git commit -m" in captured.out
        # 建議指令必須帶 `--` path-limited 標記
        assert " -- " in captured.out
        # 每個實際 staged 路徑都須出現在建議指令中
        for path in staged:
            assert path in captured.out, (path, captured.out)

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
