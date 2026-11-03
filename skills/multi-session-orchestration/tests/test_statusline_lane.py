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


def run(tmp_path, stdin, args, ticket=None, project_dir=None):
    argv = [sys.executable, str(SCRIPT), *args]
    if ticket is not None:
        (tmp_path / "coord.md").write_text(ticket, encoding="utf-8")
    env = {"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"}
    if project_dir is not None:
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)
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


TODOLIST = """versions:
  - version: "0.5.0"
    status: "active"
    worklog: "docs/work-logs/v0/v0.5/v0.5.0/"
"""
COORD_ID = "0.5.0-W1-349"


def add_ticket(proj, ticket_id, status="in_progress", coordination=True, body=LIVE_TICKET):
    d = proj / "docs/work-logs/v0/v0.5/v0.5.0/tickets"
    d.mkdir(parents=True, exist_ok=True)
    flag = "coordination: true\n" if coordination else ""
    (d / f"{ticket_id}.md").write_text(f"---\nid: {ticket_id}\nstatus: {status}\n{flag}---\n{body}", encoding="utf-8")


def make_project(tmp_path, ticket_ids=(COORD_ID,)):
    proj = tmp_path / "proj"
    (proj / "docs").mkdir(parents=True, exist_ok=True)
    (proj / "docs/todolist.yaml").write_text(TODOLIST, encoding="utf-8")
    for ticket_id in ticket_ids:
        add_ticket(proj, ticket_id)
    return proj


def run_auto(tmp_path, proj):
    return run(tmp_path, payload(), ["--inner", INNER], project_dir=proj)


def test_auto_one_coordination_ticket(tmp_path):
    r = run_auto(tmp_path, make_project(tmp_path))
    assert r.stdout == "L6 │ alpha\nINNER-OUT\n"


def test_auto_zero_tickets_omits_lane_with_stderr(tmp_path):
    r = run_auto(tmp_path, make_project(tmp_path, ticket_ids=()))
    assert r.stdout == "alpha\nINNER-OUT\n"
    assert "[statusline_lane]" in r.stderr and "none" in r.stderr


def test_auto_multiple_tickets_omits_lane_with_stderr(tmp_path):
    r = run_auto(tmp_path, make_project(tmp_path, ticket_ids=(COORD_ID, "0.5.0-W1-350")))
    assert r.stdout == "alpha\nINNER-OUT\n"
    assert "multiple" in r.stderr and "Traceback" not in r.stderr


def test_e1_coordination_flag_vs_no_flag(tmp_path):
    proj = make_project(tmp_path)
    with_flag = run_auto(tmp_path, proj)
    add_ticket(proj, COORD_ID, coordination=False)
    without_flag = run_auto(tmp_path, proj)
    assert with_flag.stdout != without_flag.stdout
    assert without_flag.stdout == "alpha\nINNER-OUT\n"


def test_missing_todolist_degrades_with_stderr(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    r = run_auto(tmp_path, proj)
    assert r.stdout == "alpha\nINNER-OUT\n"
    assert "[statusline_lane]" in r.stderr and "Traceback" not in r.stderr


def test_explicit_coord_ticket_overrides_auto(tmp_path):
    proj = make_project(tmp_path, ticket_ids=())
    r = run(tmp_path, payload(), coord_args(tmp_path), LIVE_TICKET, project_dir=proj)
    assert r.stdout == "L6 │ alpha\nINNER-OUT\n"


def test_closed_override_warns_and_falls_back_to_auto(tmp_path):
    proj = make_project(tmp_path)
    closed = tmp_path / "coord.md"
    closed.write_text("---\nstatus: completed\n---\n## Solution\n**L9 現行佇列**（alpha）：1\n", encoding="utf-8")
    r = run(tmp_path, payload(), ["--coord-ticket", str(closed), "--inner", INNER], project_dir=proj)
    assert r.stdout == "L6 │ alpha\nINNER-OUT\n"
    assert "已結案" in r.stderr
