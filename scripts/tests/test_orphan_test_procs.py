"""orphan-test-procs.py 測試。

只終止本測試自己啟動並記下 PID 的替身；一律以 --root 指向暫存目錄，
使真實的測試執行器永遠不在認定範圍內。
"""
import importlib.util
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "orphan-test-procs.py"
LIFE = 30  # 替身存活上限（秒），保證測試失敗也會自行結束

# 替身本體：寫出 PID 後睡眠；ignore_term=1 時忽略 TERM
STAND_IN_SRC = (
    "import os,signal,sys,time\n"
    "if sys.argv[2]=='1': signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
    "open(sys.argv[1],'w').write(str(os.getpid()))\n"
    "time.sleep(%d)\n" % LIFE
)
# 中介程序：啟動替身（指定 argv0 與 cwd）後立即結束，替身被 launchd 收養
LAUNCHER_SRC = (
    "import subprocess,sys\n"
    "argv0,cwd,pidfile,ign=sys.argv[1:5]\n"
    "subprocess.Popen([argv0,'-c',%r,pidfile,ign],executable=sys.executable,"
    "cwd=cwd,start_new_session=True)\n" % STAND_IN_SRC
)


def _load():
    spec = importlib.util.spec_from_file_location("otp", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _alive(pid):
    out = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)],
                         capture_output=True, text=True).stdout.strip()
    return bool(out) and not out.startswith("Z")


def _wait_pid(pidfile, within=10.0):
    deadline = time.monotonic() + within
    while time.monotonic() < deadline:
        if pidfile.exists() and pidfile.read_text().strip():
            return int(pidfile.read_text())
        time.sleep(0.05)
    raise AssertionError("替身未寫出 PID")


def _wait_gone(pid, within=10.0):
    deadline = time.monotonic() + within
    while time.monotonic() < deadline and _alive(pid):
        time.sleep(0.05)
    return not _alive(pid)


def _dead_pid():
    """剛結束並已回收的程序 PID（macOS 的 ps 對超過 PID 上限的值回錯誤，不能用來表示不存在）。"""
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


def _ppid(pid):
    return int(subprocess.run(["ps", "-o", "ppid=", "-p", str(pid)],
                              capture_output=True, text=True).stdout.strip())


class Env:
    def __init__(self, tmp_path):
        self.root = (tmp_path / "proj").resolve()
        self.root.mkdir()
        self.outside = (tmp_path / "outside").resolve()
        self.outside.mkdir()
        self.tmp = tmp_path
        self.pids = []
        self.n = 0
        self.holders = []

    def orphan(self, argv0="flutter_tester", cwd=None, ign="0"):
        """啟動並等到被 launchd 收養的替身，回傳 PID。"""
        self.n += 1
        pidfile = self.tmp / ("pid%d" % self.n)
        subprocess.run([sys.executable, "-c", LAUNCHER_SRC, argv0,
                        str(cwd or self.root), str(pidfile), ign], check=True, timeout=15)
        pid = _wait_pid(pidfile)
        self.pids.append(pid)
        deadline = time.monotonic() + 10
        while _ppid(pid) != 1 and time.monotonic() < deadline:
            time.sleep(0.05)
        return pid

    def child_of_test(self, cwd=None):
        """父程序為本測試程序（非 1）的替身。"""
        self.n += 1
        pidfile = self.tmp / ("pid%d" % self.n)
        holder = subprocess.Popen(["flutter_tester", "-c", STAND_IN_SRC, str(pidfile), "0"],
                                  executable=sys.executable, cwd=str(cwd or self.root))
        self.holders.append(holder)
        pid = _wait_pid(pidfile)
        self.pids.append(pid)
        return pid

    def run(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root), *args],
                              capture_output=True, text=True, timeout=60)


@pytest.fixture
def env(tmp_path):
    e = Env(tmp_path)
    yield e
    for pid in e.pids:
        try:
            os.kill(pid, signal.SIGKILL)  # 以記下的 PID 清理
        except (ProcessLookupError, PermissionError):
            pass
    for h in e.holders:
        h.wait()


def test_default_lists_without_killing(env):
    pid = env.orphan()
    res = env.run()
    assert res.returncode == 0
    assert str(pid) in res.stdout
    assert _alive(pid)


def test_kill_terminates_matching_orphan_positive_control(env):
    pid = env.orphan()
    res = env.run("--kill")
    assert res.returncode == 0
    assert _wait_gone(pid)


def test_kill_escalates_to_sigkill_when_term_ignored(env):
    pid = env.orphan(ign="1")
    assert env.run("--kill").returncode == 0
    assert _wait_gone(pid)


def test_negative_parent_not_init_survives(env):
    pid = env.child_of_test()
    assert _ppid(pid) != 1
    env.run("--kill")
    assert _alive(pid)


def test_negative_cwd_outside_project_survives(env):
    pid = env.orphan(cwd=env.outside)
    env.run("--kill")
    assert _alive(pid)


def test_negative_command_not_in_list_survives(env):
    pid = env.orphan(argv0="not_a_runner")
    env.run("--kill")
    assert _alive(pid)


def test_deleted_cwd_orphan_is_skipped_and_reported(env):
    gone = env.root / "wt-gone"
    gone.mkdir()
    pid = env.orphan(cwd=gone)
    gone.rmdir()
    res = env.run("--kill")
    assert res.returncode == 0
    assert _alive(pid)
    assert "cwd" in res.stdout and str(pid) in res.stdout


def test_no_orphans_exit_0_and_idempotent(env):
    first, second = env.run("--kill"), env.run("--kill")
    assert (first.returncode, second.returncode) == (0, 0)
    assert first.stdout == second.stdout


def test_repeat_after_kill_is_stable(env):
    pid = env.orphan()
    env.run("--kill")
    assert _wait_gone(pid)
    a, b = env.run("--kill"), env.run("--kill")
    assert a.returncode == b.returncode == 0
    assert a.stdout == b.stdout


def test_send_signal_tolerates_missing_and_eperm():
    mod = _load()

    def raiser(exc):
        def fake(pid, sig):
            raise exc
        return fake

    real = os.kill
    try:
        for exc in (ProcessLookupError(), PermissionError()):
            os.kill = raiser(exc)
            mod._send(12345, signal.SIGTERM)  # 不得拋出
    finally:
        os.kill = real


def test_survivor_after_nonpositive_zombie_check():
    """殭屍（ps 狀態 Z）不算存活，kill 流程不會等它。"""
    mod = _load()
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and mod._is_alive(proc.pid):
            time.sleep(0.05)
        assert mod._is_alive(proc.pid) is False
    finally:
        proc.wait()


# ---- 認定表、終止結果、失敗可見性 ----

SPACE = "/Users/me/My Projects/app/.venv/bin"
RUNNER_CASES = [
    # (命令列, 是否認定)
    ("/opt/flutter/bin/cache/artifacts/engine/darwin-x64/flutter_tester --a", True),
    ("flutter_tester", True),
    ("/usr/bin/python3 -m pytest tests/ -q", True),
    ("python -m pytest", True),
    ("/opt/homebrew/bin/python3.12 /repo/.venv/bin/pytest -x", True),
    ("/repo/.venv/bin/python /repo/.venv/bin/py.test", True),
    ("node /repo/node_modules/.bin/jest --runInBand", True),
    ("node /repo/node_modules/jest/bin/jest.js", True),
    ("/usr/local/bin/node /repo/node_modules/vitest/vitest.mjs run", True),
    ("/usr/local/bin/node /repo/node_modules/.bin/vitest", True),
    ("python3 -mpytest", True),
    # 執行檔路徑含空白：ps 無法分辨詞界，保守不認定（漏認）
    (SPACE + "/python -m pytest tests", False),
    ("/Users/me/My Dir/flutter_tester --x", False),
    ("node /Users/me/My Dir/node_modules/.bin/jest", False),
    # 不該認定
    ("vim pytest.ini", False),
    ("grep pytest file.txt", False),
    ("/usr/bin/grep -r jest .", False),
    ("python other.py pytest", False),
    ("python3 -c import pytest", False),
    ("python -m http.server", False),
    ("node server.js --jest", False),
    ("tail -f /var/log/vitest.log", False),
    ("/usr/bin/python3", False),
    ("", False),
    # 首詞為絕對路徑的普通程式，後接執行器路徑
    ("/usr/bin/vim /repo/.venv/bin/pytest", False),
    ("/usr/bin/less /repo/node_modules/.bin/jest", False),
    ("/usr/bin/git add /repo/tools/pytest", False),
    ("/usr/bin/grep /repo/pytest /tmp/file", False),
    ("/usr/bin/find /repo/node_modules/.bin/jest", False),
    ("/usr/bin/ssh host /usr/bin/python3 -m pytest", False),
    ("/usr/bin/sudo /usr/bin/python3 -m pytest", False),
    ("/bin/cat /x/pytest", False),
    # 直譯器後的腳本不是執行器，其後的路徑不看
    ("python3 /repo/run /data/pytest", False),
    ("python3 /repo/manage /srv/logs/jest", False),
    ("node /repo/server /var/data/vitest.ts", False),
    ("python /opt/app/serve /x/.venv/bin/pytest", False),
    # 目錄名以執行器名結尾且後接空白
    ("/Users/me/pytest runs/bin/python server.py", False),
    ("/Users/me/pytest runs/tool --flag", False),
    ("/Users/me/flutter_tester backup/run.sh", False),
    # 次詞為含斜線的直譯器路徑，但首詞是真實執行器：認定
    ("/repo/.venv/bin/pytest /repo/tests/python", True),
    ("pytest /repo/scripts/python3", True),
    ("jest /repo/src/node", True),
    # 帶值選項：遇到即不認定（兩個方向）
    ("python3 -W /repo/pytest other.py", False),
    ("node --require /repo/node_modules/.bin/jest server.js", False),
    ("python3 -W ignore -m pytest", False),
    ("python3 -X dev /repo/.venv/bin/pytest", False),
    ("node --require x.js /repo/node_modules/.bin/jest", False),
    ("node --import x.mjs /repo/node_modules/.bin/vitest", False),
    ("node --loader x.mjs /repo/node_modules/.bin/jest", False),
    ("node -r x.js /repo/node_modules/.bin/jest", False),
]


@pytest.mark.parametrize("command,expected", RUNNER_CASES)
def test_is_runner_table(command, expected, monkeypatch):
    mod = _load()
    # 除明列的半截路徑外，視所有絕對路徑檔案為存在
    missing = {"/Users/me/pytest", "/Users/me/flutter_tester"}
    monkeypatch.setattr(mod, "_is_regular_file", lambda path: path not in missing)
    assert mod.is_runner(command) is expected


def test_absolute_first_token_must_exist(tmp_path):
    mod = _load()
    real = tmp_path / "pytest"
    real.write_text("")
    assert mod.is_runner(f"{real} -x") is True
    assert mod.is_runner(f"{tmp_path}/gone/pytest -x") is False
    assert mod.is_runner(f"{tmp_path} /pytest") is False
    # 目錄不是一般檔案
    (tmp_path / "jest").mkdir()
    assert mod.is_runner(f"{tmp_path}/jest") is False


def _fake_world(mod, monkeypatch, root, *, alive=True, same=True):
    """不送任何真實訊號的世界：一個假程序，存活與身份由參數決定。"""
    fake = mod.Proc(999999, 1, "S", "flutter_tester")
    sent = []
    monkeypatch.setattr(mod, "list_processes", lambda: [fake])
    monkeypatch.setattr(mod, "process_cwd", lambda pid: str(root))
    monkeypatch.setattr(mod, "_send", lambda pid, sig: sent.append((pid, sig)))
    monkeypatch.setattr(mod, "_is_alive", alive if callable(alive) else (lambda pid: alive))
    monkeypatch.setattr(mod, "_same_identity", lambda p: same)
    monkeypatch.setattr(mod, "GRACE_SECONDS", 0.05)
    monkeypatch.setattr(mod, "POLL_INTERVAL", 0.001)
    return fake, sent


def test_kill_reports_survivor_and_exits_nonzero(tmp_path, monkeypatch, capsys):
    mod = _load()
    _fake_world(mod, monkeypatch, tmp_path)
    rc = mod.main(["--kill", "--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "未能終止 999999" in out and "已終止" not in out


def test_kill_skips_signal_when_identity_changed(tmp_path, monkeypatch):
    mod = _load()
    _, sent = _fake_world(mod, monkeypatch, tmp_path, same=False)
    rc = mod.main(["--kill", "--root", str(tmp_path)])
    assert sent == []
    assert rc == 0


def test_identity_changed_between_term_and_kill_sends_no_kill(tmp_path, monkeypatch):
    mod = _load()
    fake, sent = _fake_world(mod, monkeypatch, tmp_path)
    answers = iter([True, False])  # TERM 前相符，KILL 前已不符
    monkeypatch.setattr(mod, "_same_identity", lambda p: next(answers))
    result = mod.terminate(fake, grace=0.05)
    assert sent == [(999999, signal.SIGTERM)]
    assert result == "changed_after_term"


@pytest.mark.parametrize("failing", ["ps", "git"])
def test_external_command_failure_is_visible(tmp_path, monkeypatch, capsys, failing):
    mod = _load()
    real = subprocess.run

    def fake_run(cmd, *a, **kw):
        if cmd[0] == failing:
            return subprocess.CompletedProcess(cmd, 1, "", "boom")
        return real(cmd, *a, **kw)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    rc = mod.main(["--root", str(tmp_path)] if failing == "ps" else [])
    cap = capsys.readouterr()
    assert rc == 2
    assert "boom" in cap.err
    assert "符合 0" not in cap.out


def test_root_given_does_not_expand_worktrees(tmp_path):
    mod = _load()
    repo = tmp_path / "repo"
    repo.mkdir()
    git = ["git", "-C", str(repo)]
    subprocess.run(git + ["init", "-q"], check=True)
    subprocess.run(git + ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
                          "--allow-empty", "-m", "i"], check=True)
    subprocess.run(git + ["worktree", "add", "-q", str(tmp_path / "wt")], check=True)
    assert mod.project_roots(str(repo)) == [os.path.realpath(repo)]


def test_root_flag_hidden_from_help():
    res = subprocess.run([sys.executable, str(SCRIPT), "--help"],
                         capture_output=True, text=True, timeout=30)
    assert "--kill" in res.stdout and "--root" not in res.stdout


def test_skip_reason_deleted_cwd_prints_path(env):
    gone = env.root / "wt-gone2"
    gone.mkdir()
    pid = env.orphan(cwd=gone)
    gone.rmdir()
    res = env.run()
    line = [l for l in res.stdout.splitlines() if str(pid) in l][0]
    assert "cwd 已刪除" in line and str(gone) in line


def test_list_mode_wording_consistent_and_states_nothing_killed(env):
    pid = env.orphan()
    res = env.run()
    assert f"符合 {pid}" in res.stdout and "孤兒" not in res.stdout
    assert "未終止任何程序" in res.stdout


def test_negative_control_asserts_exit_code_and_output(env):
    pid = env.orphan(cwd=env.outside)
    res = env.run("--kill")
    assert _alive(pid)
    assert res.returncode == 0
    assert str(pid) not in res.stdout and "已終止" not in res.stdout
    assert "符合 0 略過 0" in res.stdout


# ---- KILL 後的存活判定、結果回報 ----

def _killable_world(mod, monkeypatch, tmp_path, polls_after_kill):
    """TERM 無效；KILL 送出後再被查詢 polls_after_kill 次仍存活，之後消失。"""
    state = {"left": polls_after_kill}
    sent = []

    def alive(pid):
        if signal.SIGKILL not in [s for _, s in sent]:
            return True
        state["left"] -= 1
        return state["left"] >= 0

    fake, sent_ref = _fake_world(mod, monkeypatch, tmp_path, alive=alive)
    sent.extend(sent_ref)
    monkeypatch.setattr(mod, "_send", lambda pid, sig: (sent.append((pid, sig)), sent_ref.append((pid, sig))))
    return fake, sent


def test_slow_exit_after_kill_is_reported_terminated(tmp_path, monkeypatch, capsys):
    mod = _load()
    monkeypatch.setattr(mod, "KILL_WAIT_SECONDS", 2.0, raising=True)
    _killable_world(mod, monkeypatch, tmp_path, polls_after_kill=5)
    rc = mod.main(["--kill", "--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "已終止 999999" in out and "未能終止" not in out


def test_alive_past_kill_deadline_is_failure(tmp_path, monkeypatch, capsys):
    mod = _load()
    monkeypatch.setattr(mod, "KILL_WAIT_SECONDS", 0.05, raising=True)
    _killable_world(mod, monkeypatch, tmp_path, polls_after_kill=10 ** 9)
    rc = mod.main(["--kill", "--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "未能終止 999999" in out and "已終止" not in out


def test_vanished_before_signal_reports_absent_not_terminated(tmp_path, monkeypatch, capsys):
    mod = _load()
    _, sent = _fake_world(mod, monkeypatch, tmp_path, alive=False, same=False)
    rc = mod.main(["--kill", "--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0 and sent == []
    assert "已不存在 999999" in out and "已終止" not in out


def test_ps_failure_during_terminate_is_error_exit_2(tmp_path, monkeypatch, capsys):
    mod = _load()
    fake = mod.Proc(999999, 1, "S", "flutter_tester")
    sent = []
    monkeypatch.setattr(mod, "list_processes", lambda: [fake])
    monkeypatch.setattr(mod, "process_cwd", lambda pid: str(tmp_path))
    monkeypatch.setattr(mod, "_send", lambda pid, sig: sent.append((pid, sig)))
    real = subprocess.run

    def fake_run(cmd, *a, **kw):
        if cmd[0] == "ps":
            return subprocess.CompletedProcess(cmd, 1, "", "boom")
        return real(cmd, *a, **kw)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    rc = mod.main(["--kill", "--root", str(tmp_path)])
    cap = capsys.readouterr()
    assert rc == 2 and sent == []
    assert "boom" in cap.err and "已終止" not in cap.out


def test_identity_changed_after_term_is_failure_with_distinct_message(tmp_path, monkeypatch, capsys):
    mod = _load()
    _fake_world(mod, monkeypatch, tmp_path)
    answers = iter([True, False])
    monkeypatch.setattr(mod, "_same_identity", lambda p: next(answers))
    rc = mod.main(["--kill", "--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "TERM 後身份已變" in out and "送訊號前身份已變" not in out


def test_identity_changed_before_signal_message_distinct(tmp_path, monkeypatch, capsys):
    mod = _load()
    _fake_world(mod, monkeypatch, tmp_path, same=False)
    mod.main(["--kill", "--root", str(tmp_path)])
    assert "送訊號前身份已變" in capsys.readouterr().out


# ---- 真實的 _same_identity（不經替換）----

def _command_of(pid):
    return subprocess.run(["ps", "-o", "command=", "-p", str(pid)],
                          capture_output=True, text=True).stdout.strip()


def test_real_same_identity_true_for_matching_orphan(env):
    mod = _load()
    pid = env.orphan()
    assert mod._same_identity(mod.Proc(pid, 1, "S", _command_of(pid))) is True


def test_real_same_identity_false_when_command_differs(env):
    mod = _load()
    pid = env.orphan()
    assert mod._same_identity(mod.Proc(pid, 1, "S", "some other command")) is False


def test_real_same_identity_false_when_parent_not_init(env):
    mod = _load()
    pid = env.child_of_test()
    assert mod._same_identity(mod.Proc(pid, 1, "S", _command_of(pid))) is False


def test_real_same_identity_false_for_missing_pid(env):
    mod = _load()
    pid = env.orphan()
    os.kill(pid, signal.SIGKILL)
    assert _wait_gone(pid)
    assert mod._same_identity(mod.Proc(pid, 1, "S", "flutter_tester")) is False


def test_help_lists_unsupported_forms():
    res = subprocess.run([sys.executable, str(SCRIPT), "--help"],
                         capture_output=True, text=True, timeout=30)
    for phrase in ("路徑含空白", "帶值選項", "工作程序"):
        assert phrase in res.stdout


def test_test_file_has_no_ticket_ids():
    import re
    assert not re.search(r"\d+\.\d+\.\d+-W\d+-\d+", Path(__file__).read_text())


# ---- 疑似殘留：被收養且子孫含執行器的程序樹（只顯示不終止） ----

def _tree_procs(mod):
    """父子關係表：命令首詞 flutter_tester 為執行器（見 _runner_by_name）。"""
    P = mod.Proc
    return [
        # 樹 A：根 100（父 1）> 101 > 102(flutter_tester)
        P(100, 1, "S", "dartvm flutter_tools"), P(101, 100, "S", "dartaotruntime"),
        P(102, 101, "S", "flutter_tester"),
        # 樹 B：根 200（父 1），子孫不含執行器
        P(200, 1, "S", "dartvm other"), P(201, 200, "S", "dartaotruntime"),
        # 樹 C：根 300（父 1）含執行器，但 cwd 在專案外
        P(300, 1, "S", "dartvm outside"), P(301, 300, "S", "flutter_tester"),
        # 樹 D：根 400 的父為 50（非 1），子孫含執行器
        P(400, 50, "S", "dartvm child"), P(401, 400, "S", "flutter_tester"),
        # 無關程序
        P(50, 2, "S", "zsh"),
    ]


def _runner_by_name(command):
    return command.split()[0] == "flutter_tester"


_PROJ = os.path.realpath(tempfile.gettempdir())  # 實際存在的目錄
_OUTSIDE = os.path.realpath("/usr")
_TREE_CWD = {100: _PROJ, 101: _PROJ, 102: _PROJ, 200: _PROJ, 300: _OUTSIDE,
             400: _PROJ}


def _suspects(mod, procs=None, cwd=None, roots=(_PROJ,)):
    cwds = _TREE_CWD if cwd is None else cwd
    return mod.find_suspect_trees(procs or _tree_procs(mod), list(roots),
                                  lambda pid: cwds.get(pid), _runner_by_name)


def test_suspect_tree_lists_adopted_root_with_runner_descendant():
    mod = _load()
    found = _suspects(mod)
    assert [t.root.pid for t in found] == [100]
    assert sorted(p.pid for p in found[0].members) == [100, 101, 102]


@pytest.mark.parametrize("root_pid", [200, 300, 400])
def test_suspect_tree_negative_controls_not_listed(root_pid):
    # 200：子孫不含執行器；300：cwd 在專案外；400：根的父程序非 1
    mod = _load()
    assert root_pid not in [t.root.pid for t in _suspects(mod)]


def test_suspect_tree_skips_when_root_cwd_unknown_and_never_for_runner_root():
    mod = _load()
    assert _suspects(mod, cwd={}) == []
    P = mod.Proc
    procs = [P(10, 1, "S", "flutter_tester"), P(11, 10, "S", "flutter_tester")]
    # 根本身是執行器者屬「符合」類別，不重複列為疑似殘留
    assert _suspects(mod, procs=procs, cwd={10: _PROJ}) == []


def test_suspect_tree_ignores_zombie_runner_descendant():
    mod = _load()
    P = mod.Proc
    procs = [P(1000, 1, "S", "dartvm"), P(1001, 1000, "Z", "flutter_tester")]
    assert _suspects(mod, procs=procs, cwd={1000: _PROJ}) == []


def test_suspect_tree_handles_parent_cycle_without_hanging():
    mod = _load()
    P = mod.Proc
    procs = [P(1, 1, "S", "launchd"), P(2, 3, "S", "a"), P(3, 2, "S", "b")]
    assert _suspects(mod, procs=procs) == []


@pytest.mark.parametrize("raw,shown", [("01:23", "01:23"), ("2-03:04:05", "2-03:04:05"),
                                       ("", "未知"), ("  ", "未知")])
def test_format_age_unknown_when_missing(raw, shown):
    assert _load().format_age(raw) == shown


def test_render_suspects_explains_unkilled_and_shows_age_and_pids():
    mod = _load()
    P = mod.Proc
    root = P(100, 1, "S", "dartvm", "05:07")
    tree = mod.SuspectTree(root, [root, P(102, 100, "S", "flutter_tester")])
    text = "\n".join(mod.render_suspects([tree]))
    assert "疑似殘留" in text and "100" in text and "102" in text
    assert "05:07" in text
    assert "不會被本指令終止" in text and "刻意放在背景" in text and "kill <PID>" in text
    unknown = mod.SuspectTree(P(7, 1, "S", "dartvm"), [P(7, 1, "S", "dartvm")])
    assert "存活 未知" in "\n".join(mod.render_suspects([unknown]))


class TreeEnv:
    """真實替身樹：根(父為 1、argv0 dartvm) > flutter_tester。"""
    ROOT_SRC = (
        "import subprocess,sys,time\n"
        "pidfile=sys.argv[1]\n"
        "subprocess.Popen(['flutter_tester','-c',%r,pidfile,'0'],executable=sys.executable)\n"
        "time.sleep(%d)\n" % (STAND_IN_SRC, LIFE)
    )
    LAUNCHER = (
        "import subprocess,sys\n"
        "cwd,pidfile,rootfile=sys.argv[1:4]\n"
        "p=subprocess.Popen(['dartvm','-c',%r,pidfile],executable=sys.executable,"
        "cwd=cwd,start_new_session=True)\n"
        "open(rootfile,'w').write(str(p.pid))\n" % ROOT_SRC
    )


def _start_tree(env):
    pidfile, rootfile = env.tmp / "child", env.tmp / "rootpid"
    subprocess.run([sys.executable, "-c", TreeEnv.LAUNCHER, str(env.root),
                    str(pidfile), str(rootfile)], check=True, timeout=15)
    root_pid, child_pid = _wait_pid(rootfile), _wait_pid(pidfile)
    env.pids += [root_pid, child_pid]
    deadline = time.monotonic() + 10
    while _ppid(root_pid) != 1 and time.monotonic() < deadline:
        time.sleep(0.05)
    return root_pid, child_pid


def test_kill_never_signals_suspect_tree_but_still_kills_matched(env):
    root_pid, child_pid = _start_tree(env)
    matched = env.orphan()
    res = env.run("--kill")
    assert res.returncode == 0
    assert _wait_gone(matched)  # 對照：現行符合類別仍被終止
    assert _alive(root_pid) and _alive(child_pid)
    assert f"疑似殘留" in res.stdout and str(root_pid) in res.stdout
    assert "未處理" in res.stdout
    assert "疑似殘留 1" in res.stdout


def test_list_mode_shows_suspect_tree_with_age(env):
    root_pid, child_pid = _start_tree(env)
    res = env.run()
    assert res.returncode == 0
    assert str(root_pid) in res.stdout and str(child_pid) in res.stdout
    assert "存活" in res.stdout and "符合 0 略過 0 疑似殘留 1" in res.stdout
    assert _alive(root_pid) and _alive(child_pid)


# ---- 登記群組（讀取端；寫入端格式由真實包裝腳本產生，兩邊一致由本節測試確保）----

import json  # noqa: E402

WRAPPER = SCRIPT.parent / "run-with-timeout.py"
SLEEPER_SRC = ("import os,sys,time\n"
               "open(sys.argv[1],'w').write(str(os.getpid()))\n"
               "time.sleep(%d)\n" % LIFE)


class RegEnv:
    def __init__(self, env):
        self.env = env
        self.reg = env.tmp / "reg"
        self.wrappers = []
        self.n = 0

    def _environ(self, **extra):
        return {**os.environ, "CLAUDE_PROC_REGISTRY_DIR": str(self.reg), **extra}

    def start_wrapper(self, **extra_env):
        """以真實包裝腳本啟動替身；回傳 (wrapper Popen, 替身 pid, 登記檔)。"""
        self.n += 1
        pidfile = self.env.tmp / ("sleeper%d" % self.n)
        w = subprocess.Popen([sys.executable, str(WRAPPER), "60", "--", sys.executable, "-c",
                              SLEEPER_SRC, str(pidfile)], cwd=str(self.env.root),
                             env=self._environ(**extra_env), stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        self.wrappers.append(w)
        pid = _wait_pid(pidfile)
        self.env.pids.append(pid)
        deadline = time.monotonic() + 10
        while not list(self.reg.glob("wrapper-%d-*.json" % w.pid)) and time.monotonic() < deadline:
            time.sleep(0.05)
        return w, pid, next(iter(self.reg.glob("wrapper-%d-*.json" % w.pid)))

    def run(self, *args, **extra_env):
        return subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.env.root), *args],
                              capture_output=True, text=True, timeout=60,
                              env=self._environ(**extra_env))

    def files(self):
        return sorted(self.reg.glob("*.json")) if self.reg.exists() else []


@pytest.fixture
def renv(env):
    r = RegEnv(env)
    yield r
    for w in r.wrappers:
        if w.poll() is None:
            w.kill()
        w.wait()


def _sigkill_wrapper(w):
    w.kill()
    w.wait(timeout=10)


def test_registered_group_listed_then_killed_after_wrapper_sigkill(renv):
    w, pid, entry = renv.start_wrapper()
    _sigkill_wrapper(w)
    listed = renv.run()
    assert "登記可終止" in listed.stdout and "僅列出" in listed.stdout
    assert _alive(pid) and entry.exists()  # 不帶 --kill 不送訊號、不動登記
    res = renv.run("--kill")
    assert res.returncode == 0 and "登記已終止" in res.stdout
    assert _wait_gone(pid)
    assert renv.files() == []


def test_contrast_wrapper_alive_sends_no_signal(renv):
    w, pid, entry = renv.start_wrapper()
    res = renv.run("--kill")
    assert "登記略過" in res.stdout and "包裝腳本仍存活" in res.stdout
    assert _alive(pid) and entry.exists()


def test_contrast_leader_start_mismatch_sends_no_signal_and_reports(renv):
    w, pid, entry = renv.start_wrapper()
    _sigkill_wrapper(w)
    data = json.loads(entry.read_text())
    data["leader_start"] = "Mon Jan  1 00:00:00 2001"
    entry.write_text(json.dumps(data))
    res = renv.run("--kill")
    assert "登記不終止" in res.stdout and "啟動時間不符" in res.stdout
    assert _alive(pid)
    assert renv.files() == []  # 過期登記已移除


def test_contrast_leader_gone_but_group_has_members_is_not_killed(renv):
    """領頭已結束、同群組仍有成員（編號可能被重用）：只列出不終止。"""
    holder = renv.env.tmp / "member"
    launcher = ("import subprocess,sys,time\n"
                "subprocess.Popen([sys.executable,'-c',%r,sys.argv[1]])\n"
                "time.sleep(1)\n" % SLEEPER_SRC)
    leader = subprocess.Popen([sys.executable, "-c", launcher, str(holder)],
                              start_new_session=True)
    member = _wait_pid(holder)
    renv.env.pids.append(member)
    start = _load().process_start(leader.pid)
    renv.reg.mkdir(mode=0o700)
    entry = renv.reg / "wrapper-999999.json"
    entry.write_text(json.dumps({
        "pgid": leader.pid, "leader_start": start, "wrapper_pid": _dead_pid(),
        "wrapper_start": "Mon Jan  1 00:00:00 2001", "cwd": str(renv.env.root),
        "command": ["x"]}))
    leader.wait(timeout=10)
    res = renv.run("--kill")
    assert "登記不終止" in res.stdout and "已不在" in res.stdout
    assert _alive(member)
    assert renv.files() == []


def test_registry_outside_project_scope_untouched(renv):
    w, pid, entry = renv.start_wrapper()
    _sigkill_wrapper(w)
    other = renv.env.outside
    res = subprocess.run([sys.executable, str(SCRIPT), "--root", str(other), "--kill"],
                         capture_output=True, text=True, timeout=60, env=renv._environ())
    assert "登記" not in res.stdout
    assert _alive(pid) and entry.exists()


def test_corrupt_entry_reported_and_other_entries_still_processed(renv):
    w, pid, entry = renv.start_wrapper()
    _sigkill_wrapper(w)
    bad = renv.reg / "wrapper-1.json"
    bad.write_text("{not json")
    res = renv.run("--kill")
    assert res.returncode == 0
    assert "登記無法讀取" in res.stdout and "wrapper-1.json" in res.stdout
    assert _wait_gone(pid) and bad.exists()


def test_unreadable_registry_dir_reported_without_abort(renv):
    renv.reg.mkdir(mode=0o700)
    renv.reg.chmod(0)
    try:
        res = renv.run("--kill")
    finally:
        renv.reg.chmod(0o700)
    assert res.returncode == 0
    assert "登記無法讀取" in res.stdout


def test_missing_registry_dir_is_empty(renv):
    res = renv.run("--kill")
    assert res.returncode == 0 and "登記" not in res.stdout


def test_unsafe_registry_dir_is_not_read_or_acted_on(renv):
    """群組可寫的登記目錄不採信：即使內有登記檔也不列出、不終止，且回報原因。"""
    w, pid, entry = renv.start_wrapper()
    _sigkill_wrapper(w)
    renv.reg.chmod(0o770)
    try:
        res = renv.run("--kill")
    finally:
        renv.reg.chmod(0o700)
    assert res.returncode == 0
    assert "登記目錄不安全" in res.stdout and "登記已終止" not in res.stdout
    assert _alive(pid) and entry.exists()


def test_symlinked_registry_dir_is_not_read(renv, tmp_path):
    real = tmp_path / "real-reg"
    real.mkdir(mode=0o700)
    renv.reg.symlink_to(real)
    res = renv.run("--kill")
    assert res.returncode == 0 and "登記目錄不安全" in res.stdout


def test_machine_readable_summary_line_matches_human_line(renv):
    """機器可讀契約行與人讀行數字一致；count_orphans 只解析前者。"""
    import re
    res = renv.run()
    human = re.search(r"^符合 (\d+) 略過 (\d+) 疑似殘留 (\d+)$", res.stdout, re.M)
    machine = re.search(r"^ORPHAN_SUMMARY matched=(\d+) skipped=(\d+) suspects=(\d+) registered=(\d+)$",
                        res.stdout, re.M)
    assert human and machine and human.groups() == machine.groups()[:3]


def test_summary_registered_counts_killable_registry_entries(renv):
    import re
    w, _pid, _entry = renv.start_wrapper()
    _sigkill_wrapper(w)
    res = renv.run()
    machine = re.search(r"registered=(\d+)", res.stdout)
    assert "登記可終止" in res.stdout and machine and int(machine.group(1)) == 1


# ---- 登記群組：KILL 升級、登記驗證、查詢失敗、時區、過期登記 ----

# 領頭：啟動一個忽略 TERM 的成員後，收到 TERM 即退出（模擬領頭先走、成員殘留）
MEMBER_SRC = ("import os,signal,sys,time\n"
              "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
              "open(sys.argv[1],'w').write(str(os.getpid()))\n"
              "time.sleep(%d)\n" % LIFE)
LEADER_SRC = ("import signal,subprocess,sys,time\n"
              "subprocess.Popen([sys.executable,'-c',%r,sys.argv[1]])\n"
              "signal.signal(signal.SIGTERM, lambda *a: sys.exit(0))\n"
              "time.sleep(%d)\n" % (MEMBER_SRC, LIFE))


def _reap_in_background(proc):
    """領頭退出後立即被回收，使其 PID 查無（而非殭屍）。"""
    import threading
    threading.Thread(target=proc.wait, daemon=True).start()


def _start_term_exiting_group(renv):
    """領頭收 TERM 即退出、另一成員忽略 TERM；回傳 (領頭 Popen, 成員 pid, 登記檔)。"""
    holder = renv.env.tmp / ("member%d" % renv.n)
    renv.n += 1
    leader = subprocess.Popen([sys.executable, "-c", LEADER_SRC, str(holder)],
                              start_new_session=True)
    _reap_in_background(leader)
    member = _wait_pid(holder)
    renv.env.pids.append(member)
    renv.env.pids.append(leader.pid)
    entry = write_entry(renv, leader.pid)
    return leader, member, entry


def write_entry(renv, pgid, wrapper_pid=None, name=None, **override):
    mod = _load()
    wrapper_pid = wrapper_pid or _dead_pid()
    renv.reg.mkdir(mode=0o700, exist_ok=True)
    data = {"pgid": pgid, "leader_start": mod.process_start(pgid) or "x",
            "wrapper_pid": wrapper_pid, "wrapper_start": "Mon Jan  1 00:00:00 2001",
            "cwd": str(renv.env.root), "command": ["x"]}
    data.update(override)
    path = renv.reg / (name or "wrapper-%d-test.json" % wrapper_pid)
    path.write_text(json.dumps(data))
    return path


def test_kill_escalates_when_leader_exits_on_term_and_member_ignores_term(renv):
    leader, member, entry = _start_term_exiting_group(renv)
    res = renv.run("--kill")
    assert res.returncode == 0, res.stdout
    assert "登記已終止" in res.stdout and "身份已變" not in res.stdout and "啟動時間已變" not in res.stdout
    assert _wait_gone(member)
    assert renv.files() == []


def test_contrast_leader_start_changes_before_kill_sends_no_kill_and_fails(tmp_path, monkeypatch, capsys):
    """TERM 後領頭程序仍在、但啟動時間與登記不符：不送 KILL，回報未能終止，結束碼非 0。"""
    mod = _load()
    sent = []
    starts = iter(["T0", "OTHER"])  # 送 TERM 前通過；KILL 前驗證不符
    monkeypatch.setattr(mod, "process_start", lambda pid: next(starts, "OTHER"))
    monkeypatch.setattr(mod, "group_members", lambda pgid: [4242])
    monkeypatch.setattr(mod.os, "killpg", lambda pgid, sig: sent.append(sig))
    e = mod.RegEntry(str(tmp_path / "e.json"), 4000, "T0", 999999, "W0", str(tmp_path), ["x"])
    assert mod.terminate_registered(e, grace=0.1) == "changed_after_term"
    assert sent == [signal.SIGTERM]


def test_changed_after_term_is_reported_as_failure(tmp_path, monkeypatch, capsys):
    mod = _load()
    monkeypatch.setenv("CLAUDE_PROC_REGISTRY_DIR", str(tmp_path / "reg"))
    (tmp_path / "reg").mkdir(mode=0o700)
    entry = tmp_path / "reg" / "wrapper-999999-x.json"
    entry.write_text(json.dumps({"pgid": 4000, "leader_start": "T0", "wrapper_pid": 999999,
                                 "wrapper_start": "W0", "cwd": str(tmp_path), "command": ["x"]}))
    monkeypatch.setattr(mod, "process_start", lambda pid: None if pid == 999999 else "T0")
    monkeypatch.setattr(mod, "group_members", lambda pgid: [4242])
    monkeypatch.setattr(mod, "terminate_registered", lambda e: "changed_after_term")
    failed = mod.process_registry([str(tmp_path)], True)
    out = capsys.readouterr().out
    assert failed == 1 and "登記未能終止" in out and "啟動時間不符" in out


BAD_PGIDS = ["0", "1", "-5", "true", "false", "2.0", "2.5", '"7"', "GETPGRP"]


@pytest.mark.parametrize("raw", BAD_PGIDS)
def test_invalid_pgid_is_corrupt_entry_and_sends_no_signal(raw, tmp_path, monkeypatch, capsys):
    mod = _load()
    reg = tmp_path / "reg"
    reg.mkdir(mode=0o700)
    monkeypatch.setenv("CLAUDE_PROC_REGISTRY_DIR", str(reg))
    raw = str(os.getpgrp()) if raw == "GETPGRP" else raw
    path = reg / "wrapper-999999-x.json"
    path.write_text('{"pgid": %s, "leader_start": "T0", "wrapper_pid": 999999, '
                    '"wrapper_start": "W0", "cwd": "%s", "command": ["x"]}' % (raw, tmp_path))
    sent = []
    monkeypatch.setattr(mod.os, "killpg", lambda pgid, sig: sent.append((pgid, sig)))
    failed = mod.process_registry([str(tmp_path)], True)
    out = capsys.readouterr().out
    assert sent == [] and failed == 0
    assert "登記無法讀取" in out and path.exists()


def test_killpg_unexpected_oserror_reported_as_error_not_raised(tmp_path, monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "process_start", lambda pid: "T0")
    monkeypatch.setattr(mod, "group_members", lambda pgid: [4242])

    def boom(pgid, sig):
        raise OSError(22, "Invalid argument")
    monkeypatch.setattr(mod.os, "killpg", boom)
    e = mod.RegEntry(str(tmp_path / "e.json"), 4000, "T0", 999999, "W0", str(tmp_path), ["x"])
    assert mod.terminate_registered(e, grace=0.1) == "error"


def test_ps_failure_on_one_entry_is_error_others_and_classes_still_processed(env, tmp_path, monkeypatch, capsys):
    mod = _load()
    reg = tmp_path / "reg"
    reg.mkdir(mode=0o700)
    monkeypatch.setenv("CLAUDE_PROC_REGISTRY_DIR", str(reg))
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    base = {"leader_start": "T0", "wrapper_start": "W0", "cwd": str(env.root), "command": ["x"]}
    a = reg / "wrapper-777001-a.json"
    a.write_text(json.dumps({**base, "pgid": 888001, "wrapper_pid": 777001}))
    b = reg / "wrapper-b.json"
    b.write_text(json.dumps({**base, "pgid": dead.pid, "wrapper_pid": _dead_pid()}))
    real = mod.process_start

    def flaky(pid):
        if pid == 777001:
            raise mod.CommandError("ps 失敗")
        return real(pid)
    monkeypatch.setattr(mod, "process_start", flaky)
    killpg_calls = []
    monkeypatch.setattr(mod.os, "killpg", lambda pgid, sig: killpg_calls.append(pgid))
    orphan = env.orphan()
    rc = mod.main(["--root", str(env.root), "--kill"])
    out = capsys.readouterr().out
    assert rc != 0 and "登記查詢失敗" in out
    assert a.exists() and killpg_calls == []
    assert not b.exists()  # 另一筆登記照常處理（已過期，移除）
    assert "已終止 %d" % orphan in out  # 既有類別照常處理


def test_process_start_ignores_timezone_env(monkeypatch):
    mod = _load()
    monkeypatch.setenv("TZ", "Asia/Tokyo")
    tokyo = mod.process_start(os.getpid())
    monkeypatch.setenv("TZ", "America/Los_Angeles")
    assert tokyo is not None and mod.process_start(os.getpid()) == tokyo


def test_live_wrapper_still_alive_under_different_timezone(renv):
    w, pid, entry = renv.start_wrapper(TZ="Asia/Tokyo")
    res = renv.run("--kill", TZ="America/Los_Angeles")
    assert "登記略過" in res.stdout and "包裝腳本仍存活" in res.stdout
    assert _alive(pid) and entry.exists()


def test_out_of_scope_entry_with_empty_group_is_removed(renv):
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    entry = write_entry(renv, dead.pid, cwd=str(renv.env.outside))
    res = renv.run("--kill")
    assert res.returncode == 0
    assert not entry.exists()


def test_process_start_query_failure_distinct_from_missing(monkeypatch):
    mod = _load()
    assert mod.process_start(_dead_pid()) is None  # 不存在：None，不拋

    def failing(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 3, "", "ps: boom")
    monkeypatch.setattr(mod.subprocess, "run", failing)
    with pytest.raises(mod.CommandError):
        mod.process_start(os.getpid())
