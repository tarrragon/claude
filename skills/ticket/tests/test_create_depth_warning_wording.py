"""
create --parent 深度警告措辭（0.5.0-W1-282，E1 對照）

同一批 fixture 建立深度 3 與深度 4 的子票：深度 4 有警告、深度 3 沒有；
警告措辭不得宣稱深度超限的 ticket 不可被派發。
"""

import argparse
from unittest.mock import patch

from ticket_system.constants import MAX_TICKET_DEPTH
from ticket_system.lib.messages import WarningMessages
from ticket_system.lib.ticket_id_allocator import resolve_ticket_id_and_wave

PARENT = "1.0.0-W1-056.5"
CHILD_ID = "1.0.0-W1-056.5.1"


def _create_at_parent_depth(parent_depth, capsys):
    """以指定父票深度建立子票，回傳 stdout。"""
    args = argparse.Namespace(parent=PARENT, seq=None, wave=None)
    with patch("ticket_system.lib.ticket_id_allocator.get_next_child_seq", return_value=1), \
         patch("ticket_system.lib.ticket_id_allocator.compute_depth", return_value=parent_depth), \
         patch("ticket_system.lib.ticket_id_allocator.extract_wave_from_ticket_id", return_value=1), \
         patch("ticket_system.lib.ticket_id_allocator.validate_ticket_id", return_value=True):
        resolve_ticket_id_and_wave(args, "1.0.0")
    return capsys.readouterr().out


def _expected_warning(depth):
    return WarningMessages.DEPTH_LIMIT_REACHED.format(
        ticket_id=CHILD_ID, depth=depth, max_depth=MAX_TICKET_DEPTH
    )


def test_depth_4_warns_and_depth_3_does_not(capsys):
    out_depth_3 = _create_at_parent_depth(MAX_TICKET_DEPTH - 1, capsys)
    out_depth_4 = _create_at_parent_depth(MAX_TICKET_DEPTH, capsys)
    first_line_4 = _expected_warning(MAX_TICKET_DEPTH + 1).splitlines()[0]
    first_line_3 = _expected_warning(MAX_TICKET_DEPTH).splitlines()[0]
    assert first_line_4 in out_depth_4
    assert first_line_3 not in out_depth_3
    assert out_depth_3.strip() == ""


def test_warning_wording_no_longer_claims_unassignable():
    text = WarningMessages.DEPTH_LIMIT_REACHED
    assert "不可被派發" not in text


def test_warning_wording_states_mainline_unaffected_and_subagent_limit():
    text = WarningMessages.DEPTH_LIMIT_REACHED
    assert "主線程派發此 ticket 不受影響" in text
    assert "子代理人持有此 ticket 時不可再往下派發" in text
