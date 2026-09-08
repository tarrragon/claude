"""reclaim --confirm 落地把鑑識報告 append-log 落票（Round 3 finding 3-F
共用原則，項目 (5)）。

reclaim --confirm 成功後，鑑識報告原僅印在終端機，事後無法對帳（3-F F3：
判準文件與實作落差的根因之一即鑑識結果不落票）。`lease.reclaim_ticket`
新增 `landing_report_hook` 注入點（lib 層維持不 import commands 的層級
邊界，見 lease.py 檔頭說明），CLI 層（`track._execute_reclaim`）注入呼叫
`track_acceptance.execute_append_log` 的 hook，把報告 append 進票面
Solution 章節。
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ticket_system.commands import track_acceptance
from ticket_system.commands.track import _execute_reclaim
from ticket_system.lib import lease


def _write_in_progress_ticket(path: Path, tid: str) -> None:
    """最小合法 ticket，status=in_progress，where.files 供 ghost 鑑識比對。"""
    lines = [
        "---",
        f"id: {tid}",
        "title: reclaim target",
        "type: IMP",
        "status: in_progress",
        "assigned: true",
        "started_at: '2026-05-29T10:00:00'",
        "acceptance: []",
        "tdd_phase: ''",
        "children: []",
        "blockedBy: []",
        "where:",
        "  files:",
        "  - lib/foo.dart",
        "---",
        "",
        "## Solution",
        "",
        "placeholder",
        "",
        "## Exit Status",
        "```yaml",
        "exit_status: success",
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


@pytest.fixture
def tmp_ticket_dir(tmp_path: Path) -> Path:
    d = tmp_path / "tickets"
    d.mkdir()
    return d


@pytest.fixture
def patch_reclaim_and_append_log_paths(tmp_ticket_dir, monkeypatch):
    """重導 `lease` 與 `track_acceptance` 兩模組內部的 get_ticket_path /
    load_ticket 至同一 tmp dir，使 landing report hook 的 append-log
    落地在測試可觀察的檔案上。兩模組各自於 import 時綁定了獨立的名稱
    複本（`from ... import load_ticket` 非模組屬性存取），故須逐一重導，
    僅重導共用的 `ticket_loader`/`ticket_ops` 模組本身不足以覆蓋。
    """
    from ticket_system.lib.parser import parse_frontmatter
    from ticket_system.lib import parser as parser_mod
    from ticket_system.lib import ticket_ops, ticket_loader

    def _fake_get_ticket_path(version: str, ticket_id: str) -> Path:
        return tmp_ticket_dir / f"{ticket_id}.md"

    def _fake_load_ticket(version: str, ticket_id: str):
        path = tmp_ticket_dir / f"{ticket_id}.md"
        if not path.exists():
            return None
        fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        if not fm:
            return None
        fm["_body"] = body
        fm["_path"] = str(path)
        return fm

    for mod in (lease, track_acceptance, ticket_loader, ticket_ops):
        monkeypatch.setattr(mod, "get_ticket_path", _fake_get_ticket_path, raising=False)
        monkeypatch.setattr(mod, "load_ticket", _fake_load_ticket, raising=False)

    yield

    try:
        parser_mod._ticket_cache.clear()
    except Exception:
        pass


@pytest.fixture
def real_pm_registry(tmp_path, monkeypatch):
    """載入真實 `.claude/lib/pm_registry` 模組，registry 路徑重導至
    tmp_path（不預先寫入，registry 未追蹤此票 lease 仍屬合法 reclaimable
    路徑，見 `check_reclaimable` owner is None 分支）。"""
    pm_registry = lease._load_pm_registry()
    if pm_registry is None:
        pytest.skip("找不到 .claude/lib/pm_registry.py（開發環境結構異常）")
    registry_file = tmp_path / "pm-registry.json"
    lock_file = tmp_path / "pm-registry.lock"
    monkeypatch.setattr(
        pm_registry, "get_registry_paths", lambda cwd=None: (registry_file, lock_file)
    )
    return pm_registry, registry_file, lock_file


def _md_text(tmp_ticket_dir: Path, tid: str) -> str:
    return (tmp_ticket_dir / f"{tid}.md").read_text(encoding="utf-8")


class TestReclaimLandingReport:
    def test_confirm_success_appends_ghost_report_to_solution(
        self, tmp_ticket_dir, patch_reclaim_and_append_log_paths, real_pm_registry, monkeypatch
    ):
        tid = "0.0.0-W0-LANDING"
        _write_in_progress_ticket(tmp_ticket_dir / f"{tid}.md", tid)
        monkeypatch.setattr(lease, "_run_git_lines", lambda args, cwd=None: [])
        monkeypatch.setenv("HOOK_LOGS_DIR", str(tmp_ticket_dir.parent / "hook-logs"))

        args = argparse.Namespace(ticket_id=tid, confirm=True)
        rc = _execute_reclaim(args, "0.0.0")

        assert rc == 0
        text = _md_text(tmp_ticket_dir, tid)
        assert "Reclaim 落地鑑識報告" in text
        assert "鑑識通過，允許 reclaim" in text

    def test_dry_run_does_not_append_report(
        self, tmp_ticket_dir, patch_reclaim_and_append_log_paths, real_pm_registry, monkeypatch
    ):
        """dry-run（無 --confirm）不落地寫入，鑑識報告只印終端機，票面
        不變（既有行為，回歸防護）。"""
        tid = "0.0.0-W0-DRYRUN"
        _write_in_progress_ticket(tmp_ticket_dir / f"{tid}.md", tid)
        monkeypatch.setattr(lease, "_run_git_lines", lambda args, cwd=None: [])

        args = argparse.Namespace(ticket_id=tid, confirm=False)
        rc = _execute_reclaim(args, "0.0.0")

        assert rc == 0
        text = _md_text(tmp_ticket_dir, tid)
        assert "Reclaim 落地鑑識報告" not in text

    def test_rejected_by_ghost_signal_does_not_append_report(
        self, tmp_ticket_dir, patch_reclaim_and_append_log_paths, real_pm_registry, monkeypatch
    ):
        """三查未通過拒絕 reclaim 時不落地寫入。"""
        tid = "0.0.0-W0-REJECTED"
        _write_in_progress_ticket(tmp_ticket_dir / f"{tid}.md", tid)
        monkeypatch.setattr(
            lease, "_run_git_lines",
            lambda args, cwd=None: ([" M lib/foo.dart"] if args[0] == "status" else []),
        )

        args = argparse.Namespace(ticket_id=tid, confirm=True)
        rc = _execute_reclaim(args, "0.0.0")

        assert rc == 1
        text = _md_text(tmp_ticket_dir, tid)
        assert "Reclaim 落地鑑識報告" not in text

    def test_hook_failure_does_not_fail_reclaim(
        self, tmp_ticket_dir, patch_reclaim_and_append_log_paths, real_pm_registry, monkeypatch
    ):
        """landing_report_hook 失敗（append-log 內部拋例外）不影響 reclaim
        本身已完成的狀態轉換，僅 stderr 記錄（見 lease.reclaim_ticket
        docstring：落票為稽核強化，非 reclaim 成功的前提）。"""
        tid = "0.0.0-W0-HOOKFAIL"
        _write_in_progress_ticket(tmp_ticket_dir / f"{tid}.md", tid)
        monkeypatch.setattr(lease, "_run_git_lines", lambda args, cwd=None: [])

        def _raise(*args, **kwargs):
            raise RuntimeError("append-log 模擬失敗")

        rc = lease.reclaim_ticket(
            "0.0.0", tid, confirm=True, now=datetime.now(timezone.utc),
            landing_report_hook=_raise,
        )

        assert rc == 0
        from ticket_system.lib.parser import parse_frontmatter
        fm, _body = parse_frontmatter(_md_text(tmp_ticket_dir, tid))
        assert fm.get("status") == "pending"
