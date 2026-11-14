"""
G1 讀回 hook-logs 的三支 hook：linked worktree 內讀寫皆落主 checkout（3.3.0-W1-204.1.6.9）

涵蓋 agent-commit-verification-hook（scan_hook_errors / dedup state）、
dispatch-stall-reminder-hook（reminded.json）、hook-health-monitor（resolve_hook_log_dir）。

不設 HOOK_TEST_ISOLATION、不設 CLAUDE_PROJECT_DIR：以真實 git linked worktree 為 fixture，
cwd 切到各 checkout 模擬「主 checkout 啟動」「linked worktree 啟動」，
並以雙 checkout 各自寫入模擬並行寫入。
"""

import importlib.util
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from lib import get_hook_log_dir  # noqa: E402
from lib import hook_base  # noqa: E402


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, _HOOKS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


acv = _load("acv_readback", "agent-commit-verification-hook.py")
stall = _load("stall_readback", "dispatch-stall-reminder-hook.py")
monitor = _load("monitor_readback", "hook-health-monitor.py")

ERROR_LOG = "[2026-11-13 10:00:00] ERROR - boom\n"


def _git(cwd: Path, *args: str) -> None:
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    subprocess.run(["git", "-C", str(cwd), *args], check=True,
                   capture_output=True, env=env)


class Checkouts:
    """主 checkout + linked worktree，並提供切換 cwd 的 at()。"""

    def __init__(self, main: Path, wt: Path, monkeypatch):
        self.main, self.wt, self._mp = main, wt, monkeypatch

    def at(self, root: Path) -> Path:
        self._mp.chdir(root)
        hook_base.clear_project_root_cache()
        return Path(hook_base.get_project_root())

    @property
    def main_logs(self) -> Path:
        return self.main / ".claude" / "hook-logs"

    @property
    def wt_logs(self) -> Path:
        return self.wt / ".claude" / "hook-logs"


@pytest.fixture
def co(tmp_path, monkeypatch):
    main = (tmp_path / "main").resolve()
    main.mkdir()
    _git(main, "init", "-q", "-b", "main")
    (main / "CLAUDE.md").write_text("# t\n", encoding="utf-8")
    (main / ".claude").mkdir()
    (main / ".claude" / "keep").write_text("x", encoding="utf-8")
    _git(main, "add", ".")
    _git(main, "commit", "-q", "-m", "init")
    wt = (tmp_path / "wt").resolve()
    _git(main, "worktree", "add", "-q", "-b", "feat", str(wt))
    monkeypatch.delenv("HOOK_TEST_ISOLATION", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    yield Checkouts(main, wt, monkeypatch)
    hook_base.clear_project_root_cache()


def _write_log(dir_: Path, name: str, content: str, age_hours: float = 0) -> Path:
    dir_.mkdir(parents=True, exist_ok=True)
    f = dir_ / name
    f.write_text(content, encoding="utf-8")
    ts = time.time() - age_hours * 3600
    os.utime(f, (ts, ts))
    return f


LOGGER = logging.getLogger("readback-test")


# ----------------------------------------------------------------------------
# agent-commit-verification-hook：scan_hook_errors / dedup state
# ----------------------------------------------------------------------------

class TestAgentCommitVerification:
    def test_scan_from_linked_worktree_reads_main_logs(self, co):
        _write_log(co.main_logs / "hook-x", "a.log", ERROR_LOG)
        root = co.at(co.wt)
        assert acv.scan_hook_errors(str(root), 10, LOGGER) == [("hook-x", 1)]

    def test_scan_from_main_checkout_reads_main_logs(self, co):
        _write_log(co.main_logs / "hook-x", "a.log", ERROR_LOG)
        root = co.at(co.main)
        assert acv.scan_hook_errors(str(root), 10, LOGGER) == [("hook-x", 1)]

    def test_scan_ignores_stray_worktree_local_logs(self, co):
        """worktree 根下殘留的舊日誌不再被讀；只讀主 checkout 合流目錄。"""
        _write_log(co.wt_logs / "stray-hook", "s.log", ERROR_LOG)
        root = co.at(co.wt)
        assert acv.scan_hook_errors(str(root), 10, LOGGER) == []

    def test_parallel_writers_merge_and_both_starts_agree(self, co):
        for checkout, name in ((co.main, "m.log"), (co.wt, "w.log")):
            co.at(checkout)
            _write_log(get_hook_log_dir("hook-x"), name, ERROR_LOG)
        from_wt = acv.scan_hook_errors(str(co.at(co.wt)), 10, LOGGER)
        from_main = acv.scan_hook_errors(str(co.at(co.main)), 10, LOGGER)
        assert from_wt == from_main == [("hook-x", 2)]

    def test_dedup_state_file_same_from_both_checkouts_in_main(self, co):
        p_main = acv._get_error_dedup_state_file(co.at(co.main))
        p_wt = acv._get_error_dedup_state_file(co.at(co.wt))
        assert p_main == p_wt
        assert p_wt.parent == co.main_logs / acv.HOOK_NAME


# ----------------------------------------------------------------------------
# dispatch-stall-reminder-hook：reminded.json 跨 checkout 去重
# ----------------------------------------------------------------------------

class TestDispatchStallReminder:
    @pytest.fixture
    def run_main(self, monkeypatch, capsys):
        monkeypatch.setattr(stall, "build_reminders",
                            lambda *_a, **_k: [("k1", "- T1 line")])
        monkeypatch.setattr(stall, "read_json_from_stdin", lambda _l: {})
        monkeypatch.setattr(stall, "resolve_session_id", lambda _d: "s")

        def _run() -> str:
            assert stall.main() == 0
            return capsys.readouterr().out

        return _run

    def test_wt_start_writes_state_into_main(self, co, run_main):
        co.at(co.wt)
        assert "T1" in run_main()
        assert (co.main_logs / "dispatch-stall-reminder" / "reminded.json").exists()
        assert not (co.wt_logs / "dispatch-stall-reminder" / "reminded.json").exists()

    def test_main_start_writes_state_into_main(self, co, run_main):
        co.at(co.main)
        assert "T1" in run_main()
        assert (co.main_logs / "dispatch-stall-reminder" / "reminded.json").exists()

    def test_dedup_merges_across_checkouts(self, co, run_main):
        """wt 先提醒、主 checkout 再跑：同鍵已去重（跨 checkout 合流）。"""
        co.at(co.wt)
        assert "T1" in run_main()
        co.at(co.main)
        assert run_main().strip() == ""

    def test_new_key_from_other_checkout_still_reminds(self, co, run_main, monkeypatch):
        """合流不會漏提醒：另一 checkout 的新鍵不在已提醒清單，照常提醒。"""
        co.at(co.wt)
        assert "T1" in run_main()
        monkeypatch.setattr(stall, "build_reminders",
                            lambda *_a, **_k: [("k1", "- T1 line"), ("k2", "- T2 line")])
        co.at(co.main)
        out = run_main()
        assert "T2" in out and "T1" not in out


# ----------------------------------------------------------------------------
# hook-health-monitor：resolve_hook_log_dir / _check_single_hook_log
# ----------------------------------------------------------------------------

class TestHookHealthMonitor:
    def test_wt_start_finds_main_log_dir(self, co):
        _write_log(co.main_logs / "foo-hook", "x.log", "ok\n")
        root = co.at(co.wt)
        name, path, found = monitor.resolve_hook_log_dir("foo-hook.py", root)
        assert found is True
        assert path == co.main_logs / "foo-hook"

    def test_main_start_finds_main_log_dir(self, co):
        _write_log(co.main_logs / "foo-hook", "x.log", "ok\n")
        root = co.at(co.main)
        _, path, found = monitor.resolve_hook_log_dir("foo-hook.py", root)
        assert found is True and path == co.main_logs / "foo-hook"

    def test_merged_logs_decide_liveness_main_stale_wt_stray_fresh(self, co):
        """主 checkout 日誌過期、worktree 殘留日誌新鮮：只認合流目錄 -> FAIL。"""
        _write_log(co.main_logs / "foo-hook", "x.log", "ok\n", age_hours=100)
        _write_log(co.wt_logs / "foo-hook", "y.log", "ok\n", age_hours=0)
        root = co.at(co.wt)
        severity, msg, _ = monitor._check_single_hook_log("foo-hook.py", root)
        assert severity == 2 and "[FAIL]" in msg

    def test_parallel_writers_both_visible_from_either_start(self, co):
        for checkout, name in ((co.main, "m.log"), (co.wt, "w.log")):
            co.at(checkout)
            _write_log(get_hook_log_dir("foo-hook"), name, "ok\n")
        r_wt = monitor._check_single_hook_log("foo-hook.py", co.at(co.wt))
        r_main = monitor._check_single_hook_log("foo-hook.py", co.at(co.main))
        assert r_wt == r_main
        assert r_wt[0] == 0
        assert {f.name for f in (co.main_logs / "foo-hook").iterdir()} == {"m.log", "w.log"}
