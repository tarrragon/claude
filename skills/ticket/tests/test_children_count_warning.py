"""
測試 create --parent 時 children 數 warning（W5-005.11 D11）

- 超閾值 emit warning 不硬擋（留旁路）
- 恰在閾值邊界案例
- 低於閾值不 warn
"""

import argparse
from unittest.mock import patch

from ticket_system.constants import MAX_CHILDREN_WARNING_THRESHOLD
from ticket_system.commands.create import _resolve_ticket_id_and_wave


class TestCreateParentChildrenCountWarning:
    """create --parent 扇出 warning"""

    def _run(self, parent_id, child_seq, capsys):
        """以 child_seq mock 執行 _resolve_ticket_id_and_wave，回傳 stdout。"""
        args = argparse.Namespace(parent=parent_id, seq=None, wave=None)
        with patch("ticket_system.commands.create.get_next_child_seq", return_value=child_seq), \
             patch("ticket_system.commands.create.compute_depth", return_value=1), \
             patch("ticket_system.commands.create.extract_wave_from_ticket_id", return_value=1), \
             patch("ticket_system.commands.create.validate_ticket_id", return_value=True):
            result = _resolve_ticket_id_and_wave(args, "1.0.0")
        out = capsys.readouterr().out
        return result, out

    def test_no_warning_below_threshold(self, capsys):
        """9 existing children (child_seq=10) → below threshold 10, no warn"""
        result, out = self._run("1.0.0-W5-001", child_seq=10, capsys=capsys)
        assert "子任務" not in out or "超過" not in out
        assert result is not None

    def test_warning_at_threshold(self, capsys):
        """10 existing children (child_seq=11) → at threshold, warn"""
        result, out = self._run("1.0.0-W5-001", child_seq=11, capsys=capsys)
        assert f"{MAX_CHILDREN_WARNING_THRESHOLD}" in out
        assert "1.0.0-W5-001" in out
        assert result is not None

    def test_warning_above_threshold(self, capsys):
        """18 existing children (child_seq=19) → above threshold, warn"""
        result, out = self._run("1.0.0-W5-001", child_seq=19, capsys=capsys)
        assert "18" in out
        assert f"{MAX_CHILDREN_WARNING_THRESHOLD}" in out
        assert result is not None

    def test_no_warning_with_few_children(self, capsys):
        """2 existing children (child_seq=3) → well below threshold, no warn"""
        result, out = self._run("1.0.0-W5-001", child_seq=3, capsys=capsys)
        assert "超過建議閾值" not in out
        assert result is not None

    def test_warning_does_not_block(self, capsys):
        """warning 不硬擋：仍回傳有效 tuple"""
        result, out = self._run("1.0.0-W5-001", child_seq=15, capsys=capsys)
        assert result is not None
        version, ticket_id, wave = result
        assert version == "1.0.0"
        assert "W5-001" in ticket_id
        assert wave == 1
