"""framework-issue feedback 測試：界線決定、三類判定、輸出欄位。

gh 以注入的假 runner 取代，git 本地 tag 查詢以 monkeypatch 取代，不打真實 API。
"""

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import feedback  # noqa: E402
import gh_common  # noqa: E402

TAG_TIME = "2026-11-10T12:00:00+08:00"  # = 2026-11-10T04:00:00Z
BEFORE = "2026-11-09T00:00:00Z"
AFTER = "2026-11-11T00:00:00Z"

TODOLIST = """versions:
  - version: "3.2.0"
    status: "completed"
  - version: "3.2.1"
    status: "completed"
  - version: "3.3.0"
    status: "active"
"""

OBS = "<!-- observation: 仍重現 by s1 -->\n<!-- framework-version: 3.2.1 -->\n內容"
OBS_NO_VERSION = "<!-- observation: 舊格式 by s2 -->\n內容"
SECTION = "<!-- section: 當前結論 owner: llm-dev -->\n分診"
PLAIN = "主控方分診：排入 3.4.0"
ENV_BODY = "描述\n\n<!-- env-info -->\n- OS: macOS\n- 框架版本: 3.2.1\n<!-- /env-info -->"


def _issue(number, created, body="", labels=()):
    return {
        "number": number,
        "title": f"issue {number}",
        "createdAt": created,
        "labels": [{"name": n} for n in labels],
        "body": body,
        "state": "OPEN",
    }


class FakeGh:
    """依參數回應的假 gh；記錄所有呼叫。"""

    def __init__(self, issues=(), comments=None, remote_tag=None):
        self.issues = list(issues)
        self.comments = comments or {}
        self.remote_tag = remote_tag
        self.calls = []

    def __call__(self, args):
        self.calls.append(args)
        if args[:2] == ["issue", "list"]:
            return json.dumps(self.issues)
        if args[0] == "api" and "/commits/" in args[1]:
            if self.remote_tag is None:
                raise feedback.FeedbackError("404", 3)
            return self.remote_tag + "\n"
        if args[0] == "api" and args[1] == "--paginate":
            number = int(args[2].split("/issues/")[1].split("/")[0])
            return "\n".join(json.dumps(c) for c in self.comments.get(number, []))
        raise AssertionError(f"unexpected gh call: {args}")


@pytest.fixture
def todolist(tmp_path):
    path = tmp_path / "todolist.yaml"
    path.write_text(TODOLIST, encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def gh_ready(monkeypatch):
    monkeypatch.setattr(gh_common, "check_gh_available", lambda: True)
    monkeypatch.setattr(gh_common, "check_gh_authenticated", lambda: True)


def _run_json(capsys, argv, gh):
    rc = feedback.main(argv + ["--json"], gh=gh)
    out = capsys.readouterr().out
    return rc, (json.loads(out) if rc == 0 else None)


# --- 界線 ---

def test_last_completed_version_picks_highest(todolist):
    assert feedback.last_completed_version(todolist) == "3.2.1"


def test_boundary_uses_local_tag(monkeypatch, todolist, capsys):
    seen = []
    monkeypatch.setattr(feedback, "local_tag_time", lambda v: seen.append(v) or TAG_TIME)
    rc, data = _run_json(capsys, ["--todolist", str(todolist)], FakeGh())
    assert rc == 0
    assert seen == ["3.2.1"]
    assert data["version"] == "3.2.1"
    assert data["since_source"] == "本地 tag"


def test_boundary_falls_back_to_remote_tag(monkeypatch, todolist, capsys):
    monkeypatch.setattr(feedback, "local_tag_time", lambda v: None)
    rc, data = _run_json(capsys, ["--todolist", str(todolist)], FakeGh(remote_tag="2026-11-10T04:00:00Z"))
    assert rc == 0
    assert data["since_source"] == "遠端 tag"


def test_missing_tag_everywhere_exits_nonzero_and_asks_since(monkeypatch, todolist, capsys):
    """E2 正向對照：本地與遠端都沒有 tag → exit 非 0，不送 issue 查詢。"""
    monkeypatch.setattr(feedback, "local_tag_time", lambda v: None)
    gh = FakeGh(issues=[_issue(1, AFTER)])
    rc = feedback.main(["--todolist", str(todolist), "--since-version", "9.9.9"], gh=gh)
    err = capsys.readouterr().err
    assert rc == feedback.EXIT_NEED_SINCE
    assert "--since" in err and "v9.9.9" in err
    assert not any(call[:2] == ["issue", "list"] for call in gh.calls)


def test_since_overrides_tag_lookup(monkeypatch, todolist, capsys):
    monkeypatch.setattr(feedback, "local_tag_time", lambda v: pytest.fail("不該查 tag"))
    rc, data = _run_json(capsys, ["--todolist", str(todolist), "--since", TAG_TIME], FakeGh())
    assert rc == 0
    assert data["since_source"] == "--since"


def test_no_completed_version_exits_nonzero(tmp_path, capsys):
    path = tmp_path / "todolist.yaml"
    path.write_text('versions:\n  - version: "1.0.0"\n    status: "active"\n', encoding="utf-8")
    rc = feedback.main(["--todolist", str(path)], gh=FakeGh())
    assert rc == feedback.EXIT_NEED_SINCE


# --- 三類判定 ---

def _classify_run(monkeypatch, capsys, todolist, issues, comments):
    monkeypatch.setattr(feedback, "local_tag_time", lambda v: TAG_TIME)
    return _run_json(capsys, ["--todolist", str(todolist)], FakeGh(issues, comments))


def test_three_categories_and_unmarked_not_counted(monkeypatch, capsys, todolist):
    issues = [
        _issue(10, AFTER, body=ENV_BODY, labels=["bug"]),
        _issue(11, BEFORE),
        _issue(12, BEFORE),
    ]
    comments = {
        10: [],
        11: [{"created_at": AFTER, "body": OBS}],
        12: [{"created_at": AFTER, "body": PLAIN}],
    }
    rc, data = _classify_run(monkeypatch, capsys, todolist, issues, comments)
    assert rc == 0
    by_number = {r["number"]: r for r in data["issues"]}
    assert by_number[10]["category"] == "新開"
    assert by_number[11]["category"] == "新觀測"
    assert by_number[12]["category"] == "未標記留言"
    assert data["summary"] == {"feedback_count": 2, "new": 1, "observation": 1, "unmarked": 1}


def test_triage_only_issue_is_not_feedback(monkeypatch, capsys, todolist):
    """v3.2.1 實測誤報型：舊 issue 在界線後只有區段留言 → 不列入任何類別。"""
    issues = [_issue(20, BEFORE)]
    comments = {20: [{"created_at": AFTER, "body": SECTION}]}
    rc, data = _classify_run(monkeypatch, capsys, todolist, issues, comments)
    assert rc == 0
    assert data["issues"] == []
    assert data["summary"]["feedback_count"] == 0


def test_comment_before_boundary_ignored(monkeypatch, capsys, todolist):
    """REST since 依 updated_at 過濾，界線前建立、之後才編輯的觀測不算新觀測。"""
    issues = [_issue(21, BEFORE)]
    comments = {21: [{"created_at": BEFORE, "body": OBS}]}
    rc, data = _classify_run(monkeypatch, capsys, todolist, issues, comments)
    assert data["issues"] == []


# --- 欄位 ---

def test_row_fields_and_versions(monkeypatch, capsys, todolist):
    issues = [_issue(30, AFTER, body=ENV_BODY, labels=["bug", "hook"]), _issue(31, BEFORE)]
    comments = {
        30: [{"created_at": AFTER, "body": OBS}],
        31: [{"created_at": AFTER, "body": OBS_NO_VERSION}],
    }
    rc, data = _classify_run(monkeypatch, capsys, todolist, issues, comments)
    row30, row31 = data["issues"]
    assert set(row30) >= {
        "number", "title", "category", "created", "last_qualifying_comment",
        "framework_version", "labels",
    }
    assert row30["framework_version"] == "3.2.1"
    assert row30["last_qualifying_comment"] == AFTER
    assert row30["labels"] == ["bug", "hook"]
    assert row31["framework_version"] == "unknown"


def test_new_issue_without_env_info_is_unknown(monkeypatch, capsys, todolist):
    rc, data = _classify_run(monkeypatch, capsys, todolist, [_issue(40, AFTER, body="無環境資訊")], {40: []})
    assert data["issues"][0]["framework_version"] == "unknown"
    assert data["issues"][0]["last_qualifying_comment"] is None


def test_text_output_has_table_and_counts(monkeypatch, capsys, todolist):
    monkeypatch.setattr(feedback, "local_tag_time", lambda v: TAG_TIME)
    gh = FakeGh([_issue(50, AFTER, body=ENV_BODY)], {50: []})
    rc = feedback.main(["--todolist", str(todolist)], gh=gh)
    out = capsys.readouterr().out
    assert rc == 0
    assert "v3.2.1" in out and "回饋數：1" in out
    assert "| 50 | issue 50 | 新開 |" in out


def test_json_flag_changes_output(monkeypatch, capsys, todolist):
    """E1：同一 fixture 傳與不傳 --json 產物不同，且 --json 可解析。"""
    monkeypatch.setattr(feedback, "local_tag_time", lambda v: TAG_TIME)
    feedback.main(["--todolist", str(todolist)], gh=FakeGh([_issue(60, AFTER)], {60: []}))
    text = capsys.readouterr().out
    feedback.main(["--todolist", str(todolist), "--json"], gh=FakeGh([_issue(60, AFTER)], {60: []}))
    as_json = capsys.readouterr().out
    assert text != as_json
    assert json.loads(as_json)["issues"][0]["number"] == 60
    with pytest.raises(json.JSONDecodeError):
        json.loads(text)
