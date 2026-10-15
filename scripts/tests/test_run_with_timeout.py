"""run-with-timeout.py 測試：僅使用暫存目錄與會自行結束的替身程序。"""
import importlib.util
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "run-with-timeout.py"
STAND_IN_LIFETIME = 30  # 替身程序存活上限（秒），保證測試即使失敗也會自行收尾

# 替身：產生握住輸出管線的孫程序，把兩者 PID 寫入檔案後等待
PARENT_SRC = """
import os, signal, subprocess, sys, time
pidfile, ignore_term = sys.argv[1], sys.argv[2] == "1"
if ignore_term:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
grand = subprocess.Popen([sys.executable, "-c",
    "import signal,time\\nif %r: signal.signal(signal.SIGTERM, signal.SIG_IGN)\\ntime.sleep(LIFE)" % ignore_term])
open(pidfile, "w").write("%d %d" % (os.getpid(), grand.pid))
time.sleep(LIFE)
""".replace("LIFE", str(STAND_IN_LIFETIME))


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _read_pids(pidfile: Path):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if pidfile.exists() and len(pidfile.read_text().split()) == 2:
            return [int(p) for p in pidfile.read_text().split()]
        time.sleep(0.05)
    raise AssertionError("替身未寫出 PID")


def _wait_dead(pids, within=8.0):
    deadline = time.monotonic() + within
    while time.monotonic() < deadline and any(_alive(p) for p in pids):
        time.sleep(0.05)
    return [p for p in pids if _alive(p)]


@pytest.fixture
def stand_in(tmp_path):
    parent = tmp_path / "parent.py"
    parent.write_text(PARENT_SRC)
    pidfile = tmp_path / "pids"
    yield parent, pidfile
    if pidfile.exists() and len(pidfile.read_text().split()) == 2:
        for pid in _read_pids(pidfile):
            try:
                os.kill(pid, signal.SIGKILL)  # 以記下的 PID 清理
            except ProcessLookupError:
                pass


def _cmd(parent, pidfile, ignore_term="0", seconds="1"):
    return [sys.executable, str(SCRIPT), seconds, "--",
            sys.executable, str(parent), str(pidfile), ignore_term]


def test_timeout_kills_child_and_grandchild_exit_124(stand_in):
    parent, pidfile = stand_in
    res = subprocess.run(_cmd(parent, pidfile), capture_output=True, timeout=25)
    assert res.returncode == 124
    assert _wait_dead(_read_pids(pidfile)) == []


def _load_module():
    spec = importlib.util.spec_from_file_location("rwt", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_contrast_kill_direct_child_only_leaves_grandchild(stand_in):
    """變異：群組終止改為只終止直接子程序，孫程序存活，
    即上一測試的斷言（_wait_dead == []）在此變異下會翻紅。"""
    parent, pidfile = stand_in
    mod = _load_module()
    mod.terminate_group = lambda pgid, grace=0, leader=None: os.kill(pgid, signal.SIGKILL)
    assert mod.run(1, [sys.executable, str(parent), str(pidfile), "0"]) == 124
    survivors = _wait_dead(_read_pids(pidfile), within=1.0)
    assert survivors, "變異版應遺留孫程序"


def test_passthrough_exit_code_and_output():
    res = subprocess.run(
        [sys.executable, str(SCRIPT), "10", "--", sys.executable, "-c",
         "import sys;print('out');sys.stderr.write('err\\n');sys.exit(7)"],
        capture_output=True, text=True, timeout=20)
    assert (res.returncode, res.stdout, res.stderr) == (7, "out\n", "err\n")


def test_command_not_found_exit_127_single_line_message():
    res = subprocess.run(
        [sys.executable, str(SCRIPT), "5", "--", "no-such-command-for-run-with-timeout"],
        capture_output=True, text=True, timeout=20)
    assert res.returncode == 127
    assert len(res.stderr.strip().splitlines()) == 1
    assert "Traceback" not in res.stderr


def _assert_single_line_no_traceback(stderr: str) -> None:
    assert len(stderr.strip().splitlines()) == 1
    assert "Traceback" not in stderr
    assert stderr.startswith("run-with-timeout:")


def test_not_executable_file_exit_126_single_line_message(tmp_path):
    target = tmp_path / "no-exec-bit"
    target.write_text("#!/bin/sh\nexit 0\n")
    target.chmod(0o644)
    res = subprocess.run([sys.executable, str(SCRIPT), "5", "--", str(target)],
                         capture_output=True, text=True, timeout=20)
    assert res.returncode == 126
    _assert_single_line_no_traceback(res.stderr)


def test_exec_format_error_exit_126_single_line_message(tmp_path):
    """有執行權限但無 shebang 的文字檔：啟動失敗不屬找不到也不屬權限不足。"""
    target = tmp_path / "no-shebang"
    target.write_text("not a program\n")
    target.chmod(0o755)
    res = subprocess.run([sys.executable, str(SCRIPT), "5", "--", str(target)],
                         capture_output=True, text=True, timeout=20)
    assert res.returncode == 126
    _assert_single_line_no_traceback(res.stderr)


def test_non_numeric_seconds_exit_2_without_traceback():
    res = subprocess.run([sys.executable, str(SCRIPT), "abc", "--", "true"],
                         capture_output=True, text=True, timeout=20)
    assert res.returncode == 2
    assert "Traceback" not in res.stderr
    assert "abc" in res.stderr


def test_child_killed_by_signal_exit_128_plus_signum():
    res = subprocess.run(
        [sys.executable, str(SCRIPT), "10", "--", sys.executable, "-c",
         "import os,signal;os.kill(os.getpid(),signal.SIGKILL)"],
        capture_output=True, timeout=20)
    assert res.returncode == 128 + signal.SIGKILL


def _wait_zombie(pid: int, within=10.0) -> None:
    """等到程序結束但未被回收（ps 狀態欄以 Z 開頭），逾期拋 AssertionError。

    以輪詢 ps 判定，因 os.waitid（WNOWAIT）在 macOS 的 Python 不提供。
    """
    deadline = time.monotonic() + within
    stat = ""
    while time.monotonic() < deadline:
        stat = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)],
                              capture_output=True, text=True).stdout.strip()
        if stat.startswith("Z"):
            return
        time.sleep(0.2)
    raise AssertionError(
        f"程序 {pid} 於 {within} 秒內未進入殭屍狀態"
        f"（最後 ps 狀態：{stat!r}，空字串表示程序已不存在）")


@pytest.fixture
def zombie_only_group():
    """領頭程序已結束但未回收的程序群組。"""
    proc = subprocess.Popen([sys.executable, "-c", "pass"], start_new_session=True)
    try:
        _wait_zombie(proc.pid)
        yield proc.pid
    finally:
        proc.wait()


def test_signal_zombie_only_group_does_not_raise(zombie_only_group):
    mod = _load_module()
    for sig in (signal.SIGTERM, signal.SIGKILL):
        mod._signal_group(zombie_only_group, sig)


def test_group_alive_on_zombie_only_group_reports_alive(zombie_only_group):
    """領頭程序尚未回收時群組仍算存在，由呼叫端回收後才轉為不存在。"""
    mod = _load_module()
    assert mod._group_alive(zombie_only_group) is True


@pytest.mark.skipif(
    sys.platform != "darwin",
    reason="僅於 macOS 實測到對殭屍群組送訊號回 EPERM；其他平台不保證拋例外，對照不成立")
def test_contrast_raw_killpg_on_zombie_only_group_raises(zombie_only_group):
    """對照：同一群組不經保護直接送訊號會拋 PermissionError。

    即移除 _signal_group 或 _group_alive 的 PermissionError 處理時，
    test_signal_zombie_only_group_does_not_raise 與
    test_group_alive_on_zombie_only_group_reports_alive 在 macOS 上會翻紅。
    """
    for sig in (0, signal.SIGKILL):
        with pytest.raises(PermissionError):
            os.killpg(zombie_only_group, sig)


def test_wrapper_term_ends_whole_group(stand_in):
    parent, pidfile = stand_in
    wrapper = subprocess.Popen(_cmd(parent, pidfile, seconds="20"),
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        pids = _read_pids(pidfile)
        wrapper.send_signal(signal.SIGTERM)
        wrapper.wait(timeout=15)
        assert _wait_dead(pids) == []
    finally:
        if wrapper.poll() is None:
            wrapper.kill()


def test_term_ignoring_child_is_killed_within_bound(stand_in):
    parent, pidfile = stand_in
    start = time.monotonic()
    res = subprocess.run(_cmd(parent, pidfile, "1"), capture_output=True, timeout=25)
    elapsed = time.monotonic() - start
    assert res.returncode == 124
    assert _wait_dead(_read_pids(pidfile)) == []
    assert elapsed < 1 + 3.0 + 5  # 逾時 + 寬限 + 餘裕


# ---- 程序群組登記（寫入端；讀取端見 test_orphan_test_procs.py）----

REG_FIELDS = {"pgid", "leader_start", "wrapper_pid", "wrapper_start", "cwd", "command"}
LIST_REG_SRC = ("import os,sys,time;time.sleep(1);d=os.environ['CLAUDE_PROC_REGISTRY_DIR'];"
                "print(len([n for n in os.listdir(d) if n.endswith('.json')]))")


def _reg_files(d: Path):
    return sorted(p for p in d.iterdir() if p.name.endswith(".json")) if d.exists() else []


def _env(d: Path):
    return {**os.environ, "CLAUDE_PROC_REGISTRY_DIR": str(d)}


def _wait_reg(d: Path, within=10.0):
    deadline = time.monotonic() + within
    while time.monotonic() < deadline:
        if _reg_files(d):
            return _reg_files(d)[0]
        time.sleep(0.05)
    raise AssertionError("登記未出現")


def test_registry_written_during_run_and_removed_after_normal_exit(tmp_path):
    reg = tmp_path / "reg"
    res = subprocess.run([sys.executable, str(SCRIPT), "10", "--", sys.executable, "-c", LIST_REG_SRC],
                         capture_output=True, text=True, timeout=20, env=_env(reg))
    assert (res.returncode, res.stdout.strip()) == (0, "1")  # 執行期間登記存在
    assert _reg_files(reg) == []


def test_registry_removed_after_timeout(stand_in, tmp_path):
    parent, pidfile = stand_in
    reg = tmp_path / "reg"
    res = subprocess.run(_cmd(parent, pidfile), capture_output=True, timeout=25, env=_env(reg))
    assert res.returncode == 124
    assert _reg_files(reg) == []


def test_registry_removed_after_term_and_content_has_fields(stand_in, tmp_path):
    import json
    parent, pidfile = stand_in
    reg = tmp_path / "reg"
    wrapper = subprocess.Popen(_cmd(parent, pidfile, seconds="20"), env=_env(reg),
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        pids = _read_pids(pidfile)
        data = json.loads(_wait_reg(reg).read_text())
        assert set(data) == REG_FIELDS
        assert data["pgid"] == pids[0] and data["wrapper_pid"] == wrapper.pid
        wrapper.send_signal(signal.SIGTERM)
        wrapper.wait(timeout=15)
        assert _wait_dead(pids) == []
        assert _reg_files(reg) == []
    finally:
        if wrapper.poll() is None:
            wrapper.kill()


def test_registry_remains_after_wrapper_sigkill(stand_in, tmp_path):
    parent, pidfile = stand_in
    reg = tmp_path / "reg"
    wrapper = subprocess.Popen(_cmd(parent, pidfile, seconds="20"), env=_env(reg),
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    pids = _read_pids(pidfile)
    _wait_reg(reg)
    wrapper.kill()
    wrapper.wait(timeout=10)
    assert len(_reg_files(reg)) == 1
    for pid in pids:
        assert _alive(pid)  # 群組存活，等待清理指令處理


def test_unwritable_registry_does_not_affect_command_or_exit_code(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    reg = blocker / "sub"  # 父層是檔案，無法建立目錄
    res = subprocess.run([sys.executable, str(SCRIPT), "10", "--", sys.executable, "-c",
                          "print('ran');import sys;sys.exit(7)"],
                         capture_output=True, text=True, timeout=20, env=_env(reg))
    assert (res.returncode, res.stdout.strip()) == (7, "ran")
    assert res.stderr.startswith("run-with-timeout:") and len(res.stderr.strip().splitlines()) == 1
    assert "Traceback" not in res.stderr


def test_registry_filename_contains_wrapper_start_time(stand_in, tmp_path):
    import re
    parent, pidfile = stand_in
    reg = tmp_path / "reg"
    wrapper = subprocess.Popen(_cmd(parent, pidfile, seconds="20"), env=_env(reg),
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        _read_pids(pidfile)
        path = _wait_reg(reg)
        start = _load_module().process_start(wrapper.pid)
        assert path.name == "wrapper-%d-%s.json" % (wrapper.pid, re.sub(r"[^0-9A-Za-z]+", "-", start))
    finally:
        wrapper.kill()
        wrapper.wait()


def test_process_start_ignores_timezone_env(monkeypatch):
    mod = _load_module()
    monkeypatch.setenv("TZ", "Asia/Tokyo")
    tokyo = mod.process_start(os.getpid())
    monkeypatch.setenv("TZ", "America/Los_Angeles")
    assert tokyo is not None and mod.process_start(os.getpid()) == tokyo


@pytest.mark.parametrize("failing", ["replace", "dump"])
def test_interrupted_registry_write_leaves_no_temp_file(failing, tmp_path, monkeypatch, capsys):
    mod = _load_module()
    reg = tmp_path / "reg"
    monkeypatch.setenv("CLAUDE_PROC_REGISTRY_DIR", str(reg))
    if failing == "replace":
        monkeypatch.setattr(mod.os, "replace", lambda a, b: (_ for _ in ()).throw(OSError("中斷")))
    else:
        monkeypatch.setattr(mod.json, "dump", lambda *a, **k: (_ for _ in ()).throw(OSError("中斷")))
    assert mod.register_group(os.getpid(), ["x"]) is None
    assert list(reg.iterdir()) == []
    assert capsys.readouterr().err.startswith("run-with-timeout:")


# ---- 訊號處理器安裝時機、內部例外清理、清理期間再收訊號（0.5.0-W1-187.9）----

# 在子程序啟動回傳後立即制造指定事件，模擬「啟動之後、處理器生效之前」的空窗
HARNESS_SRC = """
import importlib.util, os, signal, subprocess, sys
spec = importlib.util.spec_from_file_location("rwt", sys.argv[1])
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
mode, pidfile = sys.argv[2], sys.argv[3]
real_popen, fired = subprocess.Popen, []
def popen(*a, **k):
    proc = real_popen(*a, **k)
    if not fired:
        fired.append(1)
        open(pidfile, "w").write("%d" % proc.pid)
        if mode == "signal":
            os.kill(os.getpid(), signal.SIGTERM)
    return proc
subprocess.Popen = popen
if mode == "raise":
    def boom(*a, **k): raise RuntimeError("內部例外")
    mod.register_group = boom
sys.exit(mod.run(30, [sys.executable, "-c", "import time; time.sleep(%d)" % LIFE]))
""".replace("LIFE", str(STAND_IN_LIFETIME))


def _run_harness(tmp_path, mode):
    harness = tmp_path / "harness.py"
    harness.write_text(HARNESS_SRC)
    pidfile = tmp_path / "hpid"
    res = subprocess.run([sys.executable, str(harness), str(SCRIPT), mode, str(pidfile)],
                         capture_output=True, text=True, timeout=25)
    child = int(pidfile.read_text())
    try:
        assert _wait_dead([child]) == [], "子程序群組未被終止"
    finally:
        try:
            os.killpg(child, signal.SIGKILL)  # 測試失敗時的收尾
        except (ProcessLookupError, PermissionError):
            pass
    return res


def test_signal_between_spawn_and_handler_still_kills_group(tmp_path):
    res = _run_harness(tmp_path, "signal")
    assert res.returncode == 128 + signal.SIGTERM


def test_internal_exception_after_spawn_kills_group(tmp_path):
    res = _run_harness(tmp_path, "raise")
    assert res.returncode != 0 and "內部例外" in res.stderr


def test_term_during_timeout_cleanup_keeps_exit_124(tmp_path):
    """子程序收到逾時 TERM 時寫標記並忽略之，標記出現即確定清理中，再送 TERM。"""
    marker = tmp_path / "got-term"
    src = ("import signal,time;"
           "signal.signal(signal.SIGTERM, lambda *a: open(%r,'w').write('x'));"
           "time.sleep(%d)" % (str(marker), STAND_IN_LIFETIME))
    wrapper = subprocess.Popen([sys.executable, str(SCRIPT), "1", "--", sys.executable, "-c", src],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 20
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert marker.exists()
        wrapper.send_signal(signal.SIGTERM)
        assert wrapper.wait(timeout=15) == 124
    finally:
        if wrapper.poll() is None:
            wrapper.kill()


def test_usage_message_prefixed_and_lists_exit_codes():
    res = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, timeout=20)
    assert res.returncode == 2
    assert res.stderr.startswith("run-with-timeout:")
    assert "2" in res.stderr and "128" in res.stderr


# ---- 本機名額閘門（heavy 命令全機只跑一份）----
# 替身 pytest／flutter 放在 tmp PATH：以真實的 heavy／light 判定走完整路徑，不跑任何真實測試套件。
# 鎖目錄一律指向 tmp_path，不碰全機共用的鎖目錄。替身的輸出檔與存活秒數由環境變數傳入。

PROBE_SRC = """#!{python}
import os, sys, time
out, life = os.environ["PROBE_OUT"], float(os.environ["PROBE_LIFE"])
open(out + ".start", "w").write("%d %r" % (os.getpid(), time.time()))
time.sleep(life)
open(out + ".end", "w").write("%r" % time.time())
"""

HEAVY_ARGV = ["pytest", "tests/"]  # 未指定具體測試檔 -> heavy
LIGHT_ARGV = ["pytest", "tests/test_x.py"]  # 指定具體測試檔 -> light


def _orphan_stub(tmp_path, body):
    """替身 orphan-test-procs.py：預設輸出無孤兒，不查詢任何真實程序。"""
    stub = tmp_path / "orphan-stub.py"
    stub.write_text(body)
    return stub


@pytest.fixture
def gate(tmp_path):
    """回傳 (env, tmp_path, procs)；procs 內的程序於測試結束時整群清除。"""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for name in ("pytest", "flutter"):
        probe = bindir / name
        probe.write_text(PROBE_SRC.format(python=sys.executable))
        probe.chmod(0o755)
    env = dict(os.environ)
    env.update({
        "PATH": f"{bindir}{os.pathsep}{env['PATH']}",
        "CLAUDE_SLOT_LOCK_DIR": str(tmp_path / "locks"),
        "CLAUDE_PROC_REGISTRY_DIR": str(tmp_path / "reg"),
        "CLAUDE_ORPHAN_SCRIPT": str(_orphan_stub(tmp_path, "print('ORPHAN_SUMMARY matched=0 skipped=0 suspects=0 registered=0')")),
    })
    procs = []
    yield env, tmp_path, procs
    for proc in procs:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        proc.wait()
    for pidfile in tmp_path.glob("*.start"):
        try:
            pid = int(pidfile.read_text().split()[0])
            if pid > 1:
                os.kill(pid, signal.SIGKILL)  # 脫離群組的替身
        except (ProcessLookupError, ValueError, IndexError):
            pass


def _spawn(gate, name, argv, life=30, seconds="30", **env_extra):
    env, tmp_path, procs = gate
    out = tmp_path / name
    cmd = [sys.executable, str(SCRIPT), seconds, "--"] + [a.replace("OUT", str(out)) for a in argv]
    proc_env = {**env, "PROBE_OUT": str(out), "PROBE_LIFE": str(life), **env_extra}
    proc = subprocess.Popen(cmd, env=proc_env, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, start_new_session=True)
    procs.append(proc)
    return proc, out


def _stamp(out, suffix, within=10.0):
    path = Path(str(out) + "." + suffix)
    deadline = time.monotonic() + within
    while time.monotonic() < deadline:
        if path.exists() and path.read_text().strip():
            return float(path.read_text().split()[-1])
        time.sleep(0.02)
    raise AssertionError(f"{path.name} 未出現")


@pytest.mark.wallclock
def test_two_heavy_commands_run_one_at_a_time(gate):
    a, out_a = _spawn(gate, "a", HEAVY_ARGV, life=1.0)
    _stamp(out_a, "start")
    b, out_b = _spawn(gate, "b", HEAVY_ARGV, life=0.1)
    a_end, b_start = _stamp(out_a, "end"), _stamp(out_b, "start")
    assert b_start >= a_end
    assert a.wait(timeout=20) == 0 and b.wait(timeout=20) == 0


@pytest.mark.wallclock
def test_light_command_does_not_queue_behind_heavy(gate):
    a, out_a = _spawn(gate, "a", HEAVY_ARGV, life=4.0)
    a_start = _stamp(out_a, "start")
    b, out_b = _spawn(gate, "b", LIGHT_ARGV, life=0.0)
    assert b.wait(timeout=20) == 0
    assert _stamp(out_b, "start") < a_start + 3.5
    assert not Path(str(out_a) + ".end").exists(), "light 應在 heavy 結束前完成"


@pytest.mark.wallclock
def test_mixed_directory_and_file_args_still_queue(gate):
    """繞過形態：目錄與具體檔並列不得判為 light。"""
    a, out_a = _spawn(gate, "a", HEAVY_ARGV, life=1.5)
    _stamp(out_a, "start")
    b, out_b = _spawn(gate, "b", ["pytest", "tests/", "tests/test_x.py"], life=0.1)
    time.sleep(0.6)
    assert not Path(str(out_b) + ".start").exists()
    assert b.wait(timeout=20) == 0


@pytest.mark.wallclock
def test_queue_wait_not_counted_against_timeout(gate):
    a, out_a = _spawn(gate, "a", HEAVY_ARGV, life=2.0)
    _stamp(out_a, "start")
    b, out_b = _spawn(gate, "b", HEAVY_ARGV, life=0.3, seconds="1")
    assert b.wait(timeout=20) == 0, b.stderr.read()
    assert Path(str(out_b) + ".end").exists()
    assert _stamp(out_b, "start") >= _stamp(out_a, "end")  # 確實排過隊，而非碰巧未逾時


@pytest.mark.wallclock
def test_waiter_prints_holder_info_periodically(gate):
    a, out_a = _spawn(gate, "a", HEAVY_ARGV, life=2.5)
    _stamp(out_a, "start")
    b, _ = _spawn(gate, "b", HEAVY_ARGV, life=0.0, CLAUDE_SLOT_NOTICE_INTERVAL="0.3")
    _, err = b.communicate(timeout=30)
    notices = [ln for ln in err.splitlines() if "等待名額" in ln]
    assert len(notices) >= 3
    for key in ("pid=", "cwd=", "命令=", "開始=", "目前負載="):
        assert key in notices[-1]
    assert f"pid={a.pid}" in notices[-1]


@pytest.mark.wallclock
def test_wait_limit_exits_with_dedicated_code_naming_holder(gate):
    mod = _load_module()
    a, out_a = _spawn(gate, "a", HEAVY_ARGV, life=5.0)
    _stamp(out_a, "start")
    # 等待上限只偵測持有者超出自身預估：把持有者的開始時間往前推，使其超出預估逾上限
    holder_file = gate[1] / "locks" / "heavy-slot-0.holder.json"
    info = json.loads(holder_file.read_text())
    info["started_epoch"] = time.time() - info["estimate"] - 100
    holder_file.write_text(json.dumps(info))
    b, _ = _spawn(gate, "b", HEAVY_ARGV, life=0.0, CLAUDE_SLOT_WAIT_LIMIT="0.5")
    _, err = b.communicate(timeout=30)
    assert b.returncode == mod.slot_gate.SLOT_WAIT_EXIT_CODE
    assert str(a.pid) in err and err.startswith("run-with-timeout:")
    assert str(mod.slot_gate.SLOT_WAIT_EXIT_CODE) in mod.__doc__


@pytest.mark.wallclock
def test_slot_released_when_holder_sigkilled(gate):
    a, out_a = _spawn(gate, "a", HEAVY_ARGV, life=30)
    _stamp(out_a, "start")
    b, out_b = _spawn(gate, "b", HEAVY_ARGV, life=0.1)
    time.sleep(0.8)
    assert not Path(str(out_b) + ".start").exists(), "持有者存活時不得取得名額"
    killed_at = time.time()
    os.kill(a.pid, signal.SIGKILL)  # 只殺包裝程序；替身子程序仍存活，鎖不得被其繼承
    assert b.wait(timeout=20) == 0
    assert _stamp(out_b, "start") >= killed_at


@pytest.mark.wallclock
def test_background_started_heavy_keeps_slot_until_it_ends(gate):
    a, out_a = _spawn(gate, "a", HEAVY_ARGV, life=3.0)  # 啟動後不等待，模擬 run_in_background
    a_start = _stamp(out_a, "start")
    b, out_b = _spawn(gate, "b", HEAVY_ARGV, life=0.0)
    time.sleep(1.5)
    assert b.poll() is None and not Path(str(out_b) + ".start").exists()
    assert _stamp(out_b, "start") >= _stamp(out_a, "end") >= a_start


@pytest.mark.wallclock
def test_launcher_led_unknown_runner_is_treated_as_heavy(gate):
    a, out_a = _spawn(gate, "a", HEAVY_ARGV, life=1.5)
    _stamp(out_a, "start")
    b, out_b = _spawn(gate, "b", ["env", "X=1", sys.executable, "-c",
                                  "import os, sys; open(sys.argv[1] + '.start', 'w').write('%d 1.0' % os.getpid())",
                                  "OUT"])
    time.sleep(0.6)
    assert not Path(str(out_b) + ".start").exists(), "launcher 開頭且判不出 runner 應排隊"
    assert b.wait(timeout=20) == 0


def test_bare_unknown_command_is_light():
    mod = _load_module()
    assert mod.slot_gate.is_heavy_command(["python3", "script.py"]) is False
    assert mod.slot_gate.is_heavy_command(["env", "X=1", "./run.sh"]) is True
    assert mod.slot_gate.is_heavy_command(["flutter", "test"]) is True
    assert mod.slot_gate.is_heavy_command(["flutter", "test", "test/a_test.dart"]) is False


def test_usage_notes_exit_125_may_overlap_command_codes():
    mod = _load_module()
    assert "125" in mod.USAGE and "stderr" in mod.USAGE


def test_heavy_command_runs_when_cwd_deleted(gate):
    """閘門讀不到 cwd 時 fail-open：命令照常執行，rc 為命令本身的 rc。"""
    env, tmp_path, _ = gate
    doomed = tmp_path / "doomed"
    doomed.mkdir()
    code = ("import os, subprocess, sys; os.chdir(sys.argv[1]); os.rmdir(sys.argv[1]); "
            "r = subprocess.run([sys.executable, sys.argv[2], '5', '--', 'pytest', 'tests/'], "
            "capture_output=True, text=True); print(r.returncode); print(r.stderr)")
    env = {**env, "PROBE_OUT": str(tmp_path / "d"), "PROBE_LIFE": "0"}
    res = subprocess.run([sys.executable, "-c", code, str(doomed), str(SCRIPT)], env=env,
                         capture_output=True, text=True, timeout=30)
    rc, _, err = res.stdout.partition("\n")
    assert rc == "0", res.stdout + res.stderr
    assert Path(str(tmp_path / "d") + ".end").exists()
    assert "Traceback" not in err


def test_classifier_exception_does_not_stop_command(gate, tmp_path, monkeypatch):
    """判定函式拋出非 ImportError 例外：命令仍執行並寫 stderr。"""
    mod = _load_module()
    sentinel = tmp_path / "ran"
    def boom(_command):
        raise RuntimeError("判定壞了")

    monkeypatch.setattr(mod.slot_gate, "is_heavy_command", boom)  # 該模組與其他測試共用，須還原
    env, _, _ = gate
    os.environ["CLAUDE_SLOT_LOCK_DIR"] = env["CLAUDE_SLOT_LOCK_DIR"]
    try:
        code = mod.run(5, [sys.executable, "-c", f"open({str(sentinel)!r}, 'w').write('x')"])
    finally:
        os.environ.pop("CLAUDE_SLOT_LOCK_DIR", None)
    assert code == 0 and sentinel.exists()


def _orphan_env(tmp_path, summary):
    marker = tmp_path / "orphan-queried"
    stub = _orphan_stub(tmp_path, "open(%r, 'a').write('x')\nprint(%r)\n" % (str(marker), summary))
    return marker, {"CLAUDE_ORPHAN_SCRIPT": str(stub)}


def test_heavy_start_prints_orphan_notice_before_command_runs(gate):
    _, tmp_path, _ = gate
    marker, extra = _orphan_env(tmp_path, "ORPHAN_SUMMARY matched=2 skipped=0 suspects=0 registered=0")
    b, out_b =_spawn(gate, "b", HEAVY_ARGV, life=0.0, **extra)
    _, err = b.communicate(timeout=30)
    assert b.returncode == 0 and Path(str(out_b) + ".end").exists()
    assert "orphan-test-procs.py --kill" in err and marker.exists()


def test_heavy_start_without_orphans_prints_no_notice(gate):
    _, tmp_path, _ = gate
    marker, extra = _orphan_env(tmp_path, "ORPHAN_SUMMARY matched=0 skipped=0 suspects=0 registered=0")
    b, _ = _spawn(gate, "b", HEAVY_ARGV, life=0.0, **extra)
    _, err = b.communicate(timeout=30)
    assert b.returncode == 0 and marker.exists() and "orphan-test-procs" not in err


def test_light_command_does_not_query_orphans(gate):
    _, tmp_path, _ = gate
    marker, extra = _orphan_env(tmp_path, "ORPHAN_SUMMARY matched=2 skipped=0 suspects=0 registered=0")
    b, _ = _spawn(gate, "b", LIGHT_ARGV, life=0.0, **extra)
    _, err = b.communicate(timeout=30)
    assert b.returncode == 0 and not marker.exists() and "orphan-test-procs" not in err


def test_orphan_query_failure_does_not_block_heavy_command(gate):
    _, tmp_path, _ = gate
    b, out_b = _spawn(gate, "b", HEAVY_ARGV, life=0.0, CLAUDE_ORPHAN_SCRIPT=str(tmp_path / "missing.py"))
    _, err = b.communicate(timeout=30)
    assert b.returncode == 0 and Path(str(out_b) + ".end").exists()
    assert "Traceback" not in err


def test_hold_marker_and_wait_limit_do_not_reach_wrapped_command(tmp_path, monkeypatch):
    """持有標記只給直接子層的 run-with-timeout：被包裝命令的環境不含標記，等待上限還原為持有前的值。"""
    sys.path.insert(0, str(SCRIPT.parent.parent))
    from lib import slot_gate

    lock_dir = tmp_path / "slots"
    lock_dir.mkdir(mode=0o700)
    monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(lock_dir))
    probe = ("import os; print(os.environ.get('CLAUDE_SLOT_HELD_BY'), os.environ.get('CLAUDE_SLOT_WAIT_LIMIT'),"
             " os.environ.get('CLAUDE_SLOT_WAIT_LIMIT_BEFORE_HOLD'))")

    def run_under_hold(before):
        if before is None:
            monkeypatch.delenv("CLAUDE_SLOT_WAIT_LIMIT", raising=False)
        else:
            monkeypatch.setenv("CLAUDE_SLOT_WAIT_LIMIT", before)
        hold, _ = slot_gate.acquire_slot(["x"], lambda: None)
        try:
            with slot_gate.export_hold(hold):
                res = subprocess.run([sys.executable, str(SCRIPT), "30", "--", sys.executable, "-c", probe],
                                     capture_output=True, text=True, timeout=60)
        finally:
            hold.release()
        assert res.returncode == 0, res.stderr
        return res.stdout.split()

    assert run_under_hold("7") == ["None", "7", "None"]
    assert run_under_hold(None) == ["None", "None", "None"]


# ---- 登記目錄的擁有者／權限／symlink 驗證與 O_NOFOLLOW 寫入 ----
# 全部以 tmp 目錄模擬，不碰真實登記位置。驗證失敗：命令照常執行、不登記、stderr 單行。

def _make_unsafe(kind, tmp_path, monkeypatch):
    """回傳 (供 CLAUDE_PROC_REGISTRY_DIR 使用的路徑, 不該出現登記檔的真實目錄)。"""
    real = tmp_path / "real"
    real.mkdir(mode=0o700)
    if kind == "symlink":
        link = tmp_path / "link"
        link.symlink_to(real)
        return link, real
    if kind == "group_writable":
        real.chmod(0o770)
    elif kind == "other_writable":
        real.chmod(0o707)
    elif kind == "other_owned":
        # 無法在測試中真的換擁有者；讓驗證端看到的目前使用者與目錄擁有者不同
        monkeypatch.setattr(_load_module_cache(), "_owner_uid", lambda: os.getuid() + 1, raising=False)
    return real, real


def _load_module_cache():
    return _MOD_HOLDER.setdefault("mod", _load_module())


_MOD_HOLDER = {}


@pytest.mark.parametrize("kind", ["other_owned", "group_writable", "other_writable", "symlink"])
def test_unsafe_registry_dir_is_not_used_and_warns(kind, tmp_path, monkeypatch, capsys):
    _MOD_HOLDER.clear()
    mod = _load_module_cache()
    target, real = _make_unsafe(kind, tmp_path, monkeypatch)
    monkeypatch.setenv("CLAUDE_PROC_REGISTRY_DIR", str(target))
    assert mod.register_group(os.getpid(), ["x"]) is None
    assert list(real.iterdir()) == []
    err = capsys.readouterr().err
    assert err.startswith("run-with-timeout:") and len(err.strip().splitlines()) == 1


@pytest.mark.parametrize("kind", ["group_writable", "symlink"])
def test_unsafe_registry_dir_does_not_block_command(kind, tmp_path, monkeypatch):
    target, real = _make_unsafe(kind, tmp_path, monkeypatch)
    res = subprocess.run([sys.executable, str(SCRIPT), "10", "--", sys.executable, "-c",
                          "print('ran');import sys;sys.exit(7)"],
                         capture_output=True, text=True, timeout=20, env=_env(target))
    assert (res.returncode, res.stdout.strip()) == (7, "ran")
    assert res.stderr.startswith("run-with-timeout:") and "Traceback" not in res.stderr
    assert list(real.iterdir()) == []


def test_registry_file_is_created_with_o_nofollow(tmp_path, monkeypatch):
    """登記暫存檔須以 O_CREAT|O_EXCL|O_NOFOLLOW 建立，不跟隨預先放置的 symlink。"""
    mod = _load_module()
    reg = tmp_path / "reg"
    monkeypatch.setenv("CLAUDE_PROC_REGISTRY_DIR", str(reg))
    flags_seen = []
    real_open = os.open

    def spy(path, flags, *a, **k):
        if str(path).startswith(str(reg)):
            flags_seen.append(flags)
        return real_open(path, flags, *a, **k)

    monkeypatch.setattr(os, "open", spy)
    path = mod.register_group(os.getpid(), ["x"])
    assert path is not None and flags_seen
    assert all(f & os.O_NOFOLLOW and f & os.O_EXCL for f in flags_seen)
    mod.unregister_group(path)


def test_safe_registry_dir_is_created_private(tmp_path, monkeypatch):
    mod = _load_module()
    reg = tmp_path / "reg"
    monkeypatch.setenv("CLAUDE_PROC_REGISTRY_DIR", str(reg))
    path = mod.register_group(os.getpid(), ["x"])
    assert path is not None and (reg.stat().st_mode & 0o077) == 0
    mod.unregister_group(path)


def _load_orphan_module():
    spec = importlib.util.spec_from_file_location("otp_loc", SCRIPT.parent / "orphan-test-procs.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_default_registry_dir_is_under_home_and_both_ends_agree(tmp_path, monkeypatch):
    """寫入端與讀取端的預設位置一致，且在 HOME 底下（與名額鎖同處），不在共用暫存目錄。"""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("CLAUDE_PROC_REGISTRY_DIR", raising=False)
    writer, reader = _load_module().registry_dir(), _load_orphan_module().registry_dir()
    assert writer == reader
    assert Path(writer).parent == tmp_path / ".cache"


def test_override_registry_dir_agrees_on_both_ends(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROC_REGISTRY_DIR", str(tmp_path / "x"))
    assert _load_module().registry_dir() == _load_orphan_module().registry_dir() == str(tmp_path / "x")
