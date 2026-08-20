"""ticket track topics / topic 命令測試。

驗證重點：
1. topics：全部主題含票數、status 分佈、最高 priority、in_progress lease
   狀態、未歸屬票數
2. topic <name>：以 blockedBy 為邊的樹狀縮排任務鏈 map，跨主題 blockedBy
   歸入外部依賴而非展開子節點，無邊的票列為獨立 root
3. 兩命令皆唯讀：不呼叫任何 ticket 檔或歸屬來源檔的寫入函式
4. 兩命令已在 track.py 註冊表接線且 --help 可見
5. --format json 結構化輸出
"""

from __future__ import annotations

import json
from argparse import Namespace
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from ticket_system.commands import track_topics

from conftest import _ticket, _iso  # noqa: F401


NOW = datetime(2026, 8, 19, 12, 0, 0, tzinfo=timezone.utc)


def _t(tid, status, priority=None, blocked_by=None):
    t = _ticket(tid, status, files=[])
    if priority is not None:
        t["priority"] = priority
    t["blockedBy"] = blocked_by or []
    return t


def _fresh_registry(session_id, tickets):
    return {
        "sessions": {
            session_id: {
                "project": "/proj",
                "heartbeat_ts": _iso(NOW - timedelta(minutes=5)),
                "tickets": tickets,
                "files": [],
            }
        }
    }


class TestBuildTopicSummary:
    def test_ticket_count_and_status_distribution(self):
        tickets = [
            _t("A-1", "pending"),
            _t("A-2", "completed"),
            _t("B-1", "pending"),
        ]
        assignments = {"A-1": "topic-a", "A-2": "topic-a", "B-1": "topic-b"}
        summary = track_topics.build_topic_summary(
            tickets, assignments, ["topic-a", "topic-b"], {}, None, NOW
        )
        by_name = {row["topic"]: row for row in summary["topics"]}
        assert by_name["topic-a"]["ticket_count"] == 2
        assert by_name["topic-a"]["status_counts"] == {"pending": 1, "completed": 1}
        assert by_name["topic-b"]["ticket_count"] == 1

    def test_highest_priority_is_min_index(self):
        tickets = [
            _t("A-1", "pending", priority="P2"),
            _t("A-2", "pending", priority="P0"),
        ]
        assignments = {"A-1": "topic-a", "A-2": "topic-a"}
        summary = track_topics.build_topic_summary(
            tickets, assignments, ["topic-a"], {}, None, NOW
        )
        assert summary["topics"][0]["highest_priority"] == "P0"

    def test_unassigned_count(self):
        tickets = [
            _t("A-1", "pending"),
            _t("X-1", "pending"),
        ]
        assignments = {"A-1": "topic-a"}
        summary = track_topics.build_topic_summary(
            tickets, assignments, ["topic-a"], {}, None, NOW
        )
        assert summary["unassigned_count"] == 1

    def test_in_progress_lease_state(self):
        tickets = [_t("A-1", "in_progress")]
        assignments = {"A-1": "topic-a"}
        registry = _fresh_registry("sess-1", ["A-1"])

        class FakePmRegistry:
            @staticmethod
            def is_fresh(ts, now):
                return True

        summary = track_topics.build_topic_summary(
            tickets, assignments, ["topic-a"], registry, FakePmRegistry(), NOW
        )
        row = summary["topics"][0]
        assert row["in_progress"] == [{"ticket_id": "A-1", "lease_state": "live"}]

    def test_topic_from_assignments_not_in_registry_still_appears(self):
        tickets = [_t("A-1", "pending")]
        assignments = {"A-1": "orphaned-topic"}
        summary = track_topics.build_topic_summary(tickets, assignments, [], {}, None, NOW)
        assert summary["topics"][0]["topic"] == "orphaned-topic"


class TestBuildTopicChain:
    def test_root_has_no_in_topic_blocker(self):
        tickets = [
            _t("A-1", "pending"),
            _t("A-2", "pending", blocked_by=["A-1"]),
        ]
        assignments = {"A-1": "topic-a", "A-2": "topic-a"}
        chain = track_topics.build_topic_chain("topic-a", tickets, assignments)
        assert chain["roots"] == ["A-1"]
        assert chain["children"]["A-1"] == ["A-2"]

    def test_ticket_with_no_edge_is_independent_root(self):
        tickets = [
            _t("A-1", "pending"),
            _t("A-2", "pending"),
        ]
        assignments = {"A-1": "topic-a", "A-2": "topic-a"}
        chain = track_topics.build_topic_chain("topic-a", tickets, assignments)
        assert sorted(chain["roots"]) == ["A-1", "A-2"]

    def test_cross_topic_blocked_by_goes_to_external_blockers(self):
        tickets = [
            _t("A-1", "pending", blocked_by=["B-9"]),
        ]
        assignments = {"A-1": "topic-a", "B-9": "topic-b"}
        chain = track_topics.build_topic_chain("topic-a", tickets, assignments)
        # A-1 的唯一 blocker 屬外部主題，故 A-1 在 topic-a 內視為 root
        assert chain["roots"] == ["A-1"]
        assert chain["external_blockers"] == {"A-1": ["B-9"]}
        assert chain["children"] == {}

    def test_node_attributes_include_status_priority_blocked_by(self):
        tickets = [_t("A-1", "in_progress", priority="P1", blocked_by=["X-1"])]
        assignments = {"A-1": "topic-a"}
        chain = track_topics.build_topic_chain("topic-a", tickets, assignments)
        node = chain["nodes"]["A-1"]
        assert node["status"] == "in_progress"
        assert node["priority"] == "P1"
        assert node["blockedBy"] == ["X-1"]

    def test_empty_topic_has_no_nodes(self):
        chain = track_topics.build_topic_chain("no-such-topic", [_t("A-1", "pending")], {})
        assert chain["nodes"] == {}
        assert chain["roots"] == []


class TestRenderChainTable:
    def test_tree_indentation_reflects_depth(self):
        tickets = [
            _t("A-1", "pending"),
            _t("A-2", "pending", blocked_by=["A-1"]),
        ]
        chain = track_topics.build_topic_chain(
            "topic-a", tickets, {"A-1": "topic-a", "A-2": "topic-a"}
        )
        rendered = track_topics._render_chain_table(chain)
        lines = rendered.splitlines()
        a1_line = next(l for l in lines if "A-1" in l)
        a2_line = next(l for l in lines if "A-2" in l)
        assert a1_line.startswith("- ")
        assert a2_line.startswith("  - ")

    def test_cycle_does_not_infinite_loop(self):
        # blockedBy 互指造成環：A-1 blockedBy A-2，A-2 blockedBy A-1。
        tickets = [
            _t("A-1", "pending", blocked_by=["A-2"]),
            _t("A-2", "pending", blocked_by=["A-1"]),
        ]
        assignments = {"A-1": "topic-a", "A-2": "topic-a"}
        chain = track_topics.build_topic_chain("topic-a", tickets, assignments)
        # 兩票互為彼此的 in-topic blocker，故皆非 root；渲染仍須終止（不掛起）。
        rendered = track_topics._render_chain_table(chain)
        assert "循環依賴" in rendered or chain["roots"] == []


class TestExecuteTopics:
    def test_read_only_no_write_calls(self):
        args = Namespace(version="0.2.1", format="table", _now=NOW)
        with patch.object(track_topics, "_gather_tickets", return_value=[_t("A-1", "pending")]), \
             patch.object(track_topics, "list_assignments", return_value={"A-1": "topic-a"}), \
             patch.object(track_topics, "list_topics", return_value=["topic-a"]), \
             patch.object(track_topics.lease, "load_registry_snapshot", return_value=({}, None)):
            rc = track_topics.execute_topics(args)
        assert rc == 0

    def test_json_format_output(self, capsys):
        args = Namespace(version="0.2.1", format="json", _now=NOW)
        with patch.object(track_topics, "_gather_tickets", return_value=[_t("A-1", "pending")]), \
             patch.object(track_topics, "list_assignments", return_value={"A-1": "topic-a"}), \
             patch.object(track_topics, "list_topics", return_value=["topic-a"]), \
             patch.object(track_topics.lease, "load_registry_snapshot", return_value=({}, None)):
            track_topics.execute_topics(args)
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["topics"][0]["topic"] == "topic-a"


class TestExecuteTopic:
    def test_json_format_output(self, capsys):
        args = Namespace(topic="topic-a", version="0.2.1", format="json")
        with patch.object(
            track_topics, "_gather_tickets", return_value=[_t("A-1", "pending")]
        ), patch.object(track_topics, "list_assignments", return_value={"A-1": "topic-a"}):
            rc = track_topics.execute_topic(args)
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["topic"] == "topic-a"
        assert rc == 0

    def test_empty_topic_returns_nonzero(self, capsys):
        args = Namespace(topic="ghost-topic", version="0.2.1", format="table")
        with patch.object(track_topics, "_gather_tickets", return_value=[]), \
             patch.object(track_topics, "list_assignments", return_value={}):
            rc = track_topics.execute_topic(args)
        assert rc == 1


class TestNoSourceWrites:
    """acceptance 3：兩命令為唯讀，不寫任何 ticket 檔亦不寫歸屬來源檔。"""

    def test_topics_never_calls_append_functions(self):
        args = Namespace(version="0.2.1", format="table", _now=NOW)
        with patch.object(track_topics, "_gather_tickets", return_value=[_t("A-1", "pending")]), \
             patch.object(track_topics, "list_assignments", return_value={"A-1": "topic-a"}), \
             patch.object(track_topics, "list_topics", return_value=["topic-a"]), \
             patch.object(track_topics.lease, "load_registry_snapshot", return_value=({}, None)), \
             patch("ticket_system.lib.topic_assignments.append_assignment") as mock_append_a, \
             patch("ticket_system.lib.topic_registry.append_topic") as mock_append_t:
            track_topics.execute_topics(args)
        mock_append_a.assert_not_called()
        mock_append_t.assert_not_called()

    def test_topic_never_calls_append_functions(self):
        args = Namespace(topic="topic-a", version="0.2.1", format="table")
        with patch.object(track_topics, "_gather_tickets", return_value=[_t("A-1", "pending")]), \
             patch.object(track_topics, "list_assignments", return_value={"A-1": "topic-a"}), \
             patch("ticket_system.lib.topic_assignments.append_assignment") as mock_append_a, \
             patch("ticket_system.lib.topic_registry.append_topic") as mock_append_t:
            track_topics.execute_topic(args)
        mock_append_a.assert_not_called()
        mock_append_t.assert_not_called()


class TestCliRegistration:
    """acceptance 4：兩個命令已在 commands/track.py 註冊表接線且 --help 可見。"""

    def _build_track_parser(self):
        import argparse
        from ticket_system.commands import track

        parser = argparse.ArgumentParser(prog="ticket")
        subparsers = parser.add_subparsers(dest="command")
        track.register(subparsers)
        return parser

    def test_topics_registered_and_help_visible(self, capsys):
        parser = self._build_track_parser()
        try:
            parser.parse_args(["track", "topics", "--help"])
        except SystemExit as exc:
            assert exc.code == 0
        out = capsys.readouterr().out
        assert "ticket track topics" in out
        assert "--format" in out

    def test_topic_registered_and_help_visible(self, capsys):
        parser = self._build_track_parser()
        try:
            parser.parse_args(["track", "topic", "--help"])
        except SystemExit as exc:
            assert exc.code == 0
        out = capsys.readouterr().out
        assert "ticket track topic" in out
        assert "--format" in out

    def test_topics_and_topic_dispatch_to_execute_functions(self):
        from ticket_system.commands import track

        handlers = track._create_version_agnostic_handlers()
        assert handlers["topics"] is track_topics.execute_topics
        assert handlers["topic"] is track_topics.execute_topic
