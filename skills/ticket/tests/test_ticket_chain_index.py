"""
任務鏈索引模組測試

測試 TicketChainIndex 的各項功能：
- build_from_tickets() 索引建立
- get_children() 直接子任務查詢
- get_descendants() 所有後代查詢
- has_children() 子任務檢查
- get_child_count() 子任務計數
- get_descendant_count() 後代計數

測試案例涵蓋：
- 空列表
- 無依賴的 Ticket
- 線性依賴鏈
- 多級任務樹
- 混合格式（字串和字典）
- 邊界情況（不存在的 ID）
"""

import pytest
from typing import List, Dict, Any

from ticket_system.lib.ticket_chain_index import TicketChainIndex


class TestTicketChainIndexBuild:
    """測試 build_from_tickets() 索引建立功能"""

    def test_empty_tickets_list(self):
        """測試空 Ticket 列表"""
        index = TicketChainIndex()
        index.build_from_tickets([])

        # 索引應為空
        assert len(index.parent_index) == 0
        assert len(index.root_index) == 0

    def test_single_root_ticket_no_children(self):
        """測試單一根 Ticket（無子任務）"""
        tickets = [
            {
                "id": "0.31.0-W4-001",
                "chain": {},
                "children": [],
            }
        ]
        index = TicketChainIndex()
        index.build_from_tickets(tickets)

        # parent_index 應為空（無子任務）
        assert len(index.parent_index) == 0

        # root_index 應包含此 Ticket
        assert "0.31.0-W4-001" in index.root_index
        assert index.root_index["0.31.0-W4-001"] == ["0.31.0-W4-001"]

    def test_root_with_children_string_format(self):
        """測試根 Ticket 包含子任務（字串格式）"""
        tickets = [
            {
                "id": "0.31.0-W4-001",
                "chain": {},
                "children": ["0.31.0-W4-001.1", "0.31.0-W4-001.2"],
            },
            {
                "id": "0.31.0-W4-001.1",
                "chain": {"parent": "0.31.0-W4-001"},
                "children": [],
            },
            {
                "id": "0.31.0-W4-001.2",
                "chain": {"parent": "0.31.0-W4-001"},
                "children": [],
            },
        ]
        index = TicketChainIndex()
        index.build_from_tickets(tickets)

        # parent_index 驗證
        assert index.get_children("0.31.0-W4-001") == [
            "0.31.0-W4-001.1",
            "0.31.0-W4-001.2",
        ]

        # root_index 驗證
        descendants = index.get_descendants("0.31.0-W4-001")
        assert "0.31.0-W4-001" in descendants
        assert "0.31.0-W4-001.1" in descendants
        assert "0.31.0-W4-001.2" in descendants
        assert len(descendants) == 3

    def test_root_with_children_dict_format(self):
        """測試根 Ticket 包含子任務（字典格式）"""
        tickets = [
            {
                "id": "0.31.0-W4-001",
                "chain": {},
                "children": [
                    {"id": "0.31.0-W4-001.1", "status": "pending"},
                    {"id": "0.31.0-W4-001.2", "status": "pending"},
                ],
            },
            {
                "id": "0.31.0-W4-001.1",
                "chain": {"parent": "0.31.0-W4-001"},
                "children": [],
            },
            {
                "id": "0.31.0-W4-001.2",
                "chain": {"parent": "0.31.0-W4-001"},
                "children": [],
            },
        ]
        index = TicketChainIndex()
        index.build_from_tickets(tickets)

        # parent_index 驗證
        assert index.get_children("0.31.0-W4-001") == [
            "0.31.0-W4-001.1",
            "0.31.0-W4-001.2",
        ]

        # root_index 驗證
        descendants = index.get_descendants("0.31.0-W4-001")
        assert len(descendants) == 3

    def test_multi_level_hierarchy(self):
        """測試多級任務樹：001 → 001.1 → 001.1.1"""
        tickets = [
            {
                "id": "0.31.0-W4-001",
                "chain": {},
                "children": ["0.31.0-W4-001.1"],
            },
            {
                "id": "0.31.0-W4-001.1",
                "chain": {"parent": "0.31.0-W4-001"},
                "children": ["0.31.0-W4-001.1.1"],
            },
            {
                "id": "0.31.0-W4-001.1.1",
                "chain": {"parent": "0.31.0-W4-001.1"},
                "children": [],
            },
        ]
        index = TicketChainIndex()
        index.build_from_tickets(tickets)

        # 驗證各級索引
        assert index.get_children("0.31.0-W4-001") == ["0.31.0-W4-001.1"]
        assert index.get_children("0.31.0-W4-001.1") == ["0.31.0-W4-001.1.1"]
        assert index.get_children("0.31.0-W4-001.1.1") == []

        # 驗證後代
        descendants = index.get_descendants("0.31.0-W4-001")
        assert len(descendants) == 3
        assert descendants == [
            "0.31.0-W4-001",
            "0.31.0-W4-001.1",
            "0.31.0-W4-001.1.1",
        ]

    def test_multiple_root_tickets(self):
        """測試多個根 Ticket（各自獨立的樹）"""
        tickets = [
            {
                "id": "0.31.0-W4-001",
                "chain": {},
                "children": ["0.31.0-W4-001.1"],
            },
            {
                "id": "0.31.0-W4-001.1",
                "chain": {"parent": "0.31.0-W4-001"},
                "children": [],
            },
            {
                "id": "0.31.0-W4-002",
                "chain": {},
                "children": ["0.31.0-W4-002.1"],
            },
            {
                "id": "0.31.0-W4-002.1",
                "chain": {"parent": "0.31.0-W4-002"},
                "children": [],
            },
        ]
        index = TicketChainIndex()
        index.build_from_tickets(tickets)

        # 驗證兩個獨立的樹
        assert len(index.root_index) == 2
        assert len(index.get_descendants("0.31.0-W4-001")) == 2
        assert len(index.get_descendants("0.31.0-W4-002")) == 2

    def test_invalid_ticket_without_id(self):
        """測試無效 Ticket（缺少 ID）"""
        tickets = [
            {
                # 缺少 id
                "chain": {},
                "children": [],
            }
        ]
        index = TicketChainIndex()
        # 應該安全處理，不拋異常
        index.build_from_tickets(tickets)

        # 索引應為空
        assert len(index.root_index) == 0


class TestGetChildren:
    """測試 get_children() 直接子任務查詢"""

    def test_get_children_exists(self):
        """測試存在的父任務"""
        tickets = [
            {
                "id": "001",
                "chain": {},
                "children": ["001.1", "001.2", "001.3"],
            }
        ]
        index = TicketChainIndex()
        index.build_from_tickets(tickets)

        result = index.get_children("001")
        assert result == ["001.1", "001.2", "001.3"]

    def test_get_children_not_exists(self):
        """測試不存在的父任務"""
        tickets = [{"id": "001", "chain": {}, "children": []}]
        index = TicketChainIndex()
        index.build_from_tickets(tickets)

        result = index.get_children("999")
        assert result == []

    def test_get_children_no_children(self):
        """測試無子任務的父任務"""
        tickets = [
            {
                "id": "001",
                "chain": {},
                "children": [],
            }
        ]
        index = TicketChainIndex()
        index.build_from_tickets(tickets)

        result = index.get_children("001")
        assert result == []


class TestGetDescendants:
    """測試 get_descendants() 所有後代查詢"""

    def test_get_descendants_linear_chain(self):
        """測試線性依賴鏈的後代"""
        tickets = [
            {
                "id": "A",
                "chain": {},
                "children": ["B"],
            },
            {
                "id": "B",
                "chain": {"parent": "A"},
                "children": ["C"],
            },
            {
                "id": "C",
                "chain": {"parent": "B"},
                "children": [],
            },
        ]
        index = TicketChainIndex()
        index.build_from_tickets(tickets)

        result = index.get_descendants("A")
        assert result == ["A", "B", "C"]

    def test_get_descendants_tree_structure(self):
        """測試樹形結構的後代"""
        tickets = [
            {
                "id": "A",
                "chain": {},
                "children": ["B", "C"],
            },
            {
                "id": "B",
                "chain": {"parent": "A"},
                "children": ["D"],
            },
            {
                "id": "C",
                "chain": {"parent": "A"},
                "children": ["E"],
            },
            {
                "id": "D",
                "chain": {"parent": "B"},
                "children": [],
            },
            {
                "id": "E",
                "chain": {"parent": "C"},
                "children": [],
            },
        ]
        index = TicketChainIndex()
        index.build_from_tickets(tickets)

        result = index.get_descendants("A")
        # 順序應為深度優先搜尋：A, B, D, C, E
        assert "A" in result
        assert "B" in result
        assert "C" in result
        assert "D" in result
        assert "E" in result
        assert len(result) == 5

    def test_get_descendants_not_exists(self):
        """測試不存在的根任務"""
        tickets = [{"id": "A", "chain": {}, "children": []}]
        index = TicketChainIndex()
        index.build_from_tickets(tickets)

        result = index.get_descendants("999")
        assert result == []


class TestHasChildren:
    """測試 has_children() 子任務檢查"""

    def test_has_children_true(self):
        """測試有子任務的任務"""
        tickets = [{"id": "001", "chain": {}, "children": ["001.1"]}]
        index = TicketChainIndex()
        index.build_from_tickets(tickets)

        assert index.has_children("001") is True

    def test_has_children_false_no_children(self):
        """測試無子任務的任務"""
        tickets = [{"id": "001", "chain": {}, "children": []}]
        index = TicketChainIndex()
        index.build_from_tickets(tickets)

        assert index.has_children("001") is False

    def test_has_children_false_not_exists(self):
        """測試不存在的任務"""
        tickets = [{"id": "001", "chain": {}, "children": []}]
        index = TicketChainIndex()
        index.build_from_tickets(tickets)

        assert index.has_children("999") is False


class TestGetChildCount:
    """測試 get_child_count() 子任務計數"""

    def test_get_child_count(self):
        """測試子任務數量計算"""
        tickets = [
            {
                "id": "001",
                "chain": {},
                "children": ["001.1", "001.2", "001.3"],
            }
        ]
        index = TicketChainIndex()
        index.build_from_tickets(tickets)

        assert index.get_child_count("001") == 3

    def test_get_child_count_no_children(self):
        """測試無子任務的計數"""
        tickets = [{"id": "001", "chain": {}, "children": []}]
        index = TicketChainIndex()
        index.build_from_tickets(tickets)

        assert index.get_child_count("001") == 0

    def test_get_child_count_not_exists(self):
        """測試不存在任務的計數"""
        tickets = [{"id": "001", "chain": {}, "children": []}]
        index = TicketChainIndex()
        index.build_from_tickets(tickets)

        assert index.get_child_count("999") == 0


class TestGetDescendantCount:
    """測試 get_descendant_count() 後代計數"""

    def test_get_descendant_count_linear(self):
        """測試線性結構的後代計數"""
        tickets = [
            {
                "id": "A",
                "chain": {},
                "children": ["B"],
            },
            {
                "id": "B",
                "chain": {"parent": "A"},
                "children": ["C"],
            },
            {
                "id": "C",
                "chain": {"parent": "B"},
                "children": [],
            },
        ]
        index = TicketChainIndex()
        index.build_from_tickets(tickets)

        # A 的後代應包括 A 本身
        assert index.get_descendant_count("A") == 3

    def test_get_descendant_count_tree(self):
        """測試樹形結構的後代計數"""
        tickets = [
            {
                "id": "A",
                "chain": {},
                "children": ["B", "C"],
            },
            {
                "id": "B",
                "chain": {"parent": "A"},
                "children": ["D"],
            },
            {
                "id": "C",
                "chain": {"parent": "A"},
                "children": ["E"],
            },
            {
                "id": "D",
                "chain": {"parent": "B"},
                "children": [],
            },
            {
                "id": "E",
                "chain": {"parent": "C"},
                "children": [],
            },
        ]
        index = TicketChainIndex()
        index.build_from_tickets(tickets)

        # 只有根任務 A 在 root_index 中
        assert index.get_descendant_count("A") == 5
        # B、C、D、E 不在 root_index 中（它們不是根任務），返回 0
        assert index.get_descendant_count("B") == 0
        assert index.get_descendant_count("C") == 0
        assert index.get_descendant_count("D") == 0
        assert index.get_descendant_count("E") == 0

    def test_get_descendant_count_not_exists(self):
        """測試不存在任務的後代計數"""
        tickets = [{"id": "A", "chain": {}, "children": []}]
        index = TicketChainIndex()
        index.build_from_tickets(tickets)

        assert index.get_descendant_count("999") == 0


class TestIndexRebuild:
    """測試索引重建"""

    def test_rebuild_clears_old_index(self):
        """測試重新建立索引清除舊資料"""
        tickets1 = [{"id": "A", "chain": {}, "children": ["B"]}]
        index = TicketChainIndex()
        index.build_from_tickets(tickets1)

        assert index.has_children("A") is True

        # 重新建立空索引
        index.build_from_tickets([])
        assert index.has_children("A") is False
        assert len(index.root_index) == 0


class TestEdgeCases:
    """測試邊界情況"""

    def test_mixed_format_children(self):
        """測試混合格式的子任務（字串和字典）"""
        tickets = [
            {
                "id": "001",
                "chain": {},
                "children": [
                    "001.1",  # 字串格式
                    {"id": "001.2", "status": "pending"},  # 字典格式
                ],
            }
        ]
        index = TicketChainIndex()
        index.build_from_tickets(tickets)

        children = index.get_children("001")
        assert "001.1" in children
        assert "001.2" in children
        assert len(children) == 2

    def test_invalid_child_format(self):
        """測試無效的子任務格式"""
        tickets = [
            {
                "id": "001",
                "chain": {},
                "children": [
                    "001.1",
                    123,  # 無效型別
                    None,  # 無效值
                    {"id": "001.2"},
                ],
            }
        ]
        index = TicketChainIndex()
        # 應該安全處理，跳過無效項目
        index.build_from_tickets(tickets)

        children = index.get_children("001")
        # 應該包含有效的項目
        assert "001.1" in children
        assert "001.2" in children
