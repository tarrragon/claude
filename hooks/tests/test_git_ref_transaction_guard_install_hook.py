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


def _install_shim_with_fake_uv(repo, tmp_path, uv_rc):
    """安裝 shim，並讓 repo 內存在 guard 檔、PATH 內的 uv 以 uv_rc 結束。
    uv_rc 為 None 時 PATH 不含 uv（模擬 rc=127）。回傳 env。"""
    _run_installer(repo)
    guard = repo / ".claude" / "hooks" / "git-ref-transaction-content-guard.py"
    guard.parent.mkdir(parents=True, exist_ok=True)
    guard.write_text("", encoding="utf-8")
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir()
    if uv_rc is not None:
        uv = fakebin / "uv"
        uv.write_text(f"#!/bin/sh\nexit {uv_rc}\n", encoding="utf-8")
        uv.chmod(0o755)
    # 系統路徑不含 uv（uv 在 homebrew / ~/.local），故 None 即 127
    return {"PATH": f"{fakebin}:/usr/bin:/bin", "HOME": str(tmp_path),
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def _commit(repo, env):
    (repo / "f.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "f.txt"], cwd=str(repo), env=env, check=True)
    return subprocess.run(["git", "commit", "-qm", "m"], cwd=str(repo),
                          capture_output=True, text=True, env=env)


class TestShimExitSemantics:
    def test_guard_block_code_aborts_ref_write(self, scratch_repo, tmp_path):
        env = _install_shim_with_fake_uv(
            scratch_repo, tmp_path, hook_module.GUARD_BLOCK_EXIT_CODE)
        result = _commit(scratch_repo, env)
        assert result.returncode != 0
        head = subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD"],
                              cwd=str(scratch_repo), capture_output=True, env=env)
        assert head.returncode != 0

    @pytest.mark.parametrize("rc", [1, 2, 101])
    def test_uv_failure_fails_open_with_warning(self, scratch_repo, tmp_path, rc):
        env = _install_shim_with_fake_uv(scratch_repo, tmp_path, rc)
        result = _commit(scratch_repo, env)
        assert result.returncode == 0, result.stderr
        assert "reference-transaction" in result.stderr

    def test_uv_missing_fails_open_with_warning(self, scratch_repo, tmp_path):
        env = _install_shim_with_fake_uv(scratch_repo, tmp_path, None)
        result = _commit(scratch_repo, env)
        assert result.returncode == 0, result.stderr
        assert "reference-transaction" in result.stderr


class TestShimVersion:
    def test_body_carries_version_marker(self):
        assert f"shim-version: {hook_module.SHIM_VERSION}" in hook_module._shim_body()

    def test_old_shim_without_version_is_upgraded(self, scratch_repo):
        target = scratch_repo / ".git" / "hooks" / hook_module.HOOK_FILENAME
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            f"#!/bin/sh\n{hook_module.SHIM_MARKER} -- old\nexec uv run --quiet x\n",
            encoding="utf-8")
        _run_installer(scratch_repo)
        assert f"shim-version: {hook_module.SHIM_VERSION}" in target.read_text(encoding="utf-8")


class TestShimWarningRcExpansion:
    def test_rc_is_brace_delimited_before_fullwidth_punctuation(self):
        """警告訊息中 rc 須寫成 ${rc}。

        bash 在 C locale 會把緊接的全形標點位元組併入變數名，`$rc）` 展開為空值並輸出亂碼，
        使「guard 啟動失敗（rc=...）」看不到實際離開碼。
        """
        body = hook_module._shim_body()
        assert "rc=${rc}" in body
        assert "rc=$rc）" not in body


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
