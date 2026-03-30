"""list 子命令測試。"""

import argparse
from unittest.mock import patch

from doc_system.commands.list_cmd import execute
from doc_system.core.file_locator import FileLocator


def _setup_docs(tmp_path):
    """建立 proposals + usecases + spec 目錄和檔案。"""
    for subdir, files in [
        ("proposals", [("PROP-001-test.md", "PROP-001", "Test Prop", "draft")]),
        ("usecases", [("UC-01-import.md", "UC-01", "Import UC", "approved")]),
        ("spec/core", [("core-systems.md", "SPEC-001", "Core Spec", "approved")]),
    ]:
        d = tmp_path / "docs" / subdir
        d.mkdir(parents=True, exist_ok=True)
        for filename, fid, title, status in files:
            (d / filename).write_text(
                f"---\nid: {fid}\ntitle: \"{title}\"\nstatus: {status}\n---\n"
            )
    return str(tmp_path)


class TestListExecute:
    """list_cmd.execute 的測試案例。"""

    def test_list_proposals(self, tmp_path, capsys):
        """列出 proposals 應顯示表格。"""
        project_root = _setup_docs(tmp_path)
        args = argparse.Namespace(doc_type="proposals")

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            execute(args)

        output = capsys.readouterr().out
        assert "proposals" in output
        assert "PROP-001" in output
        assert "draft" in output

    def test_list_all_types(self, tmp_path, capsys):
        """省略 doc_type 應列出全部三種類型。"""
        project_root = _setup_docs(tmp_path)
        args = argparse.Namespace(doc_type=None)

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            execute(args)

        output = capsys.readouterr().out
        assert "proposals" in output
        assert "usecases" in output
        assert "specs" in output

    def test_list_empty_type(self, tmp_path, capsys):
        """列出空目錄應輸出表頭但無資料行。"""
        (tmp_path / "docs" / "usecases").mkdir(parents=True)
        args = argparse.Namespace(doc_type="usecases")

        with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
            execute(args)

        output = capsys.readouterr().out
        assert "usecases" in output
        # 表頭後無資料行
        lines = [line for line in output.strip().splitlines() if line.strip() and not line.startswith("=") and not line.startswith("-") and "ID" not in line]
        assert len(lines) == 0
