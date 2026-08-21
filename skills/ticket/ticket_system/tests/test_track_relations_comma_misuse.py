"""0.2.1-W3-849 — set-blocked-by / set-related-to 逗號分隔誤用錯誤訊息回歸測試。

驗證：
1. 逗號分隔且各段皆為合法 ID 格式時，錯誤訊息指出分隔符應為空格並附正確指令範例。
2. 真正不存在的 ID（非逗號分隔）維持原本的 TICKET_NOT_FOUND 訊息，兩種情況可區分。
3. set-related-to 與 set-blocked-by 共用同一偵測邏輯（同型缺口一併修復）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ticket_system.lib import ticket_loader
from ticket_system.lib.parser import parse_frontmatter


class _Args:
    """簡易 argparse.Namespace 替身。"""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


@pytest.fixture
def tmp_ticket_dir(tmp_path: Path) -> Path:
    d = tmp_path / "tickets"
    d.mkdir()
    return d


def _write_ticket(path: Path, tid: str) -> None:
    lines = [
        "---",
        f"id: {tid}",
        "title: comma misuse target",
        "type: IMP",
        "status: pending",
        "assigned: false",
        "started_at: null",
        "tdd_phase: phase1",
        "children: []",
        "blockedBy: []",
        "relatedTo: []",
        "acceptance: []",
        "spawned_tickets: []",
        "---",
        "",
        "body",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


@pytest.fixture
def patch_ticket_paths(tmp_ticket_dir: Path, monkeypatch):
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

    from ticket_system.lib import ticket_ops
    monkeypatch.setattr(ticket_ops, "load_ticket", _fake_load_ticket)
    monkeypatch.setattr(ticket_ops, "get_ticket_path", _fake_get_ticket_path)

    from ticket_system.commands import track_relations as tr_mod
    monkeypatch.setattr(tr_mod, "get_ticket_path", _fake_get_ticket_path)
    monkeypatch.setattr(tr_mod, "load_ticket", _fake_load_ticket)

    return tr_mod


class TestSetBlockedByCommaMisuse:
    """set-blocked-by 逗號分隔誤用訊息。"""

    def test_comma_separated_valid_ids_shows_delimiter_hint(
        self, tmp_ticket_dir, patch_ticket_paths, capsys
    ):
        tr_mod = patch_ticket_paths
        _write_ticket(tmp_ticket_dir / "0.2.1-W3-001.md", "0.2.1-W3-001")
        _write_ticket(tmp_ticket_dir / "0.2.1-W3-002.md", "0.2.1-W3-002")
        _write_ticket(tmp_ticket_dir / "0.2.1-W3-003.md", "0.2.1-W3-003")

        ns = _Args(
            ticket_id="0.2.1-W3-001",
            value="0.2.1-W3-002,0.2.1-W3-003",
            add=False,
            remove=False,
        )
        exit_code = tr_mod.execute_set_blocked_by(ns, "0.2.1")
        output = capsys.readouterr().out

        assert exit_code == 1
        assert "空格" in output
        assert "0.2.1-W3-002 0.2.1-W3-003" in output

    def test_real_missing_id_shows_generic_not_found(
        self, tmp_ticket_dir, patch_ticket_paths, capsys
    ):
        tr_mod = patch_ticket_paths
        _write_ticket(tmp_ticket_dir / "0.2.1-W3-001.md", "0.2.1-W3-001")

        ns = _Args(
            ticket_id="0.2.1-W3-001",
            value="0.2.1-W3-999",
            add=False,
            remove=False,
        )
        exit_code = tr_mod.execute_set_blocked_by(ns, "0.2.1")
        output = capsys.readouterr().out

        assert exit_code == 1
        assert "找不到 Ticket 0.2.1-W3-999" in output
        # 兩種情況可區分：真正不存在 ID 不應觸發分隔符提示
        assert "空格" not in output


class TestSetRelatedToCommaMisuse:
    """set-related-to 與 set-blocked-by 共用同一偵測邏輯，須一併修復。"""

    def test_comma_separated_valid_ids_shows_delimiter_hint(
        self, tmp_ticket_dir, patch_ticket_paths, capsys
    ):
        tr_mod = patch_ticket_paths
        _write_ticket(tmp_ticket_dir / "0.2.1-W3-001.md", "0.2.1-W3-001")
        _write_ticket(tmp_ticket_dir / "0.2.1-W3-002.md", "0.2.1-W3-002")
        _write_ticket(tmp_ticket_dir / "0.2.1-W3-003.md", "0.2.1-W3-003")

        ns = _Args(
            ticket_id="0.2.1-W3-001",
            value="0.2.1-W3-002,0.2.1-W3-003",
            add=False,
            remove=False,
        )
        exit_code = tr_mod.execute_set_related_to(ns, "0.2.1")
        output = capsys.readouterr().out

        assert exit_code == 1
        assert "空格" in output
        assert "0.2.1-W3-002 0.2.1-W3-003" in output

    def test_real_missing_id_shows_generic_not_found(
        self, tmp_ticket_dir, patch_ticket_paths, capsys
    ):
        tr_mod = patch_ticket_paths
        _write_ticket(tmp_ticket_dir / "0.2.1-W3-001.md", "0.2.1-W3-001")

        ns = _Args(
            ticket_id="0.2.1-W3-001",
            value="0.2.1-W3-999",
            add=False,
            remove=False,
        )
        exit_code = tr_mod.execute_set_related_to(ns, "0.2.1")
        output = capsys.readouterr().out

        assert exit_code == 1
        assert "找不到 Ticket 0.2.1-W3-999" in output
        assert "空格" not in output
