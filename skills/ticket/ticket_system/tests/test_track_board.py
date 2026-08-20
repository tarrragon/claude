"""track_board.py 主題分組模式測試。

驗證重點（board 主題分組模式，acceptance 見對應 ticket）：
1. 新模式下輸出依主題分組，每個主題為一節並列出其票
2. 未歸屬票獨立成節且明確標示，不與任一主題混列
3. 不指定新旗標時輸出與現行 Wave 分組加 ID 排序逐字相同（回歸鎖定）
4. 主題節點顯示該主題的票數與最高優先級，排序依最高優先級再依票數

既有 Wave 分組基線測試（TestGroupByWave / TestRenderBoardTree /
TestExecuteBoardMainFunction 等）位於 `.claude/skills/ticket/tests/
test_track_board.py`（1198 行），本檔不重複、不修改。
"""

from __future__ import annotations

import argparse
from typing import Any, Dict, List
from unittest.mock import patch

from ticket_system.commands.track_board import (
    GROUP_BY_TOPIC,
    GROUP_BY_WAVE,
    execute_board,
    group_by_topic,
    render_board_topics,
    render_board_tree,
)
from ticket_system.lib.command_tracking_messages import TrackBoardMessages


def _ticket(tid: str, title: str, status: str = "pending", priority: str = "P2") -> Dict[str, Any]:
    return {"id": tid, "title": title, "status": status, "priority": priority}


# ============================================================================
# group_by_topic
# ============================================================================


class TestGroupByTopic:
    def test_groups_tickets_by_assigned_topic(self):
        tickets = [
            _ticket("0.31.0-W1-001", "Task A1"),
            _ticket("0.31.0-W1-002", "Task A2"),
            _ticket("0.31.0-W1-003", "Task B1"),
        ]
        assignments = {
            "0.31.0-W1-001": "topic-a",
            "0.31.0-W1-002": "topic-a",
            "0.31.0-W1-003": "topic-b",
        }

        groups, unassigned = group_by_topic(tickets, assignments)

        assert set(groups.keys()) == {"topic-a", "topic-b"}
        assert len(groups["topic-a"]) == 2
        assert len(groups["topic-b"]) == 1
        assert unassigned == []

    def test_tickets_without_assignment_go_to_unassigned(self):
        tickets = [
            _ticket("0.31.0-W1-001", "Assigned"),
            _ticket("0.31.0-W1-002", "Not assigned"),
        ]
        assignments = {"0.31.0-W1-001": "topic-a"}

        groups, unassigned = group_by_topic(tickets, assignments)

        assert list(groups.keys()) == ["topic-a"]
        assert len(unassigned) == 1
        assert unassigned[0]["id"] == "0.31.0-W1-002"

    def test_sorted_by_highest_priority_first(self):
        tickets = [
            _ticket("0.31.0-W1-001", "Low prio topic", priority="P2"),
            _ticket("0.31.0-W1-002", "High prio topic", priority="P0"),
        ]
        assignments = {
            "0.31.0-W1-001": "topic-low",
            "0.31.0-W1-002": "topic-high",
        }

        groups, _ = group_by_topic(tickets, assignments)

        assert list(groups.keys()) == ["topic-high", "topic-low"]

    def test_same_priority_sorted_by_ticket_count_descending(self):
        tickets = [
            _ticket("0.31.0-W1-001", "Big topic 1", priority="P1"),
            _ticket("0.31.0-W1-002", "Big topic 2", priority="P1"),
            _ticket("0.31.0-W1-003", "Small topic", priority="P1"),
        ]
        assignments = {
            "0.31.0-W1-001": "topic-big",
            "0.31.0-W1-002": "topic-big",
            "0.31.0-W1-003": "topic-small",
        }

        groups, _ = group_by_topic(tickets, assignments)

        assert list(groups.keys()) == ["topic-big", "topic-small"]

    def test_topics_without_valid_priority_sorted_last(self):
        tickets = [
            _ticket("0.31.0-W1-001", "No priority", priority=None),
            _ticket("0.31.0-W1-002", "Has priority", priority="P3"),
        ]
        assignments = {
            "0.31.0-W1-001": "topic-none",
            "0.31.0-W1-002": "topic-p3",
        }

        groups, _ = group_by_topic(tickets, assignments)

        assert list(groups.keys()) == ["topic-p3", "topic-none"]


# ============================================================================
# render_board_topics
# ============================================================================


class TestRenderBoardTopics:
    def test_each_topic_is_a_section_listing_its_tickets(self):
        tickets = [
            _ticket("0.31.0-W1-001", "Task A1"),
            _ticket("0.31.0-W1-002", "Task B1"),
        ]
        assignments = {"0.31.0-W1-001": "topic-a", "0.31.0-W1-002": "topic-b"}

        output = render_board_topics(tickets, assignments, "0.31.0")

        assert "topic-a" in output
        assert "topic-b" in output
        assert "Task A1" in output
        assert "Task B1" in output

    def test_unassigned_section_present_and_separate(self):
        tickets = [
            _ticket("0.31.0-W1-001", "Assigned task"),
            _ticket("0.31.0-W1-002", "Orphan task"),
        ]
        assignments = {"0.31.0-W1-001": "topic-a"}

        output = render_board_topics(tickets, assignments, "0.31.0")
        lines = output.splitlines()

        unassigned_title = TrackBoardMessages.TOPIC_UNASSIGNED_TITLE_FORMAT.format(count=1)
        assert unassigned_title in output

        # 未歸屬節在主題節之後，Orphan task 出現於未歸屬節標題行之後
        unassigned_idx = lines.index(unassigned_title)
        orphan_idx = next(i for i, line in enumerate(lines) if "Orphan task" in line)
        assigned_idx = next(i for i, line in enumerate(lines) if "Assigned task" in line)
        assert orphan_idx > unassigned_idx
        assert assigned_idx < unassigned_idx

    def test_no_unassigned_section_when_all_tickets_assigned(self):
        tickets = [_ticket("0.31.0-W1-001", "Task A1")]
        assignments = {"0.31.0-W1-001": "topic-a"}

        output = render_board_topics(tickets, assignments, "0.31.0")

        assert "未歸屬" not in output

    def test_topic_node_shows_ticket_count_and_highest_priority(self):
        tickets = [
            _ticket("0.31.0-W1-001", "Task A1", priority="P2"),
            _ticket("0.31.0-W1-002", "Task A2", priority="P0"),
        ]
        assignments = {"0.31.0-W1-001": "topic-a", "0.31.0-W1-002": "topic-a"}

        output = render_board_topics(tickets, assignments, "0.31.0")

        expected_header = TrackBoardMessages.TOPIC_TITLE_FORMAT.format(
            topic="topic-a", count=2, priority="P0"
        )
        assert expected_header in output

    def test_topic_without_valid_priority_uses_placeholder(self):
        tickets = [_ticket("0.31.0-W1-001", "Task A1", priority=None)]
        assignments = {"0.31.0-W1-001": "topic-a"}

        output = render_board_topics(tickets, assignments, "0.31.0")

        expected_header = TrackBoardMessages.TOPIC_TITLE_FORMAT.format(
            topic="topic-a", count=1, priority=TrackBoardMessages.TOPIC_NO_PRIORITY_TEXT
        )
        assert expected_header in output

    def test_no_tickets_shows_no_tasks_text(self):
        output = render_board_topics([], {}, "0.31.0")
        assert TrackBoardMessages.NO_TASKS_TEXT in output


# ============================================================================
# execute_board --group-by（acceptance 3：預設行為零變更回歸鎖定）
# ============================================================================


class TestExecuteBoardGroupBy:
    _TICKETS = [
        {"id": "0.31.0-W1-001", "title": "Task A1", "status": "pending", "priority": "P1"},
        {"id": "0.31.0-W2-001", "title": "Task B1", "status": "in_progress", "priority": "P0"},
    ]

    def test_group_by_topic_dispatches_to_render_board_topics(self):
        args = argparse.Namespace(wave=None, all=False, group_by=GROUP_BY_TOPIC)

        with patch(
            "ticket_system.commands.track_board.list_tickets", return_value=self._TICKETS
        ), patch(
            "ticket_system.commands.track_board.list_assignments",
            return_value={"0.31.0-W1-001": "topic-a"},
        ), patch("builtins.print") as mock_print:
            result = execute_board(args, "0.31.0")

        assert result == 0
        output = mock_print.call_args[0][0]
        assert "topic-a" in output
        assert TrackBoardMessages.TOPIC_UNASSIGNED_TITLE_FORMAT.format(count=1) in output

    def test_default_group_by_wave_output_identical_to_tree_render(self):
        """acceptance 3：不指定新旗標時，輸出與 render_board_tree() 逐字相同"""
        args = argparse.Namespace(wave=None, all=False, group_by=GROUP_BY_WAVE)

        expected = render_board_tree(self._TICKETS, "0.31.0", show_all=False)

        with patch(
            "ticket_system.commands.track_board.list_tickets", return_value=self._TICKETS
        ), patch("builtins.print") as mock_print:
            result = execute_board(args, "0.31.0")

        assert result == 0
        actual = mock_print.call_args[0][0]
        assert actual == expected

    def test_namespace_without_group_by_attribute_falls_back_to_wave(self):
        """回歸保護：既有呼叫端（未帶 group_by 屬性的 Namespace）不得炸掉，
        且輸出須與 render_board_tree() 逐字相同（既有測試套件即此形態）"""
        args = argparse.Namespace(wave=None, all=False)

        expected = render_board_tree(self._TICKETS, "0.31.0", show_all=False)

        with patch(
            "ticket_system.commands.track_board.list_tickets", return_value=self._TICKETS
        ), patch("builtins.print") as mock_print:
            result = execute_board(args, "0.31.0")

        assert result == 0
        actual = mock_print.call_args[0][0]
        assert actual == expected
