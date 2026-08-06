"""
resume.py 消費 --next 產生的 target_ticket_id handoff 測試（0.2.1-W3-306 第二輪）。

PM 驗收發現：resume.py 尚有三處以來源票為對象，未讀 target_ticket_id：
1. _handle_completed_ticket_redirect：direction="context-refresh" 無後綴，
   extract_direction_target_id 恆為 None，來源已 completed 時不 redirect，
   使用者落在已完成的來源票。
2. _execute_list：顯示來源票 ID / title，應顯示 target。
3. _apply_runqueue_ordering：排序依來源票 priority，應依 target priority。

判準：此三處問的都是「這個 handoff 指向的工作是否還需要做／該做哪張」，屬 target 類。
"""

import argparse
import os
import tempfile
from pathlib import Path

import pytest
import yaml

from ticket_system.commands.handoff import execute as handoff_execute
from ticket_system.commands.resume import (
    _execute_list,
    _handle_completed_ticket_redirect,
    load_handoff_file,
)
from ticket_system.lib.constants import (
    STATUS_COMPLETED,
    STATUS_IN_PROGRESS,
    STATUS_PENDING,
)


@pytest.fixture
def temp_project():
    """建立臨時專案根目錄與 ticket 檔案（與 test_handoff_next.py 同構）。"""
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


def _create_ticket(
    tickets_dir: Path,
    ticket_id: str,
    *,
    status: str = STATUS_IN_PROGRESS,
    title: str = "Sample Ticket",
    what: str = "sample what",
    priority: str = "P2",
) -> None:
    data = {
        "id": ticket_id,
        "title": title,
        "status": status,
        "priority": priority,
        "type": "IMP",
        "what": what,
        "created": "2026-04-20",
    }
    fm = yaml.dump(data, allow_unicode=True, sort_keys=False)
    (tickets_dir / f"{ticket_id}.md").write_text(
        f"---\n{fm}---\n# {title}\n", encoding="utf-8"
    )


def _make_next_args(**overrides) -> argparse.Namespace:
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
        list=False,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def _build_next_handoff(root, tickets_dir, source_id, target_id, *, source_status, target_status):
    """透過 handoff --next 建立真實 handoff JSON（走完整寫入路徑）。"""
    _create_ticket(tickets_dir, source_id, status=source_status, title="來源票標題")
    _create_ticket(tickets_dir, target_id, status=target_status, title="Target 票標題", priority="P0")

    args = _make_next_args(next=target_id, from_ticket_id=source_id)
    rc = handoff_execute(args)
    assert rc == 0
    return load_handoff_file(source_id)


class TestRedirectUsesTarget:
    """RED 1：來源已 completed 的 context-refresh + target_ticket_id 應 redirect 至 target。"""

    def test_redirect_to_target_when_source_completed(self, temp_project, capsys):
        root, tickets_dir = temp_project
        source_id = "0.18.0-W17-101"
        target_id = "0.18.0-W17-102"
        handoff = _build_next_handoff(
            root, tickets_dir, source_id, target_id,
            source_status=STATUS_COMPLETED, target_status=STATUS_PENDING,
        )

        result = _handle_completed_ticket_redirect(source_id, handoff)

        assert result == 0, "來源已 completed 且有明確 target 時應 redirect（回傳 0）"
        out = capsys.readouterr().out
        assert target_id in out
        assert f"ticket resume {target_id}" in out

    def test_no_redirect_when_source_not_completed(self, temp_project):
        root, tickets_dir = temp_project
        source_id = "0.18.0-W17-103"
        target_id = "0.18.0-W17-104"
        handoff = _build_next_handoff(
            root, tickets_dir, source_id, target_id,
            source_status=STATUS_IN_PROGRESS, target_status=STATUS_PENDING,
        )

        result = _handle_completed_ticket_redirect(source_id, handoff)

        assert result is None, "來源未 completed 時不應 redirect，應 fall through 正常流程"


class TestListDisplaysTarget:
    """RED 2：--list 應顯示 target 的 ID 與 title，而非來源票。"""

    def test_list_shows_target_id_and_title(self, temp_project, capsys):
        root, tickets_dir = temp_project
        source_id = "0.18.0-W17-201"
        target_id = "0.18.0-W17-202"
        _build_next_handoff(
            root, tickets_dir, source_id, target_id,
            source_status=STATUS_COMPLETED, target_status=STATUS_PENDING,
        )
        capsys.readouterr()  # 清空建立 handoff 過程中的輸出（含來源票檔名）

        rc = _execute_list()
        assert rc == 0

        out = capsys.readouterr().out
        assert target_id in out, "清單應顯示 target ticket id"
        assert "Target 票標題" in out, "清單應顯示 target 的 title，非來源票 title"
        assert source_id not in out, "清單不應顯示已完成的來源票 id"


class TestSortByTargetPriority:
    """RED 3：排序應依 target 的 priority，而非來源票的 priority。"""

    def test_sort_uses_target_priority_not_source(self, temp_project, capsys):
        root, tickets_dir = temp_project

        # Handoff A：來源 P2（低優先），target P0（高優先）
        source_a = "0.18.0-W17-301"
        target_a = "0.18.0-W17-302"
        _create_ticket(tickets_dir, source_a, status=STATUS_COMPLETED, title="A 來源", priority="P2")
        _create_ticket(tickets_dir, target_a, status=STATUS_PENDING, title="A Target", priority="P0")
        args_a = _make_next_args(next=target_a, from_ticket_id=source_a)
        assert handoff_execute(args_a) == 0

        # Handoff B：來源 P0（高優先，但已 completed 非考量對象），target P2（低優先）
        source_b = "0.18.0-W17-303"
        target_b = "0.18.0-W17-304"
        _create_ticket(tickets_dir, source_b, status=STATUS_COMPLETED, title="B 來源", priority="P0")
        _create_ticket(tickets_dir, target_b, status=STATUS_PENDING, title="B Target", priority="P2")
        args_b = _make_next_args(next=target_b, from_ticket_id=source_b)
        assert handoff_execute(args_b) == 0

        rc = _execute_list()
        assert rc == 0
        out = capsys.readouterr().out

        # target_a（P0）應排在 target_b（P2）之前——若誤用來源 priority，
        # source_b（P0）會使 B 排前面，此斷言即會失敗。
        pos_a = out.find(target_a)
        pos_b = out.find(target_b)
        assert pos_a != -1 and pos_b != -1
        assert pos_a < pos_b, "target priority 較高者應排在前面"
