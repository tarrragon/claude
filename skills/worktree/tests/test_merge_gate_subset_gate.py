"""合併閘門關鍵路徑改跑測試子集（select_test_files）。

正向對照：改中介依賴的模組、紅燈在不提及它的測試（3.4.0-W1-191 樣本形態），經子集仍被擋。
收窄對照：與改動無關的測試不進子集——沒有這一側，子集退化成全套件時正向對照照樣全綠。
保守落點：選擇函式拋例外、依賴缺席、逾時、回傳 None 時，該套件退回全套件並在閘門日誌留一行。

套件執行器一律注入假的：測試檔被收集（argv 列出它，或 argv 不列任何測試檔＝全套件）即回紅燈。
"""

import subprocess
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / ".claude"))

import merge_gate as mg  # noqa: E402
import worktree_manager as wm  # noqa: E402
import merge_cas as mc  # noqa: E402

PKG = ".claude/skills/demo/demo_sys"
TESTS = ".claude/skills/demo/tests"
VERSION = f"{PKG}/lib/version.py"
T_CREATE = f"{TESTS}/test_create_visible.py"  # 只匯入 create；create 匯入 version（鏈長 2）
T_UNRELATED = f"{TESTS}/test_unrelated.py"
FULL_SKILL_TAIL = "../skills/demo/tests"  # 無 pyproject 的 skill 全套件命令尾端

BASE = {
    f"{PKG}/__init__.py": "",
    f"{PKG}/lib/__init__.py": "",
    VERSION: "def suggest():\n    return '1.0'\n",
    f"{PKG}/lib/other.py": "def other():\n    return 1\n",
    f"{PKG}/commands/__init__.py": "",
    f"{PKG}/commands/create.py": "from demo_sys.lib.version import suggest\n\n\ndef run():\n    return suggest()\n",
    T_CREATE: "def test_create():\n    from demo_sys.commands.create import run\n    assert run()\n",
    T_UNRELATED: "from demo_sys.lib.other import other\n\n\ndef test_other():\n    assert other()\n",
    ".claude/hooks/pyproject.toml": '[tool.pytest.ini_options]\ntestpaths = ["tests", "../lib/tests"]\n',
    ".claude/hooks/tests/test_h.py": "def test_h():\n    assert True\n",
    ".claude/lib/__init__.py": "",
    ".claude/lib/x.py": "y = 1\n",
    ".claude/lib/tests/test_x.py": "from lib.x import y\n\n\ndef test_y():\n    assert y\n",
}


def git(repo, *args):
    proc = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def write(repo, rel, text):
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def branch_with(repo, branch, rel, text):
    git(repo, "checkout", "-q", "-b", branch, "main")
    write(repo, rel, text)
    git(repo, "add", rel)
    git(repo, "commit", "-q", "-m", f"{branch} change")
    git(repo, "checkout", "-q", "main")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(mc, "_sleep", lambda _s: None)
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    git(r, "config", "user.email", "t@example.com")
    git(r, "config", "user.name", "t")
    for rel, text in BASE.items():
        write(r, rel, text)
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "base")
    branch_with(r, "feat", VERSION, "def suggest():\n    return '2.0'\n")
    slots = tmp_path / "slots"
    slots.mkdir(mode=0o700)
    monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(slots))
    monkeypatch.chdir(r)
    monkeypatch.setattr(wm, "get_project_root", lambda: str(r))
    monkeypatch.setattr(wm, "get_worktree_list", lambda: [])
    return r


def red_when_collected(target, calls):
    """target 被收集即紅燈：argv 列出它，或 argv 不列任何測試檔（全套件）。"""
    def run(argv, cwd):
        cmd = argv[argv.index("--") + 1:]
        calls.append(cmd)
        files = [a for a in cmd if a.endswith(".py")]
        if not files or any(f.endswith(target) for f in files):
            return 1, f"FAILED {target}::test_x - assert False\n"
        return 0, "1 passed in 0.1s"
    return run


def merge(repo, branch, runner, **gate_kwargs):
    """預設注入無暫停的定期全套件替身：conftest 以 MERGE_GATE_PERIODIC=0 停用定期全套件，
    停用時閘門一律跑全套件，子集路徑須有啟用中的定期全套件才會生效。"""
    gate_kwargs.setdefault("periodic", StubPeriodic())
    gate = mg.MergeGate(str(repo), runner, **gate_kwargs)
    return wm.merge_branch_cas(branch, repo=str(repo), pre_merge_check=gate)


def gate_log(repo):
    return (repo / ".claude/logs/worktree-merge.log").read_text(encoding="utf-8")


def listed_tests(cmd):
    return [a for a in cmd if a.endswith(".py")]


class TestPositiveControl:
    def test_transitive_red_is_still_blocked_through_subset(self, repo):
        """正向對照：紅燈測試不提及改動檔、只經中介模組遞移匯入，子集仍選中它並擋下合併。"""
        old = git(repo, "rev-parse", "main")
        calls = []
        out = merge(repo, "feat", red_when_collected("tests/test_create_visible.py", calls))
        assert not out.ok
        assert "test_create_visible.py" in out.error
        assert git(repo, "rev-parse", "main") == old
        files = listed_tests(calls[0])
        assert files == ["../skills/demo/tests/test_create_visible.py"]  # 走的是子集，不是全套件

    def test_subset_excludes_unrelated_test(self, repo, capsys):
        """收窄對照：無關測試不進子集；全套件會收集它而紅燈，子集不收集故綠燈。"""
        calls = []
        out = merge(repo, "feat", red_when_collected("tests/test_unrelated.py", calls))
        assert out.ok, out.error
        assert all(FULL_SKILL_TAIL != c[-1] for c in calls)
        assert "測試子集：套件 skill:demo 選中 1 檔" in capsys.readouterr().out
        assert "測試子集：套件 skill:demo 選中 1 檔" in gate_log(repo)


def _raise_runtime(_changed, _root):
    raise RuntimeError("boom")


def _raise_missing(_changed, _root):
    raise ModuleNotFoundError("No module named 'tomllib'")


def _return_none(_changed, _root):
    return None


class TestConservativeFallback:
    @pytest.mark.parametrize("selector,reason", [
        (_raise_runtime, "RuntimeError"),
        (_raise_missing, "ModuleNotFoundError"),
        (_return_none, "回傳 None"),
    ], ids=["exception", "dependency_missing", "returns_none"])
    def test_selector_failure_falls_back_to_full_suite(self, repo, selector, reason):
        calls = []
        out = merge(repo, "feat", red_when_collected("tests/test_unrelated.py", calls), test_selector=selector)
        assert not out.ok  # 全套件收集到無關測試而紅燈：證明確實退回全套件
        assert calls[0][-1] == FULL_SKILL_TAIL and not listed_tests(calls[0])
        log = gate_log(repo)
        assert "測試子集：套件 skill:demo 退回全套件" in log and reason in log

    def test_selector_timeout_falls_back_to_full_suite(self, repo, monkeypatch):
        monkeypatch.setattr(mg, "SUBSET_SELECT_TIMEOUT_SECONDS", 0.2)
        release = threading.Event()

        def slow(_changed, _root):
            release.wait(10)
            return [T_CREATE]

        calls = []
        try:
            out = merge(repo, "feat", red_when_collected("tests/test_unrelated.py", calls), test_selector=slow)
        finally:
            release.set()
        assert not out.ok
        assert calls[0][-1] == FULL_SKILL_TAIL and not listed_tests(calls[0])
        log = gate_log(repo)
        assert "測試子集：套件 skill:demo 退回全套件" in log and "逾時" in log

    def test_zero_selected_files_falls_back_to_full_suite(self, repo):
        """子集 0 檔：套件已因路徑選中、選擇函式卻找不到參照，兩者不一致時保守跑全套件。"""
        branch_with(repo, "notes", ".claude/skills/demo/notes.md", "n\n")
        calls = []
        out = merge(repo, "notes", red_when_collected("tests/test_unrelated.py", calls))
        assert not out.ok
        assert calls[0][-1] == FULL_SKILL_TAIL
        assert "測試子集：套件 skill:demo 退回全套件（子集 0 檔）" in gate_log(repo)


class StubPeriodic:
    """定期全套件替身：blocked 為暫停中套件；error 非 None 時模擬讀不到暫停狀態。"""

    def __init__(self, blocked=None, error=None):
        self.blocked, self.error = blocked or {}, error

    def blocked_suites(self):
        if self.error is not None:
            raise self.error
        return self.blocked

    def maybe_trigger(self):
        return None


class TestPausedSuiteRunsFull:
    """暫停中的套件一律跑全套件；同一改動在未暫停時跑子集（對照）。"""

    def _argv(self, repo, periodic):
        calls = []
        out = merge(repo, "feat", red_when_collected("tests/test_create_visible.py", calls), periodic=periodic)
        assert not out.ok  # 兩種情況都收集到紅燈測試；差別只在跑的範圍
        return calls[0]

    def test_unpaused_suite_runs_subset(self, repo):
        cmd = self._argv(repo, StubPeriodic())
        assert listed_tests(cmd) == ["../skills/demo/tests/test_create_visible.py"]

    def test_paused_suite_runs_full_suite(self, repo, capsys):
        cmd = self._argv(repo, StubPeriodic({"skill:demo": {"culprit": "a" * 40}}))
        assert cmd[-1] == FULL_SKILL_TAIL and not listed_tests(cmd)
        assert "測試子集：套件 skill:demo 退回全套件（套件暫停中）" in capsys.readouterr().out

    def test_unknown_pause_state_runs_full_suite(self, repo):
        cmd = self._argv(repo, StubPeriodic(error=mg.PeriodicStateError("壞檔")))
        assert cmd[-1] == FULL_SKILL_TAIL and not listed_tests(cmd)


class TestPeriodicDisabledRunsFull:
    """定期全套件停用（補償控制不在）時閘門不跑子集；同一改動在啟用且無暫停時跑子集（對照）。"""

    def _argv(self, repo, **gate_kwargs):
        calls = []
        out = merge(repo, "feat", red_when_collected("tests/test_create_visible.py", calls), **gate_kwargs)
        assert not out.ok
        return calls[0]

    def test_env_disabled_runs_full_suite(self, repo, monkeypatch, capsys):
        monkeypatch.setenv(mg.PERIODIC_ENV, "0")
        cmd = self._argv(repo, periodic=mg._PERIODIC_DEFAULT)  # 正式路徑：預設值經環境變數判定
        assert cmd[-1] == FULL_SKILL_TAIL and not listed_tests(cmd)
        assert "測試子集：套件 skill:demo 退回全套件（定期全套件停用）" in capsys.readouterr().out
        assert "退回全套件（定期全套件停用）" in gate_log(repo)

    def test_env_unset_without_pause_runs_subset(self, repo, monkeypatch):
        monkeypatch.delenv(mg.PERIODIC_ENV, raising=False)
        monkeypatch.setattr(mg.PeriodicSuite, "maybe_trigger", lambda self: None)  # 不啟動真實定期全套件
        cmd = self._argv(repo, periodic=mg._PERIODIC_DEFAULT)
        assert listed_tests(cmd) == ["../skills/demo/tests/test_create_visible.py"]

    def test_injected_none_also_runs_full_suite(self, repo):
        """periodic=None 與環境變數停用同一判定：沒有任何路徑在定期全套件缺席時跑子集。"""
        cmd = self._argv(repo, periodic=None)
        assert cmd[-1] == FULL_SKILL_TAIL and not listed_tests(cmd)


class TestSuitePartition:
    def test_hooks_subset_follows_pyproject_testpaths(self, repo):
        """lib 改動：hooks 套件的子集取自 testpaths（含 ../lib/tests），路徑相對 uv --directory。"""
        branch_with(repo, "libch", ".claude/lib/x.py", "y = 2\n")
        calls = []
        hooks_prefix = ["uv", "--directory", ".claude/hooks"]
        hooks_red = red_when_collected("hooks/tests/test_h.py", [])

        def run(argv, cwd):  # 只有 hooks 套件依收集判紅；scripts 等其他套件一律綠燈
            cmd = argv[argv.index("--") + 1:]
            calls.append(cmd)
            return hooks_red(argv, cwd) if cmd[:3] == hooks_prefix else (0, "ok")

        out = merge(repo, "libch", run)
        assert out.ok, out.error
        hooks = [c for c in calls if c[:3] == hooks_prefix]
        assert hooks and listed_tests(hooks[0]) == ["../lib/tests/test_x.py"]

    def test_subset_command_for_skill_with_pyproject(self, tmp_path):
        write(tmp_path, ".claude/skills/withpy/pyproject.toml", '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n')
        cmd = mg.subset_command("skill:withpy", str(tmp_path), [".claude/skills/withpy/tests/test_a.py"])
        assert cmd == ["uv", "--directory", ".claude/skills/withpy", "run", "pytest", "tests/test_a.py"]

    def test_files_outside_suite_testpaths_are_not_assigned(self, tmp_path):
        """skill 內非 testpaths 下的 test_*.py（如產品模組 test_map.py）不得塞進該套件的 argv。"""
        write(tmp_path, ".claude/skills/withpy/pyproject.toml", '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n')
        picked = mg.suite_test_subset("skill:withpy", str(tmp_path), [
            ".claude/skills/withpy/tests/test_a.py",
            ".claude/skills/withpy/withpy_system/commands/test_map.py",
            ".claude/hooks/tests/test_h.py",
        ])
        assert picked == [".claude/skills/withpy/tests/test_a.py"]
