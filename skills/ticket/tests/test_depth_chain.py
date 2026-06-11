"""
Ticket 嵌套深度計算測試（W1-056.8 / 協議 v2 D3）

驗證深度沿 parent_id 鏈計算，而非 ID 字串數點（linux F1 fatal 教訓）：
- _depth_via_resolver 純邏輯（含完整版本前綴 ID 案例）
- compute_depth 透過 load_ticket 回溯（mock）
- can_descend 以 MAX_TICKET_DEPTH 為唯一判準
- 異常成環不導致無限迴圈
"""

from unittest.mock import patch

import pytest

from ticket_system.constants import MAX_TICKET_DEPTH
from ticket_system.lib.depth import (
    _depth_via_resolver,
    compute_depth,
    can_descend,
)


class TestDepthViaResolver:
    """純邏輯深度計算（resolver 注入，無 I/O）"""

    def test_root_is_depth_1(self):
        chain = {"1.0.0-W1-056": None}
        assert _depth_via_resolver("1.0.0-W1-056", lambda t: chain.get(t)) == 1

    def test_first_level_child_is_depth_2(self):
        """完整版本前綴 ID（含 3 個點）必須仍算出 depth 2，非 count('.')+1=4"""
        chain = {
            "1.0.0-W1-056.5": "1.0.0-W1-056",
            "1.0.0-W1-056": None,
        }
        assert _depth_via_resolver("1.0.0-W1-056.5", lambda t: chain.get(t)) == 2

    def test_second_level_child_is_depth_3(self):
        chain = {
            "1.0.0-W1-056.5.1": "1.0.0-W1-056.5",
            "1.0.0-W1-056.5": "1.0.0-W1-056",
            "1.0.0-W1-056": None,
        }
        assert _depth_via_resolver("1.0.0-W1-056.5.1", lambda t: chain.get(t)) == 3

    def test_id_string_dot_count_would_be_wrong(self):
        """反例驗證：ID 字串數點對完整版本前綴 ID 算出錯誤深度"""
        ticket_id = "1.0.0-W1-056.5"
        # 字串數點法（v1 fatal bug）會算出 4
        assert ticket_id.count(".") + 1 == 4
        # parent_id 鏈法正確算出 2
        chain = {"1.0.0-W1-056.5": "1.0.0-W1-056", "1.0.0-W1-056": None}
        assert _depth_via_resolver(ticket_id, lambda t: chain.get(t)) == 2

    def test_circular_chain_does_not_hang(self):
        """parent_id 異常成環時回傳有限值（不無限迴圈）"""
        chain = {"A": "B", "B": "A"}
        result = _depth_via_resolver("A", lambda t: chain.get(t))
        assert isinstance(result, int)
        assert result >= 1


class TestComputeDepth:
    """compute_depth 透過 load_ticket 回溯 parent_id 鏈"""

    def _make_loader(self, parent_map):
        def fake_load(version, tid):
            if tid not in parent_map:
                return None
            return {"id": tid, "parent_id": parent_map[tid]}
        return fake_load

    def test_root_depth(self):
        loader = self._make_loader({"1.0.0-W1-056": None})
        with patch("ticket_system.lib.depth.load_ticket", side_effect=loader):
            assert compute_depth("1.0.0-W1-056") == 1

    def test_child_depth_with_version_prefix(self):
        loader = self._make_loader({
            "1.0.0-W1-056.5": "1.0.0-W1-056",
            "1.0.0-W1-056": None,
        })
        with patch("ticket_system.lib.depth.load_ticket", side_effect=loader):
            assert compute_depth("1.0.0-W1-056.5") == 2

    def test_grandchild_depth_at_limit(self):
        loader = self._make_loader({
            "1.0.0-W1-056.5.1": "1.0.0-W1-056.5",
            "1.0.0-W1-056.5": "1.0.0-W1-056",
            "1.0.0-W1-056": None,
        })
        with patch("ticket_system.lib.depth.load_ticket", side_effect=loader):
            assert compute_depth("1.0.0-W1-056.5.1") == 3

    def test_missing_ticket_defaults_depth_1(self):
        loader = self._make_loader({})
        with patch("ticket_system.lib.depth.load_ticket", side_effect=loader):
            assert compute_depth("1.0.0-W1-999") == 1


class TestCanDescend:
    """can_descend = depth < MAX_TICKET_DEPTH（唯一判準）"""

    def _patch_depth(self, value):
        return patch("ticket_system.lib.depth.compute_depth", return_value=value)

    def test_depth_below_limit_can_descend(self):
        with self._patch_depth(MAX_TICKET_DEPTH - 1):
            assert can_descend("1.0.0-W1-056.5") is True

    def test_depth_at_limit_cannot_descend(self):
        with self._patch_depth(MAX_TICKET_DEPTH):
            assert can_descend("1.0.0-W1-056.5.1") is False

    def test_depth_above_limit_cannot_descend(self):
        with self._patch_depth(MAX_TICKET_DEPTH + 1):
            assert can_descend("1.0.0-W1-056.5.1.1") is False

    def test_max_ticket_depth_is_3(self):
        """協議 v2 上限收緊至 3"""
        assert MAX_TICKET_DEPTH == 3
