"""
ticket complete 自動隔離索引提交測試

沿革：W11-035 原採「自動 git add + stdout 建議裸 commit」（方案 D），留
staged 狀態於共用 index 等人工裸 commit；同儕 commit 8db456783 把共用
index 中過期 index 快照寫進 HEAD 的事故顯示，留 staged 狀態本身就是入口。
改為 CLI 自身以 commit_files_isolated（GIT_INDEX_FILE 隔離 + 提交前自檢）
直接完成提交，不留任何 staged 殘留於共用 index。

驗證情境：
1. 正常 complete：ticket md + worklog md 交由 commit_files_isolated 提交
2. cascade complete：unblocked children 正確落盤，但不進入提交清單
3. blockedBy 反向解鎖的 siblings 正確落盤，但不進入提交清單
4. --no-stage flag：跳過自動提交
5. stdout 含 commit SHA（成功時），不再印出「建議裸 commit」指令
6. 不誤觸提交範圍外的 WIP 檔案（僅提交已知 modified 路徑）
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
    commit_result=None,
):
    """共用 patch 結構，回傳 (result, captured_commit_calls)。

    commit_result: 若傳入，覆寫 commit_files_isolated 的回傳值（預設為
        committed + 固定 SHA）。
    reverse_unblock_tickets: 額外併入 list_tickets 回傳值的 ticket dict
        清單，供真實 _reverse_unblock_blockedby（未 mock）掃描 blockedBy
        反向解鎖（siblings 測試用）。
    captured_saves: 若傳入 list，save_ticket 每次呼叫的 {id, status}
        會被記錄進去，供驗證「落盤仍發生」。
    """
    from ticket_system.commands.lifecycle import TicketLifecycle

    lifecycle = TicketLifecycle("0.18.0")

    captured_calls = []

    default_commit_result = {
        "status": "committed",
        "commit_sha": "abc123def4567890",
        "error": None,
    }

    def fake_commit_files_isolated(paths, message, cwd=None):
        captured_calls.append(
            {"paths": list(paths), "message": message, "cwd": cwd}
        )
        return commit_result or default_commit_result

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
        "ticket_system.commands.lifecycle.commit_files_isolated",
        side_effect=fake_commit_files_isolated,
    ):
        result = lifecycle.complete(ticket["id"], no_stage=no_stage)

    return result, captured_calls


class TestCompleteAutoStage:
    def test_complete_commits_ticket_and_worklog(self, capsys):
        ticket = _build_ticket()
        result, calls = _run_complete(ticket=ticket)

        assert result == 0
        assert len(calls) == 1, f"expected 1 commit_files_isolated call, got {calls}"
        committed = calls[0]["paths"]
        assert any("0.18.0-W17-998.md" in p for p in committed), committed
        assert any("worklog" in p for p in committed), committed
        # W4-026：cwd 錨定為 modified_paths[0]（票面 md）所在目錄
        assert calls[0]["cwd"] == "/tmp", calls[0]

    def test_complete_cascade_does_not_commit_children(self, capsys):
        """children 解鎖仍落盤（save_ticket 被呼叫），但不進入提交清單。"""
        captured_saves = []
        ticket = _build_ticket(children=["0.18.0-W17-998.1"])
        result, calls = _run_complete(
            ticket=ticket,
            cascade_unblocked=["0.18.0-W17-998.1"],
            captured_saves=captured_saves,
        )

        assert result == 0
        assert len(calls) == 1
        committed = calls[0]["paths"]
        assert not any("0.18.0-W17-998.1.md" in p for p in committed), committed
        # cascade fake 不經 save_ticket（本測試用 fake_cascade 直接模擬解鎖，
        # 落盤驗證見 test_complete_reverse_unblock_does_not_commit_siblings
        # 的真實 _reverse_unblock_blockedby 路徑）

    def test_complete_reverse_unblock_does_not_commit_siblings(self, capsys):
        """blockedBy 反向解鎖的兄弟 Ticket 正確落盤，但不進入提交清單。"""
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
        # 但不進入提交清單
        assert len(calls) == 1
        committed = calls[0]["paths"]
        assert not any(sibling_id in p for p in committed), committed

    def test_no_stage_flag_skips_commit(self, capsys):
        ticket = _build_ticket()
        result, calls = _run_complete(ticket=ticket, no_stage=True)

        assert result == 0
        assert len(calls) == 0, f"--no-stage should skip commit, got {calls}"

    def test_stdout_prints_commit_sha_on_success(self, capsys):
        ticket = _build_ticket(ticket_id="0.18.0-W17-997")
        result, calls = _run_complete(ticket=ticket)
        captured = capsys.readouterr()

        assert result == 0
        assert "abc123de" in captured.out

    def test_stdout_silent_on_empty_status(self, capsys):
        """工作區內容與 HEAD 相同（empty 短路）時不印出提交相關訊息。"""
        ticket = _build_ticket(ticket_id="0.18.0-W17-995")
        result, calls = _run_complete(
            ticket=ticket,
            commit_result={"status": "empty", "commit_sha": None, "error": None},
        )
        captured = capsys.readouterr()

        assert result == 0
        assert len(calls) == 1
        assert "Auto-commit" not in captured.out
        assert "chore(" not in captured.out

    def test_stderr_warns_on_failed_status_not_stdout(self, capsys):
        """提交失敗時警告寫 stderr，不寫 stdout，且不中斷 complete。"""
        ticket = _build_ticket(ticket_id="0.18.0-W17-991")
        result, calls = _run_complete(
            ticket=ticket,
            commit_result={
                "status": "failed",
                "commit_sha": None,
                "error": "提交範圍自我驗證失敗",
            },
        )
        captured = capsys.readouterr()

        assert result == 0
        assert len(calls) == 1
        assert "提交範圍自我驗證失敗" in captured.err
        assert "提交範圍自我驗證失敗" not in captured.out

    def test_no_pathspec_bare_commit_suggestion_printed(self, capsys):
        """改造後不再印出「建議裸 commit」指令——提交已由 CLI 自身完成，
        不留 staged 狀態給人工操作。"""
        ticket = _build_ticket(ticket_id="0.18.0-W17-996")
        result, calls = _run_complete(ticket=ticket)
        captured = capsys.readouterr()

        assert result == 0
        assert "git commit -m" not in captured.out
        assert "git diff --cached --name-only" not in captured.out

    def test_commit_message_contains_ticket_id(self, capsys):
        ticket = _build_ticket(ticket_id="0.18.0-W17-990")
        result, calls = _run_complete(ticket=ticket)

        assert result == 0
        assert len(calls) == 1
        assert "0.18.0-W17-990" in calls[0]["message"]

    def test_auto_commit_only_passes_known_paths(self, capsys):
        """commit_files_isolated 參數須為精確路徑，不包含 './' 或 '-A'"""
        ticket = _build_ticket()
        _, calls = _run_complete(ticket=ticket)

        assert calls
        committed = calls[0]["paths"]
        # 禁止寬範圍參數
        for arg in committed:
            assert arg not in (".", "./", "-A", "--all"), (
                f"auto-commit must use precise paths, got {committed}"
            )
        # 所有提交路徑都應是 .md 結尾
        for arg in committed:
            assert arg.endswith(".md"), f"unexpected committed path: {arg}"
