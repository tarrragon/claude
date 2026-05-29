"""W3-082 — release() 狀態語意測試。

驗證 release() 依 blockedBy 是否為空決定目標狀態：
- blockedBy=[]    → status == pending（退回休眠態，非 blocked）
- blockedBy=["X"] → status == blocked（確實被其他 ticket 擋著）

並驗證 stdout 狀態訊息反映實際目標狀態（取代先前寫死的「狀態: 被阻塞」）。

路徑重導沿用 test_lifecycle_race.py 的 patch_ticket_paths fixture 模式：
lifecycle.py 透過 `from ... import` 綁定名稱，需對 ticket_loader、lifecycle、
ticket_ops 三個命名空間都 patch。
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

import pytest

from ticket_system.lib import parser, ticket_loader
from ticket_system.lib.parser import parse_frontmatter


# --- Fixtures ----------------------------------------------------------------


@pytest.fixture
def tmp_ticket_dir(tmp_path: Path) -> Path:
    d = tmp_path / "tickets"
    d.mkdir()
    return d


def _write_in_progress_ticket(path: Path, tid: str, blocked_by: list) -> None:
    """最小合法 ticket，status=in_progress，可被 release。"""
    blocked_repr = (
        "[]" if not blocked_by else "[" + ", ".join(blocked_by) + "]"
    )
    lines = [
        "---",
        f"id: {tid}",
        "title: release target",
        "type: IMP",
        "status: in_progress",
        "assigned: true",
        "started_at: '2026-05-29T10:00:00'",
        "acceptance: []",
        "tdd_phase: ''",
        "children: []",
        f"blockedBy: {blocked_repr}",
        "---",
        "",
        "body",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


@pytest.fixture
def patch_ticket_paths(tmp_ticket_dir: Path, monkeypatch):
    """重導 lifecycle 內部的 get_ticket_path / load_ticket 至 tmp dir。"""
    from ticket_system.commands import lifecycle as lifecycle_mod

    def _fake_get_ticket_path(version: str, ticket_id: str) -> Path:
        return tmp_ticket_dir / f"{ticket_id}.md"

    def _fake_load_ticket(version: str, ticket_id: str):
        path = tmp_ticket_dir / f"{ticket_id}.md"
        if not path.exists():
            return None
        try:
            fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not fm:
            return None
        fm["_body"] = body
        fm["_path"] = str(path)
        return fm

    monkeypatch.setattr(ticket_loader, "get_ticket_path", _fake_get_ticket_path)
    monkeypatch.setattr(ticket_loader, "load_ticket", _fake_load_ticket)
    monkeypatch.setattr(lifecycle_mod, "get_ticket_path", _fake_get_ticket_path)
    monkeypatch.setattr(lifecycle_mod, "load_ticket", _fake_load_ticket)
    from ticket_system.lib import ticket_ops
    monkeypatch.setattr(ticket_ops, "load_ticket", _fake_load_ticket)
    monkeypatch.setattr(ticket_ops, "get_ticket_path", _fake_get_ticket_path)


@pytest.fixture(autouse=True)
def _clear_cache():
    """每個 test 清 parser cache，避免跨 case 污染。"""
    try:
        parser._ticket_cache.clear()
    except Exception:
        pass
    yield


def _release(tmp_ticket_dir: Path, tid: str):
    from ticket_system.commands.lifecycle import TicketLifecycle

    rc = TicketLifecycle("0.0.0").release(tid)
    content = (tmp_ticket_dir / f"{tid}.md").read_text(encoding="utf-8")
    fm, _ = parse_frontmatter(content)
    return rc, fm


# --- Tests -------------------------------------------------------------------


class TestReleaseStatusSemantics:
    """release() blockedBy 兩分支與 stdout 訊息。"""

    def test_empty_blocked_by_returns_pending(
        self, tmp_ticket_dir, patch_ticket_paths
    ):
        """分支 A：blockedBy=[] 的 in_progress → release → pending。"""
        tid = "0.0.0-W0-RELPENDING"
        _write_in_progress_ticket(
            tmp_ticket_dir / f"{tid}.md", tid, blocked_by=[]
        )

        rc, fm = _release(tmp_ticket_dir, tid)

        assert rc == 0
        assert fm.get("status") == "pending", (
            f"blockedBy 為空時應退回 pending，實際={fm.get('status')!r}"
        )
        assert fm.get("assigned") is False
        assert fm.get("started_at") in (None, "null", "")

    def test_nonempty_blocked_by_returns_blocked(
        self, tmp_ticket_dir, patch_ticket_paths
    ):
        """分支 B：blockedBy=["X"] 的 in_progress → release → blocked。"""
        tid = "0.0.0-W0-RELBLOCKED"
        _write_in_progress_ticket(
            tmp_ticket_dir / f"{tid}.md", tid, blocked_by=["0.0.0-W0-DEP"]
        )

        rc, fm = _release(tmp_ticket_dir, tid)

        assert rc == 0
        assert fm.get("status") == "blocked", (
            f"blockedBy 非空時應設 blocked，實際={fm.get('status')!r}"
        )
        assert fm.get("assigned") is False

    def test_stdout_reflects_pending_target(
        self, tmp_ticket_dir, patch_ticket_paths, capsys
    ):
        """blockedBy 空 → stdout 顯示「待處理」，非寫死的「被阻塞」。"""
        tid = "0.0.0-W0-RELOUTPENDING"
        _write_in_progress_ticket(
            tmp_ticket_dir / f"{tid}.md", tid, blocked_by=[]
        )

        TicketLifecycle = __import__(
            "ticket_system.commands.lifecycle",
            fromlist=["TicketLifecycle"],
        ).TicketLifecycle
        TicketLifecycle("0.0.0").release(tid)

        out = capsys.readouterr().out
        assert "待處理" in out, f"stdout 應反映 pending 目標狀態，實際輸出：{out!r}"
        assert "被阻塞" not in out

    def test_stdout_reflects_blocked_target(
        self, tmp_ticket_dir, patch_ticket_paths, capsys
    ):
        """blockedBy 非空 → stdout 顯示「被阻塞」。"""
        tid = "0.0.0-W0-RELOUTBLOCKED"
        _write_in_progress_ticket(
            tmp_ticket_dir / f"{tid}.md", tid, blocked_by=["0.0.0-W0-DEP"]
        )

        from ticket_system.commands.lifecycle import TicketLifecycle

        TicketLifecycle("0.0.0").release(tid)

        out = capsys.readouterr().out
        assert "被阻塞" in out, f"stdout 應反映 blocked 目標狀態，實際輸出：{out!r}"
