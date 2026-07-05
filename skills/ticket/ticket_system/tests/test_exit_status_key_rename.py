"""Exit Status body key 重命名 status -> exit_status 的雙 key 相容測試（1.5.0-W5-005.10）。

覆蓋三處消費端對「新 key（exit_status）」與「舊 key（status，歷史票零回填）」
的相容行為：

- handoff._extract_exit_status_for_handoff
- track_runqueue._get_exit_status_tag
- track_runqueue._compute_readiness（透過 exit_status_obj 的 status 分支）
"""

from __future__ import annotations

from ticket_system.commands import track_runqueue
from ticket_system.commands.handoff import _extract_exit_status_for_handoff


def _make_ticket_with_body(body: str) -> dict:
    return {"id": "test-ticket", "_body": body}


def _exit_status_section(yaml_text: str) -> str:
    return (
        "## Exit Status\n\n"
        "```yaml\n"
        f"{yaml_text}\n"
        "```\n"
    )


class TestHandoffExtractExitStatusDualKey:
    """_extract_exit_status_for_handoff 新舊 key 相容。"""

    def test_new_key_exit_status_recognized(self):
        body = _exit_status_section("exit_status: success\nreason: ok")
        ticket = _make_ticket_with_body(body)

        result = _extract_exit_status_for_handoff(ticket)

        assert result is not None
        assert result.get("exit_status") == "success"

    def test_old_key_status_fallback(self):
        body = _exit_status_section("status: needs_context\nreason: legacy")
        ticket = _make_ticket_with_body(body)

        result = _extract_exit_status_for_handoff(ticket)

        assert result is not None
        assert result.get("status") == "needs_context"

    def test_neither_key_present_returns_none(self):
        body = _exit_status_section("reason: no status key at all")
        ticket = _make_ticket_with_body(body)

        result = _extract_exit_status_for_handoff(ticket)

        assert result is None


class TestTrackRunqueueGetExitStatusTagDualKey:
    """track_runqueue._get_exit_status_tag 新舊 key 相容。"""

    def test_new_key_exit_status(self):
        handoff_info = {"exit_status": {"exit_status": "blocked"}}

        tag = track_runqueue._get_exit_status_tag(handoff_info)

        assert tag == "blocked"

    def test_old_key_status_fallback(self):
        handoff_info = {"exit_status": {"status": "failed"}}

        tag = track_runqueue._get_exit_status_tag(handoff_info)

        assert tag == "failed"

    def test_neither_key_present_returns_none(self):
        handoff_info = {"exit_status": {"reason": "no key"}}

        tag = track_runqueue._get_exit_status_tag(handoff_info)

        assert tag is None


class TestTrackRunqueueComputeReadinessDualKey:
    """track_runqueue._compute_readiness 透過 exit_status_obj 的 status 分支相容新舊 key。"""

    def test_new_key_exit_status_success(self):
        ticket = {"id": "t1"}
        handoff_info = {"t1": {"exit_status": {"exit_status": "success"}}}

        readiness = track_runqueue._compute_readiness(ticket, handoff_info)

        assert readiness == track_runqueue.READINESS_READY

    def test_old_key_status_success(self):
        ticket = {"id": "t2"}
        handoff_info = {"t2": {"exit_status": {"status": "success"}}}

        readiness = track_runqueue._compute_readiness(ticket, handoff_info)

        assert readiness == track_runqueue.READINESS_READY
