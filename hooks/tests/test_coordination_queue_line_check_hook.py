"""
Test: coordination-queue-line-check-hook

1. 解析與 lanes.ts 一致：逐筆跑 queue-line-cases.json
2. 漂移守衛：fixtures.ts 內嵌副本與 JSON 一致；E2 正向對照：不一致的文字必判不一致
3. 檢查層 E2：括號附註、全終態未寫（無）會提示；正常寫法不提示
4. main() 端到端：兩條寫入路徑觸發、multi-session.json 缺席不輸出
"""

import importlib.util
import io
import json
import re
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent))

_spec = importlib.util.spec_from_file_location(
    "coordination_queue_line_check_hook", HOOKS_DIR / "coordination-queue-line-check-hook.py"
)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

LB_TESTS = HOOKS_DIR.parent / "skills" / "line-board" / "tests"
CASES_JSON = LB_TESTS / "queue-line-cases.json"
FIXTURES_TS = LB_TESTS / "fixtures.ts"
CASES = json.loads(CASES_JSON.read_text(encoding="utf-8"))["cases"]

COORD = "0.5.0-W1-349"
PREFIX = "0.5.0-W1-"


# ---------------------------------------------------------------- 1 共用案例
@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_parse_lanes_matches_shared_case(case):
    assert hook.parse_lanes(case["text"], case["prefix"]) == case["expect"]


# ---------------------------------------------------------------- 2 漂移守衛
def extract_fixture_json(ts_text):
    """取 fixtures.ts 中 BEGIN/END queue-line-cases.json 標記間 String.raw 模板的 JSON 內文；找不到回傳 None。"""
    m = re.search(
        r"// BEGIN queue-line-cases\.json\n.*?String\.raw`(.*?)`\n// END queue-line-cases\.json",
        ts_text,
        re.S,
    )
    return None if m is None else m.group(1)


def fixture_matches_json(ts_text, json_text):
    raw = extract_fixture_json(ts_text)
    if raw is None:
        return False
    try:
        return json.loads(raw) == json.loads(json_text)
    except ValueError:
        return False


def test_fixtures_ts_copy_matches_json():
    assert fixture_matches_json(FIXTURES_TS.read_text(encoding="utf-8"), CASES_JSON.read_text(encoding="utf-8"))


def test_drift_guard_positive_control_detects_changed_note():
    """E2：只用 tmp 字串，把某案例的 note 改掉，漂移守衛必須判為不一致。"""
    ts = FIXTURES_TS.read_text(encoding="utf-8")
    assert "（已完成，待合併）" in ts
    drifted = ts.replace("（已完成，待合併）", "（已完成，待合併X）", 1)
    assert drifted != ts
    assert not fixture_matches_json(drifted, CASES_JSON.read_text(encoding="utf-8"))
    # 標記遺失同樣判不一致
    assert not fixture_matches_json("const x = 1", CASES_JSON.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- 3 檢查層 E2
def _problems(text, alive, statuses=None):
    statuses = statuses or {}
    return hook.find_problems(
        hook.parse_lanes(text, PREFIX), alive, lambda tid: statuses.get(tid)
    )


def test_check1_bracket_with_note_prompts():
    text = "## Solution\n**L5 現行佇列**（畫面接真資料，待 /clear）：100\n"
    msgs = _problems(text, {"畫面接真資料"}, {"0.5.0-W1-100": "pending"})
    assert len(msgs) == 1 and "L5 括號內『畫面接真資料，待 /clear』" in msgs[0]


def test_check2_all_terminal_without_none_prompts():
    text = "## Solution\n**L5 現行佇列**：100 → 101\n"
    st = {"0.5.0-W1-100": "completed", "0.5.0-W1-101": "closed"}
    msgs = _problems(text, set(), st)
    assert msgs == ["L5 佇列票皆已終態，若線已結束請寫（無），格式：%s" % (hook.LANE_FORMAT % 5)]
    assert "（<session 名稱>）：<票序，或（無）>" in msgs[0]


def test_check3_missing_colon_after_last_valid_prompts():
    # 正向對照（E2）：線已結束卻漏冒號，解析層忽略此行，必須報出原文
    text = "## Solution\n**L5 現行佇列**（s-a）：100\n**L5 現行佇列**（無）\n"
    msgs = hook.find_malformed_lines(text)
    assert len(msgs) == 1
    assert "『**L5 現行佇列**（無）』" in msgs[0] and hook.LANE_FORMAT % 5 in msgs[0]


def test_check3_malformed_superseded_by_valid_is_silent():
    # 之後已補上合格行：歷史的錯誤行不再報
    text = "## Solution\n**L5 現行佇列**（無）\n**L5 現行佇列**（s-a）：（無）\n"
    assert hook.find_malformed_lines(text) == []
    # 合格行、其他線、Solution 以外的段落都不報
    ok = "## Problem Analysis\n**L5 現行佇列** 壞\n## Solution\n**L5 現行佇列**：100\n**L6 現行佇列**（x）：（無）\n"
    assert hook.find_malformed_lines(ok) == []


def test_normal_forms_do_not_prompt():
    ok = "## Solution\n**L5 現行佇列**（s-a）：100 → 101\n**L6 現行佇列**：（無）\n"
    st = {"0.5.0-W1-100": "completed", "0.5.0-W1-101": "pending"}
    assert _problems(ok, {"s-a"}, st) == []
    # 查不到票檔（None）不判終態
    assert _problems("## Solution\n**L5 現行佇列**：100\n", set(), {}) == []
    # session 名單不可得時略過檢查 1
    assert _problems("## Solution\n**L5 現行佇列**（x）：100\n", None, {"0.5.0-W1-100": "pending"}) == []


# ---------------------------------------------------------------- 4 main() 端到端
def _setup_project(tmp_path, monkeypatch, body, with_config=True):
    root = tmp_path / "proj"
    tdir = root / "docs/work-logs/v0/v0.5/v0.5.0/tickets"
    tdir.mkdir(parents=True)
    (tdir / (COORD + ".md")).write_text("---\nstatus: in_progress\n---\n## Solution\n" + body, encoding="utf-8")
    if with_config:
        cfg = root / ".claude/project-integration"
        cfg.mkdir(parents=True)
        (cfg / "multi-session.json").write_text(json.dumps({"coordinationTicket": COORD}), encoding="utf-8")
    home = tmp_path / "home"
    (home / ".claude/sessions").mkdir(parents=True)
    (home / ".claude/sessions/1.json").write_text(
        json.dumps({"name": "s-a", "cwd": str(root), "pid": 1, "status": "idle"}), encoding="utf-8"
    )
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(hook, "get_project_root", lambda: root)
    monkeypatch.setattr(hook, "list_checkouts", lambda logger, r: [str(root)])
    return root


def _run(monkeypatch, payload, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    assert hook.main() == 0
    return capsys.readouterr().out


BASH = {"tool_name": "Bash", "tool_input": {"command": "ticket track append-log %s --section Solution x" % COORD}}
EDIT = {"tool_name": "Edit", "tool_input": {"file_path": "/x/docs/%s.md" % COORD}}


@pytest.mark.parametrize("payload", [BASH, EDIT], ids=["bash", "edit"])
def test_main_emits_additional_context_on_both_paths(tmp_path, monkeypatch, capsys, payload):
    _setup_project(tmp_path, monkeypatch, "**L5 現行佇列**（s-a，待 /clear）：100\n")
    out = _run(monkeypatch, payload, capsys)
    data = json.loads(out)
    ctx = data["hookSpecificOutput"]["additionalContext"]
    assert data["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    assert "L5 括號內『s-a，待 /clear』" in ctx


def test_main_all_terminal_emits(tmp_path, monkeypatch, capsys):
    root = _setup_project(tmp_path, monkeypatch, "**L5 現行佇列**：100\n")
    t = root / "docs/work-logs/v0/v0.5/v0.5.0/tickets/0.5.0-W1-100.md"
    t.write_text("---\nstatus: completed\n---\n", encoding="utf-8")
    ctx = json.loads(_run(monkeypatch, BASH, capsys))["hookSpecificOutput"]["additionalContext"]
    assert "L5 佇列票皆已終態，若線已結束請寫（無）" in ctx


def test_main_malformed_line_emits(tmp_path, monkeypatch, capsys):
    _setup_project(tmp_path, monkeypatch, "**L5 現行佇列**（s-a）：100\n**L5 現行佇列**（無）\n")
    ctx = json.loads(_run(monkeypatch, BASH, capsys))["hookSpecificOutput"]["additionalContext"]
    assert "L5 有一行佇列行格式不符" in ctx


def test_main_normal_is_silent(tmp_path, monkeypatch, capsys):
    _setup_project(tmp_path, monkeypatch, "**L5 現行佇列**（s-a）：100\n")
    assert _run(monkeypatch, BASH, capsys) == ""


def test_main_unrelated_command_is_silent(tmp_path, monkeypatch, capsys):
    _setup_project(tmp_path, monkeypatch, "**L5 現行佇列**（bad）：100\n")
    other = {"tool_name": "Bash", "tool_input": {"command": "ls"}}
    assert _run(monkeypatch, other, capsys) == ""


def test_main_silent_without_multi_session_config(tmp_path, monkeypatch, capsys):
    _setup_project(tmp_path, monkeypatch, "**L5 現行佇列**（bad）：100\n", with_config=False)
    assert _run(monkeypatch, BASH, capsys) == ""
