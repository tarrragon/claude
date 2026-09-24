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
    """集中將 migrate / ticket_loader / paths 的 get_project_root 指向 tmp_path。

    0.2.1-W4-031：migrate.py 的根目錄解析已改用 get_ticket_state_root()
    （非 get_project_root()，理由見該命令模組內對應行的註解），故改 patch
    migrate_mod 上的 get_ticket_state_root 名稱；loader_mod / paths_mod 的
    get_project_root patch 保留（get_ticket_state_root 非 worktree 場景會
    委派 paths_mod.get_project_root，此處為雙重保險）。
    """
    import ticket_system.commands.migrate as migrate_mod
    import ticket_system.lib.ticket_loader as loader_mod

    monkeypatch.setattr(migrate_mod, "get_ticket_state_root", lambda: tmp_path)
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
    """AC1（W1-041 改版）：dry_run 階段對既有 target_path 判 FAIL 並印改號預覽。"""

    def test_dry_run_fails_and_previews_renumber_when_target_exists(
        self, project_with_tickets, capsys
    ):
        """
        Given: source_id 存在，target_id 也存在（既有 ticket）
        When: 以 dry_run=True、force_overwrite=False 呼叫 _migrate_single_ticket
        Then:
          - exit code 1（碰撞在 dry-run 階段即判 FAIL，不再視為可放行的預覽）
          - stdout 含 ERROR 字樣、既有 target 標題與改號預覽（下一可用序號）
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

        assert rc == 1
        assert "ERROR" in captured.out
        assert "Existing Target Title" in captured.out
        assert "0.18.0-W14-002" in captured.out  # 改號預覽：下一可用序號

        # 既有 target 應仍存在且內容未變
        assert (tickets_dir / f"{target_id}.md").exists()
        fm = _read_frontmatter(tickets_dir / f"{target_id}.md")
        assert fm["title"] == "Existing Target Title"

    def test_dry_run_warns_when_force_overwrite_and_target_exists(
        self, project_with_tickets, capsys
    ):
        """
        Given: source_id 存在，target_id 也存在（既有 ticket）
        When: dry_run=True、force_overwrite=True
        Then: 維持覆寫預覽語意（WARN 而非 FAIL），exit code 0
        """
        _, tickets_dir = project_with_tickets
        source_id = "0.18.0-W5-005"
        target_id = "0.18.0-W14-005"

        _write_ticket(tickets_dir, source_id, {})
        _write_ticket(tickets_dir, target_id, {"title": "Existing Target Title"})

        rc = _migrate_single_ticket(
            "0.18.0", source_id, target_id,
            dry_run=True, backup=False, force_overwrite=True,
        )
        captured = capsys.readouterr()

        assert rc == 0
        assert "WARNING" in captured.out
        assert "Existing Target Title" in captured.out

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


class Test_Actual_Default_Renumbers:
    """AC2（W1-041 改版）：實際執行階段預設對碰撞自動改號並寫 migrated_from。"""

    def test_actual_run_renumbers_on_collision_by_default(
        self, project_with_tickets, capsys
    ):
        """
        Given: source / target 都存在
        When: dry_run=False, force_overwrite=False
        Then:
          - exit code 0（改號後照常遷移成功）
          - 既有 target 未被覆寫
          - 新序號檔案（0.18.0-W14-004）被建立，frontmatter 含
            migrated_from: 0.18.0-W14-003（原碰撞目標）
          - source 已被刪除（遷移已完成，只是落在改號後的新 ID）
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

        assert rc == 0
        assert "INFO" in captured.out
        assert "0.18.0-W14-004" in captured.out  # 改號後的新目標

        # 既有 target 內容未變（未被覆寫）
        fm_existing = _read_frontmatter(tickets_dir / f"{target_id}.md")
        assert fm_existing["title"] == "Should Not Be Overwritten"

        # 改號後的新檔案已建立，且記錄 migrated_from
        renumbered_path = tickets_dir / "0.18.0-W14-004.md"
        assert renumbered_path.exists()
        fm_new = _read_frontmatter(renumbered_path)
        assert fm_new["id"] == "0.18.0-W14-004"
        assert fm_new["migrated_from"] == target_id

        # source 已完成遷移（原檔案被刪）
        assert not (tickets_dir / f"{source_id}.md").exists()


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


class Test_Batch_Renumber:
    """AC4（W1-041 改版）：批量遷移碰撞不再 fail-fast，改由個別項目自動改號。"""

    def test_batch_renumbers_colliding_target_instead_of_failing(
        self, project_with_tickets, tmp_path, capsys
    ):
        """
        Given: 兩筆批量遷移，其中第二筆 target 已存在
        When: _batch_migrate 實際執行（無 --force-overwrite）
        Then:
          - exit code 0（碰撞自動改號，不再整批 fail-fast）
          - 兩筆 source 均完成遷移
          - 第一筆落在原目標；第二筆落在改號後的新目標，且記錄 migrated_from
          - 既有碰撞的 target 檔案未被覆寫
        """
        _, tickets_dir = project_with_tickets

        _write_ticket(tickets_dir, "0.18.0-W5-010", {})
        _write_ticket(tickets_dir, "0.18.0-W5-011", {})
        # 第二筆 target 撞
        _write_ticket(
            tickets_dir, "0.18.0-W14-011",
            {"title": "Pre-existing Collision Target"},
        )

        config = {
            "migrations": [
                {"from": "0.18.0-W5-010", "to": "0.18.0-W14-010"},
                {"from": "0.18.0-W5-011", "to": "0.18.0-W14-011"},
            ]
        }
        config_path = tmp_path / "migrations.yaml"
        config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

        rc = _batch_migrate(
            "0.18.0", str(config_path), dry_run=False, backup=False
        )
        captured = capsys.readouterr()

        assert rc == 0
        assert "INFO" in captured.out

        # 兩個 source 皆已遷移完成（原檔被刪）
        assert not (tickets_dir / "0.18.0-W5-010.md").exists()
        assert not (tickets_dir / "0.18.0-W5-011.md").exists()

        # 第一筆落在原目標
        assert (tickets_dir / "0.18.0-W14-010.md").exists()

        # 既有碰撞 target 未變
        fm_existing = _read_frontmatter(tickets_dir / "0.18.0-W14-011.md")
        assert fm_existing["title"] == "Pre-existing Collision Target"

        # 第二筆改號落在下一可用序號，並記錄 migrated_from
        renumbered_path = tickets_dir / "0.18.0-W14-012.md"
        assert renumbered_path.exists()
        fm_new = _read_frontmatter(renumbered_path)
        assert fm_new["id"] == "0.18.0-W14-012"
        assert fm_new["migrated_from"] == "0.18.0-W14-011"

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
