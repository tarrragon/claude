"""
Test: path_permission 的 .. 路徑段收斂（白名單前綴穿越到受限路徑）

E1/E2：每個穿越輸入配一個正向對照（應放行）與一個直接寫受限路徑的對照（應拒絕）。
"""

import logging
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE_DIR = HOOKS_DIR.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(CLAUDE_DIR))

from lib import path_permission as pp  # noqa: E402

_LOG = logging.getLogger("test_path_permission_dotdot")
ROOT = "/proj/root"


def _allowed(path: str) -> bool:
    return pp.check_file_permission(path, _LOG, root=ROOT)[0]


@pytest.mark.parametrize("path", [
    ".claude/hooks/../../lib/a.dart",
    ".claude/skills/../../test/a_test.dart",
    ".claude/lib/../../lib/a.dart",
    ROOT + "/.claude/skills/../../test/a_test.dart",
    ".claude/hooks/../../../etc/passwd",
    ".claude/hooks/../../../README.md",
    "docs/../../outside.md",
    ".claude\\hooks\\..\\..\\lib\\a.dart",
])
def test_dotdot_traversal_denied(path):
    assert _allowed(path) is False


@pytest.mark.parametrize("path", [
    ".claude/hooks/a.py",
    ".claude/hooks/../skills/a.py",
    ".claude/hooks/./a.py",
    "./docs/x.md",
    ROOT + "/.claude/lib/a.py",
    "docs/a/../b.md",
])
def test_legit_paths_still_allowed(path):
    assert _allowed(path) is True


@pytest.mark.parametrize("path", ["lib/a.dart", "test/a_test.dart", "src/x.dart"])
def test_restricted_paths_still_denied(path):
    assert _allowed(path) is False


def test_normalize_path_collapses_dotdot():
    assert pp.normalize_path(".claude/hooks/../../lib/a.dart", ROOT) == "lib/a.dart"
    assert pp.normalize_path(".claude/hooks/../../../x", ROOT) == "../x"


def test_is_allowed_path_rejects_escape():
    assert pp.is_allowed_path("../README.md", _LOG) is False
