"""
finish 前移撞號測試（0.3.0-W1-041）

驗收對應：
- finish --dry-run 對碰撞 rc=0 預覽改號並續行；正式執行走改號並列對照表，測試覆蓋

`migrate_overflow_tickets` 呼叫 `_run_ticket_migrate` 產生獨立 subprocess，
本檔以 mock 模擬 `ticket migrate` 在碰撞情境下的兩種真實行為：
- dry-run：exit code 0、stdout 含改號預覽與 [MIGRATE-MAP] 標記
- 正式執行：exit code 0（已自動改號）、stdout 含實際改號後的目標 ID
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import version_release as vr  # noqa: E402


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _ticket_md(ticket_id: str, status: str, what: str = "測試票") -> str:
    return "\n".join([
        "---",
        f"id: {ticket_id}",
        f"title: {what}",
        "type: IMP",
        f"status: {status}",
        "---",
        "",
        "# Body",
    ])


def _setup_overflow(tmp_path, version="0.1.0", wave=3, seq="010"):
    major, minor, patch = version.split(".")
    tickets_dir = (
        tmp_path / "docs" / "work-logs" / f"v{major}" / f"v{major}.{minor}"
        / f"v{version}" / "tickets"
    )
    ticket_id = f"{version}-W{wave}-{seq}"
    _write(
        tickets_dir / f"{ticket_id}.md",
        _ticket_md(ticket_id, "pending"),
    )
    return tickets_dir


def _write_todolist(tmp_path, versions):
    content_lines = ["versions:"]
    for v in versions:
        content_lines.append(f"  - version: {v}")
    _write(tmp_path / "docs" / "todolist.yaml", "\n".join(content_lines) + "\n")


class TestFinishMigrateCollisionDryRun:
    """finish --dry-run 對碰撞以 rc=0 預覽改號並續行。"""

    def test_dry_run_collision_previews_renumber_and_continues(
        self, tmp_path, capsys
    ):
        _setup_overflow(tmp_path)
        _write_todolist(tmp_path, ["0.1.0", "0.1.1"])
        config = dict(vr.DEFAULT_VERSION_RELEASE_CONFIG)

        # 模擬 ticket migrate --dry-run 對碰撞印改號預覽並回 rc=0
        collision_preview = MagicMock(
            returncode=0,
            stdout=(
                "[WARNING] dry-run 偵測到目標 Ticket 已存在，正式執行將自動改號:\n"
                "  原目標: 0.1.1-W3-010\n"
                "  改號預覽: 0.1.1-W3-011\n"
                "[MIGRATE-MAP] 0.1.1-W3-010 -> 0.1.1-W3-011\n"
            ),
            stderr="",
        )
        mapping = []
        with patch.object(vr, "get_project_root", return_value=tmp_path), \
                patch.object(vr, "load_version_release_config", return_value=config), \
                patch.object(
                    vr, "_run_ticket_migrate", return_value=collision_preview
                ) as mock_migrate:
            ok = vr.migrate_overflow_tickets("0.1.0", dry_run=True, mapping_out=mapping)

        captured = capsys.readouterr()

        assert ok is True
        mock_migrate.assert_called_once_with(
            "0.1.0-W3-010", "0.1.1-W3-010", "0.1.1", True
        )
        assert "改號預覽" in captured.out
        assert "0.1.1-W3-011" in captured.out
        assert "前移失敗" not in captured.out
        assert mapping == [("0.1.0-W3-010", "0.1.1-W3-010", "0.1.1-W3-011")]

    def test_dry_run_passes_earlier_preview_targets_as_reserved(self, tmp_path):
        """第二張票的 dry-run 呼叫帶入第一張票的預覽目標，避免兩票預覽同一目標。"""
        tickets_dir = _setup_overflow(tmp_path, seq="010")
        _write(
            tickets_dir / "0.1.0-W3-011.md",
            _ticket_md("0.1.0-W3-011", "pending"),
        )
        _write_todolist(tmp_path, ["0.1.0", "0.1.1"])
        config = dict(vr.DEFAULT_VERSION_RELEASE_CONFIG)

        first = MagicMock(
            returncode=0, stderr="",
            stdout="[MIGRATE-MAP] 0.1.1-W3-010 -> 0.1.1-W3-012\n",
        )
        second = MagicMock(returncode=0, stdout="", stderr="")
        with patch.object(vr, "get_project_root", return_value=tmp_path), \
                patch.object(vr, "load_version_release_config", return_value=config), \
                patch.object(
                    vr, "_run_ticket_migrate", side_effect=[first, second]
                ) as mock_migrate:
            ok = vr.migrate_overflow_tickets("0.1.0", dry_run=True)

        assert ok is True
        assert mock_migrate.call_count == 2
        second_call = mock_migrate.call_args_list[1]
        assert set(second_call.kwargs["reserved"]) == {"0.1.1-W3-012"}


class TestFinishMappingTable:
    """正式 finish 結尾列出原目標到實際目標對照表。"""

    def test_print_mapping_lists_original_and_actual_targets(self, capsys):
        vr.print_overflow_mapping([
            ("0.1.0-W3-010", "0.1.1-W3-010", "0.1.1-W3-011"),
            ("0.1.0-W3-020", "0.1.1-W3-020", "0.1.1-W3-020"),
        ])
        out = capsys.readouterr().out
        assert "0.1.1-W3-010 -> 0.1.1-W3-011" in out
        assert "0.1.1-W3-020 -> 0.1.1-W3-020" in out
        assert "0.1.0-W3-010" in out


class TestFinishMigrateCollisionActualRun:
    """finish 正式執行對碰撞走改號，不中止。"""

    def test_actual_run_collision_renumbers_and_continues(self, tmp_path, capsys):
        _setup_overflow(tmp_path)
        _write_todolist(tmp_path, ["0.1.0", "0.1.1"])
        config = dict(vr.DEFAULT_VERSION_RELEASE_CONFIG)

        # 模擬 ticket migrate 正式執行碰撞後自動改號成功（rc=0）
        renumbered_success = MagicMock(
            returncode=0,
            stdout=(
                "[INFO] 目標 Ticket 0.1.1-W3-010 已存在，"
                "自動改號為 0.1.1-W3-011"
                "（已寫入 migrated_from: 0.1.1-W3-010）\n"
                "[MIGRATE-MAP] 0.1.1-W3-010 -> 0.1.1-W3-011\n"
            ),
            stderr="",
        )
        with patch.object(vr, "get_project_root", return_value=tmp_path), \
                patch.object(vr, "load_version_release_config", return_value=config), \
                patch.object(
                    vr, "_run_ticket_migrate", return_value=renumbered_success
                ) as mock_migrate:
            ok = vr.migrate_overflow_tickets("0.1.0", dry_run=False)

        captured = capsys.readouterr()

        assert ok is True
        mock_migrate.assert_called_once_with(
            "0.1.0-W3-010", "0.1.1-W3-010", "0.1.1", False
        )
        # 實際改號結果已轉印，且前移視為成功（不中止）
        assert "自動改號為 0.1.1-W3-011" in captured.out
        assert "已前移" in captured.out
