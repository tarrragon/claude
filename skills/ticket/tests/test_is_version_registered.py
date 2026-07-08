"""
is_version_registered 單元測試（W9-002）

與 validate_version_registered 不同：只檢查版本是否存在於
todolist.yaml，不檢查是否 active。供 migrate 等允許遷入
planned/active/completed 版本的場景使用。
"""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from ticket_system.lib.version import is_version_registered


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


class TestIsVersionRegistered:
    """is_version_registered 測試"""

    def test_active_version_registered(self, temp_project):
        """active 版本視為已註冊"""
        _write_todolist(temp_project, {
            "versions": [{"version": "0.17.4", "status": "active"}],
        })
        with patch(
            "ticket_system.lib.version.get_project_root",
            return_value=temp_project,
        ):
            assert is_version_registered("0.17.4") is True

    def test_planned_version_registered(self, temp_project):
        """planned 版本視為已註冊（與 validate_version_registered 的關鍵差異）"""
        _write_todolist(temp_project, {
            "versions": [{"version": "1.0.0", "status": "planned"}],
        })
        with patch(
            "ticket_system.lib.version.get_project_root",
            return_value=temp_project,
        ):
            assert is_version_registered("1.0.0") is True

    def test_completed_version_registered(self, temp_project):
        """completed 版本視為已註冊"""
        _write_todolist(temp_project, {
            "versions": [{"version": "0.17.3", "status": "completed"}],
        })
        with patch(
            "ticket_system.lib.version.get_project_root",
            return_value=temp_project,
        ):
            assert is_version_registered("0.17.3") is True

    def test_unregistered_version_rejected(self, temp_project):
        """未註冊的版本回傳 False"""
        _write_todolist(temp_project, {
            "versions": [{"version": "0.17.4", "status": "active"}],
        })
        with patch(
            "ticket_system.lib.version.get_project_root",
            return_value=temp_project,
        ):
            assert is_version_registered("99.99.99") is False

    def test_todolist_not_exists_allows(self, temp_project):
        """todolist.yaml 不存在時向後相容（允許）"""
        with patch(
            "ticket_system.lib.version.get_project_root",
            return_value=temp_project,
        ):
            assert is_version_registered("0.17.4") is True

    def test_malformed_yaml_allows(self, temp_project):
        """todolist.yaml 格式錯誤時跳過驗證（允許）"""
        todolist_path = temp_project / "docs" / "todolist.yaml"
        todolist_path.write_text("{{invalid yaml", encoding="utf-8")
        with patch(
            "ticket_system.lib.version.get_project_root",
            return_value=temp_project,
        ):
            assert is_version_registered("0.17.4") is True
