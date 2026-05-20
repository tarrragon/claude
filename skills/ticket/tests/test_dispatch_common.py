"""測試 ticket_system.lib.dispatch_common.load_and_unpack（W17-213 DRY helper）。"""

from __future__ import annotations

import argparse
from unittest.mock import patch

from ticket_system.lib.dispatch_common import load_and_unpack


def _args(ticket_id: str | None = "0.18.0-W17-001") -> argparse.Namespace:
    return argparse.Namespace(ticket_id=ticket_id)


class TestLoadAndUnpack:
    def test_missing_ticket_id_returns_exit_2(self):
        result = load_and_unpack(_args(None), "0.18.0")
        assert result.error_exit_code == 2
        assert result.ticket is None

    def test_ticket_not_found_returns_exit_2(self):
        with patch(
            "ticket_system.lib.dispatch_common.load_ticket",
            return_value=None,
        ):
            result = load_and_unpack(_args(), "0.18.0")
        assert result.error_exit_code == 2

    def test_yaml_error_returns_exit_2(self):
        with patch(
            "ticket_system.lib.dispatch_common.load_ticket",
            return_value={"_yaml_error": "bad"},
        ):
            result = load_and_unpack(_args(), "0.18.0")
        assert result.error_exit_code == 2

    def test_success_unpacks_all_fields(self):
        ticket = {
            "_body": "## Context Bundle\n\nbody",
            "where": {"files": ["a.py", "b.py"]},
            "acceptance": ["[ ] x", "[ ] y", "[ ] z"],
        }
        with patch(
            "ticket_system.lib.dispatch_common.load_ticket",
            return_value=ticket,
        ):
            result = load_and_unpack(_args(), "0.18.0")
        assert result.error_exit_code is None
        assert result.body == "## Context Bundle\n\nbody"
        assert result.where_files == ["a.py", "b.py"]
        assert len(result.acceptance) == 3

    def test_missing_optional_fields_default_safely(self):
        with patch(
            "ticket_system.lib.dispatch_common.load_ticket",
            return_value={},
        ):
            result = load_and_unpack(_args(), "0.18.0")
        assert result.error_exit_code is None
        assert result.body == ""
        assert result.where_files == []
        assert result.acceptance == []

    def test_where_not_dict_handled(self):
        with patch(
            "ticket_system.lib.dispatch_common.load_ticket",
            return_value={"where": "not-a-dict"},
        ):
            result = load_and_unpack(_args(), "0.18.0")
        assert result.error_exit_code is None
        assert result.where_files == []
