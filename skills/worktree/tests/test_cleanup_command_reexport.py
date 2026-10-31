"""
worktree_manager 對 cleanup_command 的延遲轉出（模組層 __getattr__）

鎖住三件事：轉出清單與 cleanup_command 實際定義的函式一致、取用得到同一物件、
測試注入點與未知名稱不被轉出。另以正向對照記錄「patch 轉出名稱不影響 cleanup 行為」，
說明測試為何必須 patch cleanup_command。
"""

import inspect
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import cleanup_command  # noqa: E402
import worktree_manager  # noqa: E402


def _functions_defined_in_cleanup_command() -> set[str]:
    return {
        name for name, obj in vars(cleanup_command).items()
        if inspect.isfunction(obj) and obj.__module__ == cleanup_command.__name__
    }


def test_reexport_set_matches_functions_defined_in_cleanup_command():
    assert worktree_manager._CLEANUP_REEXPORTS == _functions_defined_in_cleanup_command()


@pytest.mark.parametrize("name", sorted(_functions_defined_in_cleanup_command()))
def test_reexported_name_resolves_to_same_object(name):
    assert getattr(worktree_manager, name) is getattr(cleanup_command, name)


def test_from_import_form_used_by_merge_reminder_hook():
    from worktree_manager import _cleanup_target_arg

    assert _cleanup_target_arg is cleanup_command._cleanup_target_arg


def test_remove_timeout_injection_point_is_not_reexported():
    assert cleanup_command.WORKTREE_REMOVE_TIMEOUT_SECONDS == 300
    with pytest.raises(AttributeError):
        getattr(worktree_manager, "WORKTREE_REMOVE_TIMEOUT_SECONDS")


def test_unknown_name_still_raises_attribute_error():
    with pytest.raises(AttributeError, match="no_such_name"):
        getattr(worktree_manager, "no_such_name")


def test_patching_reexported_name_does_not_reach_cleanup(monkeypatch):
    """正向對照：patch worktree_manager 上的轉出名稱，cleanup_command 內的呼叫照舊。"""
    monkeypatch.setattr(worktree_manager, "_cleanup_target_arg", lambda target: "patched")
    assert cleanup_command._cleanup_target_arg("0.1.1-W9-001") != "patched"


def test_main_dispatches_cleanup_to_cleanup_command(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        cleanup_command, "cmd_cleanup",
        lambda ticket_id, **kw: seen.update(ticket_id=ticket_id, **kw) or 0,
    )
    monkeypatch.setattr(sys, "argv", ["worktree_manager.py", "cleanup", "0.1.1-W9-001", "--force"])
    assert worktree_manager.main() == 0
    assert seen == {"ticket_id": "0.1.1-W9-001", "force": True, "branch": None, "unlock": False}


def test_package_mode_import_resolves_without_cycle():
    """以套件形式（scripts.worktree_manager）載入時，轉出走相對匯入且不形成循環。"""
    code = (
        "import scripts.worktree_manager as wm, scripts.cleanup_command as cc;"
        "assert wm.cmd_cleanup is cc.cmd_cleanup;"
        "assert cc._check_working_tree_clean is wm._check_working_tree_clean"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=SCRIPTS.parent, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
