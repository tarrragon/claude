"""
worktree merge 與 cleanup 的主 checkout 根（MR）一致性測試（3.4.0-W1-188）。

在 sibling WT（主 checkout 的 git worktree，AR 與 MR 不同）實跑 merge 與 cleanup，
斷言 CAS repo、MergeGate 根、閘門日誌都取 MR，且兩端的 worktree-merge.log 是同一份。
"""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import cleanup_command as cc  # noqa: E402
import merge_cas as mc  # noqa: E402
import worktree_manager as wm  # noqa: E402

LOG_REL = Path(".claude") / "logs" / "worktree-merge.log"


def git(repo, *args):
    proc = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def commit_file(repo, name, text, msg):
    path = Path(repo) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    git(repo, "add", name)
    git(repo, "commit", "-m", msg)


@pytest.fixture
def sibling(tmp_path, monkeypatch):
    """MR 為 main repo；AR 為其 sibling WT（分支 wt-base，與 main 同點）。feat 為待合併分支。"""
    monkeypatch.setattr(mc, "_sleep", lambda _s: None)
    mr = tmp_path / "main"
    mr.mkdir()
    git(mr, "init", "-b", "main")
    git(mr, "config", "user.email", "t@example.com")
    git(mr, "config", "user.name", "t")
    commit_file(mr, "pubspec.yaml", "name: app\n", "base pubspec")
    commit_file(mr, "lib/other.txt", "o\n", "base other")
    git(mr, "checkout", "-b", "feat")
    commit_file(mr, "lib/other.txt", "o-feat\n", "feat edit")
    git(mr, "checkout", "main")
    ar = tmp_path / "sibling-wt"
    git(mr, "worktree", "add", "-b", "wt-base", str(ar))
    slots = tmp_path / "slots"
    slots.mkdir(mode=0o700)
    monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(slots))
    monkeypatch.chdir(ar)
    monkeypatch.setattr(wm, "get_project_root", lambda: str(ar))
    monkeypatch.setattr(cc, "get_project_root", lambda: str(ar))
    monkeypatch.setattr(wm, "get_worktree_list", lambda: [])
    return {"mr": mr.resolve(), "ar": ar.resolve()}


def green_runner(argv, cwd):
    if "pub" in argv:
        art = Path(cwd) / ".dart_tool" / "package_config.json"
        art.parent.mkdir(exist_ok=True)
        art.write_text("{}")
    return 0, "ok"


class TestMergeRoots:
    def test_cas_repo_and_gate_root_are_mr(self, sibling, monkeypatch):
        seen = {}
        real_cas = wm.merge_branch_cas

        def spy_cas(branch, repo=None, **kw):
            seen["cas_repo"] = Path(repo).resolve()
            return real_cas(branch, repo=repo, **kw)

        class spy_gate(wm.MergeGate):  # 子類別保留 isinstance 判斷
            def __init__(self, root, *a, **kw):
                seen["gate_root"] = Path(root).resolve()
                super().__init__(root, *a, **kw)

        monkeypatch.setattr(wm, "merge_branch_cas", spy_cas)
        monkeypatch.setattr(wm, "MergeGate", spy_gate)

        assert wm.cmd_merge(None, branch="feat", gate_runner=green_runner) == 0
        assert seen["cas_repo"] == sibling["mr"]
        assert seen["gate_root"] == sibling["mr"]

    def test_gate_log_lands_in_mr_not_ar(self, sibling):
        assert wm.cmd_merge(None, branch="feat", gate_runner=green_runner) == 0
        assert "[合併閘門]" in (sibling["mr"] / LOG_REL).read_text()
        assert not (sibling["ar"] / LOG_REL).exists()

    def test_skip_gate_log_dir_is_mr(self, sibling):
        assert wm.cmd_merge(None, branch="feat", skip_gate_reason="測試略過") == 0
        assert "測試略過" in (sibling["mr"] / LOG_REL).read_text()
        assert not (sibling["ar"] / LOG_REL).exists()


class TestMergeAndCleanupShareLog:
    def test_same_log_file_for_both_ends(self, sibling):
        assert wm.cmd_merge(None, branch="feat", gate_runner=green_runner) == 0
        victim = str(sibling["mr"].parent / "tmp-wt")
        git(sibling["mr"], "worktree", "add", "-b", "wt-tmp", victim)

        ok, _ = cc._timed_git_remove(victim, [])

        assert ok
        log = (sibling["mr"] / LOG_REL).read_text()
        assert "[合併閘門]" in log and "[清理移除]" in log
        assert not (sibling["ar"] / LOG_REL).exists()


class TestResolveMainRoot:
    def test_falls_back_to_ar_when_mr_unresolvable(self, tmp_path):
        assert mc.resolve_main_checkout_root(str(tmp_path / "nowhere")) == str(tmp_path / "nowhere")

    def test_sibling_wt_resolves_to_mr(self, sibling):
        assert Path(mc.resolve_main_checkout_root(str(sibling["ar"]))).resolve() == sibling["mr"]
