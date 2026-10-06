"""acceptance_auditor._has_impl_or_adj_child 跨版本載入 children。

前移規則讓已完成子孫留在舊版本、只改寫 parent 引用；若只以父票版本載入，
舊版本的 IMP/ADJ 子票會被誤判為不存在。
"""

from ticket_system.lib.acceptance_auditor import _has_impl_or_adj_child
from ticket_system.lib.paths import get_tickets_dir

OLD_VERSION = "0.4.1"
NEW_VERSION = "0.4.2"

OLD_IMP_CHILD = f"{OLD_VERSION}-W1-038.1"
OLD_ADJ_CHILD = f"{OLD_VERSION}-W1-038.2"
OLD_ANA_CHILD = f"{OLD_VERSION}-W1-038.3"
OLD_MISSING_CHILD = f"{OLD_VERSION}-W9-999"
NEW_IMP_CHILD = f"{NEW_VERSION}-W1-050"
PARENT_ID = f"{NEW_VERSION}-W1-001"


def _write_ticket(version: str, ticket_id: str, ticket_type: str) -> None:
    tickets_dir = get_tickets_dir(version)
    tickets_dir.mkdir(parents=True, exist_ok=True)
    (tickets_dir / f"{ticket_id}.md").write_text(
        f"---\nid: {ticket_id}\ntitle: t\ntype: {ticket_type}\nstatus: completed\n"
        f"version: {version}\n---\n\n# Execution Log\n",
        encoding="utf-8",
    )


def _parent(*children: str) -> dict:
    return {"id": PARENT_ID, "children": list(children)}


class TestHasImplOrAdjChildCrossVersion:
    def test_imp_child_in_old_version_detected(self):
        """E1：同批 fixture，舊版本 IMP 子票 -> True，不存在的 ID -> False，兩者不同。"""
        _write_ticket(OLD_VERSION, OLD_IMP_CHILD, "IMP")
        found = _has_impl_or_adj_child(_parent(OLD_IMP_CHILD), NEW_VERSION)
        missing = _has_impl_or_adj_child(_parent(OLD_MISSING_CHILD), NEW_VERSION)
        assert found is True
        assert missing is False
        assert found != missing

    def test_adj_child_in_old_version_detected(self):
        _write_ticket(OLD_VERSION, OLD_ADJ_CHILD, "ADJ")
        assert _has_impl_or_adj_child(_parent(OLD_ADJ_CHILD), NEW_VERSION) is True

    def test_ana_child_in_old_version_still_false(self):
        """E2：舊版本子票為 ANA -> False。"""
        _write_ticket(OLD_VERSION, OLD_ANA_CHILD, "ANA")
        assert _has_impl_or_adj_child(_parent(OLD_ANA_CHILD), NEW_VERSION) is False

    def test_missing_child_still_false(self):
        """E2：不存在的 ID -> False。"""
        assert _has_impl_or_adj_child(_parent(OLD_MISSING_CHILD), NEW_VERSION) is False

    def test_same_version_child_unchanged(self):
        _write_ticket(NEW_VERSION, NEW_IMP_CHILD, "IMP")
        assert _has_impl_or_adj_child(_parent(NEW_IMP_CHILD), NEW_VERSION) is True
