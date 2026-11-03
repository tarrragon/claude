"""coordination_ticket.py 測試：以 tmp_path 建假 repo。"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import coordination_ticket as ct  # noqa: E402

TODOLIST = """versions:
  - version: "0.5.0"
    status: "completed"
    worklog: "docs/work-logs/v0/v0.5/v0.5.0/"
  - version: "0.6.0"
    status: "active"
    worklog: "docs/work-logs/v0/v0.6/v0.6.0/"
"""
COORD = "status: in_progress\ncoordination: true\n"


def make_repo(tmp_path, tickets, todolist=TODOLIST, override=None):
    if todolist is not None:
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs/todolist.yaml").write_text(todolist, encoding="utf-8")
    for ticket_id, fm in tickets.items():
        version = ticket_id.split("-")[0]
        minor = ".".join(version.split(".")[:2])
        d = tmp_path / f"docs/work-logs/v0/v{minor}/v{version}/tickets"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{ticket_id}.md").write_text(f"---\nid: {ticket_id}\n{fm}---\n# body\n", encoding="utf-8")
    if override:
        cfg = tmp_path / ".claude/project-integration"
        cfg.mkdir(parents=True)
        (cfg / "multi-session.json").write_text(json.dumps({"coordinationTicket": override}))
    return tmp_path


def test_one_ticket_ok(tmp_path):
    make_repo(tmp_path, {"0.6.0-W1-099": COORD, "0.6.0-W1-100": "status: in_progress\n"})
    r = ct.resolve_coordination_ticket(tmp_path)
    assert (r["kind"], r["ticket"], r["source"]) == ("ok", "0.6.0-W1-099", "auto")


def test_none(tmp_path):
    make_repo(tmp_path, {"0.6.0-W1-100": "status: in_progress\n"})
    assert ct.resolve_coordination_ticket(tmp_path)["kind"] == "none"


def test_multiple(tmp_path):
    make_repo(tmp_path, {"0.6.0-W1-099": COORD, "0.6.0-W1-101": COORD})
    r = ct.resolve_coordination_ticket(tmp_path)
    assert r["kind"] == "multiple"
    assert [c["ticket"] for c in r["candidates"]] == ["0.6.0-W1-099", "0.6.0-W1-101"]


def test_override_open_wins(tmp_path):
    make_repo(tmp_path, {"0.6.0-W1-099": COORD, "0.6.0-W1-050": "status: pending\n"},
              override="0.6.0-W1-050")
    r = ct.resolve_coordination_ticket(tmp_path)
    assert (r["kind"], r["ticket"], r["source"]) == ("ok", "0.6.0-W1-050", "override")


def test_override_closed_falls_back_with_warning(tmp_path):
    make_repo(tmp_path, {"0.6.0-W1-099": COORD, "0.5.0-W1-349": "status: completed\n"},
              override="0.5.0-W1-349")
    r = ct.resolve_coordination_ticket(tmp_path)
    assert (r["kind"], r["ticket"], r["source"]) == ("ok", "0.6.0-W1-099", "auto")
    assert any("0.5.0-W1-349" in w and "已結案" in w for w in r["warnings"])


def test_call_override_beats_config(tmp_path):
    make_repo(tmp_path, {"0.6.0-W1-099": COORD, "0.6.0-W1-050": "status: pending\n"},
              override="0.5.0-W1-349")
    r = ct.resolve_coordination_ticket(tmp_path, override="0.6.0-W1-050")
    assert r["ticket"] == "0.6.0-W1-050" and r["source"] == "override"


def test_todolist_missing_is_error(tmp_path, capsys):
    make_repo(tmp_path, {"0.6.0-W1-099": COORD}, todolist=None)
    r = ct.resolve_coordination_ticket(tmp_path)
    assert r["kind"] == "error" and r["reason"]
    assert "todolist" in capsys.readouterr().err


FOUR_SPACE = """versions:
    - version: "0.6.0"
      status: "active"
      worklog: "docs/work-logs/v0/v0.6/v0.6.0/"
"""
INLINE_STATUS = """versions:
  - status: "active"
    version: "0.6.0"
  - { version: "0.6.0", status: "active" }
"""


@pytest.mark.parametrize("todolist", [FOUR_SPACE, INLINE_STATUS], ids=["four-space", "inline-item"])
def test_unparsable_todolist_is_error(tmp_path, capsys, todolist):
    """E2 正向對照：格式不符不可安靜回 none。"""
    make_repo(tmp_path, {"0.6.0-W1-099": COORD}, todolist=todolist)
    r = ct.resolve_coordination_ticket(tmp_path)
    assert r["kind"] == "error" and "0 個版本" in r["reason"]
    assert "0 個版本" in capsys.readouterr().err


def test_completed_version_coordination_ticket_not_scanned(tmp_path):
    make_repo(tmp_path, {"0.5.0-W1-001": COORD})
    assert ct.resolve_coordination_ticket(tmp_path)["kind"] == "none"


def test_cli_json_fields(tmp_path):
    make_repo(tmp_path, {"0.6.0-W1-099": COORD})
    out = subprocess.run([sys.executable, str(SCRIPTS / "coordination_ticket.py"), "--json",
                          "--project-dir", str(tmp_path)], capture_output=True, text=True)
    data = json.loads(out.stdout)
    assert out.returncode == 0
    assert {"kind", "ticket", "path", "source", "warnings", "candidates", "reason"} <= set(data)


# ---------------------------------------------------------------- U1 配對（對應 userTodos.ts parseUserTodos）
LB_TESTS = SCRIPTS.parent.parent / "line-board" / "tests"
CASES_JSON = LB_TESTS / "user-todo-cases.json"
FIXTURES_TS = LB_TESTS / "fixtures.ts"
U1_CASES = json.loads(CASES_JSON.read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", U1_CASES, ids=[c["name"] for c in U1_CASES])
def test_parse_user_todos_matches_shared_case(case):
    assert ct.parse_user_todos(case["text"]) == case["expect"]


def _extract_ts_copy(ts_text):
    m = re.search(
        r"// BEGIN user-todo-cases\.json\n.*?String\.raw`(.*?)`\n// END user-todo-cases\.json", ts_text, re.S
    )
    return None if m is None else m.group(1)


def _copy_matches(ts_text, json_text):
    raw = _extract_ts_copy(ts_text)
    if raw is None:
        return False
    try:
        return json.loads(raw) == json.loads(json_text)
    except ValueError:
        return False


def test_fixtures_ts_copy_matches_user_todo_json():
    assert _copy_matches(FIXTURES_TS.read_text(encoding="utf-8"), CASES_JSON.read_text(encoding="utf-8"))


def test_user_todo_drift_guard_detects_changed_copy():
    """E2：副本內容被改、標記遺失，漂移守衛都必須判為不一致。"""
    ts = FIXTURES_TS.read_text(encoding="utf-8")
    drifted = ts.replace("開 L44 session", "開 L45 session", 1)
    assert drifted != ts
    assert not _copy_matches(drifted, CASES_JSON.read_text(encoding="utf-8"))
    assert not _copy_matches("const x = 1", CASES_JSON.read_text(encoding="utf-8"))


def test_parse_user_todos_ignores_fenced_block():
    fence = "`" * 3
    text = f"## Solution\n{fence}\n**用戶待辦**（c）：fence 內\n{fence}\n**用戶待辦**（d）：真的\n"
    assert ct.parse_user_todos(text) == [{"key": "d", "item": "真的"}]
    # fence 未閉合時其後的行都算示例
    assert ct.parse_user_todos(f"## Solution\n{fence}\n**用戶待辦**（c）：x\n") == []
