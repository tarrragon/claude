"""
Test: git-ref-transaction-guard-install-hook（SessionStart，冪等安裝
`.git/hooks/reference-transaction` shim）。

驗證項目：
1. `_shim_body`：內容含 SHIM_MARKER 與 prepared 狀態過濾
2. `main()` 整合行為（以拋棄式 git repo 隔離）：
   - 目標檔案不存在 -> 寫入、可執行
   - 目標檔案已存在且含 SHIM_MARKER -> 覆寫更新
   - 目標檔案已存在但不含 SHIM_MARKER（使用者自訂 hook）-> 不覆寫，
     stderr 含可見 WARNING
   - 冪等：內容已是最新版本時重跑不報錯（第二次呼叫仍 exit 0）
   - 非 git repo（無 `.git`）-> 略過，exit 0，不建立任何檔案

Source: 0.2.1-W3-1151
"""

import importlib.util
import stat
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE_DIR = HOOKS_DIR.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(CLAUDE_DIR))

_spec = importlib.util.spec_from_file_location(
    "git_ref_transaction_guard_install_hook",
    HOOKS_DIR / "git-ref-transaction-guard-install-hook.py",
)
hook_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook_module)


def _run_git(args, cwd):
    result = subprocess.run(["git"] + args, cwd=str(cwd), capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


@pytest.fixture()
def scratch_repo(tmp_path):
    repo = tmp_path / "scratch"
    repo.mkdir()
    _run_git(["init", "-q"], cwd=repo)
    return repo


def _run_installer(repo):
    result = subprocess.run(
        [sys.executable, str(HOOKS_DIR / "git-ref-transaction-guard-install-hook.py")],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"},
    )
    return result


class TestShimBody:
    def test_contains_marker(self):
        body = hook_module._shim_body()
        assert hook_module.SHIM_MARKER in body

    def test_only_runs_target_on_prepared_state(self):
        body = hook_module._shim_body()
        assert 'if [ "$1" != "prepared" ]; then' in body


class TestInstall:
    def test_installs_when_absent(self, scratch_repo):
        target = scratch_repo / ".git" / "hooks" / hook_module.HOOK_FILENAME
        assert not target.exists()

        result = _run_installer(scratch_repo)

        assert result.returncode == 0
        assert target.exists()
        assert hook_module.SHIM_MARKER in target.read_text(encoding="utf-8")
        assert target.stat().st_mode & stat.S_IXUSR

    def test_idempotent_second_run(self, scratch_repo):
        _run_installer(scratch_repo)
        result = _run_installer(scratch_repo)
        assert result.returncode == 0

    def test_overwrites_stale_marker_content(self, scratch_repo):
        target = scratch_repo / ".git" / "hooks" / hook_module.HOOK_FILENAME
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            f"#!/bin/sh\n{hook_module.SHIM_MARKER} -- 舊版本\nexit 0\n",
            encoding="utf-8",
        )

        result = _run_installer(scratch_repo)

        assert result.returncode == 0
        assert target.read_text(encoding="utf-8") == hook_module._shim_body()

    def test_does_not_overwrite_foreign_hook(self, scratch_repo):
        target = scratch_repo / ".git" / "hooks" / hook_module.HOOK_FILENAME
        target.parent.mkdir(parents=True, exist_ok=True)
        foreign_content = "#!/bin/sh\necho custom user hook\nexit 0\n"
        target.write_text(foreign_content, encoding="utf-8")

        result = _run_installer(scratch_repo)

        assert result.returncode == 0
        assert target.read_text(encoding="utf-8") == foreign_content
        assert "非本機制所裝" in result.stderr

    def test_non_git_repo_skips_without_error(self, tmp_path):
        non_repo = tmp_path / "not-a-repo"
        non_repo.mkdir()

        result = _run_installer(non_repo)

        assert result.returncode == 0
        assert not (non_repo / ".git").exists()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
