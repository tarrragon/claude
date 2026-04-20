"""
測試 migrate _update_cross_references 在真實檔案系統中的引用更新行為

來源 Ticket: 0.18.0-W10-037
驗收條件：
- blockedBy/relatedTo 等依賴欄位在 migrate 後的引用更新（.4 遷移為 .2 後 blockedBy 仍指向舊 ID）
- 父 Ticket children 欄位自動更新

測試範圍：
- 依賴 Ticket (A.blockedBy = [B]) 在 B migrate 後，blockedBy 自動更新為新 ID
- 相關 Ticket (A.relatedTo = [B]) 同步更新
- 父 Ticket A.children = [B] 在 B migrate 後，children 更新為新 ID
- 子任務 file stem 恰好以 new_id 開頭時不被誤跳過（Bug 2 疑似根因 B 驗證）
"""

import pytest
from pathlib import Path

from ticket_system.commands.migrate import _update_cross_references


def _write_ticket(tickets_dir: Path, ticket_id: str, extra_fields: dict) -> Path:
    """寫入最小化 Ticket 檔案（用於測試）"""
    filename = f"{ticket_id}.md"
    path = tickets_dir / filename

    lines = [
        "---",
        f"id: {ticket_id}",
        f"title: Test {ticket_id}",
        "type: IMP",
        "status: pending",
    ]
    for key, value in extra_fields.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                if isinstance(item, dict):
                    first_k, first_v = next(iter(item.items()))
                    lines.append(f"  - {first_k}: {first_v}")
                    for k, v in list(item.items())[1:]:
                        lines.append(f"    {k}: {v}")
                else:
                    lines.append(f"  - {item}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    lines.append("# Body")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _read_frontmatter(path: Path) -> dict:
    """簡易讀 frontmatter"""
    from ticket_system.lib.parser import parse_frontmatter

    content = path.read_text(encoding="utf-8")
    fm, _ = parse_frontmatter(content)
    return fm


@pytest.fixture
def project_with_tickets(tmp_path, monkeypatch):
    """建立 tmp 專案結構並 patch get_project_root 到 migrate 模組"""
    work_logs = tmp_path / "docs" / "work-logs" / "v0.18.0" / "tickets"
    work_logs.mkdir(parents=True)

    # Patch 兩處 get_project_root：migrate 模組的引用 和 paths 模組的來源
    import ticket_system.commands.migrate as migrate_mod
    import ticket_system.lib.paths as paths_mod

    monkeypatch.setattr(migrate_mod, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(paths_mod, "get_project_root", lambda: tmp_path)

    return tmp_path, work_logs


class TestBlockedByReference:
    """blockedBy 引用必須在 migrate 後自動更新"""

    def test_blockedby_updated_after_migrate(self, project_with_tickets):
        """依賴 Ticket A 的 blockedBy 指向被 migrate 的 B，migrate 後必須更新"""
        tmp_path, tickets_dir = project_with_tickets

        old_id = "0.18.0-W10-036.4"
        new_id = "0.18.0-W10-036.2"

        # 依賴 Ticket A（blockedBy 指向 B 的舊 ID）
        _write_ticket(tickets_dir, "0.18.0-W10-100",
                      {"blockedBy": [old_id]})

        # 執行 cross_references 更新
        count = _update_cross_references(old_id, new_id)

        assert count == 1, f"應更新 1 個檔案，實際: {count}"

        # 驗證 A 的 blockedBy 已更新
        a_path = tickets_dir / "0.18.0-W10-100.md"
        a_fm = _read_frontmatter(a_path)
        assert a_fm["blockedBy"] == [new_id]


class TestRelatedToReference:
    """relatedTo 引用同步更新"""

    def test_relatedto_updated_after_migrate(self, project_with_tickets):
        tmp_path, tickets_dir = project_with_tickets

        old_id = "0.18.0-W10-036.4"
        new_id = "0.18.0-W10-036.2"

        _write_ticket(tickets_dir, "0.18.0-W10-101",
                      {"relatedTo": [old_id, "0.18.0-W10-999"]})

        count = _update_cross_references(old_id, new_id)

        assert count == 1
        fm = _read_frontmatter(tickets_dir / "0.18.0-W10-101.md")
        assert fm["relatedTo"] == [new_id, "0.18.0-W10-999"]


class TestChildrenReference:
    """父 Ticket children 欄位必須在子 Ticket migrate 後更新"""

    def test_children_string_list_updated(self, project_with_tickets):
        """children 為字串列表時，migrate 子 Ticket 後必須更新"""
        tmp_path, tickets_dir = project_with_tickets

        old_id = "0.18.0-W10-036.4"
        new_id = "0.18.0-W10-036.2"

        # 父 Ticket 的 children 包含即將 migrate 的子任務
        _write_ticket(tickets_dir, "0.18.0-W10-036",
                      {"children": [old_id, "0.18.0-W10-036.1"]})

        count = _update_cross_references(old_id, new_id)

        assert count == 1
        fm = _read_frontmatter(tickets_dir / "0.18.0-W10-036.md")
        assert new_id in fm["children"]
        assert old_id not in fm["children"]


class TestSubtaskFileStemEdgeCase:
    """Bug 2 疑似根因 B 驗證：L108 startswith 可能誤跳過子 Ticket"""

    def test_subtask_with_new_id_prefix_is_not_skipped(self, project_with_tickets):
        """
        當子 Ticket file stem 恰以 new_id 為前綴（如 new_id='W10-036.2'
        而子任務檔案為 'W10-036.2.1.md'），若子任務 blockedBy 仍指向 old_id，
        必須更新而非被 startswith 跳過。
        """
        tmp_path, tickets_dir = project_with_tickets

        old_id = "0.18.0-W10-036.4"
        new_id = "0.18.0-W10-036.2"

        # 子任務 file 以 new_id 為前綴（關鍵邊界條件）
        _write_ticket(tickets_dir, "0.18.0-W10-036.2.1",
                      {"blockedBy": [old_id]})

        count = _update_cross_references(old_id, new_id)

        fm = _read_frontmatter(tickets_dir / "0.18.0-W10-036.2.1.md")
        assert fm["blockedBy"] == [new_id], (
            "子任務檔案 stem 以 new_id 為前綴時，blockedBy 仍必須被更新，"
            "不應被 startswith 誤跳過"
        )


class TestParentIdReference:
    """parent_id 引用同步更新（測試覆蓋驗收條件的隱含要求）"""

    def test_parent_id_updated_after_migrate(self, project_with_tickets):
        tmp_path, tickets_dir = project_with_tickets

        old_id = "0.18.0-W10-036.4"
        new_id = "0.18.0-W10-036.2"

        _write_ticket(tickets_dir, "0.18.0-W10-200",
                      {"parent_id": old_id})

        count = _update_cross_references(old_id, new_id)

        assert count == 1
        fm = _read_frontmatter(tickets_dir / "0.18.0-W10-200.md")
        assert fm["parent_id"] == new_id
