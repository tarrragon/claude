"""
migrate 發版前移撞號改號機制測試（0.3.0-W1-041）

驗收對應：
- migrate 對已存在目標改取下一可用序號並寫 migrated_from，測試覆蓋碰撞與無碰撞
"""

from pathlib import Path

import pytest
import yaml

from ticket_system.commands.migrate import _migrate_single_ticket
from ticket_system.lib.parser import parse_frontmatter


def _write_ticket(tickets_dir: Path, ticket_id: str, title: str = "Test") -> Path:
    """寫入最小化 Ticket 檔案（用於測試）"""
    tickets_dir.mkdir(parents=True, exist_ok=True)
    path = tickets_dir / f"{ticket_id}.md"
    content = "\n".join([
        "---",
        f"id: {ticket_id}",
        f"title: {title}",
        "type: IMP",
        "status: pending",
        "---",
        "",
        "# Body",
    ])
    path.write_text(content, encoding="utf-8")
    return path


def _read_frontmatter(path: Path) -> dict:
    content = path.read_text(encoding="utf-8")
    fm, _ = parse_frontmatter(content)
    return fm


def _write_todolist(project_root: Path, versions: list) -> None:
    docs_dir = project_root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    todolist_path = docs_dir / "todolist.yaml"
    with open(todolist_path, "w", encoding="utf-8") as f:
        yaml.dump({"versions": versions}, f, allow_unicode=True)


@pytest.fixture
def project(tmp_path, monkeypatch):
    """建立 tmp 專案結構，patch 所有涉及的 get_project_root 引用。"""
    source_tickets_dir = (
        tmp_path / "docs" / "work-logs" / "v0" / "v0.20" / "v0.20.0" / "tickets"
    )
    source_tickets_dir.mkdir(parents=True)

    import ticket_system.commands.migrate as migrate_mod
    import ticket_system.lib.paths as paths_mod
    import ticket_system.lib.version as version_mod

    monkeypatch.setattr(migrate_mod, "get_ticket_state_root", lambda: tmp_path)
    monkeypatch.setattr(paths_mod, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(version_mod, "get_project_root", lambda: tmp_path)

    _write_todolist(tmp_path, [{"version": "0.20.0", "status": "active"}])

    return tmp_path, source_tickets_dir


class TestMigrateCollisionRenumber:
    """碰撞時改取下一可用序號並寫 migrated_from"""

    def test_collision_renumbers_and_records_migrated_from(self, project):
        """
        Given: 來源存在，目標已被其他 Ticket 佔用
        When: 實際執行（無 --force-overwrite）
        Then: 改取下一可用序號，新檔含 migrated_from 指向原碰撞目標，
              既有目標未被覆寫
        """
        root, tickets_dir = project
        _write_ticket(tickets_dir, "0.20.0-W3-001", title="Source")
        _write_ticket(tickets_dir, "0.20.0-W3-002", title="Existing Occupant")

        rc = _migrate_single_ticket(
            "0.20.0", "0.20.0-W3-001", "0.20.0-W3-002", dry_run=False, backup=False
        )

        assert rc == 0

        # 既有目標未被覆寫
        existing_fm = _read_frontmatter(tickets_dir / "0.20.0-W3-002.md")
        assert existing_fm["title"] == "Existing Occupant"

        # 改號後新檔案存在並記錄 migrated_from
        renumbered_path = tickets_dir / "0.20.0-W3-003.md"
        assert renumbered_path.exists()
        renumbered_fm = _read_frontmatter(renumbered_path)
        assert renumbered_fm["id"] == "0.20.0-W3-003"
        assert renumbered_fm["title"] == "Source"
        assert renumbered_fm["migrated_from"] == "0.20.0-W3-002"

        # source 已完成遷移
        assert not (tickets_dir / "0.20.0-W3-001.md").exists()

    def test_collision_renumber_skips_multiple_occupied_slots(self, project):
        """
        Given: 連續多個序號已被佔用（001 空缺不計，002/003 皆存在）
        When: 目標指向 002
        Then: 改號跳過已佔用的 003，落在第一個空缺 004
        """
        root, tickets_dir = project
        _write_ticket(tickets_dir, "0.20.0-W4-010", title="Source")
        _write_ticket(tickets_dir, "0.20.0-W4-011", title="Occupant A")
        _write_ticket(tickets_dir, "0.20.0-W4-012", title="Occupant B")

        rc = _migrate_single_ticket(
            "0.20.0", "0.20.0-W4-010", "0.20.0-W4-011", dry_run=False, backup=False
        )

        assert rc == 0
        assert (tickets_dir / "0.20.0-W4-013.md").exists()
        fm = _read_frontmatter(tickets_dir / "0.20.0-W4-013.md")
        assert fm["migrated_from"] == "0.20.0-W4-011"


class TestMigrateNoCollisionUnchanged:
    """無碰撞時維持原號，不寫 migrated_from"""

    def test_no_collision_keeps_original_target_id(self, project):
        """
        Given: 來源存在，目標不存在
        When: 實際執行
        Then: 落在原目標 ID，不寫 migrated_from 欄位
        """
        root, tickets_dir = project
        _write_ticket(tickets_dir, "0.20.0-W5-020", title="Source")

        rc = _migrate_single_ticket(
            "0.20.0", "0.20.0-W5-020", "0.20.0-W5-021", dry_run=False, backup=False
        )

        assert rc == 0
        target_path = tickets_dir / "0.20.0-W5-021.md"
        assert target_path.exists()
        fm = _read_frontmatter(target_path)
        assert fm["id"] == "0.20.0-W5-021"
        assert "migrated_from" not in fm
        assert not (tickets_dir / "0.20.0-W5-020.md").exists()
