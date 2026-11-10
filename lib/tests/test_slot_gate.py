#!/usr/bin/env python3
"""
slot_gate 模組單元測試（本機名額閘門）

驗證項目：
1. 鎖目錄不依賴 TMPDIR（不同 TMPDIR 的程序共用同一名額）
2. 閘門內部例外不以 traceback 結束（holder 寫入失敗、heavy 判定失敗）
3. 等待訊息標示過期的持有者資訊
"""

import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib import slot_gate


def test_default_slot_dir_ignores_tmpdir(tmp_path):
    """名額是全機一份：不同 session 的 TMPDIR 不同時仍指向同一目錄。"""
    code = "import sys; sys.path.insert(0, %r); from lib import slot_gate; print(slot_gate.slot_dir())" % str(
        Path(__file__).parent.parent.parent)
    outs = []
    for name in ("a", "b"):
        tmp = tmp_path / name
        tmp.mkdir()
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_SLOT_LOCK_DIR"}
        env["TMPDIR"] = str(tmp)
        outs.append(subprocess.run([sys.executable, "-c", code], env=env, capture_output=True,
                                   text=True, timeout=20).stdout.strip())
    assert outs[0] == outs[1] == os.path.join(os.path.expanduser("~"), ".cache", "claude-slot")


def test_env_override_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(tmp_path))
    assert slot_gate.slot_dir() == str(tmp_path)


def test_acquire_and_release_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(tmp_path))
    hold, early = slot_gate.acquire_slot(["flutter", "test"], lambda: None)
    assert early is None and hold is not None
    info = json.loads(Path(hold.holder_path).read_text())
    assert info["pid"] == os.getpid()
    hold.release()
    assert not Path(hold.holder_path).exists()


def test_holder_write_failure_does_not_raise(monkeypatch, tmp_path, capsys):
    """entry 組裝（getloadavg）失敗也只寫一行 stderr，仍取得名額。"""
    monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(tmp_path))

    def boom():
        raise OSError("no loadavg")

    monkeypatch.setattr(slot_gate.os, "getloadavg", boom)
    hold, early = slot_gate.acquire_slot(["flutter", "test"], lambda: None)
    assert early is None and hold is not None
    hold.release()
    assert capsys.readouterr().err.startswith("run-with-timeout:")


def test_is_heavy_command_swallows_classifier_exception_as_heavy(monkeypatch, capsys):
    import lib.test_command_parse as parse

    def boom(_tokens):
        raise RuntimeError("classifier bug")

    monkeypatch.setattr(parse, "classify_argv_weight", boom)
    assert slot_gate.is_heavy_command(["echo", "hi"]) is True
    err = capsys.readouterr().err
    assert err.startswith("run-with-timeout:") and "Traceback" not in err


def test_stale_holder_info_is_marked(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(tmp_path))
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    (tmp_path / "heavy-slot-0.holder.json").write_text(json.dumps({
        "pid": dead.pid, "cwd": "/x", "command": ["flutter", "test"],
        "started": "2026-10-14 00:00:00", "load": "0.1/0.1/0.1"}))
    assert "過期" in slot_gate.describe_holder(str(tmp_path))


def test_live_holder_info_not_marked_stale(monkeypatch, tmp_path):
    (tmp_path / "heavy-slot-0.holder.json").write_text(json.dumps({
        "pid": os.getpid(), "cwd": "/x", "command": ["flutter", "test"],
        "started": "2026-10-14 00:00:00", "load": "0.1/0.1/0.1"}))
    assert "過期" not in slot_gate.describe_holder(str(tmp_path))


def _expect_unused(directory, capsys):
    hold, early = slot_gate.acquire_slot(["flutter", "test"], lambda: None)
    assert hold is None and early is None
    assert capsys.readouterr().err.startswith("run-with-timeout:")
    assert not list(Path(directory).glob("heavy-slot-*")) if Path(directory).is_dir() else True


def test_dir_owned_by_someone_else_is_not_used(monkeypatch, tmp_path, capsys):
    target = tmp_path / "locks"
    target.mkdir(mode=0o700)
    monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(target))
    monkeypatch.setattr(slot_gate, "_owner_uid", lambda: os.getuid() + 1)
    _expect_unused(target, capsys)


def test_group_other_writable_dir_is_not_used(monkeypatch, tmp_path, capsys):
    target = tmp_path / "locks"
    target.mkdir()
    target.chmod(0o777)
    monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(target))
    _expect_unused(target, capsys)


def test_symlinked_dir_is_not_used(monkeypatch, tmp_path, capsys):
    real = tmp_path / "attacker"
    real.mkdir(mode=0o700)
    link = tmp_path / "locks"
    link.symlink_to(real)
    monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(link))
    _expect_unused(real, capsys)


def test_new_dir_is_created_private(monkeypatch, tmp_path):
    target = tmp_path / "fresh" / "locks"
    monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(target))
    hold, _ = slot_gate.acquire_slot(["flutter", "test"], lambda: None)
    try:
        assert hold is not None and (target.stat().st_mode & 0o077) == 0
    finally:
        hold.release()


def test_symlinked_lock_file_is_not_followed(monkeypatch, tmp_path, capsys):
    target = tmp_path / "locks"
    target.mkdir(mode=0o700)
    victim = tmp_path / "victim"
    victim.write_text("keep")
    (target / "heavy-slot-0.lock").symlink_to(victim)
    monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(target))
    hold, early = slot_gate.acquire_slot(["flutter", "test"], lambda: None)
    assert hold is None and early is None and victim.read_text() == "keep"
    assert capsys.readouterr().err.startswith("run-with-timeout:")


def test_waiter_shows_current_load_not_recorded_load(monkeypatch, tmp_path):
    (tmp_path / "heavy-slot-0.holder.json").write_text(json.dumps({
        "pid": os.getpid(), "cwd": "/x", "command": ["flutter", "test"],
        "started": "2026-10-14 00:00:00", "load": "0.11/0.11/0.11"}))
    monkeypatch.setattr(slot_gate.os, "getloadavg", lambda: (9.99, 8.88, 7.77))
    text = slot_gate.describe_holder(str(tmp_path))
    assert "9.99" in text and "0.11" not in text
    # 負載標為當下值，並以分隔符與持有者描述區隔
    assert " ｜ 目前負載=9.99/8.88/7.77" in text
    assert text.index("開始=") < text.index(" ｜ ") < text.index("目前負載=")
    assert " load=" not in text


def test_stale_pid_tmp_removed_live_kept(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(tmp_path))
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    stale = tmp_path / ("heavy-slot-0.holder.json.%d.tmp" % dead.pid)
    live = tmp_path / ("heavy-slot-0.holder.json.%d.tmp" % os.getppid())
    stale.write_text("{}")
    live.write_text("{}")
    hold, _ = slot_gate.acquire_slot(["flutter", "test"], lambda: None)
    try:
        assert not stale.exists() and live.exists()
    finally:
        hold.release()


# ---- 孤兒程序提示（以替身腳本取代 orphan-test-procs.py，不查詢也不終止任何真實程序）----

def _fake_orphan_script(tmp_path, body):
    script = tmp_path / "fake-orphan.py"
    script.write_text(body)
    return str(script)


def _summary_script(tmp_path, matched=0, suspects=0, registered=0, extra="",
                    human="符合 %d 略過 0 疑似殘留 %d"):
    """替身輸出：人讀行（可任意改字）加機器可讀契約行；count_orphans 只該解析後者。"""
    return _fake_orphan_script(
        tmp_path, "print(%r)\nprint(%r)\nprint('ORPHAN_SUMMARY matched=%d skipped=0 suspects=%d registered=%d')\n" % (
            extra, human % (matched, suspects) if "%d" in human else human, matched, suspects, registered))


def test_orphans_present_prints_count_and_cleanup_command(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("CLAUDE_ORPHAN_SCRIPT", _summary_script(tmp_path, matched=2, suspects=1))
    slot_gate.report_orphans()
    err = capsys.readouterr().err
    assert err.startswith("run-with-timeout:")
    assert "可清理 2 個" in err and "疑似殘留 1 棵" in err
    assert "python3 .claude/scripts/orphan-test-procs.py --kill" in err


def test_only_suspects_message_has_no_kill_command(monkeypatch, tmp_path, capsys):
    """--kill 不處理疑似殘留；只有疑似殘留時提示不得引導使用 --kill。"""
    monkeypatch.setenv("CLAUDE_ORPHAN_SCRIPT", _summary_script(tmp_path, suspects=2))
    slot_gate.report_orphans()
    err = capsys.readouterr().err
    assert "疑似殘留 2 棵" in err and "人工核對" in err
    assert "--kill" not in err and "可清理" not in err


def test_only_cleanable_message_has_no_suspect_part(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("CLAUDE_ORPHAN_SCRIPT", _summary_script(tmp_path, matched=3))
    slot_gate.report_orphans()
    err = capsys.readouterr().err
    assert "可清理 3 個" in err and "--kill" in err and "疑似殘留" not in err


def test_no_orphans_prints_nothing(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("CLAUDE_ORPHAN_SCRIPT", _summary_script(tmp_path))
    slot_gate.report_orphans()
    assert capsys.readouterr().err == ""


def test_registered_groups_in_summary_count_as_orphans(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("CLAUDE_ORPHAN_SCRIPT", _summary_script(tmp_path, registered=1))
    slot_gate.report_orphans()
    assert "可清理 1 個" in capsys.readouterr().err


def test_human_summary_wording_change_does_not_change_count(monkeypatch, tmp_path, capsys):
    """人讀行改字（前綴、語言）不得造成少算：計數只認機器可讀契約行。"""
    script = _summary_script(tmp_path, matched=2, suspects=1, human="Summary: changed wording")
    monkeypatch.setenv("CLAUDE_ORPHAN_SCRIPT", script)
    slot_gate.report_orphans()
    err = capsys.readouterr().err
    assert "可清理 2 個" in err and "疑似殘留 1 棵" in err


def test_human_lines_alone_are_not_a_contract(monkeypatch, tmp_path, capsys):
    """只有人讀行、無契約行：視為查詢失敗（單行警告），不從人讀行猜數量。"""
    script = _fake_orphan_script(tmp_path, "print('符合 5 略過 0 疑似殘留 0')\nprint('登記可終止 群組 1')\n")
    monkeypatch.setenv("CLAUDE_ORPHAN_SCRIPT", script)
    slot_gate.report_orphans()
    err = capsys.readouterr().err
    assert len(err.strip().splitlines()) == 1 and "可清理" not in err


@pytest.mark.parametrize("body", [
    "import sys; sys.exit(2)",
    "print('無法解析的輸出')",
    "raise SystemExit('boom')",
])
def test_orphan_query_failure_warns_one_line_and_does_not_raise(monkeypatch, tmp_path, capsys, body):
    monkeypatch.setenv("CLAUDE_ORPHAN_SCRIPT", _fake_orphan_script(tmp_path, body))
    slot_gate.report_orphans()
    err = capsys.readouterr().err
    assert err.startswith("run-with-timeout:") and len(err.strip().splitlines()) == 1
    assert "Traceback" not in err


def test_orphan_script_missing_warns_one_line(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("CLAUDE_ORPHAN_SCRIPT", str(tmp_path / "nope.py"))
    slot_gate.report_orphans()
    assert len(capsys.readouterr().err.strip().splitlines()) == 1


# ---- 到達順序排隊（0.5.0-W1-303.1）----

SLEEPER_LIFETIME = 60  # 偽造「前方排隊者」的存活秒數（測試結束即 kill）
HOLD_SECONDS = 0.4  # 子程序取得名額後持有的秒數
ENTER_POLL = 0.02
STEP_TIMEOUT = 30
SHORT_LIMIT = "0.3"


def _sleeper():
    """存活的外部 pid，供偽造「前方排隊者」。"""
    return subprocess.Popen([sys.executable, "-c", f"import time; time.sleep({SLEEPER_LIFETIME})"])


def _fake_entry(directory, seq, pid, estimate=0):
    """estimate 預設 0：既有測試只關心順序，不讓預估值觸發提早拒絕。"""
    path = Path(directory) / f"queue-{seq:012d}-{pid}.json"
    path.write_text(json.dumps({"pid": pid, "command": ["x"], "arrived": "t", "estimate": estimate}))
    return path


def _queue_files(directory):
    return sorted(p.name for p in Path(directory).glob("queue-*.json"))


def _interrupt_after(seconds):
    """等待 seconds 秒後回傳 SIGTERM 的 interrupted 回呼：佇列不設總等待上限，測試以訊號收尾。"""
    t0 = time.monotonic()
    return lambda: signal.SIGTERM if time.monotonic() - t0 >= seconds else None


def test_late_comer_cannot_take_free_slot_while_live_waiter_is_ahead(monkeypatch, tmp_path):
    """E2：名額空著，但前方有存活排隊者時，後到者取不到。"""
    monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(tmp_path))
    ahead = _sleeper()
    try:
        entry = _fake_entry(tmp_path, 1, ahead.pid)
        hold, early = slot_gate.acquire_slot(["flutter", "test"], _interrupt_after(0.3))
        assert hold is None and early == 128 + signal.SIGTERM
        assert entry.exists(), "不得清除存活者的排隊檔"
    finally:
        ahead.kill()
        ahead.wait()


def test_three_waiters_acquire_in_arrival_order(monkeypatch, tmp_path):
    """三個排隊者依到達順序取得（取得時間戳遞增），後到者不插隊。"""
    code = (
        "import sys,time; sys.path.insert(0, %r)\n"
        "from lib import slot_gate\n"
        "hold,_ = slot_gate.acquire_slot(['x'], lambda: None)\n"
        "print(time.time(), flush=True)\n"
        "time.sleep(%r)\n"
        "hold.release()\n"
    ) % (str(Path(__file__).parent.parent.parent), HOLD_SECONDS)
    env = dict(os.environ, CLAUDE_SLOT_LOCK_DIR=str(tmp_path), CLAUDE_SLOT_WAIT_LIMIT=str(STEP_TIMEOUT))
    monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(tmp_path))
    holder, _ = slot_gate.acquire_slot(["holder"], lambda: None)  # 先占住名額
    procs = []
    for i in range(3):
        procs.append(subprocess.Popen([sys.executable, "-c", code], env=env, stdout=subprocess.PIPE,
                                      stderr=subprocess.DEVNULL, text=True))
        deadline = time.monotonic() + STEP_TIMEOUT
        while len(_queue_files(tmp_path)) < i + 1 and time.monotonic() < deadline:
            time.sleep(ENTER_POLL)  # 確保第 i 個已進隊再啟動下一個
    holder.release()
    stamps = [float(p.communicate(timeout=STEP_TIMEOUT)[0]) for p in procs]
    assert stamps == sorted(stamps) and len(set(stamps)) == 3
    assert _queue_files(tmp_path) == []


def test_dead_waiter_entry_is_removed_and_does_not_block(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(tmp_path))
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    entry = _fake_entry(tmp_path, 1, dead.pid)
    hold, early = slot_gate.acquire_slot(["x"], lambda: None)
    assert hold is not None and early is None
    assert not entry.exists()
    hold.release()


def test_entry_removed_on_acquire_giveup_timeout_and_signal(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(tmp_path))
    hold, _ = slot_gate.acquire_slot(["x"], lambda: None, estimate_seconds=0)  # 取得；預估 0 使後方真的等待而非提早拒絕
    assert _queue_files(tmp_path) == []
    monkeypatch.setenv("CLAUDE_SLOT_WAIT_LIMIT", SHORT_LIMIT)  # 持有者（預估 0）超出預估過久
    got, early = slot_gate.acquire_slot(["x"], lambda: None, estimate_seconds=0)
    assert got is None and early == slot_gate.SLOT_WAIT_EXIT_CODE
    assert _queue_files(tmp_path) == []
    monkeypatch.setenv("CLAUDE_SLOT_WAIT_LIMIT", str(STEP_TIMEOUT))
    got, early = slot_gate.acquire_slot(["x"], lambda: signal.SIGTERM)  # 訊號中斷
    assert got is None and early == 128 + signal.SIGTERM
    assert _queue_files(tmp_path) == []

    def boom():
        raise RuntimeError("abort")
    with pytest.raises(RuntimeError):  # 放棄：等待中途例外
        slot_gate.acquire_slot(["x"], boom)
    assert _queue_files(tmp_path) == []
    hold.release()


def test_waiting_notice_shows_position_and_ahead_count(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(tmp_path))
    monkeypatch.setenv("CLAUDE_SLOT_WAIT_LIMIT", SHORT_LIMIT)
    monkeypatch.setenv("CLAUDE_SLOT_NOTICE_INTERVAL", "0")
    a, b = _sleeper(), _sleeper()
    try:
        _fake_entry(tmp_path, 1, a.pid)
        _fake_entry(tmp_path, 2, b.pid)
        slot_gate.acquire_slot(["x"], _interrupt_after(0.3))
        err = capsys.readouterr().err
        assert "順位 3" in err and "前方 2 筆" in err
    finally:
        for p in (a, b):
            p.kill()
            p.wait()


def test_held_marker_and_light_command_bypass_unchanged(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(tmp_path))
    hold, _ = slot_gate.acquire_slot(["x"], lambda: None)
    with slot_gate.export_hold(hold):
        assert slot_gate.held_by_ancestor()
        assert slot_gate.is_heavy_command(["flutter", "test"]) is False
        assert slot_gate.HELD_ENV not in slot_gate.child_env(os.environ)
    assert not slot_gate.held_by_ancestor()
    assert slot_gate.is_heavy_command(["pytest", "tests/test_x.py"]) is False
    hold.release()


def test_orphan_query_timeout_is_bounded(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("CLAUDE_ORPHAN_SCRIPT", _fake_orphan_script(tmp_path, "import time; time.sleep(30)"))
    monkeypatch.setenv("CLAUDE_ORPHAN_QUERY_TIMEOUT", "0.5")
    started = time.monotonic()
    slot_gate.report_orphans()
    assert time.monotonic() - started < 5
    assert "逾時" in capsys.readouterr().err


# ---- 前方預估耗時提早拒絕（0.5.0-W1-303.2）----

AHEAD_ESTIMATE_SECONDS = 5  # 遠小於等待上限的前方預估
REJECT_BUDGET_SECONDS = 2.0 # 立即拒絕的耗時上限（遠小於 WAIT_LIMIT，舊碼會等滿上限）


def _backdate_holder(holder, seconds):
    info = json.loads(Path(holder.holder_path).read_text())
    info["started_epoch"] = time.time() - seconds
    Path(holder.holder_path).write_text(json.dumps(info))


def test_saturated_queue_does_not_starve_earlier_arrival(monkeypatch, tmp_path, capsys):
    """前方預估加總 300 秒 > 上限 150 秒，且佇列持續補進新到者：先到者仍在有限輪內取得，不被提早拒絕。"""
    monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(tmp_path))
    monkeypatch.setenv("CLAUDE_SLOT_WAIT_LIMIT", "150")
    ahead = [_sleeper() for _ in range(3)]
    spare = []
    for i, p in enumerate(ahead, start=1):
        _fake_entry(tmp_path, i, p.pid, estimate=100)
    result = {}
    worker = threading.Thread(target=lambda: result.update(
        zip(("hold", "early"), slot_gate.acquire_slot(["x"], lambda: None, estimate_seconds=0))), daemon=True)
    worker.start()
    try:
        deadline = time.monotonic() + STEP_TIMEOUT
        while len(_queue_files(tmp_path)) < 4 and worker.is_alive() and time.monotonic() < deadline:
            time.sleep(ENTER_POLL)
        seq = 5
        rounds = 0
        while worker.is_alive() and rounds < 10 and time.monotonic() < deadline:
            rounds += 1  # 每輪前方最舊的一位離場，同時補進一位新到者，佇列長度維持在超限
            if ahead:
                victim = ahead.pop(0)
                victim.kill()
                victim.wait()
            fresh = _sleeper()
            spare.append(fresh)
            _fake_entry(tmp_path, seq, fresh.pid, estimate=100)
            seq += 1
            time.sleep(0.3)
        worker.join(timeout=STEP_TIMEOUT)
        assert result.get("hold") is not None and result.get("early") is None, capsys.readouterr().err
        assert rounds <= 4, "先到者應在前方三位離場後即取得"
        result["hold"].release()
    finally:
        for p in ahead + spare:
            p.kill()
            p.wait()


def test_entry_prints_position_and_estimate_without_total_wait_cap(monkeypatch, tmp_path, capsys):
    """進場即輸出順位與預估，並說明可自行中止；佇列總等待不設上限。"""
    monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(tmp_path))
    monkeypatch.setenv("CLAUDE_SLOT_WAIT_LIMIT", "5")
    monkeypatch.setenv("CLAUDE_SLOT_NOTICE_INTERVAL", "999")
    a, b = _sleeper(), _sleeper()
    try:
        _fake_entry(tmp_path, 1, a.pid, estimate=100)
        _fake_entry(tmp_path, 2, b.pid, estimate=100)
        hold, early = slot_gate.acquire_slot(["x"], _interrupt_after(0.5))
        err = capsys.readouterr().err
        assert hold is None and early == 128 + signal.SIGTERM
        assert "順位 3" in err and "前方 2 筆" in err and "預估" in err and "200" in err
    finally:
        for p in (a, b):
            p.kill()
            p.wait()


def test_estimate_within_limit_queues_and_acquires(monkeypatch, tmp_path):
    """對照：前方排隊者結束後取得。"""
    monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(tmp_path))
    monkeypatch.setenv("CLAUDE_SLOT_WAIT_LIMIT", str(STEP_TIMEOUT))
    ahead = subprocess.Popen([sys.executable, "-c", f"import time; time.sleep({HOLD_SECONDS})"])
    threading.Thread(target=ahead.wait, daemon=True).start()  # 及時回收，避免殭屍程序被 kill(0) 視為存活
    _fake_entry(tmp_path, 1, ahead.pid, estimate=AHEAD_ESTIMATE_SECONDS)
    hold, early = slot_gate.acquire_slot(["x"], lambda: None)
    assert hold is not None and early is None
    hold.release()


def test_holder_overrunning_its_estimate_is_detected(monkeypatch, tmp_path, capsys):
    """E1：持有者預估 100 秒，超出預估的時間 > 上限 50 秒才回報卡住；未超出上限則照常等待。"""
    monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(tmp_path))
    monkeypatch.setenv("CLAUDE_SLOT_WAIT_LIMIT", "50")
    holder, _ = slot_gate.acquire_slot(["h"], lambda: None, estimate_seconds=100)
    try:
        info = json.loads(Path(holder.holder_path).read_text())
        assert info["estimate"] == 100
        _backdate_holder(holder, 140)  # 超出預估 40 秒 < 上限：不算卡住，照常等待
        got, early = slot_gate.acquire_slot(["x"], _interrupt_after(0.3))
        assert got is None and early == 128 + signal.SIGTERM
        _backdate_holder(holder, 200)  # 超出預估 100 秒 > 上限
        started = time.monotonic()
        got, early = slot_gate.acquire_slot(["x"], lambda: None)
        assert got is None and early == slot_gate.SLOT_WAIT_EXIT_CODE
        assert time.monotonic() - started < REJECT_BUDGET_SECONDS
        err = capsys.readouterr().err
        assert "超出" in err and "預估" in err
    finally:
        holder.release()


def test_inherited_hold_marker_keeps_total_wait_cap(monkeypatch, tmp_path):
    """持有期間子程序（環境帶持有標記）的等待上限仍是總等待上限：持有者未超出預估也在上限到時放棄。"""
    monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(tmp_path))
    holder, _ = slot_gate.acquire_slot(["h"], lambda: None, estimate_seconds=100)
    try:
        with slot_gate.export_hold(holder):
            monkeypatch.setenv("CLAUDE_SLOT_WAIT_LIMIT", SHORT_LIMIT)
            started = time.monotonic()
            got, early = slot_gate.acquire_slot(["x"], lambda: None)
        assert got is None and early == slot_gate.SLOT_WAIT_EXIT_CODE
        assert time.monotonic() - started < REJECT_BUDGET_SECONDS
    finally:
        holder.release()


def test_waiting_notice_shows_remaining_estimate(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(tmp_path))
    monkeypatch.setenv("CLAUDE_SLOT_WAIT_LIMIT", SHORT_LIMIT)
    monkeypatch.setenv("CLAUDE_SLOT_NOTICE_INTERVAL", "0")
    a = _sleeper()
    try:
        _fake_entry(tmp_path, 1, a.pid, estimate=0)
        monkeypatch.setattr(slot_gate, "DEFAULT_ESTIMATE_SECONDS", 0.0, raising=False)
        slot_gate.acquire_slot(["x"], _interrupt_after(0.3), estimate_seconds=0)
        assert "預估剩餘" in capsys.readouterr().err
    finally:
        a.kill()
        a.wait()


def test_default_estimates_are_positive_and_heavier_for_flutter():
    assert slot_gate.default_estimate_seconds(["fvm", "flutter", "test"]) > 0
    assert slot_gate.default_estimate_seconds(["something", "else"]) == slot_gate.DEFAULT_ESTIMATE_SECONDS
    assert slot_gate.default_estimate_seconds(["merge-gate", "b"]) >= slot_gate.default_estimate_seconds(["pytest"])


def test_entry_without_estimate_uses_command_default(monkeypatch, tmp_path):
    """舊格式排隊檔（無 estimate）以預設值計，仍可解析。"""
    monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(tmp_path))
    a = _sleeper()
    try:
        path = Path(tmp_path) / f"queue-{1:012d}-{a.pid}.json"
        path.write_text(json.dumps({"pid": a.pid, "command": ["x"], "arrived": "t"}))
        ahead, seconds = slot_gate.estimate_wait(str(tmp_path), f"queue-{2:012d}-{os.getpid()}.json")
        assert ahead == 1 and seconds == slot_gate.default_estimate_seconds(["x"])
    finally:
        a.kill()
        a.wait()


def test_notice_names_first_ahead_and_marks_position_excludes_holder(monkeypatch, tmp_path, capsys):
    """有前方者：提示指名前方第一筆命令，並標明順位不含持有者。"""
    monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(tmp_path))
    monkeypatch.setenv("CLAUDE_SLOT_NOTICE_INTERVAL", "0")
    a = _sleeper()
    try:
        path = Path(tmp_path) / f"queue-{1:012d}-{a.pid}.json"
        path.write_text(json.dumps({"pid": a.pid, "command": ["merge-gate", "feat-x"], "estimate": 1}))
        slot_gate.acquire_slot(["x"], _interrupt_after(0.3))
        err = capsys.readouterr().err
        assert "前方第一筆：merge-gate feat-x" in err and "持有者之後第 2 位" in err and "不含持有者" in err
    finally:
        a.kill()
        a.wait()


def test_notice_without_ahead_says_no_queue(monkeypatch, tmp_path, capsys):
    """無前方者：提示明說前方無排隊者，不出現前方第一筆。"""
    monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(tmp_path))
    monkeypatch.setenv("CLAUDE_SLOT_NOTICE_INTERVAL", "0")
    holder, _ = slot_gate.acquire_slot(["h"], lambda: None, estimate_seconds=100)
    try:
        slot_gate.acquire_slot(["x"], _interrupt_after(0.3))
        err = capsys.readouterr().err
        assert "前方無排隊者" in err and "前方第一筆" not in err and "持有者之後第 1 位" in err
    finally:
        holder.release()


# --- 排頭排隊者停住（SIGSTOP）偵測 ---

STALL_SECONDS = "1"


def _spawn_real_head(tmp_path):
    """真實排頭：subprocess 內呼叫 acquire_slot，名額被占時持續輪詢並更新心跳。"""
    code = (
        "import sys; sys.path.insert(0, %r)\n"
        "from lib import slot_gate\n"
        "slot_gate.acquire_slot(['head'], lambda: None)\n"
    ) % str(Path(__file__).parent.parent.parent)
    env = dict(os.environ, CLAUDE_SLOT_LOCK_DIR=str(tmp_path), CLAUDE_SLOT_STALL_SECONDS=STALL_SECONDS)
    proc = subprocess.Popen([sys.executable, "-c", code], env=env, stderr=subprocess.DEVNULL)
    deadline = time.monotonic() + STEP_TIMEOUT
    while not _queue_files(tmp_path) and time.monotonic() < deadline:
        time.sleep(ENTER_POLL)
    assert _queue_files(tmp_path), "排頭未進隊"
    return proc


def _stop_proc(proc):
    try:
        proc.send_signal(signal.SIGCONT)
    except OSError:
        pass  # 已結束
    proc.kill()
    proc.wait()


def test_stalled_head_is_skipped_and_follower_acquires(monkeypatch, tmp_path, capsys):
    """排頭收到 SIGSTOP、名額空閒：後方在有限時間內取得，並輸出一行可見訊號。"""
    monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(tmp_path))
    monkeypatch.setenv("CLAUDE_SLOT_STALL_SECONDS", STALL_SECONDS)
    blocker, _ = slot_gate.acquire_slot(["blocker"], lambda: None)
    head = _spawn_real_head(tmp_path)
    try:
        time.sleep(0.5)  # 讓排頭至少跳過一次心跳
        head.send_signal(signal.SIGSTOP)
        blocker.release()
        t0 = time.monotonic()
        hold, early = slot_gate.acquire_slot(["follower"], _interrupt_after(10))
        assert hold is not None and early is None, "排頭停住時後方未在有限時間內取得"
        assert time.monotonic() - t0 < 8
        assert "停住" in capsys.readouterr().err
        hold.release()
    finally:
        _stop_proc(head)


def test_polling_head_is_not_skipped(monkeypatch, tmp_path):
    """E1 對照：排頭正常輪詢（心跳持續更新）時，超過停住門檻後仍不被略過。"""
    monkeypatch.setenv("CLAUDE_SLOT_LOCK_DIR", str(tmp_path))
    monkeypatch.setenv("CLAUDE_SLOT_STALL_SECONDS", STALL_SECONDS)
    blocker, _ = slot_gate.acquire_slot(["blocker"], lambda: None)
    head = _spawn_real_head(tmp_path)
    try:
        hold, early = slot_gate.acquire_slot(["follower"], _interrupt_after(3))  # 3 秒 > 2 倍門檻
        assert hold is None and early == 128 + signal.SIGTERM
        assert head.poll() is None and _queue_files(tmp_path), "排頭的排隊檔不得被清除"
    finally:
        _stop_proc(head)
        blocker.release()
