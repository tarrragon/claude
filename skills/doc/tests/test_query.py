"""query 子命令測試。"""

import argparse
from unittest.mock import patch

from doc_system.commands.query import execute
from doc_system.core.file_locator import FileLocator


def _create_proposal(tmp_path, prop_id="PROP-001", title="Test Proposal", status="draft"):
    """在 tmp_path 建立 proposals 結構和 proposal 檔案。"""
    proposals_dir = tmp_path / "docs" / "proposals"
    proposals_dir.mkdir(parents=True)
    md = proposals_dir / f"{prop_id}-test.md"
    md.write_text(
        f"---\nid: {prop_id}\ntitle: \"{title}\"\nstatus: {status}\n"
        f"spec_refs: [SPEC-001]\nusecase_refs: [UC-01]\n---\n# Content\n"
    )
    return str(tmp_path)


class TestQueryExecute:
    """query.execute 的測試案例。"""

    def test_query_existing_proposal(self, tmp_path, capsys):
        """查詢存在的 proposal 應輸出 ID/標題/狀態/引用鏈。"""
        project_root = _create_proposal(tmp_path)
        args = argparse.Namespace(doc_id="PROP-001")

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            execute(args)

        output = capsys.readouterr().out
        assert "PROP-001" in output
        assert "Test Proposal" in output
        assert "draft" in output
        assert "SPEC-001" in output
        assert "UC-01" in output

    def test_query_nonexistent_id(self, tmp_path, capsys):
        """查詢不存在的 ID 應顯示錯誤訊息。"""
        proposals_dir = tmp_path / "docs" / "proposals"
        proposals_dir.mkdir(parents=True)
        args = argparse.Namespace(doc_id="PROP-999")

        with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
            execute(args)

        output = capsys.readouterr().out
        assert "找不到文件" in output

    def test_resolve_file_usecase(self, tmp_path):
        """resolve_file 應能找到 UC 類型文件。"""
        usecases_dir = tmp_path / "docs" / "usecases"
        usecases_dir.mkdir(parents=True)
        md = usecases_dir / "UC-01-import.md"
        md.write_text("---\nid: UC-01\n---\n")

        locator = FileLocator(str(tmp_path))
        result = locator.resolve_file("UC-01")

        assert result is not None
        assert "UC-01" in result

    def test_resolve_file_unknown_prefix(self, tmp_path):
        """未知前綴的 ID 應回傳 None。"""
        locator = FileLocator(str(tmp_path))
        result = locator.resolve_file("UNKNOWN-001")

        assert result is None
