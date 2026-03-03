#!/usr/bin/env python3
"""
Mermaid ASCII CLI 入口

支援將 Mermaid 圖表渲染為 ASCII 或 Unicode 藝術，支援檔案和 stdin 輸入。

用法:
    # 從檔案輸入
    python render.py --input diagram.mmd --ascii

    # 從 stdin 輸入（pipe）
    cat diagram.mmd | python render.py --unicode

    # 指定輸出格式
    python render.py -i diagram.mmd --ascii    # 純 ASCII（無 Unicode）
    python render.py -i diagram.mmd --unicode  # 使用 Unicode 方框字元
"""

import sys
import argparse
from pathlib import Path
from typing import Optional

from mermaid_ascii.mermaid_ascii_renderer import MermaidAsciiRenderer
from mermaid_ascii.messages import (
    ERROR_EMPTY_INPUT,
    ERROR_RENDER_FAILED,
    ERROR_FILE_NOT_FOUND,
    ERROR_READ_INPUT_FAILED,
    ERROR_PREFIX,
    RENDER_ERROR_PREFIX,
    IO_ERROR_PREFIX,
    UNEXPECTED_ERROR_PREFIX,
    INTERRUPT_MESSAGE,
    PROGRAM_NAME,
    PROGRAM_DESCRIPTION,
    PROGRAM_VERSION,
    INPUT_OPTION_HELP,
    INPUT_OPTION_METAVAR,
    ASCII_OPTION_HELP,
    UNICODE_OPTION_HELP,
    CLI_EXAMPLES,
)


class ASCIIRenderer:
    """ASCII 渲染管理器，支援 ASCII/Unicode 輸出模式"""

    def __init__(self, use_unicode: bool = True):
        """
        初始化渲染器

        Args:
            use_unicode: 是否使用 Unicode 字元（True）或純 ASCII（False）
        """
        self.use_unicode = use_unicode

    def render(self, mermaid_text: str) -> str:
        """
        渲染 Mermaid 文本為 ASCII/Unicode

        Args:
            mermaid_text: Mermaid 圖表語法

        Returns:
            渲染後的 ASCII/Unicode 輸出

        Raises:
            ValueError: 如果 Mermaid 文本格式無效
        """
        if not mermaid_text.strip():
            raise ValueError(ERROR_EMPTY_INPUT)

        renderer = MermaidAsciiRenderer()
        try:
            renderer.parse(mermaid_text)
            output = renderer.render()

            if not self.use_unicode:
                output = self._convert_to_ascii(output)

            return output
        except Exception as error:
            raise ValueError(ERROR_RENDER_FAILED.format(error=error)) from error

    @staticmethod
    def _convert_to_ascii(text: str) -> str:
        """
        將 Unicode 方框字元轉換為純 ASCII 等效字元

        Args:
            text: 包含 Unicode 方框字元的文本

        Returns:
            使用純 ASCII 等效的文本
        """
        unicode_to_ascii_map = {
            # 方框字元
            "┌": "+",
            "─": "-",
            "┐": "+",
            "│": "|",
            "└": "+",
            "┘": "+",
            # 圓角字元
            "╭": "+",
            "╮": "+",
            "╰": "+",
            "╯": "+",
            # 菱形字元
            "◇": "*",
            # 箭頭
            "→": "->",
            "↓": "|",
            "↑": "^",
            "←": "<-",
        }

        result = text
        for unicode_char, ascii_char in unicode_to_ascii_map.items():
            result = result.replace(unicode_char, ascii_char)

        return result

    @staticmethod
    def read_input(input_file: Optional[str]) -> str:
        """
        從檔案或 stdin 讀取輸入

        Args:
            input_file: 輸入檔案路徑，若為 None 則從 stdin 讀取

        Returns:
            讀取的內容

        Raises:
            FileNotFoundError: 如果指定的檔案不存在
            IOError: 如果讀取失敗
        """
        try:
            if input_file:
                file_path = Path(input_file)
                if not file_path.exists():
                    raise FileNotFoundError(ERROR_FILE_NOT_FOUND.format(file_path=input_file))
                return file_path.read_text(encoding="utf-8")
            else:
                # 從 stdin 讀取
                return sys.stdin.read()
        except FileNotFoundError as error:
            raise error
        except IOError as error:
            raise IOError(ERROR_READ_INPUT_FAILED.format(error=error)) from error


def setup_argument_parser() -> argparse.ArgumentParser:
    """
    設定命令列參數解析器

    Returns:
        配置完成的 ArgumentParser
    """
    parser = argparse.ArgumentParser(
        prog=PROGRAM_NAME,
        description=PROGRAM_DESCRIPTION,
        epilog=CLI_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # 輸入選項
    parser.add_argument(
        "-i",
        "--input",
        type=str,
        default=None,
        help=INPUT_OPTION_HELP,
        metavar=INPUT_OPTION_METAVAR,
    )

    # 輸出格式選項
    format_group = parser.add_mutually_exclusive_group()
    format_group.add_argument(
        "--ascii",
        action="store_true",
        help=ASCII_OPTION_HELP,
    )
    format_group.add_argument(
        "--unicode",
        action="store_true",
        help=UNICODE_OPTION_HELP,
    )

    # 版本資訊
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {PROGRAM_VERSION}",
    )

    return parser


def main() -> int:
    """
    主程式進入點

    Returns:
        退出碼 (0=成功, 1=失敗)
    """
    parser = setup_argument_parser()
    args = parser.parse_args()

    try:
        # 決定輸出格式（預設 Unicode）
        use_unicode = not args.ascii

        # 讀取輸入
        mermaid_input = ASCIIRenderer.read_input(args.input)

        # 渲染圖表
        renderer = ASCIIRenderer(use_unicode=use_unicode)
        output = renderer.render(mermaid_input)

        # 輸出結果
        print(output)
        return 0

    except FileNotFoundError as error:
        print(f"{ERROR_PREFIX}{error}", file=sys.stderr)
        return 1
    except ValueError as error:
        print(f"{RENDER_ERROR_PREFIX}{error}", file=sys.stderr)
        return 1
    except IOError as error:
        print(f"{IO_ERROR_PREFIX}{error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(INTERRUPT_MESSAGE, file=sys.stderr)
        return 130
    except Exception as error:
        print(f"{UNEXPECTED_ERROR_PREFIX}{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
