"""Handoff 寫入 exit_status 欄位測試（0.18.0-W17-031.6）。

覆蓋三路徑：
- 成功：ticket body 含合法 ## Exit Status YAML → handoff JSON exit_status 為 dict
- 缺段：ticket body 無 ## Exit Status → exit_status 為 None（fail-open）
- 解析失敗：YAML 格式錯誤 → exit_status 為 None + stderr warning
"""

import argparse
import json
import os
import tempfile
from pathlib import Path

import pytest
import yaml

from ticket_system.commands.handoff import (
    _execute_auto_handoff,
    _extract_exit_status_for_handoff,
)
from ticket_system.lib.constants import STATUS_IN_PROGRESS


@pytest.fixture
def temp_project():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        tickets_dir = root / "docs" / "work-logs" / "v0" / "v0.18" / "v0.18.0" / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)
        (root / "pubspec.yaml").touch()

        old_env = os.environ.get("CLAUDE_PROJECT_DIR")
        os.environ["CLAUDE_PROJECT_DIR"] = str(root)
        try:
            yield root, tickets_dir
        finally:
            if old_env is None:
                os.environ.pop("CLAUDE_PROJECT_DIR", None)
            else:
                os.environ["CLAUDE_PROJECT_DIR"] = old_env


def _write_ticket(tickets_dir: Path, ticket_id: str, body_extra: str = "") -> None:
    fm = yaml.dump(
        {
            "id": ticket_id,
            "title": "T",
            "status": STATUS_IN_PROGRESS,
            "priority": "P2",
            "type": "IMP",
            "what": "what",
            "created": "2026-05-03",
        },
        allow_unicode=True,
        sort_keys=False,
    )
    content = f"---\n{fm}---\n# T\n\n{body_extra}\n"
    (tickets_dir / f"{ticket_id}.md").write_text(content, encoding="utf-8")


def _make_args(**overrides) -> argparse.Namespace:
    base = dict(
        auto=True,
        from_ticket_id=None,
        direction=None,
        version=None,
        ticket_id=None,
        gc=False,
        status=False,
        to_parent=False,
        to_child=None,
        to_sibling=None,
        context_refresh=False,
        dry_run=False,
        execute=False,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


# ---------------------------------------------------------------------------
# helper unit tests
# ---------------------------------------------------------------------------


def test_extract_returns_dict_when_fenced_yaml_present():
    body = (
        "## Exit Status\n\n"
        "```yaml\n"
        "status: needs_context\n"
        "reason: missing context\n"
        "```\n"
    )
    result = _extract_exit_status_for_handoff({"_body": body})
    assert isinstance(result, dict)
    assert result["status"] == "needs_context"
    assert result["reason"] == "missing context"


def test_extract_strips_html_comment_template():
    """ticket 模板的 HTML 註解區（含示例 YAML）應被剝除，避免誤抽樣板。"""
    body = (
        "## Exit Status\n\n"
        "<!-- 代理人結束時以 YAML 格式回報：\n"
        "```yaml\nstatus: success\n```\n"
        "-->\n"
    )
    result = _extract_exit_status_for_handoff({"_body": body})
    assert result is None  # 樣板註解不應被當成真實回報


def test_extract_returns_none_when_section_missing():
    body = "# T\n\n沒有 Exit Status 段落。\n"
    result = _extract_exit_status_for_handoff({"_body": body})
    assert result is None


def test_extract_returns_none_on_yaml_parse_error(capsys):
    body = (
        "## Exit Status\n\n"
        "```yaml\n"
        "status: needs_context\n"
        "  invalid: : indent: bad\n"
        "```\n"
    )
    result = _extract_exit_status_for_handoff({"_body": body})
    assert result is None
    err = capsys.readouterr().err
    assert "Exit Status YAML 解析失敗" in err


def test_extract_returns_none_when_status_invalid():
    body = "## Exit Status\n\n```yaml\nstatus: weird_state\n```\n"
    result = _extract_exit_status_for_handoff({"_body": body})
    assert result is None


# ---------------------------------------------------------------------------
# 整合：handoff --auto 寫入 JSON
# ---------------------------------------------------------------------------


def _read_handoff_json(root: Path, ticket_id: str) -> dict:
    return json.loads(
        (root / ".claude" / "handoff" / "pending" / f"{ticket_id}.json").read_text()
    )


def test_auto_handoff_writes_exit_status_when_present(temp_project):
    root, tickets_dir = temp_project
    _write_ticket(
        tickets_dir,
        "0.18.0-W17-201",
        body_extra=(
            "## Exit Status\n\n"
            "```yaml\n"
            "status: needs_context\n"
            "reason: 缺料\n"
            "confidence: 0.7\n"
            "```\n"
        ),
    )

    args = _make_args(from_ticket_id="0.18.0-W17-201", direction="to-parent")
    rc = _execute_auto_handoff(args)
    assert rc == 0

    data = _read_handoff_json(root, "0.18.0-W17-201")
    assert "exit_status" in data
    assert isinstance(data["exit_status"], dict)
    assert data["exit_status"]["status"] == "needs_context"
    assert data["exit_status"]["reason"] == "缺料"


def test_auto_handoff_writes_null_exit_status_when_section_missing(temp_project):
    root, tickets_dir = temp_project
    _write_ticket(tickets_dir, "0.18.0-W17-202", body_extra="")

    args = _make_args(from_ticket_id="0.18.0-W17-202", direction="to-parent")
    rc = _execute_auto_handoff(args)
    assert rc == 0

    data = _read_handoff_json(root, "0.18.0-W17-202")
    assert "exit_status" in data
    assert data["exit_status"] is None


def test_auto_handoff_writes_null_on_yaml_parse_error(temp_project, capsys):
    root, tickets_dir = temp_project
    _write_ticket(
        tickets_dir,
        "0.18.0-W17-203",
        body_extra=(
            "## Exit Status\n\n"
            "```yaml\n"
            "status: blocked\n"
            "  : : bad indent\n"
            "```\n"
        ),
    )

    args = _make_args(from_ticket_id="0.18.0-W17-203", direction="to-parent")
    rc = _execute_auto_handoff(args)
    assert rc == 0  # 不阻擋 handoff

    data = _read_handoff_json(root, "0.18.0-W17-203")
    assert data["exit_status"] is None
    err = capsys.readouterr().err
    assert "Exit Status YAML 解析失敗" in err
