"""
測試 ticket track depth 命令 + create --parent 深度上限 warning（W1-056.8）

- track depth：輸出 depth / max_depth / can_descend
- create --parent：新子任務深度 >= MAX_TICKET_DEPTH 時 emit warning（不硬擋）
"""

import argparse
from unittest.mock import patch

import pytest

from ticket_system.constants import MAX_TICKET_DEPTH
from ticket_system.commands.track_depth import execute_depth
from ticket_system.commands.create import _resolve_ticket_id_and_wave


class TestTrackDepthCommand:
    """ticket track depth <id>"""

    def test_depth_output_for_child(self, capsys):
        with patch("ticket_system.commands.track_depth.load_ticket",
                   return_value={"id": "1.0.0-W1-056.5", "parent_id": "1.0.0-W1-056"}), \
             patch("ticket_system.commands.track_depth.compute_depth", return_value=2), \
             patch("ticket_system.commands.track_depth.can_descend", return_value=True):
            args = argparse.Namespace(ticket_id="1.0.0-W1-056.5", version=None)
            rc = execute_depth(args, "1.0.0")
        out = capsys.readouterr().out
        assert rc == 0
        assert "depth = 2" in out
        assert f"max_depth = {MAX_TICKET_DEPTH}" in out
        assert "can_descend = true" in out

    def test_depth_at_limit_emits_note(self, capsys):
        with patch("ticket_system.commands.track_depth.load_ticket",
                   return_value={"id": "1.0.0-W1-056.5.1", "parent_id": "1.0.0-W1-056.5"}), \
             patch("ticket_system.commands.track_depth.compute_depth", return_value=3), \
             patch("ticket_system.commands.track_depth.can_descend", return_value=False):
            args = argparse.Namespace(ticket_id="1.0.0-W1-056.5.1", version=None)
            rc = execute_depth(args, "1.0.0")
        out = capsys.readouterr().out
        assert rc == 0
        assert "can_descend = false" in out
        assert "深度上限" in out

    def test_depth_missing_ticket_returns_1(self, capsys):
        with patch("ticket_system.commands.track_depth.load_ticket", return_value=None):
            args = argparse.Namespace(ticket_id="1.0.0-W1-999", version=None)
            rc = execute_depth(args, "1.0.0")
        assert rc == 1
        assert "找不到" in capsys.readouterr().out


class TestCreateParentDepthWarning:
    """create --parent 深度上限 warning"""

    def _run(self, parent_id, parent_depth, capsys):
        """以 parent depth mock 執行 _resolve_ticket_id_and_wave，回傳 stdout。"""
        args = argparse.Namespace(parent=parent_id, seq=None, wave=None)
        with patch("ticket_system.commands.create.get_next_child_seq", return_value=1), \
             patch("ticket_system.commands.create.compute_depth", return_value=parent_depth), \
             patch("ticket_system.commands.create.extract_wave_from_ticket_id", return_value=1), \
             patch("ticket_system.commands.create.validate_ticket_id", return_value=True):
            _resolve_ticket_id_and_wave(args, "1.0.0")
        return capsys.readouterr().out

    def test_no_warning_when_below_limit(self, capsys):
        """parent depth 1 → 新子任務 depth 2 < 3，不 warn"""
        out = self._run("1.0.0-W1-056", parent_depth=1, capsys=capsys)
        assert "嵌套上限" not in out

    def test_warning_when_new_child_reaches_limit(self, capsys):
        """parent depth 2 → 新子任務 depth 3 >= 3，warn"""
        out = self._run("1.0.0-W1-056.5", parent_depth=2, capsys=capsys)
        assert "嵌套上限" in out
        assert f"MAX_TICKET_DEPTH={MAX_TICKET_DEPTH}" in out

    def test_warning_when_new_child_exceeds_limit(self, capsys):
        """parent depth 3 → 新子任務 depth 4 > 3，warn（不硬擋，仍回傳 ticket_id）"""
        args = argparse.Namespace(parent="1.0.0-W1-056.5.1", seq=None, wave=None)
        with patch("ticket_system.commands.create.get_next_child_seq", return_value=1), \
             patch("ticket_system.commands.create.compute_depth", return_value=3), \
             patch("ticket_system.commands.create.extract_wave_from_ticket_id", return_value=1), \
             patch("ticket_system.commands.create.validate_ticket_id", return_value=True):
            result = _resolve_ticket_id_and_wave(args, "1.0.0")
        out = capsys.readouterr().out
        assert "嵌套上限" in out
        # 不硬擋：仍回傳有效 tuple（version, ticket_id, wave）
        assert result is not None
