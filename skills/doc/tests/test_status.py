"""status 子命令測試。"""

import argparse
from unittest.mock import patch

from doc_system.commands.status import execute
from doc_system.core.file_locator import FileLocator


def _create_tracking(tmp_path, proposals_data):
    """建立 proposals-tracking.yaml。"""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    tracking = docs_dir / "proposals-tracking.yaml"

    lines = ['version: "1.0"', 'last_updated: "2026-03-30"', "", "proposals:"]
    for prop_id, prop_status in proposals_data.items():
        lines.append(f"  {prop_id}:")
        lines.append(f'    title: "Test {prop_id}"')
        lines.append(f"    status: {prop_status}")

    tracking.write_text("\n".join(lines) + "\n")
    return str(tmp_path)


class TestStatusExecute:
    """status.execute 的測試案例。"""

    def test_status_summary(self, tmp_path, capsys):
        """正常追蹤檔案應顯示狀態摘要。"""
        project_root = _create_tracking(tmp_path, {
            "PROP-001": "draft",
            "PROP-002": "draft",
            "PROP-003": "confirmed",
        })
        args = argparse.Namespace()

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            execute(args)

        output = capsys.readouterr().out
        assert "提案總數: 3" in output
        assert "draft" in output
        assert "confirmed" in output

    def test_status_no_tracking_file(self, tmp_path, capsys):
        """追蹤檔案不存在時應顯示錯誤訊息。"""
        (tmp_path / "docs").mkdir(parents=True)
        args = argparse.Namespace()

        with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
            execute(args)

        output = capsys.readouterr().out
        assert "無法讀取" in output

    def test_status_empty_proposals(self, tmp_path, capsys):
        """沒有提案時應顯示相應訊息。"""
        project_root = _create_tracking(tmp_path, {})
        args = argparse.Namespace()

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            execute(args)

        output = capsys.readouterr().out
        assert "沒有提案" in output
