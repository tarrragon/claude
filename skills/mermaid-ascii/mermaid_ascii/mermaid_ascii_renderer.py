"""
Mermaid ASCII Renderer - 純 Python 實現 Mermaid 圖表的 ASCII 渲染

支援:
- flowchart TD (上下方向)
- flowchart LR (左右方向)
- 基本節點類型: 方框 [], 圓角 (), 菱形 {}
- 基本箭頭: --> 和 ---
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class Node:
    """圖表節點"""
    id: str
    label: str
    shape: str = "box"  # box, round, diamond


@dataclass
class Edge:
    """圖表邊線"""
    source: str
    target: str
    label: str = ""


class MermaidAsciiRenderer:
    """Mermaid ASCII 渲染器"""

    def __init__(self, direction: str = "TD"):
        self.direction = direction  # TD (上下) 或 LR (左右)
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []

    def parse(self, mermaid_text: str) -> None:
        """解析 Mermaid 語法"""
        lines = mermaid_text.strip().split('\n')

        # 流程控制：解析方向、節點、邊線
        self._parse_direction(lines[0])

        for line in lines[1:]:
            line = line.strip()
            if not line or line.startswith('%%'):
                continue

            # 嘗試按順序解析：節點、邊線
            if self._parse_node(line):
                continue

            self._parse_edge(line)

    def _parse_direction(self, line: str) -> None:
        """解析 flowchart 方向（TD/TB/LR）

        Args:
            line: 第一行文本，應包含 flowchart 指令
        """
        first_line = line.strip().lower()
        if 'flowchart' in first_line:
            if 'lr' in first_line:
                self.direction = "LR"
            elif 'td' in first_line:
                self.direction = "TD"
            elif 'tb' in first_line:
                self.direction = "TD"

    def _parse_node(self, line: str) -> bool:
        """解析節點定義（box/round/diamond）

        Args:
            line: 單行文本，可能包含節點定義

        Returns:
            如果成功解析節點則返回 True，否則返回 False
        """
        # 解析方框節點 id[label]
        node_match = re.match(r'^(\w+)\[(.*?)\]$', line)
        if node_match:
            node_id, label = node_match.groups()
            self.nodes[node_id] = Node(node_id, label, "box")
            return True

        # 解析圓角節點 id(label)
        node_match = re.match(r'^(\w+)\((.*?)\)$', line)
        if node_match:
            node_id, label = node_match.groups()
            self.nodes[node_id] = Node(node_id, label, "round")
            return True

        # 解析菱形節點 id{label}
        node_match = re.match(r'^(\w+)\{(.*?)\}$', line)
        if node_match:
            node_id, label = node_match.groups()
            self.nodes[node_id] = Node(node_id, label, "diamond")
            return True

        return False

    def _parse_edge(self, line: str) -> bool:
        """解析邊線定義（箭頭、標籤）

        Args:
            line: 單行文本，可能包含邊線定義

        Returns:
            如果成功解析邊線則返回 True，否則返回 False
        """
        # 解析箭頭邊線 source --> target 或 source -- label --> target
        edge_match = re.match(r'^(\w+)\s*(?:--\s*(.*?)\s*)?-->\s*(\w+)$', line)
        if edge_match:
            source, label, target = edge_match.groups()
            self.edges.append(Edge(source, target, label or ""))
            return True

        # 解析直線邊線 source --- target
        edge_match = re.match(r'^(\w+)\s*---\s*(\w+)$', line)
        if edge_match:
            source, target = edge_match.groups()
            self.edges.append(Edge(source, target, ""))
            return True

        return False

    def render(self) -> str:
        """渲染為 ASCII 藝術"""
        if not self.nodes:
            return ""

        if self.direction == "LR":
            return self._render_lr()
        else:
            return self._render_td()

    def _render_td(self) -> str:
        """上下方向渲染 (Top-Down)"""
        lines = []
        node_list = list(self.nodes.keys())

        # 簡單實作: 縱向排列節點
        for i, node_id in enumerate(node_list):
            node = self.nodes[node_id]
            box = self._format_node(node)
            lines.append(box)

            # 添加邊線到下一個節點
            for edge in self.edges:
                if edge.source == node_id and i < len(node_list) - 1:
                    lines.append("    |")
                    if edge.label:
                        lines.append(f"    {edge.label}")
                    lines.append("    v")

        return "\n".join(lines)

    def _render_lr(self) -> str:
        """左右方向渲染 (Left-Right)"""
        lines = []
        node_list = list(self.nodes.keys())

        # 簡單實作: 橫向排列節點
        for i, node_id in enumerate(node_list):
            node = self.nodes[node_id]
            box = self._format_node(node)

            if i == 0:
                lines.append(box)
            else:
                # 添加邊線
                lines.append("    -->    " + box)

        return "\n".join(lines)

    def _format_node(self, node: Node) -> str:
        """格式化節點為 ASCII"""
        label = node.label

        if node.shape == "box":
            return self._format_box(label)
        elif node.shape == "round":
            return self._format_round(label)
        elif node.shape == "diamond":
            return self._format_diamond(label)

        return self._format_box(label)

    @staticmethod
    def _format_box(text: str) -> str:
        """格式化方框"""
        width = max(len(text) + 2, 10)
        top = "┌─" + "─" * (width - 4) + "─┐"
        middle = "│ " + text.ljust(width - 4) + " │"
        bottom = "└─" + "─" * (width - 4) + "─┘"
        return "\n".join([top, middle, bottom])

    @staticmethod
    def _format_round(text: str) -> str:
        """格式化圓角框"""
        width = max(len(text) + 2, 10)
        top = "╭─" + "─" * (width - 4) + "─╮"
        middle = "│ " + text.ljust(width - 4) + " │"
        bottom = "╰─" + "─" * (width - 4) + "─╯"
        return "\n".join([top, middle, bottom])

    @staticmethod
    def _format_diamond(text: str) -> str:
        """格式化菱形"""
        width = max(len(text) + 2, 10)
        top = "◇ " + text + " ◇"
        return top


def render_mermaid(mermaid_text: str) -> str:
    """渲染 Mermaid 圖表為 ASCII

    Args:
        mermaid_text: Mermaid 圖表語法

    Returns:
        ASCII 渲染結果

    Example:
        >>> diagram = '''
        ... flowchart TD
        ...     A[開始]
        ...     B[處理]
        ...     C[結束]
        ...     A --> B
        ...     B --> C
        ... '''
        >>> print(render_mermaid(diagram))
    """
    renderer = MermaidAsciiRenderer()
    renderer.parse(mermaid_text)
    return renderer.render()


if __name__ == "__main__":
    # 測試範例
    test_diagram = """
    flowchart TD
        A[Start]
        B[Process]
        C[End]
        A --> B
        B --> C
    """

    from mermaid_ascii.messages import PROGRAM_NAME
    print(f"=== {PROGRAM_NAME} 渲染結果 ===")
    print(render_mermaid(test_diagram))
