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


def _write_ticket_with_relations(
    path: Path, tid: str, *, parent_id=None, children=None
) -> None:
    children = children or []
    lines = [
        "---",
        f"id: {tid}",
        "title: set-parent target",
        "type: IMP",
        "status: pending",
        "assigned: false",
        "started_at: null",
        "tdd_phase: phase1",
        f"parent_id: {parent_id if parent_id else 'null'}",
        "children: [" + ", ".join(children) + "]",
        "blockedBy: []",
        "relatedTo: []",
        "acceptance: []",
        "spawned_tickets: []",
        "---",
        "",
        "body",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


class TestSetParentBidirectionalConsistency:
    """set-parent 修正 parent_id 並同步上游 children 的雙向一致性回歸測試。"""

    def test_clear_removes_child_from_old_parent_children(
        self, tmp_ticket_dir, patch_ticket_paths, capsys
    ):
        tr_mod = patch_ticket_paths
        _write_ticket_with_relations(
            tmp_ticket_dir / "0.2.1-W3-010.md", "0.2.1-W3-010", children=["0.2.1-W3-011"]
        )
        _write_ticket_with_relations(
            tmp_ticket_dir / "0.2.1-W3-011.md", "0.2.1-W3-011", parent_id="0.2.1-W3-010"
        )

        ns = _Args(child_id="0.2.1-W3-011", new_parent_id=None, clear=True)
        exit_code = tr_mod.execute_set_parent(ns, "0.2.1")
        assert exit_code == 0

        child = tr_mod.load_ticket("0.2.1", "0.2.1-W3-011")
        parent = tr_mod.load_ticket("0.2.1", "0.2.1-W3-010")
        assert child["parent_id"] is None
        assert "0.2.1-W3-011" not in parent["children"]

    def test_change_parent_syncs_both_old_and_new_children(
        self, tmp_ticket_dir, patch_ticket_paths
    ):
        tr_mod = patch_ticket_paths
        _write_ticket_with_relations(
            tmp_ticket_dir / "0.2.1-W3-020.md", "0.2.1-W3-020", children=["0.2.1-W3-022"]
        )
        _write_ticket_with_relations(tmp_ticket_dir / "0.2.1-W3-021.md", "0.2.1-W3-021")
        _write_ticket_with_relations(
            tmp_ticket_dir / "0.2.1-W3-022.md", "0.2.1-W3-022", parent_id="0.2.1-W3-020"
        )

        ns = _Args(child_id="0.2.1-W3-022", new_parent_id="0.2.1-W3-021", clear=False)
        exit_code = tr_mod.execute_set_parent(ns, "0.2.1")
        assert exit_code == 0

        child = tr_mod.load_ticket("0.2.1", "0.2.1-W3-022")
        old_parent = tr_mod.load_ticket("0.2.1", "0.2.1-W3-020")
        new_parent = tr_mod.load_ticket("0.2.1", "0.2.1-W3-021")

        # 不留懸空引用：新值生效、舊上游不殘留、新上游確實收到
        assert child["parent_id"] == "0.2.1-W3-021"
        assert "0.2.1-W3-022" not in old_parent["children"]
        assert "0.2.1-W3-022" in new_parent["children"]

    def test_no_dangling_reference_after_round_trip(
        self, tmp_ticket_dir, patch_ticket_paths
    ):
        """反之亦然：add-child 建立關係後，set-parent --clear 須完全消除雙向殘留。"""
        tr_mod = patch_ticket_paths
        _write_ticket_with_relations(tmp_ticket_dir / "0.2.1-W3-030.md", "0.2.1-W3-030")
        _write_ticket_with_relations(tmp_ticket_dir / "0.2.1-W3-031.md", "0.2.1-W3-031")

        add_ns = _Args(parent_id="0.2.1-W3-030", child_id="0.2.1-W3-031")
        assert tr_mod.execute_add_child(add_ns, "0.2.1") == 0

        clear_ns = _Args(child_id="0.2.1-W3-031", new_parent_id=None, clear=True)
        assert tr_mod.execute_set_parent(clear_ns, "0.2.1") == 0

        child = tr_mod.load_ticket("0.2.1", "0.2.1-W3-031")
        parent = tr_mod.load_ticket("0.2.1", "0.2.1-W3-030")
        assert child["parent_id"] is None
        assert "0.2.1-W3-031" not in parent["children"]

    def test_missing_target_and_clear_flag_are_mutually_exclusive(
        self, tmp_ticket_dir, patch_ticket_paths, capsys
    ):
        tr_mod = patch_ticket_paths
        _write_ticket_with_relations(tmp_ticket_dir / "0.2.1-W3-040.md", "0.2.1-W3-040")

        no_target_ns = _Args(child_id="0.2.1-W3-040", new_parent_id=None, clear=False)
        assert tr_mod.execute_set_parent(no_target_ns, "0.2.1") == 1

        _write_ticket_with_relations(tmp_ticket_dir / "0.2.1-W3-041.md", "0.2.1-W3-041")
        conflict_ns = _Args(
            child_id="0.2.1-W3-040", new_parent_id="0.2.1-W3-041", clear=True
        )
        assert tr_mod.execute_set_parent(conflict_ns, "0.2.1") == 1

    def test_self_reference_rejected(self, tmp_ticket_dir, patch_ticket_paths):
        tr_mod = patch_ticket_paths
        _write_ticket_with_relations(tmp_ticket_dir / "0.2.1-W3-050.md", "0.2.1-W3-050")

        ns = _Args(child_id="0.2.1-W3-050", new_parent_id="0.2.1-W3-050", clear=False)
        assert tr_mod.execute_set_parent(ns, "0.2.1") == 1
