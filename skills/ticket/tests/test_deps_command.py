"""
ticket track deps 命令測試（0.18.0-W15-004）

涵蓋情境：
1. 純衍生關係：A spawns B, B spawns C → 遞迴展開
2. 混合：有 spawned + source
3. 無關係：無 spawned 無 source → 輸出「無」
4. 循環引用防護：A spawns B, B spawns A → 偵測 CYCLE
"""

from unittest.mock import Mock, patch

from ticket_system.commands.track_query import execute_deps


def _make_ticket(tid, spawned=None, source=None, status="pending", title="T", ttype="IMP"):
    return {
        "id": tid,
        "title": title,
        "type": ttype,
        "status": status,
        "spawned_tickets": spawned or [],
        "source_ticket": source,
    }


class TestDepsCommand:

    def test_deps_recursive_spawned_expansion(self, capsys):
        """A spawns B, B spawns C → 遞迴展開兩層"""
        args = Mock()
        args.ticket_id = "0.18.0-W1-001"

        tickets = {
            "0.18.0-W1-001": _make_ticket("0.18.0-W1-001", spawned=["0.18.0-W1-002"]),
            "0.18.0-W1-002": _make_ticket("0.18.0-W1-002", spawned=["0.18.0-W1-003"]),
            "0.18.0-W1-003": _make_ticket("0.18.0-W1-003"),
        }

        def fake_load_and_validate(version, ticket_id, auto_print_error=True):
            t = tickets.get(ticket_id)
            return (t, None) if t else (None, "not_found")

        def fake_load(version, ticket_id):
            return tickets.get(ticket_id)

        with patch(
            "ticket_system.commands.track_query.load_and_validate_ticket",
            side_effect=fake_load_and_validate,
        ), patch(
            "ticket_system.commands.track_query.load_ticket",
            side_effect=fake_load,
        ):
            result = execute_deps(args, "0.18.0")

        assert result == 0
        out = capsys.readouterr().out
        assert "0.18.0-W1-001" in out
        assert "0.18.0-W1-002" in out
        assert "0.18.0-W1-003" in out
        assert "Spawned Tickets (1)" in out

    def test_deps_mixed_spawned_and_source(self, capsys):
        """混合：有 spawned_tickets 也有 source_ticket"""
        args = Mock()
        args.ticket_id = "0.18.0-W1-010"

        tickets = {
            "0.18.0-W1-010": _make_ticket(
                "0.18.0-W1-010",
                spawned=["0.18.0-W1-011"],
                source="0.18.0-W1-000",
            ),
            "0.18.0-W1-011": _make_ticket("0.18.0-W1-011"),
            "0.18.0-W1-000": _make_ticket("0.18.0-W1-000", ttype="ANA", status="completed"),
        }

        def fake_load_and_validate(version, ticket_id, auto_print_error=True):
            t = tickets.get(ticket_id)
            return (t, None) if t else (None, "not_found")

        with patch(
            "ticket_system.commands.track_query.load_and_validate_ticket",
            side_effect=fake_load_and_validate,
        ), patch(
            "ticket_system.commands.track_query.load_ticket",
            side_effect=lambda v, tid: tickets.get(tid),
        ):
            result = execute_deps(args, "0.18.0")

        assert result == 0
        out = capsys.readouterr().out
        assert "0.18.0-W1-011" in out
        assert "0.18.0-W1-000" in out
        assert "Source Ticket" in out
        assert "（無）" not in out.split("Source Ticket")[1][:50]

    def test_deps_no_relations(self, capsys):
        """無 spawned 無 source → 兩處皆顯示「（無）」"""
        args = Mock()
        args.ticket_id = "0.18.0-W1-020"

        tickets = {
            "0.18.0-W1-020": _make_ticket("0.18.0-W1-020"),
        }

        def fake_load_and_validate(version, ticket_id, auto_print_error=True):
            t = tickets.get(ticket_id)
            return (t, None) if t else (None, "not_found")

        with patch(
            "ticket_system.commands.track_query.load_and_validate_ticket",
            side_effect=fake_load_and_validate,
        ), patch(
            "ticket_system.commands.track_query.load_ticket",
            side_effect=lambda v, tid: tickets.get(tid),
        ):
            result = execute_deps(args, "0.18.0")

        assert result == 0
        out = capsys.readouterr().out
        assert out.count("（無）") >= 2
        assert "Spawned Tickets (0)" in out

    def test_deps_cycle_detection(self, capsys):
        """循環引用：A spawns B, B spawns A → 偵測 CYCLE DETECTED"""
        args = Mock()
        args.ticket_id = "0.18.0-W1-030"

        tickets = {
            "0.18.0-W1-030": _make_ticket("0.18.0-W1-030", spawned=["0.18.0-W1-031"]),
            "0.18.0-W1-031": _make_ticket("0.18.0-W1-031", spawned=["0.18.0-W1-030"]),
        }

        def fake_load_and_validate(version, ticket_id, auto_print_error=True):
            t = tickets.get(ticket_id)
            return (t, None) if t else (None, "not_found")

        with patch(
            "ticket_system.commands.track_query.load_and_validate_ticket",
            side_effect=fake_load_and_validate,
        ), patch(
            "ticket_system.commands.track_query.load_ticket",
            side_effect=lambda v, tid: tickets.get(tid),
        ):
            result = execute_deps(args, "0.18.0")

        assert result == 0
        out = capsys.readouterr().out
        assert "CYCLE DETECTED" in out

    def test_deps_ticket_not_found(self):
        """目標 Ticket 不存在 → 返回 1"""
        args = Mock()
        args.ticket_id = "0.18.0-W1-999"

        with patch(
            "ticket_system.commands.track_query.load_and_validate_ticket",
            return_value=(None, "not_found"),
        ):
            result = execute_deps(args, "0.18.0")

        assert result == 1
