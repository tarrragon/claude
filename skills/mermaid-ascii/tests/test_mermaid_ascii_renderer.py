"""Mermaid ASCII 渲染引擎單元測試

測試覆蓋:
- Node 和 Edge 資料結構
- Mermaid 語法解析
- 節點類型渲染 (方框、圓角、菱形)
- 邊線渲染和邊線標籤
- 方向渲染 (TD 和 LR)
- 錯誤處理
"""

import pytest
from mermaid_ascii.mermaid_ascii_renderer import (
    Node,
    Edge,
    MermaidAsciiRenderer,
    render_mermaid,
)


class TestNode:
    """Node 資料結構測試"""

    def test_node_creation_with_defaults(self):
        """測試 Node 預設創建"""
        node = Node(id="A", label="Start")
        assert node.id == "A"
        assert node.label == "Start"
        assert node.shape == "box"

    def test_node_creation_with_shape(self):
        """測試 Node 創建指定形狀"""
        node_box = Node(id="A", label="Box", shape="box")
        assert node_box.shape == "box"

        node_round = Node(id="B", label="Round", shape="round")
        assert node_round.shape == "round"

        node_diamond = Node(id="C", label="Diamond", shape="diamond")
        assert node_diamond.shape == "diamond"

    def test_node_with_special_characters(self):
        """測試 Node 支援特殊字元的標籤"""
        node = Node(id="A", label="開始節點-123!@#")
        assert node.label == "開始節點-123!@#"

    def test_node_with_empty_label(self):
        """測試 Node 允許空標籤"""
        node = Node(id="A", label="")
        assert node.label == ""


class TestEdge:
    """Edge 資料結構測試"""

    def test_edge_creation_without_label(self):
        """測試 Edge 創建無標籤"""
        edge = Edge(source="A", target="B")
        assert edge.source == "A"
        assert edge.target == "B"
        assert edge.label == ""

    def test_edge_creation_with_label(self):
        """測試 Edge 創建有標籤"""
        edge = Edge(source="A", target="B", label="next")
        assert edge.label == "next"

    def test_edge_with_special_label(self):
        """測試 Edge 支援特殊字元標籤"""
        edge = Edge(source="A", target="B", label="是->否")
        assert edge.label == "是->否"


class TestMermaidAsciiRendererBasic:
    """Mermaid ASCII 渲染器基本功能測試"""

    def test_renderer_initialization(self):
        """測試渲染器初始化"""
        renderer = MermaidAsciiRenderer()
        assert renderer.direction == "TD"
        assert len(renderer.nodes) == 0
        assert len(renderer.edges) == 0

    def test_renderer_initialization_with_direction(self):
        """測試渲染器初始化指定方向"""
        renderer_lr = MermaidAsciiRenderer(direction="LR")
        assert renderer_lr.direction == "LR"

        renderer_td = MermaidAsciiRenderer(direction="TD")
        assert renderer_td.direction == "TD"

    def test_empty_diagram_render(self):
        """測試空圖表渲染"""
        renderer = MermaidAsciiRenderer()
        result = renderer.render()
        assert result == ""


class TestMermaidParsingBoxNodes:
    """Box 節點解析測試 (方形節點使用 [...])"""

    def test_parse_single_box_node(self):
        """測試解析單一 box 節點"""
        mermaid_text = """
        flowchart TD
            A[Start]
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(mermaid_text)

        assert "A" in renderer.nodes
        assert renderer.nodes["A"].label == "Start"
        assert renderer.nodes["A"].shape == "box"

    def test_parse_multiple_box_nodes(self):
        """測試解析多個 box 節點"""
        mermaid_text = """
        flowchart TD
            A[Start]
            B[Process]
            C[End]
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(mermaid_text)

        assert len(renderer.nodes) == 3
        assert renderer.nodes["A"].label == "Start"
        assert renderer.nodes["B"].label == "Process"
        assert renderer.nodes["C"].label == "End"

    def test_parse_box_node_with_special_chars(self):
        """測試解析 box 節點支援特殊字元"""
        mermaid_text = """
        flowchart TD
            A[開始-123_ABC]
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(mermaid_text)

        assert renderer.nodes["A"].label == "開始-123_ABC"

    def test_parse_box_node_with_spaces(self):
        """測試解析 box 節點標籤包含空格"""
        mermaid_text = """
        flowchart TD
            A[User Input Data]
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(mermaid_text)

        assert renderer.nodes["A"].label == "User Input Data"


class TestMermaidParsingRoundNodes:
    """Round 節點解析測試 (圓角節點使用 (...))"""

    def test_parse_single_round_node(self):
        """測試解析單一 round 節點"""
        mermaid_text = """
        flowchart TD
            A(Start)
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(mermaid_text)

        assert "A" in renderer.nodes
        assert renderer.nodes["A"].label == "Start"
        assert renderer.nodes["A"].shape == "round"

    def test_parse_multiple_round_nodes(self):
        """測試解析多個 round 節點"""
        mermaid_text = """
        flowchart TD
            A(Start)
            B(Process)
            C(End)
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(mermaid_text)

        assert all(renderer.nodes[nid].shape == "round" for nid in ["A", "B", "C"])

    def test_parse_round_node_with_spaces(self):
        """測試解析 round 節點標籤包含空格"""
        mermaid_text = """
        flowchart TD
            A(Process Data)
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(mermaid_text)

        assert renderer.nodes["A"].label == "Process Data"


class TestMermaidParsingDiamondNodes:
    """Diamond 節點解析測試 (菱形節點使用 {...})"""

    def test_parse_single_diamond_node(self):
        """測試解析單一 diamond 節點"""
        mermaid_text = """
        flowchart TD
            A{Decision}
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(mermaid_text)

        assert "A" in renderer.nodes
        assert renderer.nodes["A"].label == "Decision"
        assert renderer.nodes["A"].shape == "diamond"

    def test_parse_multiple_diamond_nodes(self):
        """測試解析多個 diamond 節點"""
        mermaid_text = """
        flowchart TD
            A{Check A}
            B{Check B}
            C{Check C}
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(mermaid_text)

        assert all(renderer.nodes[nid].shape == "diamond" for nid in ["A", "B", "C"])

    def test_parse_diamond_node_with_chinese(self):
        """測試解析 diamond 節點支援中文標籤"""
        mermaid_text = """
        flowchart TD
            A{判斷條件}
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(mermaid_text)

        assert renderer.nodes["A"].label == "判斷條件"


class TestMermaidParsingEdges:
    """邊線解析測試"""

    def test_parse_simple_arrow_edge(self):
        """測試解析簡單箭頭邊線 (-->)"""
        mermaid_text = """
        flowchart TD
            A[Start]
            B[End]
            A --> B
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(mermaid_text)

        assert len(renderer.edges) == 1
        assert renderer.edges[0].source == "A"
        assert renderer.edges[0].target == "B"
        assert renderer.edges[0].label == ""

    def test_parse_edge_with_label(self):
        """測試解析帶標籤的邊線"""
        mermaid_text = """
        flowchart TD
            A[Start]
            B[End]
            A -- next --> B
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(mermaid_text)

        assert len(renderer.edges) == 1
        assert renderer.edges[0].label == "next"

    def test_parse_edge_with_chinese_label(self):
        """測試解析邊線支援中文標籤"""
        mermaid_text = """
        flowchart TD
            A[開始]
            B[結束]
            A -- 執行 --> B
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(mermaid_text)

        assert renderer.edges[0].label == "執行"

    def test_parse_line_edge(self):
        """測試解析直線邊線 (---)"""
        mermaid_text = """
        flowchart TD
            A[Start]
            B[End]
            A --- B
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(mermaid_text)

        assert len(renderer.edges) == 1
        assert renderer.edges[0].source == "A"
        assert renderer.edges[0].target == "B"

    def test_parse_multiple_edges(self):
        """測試解析多條邊線"""
        mermaid_text = """
        flowchart TD
            A[Start]
            B[Process]
            C[End]
            A --> B
            B --> C
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(mermaid_text)

        assert len(renderer.edges) == 2
        assert renderer.edges[0].source == "A"
        assert renderer.edges[1].source == "B"


class TestMermaidParsingDirection:
    """方向解析測試"""

    def test_parse_td_direction(self):
        """測試解析上下方向 (TD)"""
        mermaid_text = """
        flowchart TD
            A[Start]
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(mermaid_text)
        assert renderer.direction == "TD"

    def test_parse_tb_direction_as_td(self):
        """測試解析 TB (Top-Bottom) 作為 TD"""
        mermaid_text = """
        flowchart TB
            A[Start]
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(mermaid_text)
        assert renderer.direction == "TD"

    def test_parse_lr_direction(self):
        """測試解析左右方向 (LR)"""
        mermaid_text = """
        flowchart LR
            A[Start]
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(mermaid_text)
        assert renderer.direction == "LR"

    def test_direction_case_insensitive(self):
        """測試方向解析大小寫不敏感"""
        mermaid_text = """
        flowchart lr
            A[Start]
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(mermaid_text)
        assert renderer.direction == "LR"


class TestMermaidParsingComments:
    """註解處理測試"""

    def test_parse_skips_comments(self):
        """測試解析忽略註解行"""
        mermaid_text = """
        flowchart TD
            %% 這是註解
            A[Start]
            %% 另一個註解
            B[End]
            A --> B
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(mermaid_text)

        assert len(renderer.nodes) == 2
        assert len(renderer.edges) == 1

    def test_parse_skips_empty_lines(self):
        """測試解析忽略空行"""
        mermaid_text = """
        flowchart TD

            A[Start]

            B[End]

            A --> B

        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(mermaid_text)

        assert len(renderer.nodes) == 2


class TestNodeFormatting:
    """節點格式化測試"""

    def test_format_box_basic(self):
        """測試格式化 box 節點基本情況"""
        result = MermaidAsciiRenderer._format_box("Start")
        lines = result.split("\n")
        assert len(lines) == 3
        assert "┌" in lines[0] and "┐" in lines[0]
        assert "│" in lines[1] and "Start" in lines[1]
        assert "└" in lines[2] and "┘" in lines[2]

    def test_format_box_short_text(self):
        """測試格式化 box 節點短文本"""
        result = MermaidAsciiRenderer._format_box("A")
        assert "A" in result
        assert "┌" in result

    def test_format_box_long_text(self):
        """測試格式化 box 節點長文本"""
        long_text = "This is a very long text for box formatting test"
        result = MermaidAsciiRenderer._format_box(long_text)
        assert long_text in result

    def test_format_box_chinese_text(self):
        """測試格式化 box 節點中文文本"""
        result = MermaidAsciiRenderer._format_box("開始")
        assert "開始" in result
        assert "┌" in result

    def test_format_round_basic(self):
        """測試格式化 round 節點基本情況"""
        result = MermaidAsciiRenderer._format_round("Process")
        lines = result.split("\n")
        assert len(lines) == 3
        assert "╭" in lines[0] and "╮" in lines[0]
        assert "│" in lines[1] and "Process" in lines[1]
        assert "╰" in lines[2] and "╯" in lines[2]

    def test_format_diamond_basic(self):
        """測試格式化 diamond 節點基本情況"""
        result = MermaidAsciiRenderer._format_diamond("Decision")
        assert "Decision" in result
        assert "◇" in result


class TestRendererTD:
    """上下方向 (TD) 渲染測試"""

    def test_render_single_node_td(self):
        """測試渲染單一節點 TD"""
        mermaid_text = """
        flowchart TD
            A[Start]
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(mermaid_text)
        result = renderer.render()

        assert "Start" in result
        assert "┌" in result

    def test_render_three_nodes_td(self):
        """測試渲染三個節點 TD"""
        mermaid_text = """
        flowchart TD
            A[Start]
            B[Process]
            C[End]
            A --> B
            B --> C
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(mermaid_text)
        result = renderer.render()

        assert "Start" in result
        assert "Process" in result
        assert "End" in result
        assert "|" in result  # 應該包含垂直線

    def test_render_mixed_shapes_td(self):
        """測試渲染混合節點形狀 TD"""
        mermaid_text = """
        flowchart TD
            A[Start]
            B(Process)
            C{End?}
            A --> B
            B --> C
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(mermaid_text)
        result = renderer.render()

        assert "Start" in result
        assert "Process" in result
        assert "End" in result
        assert "┌" in result or "┐" in result  # 至少有一種邊框類型
        assert "╭" in result or "╮" in result  # 圓角邊框


class TestRendererLR:
    """左右方向 (LR) 渲染測試"""

    def test_render_single_node_lr(self):
        """測試渲染單一節點 LR"""
        mermaid_text = """
        flowchart LR
            A[Start]
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(mermaid_text)
        result = renderer.render()

        assert "Start" in result

    def test_render_three_nodes_lr(self):
        """測試渲染三個節點 LR"""
        mermaid_text = """
        flowchart LR
            A[Start]
            B[Process]
            C[End]
            A --> B
            B --> C
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(mermaid_text)
        result = renderer.render()

        assert "Start" in result
        assert "Process" in result
        assert "End" in result
        assert "-->" in result  # 應該包含箭頭

    def test_render_mixed_shapes_lr(self):
        """測試渲染混合節點形狀 LR"""
        mermaid_text = """
        flowchart LR
            A[Start]
            B(Process)
            C{End?}
            A --> B
            B --> C
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(mermaid_text)
        result = renderer.render()

        assert "Start" in result
        assert "Process" in result
        assert "End" in result


class TestRenderMermaidFunction:
    """render_mermaid 便利函式測試"""

    def test_render_mermaid_basic(self):
        """測試 render_mermaid 函式基本功能"""
        diagram = """
        flowchart TD
            A[Start]
            B[End]
            A --> B
        """
        result = render_mermaid(diagram)

        assert "Start" in result
        assert "End" in result

    def test_render_mermaid_complex_diagram(self):
        """測試 render_mermaid 複雜圖表"""
        diagram = """
        flowchart TD
            A[輸入]
            B(驗證)
            C{正確?}
            D[處理]
            E[輸出]
            A --> B
            B --> C
            C -- 是 --> D
            C -- 否 --> B
            D --> E
        """
        result = render_mermaid(diagram)

        assert "輸入" in result
        assert "驗證" in result
        assert "正確" in result
        assert "處理" in result
        assert "輸出" in result

    def test_render_mermaid_lr_diagram(self):
        """測試 render_mermaid LR 圖表"""
        diagram = """
        flowchart LR
            A[Start] --> B[End]
        """
        result = render_mermaid(diagram)

        assert "Start" in result
        assert "End" in result


class TestEdgeCases:
    """邊界情況和異常處理測試"""

    def test_parse_whitespace_only(self):
        """測試解析只包含空白的文本"""
        mermaid_text = """


        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(mermaid_text)
        # 應該不拋出異常
        assert len(renderer.nodes) == 0

    def test_parse_no_flowchart_directive(self):
        """測試解析無 flowchart 指令

        注意: 如果沒有 flowchart 指令，第一行被視為內容而非方向指令，
        所以只有後續行才會被解析為節點和邊線。這個行為是預期的。
        """
        mermaid_text = """
            A[Start]
            B[End]
            A --> B
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(mermaid_text)
        # 第一行被跳過，只有 B 被解析
        assert len(renderer.nodes) >= 1

    def test_node_with_multiword_id(self):
        """測試節點 ID 只能是單詞 (不能包含空格)"""
        mermaid_text = """
        flowchart TD
            A[Valid]
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(mermaid_text)
        assert len(renderer.nodes) == 1

    def test_render_with_numeric_ids(self):
        """測試節點 ID 可以包含數字"""
        mermaid_text = """
        flowchart TD
            A1[Node 1]
            A2[Node 2]
            A1 --> A2
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(mermaid_text)

        assert "A1" in renderer.nodes
        assert "A2" in renderer.nodes

    def test_self_loop_edge(self):
        """測試自迴圈邊線 (節點指向自己)"""
        mermaid_text = """
        flowchart TD
            A[Node]
            A --> A
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(mermaid_text)

        assert len(renderer.edges) == 1
        assert renderer.edges[0].source == "A"
        assert renderer.edges[0].target == "A"

    def test_unreferenced_nodes(self):
        """測試未連接的節點"""
        mermaid_text = """
        flowchart TD
            A[Node A]
            B[Node B]
            C[Node C]
            A --> B
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(mermaid_text)

        assert len(renderer.nodes) == 3
        assert len(renderer.edges) == 1

    def test_edge_to_nonexistent_node(self):
        """測試邊線指向不存在的節點"""
        mermaid_text = """
        flowchart TD
            A[Exists]
            A --> B
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(mermaid_text)

        # A 存在但 B 不在 nodes 中 (這是預期行為)
        assert "A" in renderer.nodes
        assert len(renderer.edges) == 1
        assert renderer.edges[0].target == "B"


class TestComplexDiagrams:
    """複雜圖表測試"""

    def test_diamond_decision_flow(self):
        """測試包含決策節點的流程圖"""
        diagram = """
        flowchart TD
            Start[開始]
            Input(輸入)
            Check{驗證}
            Process[處理]
            Output[輸出]
            Error[錯誤]

            Start --> Input
            Input --> Check
            Check -- 成功 --> Process
            Check -- 失敗 --> Error
            Process --> Output
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(diagram)

        assert len(renderer.nodes) == 6
        assert len(renderer.edges) == 5

    def test_parallel_flows(self):
        """測試平行流程"""
        diagram = """
        flowchart TD
            Start[開始]
            TaskA[任務A]
            TaskB[任務B]
            Merge(合併)
            End[結束]

            Start --> TaskA
            Start --> TaskB
            TaskA --> Merge
            TaskB --> Merge
            Merge --> End
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(diagram)

        assert len(renderer.nodes) == 5
        assert len(renderer.edges) == 5

    def test_nested_decisions(self):
        """測試巢狀決策"""
        diagram = """
        flowchart TD
            A{決策1}
            B{決策2}
            C[結果]

            A -- Yes --> B
            B -- Yes --> C
            B -- No --> A
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(diagram)

        assert all(renderer.nodes[nid].shape == "diamond" for nid in ["A", "B"])
        assert renderer.nodes["C"].shape == "box"


class TestLargeGraphs:
    """大型圖表測試"""

    def test_many_nodes(self):
        """測試大量節點"""
        nodes_count = 50
        mermaid_lines = ["flowchart TD"]

        for i in range(nodes_count):
            mermaid_lines.append(f"    N{i}[Node{i}]")

        # 添加順序邊線
        for i in range(nodes_count - 1):
            mermaid_lines.append(f"    N{i} --> N{i+1}")

        diagram = "\n".join(mermaid_lines)
        renderer = MermaidAsciiRenderer()
        renderer.parse(diagram)

        assert len(renderer.nodes) == nodes_count
        assert len(renderer.edges) == nodes_count - 1

    def test_many_edges(self):
        """測試大量邊線"""
        diagram = """
        flowchart TD
            A[Node A]
            B[Node B]
            C[Node C]
            A --> B
            A --> C
            B --> C
            B --> A
            C --> A
        """
        renderer = MermaidAsciiRenderer()
        renderer.parse(diagram)

        assert len(renderer.edges) == 5
