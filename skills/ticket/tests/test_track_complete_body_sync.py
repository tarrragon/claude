"""
W17-016.4: complete 時同步 body Completion Info 欄位測試

驗證 sync_completion_body_fields 行為：
- Completion Time: (pending) → completed_at ISO
- Executing Agent placeholder → who.current
- Review Status: 保留現狀
- 非 placeholder 值不被覆蓋
"""

from ticket_system.commands.lifecycle import sync_completion_body_fields


TEMPLATE_BODY = """# Execution Log

## Completion Info

**Completion Time**: (pending)
**Executing Agent**: thyme-python-developer
**Review Status**: pending
"""


class TestSyncCompletionBodyFields:
    def test_replaces_completion_time_placeholder(self):
        result = sync_completion_body_fields(
            TEMPLATE_BODY,
            completed_at="2026-04-20T22:00:00",
            executing_agent="thyme-python-developer",
        )
        assert "**Completion Time**: 2026-04-20T22:00:00" in result
        assert "(pending)" not in result.split("Review Status")[0]

    def test_review_status_pending_preserved(self):
        """Review Status 無權威來源，保留原值。"""
        result = sync_completion_body_fields(
            TEMPLATE_BODY,
            completed_at="2026-04-20T22:00:00",
            executing_agent="thyme-python-developer",
        )
        assert "**Review Status**: pending" in result

    def test_empty_body_returns_empty(self):
        assert sync_completion_body_fields("", "2026-04-20T22:00:00", "agent") == ""

    def test_no_placeholder_body_unchanged(self):
        body = "# No completion info section here\n"
        result = sync_completion_body_fields(body, "2026-04-20T22:00:00", "agent")
        assert result == body

    def test_already_filled_completion_time_not_overwritten(self):
        body = "**Completion Time**: 2025-01-01T00:00:00\n"
        result = sync_completion_body_fields(body, "2026-04-20T22:00:00", "agent")
        assert "2025-01-01T00:00:00" in result
        assert "2026-04-20T22:00:00" not in result

    def test_executing_agent_placeholder_filled(self):
        body = "**Executing Agent**: (pending)\n**Review Status**: pending\n"
        result = sync_completion_body_fields(body, "t", "thyme-python-developer")
        assert "**Executing Agent**: thyme-python-developer" in result

    def test_executing_agent_already_set_not_overwritten(self):
        body = "**Executing Agent**: basil-hook-architect\n"
        result = sync_completion_body_fields(body, "t", "thyme-python-developer")
        assert "basil-hook-architect" in result
        assert "thyme-python-developer" not in result


class TestCompleteIntegration:
    """驗證 complete 流程調用 sync_completion_body_fields。"""

    def test_complete_syncs_body(self):
        """end-to-end：呼叫 lifecycle.complete 後 _body 中 Completion Time 已更新。"""
        from unittest.mock import patch, Mock
        from ticket_system.commands.lifecycle import TicketLifecycle

        lifecycle = TicketLifecycle("0.18.0")
        ticket = {
            "id": "0.18.0-W17-999",
            "status": "in_progress",
            "title": "Test",
            "who": {"current": "thyme-python-developer"},
            "acceptance": [{"text": "x", "completed": True}],
            "_body": TEMPLATE_BODY,
            "_path": "/tmp/fake.md",
        }

        saved = {}

        def fake_save(t, p):
            saved["body"] = t.get("_body", "")
            saved["completed_at"] = t.get("completed_at")

        with patch("ticket_system.commands.lifecycle.load_and_validate_ticket",
                   return_value=(ticket, None)), \
             patch("ticket_system.commands.lifecycle.validate_completable_status",
                   return_value=(True, "", False)), \
             patch("ticket_system.commands.lifecycle.validate_acceptance_criteria",
                   return_value=(True, [])), \
             patch("ticket_system.commands.lifecycle.validate_execution_log",
                   return_value=(True, [])), \
             patch("ticket_system.commands.lifecycle.validate_execution_log_by_type",
                   return_value=(True, [])), \
             patch("ticket_system.commands.lifecycle.save_ticket", side_effect=fake_save), \
             patch("ticket_system.commands.lifecycle.resolve_ticket_path",
                   return_value="/tmp/fake.md"), \
             patch("ticket_system.commands.lifecycle.append_worklog_progress"), \
             patch("ticket_system.commands.lifecycle.list_tickets", return_value=[]), \
             patch("ticket_system.commands.lifecycle._analyze_next_steps",
                   return_value={}), \
             patch("ticket_system.commands.lifecycle._print_next_steps"), \
             patch("ticket_system.commands.lifecycle._auto_handoff_if_needed"), \
             patch("ticket_system.commands.lifecycle._handle_ana_spawned_confirmation",
                   return_value=None):
            result = lifecycle.complete("0.18.0-W17-999")

        assert result == 0
        assert saved["completed_at"] is not None
        assert "(pending)" not in saved["body"].split("Review Status")[0]
        assert saved["completed_at"] in saved["body"]
