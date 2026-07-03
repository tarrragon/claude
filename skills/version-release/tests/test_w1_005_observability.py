"""
0.4.0-W1-005: version-release check 可觀測性測試

覆蓋兩情境：
1. 配置載入揭露：check/start/release 開頭印出實際命中的配置路徑，或未找到時印出偵測到的專案型別
2. 跳過類訊息標籤名實對齊：技術債務票目錄不存在 / 無票時不得標示 [OK]，須為中性的 [SKIP]
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import version_release as vr  # noqa: E402


# ---------------------------------------------------------------------------
# 情境 1：配置載入揭露
# ---------------------------------------------------------------------------
class TestFindConfigPath:
    def test_root_config_found(self, tmp_path):
        """root 層配置存在時回傳其路徑"""
        config_file = tmp_path / vr.VERSION_RELEASE_CONFIG_FILE
        config_file.write_text("project_type: npm\n", encoding="utf-8")

        result = vr.find_version_release_config_path(tmp_path)

        assert result == config_file

    def test_claude_fallback_found(self, tmp_path):
        """root 層無配置、.claude/ 層有時回傳 .claude/ 路徑"""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        config_file = claude_dir / vr.VERSION_RELEASE_CONFIG_FILE
        config_file.write_text("project_type: npm\n", encoding="utf-8")

        result = vr.find_version_release_config_path(tmp_path)

        assert result == config_file

    def test_no_config_returns_none(self, tmp_path):
        """兩層皆無配置時回傳 None"""
        result = vr.find_version_release_config_path(tmp_path)

        assert result is None


class TestPrintConfigDisclosure:
    def test_discloses_found_config_path(self, tmp_path, capsys):
        """配置存在時印出實際命中路徑"""
        config_file = tmp_path / vr.VERSION_RELEASE_CONFIG_FILE
        config_file.write_text("project_type: npm\n", encoding="utf-8")

        vr.print_config_disclosure(tmp_path)

        captured = capsys.readouterr()
        assert "載入配置" in captured.out
        assert str(config_file) in captured.out

    def test_discloses_missing_config_with_detected_type(self, tmp_path, capsys):
        """配置不存在時印出使用預設與偵測到的專案型別"""
        with patch.object(vr, "detect_project_type", return_value="unknown"):
            vr.print_config_disclosure(tmp_path)

        captured = capsys.readouterr()
        assert "未找到配置" in captured.out
        assert "使用預設" in captured.out
        assert "unknown" in captured.out


# ---------------------------------------------------------------------------
# 情境 2：跳過類訊息標籤名實對齊
# ---------------------------------------------------------------------------
class TestTechDebtStatusSkipLabel:
    def test_missing_tickets_dir_marks_skipped(self, tmp_path):
        """票目錄不存在時 result 應標示 skipped=True，訊息語意為跳過而非通過"""
        with patch.object(vr, "get_project_root", return_value=tmp_path):
            result = vr.check_technical_debt_status("0.99.0")

        assert result["skipped"] is True
        assert "跳過" in result["message"]

    def test_no_td_files_marks_skipped(self, tmp_path):
        """票目錄存在但無 TD 檔案時 result 應標示 skipped=True"""
        tickets_dir = tmp_path / "docs" / "work-logs" / "v0.99.0" / "tickets"
        tickets_dir.mkdir(parents=True)

        with patch.object(vr, "get_project_root", return_value=tmp_path):
            result = vr.check_technical_debt_status("0.99.0")

        assert result["skipped"] is True
        assert "跳過" in result["message"]

    def test_nested_worklog_dir_finds_tickets_dir(self, tmp_path):
        """nested worklog 結構（v{major}/v{major_minor}/v{version}/tickets）下應能正確找到票目錄並掃描 TD"""
        tickets_dir = (
            tmp_path / "docs" / "work-logs" / "v0" / "v0.99" / "v0.99.0" / "tickets"
        )
        tickets_dir.mkdir(parents=True)
        td_file = tickets_dir / "0.99.0-W1-TD-001.md"
        td_file.write_text(
            "---\nticket_id: 0.99.0-W1-TD-001\nstatus: pending\nversion: 0.99\n---\n",
            encoding="utf-8",
        )

        with patch.object(vr, "get_project_root", return_value=tmp_path):
            result = vr.check_technical_debt_status("0.99.0")

        assert result["skipped"] is False
        assert result["passed"] is False
        assert result["pending_count"] == 1

    def test_flat_worklog_dir_still_supported_as_fallback(self, tmp_path):
        """扁平 worklog 結構（v{version}/tickets）在 nested 路徑不存在時仍可作為向後相容 fallback"""
        tickets_dir = tmp_path / "docs" / "work-logs" / "v0.99.0" / "tickets"
        tickets_dir.mkdir(parents=True)
        td_file = tickets_dir / "0.99.0-W1-TD-001.md"
        td_file.write_text(
            "---\nticket_id: 0.99.0-W1-TD-001\nstatus: pending\nversion: 0.99\n---\n",
            encoding="utf-8",
        )

        with patch.object(vr, "get_project_root", return_value=tmp_path):
            result = vr.check_technical_debt_status("0.99.0")

        assert result["skipped"] is False
        assert result["passed"] is False
        assert result["pending_count"] == 1

    def test_preflight_check_uses_skip_label_not_ok(self, tmp_path, capsys):
        """preflight_check 對 skipped 技術債務檢查不得印出 [OK] 標籤"""
        with patch.object(vr, "get_project_root", return_value=tmp_path), \
                patch.object(vr, "check_worklog_completed", return_value=(True, [])), \
                patch.object(vr, "check_technical_debt", return_value=(True, [])), \
                patch.object(vr, "check_previous_versions_completed", return_value=(True, [])), \
                patch.object(vr, "check_stale_active_versions", return_value=(True, [])), \
                patch.object(vr, "check_version_sync", return_value=(True, [])):
            vr.preflight_check("0.99.0")

        captured = capsys.readouterr()
        assert "[SKIP]" in captured.out
        for line in captured.out.splitlines():
            if "找不到票目錄" in line or "找不到任何技術債務票" in line:
                assert "[OK]" not in line
