"""
main 定期全套件：觸發條件、紅燈二分定位、暫停受影響套件的合併與解除（3.5.0-W1-051.2）

套件執行器一律注入假的：flutter 套件看快照內 lib/ 是否有 BROKEN 字樣，skill:foo 套件看
.claude/skills/foo/foo.py 是否有 BROKEN 字樣。名額空閒與啟動子程序以注入函式取代。
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / ".claude"))

import merge_cas as mc  # noqa: E402
import merge_gate as mg  # noqa: E402
import worktree_manager as wm  # noqa: E402

FOO = ".claude/skills/foo/foo.py"


def git(repo, *args):
    proc = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def write(repo, name, text):
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def merge_change(repo, idx, name, text):
    """在 main 上以 --no-ff 合入一個分支（訊息帶分支與票號），回傳合併 commit。"""
    branch = f"b{idx}"
    git(repo, "checkout", "-q", "-b", branch)
    write(repo, name, text)
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", f"change {idx}")
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "-q", "--no-ff", "-m", f"Merge branch '{branch}' (9.9.9-W1-{idx:03d})", branch)
    return git(repo, "rev-parse", "main")


def make_branch(repo, branch, name, text):
    git(repo, "checkout", "-q", "-b", branch)
    write(repo, name, text)
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", f"{branch} edit")
    git(repo, "checkout", "-q", "main")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(mc, "_sleep", lambda _s: None)
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    git(r, "config", "user.email", "t@example.com")
    git(r, "config", "user.name", "t")
    write(r, "pubspec.yaml", "name: app\n")
    write(r, "lib/a.txt", "a\n")
    write(r, FOO, "VALUE = 1\n")
    write(r, ".claude/skills/foo/tests/test_foo.py", "def test_foo():\n    pass\n")
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "base")
    slots = tmp_path / "slots"
    slots.mkdir(mode=0o700)
    monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(slots))
    monkeypatch.chdir(r)
    monkeypatch.setattr(wm, "get_project_root", lambda: str(r))
    monkeypatch.setattr(wm, "get_worktree_list", lambda: [])
    return r


def _suite_of(argv):
    joined = " ".join(argv)
    if "skills/foo" in joined:
        return "skill:foo"
    if "flutter" in joined:
        return "flutter"
    return "other"


class FakeRunner:
    """依快照內容決定紅綠；記錄每次實跑的（套件, 快照 HEAD）。"""

    def __init__(self):
        self.runs = []

    def __call__(self, argv, cwd):
        if "pub" in argv:
            art = Path(cwd) / ".dart_tool" / "package_config.json"
            art.parent.mkdir(exist_ok=True)
            art.write_text("{}")
            return 0, ""
        suite = _suite_of(argv)
        head = git(cwd, "rev-parse", "HEAD")
        self.runs.append((suite, head))
        if suite == "skill:foo":
            broken = "BROKEN" in (Path(cwd) / FOO).read_text()
        else:
            broken = any("BROKEN" in p.read_text() for p in (Path(cwd) / "lib").rglob("*.txt"))
        return (1, "FAILED tests/test_x.py::test_boom\n1 failed") if broken else (0, "1 passed")


def periodic(repo, runner=None, idle=True, launched=None):
    launches = launched if launched is not None else []
    return mg.PeriodicSuite(str(repo), runner=runner or FakeRunner(), slot_idle=lambda: idle,
                            launcher=lambda r: launches.append(r))


def baseline(repo, runner=None):
    """以全綠的定期全套件建立基準（last_run／last_green 指向目前 main）。"""
    ps = periodic(repo, runner)
    result = ps.run()
    assert result["result"] == "green", result
    return git(repo, "rev-parse", "main")


def read_state(repo):
    return json.loads((repo / mg.PERIODIC_STATE_FILE).read_text())


def log_text(repo):
    path = repo / ".claude/logs/worktree-merge.log"
    return path.read_text() if path.exists() else ""


# ---------- 觸發條件（acceptance 1） ----------

class TestTrigger:
    def test_three_merges_idle_does_not_run(self, repo):
        baseline(repo)
        for i in range(3):
            merge_change(repo, i + 1, f"lib/n{i}.txt", "x\n")
        launched = []
        assert periodic(repo, idle=True, launched=launched).maybe_trigger() is None
        assert launched == []

    def test_four_merges_idle_runs(self, repo):
        baseline(repo)
        for i in range(4):
            merge_change(repo, i + 1, f"lib/n{i}.txt", "x\n")
        launched = []
        assert periodic(repo, idle=True, launched=launched).maybe_trigger() == mg.TRIGGER_IDLE
        assert launched == [str(repo)]

    def test_four_merges_busy_does_not_run(self, repo):
        baseline(repo)
        for i in range(4):
            merge_change(repo, i + 1, f"lib/n{i}.txt", "x\n")
        launched = []
        assert periodic(repo, idle=False, launched=launched).maybe_trigger() is None
        assert launched == []

    def test_seven_merges_busy_does_not_run(self, repo):
        baseline(repo)
        for i in range(7):
            merge_change(repo, i + 1, f"lib/n{i}.txt", "x\n")
        assert periodic(repo, idle=False).maybe_trigger() is None

    def test_eight_merges_busy_forced(self, repo):
        baseline(repo)
        for i in range(8):
            merge_change(repo, i + 1, f"lib/n{i}.txt", "x\n")
        launched = []
        assert periodic(repo, idle=False, launched=launched).maybe_trigger() == mg.TRIGGER_FORCED
        assert launched == [str(repo)]

    def test_count_resets_after_run(self, repo):
        baseline(repo)
        for i in range(4):
            merge_change(repo, i + 1, f"lib/n{i}.txt", "x\n")
        assert periodic(repo).run()["result"] == "green"
        assert periodic(repo, idle=True).maybe_trigger() is None
        assert periodic(repo).pending_count() == 0

    def test_missing_state_is_conservative(self, repo):
        launched = []
        assert periodic(repo, idle=False, launched=launched).maybe_trigger() == mg.TRIGGER_UNKNOWN
        assert launched == [str(repo)]

    def test_corrupt_state_is_conservative(self, repo):
        baseline(repo)
        (repo / mg.PERIODIC_STATE_FILE).write_text("{not json")
        assert periodic(repo, idle=False).maybe_trigger() == mg.TRIGGER_UNKNOWN

    def test_base_not_on_main_is_conservative(self, repo):
        baseline(repo)
        state = read_state(repo)
        state["last_run"]["head"] = "0" * 40
        (repo / mg.PERIODIC_STATE_FILE).write_text(json.dumps(state))
        assert periodic(repo, idle=False).maybe_trigger() == mg.TRIGGER_UNKNOWN

    def test_running_alive_skips(self, repo):
        baseline(repo)
        for i in range(8):
            merge_change(repo, i + 1, f"lib/n{i}.txt", "x\n")
        state = read_state(repo)
        state["running"] = {"pid": os.getpid(), "head": "x", "started_epoch": mg.time.time()}
        (repo / mg.PERIODIC_STATE_FILE).write_text(json.dumps(state))
        launched = []
        assert periodic(repo, idle=False, launched=launched).maybe_trigger() is None
        assert launched == []

    def test_hold_exit_evaluates_trigger(self, repo):
        """合併閘門離開名額區段時評估觸發（改動不需名額的合併同樣評估）。"""
        calls = []

        class Spy:
            def maybe_trigger(self):
                calls.append("trigger")

            def blocked_suites(self):
                return {}

        make_branch(repo, "feat", "README.txt", "doc\n")
        gate = mg.MergeGate(str(repo), FakeRunner(), periodic=Spy())
        with gate.hold("feat", "main"):
            assert calls == []
        assert calls == ["trigger"]

    def test_env_disables_default(self, repo, monkeypatch):
        monkeypatch.setenv(mg.PERIODIC_ENV, "0")
        assert mg.MergeGate(str(repo)).periodic is None
        monkeypatch.setenv(mg.PERIODIC_ENV, "1")
        assert isinstance(mg.MergeGate(str(repo)).periodic, mg.PeriodicSuite)


# ---------- 執行中殘留（acceptance 4） ----------

def _dead_pid():
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


def _set_running(repo, running):
    state = read_state(repo)
    state["running"] = running
    (repo / mg.PERIODIC_STATE_FILE).write_text(json.dumps(state))


class TestStaleRunning:
    """子程序中途消失時狀態停在執行中：下一次評估須偵測殘留並重新觸發。"""

    def test_dead_pid_retriggers(self, repo):
        baseline(repo)
        _set_running(repo, {"pid": _dead_pid(), "head": "x", "started_epoch": mg.time.time()})
        launched = []
        assert periodic(repo, idle=False, launched=launched).maybe_trigger() == mg.TRIGGER_STALE
        assert launched == [str(repo)]

    def test_alive_pid_within_timeout_does_not_retrigger(self, repo):
        baseline(repo)
        for i in range(8):
            merge_change(repo, i + 1, f"lib/n{i}.txt", "x\n")
        _set_running(repo, {"pid": os.getpid(), "head": "x", "started_epoch": mg.time.time()})
        launched = []
        assert periodic(repo, idle=True, launched=launched).maybe_trigger() is None
        assert launched == []

    def test_alive_pid_past_timeout_retriggers(self, repo):
        """休眠或卡住：pid 仍活著（或被重用）但已超過執行中逾時。"""
        baseline(repo)
        old = mg.time.time() - mg.PERIODIC_RUNNING_TIMEOUT_SECONDS - 60
        _set_running(repo, {"pid": os.getpid(), "head": "x", "started_epoch": old})
        launched = []
        assert periodic(repo, idle=False, launched=launched).maybe_trigger() == mg.TRIGGER_STALE
        assert launched == [str(repo)]

    @pytest.mark.parametrize("running", [
        {"pid": "abc", "head": "x", "started_epoch": 0},  # pid 讀不懂
        {"head": "x", "started_epoch": 0},  # 缺 pid
        {"pid": 0, "head": "x"},  # 缺開始時間
        "not-a-dict",
    ])
    def test_unreadable_running_is_conservative(self, repo, running):
        baseline(repo)
        if isinstance(running, dict) and running.get("pid") == 0:
            running["pid"] = os.getpid()  # pid 活著但缺開始時間：無法判定逾時
        _set_running(repo, running)
        assert periodic(repo, idle=False).maybe_trigger() == mg.TRIGGER_STALE

    def test_run_takes_over_stale_claim(self, repo):
        baseline(repo)
        old = mg.time.time() - mg.PERIODIC_RUNNING_TIMEOUT_SECONDS - 60
        _set_running(repo, {"pid": os.getpid() + 0, "head": "x", "started_epoch": old})
        # 以另一個活著的 pid 模擬他方殘留（本行程的父程序）
        state = read_state(repo)
        state["running"]["pid"] = os.getppid()
        (repo / mg.PERIODIC_STATE_FILE).write_text(json.dumps(state))
        assert periodic(repo).run()["result"] == "green"
        assert "running" not in read_state(repo)

    def test_run_skips_live_fresh_claim(self, repo):
        baseline(repo)
        _set_running(repo, {"pid": os.getppid(), "head": "x", "started_epoch": mg.time.time()})
        assert periodic(repo).run()["result"] == "skipped"


# ---------- 紅燈二分定位與暫停（acceptance 2） ----------

def _red_history(repo):
    """基準全綠後四筆合併：1 改 lib、2 弄壞 foo、3 改 lib、4 改 foo 的另一檔（不修好）。"""
    base = baseline(repo)
    m1 = merge_change(repo, 1, "lib/n1.txt", "x\n")
    m2 = merge_change(repo, 2, FOO, "VALUE = 1  # BROKEN\n")
    m3 = merge_change(repo, 3, "lib/n3.txt", "x\n")
    m4 = merge_change(repo, 4, ".claude/skills/foo/extra.py", "X = 2\n")
    return base, [m1, m2, m3, m4]


class TestBisectAndBlock:
    def test_red_bisects_to_culprit_merge(self, repo):
        _base, merges = _red_history(repo)
        runner = FakeRunner()
        result = periodic(repo, runner).run()
        assert result["result"] == "red"
        assert result["red"] == ["skill:foo"]
        blocked = read_state(repo)["blocked"]
        assert set(blocked) == {"skill:foo"}
        info = blocked["skill:foo"]
        assert info["culprit"] == merges[1]
        assert info["branch"] == "b2"
        assert info["ticket"] == "9.9.9-W1-002"
        assert info["red_head"] == merges[3]
        log = log_text(repo)
        assert "[定期全套件] 紅燈｜套件 skill:foo｜定位 " + merges[1][:12] in log
        assert "分支 b2" in log

    def test_bisect_reuses_untouched_points(self, repo):
        """沿用規則：m1、m3 不觸及 skill:foo，不為它們實跑 foo；flutter 全綠不二分。"""
        _base, merges = _red_history(repo)
        runner = FakeRunner()
        periodic(repo, runner).run()
        foo_heads = [h for s, h in runner.runs if s == "skill:foo"]
        assert merges[0] not in foo_heads and merges[2] not in foo_heads
        assert len(foo_heads) <= 3  # head 一次 + 二分至多兩次

    def test_blocked_suite_merge_rejected(self, repo):
        _red_history(repo)
        runner = FakeRunner()
        ps = periodic(repo, runner)
        ps.run()
        make_branch(repo, "feat-foo", ".claude/skills/foo/more.py", "Y = 3\n")
        old = git(repo, "rev-parse", "main")
        out = wm.merge_branch_cas("feat-foo", repo=str(repo), pre_merge_check=mg.MergeGate(
            str(repo), runner, periodic=ps))
        assert not out.ok
        assert "暫停" in out.error and "skill:foo" in out.error
        assert git(repo, "rev-parse", "main") == old

    def test_unrelated_suite_merge_not_blocked(self, repo):
        _red_history(repo)
        runner = FakeRunner()
        ps = periodic(repo, runner)
        ps.run()
        make_branch(repo, "feat-lib", "lib/z.txt", "z\n")
        out = wm.merge_branch_cas("feat-lib", repo=str(repo), pre_merge_check=mg.MergeGate(
            str(repo), runner, periodic=ps))
        assert out.ok, out.error

    def test_blocked_suite_is_not_reused_on_retry(self, repo):
        """暫停中的套件不沿用重試結果：verified_suites 有紀錄仍實跑。"""
        _red_history(repo)
        runner = FakeRunner()
        ps = periodic(repo, runner)
        ps.run()
        make_branch(repo, "feat-foo", ".claude/skills/foo/more.py", "Y = 3\n")
        gate = mg.MergeGate(str(repo), runner, periodic=ps)
        head = git(repo, "rev-parse", "main")
        gate.verified_suites["skill:foo"] = head
        before = len(runner.runs)
        out = wm.merge_branch_cas("feat-foo", repo=str(repo), pre_merge_check=gate)
        assert not out.ok
        assert any(s == "skill:foo" for s, _ in runner.runs[before:])

    def test_bisect_failure_still_blocks(self, repo, monkeypatch):
        _red_history(repo)

        def boom(*_a, **_k):
            raise RuntimeError("bisect exploded")

        monkeypatch.setattr(mg.PeriodicSuite, "_bisect", boom)
        result = periodic(repo).run()
        assert result["result"] == "red"
        info = read_state(repo)["blocked"]["skill:foo"]
        assert info["culprit"] is None
        assert "bisect exploded" in info["reason"]

    def test_no_green_baseline_blocks_without_bisect(self, repo):
        write(repo, FOO, "VALUE = 1  # BROKEN\n")
        git(repo, "commit", "-q", "-am", "broken from start")
        result = periodic(repo).run()
        assert result["result"] == "red"
        info = read_state(repo)["blocked"]["skill:foo"]
        assert info["culprit"] is None
        assert "flutter" not in read_state(repo)["blocked"]

    def test_unreadable_block_state_runs_all_selected_suites(self, repo, capsys):
        baseline(repo)
        (repo / mg.PERIODIC_STATE_FILE).write_text("{broken")
        runner = FakeRunner()
        ps = periodic(repo, runner)
        make_branch(repo, "feat-foo", ".claude/skills/foo/more.py", "Y = 3\n")
        gate = mg.MergeGate(str(repo), runner, periodic=ps)
        gate.verified_suites["skill:foo"] = git(repo, "rev-parse", "main")
        before = len(runner.runs)
        out = wm.merge_branch_cas("feat-foo", repo=str(repo), pre_merge_check=gate)
        assert out.ok, out.error
        assert any(s == "skill:foo" for s, _ in runner.runs[before:])
        assert "WARNING" in capsys.readouterr().out


# ---------- 解除條件（acceptance 3） ----------

class TestUnblock:
    def _blocked(self, repo):
        _base, merges = _red_history(repo)
        runner = FakeRunner()
        ps = periodic(repo, runner)
        ps.run()
        return runner, ps, merges

    def test_fix_merge_passes_but_block_stays_until_rerun(self, repo):
        runner, ps, _merges = self._blocked(repo)
        make_branch(repo, "fix-foo", FOO, "VALUE = 1\n")
        out = wm.merge_branch_cas("fix-foo", repo=str(repo), pre_merge_check=mg.MergeGate(
            str(repo), runner, periodic=ps))
        assert out.ok, out.error
        assert "skill:foo" in read_state(repo)["blocked"]
        assert ps.decide() == mg.TRIGGER_BLOCKED  # 修正觸及暫停中套件：強制重跑

    def test_rerun_green_after_fix_unblocks_and_merges_resume(self, repo):
        runner, ps, _merges = self._blocked(repo)
        make_branch(repo, "fix-foo", FOO, "VALUE = 1\n")
        assert wm.merge_branch_cas("fix-foo", repo=str(repo), pre_merge_check=mg.MergeGate(
            str(repo), runner, periodic=ps)).ok
        assert ps.run()["result"] == "green"
        assert read_state(repo)["blocked"] == {}
        assert "[定期全套件] 解除｜套件 skill:foo" in log_text(repo)
        make_branch(repo, "feat-foo", ".claude/skills/foo/more.py", "Y = 3\n")
        out = wm.merge_branch_cas("feat-foo", repo=str(repo), pre_merge_check=mg.MergeGate(
            str(repo), runner, periodic=ps))
        assert out.ok, out.error

    def test_revert_then_rerun_green_unblocks(self, repo):
        runner, ps, merges = self._blocked(repo)
        git(repo, "revert", "--no-edit", "-m", "1", merges[1])
        assert ps.decide() == mg.TRIGGER_BLOCKED
        assert ps.run()["result"] == "green"
        assert read_state(repo)["blocked"] == {}

    def test_rerun_still_red_keeps_block_and_culprit(self, repo):
        runner, ps, merges = self._blocked(repo)
        merge_change(repo, 9, ".claude/skills/foo/other.py", "Z = 1\n")
        before = len(runner.runs)
        assert ps.run()["result"] == "red"
        info = read_state(repo)["blocked"]["skill:foo"]
        assert info["culprit"] == merges[1]
        assert len([1 for s, _ in runner.runs[before:] if s == "skill:foo"]) == 1  # 不重複二分

    def test_unrelated_merges_do_not_force_rerun_while_blocked(self, repo):
        runner, ps, _merges = self._blocked(repo)
        merge_change(repo, 9, "lib/q.txt", "q\n")
        assert periodic(repo, idle=False).decide() is None
