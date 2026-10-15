"""post-commit-fetch-hook 的 commit 判定測試（E2：正向 -C 命中、反向 echo 不命中）。"""

import importlib.util
from pathlib import Path

_HOOK_PATH = Path(__file__).parent.parent / "post-commit-fetch-hook.py"
_spec = importlib.util.spec_from_file_location("post_commit_fetch_hook", _HOOK_PATH)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


def test_dash_c_commit_hits_e2():
    assert hook.is_git_commit_command("git -C x commit -m y") is True


def test_echo_commit_not_hit_e2():
    assert hook.is_git_commit_command("echo git commit") is False


def test_unparseable_not_hit():
    assert hook.is_git_commit_command("git commit -m 'unclosed") is False
