"""
Test: reference-transaction shim 預驗證命中條件的端到端對照（真實 git + 假 uv）。

與 test_git_ref_transaction_guard_install_hook.py 的分工：
- 原檔（hooks-test-gate 會對異動的 hook 執行，單檔上限 60 秒）只保留兩個代表案例：
  命中放行、多 ref 交易含違規被擋（rc=87）。
- 本檔收納其餘「不符即不命中」的對照案例。每個案例都要建 repo、安裝 shim、跑真實
  git，單案例成本高；檔名不符 gate 的命名慣例，故不在 gate 內，但全套件照跑。

假 uv 離開碼為 87（guard 判定阻擋）：命中時 uv 不得被呼叫（寫入成功），
未命中時 uv 必被呼叫並阻擋（每個不符條件都有一個該被擋的輸入）。
"""

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE_DIR = HOOKS_DIR.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(CLAUDE_DIR))

_spec = importlib.util.spec_from_file_location(
    "git_ref_transaction_guard_install_hook_e2e",
    HOOKS_DIR / "git-ref-transaction-guard-install-hook.py",
)
hook_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook_module)


def _run_git(args, cwd):
    result = subprocess.run(["git"] + args, cwd=str(cwd), capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


@pytest.fixture(scope="module")
def _empty_repo_template(tmp_path_factory):
    repo = tmp_path_factory.mktemp("template") / "repo"
    repo.mkdir()
    _run_git(["init", "-q"], cwd=repo)
    return repo


@pytest.fixture()
def scratch_repo(tmp_path, _empty_repo_template):
    repo = tmp_path / "scratch"
    shutil.copytree(_empty_repo_template, repo, symlinks=True)
    return repo


def _run_installer(repo):
    return subprocess.run(
        [sys.executable, str(HOOKS_DIR / "git-ref-transaction-guard-install-hook.py")],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"},
    )


def _install_shim_with_fake_uv(repo, tmp_path, uv_rc):
    _run_installer(repo)
    guard = repo / ".claude" / "hooks" / "git-ref-transaction-content-guard.py"
    guard.parent.mkdir(parents=True, exist_ok=True)
    guard.write_text("", encoding="utf-8")
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir()
    uv = fakebin / "uv"
    uv.write_text(f"#!/bin/sh\nexit {uv_rc}\n", encoding="utf-8")
    uv.chmod(0o755)
    return {"PATH": f"{fakebin}:/usr/bin:/bin", "HOME": str(tmp_path),
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def _commit(repo, env):
    (repo / "f.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "f.txt"], cwd=str(repo), env=env, check=True)
    return subprocess.run(["git", "commit", "-qm", "m"], cwd=str(repo),
                          capture_output=True, text=True, env=env)


class TestShimPrevalidatedMismatch:
    @pytest.fixture()
    def shim_repo(self, scratch_repo, tmp_path):
        env = _install_shim_with_fake_uv(scratch_repo, tmp_path, 0)
        assert _commit(scratch_repo, env).returncode == 0
        self.repo, self.env = scratch_repo, env
        self.calls = tmp_path / "uv-calls.log"
        self.old = self._git("rev-parse", "HEAD")
        self.branch = self._git("symbolic-ref", "HEAD")
        self.new = self._git("commit-tree", "HEAD^{tree}", "-p", self.old, "-m", "n")
        self._git("branch", "other", self.old)  # 須在假 uv 改為阻擋前建立
        uv = tmp_path / "fakebin" / "uv"
        uv.write_text(f"#!/bin/sh\necho called >> {self.calls}\ncat >/dev/null\nexit 87\n",
                      encoding="utf-8")
        uv.chmod(0o755)
        return scratch_repo

    def _git(self, *args, extra_env=None):
        env = dict(self.env, **(extra_env or {}))
        r = subprocess.run(["git", *args], cwd=str(self.repo), capture_output=True,
                           text=True, env=env)
        if extra_env is None:
            assert r.returncode == 0, r.stderr
            return r.stdout.strip()
        return r

    def _called(self):
        return self.calls.exists()

    def test_no_env_runs_python(self, shim_repo):
        r = self._git("update-ref", self.branch, self.new, self.old, extra_env={})
        assert r.returncode != 0
        assert self._called()

    def test_ref_mismatch_same_tip_other_branch_not_hit(self, shim_repo):
        """另一分支 tip 與 old 相同，env 綁的是別的 ref，不得命中。"""
        pv = f"{self.new}:{self.old}:{self.branch}"
        r = self._git("update-ref", "refs/heads/other", self.new, self.old,
                      extra_env={"GUARD_PREVALIDATED": pv})
        assert r.returncode != 0
        assert self._called()

    def test_new_mismatch_not_hit(self, shim_repo):
        other_new = self._git("commit-tree", "HEAD^{tree}", "-p", self.old, "-m", "x")
        pv = f"{other_new}:{self.old}:{self.branch}"
        r = self._git("update-ref", self.branch, self.new, self.old,
                      extra_env={"GUARD_PREVALIDATED": pv})
        assert r.returncode != 0 and self._called()

    def test_old_mismatch_not_hit(self, shim_repo):
        pv = f"{self.new}:{self.new}:{self.branch}"
        r = self._git("update-ref", self.branch, self.new, self.old,
                      extra_env={"GUARD_PREVALIDATED": pv})
        assert r.returncode != 0 and self._called()

    @pytest.mark.parametrize("pv", ["garbage", "::", "ZZ:ZZ:refs/heads/main", "a:b:HEAD"])
    def test_malformed_env_not_hit(self, shim_repo, pv):
        r = self._git("update-ref", self.branch, self.new, self.old,
                      extra_env={"GUARD_PREVALIDATED": pv})
        assert r.returncode != 0 and self._called()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
