"""逾時終止 helper 的契約測試。

hook 與 ticket_system 皆委派 lib.git_utils.run_with_graceful_timeout 單一實作，
本檔對兩個入口參數化跑同一組案例，固定委派後行為一致：
逾時先 SIGTERM（git 自行清鎖）、忽略 SIGTERM 者於寬限後被 SIGKILL、
孫程序握住輸出管線時耗時仍有上界、input 照常傳入。

持鎖情境使用暫存 repo 的真 git 加慢 clean filter；git 實驗只在 tmp_path。
耗時上界採寬鬆門檻（孫程序 sleep 30、斷言 15 秒內返回），以免機器負載造成誤判。
"""

import importlib.util
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

_SKILLS = Path(__file__).resolve().parents[2]
_HOOK_FILE = _SKILLS / "worktree" / "hooks" / "worktree-auto-commit-hook.py"
_GIT_OPS_FILE = _SKILLS / "ticket" / "ticket_system" / "lib" / "git_ops.py"

_SLOW_SECONDS = 30
_BOUND_SECONDS = 15


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_TICKET_DIR = _SKILLS / "ticket"
_DEGRADE_MARKER = "降級為備援實作"


@pytest.fixture(scope="module")
def git_ops_module():
    # 以檔案路徑載入的 git_ops 需 sys.path 含 ticket_system，延遲匯入才走 lib 而非降級備援
    sys.path.insert(0, str(_TICKET_DIR))
    try:
        yield _load("contract_ticket_git_ops", _GIT_OPS_FILE)
    finally:
        sys.path.remove(str(_TICKET_DIR))


@pytest.fixture(scope="module")
def helpers(git_ops_module):
    hook = _load("contract_worktree_hook", _HOOK_FILE)
    return {
        "hook": hook._run_with_graceful_timeout,
        "ticket": git_ops_module._run_with_graceful_timeout,
    }


class TestTicketEntryUsesLib:
    def test_ticket_entry_does_not_degrade_to_fallback(self, git_ops_module, capsys):
        git_ops_module._run_with_graceful_timeout(["echo", "ok"], 10, text=True)
        assert _DEGRADE_MARKER not in capsys.readouterr().err

    def test_degrade_marker_appears_when_lib_unloadable(
        self, git_ops_module, capsys, monkeypatch
    ):
        """正向對照：lib 不可載入時上述斷言所依據的降級訊號必須出現。"""
        import ticket_system.lib.claude_lib_loader as loader

        monkeypatch.setattr(loader, "load_claude_lib", lambda *a, **k: None)
        git_ops_module._run_with_graceful_timeout(["echo", "ok"], 10, text=True)
        assert _DEGRADE_MARKER in capsys.readouterr().err


@pytest.fixture(params=["hook", "ticket"])
def run(request, helpers):
    return helpers[request.param]


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


@pytest.fixture
def pid_log(tmp_path):
    """測試內啟動的程序把自己的 PID 追加到此檔；結束時逐一終止並確認已不存在。"""
    path = tmp_path / "pids.log"
    path.touch()
    yield path
    pids = [int(t) for t in path.read_text().split()]
    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and any(_pid_alive(p) for p in pids):
        time.sleep(0.05)
    survivors = [p for p in pids if _pid_alive(p)]
    assert not survivors, f"測試結束後仍殘留程序：{survivors}"


@pytest.fixture
def slow_filter_repo(tmp_path, monkeypatch, pid_log):
    """含慢 clean filter 的暫存 repo；git add 期間持有 index.lock。"""
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    repo = tmp_path / "repo"
    repo.mkdir()
    for cmd in (
        ["git", "init", "-q"],
        [
            "git", "config", "filter.slow.clean",
            f"echo $$ >> '{pid_log}'; sleep {_SLOW_SECONDS} & echo $! >> '{pid_log}'; wait; cat",
        ],
    ):
        subprocess.run(cmd, cwd=repo, check=True)
    (repo / ".gitattributes").write_text("*.dat filter=slow\n")
    (repo / "payload.dat").write_text("x\n")
    return repo


def _lock(repo):
    return repo / ".git" / "index.lock"


def _wait_for_lock(repo):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if _lock(repo).exists():
            return
        time.sleep(0.05)


class TestRealGitLock:
    def test_sigterm_clears_index_lock_with_bounded_wait(self, run, slow_filter_repo):
        # 逾時前鎖必須實際存在，否則「鎖不在」不是清鎖的證據
        lock_seen = threading.Event()
        stop = threading.Event()

        def watch():
            while not stop.is_set():
                if _lock(slow_filter_repo).exists():
                    lock_seen.set()
                    return
                time.sleep(0.02)

        watcher = threading.Thread(target=watch, daemon=True)
        watcher.start()
        start = time.monotonic()
        try:
            with pytest.raises(subprocess.TimeoutExpired):
                run(
                    ["git", "add", "payload.dat"], 3,
                    cwd=slow_filter_repo, text=True, start_new_session=True,
                )
        finally:
            stop.set()
            watcher.join()
        elapsed = time.monotonic() - start
        if not lock_seen.is_set():
            pytest.skip("逾時前 git 未取得 index.lock（機器負載高），無法鑑別清鎖行為")
        assert elapsed < _BOUND_SECONDS
        assert not _lock(slow_filter_repo).exists()

    def test_lock_is_held_before_timeout(self, run, slow_filter_repo):
        """對照：確認情境確實持鎖，鎖檔消失是 SIGTERM 的效果而非從未存在。"""
        proc = subprocess.Popen(
            ["git", "add", "payload.dat"],
            cwd=slow_filter_repo,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        try:
            _wait_for_lock(slow_filter_repo)
            assert _lock(slow_filter_repo).exists()
        finally:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()


_IGNORE_SIGTERM = (
    "import signal, time\n"
    "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
    "time.sleep(60)\n"
)


class TestEscalationAndBounds:
    def test_ignoring_sigterm_is_killed_after_grace(self, run):
        start = time.monotonic()
        with pytest.raises(subprocess.TimeoutExpired):
            run([sys.executable, "-c", _IGNORE_SIGTERM], 1, grace=1, text=True)
        assert time.monotonic() - start < _BOUND_SECONDS

    def test_grandchild_holding_pipe_does_not_extend_wait(self, run, pid_log):
        script = (
            f"sleep {_SLOW_SECONDS} & echo $! >> '{pid_log}'; "
            f"sleep {_SLOW_SECONDS * 2} & echo $! >> '{pid_log}'; wait"
        )
        start = time.monotonic()
        with pytest.raises(subprocess.TimeoutExpired):
            run(["sh", "-c", script], 1, grace=1, text=True, start_new_session=True)
        assert time.monotonic() - start < _BOUND_SECONDS


    def test_ignoring_sigterm_with_grandchild_holding_pipe_has_bounded_wait(
        self, run, pid_log
    ):
        """SIGKILL 之後只能等行程本身；若退化為等管線 EOF，會被孫程序拖到 sleep 結束。"""
        script = (
            f"trap '' TERM; echo $$ >> '{pid_log}'; "
            f"sleep {_SLOW_SECONDS} & echo $! >> '{pid_log}'; "
            f"sleep {_SLOW_SECONDS * 2} & echo $! >> '{pid_log}'; wait"
        )
        start = time.monotonic()
        with pytest.raises(subprocess.TimeoutExpired):
            run(["sh", "-c", script], 1, grace=1, text=True, start_new_session=True)
        assert time.monotonic() - start < _BOUND_SECONDS


class TestNormalPath:
    def test_input_is_passed_to_stdin(self, run):
        result = run(["cat"], 10, input="hello", text=True)
        assert (result.returncode, result.stdout) == (0, "hello")

    def test_completed_process_fields(self, run):
        result = run(["sh", "-c", "echo out; echo err >&2; exit 3"], 10, text=True)
        assert (result.returncode, result.stdout, result.stderr) == (3, "out\n", "err\n")

    def test_timeout_none_waits_for_completion(self, run):
        result = run(["echo", "ok"], None, text=True)
        assert result.stdout == "ok\n"
