#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試 _parse_yaml_lines 對頂層 YAML list 的解析（W11-003.4）

背景：_parse_yaml_lines 過去無法處理頂層列表（children/blockedBy/
spawned_tickets/relatedTo），導致 extract_children_from_frontmatter
在生產環境實質失效。

本測試覆蓋：
- Block-style 列表（無縮排）： children:\n- id
- Block-style 列表（2 空白縮排）： children:\n  - id
- Flow-style 列表： children: [a, b]
- Flow-style 空列表： children: []
- 混合多個列表欄位（children/blockedBy/relatedTo/spawned_tickets）
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from hook_utils import parse_ticket_frontmatter


def _wrap(frontmatter_body: str) -> str:
    """包裝為完整 frontmatter 格式"""
    return "---\n" + frontmatter_body + "\n---\n\n# Body\n"


class TestTopLevelBlockStyleList:
    """頂層 block-style 列表（無縮排 - id）"""

    def test_children_block_style_no_indent(self):
        content = _wrap(
            "id: 0.1.0-W1-001\n"
            "children:\n"
            "- 0.1.0-W1-001.1\n"
            "- 0.1.0-W1-001.2\n"
            "- 0.1.0-W1-001.3\n"
            "status: in_progress"
        )
        result = parse_ticket_frontmatter(content)
        assert result.get("children") == [
            "0.1.0-W1-001.1",
            "0.1.0-W1-001.2",
            "0.1.0-W1-001.3",
        ]
        assert result.get("status") == "in_progress"

    def test_children_block_style_2space_indent(self):
        content = _wrap(
            "id: 0.1.0-W1-001\n"
            "children:\n"
            "  - 0.1.0-W1-001.1\n"
            "  - 0.1.0-W1-001.2\n"
            "status: in_progress"
        )
        result = parse_ticket_frontmatter(content)
        assert result.get("children") == [
            "0.1.0-W1-001.1",
            "0.1.0-W1-001.2",
        ]
        assert result.get("status") == "in_progress"

    def test_blocked_by_block_style(self):
        content = _wrap(
            "id: 0.1.0-W1-002\n"
            "blockedBy:\n"
            "- 0.1.0-W1-001\n"
            "- 0.1.0-W1-000"
        )
        result = parse_ticket_frontmatter(content)
        assert result.get("blockedBy") == ["0.1.0-W1-001", "0.1.0-W1-000"]

    def test_spawned_tickets_block_style(self):
        content = _wrap(
            "id: 0.1.0-W1-003\n"
            "spawned_tickets:\n"
            "- 0.1.0-W2-001\n"
            "- 0.1.0-W2-002"
        )
        result = parse_ticket_frontmatter(content)
        assert result.get("spawned_tickets") == ["0.1.0-W2-001", "0.1.0-W2-002"]

    def test_related_to_block_style(self):
        content = _wrap(
            "id: 0.1.0-W1-004\n"
            "relatedTo:\n"
            "- 0.1.0-W1-100"
        )
        result = parse_ticket_frontmatter(content)
        assert result.get("relatedTo") == ["0.1.0-W1-100"]


class TestTopLevelFlowStyleList:
    """頂層 flow-style 列表（[a, b]）"""

    def test_children_flow_style(self):
        content = _wrap(
            "id: 0.1.0-W1-001\n"
            "children: [0.1.0-W1-001.1, 0.1.0-W1-001.2]\n"
            "status: in_progress"
        )
        result = parse_ticket_frontmatter(content)
        assert result.get("children") == [
            "0.1.0-W1-001.1",
            "0.1.0-W1-001.2",
        ]
        assert result.get("status") == "in_progress"

    def test_children_flow_style_empty(self):
        content = _wrap(
            "id: 0.1.0-W1-001\n"
            "children: []\n"
            "status: in_progress"
        )
        result = parse_ticket_frontmatter(content)
        # 空列表：接受 [] 或空字串（向後相容）
        children = result.get("children")
        assert children in ([], "", None) or children == []
        assert result.get("status") == "in_progress"

    def test_blocked_by_flow_style(self):
        content = _wrap(
            "id: 0.1.0-W1-002\n"
            "blockedBy: [0.1.0-W1-001]"
        )
        result = parse_ticket_frontmatter(content)
        assert result.get("blockedBy") == ["0.1.0-W1-001"]

    def test_flow_style_with_quotes(self):
        content = _wrap(
            "id: 0.1.0-W1-001\n"
            "children: ['0.1.0-W1-001.1', \"0.1.0-W1-001.2\"]"
        )
        result = parse_ticket_frontmatter(content)
        assert result.get("children") == [
            "0.1.0-W1-001.1",
            "0.1.0-W1-001.2",
        ]


class TestMixedListFields:
    """多個列表欄位混合的 frontmatter"""

    def test_mixed_list_fields(self):
        content = _wrap(
            "id: 0.1.0-W1-001\n"
            "children:\n"
            "- 0.1.0-W1-001.1\n"
            "- 0.1.0-W1-001.2\n"
            "blockedBy:\n"
            "- 0.1.0-W1-000\n"
            "relatedTo: []\n"
            "spawned_tickets:\n"
            "- 0.1.0-W2-001\n"
            "status: in_progress"
        )
        result = parse_ticket_frontmatter(content)
        assert result.get("children") == ["0.1.0-W1-001.1", "0.1.0-W1-001.2"]
        assert result.get("blockedBy") == ["0.1.0-W1-000"]
        assert result.get("spawned_tickets") == ["0.1.0-W2-001"]
        assert result.get("status") == "in_progress"

    def test_list_followed_by_dict_field(self):
        """列表後面接嵌套 dict 欄位，確認解析不被干擾"""
        content = _wrap(
            "id: 0.1.0-W1-001\n"
            "children:\n"
            "- 0.1.0-W1-001.1\n"
            "who:\n"
            "  current: thyme-python-developer\n"
            "status: in_progress"
        )
        result = parse_ticket_frontmatter(content)
        assert result.get("children") == ["0.1.0-W1-001.1"]
        assert isinstance(result.get("who"), dict)
        assert result["who"].get("current") == "thyme-python-developer"
        assert result.get("status") == "in_progress"


class TestExtractChildrenIntegration:
    """端到端：parse_ticket_frontmatter + extract_children_from_frontmatter"""

    def test_extract_children_via_parser_block_style(self):
        """修復後：extract_children_from_frontmatter 應正確回傳 children"""
        import logging

        sys.path.insert(0, str(Path(__file__).parent.parent))
        from acceptance_checkers.ticket_parser import extract_children_from_frontmatter

        logger = logging.getLogger("test")
        logger.addHandler(logging.NullHandler())

        content = _wrap(
            "id: 0.1.0-W1-001\n"
            "children:\n"
            "- 0.1.0-W1-001.1\n"
            "- 0.1.0-W1-001.2"
        )
        frontmatter = parse_ticket_frontmatter(content)
        children = extract_children_from_frontmatter(frontmatter, logger)
        assert children == ["0.1.0-W1-001.1", "0.1.0-W1-001.2"]
