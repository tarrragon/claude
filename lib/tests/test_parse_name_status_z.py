#!/usr/bin/env python3
"""parse_name_status_z 單元測試（git --name-status -z 輸出解析）"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.git_utils import parse_name_status_z


class TestParseNameStatusZ(unittest.TestCase):
    def test_modified(self):
        self.assertEqual(parse_name_status_z("M\0a.py\0"), [("M", None, "a.py")])

    def test_added(self):
        self.assertEqual(parse_name_status_z("A\0b.py\0"), [("A", None, "b.py")])

    def test_deleted(self):
        self.assertEqual(parse_name_status_z("D\0c.py\0"), [("D", None, "c.py")])

    def test_rename_consumes_two_paths(self):
        self.assertEqual(
            parse_name_status_z("R100\0old.py\0new.py\0"),
            [("R100", "old.py", "new.py")],
        )

    def test_copy_consumes_two_paths(self):
        self.assertEqual(
            parse_name_status_z("C75\0src.py\0dst.py\0"),
            [("C75", "src.py", "dst.py")],
        )

    def test_empty_output(self):
        self.assertEqual(parse_name_status_z(""), [])

    def test_mixed_sequence_keeps_alignment(self):
        out = "M\0a.py\0R063\0x.py\0y.py\0D\0z.py\0"
        self.assertEqual(
            parse_name_status_z(out),
            [("M", None, "a.py"), ("R063", "x.py", "y.py"), ("D", None, "z.py")],
        )

    def test_truncated_rename_is_dropped(self):
        self.assertEqual(parse_name_status_z("R100\0only.py\0"), [])


if __name__ == "__main__":
    unittest.main()
