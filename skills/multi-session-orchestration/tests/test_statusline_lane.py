"""statusline_lane.py 測試：以子行程執行，HOME 指向 tmp 隔離。"""
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "statusline_lane.py"
INNER = "echo INNER-OUT"

LIVE_TICKET = """# t
## Solution
**L6 現行佇列**（alpha）：401 → 402
**L7 現行佇列**（beta）：410
## Other
"""
ENDED_TICKET = """# t
## Solution
**L6 現行佇列**（alpha）：401 → 402
**L6 現行佇列**（alpha）：（結束）
## Other
"""


def run(tmp_path, stdin, args, ticket=None):
    argv = [sys.executable, str(SCRIPT), *args]
    if ticket is not None:
        (tmp_path / "coord.md").write_text(ticket, encoding="utf-8")
    env = {"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"}
    return subprocess.run(argv, input=stdin, capture_output=True, text=True, env=env)


def payload(name="alpha", **extra):
    return json.dumps({"session_name": name, "workspace": {"project_dir": ""}, **extra})


def coord_args(tmp_path):
    return ["--coord-ticket", str(tmp_path / "coord.md"), "--inner", INNER]


def test_prefix_has_lane_number(tmp_path):
    r = run(tmp_path, payload(), coord_args(tmp_path), LIVE_TICKET)
    assert r.stdout == "L6 │ alpha\nINNER-OUT\n"


def test_ended_lane_shows_name_only(tmp_path):
    r = run(tmp_path, payload(), coord_args(tmp_path), ENDED_TICKET)
    assert r.stdout == "alpha\nINNER-OUT\n"


def test_multiple_lanes_listed(tmp_path):
    ticket = LIVE_TICKET + ""
    ticket = ticket.replace("（beta）", "（alpha）")
    r = run(tmp_path, payload(), coord_args(tmp_path), ticket)
    assert r.stdout.startswith("L6·L7 │ alpha\n")


def test_missing_ticket_keeps_inner(tmp_path):
    r = run(tmp_path, payload(), coord_args(tmp_path))
    assert r.stdout == "alpha\nINNER-OUT\n"


def test_bad_stdin_keeps_inner(tmp_path):
    r = run(tmp_path, "not json {", coord_args(tmp_path), LIVE_TICKET)
    assert r.stdout == "INNER-OUT\n"
    assert "Traceback" not in r.stdout


def test_name_fallback_from_sessions_file(tmp_path):
    sessions = tmp_path / ".claude" / "sessions"
    sessions.mkdir(parents=True)
    (sessions / "1.json").write_text(json.dumps({"sessionId": "S1", "name": "beta"}))
    stdin = json.dumps({"session_id": "S1"})
    r = run(tmp_path, stdin, coord_args(tmp_path), LIVE_TICKET)
    assert r.stdout == "L7 │ beta\nINNER-OUT\n"


def test_inner_from_settings_and_no_recursion(tmp_path):
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "settings.json").write_text(json.dumps({"statusLine": {"command": "echo FROM-SETTINGS"}}))
    r = run(tmp_path, payload(), ["--coord-ticket", str(tmp_path / "coord.md")], LIVE_TICKET)
    assert r.stdout == "L6 │ alpha\nFROM-SETTINGS\n"
    (claude / "settings.json").write_text(json.dumps({"statusLine": {"command": f"python3 {SCRIPT}"}}))
    r = run(tmp_path, payload(), ["--coord-ticket", str(tmp_path / "coord.md")], LIVE_TICKET)
    assert r.stdout == "L6 │ alpha\n"
