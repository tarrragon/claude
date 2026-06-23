"""W2-010: lib/ 內 from hook_utils import 正規化測試。

背景：lib/common_functions.py 與 lib/markdown_formatter.py 原以
`from hook_utils import` 跨目錄依賴 .claude/hooks/hook_utils/（lib → hooks 反向
依賴，且靠 caller 的 sys.path 隱式生效）。本票將其改為依賴 lib 自身模組。

涵蓋：
- lib/hook_io.py 補 read_json_from_stdin(logger)（與 hook_utils 行為等價：
  空輸入→None、有效 JSON→dict、解析失敗→None+logger.info）
- lib/common_functions.py 不再 from hook_utils import（get_project_root 自 lib）
- lib/markdown_formatter.py 不再 from hook_utils import；script 模式 import 可解析
"""
from __future__ import annotations

import io
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_CLAUDE_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_CLAUDE_ROOT))

_LIB_DIR = _CLAUDE_ROOT / "lib"
_COMMON_FUNCTIONS_SRC = _LIB_DIR / "common_functions.py"
_MARKDOWN_FORMATTER_SRC = _LIB_DIR / "markdown_formatter.py"


class TestReadJsonFromStdinInLibHookIo(unittest.TestCase):
    """lib.hook_io 提供與 hook_utils 等價的 read_json_from_stdin。"""

    def _call(self, stdin_text: str):
        from lib.hook_io import read_json_from_stdin

        logger = MagicMock()
        with patch("sys.stdin", io.StringIO(stdin_text)):
            return read_json_from_stdin(logger), logger

    def test_valid_json_returns_dict(self):
        result, _ = self._call('{"tool_input": {"file_path": "a.md"}}')
        self.assertEqual(result, {"tool_input": {"file_path": "a.md"}})

    def test_empty_input_returns_none(self):
        result, _ = self._call("   \n  ")
        self.assertIsNone(result)

    def test_invalid_json_returns_none_and_logs(self):
        result, logger = self._call("{not valid json")
        self.assertIsNone(result)
        logger.info.assert_called()


class TestCommonFunctionsNoHookUtils(unittest.TestCase):
    """lib/common_functions.py 不再依賴 hook_utils，get_project_root 自 lib。"""

    def test_source_has_no_hook_utils_import(self):
        src = _COMMON_FUNCTIONS_SRC.read_text(encoding="utf-8")
        self.assertNotIn("from hook_utils import", src)
        self.assertNotIn("import hook_utils", src)

    def test_get_project_root_callable_via_package(self):
        from lib.common_functions import get_project_root

        self.assertTrue(callable(get_project_root))
        self.assertIsInstance(get_project_root(), str)


class TestMarkdownFormatterNoHookUtils(unittest.TestCase):
    """lib/markdown_formatter.py 不再依賴 hook_utils；script 模式 import 可解析。"""

    def test_source_has_no_hook_utils_import(self):
        src = _MARKDOWN_FORMATTER_SRC.read_text(encoding="utf-8")
        self.assertNotIn("from hook_utils import", src)
        self.assertNotIn("import hook_utils", src)

    def test_script_mode_empty_stdin_exits_zero(self):
        """空 stdin → read_json_from_stdin 回 None → sys.exit(0)，無 ImportError。"""
        proc = subprocess.run(
            [sys.executable, str(_MARKDOWN_FORMATTER_SRC)],
            input="",
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertNotIn("ModuleNotFoundError", proc.stderr)
        self.assertNotIn("ImportError", proc.stderr)


if __name__ == "__main__":
    unittest.main()
