"""set-acceptance 多值參數的重複旗標形式回歸測試。

`--add A --add B` 與 `--add A B` 兩種形式都應寫入兩條。前者原本只寫入最後
一個值：argparse 的 `nargs="+"` 未搭配 `action="append"` 時，重複出現的旗標
互相覆寫而非累積，且輸出仍回報「新增 1 項」，呼叫端無從察覺條目遺失。

同一形態涵蓋 --check / --uncheck / --remove（皆為 nargs="+"）。
"""

import argparse
import sys
from pathlib import Path

import pytest

_SKILL_ROOT = Path(__file__).resolve().parents[1]
if str(_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_ROOT))

from ticket_system.commands.track import register  # noqa: E402


def _parse(argv):
    root = argparse.ArgumentParser()
    register(root.add_subparsers(dest="command"))
    return root.parse_args(argv)


def _flat(value):
    """把 argparse 結果攤平為單層字串清單，容忍巢狀與扁平兩種形態。"""
    if value is None:
        return []
    out = []
    for item in value:
        if isinstance(item, list):
            out.extend(item)
        else:
            out.append(item)
    return out


class TestRepeatedFlagAccumulates:
    """重複旗標應累積，不應互相覆寫。"""

    def test_add_repeated_flags_keeps_all(self):
        args = _parse(["track", "set-acceptance", "T-1",
                       "--add", "條目 A", "--add", "條目 B", "--add", "條目 C"])
        assert _flat(args.add) == ["條目 A", "條目 B", "條目 C"]

    def test_add_space_separated_still_works(self):
        args = _parse(["track", "set-acceptance", "T-1",
                       "--add", "條目 A", "條目 B"])
        assert _flat(args.add) == ["條目 A", "條目 B"]

    def test_add_mixed_forms(self):
        args = _parse(["track", "set-acceptance", "T-1",
                       "--add", "A", "B", "--add", "C"])
        assert _flat(args.add) == ["A", "B", "C"]

    @pytest.mark.parametrize("flag", ["--check", "--uncheck", "--remove"])
    def test_index_flags_repeated_keeps_all(self, flag):
        args = _parse(["track", "set-acceptance", "T-1", flag, "1", flag, "2"])
        dest = flag.lstrip("-")
        assert _flat(getattr(args, dest)) == ["1", "2"]

    @pytest.mark.parametrize("flag", ["--check", "--uncheck", "--remove"])
    def test_index_flags_space_separated_still_works(self, flag):
        args = _parse(["track", "set-acceptance", "T-1", flag, "1", "2"])
        dest = flag.lstrip("-")
        assert _flat(getattr(args, dest)) == ["1", "2"]
