"""track tree／chain／spawned 顯示跨版本載入 children 與 spawned。

前移規則讓已完成子孫留在舊版本、只改寫 parent 引用；若只以單一版本解析，
舊版本子票整段從樹中消失、舊版本 spawned 顯示為 not_found。
"""

import argparse

from ticket_system.commands.track_query import (
    _collect_spawned_tree,
    execute_chain,
    execute_tree,
)
from ticket_system.lib.paths import get_tickets_dir

OLD_VERSION = "0.4.1"
NEW_VERSION = "0.4.2"

PARENT_ID = f"{NEW_VERSION}-W1-001"
OLD_CHILD = f"{OLD_VERSION}-W1-038.1"
OLD_GRANDCHILD = f"{OLD_VERSION}-W1-038.1.1"
OLD_SPAWNED = f"{OLD_VERSION}-W2-007"
MISSING_ID = f"{OLD_VERSION}-W9-999"
BARE_PARENT_ID = f"{NEW_VERSION}-W1-002"
SAME_CHILD = f"{NEW_VERSION}-W1-001.1"


def _write(version, ticket_id, parent=None, children=(), spawned=(), title="t"):
    tickets_dir = get_tickets_dir(version)
    tickets_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"id: {ticket_id}", f"title: {title}", "type: IMP",
             "status: completed", f"version: {version}", f"what: {title}"]
    if parent:
        lines.append(f"parent_id: {parent}")
    lines.append("children: [" + ", ".join(children) + "]")
    lines.append("spawned_tickets: [" + ", ".join(spawned) + "]")
    (tickets_dir / f"{ticket_id}.md").write_text(
        "---\n" + "\n".join(lines) + "\n---\n\n# Execution Log\n", encoding="utf-8"
    )


def _run(func, ticket_id, capsys):
    args = argparse.Namespace(ticket_id=ticket_id, version=NEW_VERSION)
    assert func(args, NEW_VERSION) == 0
    return capsys.readouterr().out


class TestTreeCrossVersion:
    def test_old_version_child_shown_in_tree(self, capsys):
        """E1：同批 fixture，含舊版本子票與不含時輸出不同。"""
        _write(NEW_VERSION, BARE_PARENT_ID)
        without = _run(execute_tree, BARE_PARENT_ID, capsys)
        _write(NEW_VERSION, PARENT_ID, children=[OLD_CHILD])
        _write(OLD_VERSION, OLD_CHILD, parent=PARENT_ID, children=[OLD_GRANDCHILD])
        _write(OLD_VERSION, OLD_GRANDCHILD, parent=OLD_CHILD)
        with_child = _run(execute_tree, PARENT_ID, capsys)
        assert OLD_CHILD in with_child and OLD_GRANDCHILD in with_child
        assert with_child != without
        assert "not_found" not in with_child

    def test_chain_shows_old_version_child(self, capsys):
        _write(NEW_VERSION, PARENT_ID, children=[OLD_CHILD])
        _write(OLD_VERSION, OLD_CHILD, parent=PARENT_ID)
        assert OLD_CHILD in _run(execute_chain, PARENT_ID, capsys)

    def test_missing_child_marked_not_found(self, capsys):
        """E2：真正不存在的 ID 標 not_found，不靜默省略。"""
        _write(NEW_VERSION, PARENT_ID, children=[MISSING_ID])
        out = _run(execute_tree, PARENT_ID, capsys)
        assert MISSING_ID in out and "not_found" in out

    def test_same_version_tree_unchanged(self, capsys):
        _write(NEW_VERSION, PARENT_ID, children=[SAME_CHILD], title="root")
        _write(NEW_VERSION, SAME_CHILD, parent=PARENT_ID, title="kid")
        out = _run(execute_tree, PARENT_ID, capsys)
        assert out.splitlines()[0].startswith(PARENT_ID)
        assert len(out.splitlines()) == 2
        assert "not_found" not in out


class TestSpawnedCrossVersion:
    def test_old_version_spawned_loaded(self):
        """E1：舊版本 spawned 顯示真實狀態，與不存在 ID 的輸出不同。"""
        _write(OLD_VERSION, OLD_SPAWNED, title="sp")
        found, missing = [], []
        _collect_spawned_tree(OLD_SPAWNED, NEW_VERSION, set(), 1, found)
        _collect_spawned_tree(MISSING_ID, NEW_VERSION, set(), 1, missing)
        assert "[completed]" in found[0] and "not_found" not in found[0]
        assert "(not_found)" in missing[0]
        assert found != missing

    def test_cycle_guard_unchanged(self):
        _write(OLD_VERSION, OLD_SPAWNED, spawned=[OLD_SPAWNED])
        lines = []
        _collect_spawned_tree(OLD_SPAWNED, NEW_VERSION, set(), 1, lines)
        assert any("CYCLE DETECTED" in line for line in lines)
