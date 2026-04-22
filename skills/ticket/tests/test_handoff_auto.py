"""
Handoff --auto 自動生成模式測試（0.18.0-W17-011.5）。

覆蓋範圍：
- CLI 參數驗證（缺 --from-ticket-id / 缺 --direction / 非法 direction）
- 成功路徑（各 direction；含 to-child:TARGET 任務鏈格式）
- JSON schema 對齊 handoff-reminder-hook.py 讀取格式
- ticket 不存在回 exit code 2
- chain 欄位透傳自 ticket yaml
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
    execute,
)
from ticket_system.lib.constants import STATUS_IN_PROGRESS, STATUS_PENDING


# ----------------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------------

@pytest.fixture
def temp_project():
    """建立臨時專案根目錄與 ticket 檔案。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        tickets_dir = root / "docs" / "work-logs" / "v0.18.0" / "tickets"
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


def _create_ticket(
    tickets_dir: Path,
    ticket_id: str,
    *,
    status: str = STATUS_IN_PROGRESS,
    title: str = "Sample Ticket",
    what: str = "sample what",
    chain: dict = None,
) -> None:
    data = {
        "id": ticket_id,
        "title": title,
        "status": status,
        "priority": "P2",
        "type": "IMP",
        "what": what,
        "created": "2026-04-20",
    }
    if chain is not None:
        data["chain"] = chain
    fm = yaml.dump(data, allow_unicode=True, sort_keys=False)
    (tickets_dir / f"{ticket_id}.md").write_text(
        f"---\n{fm}---\n# {title}\n", encoding="utf-8"
    )


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


# ----------------------------------------------------------------------------
# 參數驗證
# ----------------------------------------------------------------------------

def test_auto_requires_from_ticket_id(temp_project, capsys):
    args = _make_args(direction="to-child")
    rc = _execute_auto_handoff(args)
    assert rc == 1
    assert "--from-ticket-id" in capsys.readouterr().err


def test_auto_requires_direction(temp_project, capsys):
    args = _make_args(from_ticket_id="0.18.0-W17-001")
    rc = _execute_auto_handoff(args)
    assert rc == 1
    assert "--direction" in capsys.readouterr().err


def test_auto_rejects_invalid_direction(temp_project, capsys):
    args = _make_args(from_ticket_id="0.18.0-W17-001", direction="to-elsewhere")
    rc = _execute_auto_handoff(args)
    assert rc == 1
    assert "--direction 無效" in capsys.readouterr().err


def test_auto_rejects_bad_ticket_id_format(temp_project):
    args = _make_args(from_ticket_id="not-a-ticket", direction="to-child")
    rc = _execute_auto_handoff(args)
    assert rc == 1


# ----------------------------------------------------------------------------
# Ticket 載入失敗
# ----------------------------------------------------------------------------

def test_auto_returns_2_when_ticket_missing(temp_project):
    args = _make_args(
        from_ticket_id="0.18.0-W17-999",
        direction="to-parent",
    )
    rc = _execute_auto_handoff(args)
    assert rc == 2


# ----------------------------------------------------------------------------
# 成功路徑
# ----------------------------------------------------------------------------

def test_auto_generates_json_to_pending(temp_project):
    root, tickets_dir = temp_project
    _create_ticket(
        tickets_dir, "0.18.0-W17-001",
        title="Scheduler anchor",
        what="scheduler analysis",
        chain={"root": "0.18.0-W17-001", "parent": None, "depth": 0},
    )

    args = _make_args(from_ticket_id="0.18.0-W17-001", direction="to-child")
    rc = _execute_auto_handoff(args)
    assert rc == 0

    out_file = root / ".claude" / "handoff" / "pending" / "0.18.0-W17-001.json"
    assert out_file.exists()


def test_auto_stdout_includes_runqueue_hint_for_pending_candidate(temp_project, capsys):
    root, tickets_dir = temp_project
    _create_ticket(
        tickets_dir,
        "0.18.0-W17-001",
        status=STATUS_PENDING,
        title="Resume candidate",
    )

    args = _make_args(from_ticket_id="0.18.0-W17-001", direction="to-child")
    rc = _execute_auto_handoff(args)
    assert rc == 0

    out = capsys.readouterr().out
    assert "下一步候選（runqueue --context=resume --top 3）" in out
    assert "0.18.0-W17-001" in out
    assert "Resume candidate" in out
    assert "目前無待恢復 ticket" not in out


def test_auto_stdout_shows_empty_resume_message_when_no_runnable_candidate(
    temp_project, capsys
):
    root, tickets_dir = temp_project
    _create_ticket(
        tickets_dir,
        "0.18.0-W17-002",
        status=STATUS_IN_PROGRESS,
        title="Not runnable yet",
    )

    args = _make_args(from_ticket_id="0.18.0-W17-002", direction="to-child")
    rc = _execute_auto_handoff(args)
    assert rc == 0

    out = capsys.readouterr().out
    assert "下一步候選（runqueue --context=resume --top 3）" in out
    assert "目前無待恢復 ticket" in out


def test_auto_json_schema_aligns_with_hook_reader(temp_project):
    root, tickets_dir = temp_project
    _create_ticket(
        tickets_dir, "0.18.0-W17-002",
        status=STATUS_IN_PROGRESS,
        title="Title X",
        what="what X",
        chain={"root": "0.18.0-W17-001", "parent": "0.18.0-W17-001", "depth": 1},
    )

    args = _make_args(from_ticket_id="0.18.0-W17-002", direction="to-child:0.18.0-W17-003")
    rc = _execute_auto_handoff(args)
    assert rc == 0

    data = json.loads(
        (root / ".claude" / "handoff" / "pending" / "0.18.0-W17-002.json").read_text()
    )
    # 核心欄位（hook 讀取）
    assert data["ticket_id"] == "0.18.0-W17-002"
    assert data["direction"] == "to-child:0.18.0-W17-003"
    assert data["from_status"] == STATUS_IN_PROGRESS
    assert data["title"] == "Title X"
    assert data["what"] == "what X"
    assert data["chain"]["root"] == "0.18.0-W17-001"
    assert data["chain"]["parent"] == "0.18.0-W17-001"
    assert data["chain"]["depth"] == 1
    assert data["resumed_at"] is None
    assert data["auto_generated"] is True
    # timestamp 存在且為 ISO 格式字串
    assert "T" in data["timestamp"]


def test_auto_passes_through_empty_chain(temp_project):
    """無 chain 欄位的 ticket 仍應生成（chain = {}）。"""
    root, tickets_dir = temp_project
    _create_ticket(tickets_dir, "0.18.0-W17-010", chain=None)

    args = _make_args(from_ticket_id="0.18.0-W17-010", direction="to-parent")
    rc = _execute_auto_handoff(args)
    assert rc == 0

    data = json.loads(
        (root / ".claude" / "handoff" / "pending" / "0.18.0-W17-010.json").read_text()
    )
    assert data["chain"] == {}


def test_auto_supports_to_source_direction(temp_project):
    root, tickets_dir = temp_project
    _create_ticket(tickets_dir, "0.18.0-W17-005")

    args = _make_args(from_ticket_id="0.18.0-W17-005", direction="to-source")
    rc = _execute_auto_handoff(args)
    assert rc == 0
    data = json.loads(
        (root / ".claude" / "handoff" / "pending" / "0.18.0-W17-005.json").read_text()
    )
    assert data["direction"] == "to-source"


def test_auto_supports_context_refresh_direction(temp_project):
    root, tickets_dir = temp_project
    _create_ticket(tickets_dir, "0.18.0-W17-006")

    args = _make_args(from_ticket_id="0.18.0-W17-006", direction="context-refresh")
    rc = _execute_auto_handoff(args)
    assert rc == 0


# ----------------------------------------------------------------------------
# 不破壞既有手動模式
# ----------------------------------------------------------------------------

def test_manual_handoff_not_triggered_without_auto(temp_project):
    """execute() 在 auto=False 時不會走 auto 分支。"""
    root, tickets_dir = temp_project
    _create_ticket(tickets_dir, "0.18.0-W17-020", status=STATUS_PENDING)

    # auto 未啟用且無 ticket_id、無 status、無 gc → 走既有「自動搜尋 completed」分支
    args = _make_args(auto=False, from_ticket_id=None, direction=None)
    rc = execute(args)
    # 沒有 completed ticket 時返回 0（NO_COMPLETED_TASKS）
    assert rc == 0
    # 不應產生 auto 的 handoff 檔
    assert not (root / ".claude" / "handoff" / "pending").exists() or not any(
        (root / ".claude" / "handoff" / "pending").iterdir()
    )


def test_auto_overwrites_existing_file(temp_project):
    """--auto 多次呼叫同 ticket 應覆寫（scheduler 重新生成場景）。"""
    root, tickets_dir = temp_project
    _create_ticket(tickets_dir, "0.18.0-W17-030", title="First")

    args1 = _make_args(from_ticket_id="0.18.0-W17-030", direction="to-child")
    assert _execute_auto_handoff(args1) == 0

    # 以不同 direction 再跑一次，驗證檔案被覆寫
    args2 = _make_args(from_ticket_id="0.18.0-W17-030", direction="to-parent")
    assert _execute_auto_handoff(args2) == 0

    data = json.loads(
        (root / ".claude" / "handoff" / "pending" / "0.18.0-W17-030.json").read_text()
    )
    assert data["direction"] == "to-parent"
