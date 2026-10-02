"""complete 的 children / spawned 終態檢查跨版本解析（0.4.2-W1-047）。

前移規則讓已完成子孫留在舊版本、只改寫 parent 引用；終態檢查若只載入父票
所在版本，這些子票會被誤判為 not_found。
"""

from ticket_system.commands.lifecycle import (
    _collect_non_terminal_spawned,
    _collect_pending_children,
)
from ticket_system.lib.paths import get_tickets_dir

OLD_VERSION = "0.4.1"
NEW_VERSION = "0.4.2"


def _write_ticket(version: str, ticket_id: str, status: str) -> None:
    tickets_dir = get_tickets_dir(version)
    tickets_dir.mkdir(parents=True, exist_ok=True)
    (tickets_dir / f"{ticket_id}.md").write_text(
        f"---\nid: {ticket_id}\ntitle: t\ntype: IMP\nstatus: {status}\n"
        f"version: {version}\n---\n\n# Execution Log\n",
        encoding="utf-8",
    )


class TestChildrenCrossVersion:
    def test_completed_child_in_old_version_passes(self):
        """E1：父在新版本、已完成子票在舊版本 → 不阻擋。"""
        _write_ticket(OLD_VERSION, "0.4.1-W1-038.1", "completed")
        assert _collect_pending_children(["0.4.1-W1-038.1"], NEW_VERSION) == []

    def test_closed_child_in_old_version_passes(self):
        _write_ticket(OLD_VERSION, "0.4.1-W1-038.2", "closed")
        assert _collect_pending_children(["0.4.1-W1-038.2"], NEW_VERSION) == []

    def test_pending_child_in_old_version_still_blocks(self):
        """E2：舊版本中的子票為 pending 仍阻擋，狀態如實回報。"""
        _write_ticket(OLD_VERSION, "0.4.1-W1-038.3", "pending")
        assert _collect_pending_children(["0.4.1-W1-038.3"], NEW_VERSION) == [
            ("0.4.1-W1-038.3", "pending")
        ]

    def test_missing_child_still_not_found(self):
        """E2：真正不存在的 ID 仍記 not_found。"""
        assert _collect_pending_children(["0.4.1-W9-999"], NEW_VERSION) == [
            ("0.4.1-W9-999", "not_found")
        ]

    def test_same_version_child_unchanged(self):
        _write_ticket(NEW_VERSION, "0.4.2-W1-050", "in_progress")
        assert _collect_pending_children(["0.4.2-W1-050"], NEW_VERSION) == [
            ("0.4.2-W1-050", "in_progress")
        ]


class TestSpawnedCrossVersion:
    def test_completed_spawned_in_old_version_passes(self):
        _write_ticket(OLD_VERSION, "0.4.1-W2-010", "completed")
        assert _collect_non_terminal_spawned(["0.4.1-W2-010"], NEW_VERSION) == []

    def test_pending_spawned_in_old_version_still_blocks(self):
        _write_ticket(OLD_VERSION, "0.4.1-W2-011", "pending")
        assert _collect_non_terminal_spawned(["0.4.1-W2-011"], NEW_VERSION) == [
            ("0.4.1-W2-011", "pending")
        ]

    def test_missing_spawned_still_not_found(self):
        assert _collect_non_terminal_spawned(["0.4.1-W9-998"], NEW_VERSION) == [
            ("0.4.1-W9-998", "not_found")
        ]
