"""update 子命令測試。"""

import argparse
from pathlib import Path
from unittest.mock import patch

import yaml

from doc_system.commands.update import execute
from doc_system.core.file_locator import FileLocator


def _setup_proposal(tmp_path, prop_id="PROP-001", status="draft"):
    """建立 proposal 檔案和 tracking.yaml。"""
    proposals_dir = tmp_path / "docs" / "proposals"
    proposals_dir.mkdir(parents=True)

    md = proposals_dir / f"{prop_id}-test.md"
    md.write_text(
        f'---\nid: {prop_id}\ntitle: "Test Proposal"\nstatus: {status}\n---\n# Content\n'
    )

    # 建立 tracking.yaml
    tracking = tmp_path / "docs" / "proposals-tracking.yaml"
    data = {
        "version": "1.0",
        "last_updated": "2026-03-30",
        "proposals": {
            prop_id: {
                "title": "Test Proposal",
                "status": status,
                "proposed": "2026-03-30",
                "confirmed": None,
                "target_version": None,
                "source": "",
                "spec_refs": [],
                "usecase_refs": [],
                "ticket_refs": [],
                "checklist": [],
            },
        },
    }
    tracking.write_text(
        yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)
    )

    return str(tmp_path)


class TestUpdateStatus:
    """update 子命令的測試案例。"""

    def test_update_status_success(self, tmp_path, capsys):
        """正常更新 proposal status 應修改檔案和 tracking.yaml。"""
        project_root = _setup_proposal(tmp_path, "PROP-001", "draft")
        args = argparse.Namespace(id="PROP-001", status="discussing")

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            execute(args)

        output = capsys.readouterr().out
        assert "已更新" in output
        assert "draft" in output
        assert "discussing" in output
        assert "已同步 tracking.yaml" in output

        # 檢查檔案 frontmatter 已更新
        md = tmp_path / "docs" / "proposals" / "PROP-001-test.md"
        content = md.read_text()
        assert "status: discussing" in content

        # 檢查 tracking.yaml 已同步
        tracking = tmp_path / "docs" / "proposals-tracking.yaml"
        data = yaml.safe_load(tracking.read_text())
        assert data["proposals"]["PROP-001"]["status"] == "discussing"

    def test_update_nonexistent_id(self, tmp_path, capsys):
        """更新不存在的 ID 應顯示錯誤訊息。"""
        proposals_dir = tmp_path / "docs" / "proposals"
        proposals_dir.mkdir(parents=True)

        args = argparse.Namespace(id="PROP-999", status="confirmed")

        with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
            try:
                execute(args)
            except SystemExit:
                pass

        output = capsys.readouterr().out
        assert "找不到文件" in output

    def test_update_tracking_yaml_sync(self, tmp_path, capsys):
        """更新 proposal 為 confirmed 時應在 tracking.yaml 填入 confirmed 日期。"""
        project_root = _setup_proposal(tmp_path, "PROP-002", "discussing")
        args = argparse.Namespace(id="PROP-002", status="confirmed")

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            execute(args)

        output = capsys.readouterr().out
        assert "已更新" in output
        assert "已同步 tracking.yaml" in output

        # 檢查 tracking.yaml confirmed 日期已填入
        tracking = tmp_path / "docs" / "proposals-tracking.yaml"
        data = yaml.safe_load(tracking.read_text())
        assert data["proposals"]["PROP-002"]["status"] == "confirmed"
        assert data["proposals"]["PROP-002"]["confirmed"] is not None

    def test_update_usecase_no_tracking_sync(self, tmp_path, capsys):
        """更新 usecase 不應嘗試同步 tracking.yaml。"""
        usecases_dir = tmp_path / "docs" / "usecases"
        usecases_dir.mkdir(parents=True)

        md = usecases_dir / "UC-01-test.md"
        md.write_text(
            '---\nid: UC-01\ntitle: "Test UC"\nstatus: draft\n---\n# UC-01\n'
        )

        args = argparse.Namespace(id="UC-01", status="confirmed")

        with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
            execute(args)

        output = capsys.readouterr().out
        assert "已更新" in output
        # UC 不會有 tracking 同步訊息
        assert "已同步 tracking.yaml" not in output
