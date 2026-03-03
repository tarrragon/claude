"""Mermaid ASCII CLI 入口單元測試

測試覆蓋:
- 命令列參數解析
- 檔案輸入讀取
- stdin 輸入讀取
- Unicode 和 ASCII 輸出模式
- 錯誤處理
- 命令列主函式
"""

import sys
import tempfile
from pathlib import Path
from io import StringIO
from unittest.mock import patch, MagicMock

import pytest

from mermaid_ascii.scripts.render import (
    ASCIIRenderer,
    setup_argument_parser,
    main,
)


class TestASCIIRenderer:
    """ASCIIRenderer 類別測試"""

    def test_renderer_initialization_unicode_default(self):
        """測試 ASCIIRenderer 預設使用 Unicode"""
        renderer = ASCIIRenderer()
        assert renderer.use_unicode is True

    def test_renderer_initialization_unicode_true(self):
        """測試 ASCIIRenderer 初始化 Unicode 模式"""
        renderer = ASCIIRenderer(use_unicode=True)
        assert renderer.use_unicode is True

    def test_renderer_initialization_unicode_false(self):
        """測試 ASCIIRenderer 初始化 ASCII 模式"""
        renderer = ASCIIRenderer(use_unicode=False)
        assert renderer.use_unicode is False


class TestASCIIRendererRender:
    """ASCIIRenderer.render() 方法測試"""

    def test_render_basic_diagram_unicode(self):
        """測試渲染基本圖表為 Unicode"""
        mermaid_text = """
        flowchart TD
            A[Start]
            B[End]
            A --> B
        """
        renderer = ASCIIRenderer(use_unicode=True)
        result = renderer.render(mermaid_text)

        assert isinstance(result, str)
        assert "Start" in result
        assert "End" in result

    def test_render_basic_diagram_ascii(self):
        """測試渲染基本圖表為 ASCII"""
        mermaid_text = """
        flowchart TD
            A[Start]
            B[End]
            A --> B
        """
        renderer = ASCIIRenderer(use_unicode=False)
        result = renderer.render(mermaid_text)

        assert isinstance(result, str)
        assert "Start" in result
        assert "End" in result
        # ASCII 模式應該沒有 Unicode 方框字元
        assert "┌" not in result

    def test_render_empty_input_raises_error(self):
        """測試渲染空輸入拋出異常"""
        renderer = ASCIIRenderer()
        with pytest.raises(ValueError, match="不能為空"):
            renderer.render("")

    def test_render_whitespace_only_input_raises_error(self):
        """測試渲染只有空白的輸入拋出異常"""
        renderer = ASCIIRenderer()
        with pytest.raises(ValueError, match="不能為空"):
            renderer.render("   \n   \n   ")

    def test_render_complex_diagram(self):
        """測試渲染複雜圖表"""
        mermaid_text = """
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
        renderer = ASCIIRenderer(use_unicode=True)
        result = renderer.render(mermaid_text)

        assert "輸入" in result
        assert "驗證" in result
        assert "正確" in result
        assert "處理" in result
        assert "輸出" in result


class TestASCIIToUnicodeConversion:
    """Unicode 到 ASCII 轉換測試"""

    def test_convert_box_characters(self):
        """測試轉換方框字元"""
        unicode_text = "┌──┐│││└──┘"
        ascii_text = ASCIIRenderer._convert_to_ascii(unicode_text)

        assert "┌" not in ascii_text
        assert "─" not in ascii_text
        assert "┐" not in ascii_text
        assert "└" not in ascii_text
        assert "┘" not in ascii_text

    def test_convert_round_characters(self):
        """測試轉換圓角字元"""
        unicode_text = "╭──╮│││╰──╯"
        ascii_text = ASCIIRenderer._convert_to_ascii(unicode_text)

        assert "╭" not in ascii_text
        assert "╮" not in ascii_text
        assert "╰" not in ascii_text
        assert "╯" not in ascii_text

    def test_convert_diamond_character(self):
        """測試轉換菱形字元"""
        unicode_text = "◇ Test ◇"
        ascii_text = ASCIIRenderer._convert_to_ascii(unicode_text)

        assert "◇" not in ascii_text
        assert "*" in ascii_text

    def test_convert_arrow_characters(self):
        """測試轉換箭頭字元"""
        unicode_text = "→ ↓ ↑ ←"
        ascii_text = ASCIIRenderer._convert_to_ascii(unicode_text)

        assert "→" not in ascii_text
        assert "->" in ascii_text

    def test_convert_mixed_content(self):
        """測試轉換混合內容"""
        unicode_text = "┌─Test─┐│ Node │└─────┘"
        ascii_text = ASCIIRenderer._convert_to_ascii(unicode_text)

        # 驗證 Unicode 字元被替換
        assert "┌" not in ascii_text
        assert "Node" in ascii_text

    def test_convert_preserves_regular_text(self):
        """測試轉換保留普通文本"""
        text = "Hello World 123"
        result = ASCIIRenderer._convert_to_ascii(text)
        assert result == text


class TestReadInput:
    """讀取輸入測試"""

    def test_read_input_from_file(self):
        """測試從檔案讀取輸入"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as f:
            test_content = "flowchart TD\n    A[Test]"
            f.write(test_content)
            f.flush()

            try:
                result = ASCIIRenderer.read_input(f.name)
                assert result == test_content
            finally:
                Path(f.name).unlink()

    def test_read_input_from_file_utf8(self):
        """測試從 UTF-8 檔案讀取輸入"""
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.mmd', delete=False) as f:
            test_content = "flowchart TD\n    A[開始]"
            f.write(test_content)
            f.flush()

            try:
                result = ASCIIRenderer.read_input(f.name)
                assert "開始" in result
            finally:
                Path(f.name).unlink()

    def test_read_input_file_not_found(self):
        """測試讀取不存在的檔案拋出異常"""
        with pytest.raises(FileNotFoundError, match="檔案不存在"):
            ASCIIRenderer.read_input("/nonexistent/file.mmd")

    def test_read_input_from_stdin(self):
        """測試從 stdin 讀取輸入"""
        test_input = "flowchart TD\n    A[Test]"
        with patch('sys.stdin', StringIO(test_input)):
            result = ASCIIRenderer.read_input(None)
            assert result == test_input

    def test_read_input_stdin_empty(self):
        """測試從空 stdin 讀取輸入"""
        with patch('sys.stdin', StringIO("")):
            result = ASCIIRenderer.read_input(None)
            assert result == ""

    def test_read_input_stdin_with_newlines(self):
        """測試從 stdin 讀取多行輸入"""
        test_input = "line1\nline2\nline3"
        with patch('sys.stdin', StringIO(test_input)):
            result = ASCIIRenderer.read_input(None)
            assert result == test_input


class TestArgumentParser:
    """命令列參數解析器測試"""

    def test_parser_creation(self):
        """測試解析器創建"""
        parser = setup_argument_parser()
        assert parser is not None

    def test_parser_help_option(self):
        """測試解析器幫助選項"""
        parser = setup_argument_parser()
        # 驗證幫助選項存在
        with patch('sys.argv', ['prog', '--help']):
            with pytest.raises(SystemExit):
                parser.parse_args()

    def test_parser_version_option(self):
        """測試解析器版本選項"""
        parser = setup_argument_parser()
        with patch('sys.argv', ['prog', '--version']):
            with pytest.raises(SystemExit):
                parser.parse_args()

    def test_parser_input_short_option(self):
        """測試 -i 短選項"""
        parser = setup_argument_parser()
        args = parser.parse_args(['-i', 'test.mmd'])
        assert args.input == 'test.mmd'

    def test_parser_input_long_option(self):
        """測試 --input 長選項"""
        parser = setup_argument_parser()
        args = parser.parse_args(['--input', 'test.mmd'])
        assert args.input == 'test.mmd'

    def test_parser_no_input_defaults_to_none(self):
        """測試不指定 input 預設為 None"""
        parser = setup_argument_parser()
        args = parser.parse_args([])
        assert args.input is None

    def test_parser_ascii_option(self):
        """測試 --ascii 選項"""
        parser = setup_argument_parser()
        args = parser.parse_args(['--ascii'])
        assert args.ascii is True
        assert args.unicode is False

    def test_parser_unicode_option(self):
        """測試 --unicode 選項"""
        parser = setup_argument_parser()
        args = parser.parse_args(['--unicode'])
        assert args.unicode is True
        assert args.ascii is False

    def test_parser_no_format_option_defaults(self):
        """測試不指定格式選項的預設值"""
        parser = setup_argument_parser()
        args = parser.parse_args([])
        assert args.ascii is False
        assert args.unicode is False

    def test_parser_mutually_exclusive_format_options(self):
        """測試 ASCII 和 Unicode 選項互斥"""
        parser = setup_argument_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(['--ascii', '--unicode'])

    def test_parser_complex_arguments(self):
        """測試複雜的參數組合"""
        parser = setup_argument_parser()
        args = parser.parse_args(['-i', 'diagram.mmd', '--ascii'])
        assert args.input == 'diagram.mmd'
        assert args.ascii is True


class TestMainFunction:
    """main() 函式測試"""

    def test_main_success_with_file_input_unicode(self):
        """測試 main 函式成功執行 (檔案輸入, Unicode)"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as f:
            f.write("flowchart TD\n    A[Test]")
            f.flush()

            try:
                with patch('sys.argv', ['prog', '-i', f.name, '--unicode']):
                    with patch('builtins.print') as mock_print:
                        exit_code = main()
                        assert exit_code == 0
                        mock_print.assert_called_once()
            finally:
                Path(f.name).unlink()

    def test_main_success_with_file_input_ascii(self):
        """測試 main 函式成功執行 (檔案輸入, ASCII)"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as f:
            f.write("flowchart TD\n    A[Test]")
            f.flush()

            try:
                with patch('sys.argv', ['prog', '-i', f.name, '--ascii']):
                    with patch('builtins.print') as mock_print:
                        exit_code = main()
                        assert exit_code == 0
            finally:
                Path(f.name).unlink()

    def test_main_success_with_stdin_input(self):
        """測試 main 函式成功執行 (stdin 輸入)"""
        test_input = "flowchart TD\n    A[Test]"

        with patch('sys.argv', ['prog']):
            with patch('sys.stdin', StringIO(test_input)):
                with patch('builtins.print') as mock_print:
                    exit_code = main()
                    assert exit_code == 0

    def test_main_file_not_found_error(self):
        """測試 main 函式檔案不存在錯誤"""
        with patch('sys.argv', ['prog', '-i', '/nonexistent/file.mmd']):
            with patch('sys.stderr', StringIO()):
                exit_code = main()
                assert exit_code == 1

    def test_main_invalid_mermaid_error(self):
        """測試 main 函式無效 Mermaid 文本錯誤"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as f:
            f.write("")  # 空檔案
            f.flush()

            try:
                with patch('sys.argv', ['prog', '-i', f.name]):
                    with patch('sys.stderr', StringIO()):
                        exit_code = main()
                        assert exit_code == 1
            finally:
                Path(f.name).unlink()

    def test_main_keyboard_interrupt(self):
        """測試 main 函式鍵盤中斷"""
        with patch('sys.argv', ['prog']):
            with patch('sys.stdin', StringIO("")):
                with patch('sys.stdin.read', side_effect=KeyboardInterrupt()):
                    with patch('sys.stderr', StringIO()):
                        exit_code = main()
                        assert exit_code == 130

    def test_main_default_uses_unicode(self):
        """測試 main 函式預設使用 Unicode"""
        test_input = "flowchart TD\n    A[Test]"

        with patch('sys.argv', ['prog']):
            with patch('sys.stdin', StringIO(test_input)):
                with patch('builtins.print') as mock_print:
                    main()
                    # 驗證輸出包含 Unicode 字元
                    output = mock_print.call_args[0][0]
                    # 應該包含至少一個 Unicode 字元
                    assert any(ord(c) > 127 for c in output)

    def test_main_ascii_flag_disables_unicode(self):
        """測試 main 函式 ASCII 旗標禁用 Unicode"""
        test_input = "flowchart TD\n    A[Test]"

        with patch('sys.argv', ['prog', '--ascii']):
            with patch('sys.stdin', StringIO(test_input)):
                with patch('builtins.print') as mock_print:
                    main()
                    output = mock_print.call_args[0][0]
                    # ASCII 模式不應該有 Unicode 方框字元
                    assert "┌" not in output
                    assert "└" not in output


class TestEdgeCases:
    """邊界情況和異常處理測試"""

    def test_render_with_invalid_mermaid_syntax(self):
        """測試渲染無效 Mermaid 語法"""
        renderer = ASCIIRenderer()
        # 即使語法無效，渲染器也應該不拋出異常
        # 而是返回空或部分結果
        try:
            result = renderer.render("invalid syntax")
            assert isinstance(result, str)
        except ValueError:
            # 也接受 ValueError
            pass

    def test_read_input_with_large_file(self):
        """測試讀取大型檔案"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as f:
            # 建立一個大型檔案 (100KB)
            large_content = "flowchart TD\n" + "    A[Line]\n" * 10000
            f.write(large_content)
            f.flush()

            try:
                result = ASCIIRenderer.read_input(f.name)
                assert len(result) > 100000
            finally:
                Path(f.name).unlink()

    def test_render_very_long_label(self):
        """測試渲染非常長的標籤"""
        long_label = "A" * 1000
        mermaid_text = f"""
        flowchart TD
            A[{long_label}]
        """
        renderer = ASCIIRenderer()
        result = renderer.render(mermaid_text)
        assert long_label in result

    def test_convert_to_ascii_no_unicode(self):
        """測試轉換沒有 Unicode 字元的文本"""
        text = "Hello World 123"
        result = ASCIIRenderer._convert_to_ascii(text)
        assert result == text

    def test_main_with_unicode_content(self):
        """測試 main 函式處理 Unicode 內容"""
        test_input = "flowchart TD\n    A[開始]\n    B[結束]\n    A --> B"

        with patch('sys.argv', ['prog']):
            with patch('sys.stdin', StringIO(test_input)):
                with patch('builtins.print') as mock_print:
                    exit_code = main()
                    assert exit_code == 0
                    output = mock_print.call_args[0][0]
                    assert "開始" in output
                    assert "結束" in output


class TestIntegration:
    """整合測試"""

    def test_end_to_end_file_to_unicode(self):
        """測試端到端 (檔案輸入到 Unicode 輸出)"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as f:
            f.write("""
            flowchart TD
                A[開始]
                B(處理)
                C{決策}
                D[結束]
                A --> B
                B --> C
                C -- Yes --> D
                C -- No --> B
            """)
            f.flush()

            try:
                with patch('sys.argv', ['prog', '-i', f.name]):
                    with patch('builtins.print') as mock_print:
                        exit_code = main()
                        assert exit_code == 0
                        output = mock_print.call_args[0][0]
                        assert "開始" in output
                        assert "處理" in output
                        assert "決策" in output
                        assert "結束" in output
            finally:
                Path(f.name).unlink()

    def test_end_to_end_stdin_to_ascii(self):
        """測試端到端 (stdin 輸入到 ASCII 輸出)"""
        test_input = """
        flowchart LR
            A[Start] --> B[End]
        """

        with patch('sys.argv', ['prog', '--ascii']):
            with patch('sys.stdin', StringIO(test_input)):
                with patch('builtins.print') as mock_print:
                    exit_code = main()
                    assert exit_code == 0
                    output = mock_print.call_args[0][0]
                    assert "Start" in output
                    assert "End" in output
                    # 驗證 ASCII 模式
                    assert "┌" not in output

    def test_complex_diagram_full_pipeline(self):
        """測試複雜圖表的完整流程"""
        complex_diagram = """
        flowchart TD
            Start[開始輸入]
            Validate(驗證資料)
            CheckValid{資料有效?}
            Process[處理流程]
            Save(保存結果)
            CheckSave{保存成功?}
            Success[成功完成]
            Error[處理錯誤]

            Start --> Validate
            Validate --> CheckValid
            CheckValid -- 是 --> Process
            CheckValid -- 否 --> Error
            Process --> Save
            Save --> CheckSave
            CheckSave -- 是 --> Success
            CheckSave -- 否 --> Error
        """

        renderer = ASCIIRenderer(use_unicode=True)
        result = renderer.render(complex_diagram)

        # 驗證所有節點都在輸出中
        assert "開始輸入" in result
        assert "驗證資料" in result
        assert "資料有效" in result
        assert "處理流程" in result
        assert "保存結果" in result
        assert "成功完成" in result
        assert "處理錯誤" in result
