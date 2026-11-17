"""_classify_paths 對豁免路徑（docs/、頂層文件）的判定（#101）。

放寬：全為豁免路徑的 where.files 不要求 worktree。
正向對照：非豁免路徑、外部 .claude/、外部絕對路徑、判定失敗仍落 other/ext（阻擋側）。
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).parent.parent
_TICKET_HOOKS_DIR = _HOOKS_DIR.parent / "skills" / "ticket" / "hooks"
sys.path.insert(0, str(_TICKET_HOOKS_DIR))
_spec = importlib.util.spec_from_file_location(
    "agent_dispatch_validation_hook_exempt",
    _TICKET_HOOKS_DIR / "agent-dispatch-validation-hook.py",
)
_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hook)

MAIN, EXT, OTHER = (True, False, False), (False, True, False), (False, False, True)
ROOT = "/a/proj"


@pytest.mark.parametrize("path,expected", [
    # 放寬：豁免路徑視同主 repo
    ("docs/work-logs/x.md", MAIN),
    ("docs/roadmap.md", MAIN),
    ("CLAUDE.md", MAIN),
    ("README.md", MAIN),
    ("sub/dir/README.md", MAIN),
    ("/a/proj/docs/x.md", MAIN),
    ("docs\\x.md", MAIN),
    # 正向對照：非豁免仍擋
    ("lib/x.dart", OTHER),
    ("src/x.py", OTHER),
    ("test/x_test.dart", OTHER),
    ("/a/proj/lib/x.dart", OTHER),
    ("/a/proj2/docs/x.md", OTHER),
    ("/tmp/other/docs/x.md", OTHER),
    ("docs_extra/x.md", OTHER),
    # 外部 .claude/ 仍判外部
    ("/b/other/.claude/hooks/x.py", EXT),
])
def test_classify_exempt(path, expected):
    assert _hook._classify_paths([path], ROOT) == expected


def test_mixed_docs_and_code_still_blocks():
    m, e, o = _hook._classify_paths(["docs/x.md", "lib/x.dart"], ROOT)
    assert m and o


def test_empty_root_fails_closed():
    assert _hook._classify_paths(["docs/x.md"], "") == OTHER


def test_checker_load_failure_fails_closed(monkeypatch):
    def boom():
        raise RuntimeError("no list")
    monkeypatch.setattr(_hook, "_load_exempt_checker", boom)
    assert _hook._classify_paths(["docs/x.md"], ROOT) == OTHER


def test_checker_none_fails_closed(monkeypatch):
    monkeypatch.setattr(_hook, "_load_exempt_checker", lambda: None)
    assert _hook._classify_paths(["docs/x.md"], ROOT) == OTHER
