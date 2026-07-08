"""
migrate 版本合法性守衛測試（W9-002）

驗收：
- migrate 對未註冊目標版本（含 dry-run）被阻擋並顯示註冊引導
- planned 目標版本可正常遷入（回歸 1.0.0 遷移場景）
- dry-run 同樣須過守衛
"""

from pathlib import Path

import pytest
import yaml

from ticket_system.commands.migrate import _migrate_single_ticket


def _write_ticket(tickets_dir: Path, ticket_id: str) -> Path:
    """寫入最小化 Ticket 檔案（用於測試）"""
    tickets_dir.mkdir(parents=True, exist_ok=True)
    path = tickets_dir / f"{ticket_id}.md"
    content = "\n".join([
        "---",
        f"id: {ticket_id}",
        f"title: Test {ticket_id}",
        "type: IMP",
        "status: pending",
        "---",
        "",
        "# Body",
    ])
    path.write_text(content, encoding="utf-8")
    return path


def _write_todolist(project_root: Path, versions: list) -> None:
    docs_dir = project_root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    todolist_path = docs_dir / "todolist.yaml"
    with open(todolist_path, "w", encoding="utf-8") as f:
        yaml.dump({"versions": versions}, f, allow_unicode=True)


@pytest.fixture
def project(tmp_path, monkeypatch):
    """建立 tmp 專案結構，patch 所有涉及的 get_project_root 引用"""
    source_tickets_dir = (
        tmp_path / "docs" / "work-logs" / "v0" / "v0.18" / "v0.18.0" / "tickets"
    )
    source_tickets_dir.mkdir(parents=True)

    import ticket_system.commands.migrate as migrate_mod
    import ticket_system.lib.paths as paths_mod
    import ticket_system.lib.version as version_mod

    monkeypatch.setattr(migrate_mod, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(paths_mod, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(version_mod, "get_project_root", lambda: tmp_path)

    return tmp_path, source_tickets_dir


class TestMigrateVersionGuard:
    """migrate 目標版本合法性守衛"""

    def test_unregistered_target_version_blocked(self, project):
        """未註冊目標版本被阻擋，不執行遷移（來源檔案仍在原位）"""
        root, tickets_dir = project
        _write_todolist(root, [{"version": "0.18.0", "status": "active"}])
        source_path = _write_ticket(tickets_dir, "0.18.0-W10-037")

        result = _migrate_single_ticket(
            "0.18.0", "0.18.0-W10-037", "99.99.99-W1-001", dry_run=False
        )

        assert result == 1
        assert source_path.exists()

    def test_unregistered_target_version_blocked_dry_run(self, project):
        """dry-run 模式下未註冊目標版本同樣被阻擋"""
        root, tickets_dir = project
        _write_todolist(root, [{"version": "0.18.0", "status": "active"}])
        _write_ticket(tickets_dir, "0.18.0-W10-037")

        result = _migrate_single_ticket(
            "0.18.0", "0.18.0-W10-037", "99.99.99-W1-001", dry_run=True
        )

        assert result == 1

    def test_planned_target_version_allowed(self, project):
        """planned 目標版本可正常遷入（回歸 1.0.0 遷移場景）"""
        root, tickets_dir = project
        _write_todolist(root, [
            {"version": "0.18.0", "status": "active"},
            {"version": "1.0.0", "status": "planned"},
        ])
        _write_ticket(tickets_dir, "0.18.0-W10-037")

        result = _migrate_single_ticket(
            "0.18.0", "0.18.0-W10-037", "1.0.0-W1-001", dry_run=False
        )

        assert result == 0
        target_path = (
            root / "docs" / "work-logs" / "v1" / "v1.0" / "v1.0.0" / "tickets"
            / "1.0.0-W1-001.md"
        )
        assert target_path.exists()

    def test_planned_target_version_allowed_dry_run(self, project):
        """planned 目標版本 dry-run 通過守衛"""
        root, tickets_dir = project
        _write_todolist(root, [
            {"version": "0.18.0", "status": "active"},
            {"version": "1.0.0", "status": "planned"},
        ])
        _write_ticket(tickets_dir, "0.18.0-W10-037")

        result = _migrate_single_ticket(
            "0.18.0", "0.18.0-W10-037", "1.0.0-W1-001", dry_run=True
        )

        assert result == 0

    def test_no_todolist_allows_migration(self, project):
        """todolist.yaml 不存在時向後相容（允許遷移）"""
        root, tickets_dir = project
        _write_ticket(tickets_dir, "0.18.0-W10-037")

        result = _migrate_single_ticket(
            "0.18.0", "0.18.0-W10-037", "9.9.9-W1-001", dry_run=False
        )

        assert result == 0
