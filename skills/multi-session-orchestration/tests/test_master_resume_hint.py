"""master_resume_hint.py 測試。

子行程測試（HOME 與 CLAUDE_PROJECT_DIR 指向 tmp）驗整支 hook 的輸出；
模組測試（importlib 載入、monkeypatch 行程查詢）驗名稱解析的兩條路徑與優先序。

正向：名稱為「主控」且 source 為 clear／compact 時輸出 additionalContext。
E2 對照：名稱不是「主控」、source 為 startup／resume、找不到 session 檔、
路徑 1 比對到非主控而祖先檔為主控、同 id 舊檔的行程已結束時，都不輸出。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "master_resume_hint.py"
SESSION_ID = "c1c1c1c1-0000-4000-8000-000000000000"
# pid 1 必定存在；session 檔不寫 procStart 時存活判定只看 pid 存在
LIVE_PID = 1


def load_module():
    spec = importlib.util.spec_from_file_location("master_resume_hint", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_session(home: Path, file_stem: str, name: str, session_id: str, pid: int = LIVE_PID, **extra) -> None:
    directory = home / ".claude" / "sessions"
    directory.mkdir(parents=True, exist_ok=True)
    record = {"pid": pid, "name": name, "sessionId": session_id, **extra}
    (directory / f"{file_stem}.json").write_text(json.dumps(record), encoding="utf-8")


def write_config(project: Path, ticket: str = "0.5.0-W1-349") -> None:
    path = project / ".claude" / "project-integration" / "multi-session.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"coordinationTicket": ticket}), encoding="utf-8")


def env_for(tmp_path: Path) -> dict:
    return {"HOME": str(tmp_path / "home"), "CLAUDE_PROJECT_DIR": str(tmp_path / "project"), "PATH": "/usr/bin:/bin"}


def run(tmp_path: Path, source: str, session_id: str = SESSION_ID, stdin: str | None = None) -> subprocess.CompletedProcess:
    payload = stdin if stdin is not None else json.dumps({"source": source, "session_id": session_id})
    return subprocess.run([sys.executable, str(SCRIPT)], input=payload, capture_output=True, text=True, env=env_for(tmp_path), timeout=30)


def context_of(result: subprocess.CompletedProcess) -> str:
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]


# ---- 子行程：整支 hook 的輸出 ----


@pytest.mark.parametrize("source", ["clear", "compact"])
def test_master_after_clear_or_compact_gets_hint(tmp_path, source):
    write_session(tmp_path / "home", "999", "主控", SESSION_ID)
    write_config(tmp_path / "project")
    text = context_of(run(tmp_path, source))
    assert f"剛經過 /{source}" in text
    assert "mcp__line-board__line_status" in text
    assert "0.5.0-W1-349" in text
    assert "line-continuity.md §4" in text


@pytest.mark.parametrize("source", ["startup", "resume"])
def test_master_on_startup_or_resume_gets_nothing(tmp_path, source):
    """E2 對照：同一個「主控」session 檔，只換 source，輸出必須為空。"""
    write_session(tmp_path / "home", "999", "主控", SESSION_ID)
    write_config(tmp_path / "project")
    result = run(tmp_path, source)
    assert result.returncode == 0
    assert result.stdout == ""


def test_other_name_gets_nothing(tmp_path):
    """E2 對照：source=clear 不變，名稱不是「主控」時不提示。"""
    write_session(tmp_path / "home", "999", "看板工具", SESSION_ID)
    write_config(tmp_path / "project")
    result = run(tmp_path, "clear")
    assert result.returncode == 0
    assert result.stdout == ""


def test_no_session_file_gets_nothing(tmp_path):
    write_config(tmp_path / "project")
    result = run(tmp_path, "clear")
    assert result.returncode == 0
    assert result.stdout == ""


def test_dead_process_file_with_same_session_id_is_ignored(tmp_path):
    """E2 對照：同 id 的「主控」檔屬於已結束行程（procStart 不符），不得採用。"""
    write_session(tmp_path / "home", "999", "主控", SESSION_ID, procStart="Mon Jan  1 00:00:00 1990")
    write_config(tmp_path / "project")
    result = run(tmp_path, "clear")
    assert result.returncode == 0
    assert result.stdout == ""


def test_missing_config_still_hints_and_says_so(tmp_path):
    write_session(tmp_path / "home", "999", "主控", SESSION_ID)
    assert "讀不到協調票" in context_of(run(tmp_path, "clear"))


def test_invalid_stdin_does_not_block_and_logs_traceback(tmp_path):
    result = run(tmp_path, "clear", stdin="not json")
    assert result.returncode == 0
    assert result.stdout == ""
    assert "[master-resume-hint] error" in result.stderr
    log = (tmp_path / "project" / ".claude" / "hook-logs" / "master-resume-hint" / "hook.log").read_text(encoding="utf-8")
    assert "Traceback" in log


# ---- 模組：名稱解析的兩條路徑與優先序 ----


@pytest.fixture
def mod(tmp_path, monkeypatch):
    module = load_module()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path / "project"))
    return module


def fake_chain(monkeypatch, mod, start: int, chain: dict[int, tuple[str, int]]) -> None:
    """chain：pid → (執行檔名, 父 pid)；os.getppid() 回傳 start。"""
    monkeypatch.setattr(mod.os, "getppid", lambda: start)
    monkeypatch.setattr(mod, "process_comm", lambda pid: chain.get(pid, ("", 0))[0])
    monkeypatch.setattr(mod, "parent_pid", lambda pid: chain.get(pid, ("", None))[1])
    monkeypatch.setattr(mod, "is_alive_session", lambda data: True)


def test_ancestor_path_reads_nearest_claude_through_wrappers(tmp_path, monkeypatch, mod):
    """/clear 後檔內 sessionId 仍是舊的：沿 python → uv → sh → claude 找到 claude 祖先的檔。"""
    write_session(tmp_path / "home", "400", "主控", "old-id", pid=400)
    fake_chain(monkeypatch, mod, 100, {100: ("uv", 200), 200: ("/bin/sh", 400), 400: ("claude", 1)})
    assert mod.session_name(SESSION_ID) == "主控"


def test_ancestor_path_stops_at_first_claude(tmp_path, monkeypatch, mod):
    """E2 對照：最近的 claude 祖先沒有檔時停手，不得走到外層另一個 claude（主控以 claude -p 開的子 session）。"""
    write_session(tmp_path / "home", "900", "主控", "outer-id", pid=900)
    fake_chain(monkeypatch, mod, 100, {100: ("uv", 400), 400: ("claude", 800), 800: ("zsh", 900), 900: ("claude", 1)})
    assert mod.session_name(SESSION_ID) is None


def test_session_id_path_takes_priority_over_ancestor(tmp_path, monkeypatch, mod):
    """E2 對照：路徑 1 比對到非主控時，即使祖先檔名為主控也不採用（兩路徑不得取聯集或對調）。"""
    write_session(tmp_path / "home", "300", "看板工具", SESSION_ID, pid=300)
    write_session(tmp_path / "home", "400", "主控", "old-id", pid=400)
    fake_chain(monkeypatch, mod, 100, {100: ("claude", 1)})
    monkeypatch.setattr(mod.os, "getppid", lambda: 400)
    monkeypatch.setattr(mod, "process_comm", lambda pid: "claude")
    assert mod.session_name(SESSION_ID) == "看板工具"


def test_is_alive_session_compares_proc_start(monkeypatch, mod):
    monkeypatch.setattr(mod, "ps_field", lambda pid, field: "Sat Oct 31  06:58:39 2026")
    assert mod.is_alive_session({"pid": 5, "procStart": "Sat Oct 31 06:58:39 2026"})
    assert not mod.is_alive_session({"pid": 5, "procStart": "Fri Oct 30 06:58:39 2026"})
    monkeypatch.setattr(mod, "ps_field", lambda pid, field: None)
    assert not mod.is_alive_session({"pid": 5, "procStart": "Sat Oct 31 06:58:39 2026"})
