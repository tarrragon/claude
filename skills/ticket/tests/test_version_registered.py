"""
validate_version_registered 單元測試

驗證版本在 todolist.yaml 中的註冊狀態檢查。
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from ticket_system.lib.version import validate_version_registered


@pytest.fixture
def temp_project(tmp_path):
    """建立含 docs 目錄的臨時專案"""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    return tmp_path


def _write_todolist(project_root: Path, data: dict) -> None:
    """寫入 todolist.yaml"""
    todolist_path = project_root / "docs" / "todolist.yaml"
    with open(todolist_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True)


class TestValidateVersionRegistered:
    """validate_version_registered 測試"""

    def test_active_version_passes(self, temp_project):
        """已註冊且 active 的版本通過驗證"""
        _write_todolist(temp_project, {
            "versions": [
                {"version": "0.17.4", "status": "active"},
            ]
        })
        with patch(
            "ticket_system.lib.version.get_project_root",
            return_value=temp_project,
        ):
            is_valid, error_msg = validate_version_registered("0.17.4")

        assert is_valid is True
        assert error_msg == ""

    def test_unregistered_version_rejected(self, temp_project):
        """未註冊的版本被拒絕"""
        _write_todolist(temp_project, {
            "versions": [
                {"version": "0.17.4", "status": "active"},
            ]
        })
        with patch(
            "ticket_system.lib.version.get_project_root",
            return_value=temp_project,
        ):
            is_valid, error_msg = validate_version_registered("0.18.0")

        assert is_valid is False
        assert "0.18.0" in error_msg
        assert "未在 todolist.yaml 中註冊" in error_msg

    def test_completed_version_rejected(self, temp_project):
        """已註冊但 completed 狀態的版本被拒絕"""
        _write_todolist(temp_project, {
            "versions": [
                {"version": "0.17.3", "status": "completed"},
                {"version": "0.17.4", "status": "active"},
            ]
        })
        with patch(
            "ticket_system.lib.version.get_project_root",
            return_value=temp_project,
        ):
            is_valid, error_msg = validate_version_registered("0.17.3")

        assert is_valid is False
        assert "0.17.3" in error_msg
        assert "completed" in error_msg
        assert "非 active" in error_msg

    def test_todolist_not_exists_allows(self, temp_project):
        """todolist.yaml 不存在時向後相容（允許）"""
        # 不建立 todolist.yaml
        with patch(
            "ticket_system.lib.version.get_project_root",
            return_value=temp_project,
        ):
            is_valid, error_msg = validate_version_registered("0.17.4")

        assert is_valid is True
        assert error_msg == ""

    def test_empty_versions_list_rejected(self, temp_project):
        """versions 列表為空時，版本視為未註冊"""
        _write_todolist(temp_project, {"versions": []})
        with patch(
            "ticket_system.lib.version.get_project_root",
            return_value=temp_project,
        ):
            is_valid, error_msg = validate_version_registered("0.17.4")

        assert is_valid is False
        assert "未在 todolist.yaml 中註冊" in error_msg

    def test_malformed_yaml_allows(self, temp_project):
        """todolist.yaml 格式錯誤時跳過驗證（允許）"""
        todolist_path = temp_project / "docs" / "todolist.yaml"
        todolist_path.write_text("{{invalid yaml", encoding="utf-8")
        with patch(
            "ticket_system.lib.version.get_project_root",
            return_value=temp_project,
        ):
            is_valid, error_msg = validate_version_registered("0.17.4")

        assert is_valid is True
        assert error_msg == ""

    def test_error_message_suggests_workflow(self, temp_project):
        """錯誤訊息提示用戶執行正確流程"""
        _write_todolist(temp_project, {
            "versions": [
                {"version": "0.17.4", "status": "active"},
            ]
        })
        with patch(
            "ticket_system.lib.version.get_project_root",
            return_value=temp_project,
        ):
            _, error_msg = validate_version_registered("0.99.0")

        assert "version-release" in error_msg or "doc-flow" in error_msg
