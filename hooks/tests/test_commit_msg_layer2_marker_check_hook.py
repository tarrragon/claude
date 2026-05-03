"""commit-msg-layer2-marker-check-hook 單元測試（W17-126）。

涵蓋情境：
1. framework + `Layer 2 by <agent>` → 通過（無警告）
2. framework + `Layer 2 N/A by <理由 ≥ 10 字元>` → 通過（無警告）
3. framework + `Layer 2 N/A by <理由 < 10 字元>` → 警告（理由不足）
4. framework + 無標記 → 警告
5. 非 framework → skip（無警告）
6. merge commit → skip（無警告，即使 framework）
7. `[skip layer2]` 標記 → skip（無警告）
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


HOOK_PATH = Path(__file__).resolve().parent.parent / "commit-msg-layer2-marker-check-hook.py"


def _load_hook_module():
    """以檔案路徑動態載入 hook（檔名含連字號無法直接 import）。"""
    spec = importlib.util.spec_from_file_location("layer2_marker_hook", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["layer2_marker_hook"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def hook():
    return _load_hook_module()


@pytest.fixture
def base_input():
    return {
        "tool_name": "Bash",
        "tool_input": {"command": "git commit -m 'feat: foo'"},
        "tool_response": {
            "stdout": "1 file changed, 1 insertion(+)",
            "stderr": "",
        },
    }


def _make_check(hook, monkeypatch, *, changed_files, commit_msg, parents="abc123"):
    """Patch I/O 層讓 check_layer2_marker 走純邏輯。"""
    monkeypatch.setattr(hook, "_get_changed_files", lambda *a, **kw: changed_files)
    monkeypatch.setattr(hook, "_get_commit_msg", lambda *a, **kw: commit_msg)

    def fake_run_git(args, **kwargs):
        if "%P" in args:
            return parents
        return ""
    monkeypatch.setattr(hook, "run_git", fake_run_git)

    monkeypatch.setattr(hook, "get_project_root", lambda: Path("/tmp"))


def test_framework_with_layer2_by_marker_passes(hook, base_input, monkeypatch):
    _make_check(
        hook, monkeypatch,
        changed_files=[".claude/rules/core/foo.md"],
        commit_msg="docs(W17-126): xxx\n\nLayer 2 by basil-writing-critic\n",
    )
    msg = hook.check_layer2_marker(base_input, base_input["tool_input"], _Logger())
    assert msg is None


def test_framework_with_na_marker_with_sufficient_reason_passes(hook, base_input, monkeypatch):
    _make_check(
        hook, monkeypatch,
        changed_files=[".claude/rules/core/foo.md"],
        commit_msg="docs: xxx\n\nLayer 2 N/A by 純機械同步無新論述新增\n",
    )
    msg = hook.check_layer2_marker(base_input, base_input["tool_input"], _Logger())
    assert msg is None


def test_framework_with_na_marker_short_reason_warns(hook, base_input, monkeypatch):
    _make_check(
        hook, monkeypatch,
        changed_files=[".claude/rules/core/foo.md"],
        commit_msg="docs: xxx\n\nLayer 2 N/A by 短\n",
    )
    msg = hook.check_layer2_marker(base_input, base_input["tool_input"], _Logger())
    assert msg is not None
    assert "Layer 2 補審查建議" in msg


def test_framework_without_marker_warns(hook, base_input, monkeypatch):
    _make_check(
        hook, monkeypatch,
        changed_files=[".claude/rules/core/foo.md", "src/bar.py"],
        commit_msg="docs(W17-126): xxx\n",
    )
    msg = hook.check_layer2_marker(base_input, base_input["tool_input"], _Logger())
    assert msg is not None
    assert ".claude/rules/core/foo.md" in msg
    assert "建議補做 Layer 2" in msg


def test_non_framework_files_skip(hook, base_input, monkeypatch):
    _make_check(
        hook, monkeypatch,
        changed_files=["src/foo.py", "tests/test_foo.py"],
        commit_msg="feat: xxx\n",
    )
    msg = hook.check_layer2_marker(base_input, base_input["tool_input"], _Logger())
    assert msg is None


def test_merge_commit_skips_even_with_framework(hook, base_input, monkeypatch):
    _make_check(
        hook, monkeypatch,
        changed_files=[".claude/rules/core/foo.md"],
        commit_msg="Merge branch 'feature' into main\n",
        parents="abc def",  # 多 parent → merge
    )
    msg = hook.check_layer2_marker(base_input, base_input["tool_input"], _Logger())
    assert msg is None


def test_skip_layer2_marker_skips(hook, base_input, monkeypatch):
    _make_check(
        hook, monkeypatch,
        changed_files=[".claude/rules/core/foo.md"],
        commit_msg="docs: xxx [skip layer2]\n",
    )
    msg = hook.check_layer2_marker(base_input, base_input["tool_input"], _Logger())
    assert msg is None


def test_revert_commit_skips(hook, base_input, monkeypatch):
    _make_check(
        hook, monkeypatch,
        changed_files=[".claude/rules/core/foo.md"],
        commit_msg='Revert "docs: xxx"\n',
    )
    msg = hook.check_layer2_marker(base_input, base_input["tool_input"], _Logger())
    assert msg is None


def test_unsuccessful_commit_skips(hook, monkeypatch):
    """commit 未成功（如 nothing to commit）應跳過，避免誤觸發。"""
    input_data = {
        "tool_name": "Bash",
        "tool_input": {"command": "git commit -m 'noop'"},
        "tool_response": {"stdout": "nothing to commit", "stderr": ""},
    }
    msg = hook.check_layer2_marker(input_data, input_data["tool_input"], _Logger())
    assert msg is None


# Marker 解析單元測試（純函式，不需 patch）

@pytest.mark.parametrize("commit_msg,expected", [
    ("docs: foo\n\nLayer 2 by basil-writing-critic", True),
    ("docs: foo\n\nlayer 2 by ginger", True),  # 大小寫不敏感
    ("docs: foo\n\nLayer 2 N/A by 純機械同步無新論述新增", True),
    ("docs: foo\n\nLayer 2 N/A by 短", False),  # 理由 < 10 字元
    ("docs: foo\n", False),
    ("", False),
    ("docs: foo\n\nLayer 2 by ", False),  # 無 agent name
])
def test_has_valid_layer2_marker(hook, commit_msg, expected):
    assert hook.has_valid_layer2_marker(commit_msg) is expected


class _Logger:
    """Dummy logger for tests（避免依賴 hook_utils logging）。"""

    def debug(self, *a, **kw): pass
    def info(self, *a, **kw): pass
    def warning(self, *a, **kw): pass
    def error(self, *a, **kw): pass
