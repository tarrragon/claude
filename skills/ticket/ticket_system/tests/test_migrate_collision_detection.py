"""
ticket migrate collision detection 測試（W14-048）

來源 Ticket: 0.18.0-W14-048（IMP）
依據 ANA: 0.18.0-W14-047（雙層防護的 L2 工具強制層）

測試目標：
鎖定 migrate.py collision detection 行為，預防 W1-001~W1-003 類事件再發生。

AC 對應（5 條）：
- AC1：dry_run 階段對既有 target_path 輸出 WARN（含目標路徑與既有 ticket 標題）→ Test_DryRun_*
- AC2：實際執行階段預設拒絕覆寫並 exit 1 → Test_Actual_Default_*
- AC3：--force-overwrite 旗標可繞過但記錄至 audit log → Test_ForceOverwrite_*
- AC4：批量遷移任一目標撞 ID 即 fail-fast 不執行任何 migration → Test_Batch_FailFast_*
- AC5：本檔覆蓋四情境

測試環境：
- pytest + tmp_path fixture 隔離 docs/work-logs/v*/tickets/ 結構
- 透過 monkeypatch 將 migrate / ticket_loader 模組的 get_project_root 指向 tmp_path
"""

from pathlib import Path

import pytest
import yaml

from ticket_system.commands.migrate import (
    _batch_migrate,
    _migrate_single_ticket,
)
from ticket_system.lib.parser import parse_frontmatter


# ---------------------------------------------------------------------------
# Fixtures（與 test_migrate_reverse_refs.py 同樣的 patch 機制）
# ---------------------------------------------------------------------------


def _patch_get_project_root(monkeypatch, tmp_path: Path) -> None:
    """集中將 migrate / ticket_loader / paths 的 get_project_root 指向 tmp_path。"""
    import ticket_system.commands.migrate as migrate_mod
    import ticket_system.lib.ticket_loader as loader_mod

    monkeypatch.setattr(migrate_mod, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(loader_mod, "get_project_root", lambda: tmp_path)

    try:
        import ticket_system.lib.paths as paths_mod  # type: ignore

        if hasattr(paths_mod, "get_project_root"):
            monkeypatch.setattr(paths_mod, "get_project_root", lambda: tmp_path)
    except ImportError:
        pass


def _write_ticket(tickets_dir: Path, ticket_id: str, extra_fields: dict) -> Path:
    """寫入最小化 Ticket 檔案。"""
    path = tickets_dir / f"{ticket_id}.md"

    frontmatter = {
        "id": ticket_id,
        "title": f"Test {ticket_id}",
        "type": "IMP",
        "status": "pending",
        **extra_fields,
    }

    content = (
        "---\n"
        + yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True)
        + "---\n\n# Body"
    )
    path.write_text(content, encoding="utf-8")
    return path


def _read_frontmatter(path: Path) -> dict:
    content = path.read_text(encoding="utf-8")
    fm, _ = parse_frontmatter(content)
    return fm


@pytest.fixture
def project_with_tickets(tmp_path, monkeypatch):
    """建立 tmp 專案結構並 patch get_project_root。"""
    work_logs = tmp_path / "docs" / "work-logs" / "v0" / "v0.18" / "v0.18.0" / "tickets"
    work_logs.mkdir(parents=True)

    _patch_get_project_root(monkeypatch, tmp_path)

    return tmp_path, work_logs


# ---------------------------------------------------------------------------
# AC1：dry_run 階段對既有 target_path 輸出 WARN
# ---------------------------------------------------------------------------


class Test_DryRun_Collision_Warning:
    """AC1：dry_run 階段對既有 target_path 輸出 WARN。"""

    def test_dry_run_warns_when_target_exists(self, project_with_tickets, capsys):
        """
        Given: source_id 存在，target_id 也存在（既有 ticket）
        When: 以 dry_run=True 呼叫 _migrate_single_ticket
        Then:
          - exit code 0（dry-run 不阻擋）
          - stdout 含 WARNING 字樣與既有 target_id 標題
          - 既有 target 檔案未被覆寫
        """
        _, tickets_dir = project_with_tickets
        source_id = "0.18.0-W5-001"
        target_id = "0.18.0-W14-001"

        _write_ticket(tickets_dir, source_id, {})
        _write_ticket(tickets_dir, target_id, {"title": "Existing Target Title"})

        rc = _migrate_single_ticket(
            "0.18.0", source_id, target_id, dry_run=True, backup=False
        )
        captured = capsys.readouterr()

        assert rc == 0
        assert "WARNING" in captured.out
        assert "Existing Target Title" in captured.out

        # 既有 target 應仍存在且內容未變
        assert (tickets_dir / f"{target_id}.md").exists()
        fm = _read_frontmatter(tickets_dir / f"{target_id}.md")
        assert fm["title"] == "Existing Target Title"

    def test_dry_run_no_warning_when_target_absent(self, project_with_tickets, capsys):
        """
        Given: target_id 不存在（無 collision）
        When: dry_run=True
        Then: 不輸出 collision 警告
        """
        _, tickets_dir = project_with_tickets
        source_id = "0.18.0-W5-002"
        target_id = "0.18.0-W14-002"

        _write_ticket(tickets_dir, source_id, {})

        rc = _migrate_single_ticket(
            "0.18.0", source_id, target_id, dry_run=True, backup=False
        )
        captured = capsys.readouterr()

        assert rc == 0
        assert "目標 Ticket 已存在" not in captured.out


# ---------------------------------------------------------------------------
# AC2：實際執行階段預設拒絕覆寫並 exit 1
# ---------------------------------------------------------------------------


class Test_Actual_Default_Rejects:
    """AC2：實際執行階段預設拒絕覆寫並 exit 1。"""

    def test_actual_run_rejects_overwrite_by_default(
        self, project_with_tickets, capsys
    ):
        """
        Given: source / target 都存在
        When: dry_run=False, force_overwrite=False
        Then:
          - exit code 1
          - 既有 target 未被覆寫
          - source 仍存在（未被刪除）
        """
        _, tickets_dir = project_with_tickets
        source_id = "0.18.0-W5-003"
        target_id = "0.18.0-W14-003"

        _write_ticket(tickets_dir, source_id, {})
        _write_ticket(tickets_dir, target_id, {"title": "Should Not Be Overwritten"})

        rc = _migrate_single_ticket(
            "0.18.0", source_id, target_id, dry_run=False, backup=False
        )
        captured = capsys.readouterr()

        assert rc == 1
        assert "ERROR" in captured.out or "拒絕覆寫" in captured.out

        # 既有 target 內容未變
        fm = _read_frontmatter(tickets_dir / f"{target_id}.md")
        assert fm["title"] == "Should Not Be Overwritten"

        # source 仍存在（沒被刪）
        assert (tickets_dir / f"{source_id}.md").exists()


# ---------------------------------------------------------------------------
# AC3：--force-overwrite 旗標可繞過但記錄至 audit log
# ---------------------------------------------------------------------------


class Test_ForceOverwrite_Allows:
    """AC3：force_overwrite=True 時可覆寫並記錄 audit log。"""

    def test_force_overwrite_allows_and_logs(self, project_with_tickets, capsys):
        """
        Given: source / target 都存在
        When: dry_run=False, force_overwrite=True
        Then:
          - exit code 0
          - 既有 target 被覆寫（title 變為 source 的 title）
          - stdout 含 AUDIT 字樣
          - source 檔案被刪除
        """
        _, tickets_dir = project_with_tickets
        source_id = "0.18.0-W5-004"
        target_id = "0.18.0-W14-004"

        _write_ticket(tickets_dir, source_id, {"title": "Source Title"})
        _write_ticket(tickets_dir, target_id, {"title": "Existing To Be Overwritten"})

        rc = _migrate_single_ticket(
            "0.18.0", source_id, target_id,
            dry_run=False, backup=False, force_overwrite=True,
        )
        captured = capsys.readouterr()

        assert rc == 0, f"Expected rc=0 but got {rc}; stdout={captured.out}"
        assert "AUDIT" in captured.out

        # target 已被 source 取代
        fm = _read_frontmatter(tickets_dir / f"{target_id}.md")
        assert fm["id"] == target_id
        assert fm["title"] == "Source Title"

        # source 已被刪除
        assert not (tickets_dir / f"{source_id}.md").exists()


# ---------------------------------------------------------------------------
# AC4：批量遷移任一目標撞 ID 即 fail-fast 不執行任何 migration
# ---------------------------------------------------------------------------


class Test_Batch_FailFast:
    """AC4：批量 fail-fast。"""

    def test_batch_fail_fast_when_any_target_collides(
        self, project_with_tickets, tmp_path, capsys
    ):
        """
        Given: 三筆批量遷移，其中第二筆 target 已存在
        When: _batch_migrate 實際執行
        Then:
          - exit code 1
          - 任何 source 都未被遷移（fail-fast 在 pre-scan 階段阻擋）
        """
        _, tickets_dir = project_with_tickets

        # 三個 source
        _write_ticket(tickets_dir, "0.18.0-W5-010", {})
        _write_ticket(tickets_dir, "0.18.0-W5-011", {})
        _write_ticket(tickets_dir, "0.18.0-W5-012", {})
        # 第二筆 target 撞
        _write_ticket(
            tickets_dir, "0.18.0-W14-011",
            {"title": "Pre-existing Collision Target"},
        )

        config = {
            "migrations": [
                {"from": "0.18.0-W5-010", "to": "0.18.0-W14-010"},
                {"from": "0.18.0-W5-011", "to": "0.18.0-W14-011"},
                {"from": "0.18.0-W5-012", "to": "0.18.0-W14-012"},
            ]
        }
        config_path = tmp_path / "migrations.yaml"
        config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

        rc = _batch_migrate(
            "0.18.0", str(config_path), dry_run=False, backup=False
        )
        captured = capsys.readouterr()

        assert rc == 1
        assert "fail-fast" in captured.out or "ERROR" in captured.out

        # 三個 source 全部仍存在（沒人被遷移）
        assert (tickets_dir / "0.18.0-W5-010.md").exists()
        assert (tickets_dir / "0.18.0-W5-011.md").exists()
        assert (tickets_dir / "0.18.0-W5-012.md").exists()
        # 第一筆 target 不該被建立
        assert not (tickets_dir / "0.18.0-W14-010.md").exists()
        # 既有 target 未變
        fm = _read_frontmatter(tickets_dir / "0.18.0-W14-011.md")
        assert fm["title"] == "Pre-existing Collision Target"

    def test_batch_succeeds_when_no_collision(
        self, project_with_tickets, tmp_path, capsys
    ):
        """
        Given: 兩筆批量遷移，無撞 ID
        When: _batch_migrate
        Then: exit code 0，兩筆都遷移成功
        """
        _, tickets_dir = project_with_tickets

        _write_ticket(tickets_dir, "0.18.0-W5-020", {})
        _write_ticket(tickets_dir, "0.18.0-W5-021", {})

        config = {
            "migrations": [
                {"from": "0.18.0-W5-020", "to": "0.18.0-W14-020"},
                {"from": "0.18.0-W5-021", "to": "0.18.0-W14-021"},
            ]
        }
        config_path = tmp_path / "migrations.yaml"
        config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

        rc = _batch_migrate(
            "0.18.0", str(config_path), dry_run=False, backup=False
        )

        assert rc == 0
        assert (tickets_dir / "0.18.0-W14-020.md").exists()
        assert (tickets_dir / "0.18.0-W14-021.md").exists()
        assert not (tickets_dir / "0.18.0-W5-020.md").exists()
        assert not (tickets_dir / "0.18.0-W5-021.md").exists()

    def test_batch_force_overwrite_bypasses_prescan(
        self, project_with_tickets, tmp_path, capsys
    ):
        """
        Given: 批量遷移含 collision
        When: force_overwrite=True
        Then: 不在 pre-scan 階段擋下，個別執行時記錄 audit log
        """
        _, tickets_dir = project_with_tickets

        _write_ticket(tickets_dir, "0.18.0-W5-030", {})
        _write_ticket(
            tickets_dir, "0.18.0-W14-030",
            {"title": "Will Be Overwritten"},
        )

        config = {
            "migrations": [
                {"from": "0.18.0-W5-030", "to": "0.18.0-W14-030"},
            ]
        }
        config_path = tmp_path / "migrations.yaml"
        config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

        rc = _batch_migrate(
            "0.18.0", str(config_path),
            dry_run=False, backup=False, force_overwrite=True,
        )
        captured = capsys.readouterr()

        assert rc == 0
        assert "AUDIT" in captured.out
        # target 已被覆寫為 source 內容
        fm = _read_frontmatter(tickets_dir / "0.18.0-W14-030.md")
        assert fm["id"] == "0.18.0-W14-030"
        assert "Will Be Overwritten" not in fm["title"]
