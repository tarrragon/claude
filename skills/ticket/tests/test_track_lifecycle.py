"""
track_lifecycle 模組測試

測試生命週期相關的 Ticket 操作：claim, complete, release
"""

from types import SimpleNamespace
from typing import Dict, Any, List, Tuple, Optional
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path

import pytest

# 注意：這些是預期的未來模組導入
# 目前在紅燈階段，這些模組尚未建立
from ticket_system.commands.lifecycle import (
    execute_claim,
    execute_complete,
    execute_release,
    execute_close,
)


class TestClaim:
    """認領 Ticket 相關的測試"""

    def test_claim_pending_ticket_success(self):
        """
        Given: 存在一個 pending 狀態的 Ticket
        When: 執行 claim 操作
        Then: Ticket 狀態應更改為 in_progress，並返回 0
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"

        with patch('ticket_system.commands.lifecycle.load_and_validate_ticket') as mock_load:
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "status": "pending",
                "title": "Test Ticket",
                "_path": "/test/path",
            }
            mock_load.return_value = (mock_ticket, None)

            with patch('ticket_system.commands.lifecycle.save_ticket') as mock_save:
                with patch('ticket_system.commands.lifecycle.validate_claimable_status') as mock_validate:
                    mock_validate.return_value = (True, "")
                    result = execute_claim(args, "0.31.0")

                    assert result == 0
                    mock_save.assert_called_once()
                    saved_ticket = mock_save.call_args[0][0]
                    assert saved_ticket["status"] == "in_progress"

    def test_claim_already_claimed_ticket_failure(self):
        """
        Given: 存在一個已被認領的 Ticket (in_progress 狀態)
        When: 執行 claim 操作
        Then: 應返回錯誤代碼，不更改狀態
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"

        with patch('ticket_system.commands.lifecycle.load_ticket') as mock_load:
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "status": "in_progress",
                "title": "Already Claimed",
            }
            mock_load.return_value = mock_ticket

            with patch('ticket_system.commands.lifecycle.validate_claimable_status') as mock_validate:
                mock_validate.return_value = (False, "Already claimed")
                result = execute_claim(args, "0.31.0")

                assert result != 0

    def test_claim_nonexistent_ticket_failure(self):
        """
        Given: Ticket ID 不存在
        When: 執行 claim 操作
        Then: 應返回錯誤代碼 1
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-999"
        args.version = "0.31.0"

        with patch('ticket_system.commands.lifecycle.load_ticket') as mock_load:
            mock_load.return_value = None

            result = execute_claim(args, "0.31.0")

            assert result == 1

    def test_claim_blocked_ticket_failure(self):
        """
        Given: 存在一個被阻塞的 Ticket (blocked 狀態)
        When: 執行 claim 操作
        Then: 應返回錯誤代碼，提示被阻塞
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"

        with patch('ticket_system.commands.lifecycle.load_ticket') as mock_load:
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "status": "blocked",
                "title": "Blocked Ticket",
            }
            mock_load.return_value = mock_ticket

            with patch('ticket_system.commands.lifecycle.validate_claimable_status') as mock_validate:
                mock_validate.return_value = (False, "Ticket is blocked")
                result = execute_claim(args, "0.31.0")

                assert result != 0


class TestComplete:
    """完成 Ticket 相關的測試"""

    def test_complete_in_progress_ticket_success(self):
        """
        Given: 存在一個進行中的 Ticket，且所有驗收條件已完成
        When: 執行 complete 操作
        Then: Ticket 狀態應更改為 completed，並返回 0
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"

        with patch('ticket_system.commands.lifecycle.load_and_validate_ticket') as mock_load:
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "status": "in_progress",
                "title": "Test Ticket",
                "acceptance_criteria": [
                    {"text": "Condition 1", "completed": True},
                    {"text": "Condition 2", "completed": True},
                ],
                "_path": "/test/path",
            }
            mock_load.return_value = (mock_ticket, None)

            with patch('ticket_system.commands.lifecycle.save_ticket') as mock_save:
                with patch('ticket_system.commands.lifecycle.validate_completable_status') as mock_validate:
                    with patch('ticket_system.commands.lifecycle.validate_acceptance_criteria') as mock_criteria:
                        mock_validate.return_value = (True, "", False)
                        mock_criteria.return_value = (True, [])
                        result = execute_complete(args, "0.31.0")

                        assert result == 0
                        mock_save.assert_called()

    def test_complete_ticket_with_incomplete_criteria_failure(self):
        """
        Given: 存在一個進行中的 Ticket，但有驗收條件未完成
        When: 執行 complete 操作
        Then: 應返回錯誤代碼，列出未完成項目
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"

        with patch('ticket_system.commands.lifecycle.load_ticket') as mock_load:
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "status": "in_progress",
                "title": "Test Ticket",
                "acceptance_criteria": [
                    {"text": "Condition 1", "completed": True},
                    {"text": "Condition 2", "completed": False},
                ],
            }
            mock_load.return_value = mock_ticket

            with patch('ticket_system.commands.lifecycle.validate_completable_status') as mock_validate:
                with patch('ticket_system.commands.lifecycle.validate_acceptance_criteria') as mock_criteria:
                    mock_validate.return_value = (True, "", False)
                    mock_criteria.return_value = (False, ["Condition 2"])
                    result = execute_complete(args, "0.31.0")

                    assert result != 0

    def test_complete_already_completed_ticket_failure(self):
        """
        Given: Ticket 已經是 completed 狀態
        When: 執行 complete 操作
        Then: 應返回錯誤代碼，提示已完成
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"

        with patch('ticket_system.commands.lifecycle.load_and_validate_ticket') as mock_load:
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "status": "completed",
                "title": "Already Completed",
                "completed_at": "2026-01-30T10:50:00",
            }
            mock_load.return_value = (mock_ticket, None)

            with patch('ticket_system.commands.lifecycle.validate_completable_status') as mock_validate:
                mock_validate.return_value = (False, "Already completed", True)
                result = execute_complete(args, "0.31.0")

                assert result == 0

    def test_complete_pending_ticket_failure(self):
        """
        Given: Ticket 仍在 pending 狀態（未被認領）
        When: 執行 complete 操作
        Then: 應返回錯誤代碼，提示需先認領
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"

        with patch('ticket_system.commands.lifecycle.load_ticket') as mock_load:
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "status": "pending",
                "title": "Not Claimed",
            }
            mock_load.return_value = mock_ticket

            with patch('ticket_system.commands.lifecycle.validate_completable_status') as mock_validate:
                mock_validate.return_value = (False, "Not claimed yet", False)
                result = execute_complete(args, "0.31.0")

                assert result != 0


class TestRelease:
    """釋放 Ticket 相關的測試"""

    def test_release_in_progress_ticket_success(self):
        """
        Given: 存在一個進行中的 Ticket
        When: 執行 release 操作
        Then: Ticket 狀態應更改為 blocked，並返回 0
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"

        with patch('ticket_system.lib.ticket_ops.load_ticket') as mock_load:
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "status": "in_progress",
                "title": "Test Ticket",
                "_path": "/test/path",
            }
            mock_load.return_value = mock_ticket

            with patch('ticket_system.commands.lifecycle.save_ticket') as mock_save:
                result = execute_release(args, "0.31.0")

                assert result == 0
                mock_save.assert_called_once()
                saved_ticket = mock_save.call_args[0][0]
                assert saved_ticket["status"] == "blocked"

    def test_release_pending_ticket_failure(self):
        """
        Given: Ticket 仍在 pending 狀態
        When: 執行 release 操作
        Then: 應返回錯誤代碼，提示 Ticket 未被認領
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"

        with patch('ticket_system.commands.lifecycle.load_ticket') as mock_load:
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "status": "pending",
                "title": "Not Claimed",
            }
            mock_load.return_value = mock_ticket

            result = execute_release(args, "0.31.0")

            assert result != 0

    def test_release_completed_ticket_failure(self):
        """
        Given: Ticket 已是 completed 狀態
        When: 執行 release 操作
        Then: 應返回錯誤代碼，無法釋放已完成的 Ticket
        """
        args = Mock()
        args.ticket_id = "0.31.0-W4-001"
        args.version = "0.31.0"

        with patch('ticket_system.commands.lifecycle.load_ticket') as mock_load:
            mock_ticket = {
                "id": "0.31.0-W4-001",
                "status": "completed",
                "title": "Completed Ticket",
            }
            mock_load.return_value = mock_ticket

            result = execute_release(args, "0.31.0")

            assert result != 0


# ============================================================================
# TestCompleteCascadeChildren：父 complete → 子自動解鎖 + 警告（W5-019）
# ============================================================================


def _save_fails_for(ticket_ids):
    """產生 save_ticket 的 side_effect：指定 id 的 save 拋 IOError，其餘成功。"""
    def _side_effect(ticket_dict, *args, **kwargs):
        if ticket_dict.get("id") in ticket_ids:
            raise IOError(f"mock save failure for {ticket_dict['id']}")
        return None
    return _side_effect


@pytest.fixture
def make_parent_child_tickets():
    """
    建立父子 Ticket dict 的 factory。

    Returns:
        callable(parent_id, children_spec, parent_extra=None, extras=None)
        - children_spec: list of (child_id, status, blocked_by)
        - extras: 額外的 ticket dict 清單（如 X、GC1 等非 children 的票）
        Returns (parent_dict, children_list, all_tickets_list)
    """
    def _make(parent_id, children_spec, parent_extra=None, extras=None, parent_title=None):
        parent_extra = parent_extra or {}
        extras = extras or []

        children_ids = [spec[0] for spec in children_spec]
        children_list = []
        for spec in children_spec:
            child_id = spec[0]
            status = spec[1]
            blocked_by = spec[2] if len(spec) > 2 else []
            child = {
                "id": child_id,
                "status": status,
                "blockedBy": list(blocked_by),
                "parent_id": parent_id,
                "title": f"子任務 {child_id}",
            }
            children_list.append(child)

        parent = {
            "id": parent_id,
            "status": "in_progress",
            "title": parent_title or f"父任務 {parent_id}",
            "children": list(children_ids),
            "acceptance": [
                {"text": "ac1", "completed": True},
            ],
        }
        parent.update(parent_extra)

        all_tickets = [parent] + children_list + list(extras)
        return parent, children_list, all_tickets

    return _make


@pytest.fixture
def complete_env(monkeypatch):
    """封裝 complete() 執行所需的 mock bundle。"""
    env = SimpleNamespace()

    env.save_ticket = MagicMock(return_value=None)
    env.list_tickets = MagicMock(return_value=[])
    env.validate_completable_status = MagicMock(return_value=(True, "", False))
    env.validate_acceptance_criteria = MagicMock(return_value=(True, []))
    env.append_worklog_progress = MagicMock(return_value=None)
    env.auto_handoff = MagicMock(return_value=None)
    env.validate_execution_log = MagicMock(return_value=(True, []))
    env.load_ticket = MagicMock()

    env._parent = None
    env._tickets = []

    def set_tickets(parent, all_tickets):
        env._parent = parent
        env._tickets = all_tickets
        env.load_ticket.side_effect = lambda version, tid: next(
            (t for t in all_tickets if t.get("id") == tid), None
        )
        env.list_tickets.return_value = all_tickets

    env.set_tickets = set_tickets

    monkeypatch.setattr(
        "ticket_system.lib.ticket_ops.load_ticket",
        env.load_ticket,
    )
    monkeypatch.setattr(
        "ticket_system.commands.lifecycle.list_tickets",
        env.list_tickets,
    )
    monkeypatch.setattr(
        "ticket_system.commands.lifecycle.save_ticket",
        env.save_ticket,
    )
    monkeypatch.setattr(
        "ticket_system.commands.lifecycle.validate_completable_status",
        env.validate_completable_status,
    )
    monkeypatch.setattr(
        "ticket_system.commands.lifecycle.validate_acceptance_criteria",
        env.validate_acceptance_criteria,
    )
    monkeypatch.setattr(
        "ticket_system.commands.lifecycle.validate_execution_log",
        env.validate_execution_log,
    )
    monkeypatch.setattr(
        "ticket_system.commands.lifecycle.append_worklog_progress",
        env.append_worklog_progress,
    )
    monkeypatch.setattr(
        "ticket_system.commands.lifecycle._auto_handoff_if_needed",
        env.auto_handoff,
    )

    return env


def _saved_statuses_for(mock_save, ticket_id):
    """從 save_ticket.call_args_list 中擷取指定 id 的所有被儲存狀態。"""
    statuses = []
    for call in mock_save.call_args_list:
        args, kwargs = call
        if args:
            td = args[0]
            if isinstance(td, dict) and td.get("id") == ticket_id:
                statuses.append(td.get("status"))
    return statuses


class TestCompleteCascadeChildren:
    """父 complete 自動解鎖子 + children 警告的測試（W5-019）"""

    def test_cascade_unlocks_single_blocked_child(
        self, make_parent_child_tickets, complete_env, capsys
    ):
        """TC-A1：正常 cascade — 唯一 blocked 子自動解鎖。"""
        parent, children, all_tickets = make_parent_child_tickets(
            "P0", [("C1", "blocked", ["P0"])]
        )
        complete_env.set_tickets(parent, all_tickets)

        args = Mock()
        args.ticket_id = "P0"
        result = execute_complete(args, "0.18.0")

        out = capsys.readouterr().out
        assert result == 0
        c1_statuses = _saved_statuses_for(complete_env.save_ticket, "C1")
        assert "pending" in c1_statuses, f"C1 應被 save 為 pending，實際: {c1_statuses}"
        assert "[Cascade]" in out
        assert "C1" in out
        assert "[Warning] 父 Ticket 完成時尚有未完成的子 Ticket" not in out

    def test_warning_when_pending_and_in_progress_children(
        self, make_parent_child_tickets, complete_env, capsys
    ):
        """TC-A2：警告但不阻止 — 有 pending / in_progress children。"""
        parent, children, all_tickets = make_parent_child_tickets(
            "P0",
            [
                ("C1", "pending", []),
                ("C2", "in_progress", []),
            ],
        )
        complete_env.set_tickets(parent, all_tickets)

        args = Mock()
        args.ticket_id = "P0"
        result = execute_complete(args, "0.18.0")

        out = capsys.readouterr().out
        assert result == 0
        assert _saved_statuses_for(complete_env.save_ticket, "C1") == []
        assert _saved_statuses_for(complete_env.save_ticket, "C2") == []
        assert "[Warning] 父 Ticket 完成時尚有未完成的子 Ticket" in out
        assert "C1 [pending]" in out
        assert "C2 [in_progress]" in out
        assert "[Cascade]" not in out

    def test_preserves_blocked_when_other_deps_incomplete(
        self, make_parent_child_tickets, complete_env, capsys
    ):
        """TC-A3：其他依賴保留 blocked — blockedBy 尚有未完成項。"""
        x_ticket = {
            "id": "X",
            "status": "in_progress",
            "title": "外部 X",
            "blockedBy": [],
        }
        parent, children, all_tickets = make_parent_child_tickets(
            "P0",
            [("C1", "blocked", ["P0", "X"])],
            extras=[x_ticket],
        )
        complete_env.set_tickets(parent, all_tickets)

        args = Mock()
        args.ticket_id = "P0"
        result = execute_complete(args, "0.18.0")

        out = capsys.readouterr().out
        assert result == 0
        assert "pending" not in _saved_statuses_for(complete_env.save_ticket, "C1")
        assert "[Warning] 父 Ticket 完成時尚有未完成的子 Ticket" in out
        assert "C1 [blocked]" in out
        assert "[Cascade]" not in out

    def test_grandchild_not_cascaded(
        self, make_parent_child_tickets, complete_env, capsys
    ):
        """TC-B1：孫子不遞迴（§6.1）。"""
        gc1 = {
            "id": "GC1",
            "status": "blocked",
            "blockedBy": ["C1"],
            "parent_id": "C1",
            "title": "孫子 GC1",
        }
        parent, children, all_tickets = make_parent_child_tickets(
            "P0",
            [("C1", "blocked", ["P0"])],
            extras=[gc1],
        )
        children[0]["children"] = ["GC1"]
        complete_env.set_tickets(parent, all_tickets)

        args = Mock()
        args.ticket_id = "P0"
        result = execute_complete(args, "0.18.0")

        out = capsys.readouterr().out
        assert result == 0
        assert "pending" in _saved_statuses_for(complete_env.save_ticket, "C1")
        assert _saved_statuses_for(complete_env.save_ticket, "GC1") == []
        assert "GC1" not in out

    def test_orphan_parent_id_not_scanned(
        self, make_parent_child_tickets, complete_env, capsys
    ):
        """TC-B2：parent_id 單向權威，不反向掃描（§6.2）。"""
        c_orphan = {
            "id": "C_orphan",
            "status": "blocked",
            "blockedBy": ["P0"],
            "parent_id": "P0",
            "title": "孤兒 child",
        }
        parent, children, all_tickets = make_parent_child_tickets(
            "P0", [], extras=[c_orphan]
        )
        complete_env.set_tickets(parent, all_tickets)

        args = Mock()
        args.ticket_id = "P0"
        result = execute_complete(args, "0.18.0")

        out = capsys.readouterr().out
        assert result == 0
        assert _saved_statuses_for(complete_env.save_ticket, "C_orphan") == []
        assert "[Cascade]" not in out
        assert "[Warning] 父 Ticket 完成時尚有未完成的子 Ticket" not in out

    def test_empty_children(
        self, make_parent_child_tickets, complete_env, capsys
    ):
        """TC-B3：children 為空集（§6.3）。"""
        parent, children, all_tickets = make_parent_child_tickets("P0", [])
        complete_env.set_tickets(parent, all_tickets)

        args = Mock()
        args.ticket_id = "P0"
        result = execute_complete(args, "0.18.0")

        out = capsys.readouterr().out
        assert result == 0
        assert "[Cascade]" not in out
        assert "[Warning] 父 Ticket 完成時尚有未完成的子 Ticket" not in out

    def test_all_children_completed(
        self, make_parent_child_tickets, complete_env, capsys
    ):
        """TC-B4：全 completed/closed 的 children（§6.4）。"""
        parent, children, all_tickets = make_parent_child_tickets(
            "P0",
            [
                ("C1", "completed", []),
                ("C2", "closed", []),
            ],
        )
        complete_env.set_tickets(parent, all_tickets)

        args = Mock()
        args.ticket_id = "P0"
        result = execute_complete(args, "0.18.0")

        out = capsys.readouterr().out
        assert result == 0
        assert _saved_statuses_for(complete_env.save_ticket, "C1") == []
        assert _saved_statuses_for(complete_env.save_ticket, "C2") == []
        assert "[Cascade]" not in out
        assert "[Warning] 父 Ticket 完成時尚有未完成的子 Ticket" not in out

    def test_missing_child_id_is_skipped(
        self, make_parent_child_tickets, complete_env, capsys
    ):
        """TC-B5：找不到 child_id → 跳過（§6.5）。"""
        parent, children, all_tickets = make_parent_child_tickets(
            "P0", [("C1", "blocked", ["P0"])]
        )
        parent["children"].append("C_ghost")
        complete_env.set_tickets(parent, all_tickets)

        args = Mock()
        args.ticket_id = "P0"
        result = execute_complete(args, "0.18.0")

        out = capsys.readouterr().out
        assert result == 0
        assert "pending" in _saved_statuses_for(complete_env.save_ticket, "C1")
        assert "C_ghost" not in out

    def test_closed_child_treated_as_completed(
        self, make_parent_child_tickets, complete_env, capsys
    ):
        """TC-B6：closed 視同 completed（§6.6）。"""
        parent, children, all_tickets = make_parent_child_tickets(
            "P0", [("C1", "closed", [])]
        )
        complete_env.set_tickets(parent, all_tickets)

        args = Mock()
        args.ticket_id = "P0"
        result = execute_complete(args, "0.18.0")

        out = capsys.readouterr().out
        assert result == 0
        assert "[Cascade]" not in out
        assert "[Warning] 父 Ticket 完成時尚有未完成的子 Ticket" not in out

    def test_cascade_save_failure_non_fail_fast(
        self, make_parent_child_tickets, complete_env, capsys
    ):
        """TC-B7：cascade save 失敗，non-fail-fast（§6.7）。"""
        parent, children, all_tickets = make_parent_child_tickets(
            "P0",
            [
                ("C1", "blocked", ["P0"]),
                ("C2", "blocked", ["P0"]),
            ],
        )
        complete_env.set_tickets(parent, all_tickets)

        complete_env.save_ticket.side_effect = _save_fails_for({"C1"})

        args = Mock()
        args.ticket_id = "P0"
        result = execute_complete(args, "0.18.0")

        out = capsys.readouterr().out
        assert result == 0
        assert "C1" in out
        assert "pending" in _saved_statuses_for(complete_env.save_ticket, "C2")

    @pytest.mark.parametrize(
        "case_id,blocked_by,extra_status_map,expect_unblock",
        [
            ("single_parent", ["P0"], {}, True),
            ("other_completed", ["P0", "X"], {"X": "completed"}, True),
            ("other_pending", ["P0", "X"], {"X": "pending"}, False),
            ("empty_blockedby", [], {}, True),
        ],
    )
    def test_blockedby_and_semantics(
        self,
        make_parent_child_tickets,
        complete_env,
        capsys,
        case_id,
        blocked_by,
        extra_status_map,
        expect_unblock,
    ):
        """TC-B8：blockedBy AND 語義（§6.8）— 四子案例。"""
        extras = []
        for tid, status in extra_status_map.items():
            extras.append({
                "id": tid,
                "status": status,
                "blockedBy": [],
                "title": f"外部 {tid}",
            })

        parent, children, all_tickets = make_parent_child_tickets(
            "P0",
            [("C1", "blocked", blocked_by)],
            extras=extras,
        )
        complete_env.set_tickets(parent, all_tickets)

        args = Mock()
        args.ticket_id = "P0"
        result = execute_complete(args, "0.18.0")

        out = capsys.readouterr().out
        assert result == 0
        c1_statuses = _saved_statuses_for(complete_env.save_ticket, "C1")

        if expect_unblock:
            assert "pending" in c1_statuses, f"[{case_id}] C1 應被解鎖"
            assert "[Cascade]" in out, f"[{case_id}] 應有 Cascade 區塊"
        else:
            assert "pending" not in c1_statuses, f"[{case_id}] C1 應保留 blocked"
            assert "C1 [blocked]" in out, f"[{case_id}] C1 應列於 Warning"

    def test_cascade_message_format(
        self, make_parent_child_tickets, complete_env, capsys
    ):
        """TC-C1：Cascade 訊息格式（§3.3）。"""
        parent, children, all_tickets = make_parent_child_tickets(
            "P0", [("C1", "blocked", ["P0"])]
        )
        children[0]["title"] = "子任務 C1"
        complete_env.set_tickets(parent, all_tickets)

        args = Mock()
        args.ticket_id = "P0"
        execute_complete(args, "0.18.0")

        out = capsys.readouterr().out
        assert "[Cascade] 以下子 Ticket 已自動解鎖（blocked → pending）：" in out
        assert "   - C1: 子任務 C1" in out

    def test_warning_message_format(
        self, make_parent_child_tickets, complete_env, capsys
    ):
        """TC-C2：Warning 訊息格式（§3.4）。"""
        parent, children, all_tickets = make_parent_child_tickets(
            "P0",
            [
                ("C1", "pending", []),
                ("C2", "in_progress", []),
            ],
        )
        children[0]["title"] = "子任務 C1"
        children[1]["title"] = "子任務 C2"
        complete_env.set_tickets(parent, all_tickets)

        args = Mock()
        args.ticket_id = "P0"
        execute_complete(args, "0.18.0")

        out = capsys.readouterr().out
        assert "[Warning] 父 Ticket 完成時尚有未完成的子 Ticket：" in out
        assert "   - C1 [pending]: 子任務 C1" in out
        assert "   - C2 [in_progress]: 子任務 C2" in out
        assert "父 complete 不阻止" in out


# ============================================================================
# TestCompleteCascadeSaveOrderContract：cascade 呼叫順序契約（W11-002.5）
# ANA 0.18.0-W5-022 發現：Mock-based 測試共用 in-memory dict，可能矇混
# 「parent 必須先落盤再 cascade」的順序契約。本區塊補強：
#   1. TC-D1（順序斷言）：save_ticket(parent) 先於 list_tickets() 被呼叫
#   2. TC-D2（真實往返）：tmp_path 寫實檔案，驗證 _post_complete_cascade
#      透過 list_tickets fallback 讀到 disk 上 completed 的 parent，並真把
#      child 落盤為 pending
# 防護目標：若有人重構順序（例如把 save_ticket(parent) 移到 cascade 之後），
# 既有 Mock 測試仍會綠燈，但本區塊會抓出 regression。
# ============================================================================


class TestCompleteCascadeSaveOrderContract:
    """W11-002.5：cascade 呼叫順序契約測試。"""

    def test_save_ticket_parent_called_before_list_tickets(
        self, make_parent_child_tickets, complete_env, capsys
    ):
        """TC-D1：execute_complete 必須在呼叫 list_tickets 前 save_ticket(parent)。

        Why：cascade 路徑（含 fallback）依賴 disk 上 parent 為 completed，
        若順序顛倒，list_tickets 會讀到舊 parent status，導致 child
        在 _can_cascade_unblock 判定時看到 parent 仍為 in_progress 而不解鎖。

        實作：用一個共享的 call_log 記錄 save_ticket / list_tickets 的呼叫順序，
        斷言「parent save」必先於「list_tickets」第一次呼叫出現。
        """
        parent, children, all_tickets = make_parent_child_tickets(
            "P0", [("C1", "blocked", ["P0"])]
        )
        complete_env.set_tickets(parent, all_tickets)

        call_log: List[Tuple[str, str]] = []

        original_save = complete_env.save_ticket.side_effect
        original_list = complete_env.list_tickets.return_value

        def _save_spy(ticket_dict, *args, **kwargs):
            call_log.append(("save", ticket_dict.get("id", "?")))
            if callable(original_save):
                return original_save(ticket_dict, *args, **kwargs)
            return None

        def _list_spy(*args, **kwargs):
            call_log.append(("list", "*"))
            return original_list

        complete_env.save_ticket.side_effect = _save_spy
        complete_env.list_tickets.side_effect = _list_spy

        args = Mock()
        args.ticket_id = "P0"
        result = execute_complete(args, "0.18.0")

        assert result == 0

        # 找出 parent save 與第一次 list_tickets 在 call_log 中的索引
        parent_save_idx = next(
            (i for i, (k, tid) in enumerate(call_log) if k == "save" and tid == "P0"),
            None,
        )
        first_list_idx = next(
            (i for i, (k, _) in enumerate(call_log) if k == "list"), None
        )

        assert parent_save_idx is not None, (
            f"parent (P0) 應被 save_ticket，實際 call_log: {call_log}"
        )
        assert first_list_idx is not None, (
            f"應呼叫 list_tickets（cascade 載入 ticket_map），實際 call_log: {call_log}"
        )
        assert parent_save_idx < first_list_idx, (
            f"save_ticket(parent) 必須先於 list_tickets()，"
            f"實際順序：parent_save@{parent_save_idx}, first_list@{first_list_idx}, "
            f"call_log={call_log}"
        )


class TestCascadeRealDiskRoundtrip:
    """W11-002.5：cascade 真實 save→load 往返契約測試（避免 Mock 矇混）。"""

    @staticmethod
    def _write_real_ticket(
        tickets_dir: Path,
        ticket_id: str,
        status: str,
        children: List[str] = None,
        blocked_by: List[str] = None,
        parent_id: str = None,
        title: str = None,
    ) -> Path:
        """於 tickets_dir 寫入符合 parser.load_ticket 慣例的最小 Ticket 檔案。"""
        import yaml as _yaml

        fm: Dict[str, Any] = {
            "id": ticket_id,
            "title": title or f"Ticket {ticket_id}",
            "status": status,
            "type": "IMP",
            "version": "0.99.0",
            "wave": 1,
            "priority": "P2",
            "children": list(children or []),
            "blockedBy": list(blocked_by or []),
            "parent_id": parent_id,
            "acceptance": [{"text": "ac1", "completed": True}],
        }
        ticket_path = tickets_dir / f"{ticket_id}.md"
        content = (
            "---\n"
            + _yaml.dump(fm, allow_unicode=True, sort_keys=False)
            + "---\n\nbody\n"
        )
        ticket_path.write_text(content, encoding="utf-8")
        return ticket_path

    def test_post_complete_cascade_reads_completed_parent_from_disk(
        self, temp_project_dir, monkeypatch, capsys
    ):
        """TC-D2：tmp_path 真實 save→load 往返。

        Given：parent 已落盤為 completed，child 落盤為 blocked、blockedBy=[parent]
        When：呼叫 _post_complete_cascade（不傳 ticket_map → 走 list_tickets fallback）
        Then：
          - 函式從 disk 讀到 parent status=completed
          - child 被解鎖（status: blocked → pending）並真實 save 回 disk
          - 重新 load_ticket(child) 從 disk 讀到 status=pending（真往返驗證）

        防護：若有人改順序讓 parent 還沒落盤就跑 cascade，list_tickets 會讀到
        舊 status（in_progress），_can_cascade_unblock 會判定不可解鎖，本測試會抓到。
        """
        # 隔離至 tmp_path，避免污染真實 repo
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(temp_project_dir))

        # 建立版本 0.99.0 的 tickets 目錄（使用 flat 結構，避免階層 fallback）
        version = "0.99.0"
        tickets_dir = (
            temp_project_dir / "docs" / "work-logs" / f"v{version}" / "tickets"
        )
        tickets_dir.mkdir(parents=True, exist_ok=True)

        parent_id = "0.99.0-W1-100"
        child_id = "0.99.0-W1-101"

        # 落盤 parent（已 completed）+ child（blocked + blockedBy=[parent]）
        parent_path = self._write_real_ticket(
            tickets_dir,
            parent_id,
            status="completed",
            children=[child_id],
            title="父任務 P",
        )
        child_path = self._write_real_ticket(
            tickets_dir,
            child_id,
            status="blocked",
            blocked_by=[parent_id],
            parent_id=parent_id,
            title="子任務 C",
        )

        # 清快取，確保 list_tickets / load_ticket 走真實 disk
        from ticket_system.lib import parser as _parser
        from ticket_system.lib import ticket_loader as _ticket_loader

        _parser._ticket_cache.clear()
        _ticket_loader._chain_index_cache.clear()

        # 從 disk load parent 作為 _post_complete_cascade 入參
        from ticket_system.lib.parser import load_ticket as _load_ticket
        from ticket_system.commands.lifecycle import _post_complete_cascade

        parent_dict = _load_ticket(version, parent_id)
        assert parent_dict is not None and parent_dict.get("status") == "completed"

        # 不傳 ticket_map → 走 list_tickets fallback（驗證 fallback 路徑也正確）
        _post_complete_cascade(parent_dict, version, ticket_map=None)

        out = capsys.readouterr().out
        assert "[Cascade]" in out, f"應觸發 cascade unblock，stdout: {out!r}"
        assert child_id in out

        # 真實往返驗證：清快取後從 disk 重新 load child，必為 pending
        _parser._ticket_cache.clear()
        _ticket_loader._chain_index_cache.clear()
        reloaded_child = _load_ticket(version, child_id)
        assert reloaded_child is not None
        assert reloaded_child.get("status") == "pending", (
            f"child 應已被解鎖並落盤為 pending，實際 disk 上為 "
            f"{reloaded_child.get('status')!r}"
        )

    def test_post_complete_cascade_skips_when_parent_still_in_progress_on_disk(
        self, temp_project_dir, monkeypatch, capsys
    ):
        """TC-D3（負向驗證）：parent 在 disk 上仍 in_progress 時，cascade 不應解鎖 child。

        這是 TC-D2 的對照組：刻意違反「parent 先落盤」契約，驗證 cascade 確實
        從 disk 讀 parent status 並做正確判定，而非依賴呼叫者傳入的 in-memory dict。

        構造：parent dict 在記憶體中標 completed（模擬 caller 改了 status 但沒 save），
        但 disk 上 parent 仍是 in_progress。cascade 走 list_tickets fallback 會讀到
        disk 上的舊 status，child 應保留 blocked。
        """
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(temp_project_dir))

        version = "0.99.0"
        tickets_dir = (
            temp_project_dir / "docs" / "work-logs" / f"v{version}" / "tickets"
        )
        tickets_dir.mkdir(parents=True, exist_ok=True)

        parent_id = "0.99.0-W1-200"
        child_id = "0.99.0-W1-201"

        # 故意：disk 上 parent 仍 in_progress（未落盤 completed）
        self._write_real_ticket(
            tickets_dir,
            parent_id,
            status="in_progress",
            children=[child_id],
            title="父任務 P",
        )
        self._write_real_ticket(
            tickets_dir,
            child_id,
            status="blocked",
            blocked_by=[parent_id],
            parent_id=parent_id,
            title="子任務 C",
        )

        from ticket_system.lib import parser as _parser
        from ticket_system.lib import ticket_loader as _ticket_loader

        _parser._ticket_cache.clear()
        _ticket_loader._chain_index_cache.clear()

        # 構造一個 in-memory parent_ticket：status=completed（模擬 caller 改了但沒 save）
        in_memory_parent = {
            "id": parent_id,
            "status": "completed",
            "title": "父任務 P",
            "children": [child_id],
        }

        from ticket_system.commands.lifecycle import _post_complete_cascade

        # 走 list_tickets fallback，會從 disk 讀到 in_progress parent
        _post_complete_cascade(in_memory_parent, version, ticket_map=None)

        # 重新 load child，應仍為 blocked
        _parser._ticket_cache.clear()
        _ticket_loader._chain_index_cache.clear()
        from ticket_system.lib.parser import load_ticket as _load_ticket

        reloaded_child = _load_ticket(version, child_id)
        assert reloaded_child is not None
        assert reloaded_child.get("status") == "blocked", (
            f"parent 在 disk 上仍 in_progress 時，child 不應被解鎖；"
            f"實際 status={reloaded_child.get('status')!r}。"
            f"若此斷言失敗，表示 cascade 依賴 in-memory parent dict 而非 disk 真實狀態，"
            f"違反呼叫契約（W11-002.5 / ANA W5-022）。"
        )


# ============================================================================
# TestCompleteSpawnedBlocking：ANA spawned 非 terminal blocking confirmation
# （W12-005 / PC-075 Phase 2 — 方案 K）
# ============================================================================


def _make_ana_ticket(spawned_ids, ticket_type="ANA", ticket_id="0.18.0-W99-001"):
    """建立 ANA 測試 Ticket dict（預設 AC 全勾、完整執行日誌）。

    Body 內含「Problem Analysis」和「Solution」章節，以便通過 validate_execution_log。
    """
    return {
        "id": ticket_id,
        "type": ticket_type,
        "status": "in_progress",
        "title": "Test ANA Ticket",
        "acceptance": ["[x] AC1"],
        "spawned_tickets": list(spawned_ids),
        "_path": "/test/path",
        "_body": "## Problem Analysis\n內容\n## Solution\n內容",
    }


@pytest.fixture
def spawned_complete_env(monkeypatch):
    """封裝 ANA spawned 檢查 complete() 執行所需的 mock bundle。

    設計：
    - 透過 monkeypatch 置換 lifecycle 內所有 I/O 依賴
    - spawned_status_map: {"A": "pending", "B": "completed", ...}
      經由 list_tickets mock 餵入，模擬各 spawned ticket 的 status
    - 不 mock _cascade_unblock_children（無 children 時不觸發）
    """
    env = SimpleNamespace()

    env.save_ticket = MagicMock(return_value=None)
    env.validate_completable_status = MagicMock(return_value=(True, "", False))
    env.validate_acceptance_criteria = MagicMock(return_value=(True, []))
    env.append_worklog_progress = MagicMock(return_value=None)
    env.auto_handoff = MagicMock(return_value=None)
    env.validate_execution_log = MagicMock(return_value=(True, []))
    env.list_tickets = MagicMock(return_value=[])
    env.load_and_validate = MagicMock()

    env._ticket = None
    env._status_map = {}

    def set_scenario(ticket, spawned_status_map):
        env._ticket = ticket
        env._status_map = spawned_status_map
        env.load_and_validate.return_value = (ticket, None)

        # list_tickets 回傳含 main ticket + spawned tickets 的清單
        all_tickets = [ticket]
        for sid, status in spawned_status_map.items():
            all_tickets.append({
                "id": sid,
                "status": status,
                "title": f"Spawned {sid}",
            })
        env.list_tickets.return_value = all_tickets

    env.set_scenario = set_scenario

    monkeypatch.setattr(
        "ticket_system.commands.lifecycle.load_and_validate_ticket",
        env.load_and_validate,
    )
    monkeypatch.setattr(
        "ticket_system.commands.lifecycle.save_ticket",
        env.save_ticket,
    )
    monkeypatch.setattr(
        "ticket_system.commands.lifecycle.validate_completable_status",
        env.validate_completable_status,
    )
    monkeypatch.setattr(
        "ticket_system.commands.lifecycle.validate_acceptance_criteria",
        env.validate_acceptance_criteria,
    )
    monkeypatch.setattr(
        "ticket_system.commands.lifecycle.validate_execution_log",
        env.validate_execution_log,
    )
    monkeypatch.setattr(
        "ticket_system.commands.lifecycle.list_tickets",
        env.list_tickets,
    )
    monkeypatch.setattr(
        "ticket_system.commands.lifecycle.append_worklog_progress",
        env.append_worklog_progress,
    )
    monkeypatch.setattr(
        "ticket_system.commands.lifecycle._auto_handoff_if_needed",
        env.auto_handoff,
    )

    return env


class TestCompleteSpawnedBlocking:
    """ANA type + spawned 非 terminal blocking confirmation 測試（W12-005）"""

    def test_ana_all_terminal_spawned_completes_normally(
        self, spawned_complete_env, capsys
    ):
        """Test 1: ANA + spawned 全 terminal → 正常 complete（不觸發 prompt）。"""
        ticket = _make_ana_ticket(["A", "B"])
        spawned_complete_env.set_scenario(
            ticket, {"A": "completed", "B": "closed"}
        )

        args = Mock()
        args.ticket_id = "0.18.0-W99-001"
        args.yes_spawned = False

        with patch("ticket_system.commands.lifecycle.sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            with patch("builtins.input") as mock_input:
                result = execute_complete(args, "0.18.0")

        assert result == 0
        mock_input.assert_not_called()
        # 驗證 main ticket 被 save 為 completed
        saved_statuses = _saved_statuses_for(
            spawned_complete_env.save_ticket, "0.18.0-W99-001"
        )
        assert "completed" in saved_statuses

        err = capsys.readouterr().err
        assert "spawned 非 terminal" not in err

    def test_ana_non_terminal_spawned_interactive_yes_completes(
        self, spawned_complete_env, capsys
    ):
        """Test 2: ANA + spawned 含非 terminal + 互動環境 + 用戶輸入 y → complete。"""
        ticket = _make_ana_ticket(["A", "B", "C"])
        spawned_complete_env.set_scenario(
            ticket,
            {"A": "pending", "B": "in_progress", "C": "completed"},
        )

        args = Mock()
        args.ticket_id = "0.18.0-W99-001"
        args.yes_spawned = False

        with patch("ticket_system.commands.lifecycle.sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            with patch("builtins.input", return_value="y") as mock_input:
                result = execute_complete(args, "0.18.0")

        captured = capsys.readouterr()
        err = captured.err

        assert result == 0
        # 驗證 stderr 含 WARNING header 和清單
        assert "ANA Ticket 0.18.0-W99-001 有 2 個 spawned 非 terminal" in err
        assert "A: pending" in err
        assert "B: in_progress" in err
        # C 是 completed 不應出現
        assert "C: completed" not in err
        # 驗證 prompt 被呼叫
        mock_input.assert_called_once()
        prompt_arg = mock_input.call_args[0][0]
        assert "確定 complete" in prompt_arg
        assert "(y/N)" in prompt_arg
        # 驗證 main ticket 被 save 為 completed
        saved_statuses = _saved_statuses_for(
            spawned_complete_env.save_ticket, "0.18.0-W99-001"
        )
        assert "completed" in saved_statuses

    def test_ana_non_terminal_spawned_interactive_no_cancels(
        self, spawned_complete_env, capsys
    ):
        """Test 3: ANA + spawned 含非 terminal + 互動環境 + 用戶輸入 N → 取消。"""
        ticket = _make_ana_ticket(["A", "B"])
        spawned_complete_env.set_scenario(
            ticket, {"A": "pending", "B": "in_progress"}
        )

        args = Mock()
        args.ticket_id = "0.18.0-W99-001"
        args.yes_spawned = False

        with patch("ticket_system.commands.lifecycle.sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            with patch("builtins.input", return_value="N"):
                result = execute_complete(args, "0.18.0")

        err = capsys.readouterr().err

        assert result == 2
        assert "已取消 complete 操作" in err
        # 驗證 main ticket 未被 save 為 completed
        saved_statuses = _saved_statuses_for(
            spawned_complete_env.save_ticket, "0.18.0-W99-001"
        )
        assert "completed" not in saved_statuses

    def test_ana_non_terminal_spawned_non_interactive_no_flag_exits_2(
        self, spawned_complete_env, capsys
    ):
        """Test 4: ANA + spawned 含非 terminal + 非互動 + 無 flag → exit 2 + 引導。"""
        ticket = _make_ana_ticket(["A"])
        spawned_complete_env.set_scenario(ticket, {"A": "pending"})

        args = Mock()
        args.ticket_id = "0.18.0-W99-001"
        args.yes_spawned = False

        with patch("ticket_system.commands.lifecycle.sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            with patch("builtins.input") as mock_input:
                result = execute_complete(args, "0.18.0")

        err = capsys.readouterr().err

        assert result == 2
        assert "非互動環境需 --yes-spawned flag" in err
        assert "用法: ticket track complete 0.18.0-W99-001 --yes-spawned" in err
        mock_input.assert_not_called()
        # 驗證 main ticket 未被 save 為 completed
        saved_statuses = _saved_statuses_for(
            spawned_complete_env.save_ticket, "0.18.0-W99-001"
        )
        assert "completed" not in saved_statuses

    def test_ana_non_terminal_spawned_non_interactive_with_flag_completes(
        self, spawned_complete_env, capsys
    ):
        """Test 5: ANA + spawned 含非 terminal + 非互動 + --yes-spawned → complete。"""
        ticket = _make_ana_ticket(["A"])
        spawned_complete_env.set_scenario(ticket, {"A": "pending"})

        args = Mock()
        args.ticket_id = "0.18.0-W99-001"
        args.yes_spawned = True

        with patch("ticket_system.commands.lifecycle.sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            with patch("builtins.input") as mock_input:
                result = execute_complete(args, "0.18.0")

        err = capsys.readouterr().err

        assert result == 0
        assert "flag 旁路" in err
        assert "A: pending" in err
        mock_input.assert_not_called()
        # 驗證 main ticket 被 save 為 completed
        saved_statuses = _saved_statuses_for(
            spawned_complete_env.save_ticket, "0.18.0-W99-001"
        )
        assert "completed" in saved_statuses

    def test_non_ana_type_skips_spawned_check(
        self, spawned_complete_env, capsys
    ):
        """Test 6: 非 ANA（IMP）+ spawned 含非 terminal → 忽略檢查、正常 complete。"""
        ticket = _make_ana_ticket(["A"], ticket_type="IMP")
        spawned_complete_env.set_scenario(ticket, {"A": "pending"})

        args = Mock()
        args.ticket_id = "0.18.0-W99-001"
        args.yes_spawned = False

        with patch("ticket_system.commands.lifecycle.sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            with patch("builtins.input") as mock_input:
                result = execute_complete(args, "0.18.0")

        err = capsys.readouterr().err

        assert result == 0
        assert "spawned 非 terminal" not in err
        mock_input.assert_not_called()
        saved_statuses = _saved_statuses_for(
            spawned_complete_env.save_ticket, "0.18.0-W99-001"
        )
        assert "completed" in saved_statuses

    def test_ana_empty_spawned_completes_normally(
        self, spawned_complete_env, capsys
    ):
        """Test 7（邊界）：ANA + spawned_tickets=[] → 正常 complete（不觸發 prompt）。"""
        ticket = _make_ana_ticket([])
        spawned_complete_env.set_scenario(ticket, {})

        args = Mock()
        args.ticket_id = "0.18.0-W99-001"
        args.yes_spawned = False

        with patch("ticket_system.commands.lifecycle.sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            with patch("builtins.input") as mock_input:
                result = execute_complete(args, "0.18.0")

        err = capsys.readouterr().err

        assert result == 0
        assert "spawned 非 terminal" not in err
        mock_input.assert_not_called()
        saved_statuses = _saved_statuses_for(
            spawned_complete_env.save_ticket, "0.18.0-W99-001"
        )
        assert "completed" in saved_statuses

    def test_ana_spawned_not_found_listed_as_non_terminal(
        self, spawned_complete_env, capsys
    ):
        """Test 8（邊界）：ANA + spawned 查無 ticket → 視為非 terminal（not_found）。"""
        ticket = _make_ana_ticket(["A", "GHOST"])
        # 只提供 A 的 status，GHOST 故意不加入 list_tickets
        spawned_complete_env.set_scenario(ticket, {"A": "completed"})
        # 手動重設 list_tickets：只含 main ticket + A（不含 GHOST）
        spawned_complete_env.list_tickets.return_value = [
            ticket,
            {"id": "A", "status": "completed", "title": "Spawned A"},
        ]

        args = Mock()
        args.ticket_id = "0.18.0-W99-001"
        args.yes_spawned = False

        with patch("ticket_system.commands.lifecycle.sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            with patch("builtins.input", return_value="y") as mock_input:
                result = execute_complete(args, "0.18.0")

        err = capsys.readouterr().err

        assert result == 0
        # GHOST 應以 not_found 列出
        assert "GHOST: not_found" in err
        assert "有 1 個 spawned 非 terminal" in err
        mock_input.assert_called_once()


# ============================================================================
# W15-027 / PC-090: close --reason 枚舉驗證測試
# ============================================================================


class TestCloseReasonEnum:
    """close command --reason 枚舉驗證（PC-090 C1/C4）"""

    def _make_args(self, **overrides):
        args = Mock()
        args.ticket_id = "0.18.0-W15-999"
        args.version = "0.18.0"
        args.resolved_by = "0.18.0-W15-998"
        args.reason = overrides.get("reason", "goal_achieved")
        args.reason_note = overrides.get("reason_note", "")
        args.retrospective = overrides.get("retrospective", False)
        return args

    def _mock_load_ticket(self, status="in_progress"):
        return {
            "id": "0.18.0-W15-999",
            "status": status,
            "title": "Test Ticket",
            "_path": "/test/path",
        }

    def test_close_accepts_all_six_legal_reason_codes(self):
        """
        Given: 六種合法 close_reason 枚舉值
        When: 執行 close 操作
        Then: 每一種都應通過枚舉驗證並成功關閉
        """
        legal_codes = [
            "goal_achieved",
            "requirement_vanished",
            "superseded_by",
            "not_executable_knowledge_captured",
            "duplicate",
            "cancelled_by_user",
        ]
        for code in legal_codes:
            args = self._make_args(reason=code)
            with patch("ticket_system.commands.lifecycle.load_and_validate_ticket") as mock_load, \
                 patch("ticket_system.commands.lifecycle.save_ticket") as mock_save, \
                 patch("ticket_system.commands.lifecycle.resolve_ticket_path", return_value="/p"):
                mock_load.return_value = (self._mock_load_ticket(), None)
                result = execute_close(args, "0.18.0")

                assert result == 0, f"reason={code} 應該成功"
                saved_ticket = mock_save.call_args[0][0]
                assert saved_ticket["close_reason"] == code
                assert saved_ticket["status"] == "closed"

    def test_close_rejects_invalid_reason_code(self):
        """
        Given: 非枚舉值的 reason
        When: 執行 close 操作
        Then: 應返回錯誤代碼 1，不儲存 ticket
        """
        args = self._make_args(reason="some_random_reason")
        with patch("ticket_system.commands.lifecycle.load_and_validate_ticket") as mock_load, \
             patch("ticket_system.commands.lifecycle.save_ticket") as mock_save:
            mock_load.return_value = (self._mock_load_ticket(), None)
            result = execute_close(args, "0.18.0")

            assert result == 1
            mock_save.assert_not_called()

    def test_close_rejects_empty_reason(self):
        """
        Given: 空字串 reason
        When: 執行 close 操作
        Then: 應返回錯誤代碼 1
        """
        args = self._make_args(reason="")
        with patch("ticket_system.commands.lifecycle.load_and_validate_ticket") as mock_load, \
             patch("ticket_system.commands.lifecycle.save_ticket") as mock_save:
            mock_load.return_value = (self._mock_load_ticket(), None)
            result = execute_close(args, "0.18.0")

            assert result == 1
            mock_save.assert_not_called()

    def test_close_rejects_unknown_without_retrospective_flag(self):
        """
        Given: reason='unknown' 但未加 --retrospective
        When: 執行 close 操作
        Then: 應拒絕（unknown 僅限 retrospective 模式）
        """
        args = self._make_args(reason="unknown", retrospective=False)
        with patch("ticket_system.commands.lifecycle.load_and_validate_ticket") as mock_load, \
             patch("ticket_system.commands.lifecycle.save_ticket") as mock_save:
            mock_load.return_value = (self._mock_load_ticket(), None)
            result = execute_close(args, "0.18.0")

            assert result == 1
            mock_save.assert_not_called()

    def test_close_accepts_unknown_with_retrospective_flag(self):
        """
        Given: reason='unknown' 且 --retrospective
        When: 執行 close 操作
        Then: 應通過驗證，並在 frontmatter 寫入 retrospective: true
        """
        args = self._make_args(reason="unknown", retrospective=True)
        with patch("ticket_system.commands.lifecycle.load_and_validate_ticket") as mock_load, \
             patch("ticket_system.commands.lifecycle.save_ticket") as mock_save, \
             patch("ticket_system.commands.lifecycle.resolve_ticket_path", return_value="/p"):
            mock_load.return_value = (self._mock_load_ticket(), None)
            result = execute_close(args, "0.18.0")

            assert result == 0
            saved_ticket = mock_save.call_args[0][0]
            assert saved_ticket["close_reason"] == "unknown"
            assert saved_ticket["retrospective"] is True

    def test_close_writes_frontmatter_close_reason_and_note(self):
        """
        Given: 合法 reason_code 和 reason_note
        When: 執行 close 操作
        Then: frontmatter 應寫入 close_reason（代碼）和 close_reason_note（補充）
        """
        args = self._make_args(
            reason="superseded_by",
            reason_note="被 W15-100 上游整合取代"
        )
        with patch("ticket_system.commands.lifecycle.load_and_validate_ticket") as mock_load, \
             patch("ticket_system.commands.lifecycle.save_ticket") as mock_save, \
             patch("ticket_system.commands.lifecycle.resolve_ticket_path", return_value="/p"):
            mock_load.return_value = (self._mock_load_ticket(), None)
            result = execute_close(args, "0.18.0")

            assert result == 0
            saved = mock_save.call_args[0][0]
            assert saved["close_reason"] == "superseded_by"
            assert saved["close_reason_note"] == "被 W15-100 上游整合取代"
            assert saved["closed_by"] == "0.18.0-W15-998"
            assert "closed_at" in saved

    def test_close_non_retrospective_does_not_write_retrospective_flag(self):
        """
        Given: 合法 reason 且未標 --retrospective
        When: 執行 close
        Then: frontmatter 不應寫入 retrospective
        """
        args = self._make_args(reason="goal_achieved", retrospective=False)
        with patch("ticket_system.commands.lifecycle.load_and_validate_ticket") as mock_load, \
             patch("ticket_system.commands.lifecycle.save_ticket") as mock_save, \
             patch("ticket_system.commands.lifecycle.resolve_ticket_path", return_value="/p"):
            mock_load.return_value = (self._mock_load_ticket(), None)
            result = execute_close(args, "0.18.0")

            assert result == 0
            saved = mock_save.call_args[0][0]
            assert "retrospective" not in saved

    def test_close_reason_constants_has_six_entries(self):
        """
        Given: CLOSE_REASONS 常數
        Then: 必為 PC-090 C1 六種枚舉
        """
        from ticket_system.constants import CLOSE_REASONS
        expected = {
            "goal_achieved",
            "requirement_vanished",
            "superseded_by",
            "not_executable_knowledge_captured",
            "duplicate",
            "cancelled_by_user",
        }
        assert set(CLOSE_REASONS) == expected
        assert len(CLOSE_REASONS) == 6
