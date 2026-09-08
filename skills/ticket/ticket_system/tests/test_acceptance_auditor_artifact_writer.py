"""0.2.1-W3-1330 — acceptance_auditor.run_audit 補齊 artifact 寫入者/時間欄位。

3-F 共用原則：complete/reclaim/dispatch-readiness 等前置檢查衡量的都是
執行者可寫的 artifact，CLI 應輸出寫入者與時間。Step 1 結構完整性檢查的
13 個必填欄位皆屬同一張 ticket md 的 frontmatter，本次於 artifact 層級
（非逐欄位）補上 ``artifact_who`` / ``artifact_updated``，資料直接取自
已載入的 frontmatter（``who.current`` / ``updated``），zero-cost。

覆蓋 cases：
1. who.current 與 updated 皆存在 → AuditReport 正確帶出兩欄位
2. who 缺失（None）→ artifact_who 降級為空字串，不拋例外
3. updated 缺失 → artifact_updated 降級為空字串
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ticket_system.lib import ticket_loader


@pytest.fixture
def tmp_ticket_dir(tmp_path: Path) -> Path:
    d = tmp_path / "tickets"
    d.mkdir()
    return d


@pytest.fixture
def patch_paths(tmp_ticket_dir: Path, monkeypatch):
    def _fake_get_ticket_path(version: str, ticket_id: str) -> Path:
        return tmp_ticket_dir / f"{ticket_id}.md"

    def _fake_load_ticket(version: str, ticket_id: str):
        from ticket_system.lib.parser import parse_frontmatter

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

    from ticket_system.lib import acceptance_auditor as aa_mod

    monkeypatch.setattr(aa_mod, "load_ticket", _fake_load_ticket)
    monkeypatch.setattr(
        aa_mod,
        "resolve_version",
        lambda v: v or "0.0.0",
    )

    # run_audit 內部另以 `from .paths import get_ticket_path` 動態載入取 body；
    # patch 該模組的 get_ticket_path 使其解析到同一暫存路徑。
    from ticket_system.lib import paths as paths_mod

    monkeypatch.setattr(paths_mod, "get_ticket_path", _fake_get_ticket_path)


def _write_ticket(path: Path, tid: str, *, who_current: str, updated: str) -> None:
    who_block = f"who:\n  current: {who_current}\n" if who_current else "who:\n  current: ''\n"
    updated_line = f"updated: '{updated}'\n" if updated else "updated: ''\n"
    fm = (
        "---\n"
        f"id: {tid}\n"
        "title: test\n"
        "type: IMP\n"
        "status: in_progress\n"
        "version: 0.0.0\n"
        "wave: 1\n"
        "priority: P2\n"
        "what: test what\n"
        "why: test why\n"
        "assigned: true\n"
        "started_at: '2026-09-08T00:00:00'\n"
        "acceptance:\n"
        "- '[x] done'\n"
        f"{who_block}"
        f"{updated_line}"
        "children: []\n"
        "blockedBy: []\n"
        "spawned_tickets: []\n"
        "---\n\n"
        "# Execution Log\n"
    )
    path.write_text(fm, encoding="utf-8")


def test_run_audit_populates_artifact_who_and_updated(patch_paths, tmp_ticket_dir):
    from ticket_system.lib.acceptance_auditor import run_audit

    tid = "0.0.0-W1-001"
    _write_ticket(
        tmp_ticket_dir / f"{tid}.md",
        tid,
        who_current="thyme-python-developer",
        updated="2026-09-08",
    )

    report = run_audit(tid, version="0.0.0")

    assert report.artifact_who == "thyme-python-developer"
    assert report.artifact_updated == "2026-09-08"


def test_run_audit_degrades_gracefully_when_who_missing(patch_paths, tmp_ticket_dir):
    from ticket_system.lib.acceptance_auditor import run_audit

    tid = "0.0.0-W1-002"
    _write_ticket(
        tmp_ticket_dir / f"{tid}.md",
        tid,
        who_current="",
        updated="2026-09-08",
    )

    report = run_audit(tid, version="0.0.0")

    assert report.artifact_who == ""
    assert report.artifact_updated == "2026-09-08"


def test_run_audit_degrades_gracefully_when_updated_missing(patch_paths, tmp_ticket_dir):
    from ticket_system.lib.acceptance_auditor import run_audit

    tid = "0.0.0-W1-003"
    _write_ticket(
        tmp_ticket_dir / f"{tid}.md",
        tid,
        who_current="thyme-python-developer",
        updated="",
    )

    report = run_audit(tid, version="0.0.0")

    assert report.artifact_who == "thyme-python-developer"
    assert report.artifact_updated == ""
