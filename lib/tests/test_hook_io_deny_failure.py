#!/usr/bin/env python3
"""emit_hook_output：deny 決定輸出失敗須 exit 2 並於 stderr 帶 reason。

E2：print 拋 OSError 且 decision=deny -> SystemExit(2) 且 stderr 含 reason。
E1：同批 fixture 下 allow 輸出失敗維持原行為（例外原樣外拋），與 deny 結果不同。
"""

import sys
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.hook_io import emit_hook_output

REASON = "blocked-by-guard-reason"


def _broken_print(*args, **kwargs):
    raise OSError("stdout closed")


def _call(decision):
    return lambda: emit_hook_output(
        "PreToolUse", None, decision, REASON if decision == "deny" else "ok"
    )


class TestEmitDenyFailure(unittest.TestCase):
    def test_deny_output_failure_exits_2_with_reason_on_stderr(self):
        err = StringIO()
        with patch("builtins.print", _broken_print), patch("sys.stderr", err):
            with self.assertRaises(SystemExit) as cm:
                _call("deny")()
        self.assertEqual(cm.exception.code, 2)
        self.assertIn(REASON, err.getvalue())

    def test_allow_output_failure_keeps_original_behavior(self):
        # E1 對照：allow 同樣輸出失敗，不得轉為 SystemExit，原例外外拋
        with patch("builtins.print", _broken_print):
            with self.assertRaises(OSError):
                _call("allow")()

    def test_no_decision_output_failure_keeps_original_behavior(self):
        with patch("builtins.print", _broken_print):
            with self.assertRaises(OSError):
                emit_hook_output("PreToolUse", "ctx")

    def test_deny_stderr_failure_still_exits_2(self):
        class BadErr:
            def write(self, _):
                raise OSError("stderr closed")

            def flush(self):
                raise OSError("stderr closed")

        with patch("builtins.print", _broken_print), patch("sys.stderr", BadErr()):
            with self.assertRaises(SystemExit) as cm:
                _call("deny")()
        self.assertEqual(cm.exception.code, 2)

    def test_deny_success_unchanged(self):
        out = StringIO()
        with patch("sys.stdout", out):
            _call("deny")()
        self.assertIn(REASON, out.getvalue())


if __name__ == "__main__":
    unittest.main()
