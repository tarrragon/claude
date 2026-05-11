"""
Handoff --next 顯式 target_ticket_id 模式測試（0.18.0-W17-164 / L2-A）。

覆蓋範圍：
- handoff JSON schema 新增選填 target_ticket_id 欄位
- handoff --next <target-id> CLI flag（與 --auto 互斥）
- 讀取端優先讀 target_ticket_id，無則 fallback 至 direction 邏輯
- handoff_utils.resolve_target(record) helper
- 向後相容：既有 JSON 不含 target_ticket_id 仍可正確解析

來源：W17-162 ANA L2-A 設計。
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
from ticket_system.lib.handoff_utils import resolve_target


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
        auto=False,
        from_ticket_id=None,
        direction=None,
        next=None,
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
        from_worklog=False,
        worklog_path=None,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


# ----------------------------------------------------------------------------
# resolve_target helper
# ----------------------------------------------------------------------------

class TestResolveTarget:
    """handoff_utils.resolve_target() 統一解析 target ticket id。"""

    def test_prefers_target_ticket_id_field(self):
        """記錄含 target_ticket_id 時直接回傳。"""
        record = {
            "ticket_id": "0.18.0-W17-001",
            "direction": "context-refresh",
            "target_ticket_id": "0.18.0-W17-002",
        }
        assert resolve_target(record) == "0.18.0-W17-002"

    def test_fallback_to_direction_target_when_no_field(self):
        """無 target_ticket_id 時 fallback 至 direction 後綴。"""
        record = {
            "ticket_id": "0.18.0-W17-001",
            "direction": "to-sibling:0.18.0-W17-003",
        }
        assert resolve_target(record) == "0.18.0-W17-003"

    def test_returns_none_when_no_target_anywhere(self):
        """無 target_ticket_id 且 direction 無後綴 → None。"""
        record = {
            "ticket_id": "0.18.0-W17-001",
            "direction": "context-refresh",
        }
        assert resolve_target(record) is None

    def test_target_ticket_id_overrides_direction_target(self):
        """target_ticket_id 優先於 direction 後綴（不一致時取顯式欄位）。"""
        record = {
            "ticket_id": "0.18.0-W17-001",
            "direction": "to-sibling:0.18.0-W17-OLD",
            "target_ticket_id": "0.18.0-W17-NEW",
        }
        assert resolve_target(record) == "0.18.0-W17-NEW"

    def test_empty_target_ticket_id_falls_back(self):
        """target_ticket_id 為空字串時視為未提供，fallback。"""
        record = {
            "ticket_id": "0.18.0-W17-001",
            "direction": "to-child:0.18.0-W17-002",
            "target_ticket_id": "",
        }
        assert resolve_target(record) == "0.18.0-W17-002"

    def test_handles_missing_direction(self):
        """無 direction 也無 target_ticket_id → None（防禦）。"""
        record = {"ticket_id": "0.18.0-W17-001"}
        assert resolve_target(record) is None


# ----------------------------------------------------------------------------
# --next CLI flag 與 --auto 互斥
# ----------------------------------------------------------------------------

class TestNextAutoMutex:
    """--next 與 --auto 互斥驗證。"""

    def test_next_with_auto_returns_error(self, temp_project, capsys):
        """同時指定 --next 與 --auto 應錯誤退出。"""
        root, tickets_dir = temp_project
        _create_ticket(tickets_dir, "0.18.0-W17-001")

        args = _make_args(
            auto=True,
            next="0.18.0-W17-002",
            from_ticket_id="0.18.0-W17-001",
            direction="context-refresh",
        )
        rc = execute(args)
        assert rc == 1
        err = capsys.readouterr().err
        assert "--next" in err and "--auto" in err


# ----------------------------------------------------------------------------
# --next 模式生成 handoff JSON 含 target_ticket_id
# ----------------------------------------------------------------------------

class TestNextWritesTargetTicketId:
    """--next 模式應寫入 target_ticket_id 欄位至 handoff JSON。"""

    def test_next_writes_target_ticket_id_field(self, temp_project):
        """handoff --next <target> 寫入 target_ticket_id。"""
        root, tickets_dir = temp_project
        _create_ticket(tickets_dir, "0.18.0-W17-001", status=STATUS_IN_PROGRESS)

        args = _make_args(
            next="0.18.0-W17-002",
            from_ticket_id="0.18.0-W17-001",
        )
        rc = execute(args)
        assert rc == 0

        out_file = root / ".claude" / "handoff" / "pending" / "0.18.0-W17-001.json"
        assert out_file.exists()
        data = json.loads(out_file.read_text(encoding="utf-8"))
        assert data.get("target_ticket_id") == "0.18.0-W17-002"
        # 必填欄位仍存在
        assert data["ticket_id"] == "0.18.0-W17-001"
        assert "direction" in data
        assert "timestamp" in data

    def test_next_requires_from_ticket_id(self, temp_project, capsys):
        """--next 缺 --from-ticket-id 應錯誤退出。"""
        args = _make_args(next="0.18.0-W17-002")
        rc = execute(args)
        assert rc == 1
        assert "--from-ticket-id" in capsys.readouterr().err


# ----------------------------------------------------------------------------
# 向後相容：既有 JSON 不含 target_ticket_id 仍可解析
# ----------------------------------------------------------------------------

class TestBackwardCompatibility:
    """既有 handoff JSON（無 target_ticket_id）仍可正確解析。"""

    def test_legacy_json_without_target_ticket_id_resolves_via_direction(self):
        """舊 JSON 透過 direction 解析 target，與新欄位向後相容。"""
        legacy_record = {
            "ticket_id": "0.18.0-W10-001",
            "direction": "to-child:0.18.0-W10-002",
            "from_status": "completed",
            "timestamp": "2026-01-01T00:00:00",
            # 注意：無 target_ticket_id 欄位
        }
        assert resolve_target(legacy_record) == "0.18.0-W10-002"

    def test_legacy_context_refresh_resolves_to_none(self):
        """舊 context-refresh 無 target_ticket_id → None（與既有行為一致）。"""
        legacy_record = {
            "ticket_id": "0.18.0-W10-001",
            "direction": "context-refresh",
            "from_status": "in_progress",
            "timestamp": "2026-01-01T00:00:00",
        }
        assert resolve_target(legacy_record) is None
