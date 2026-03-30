"""test-map 子命令測試。"""

import argparse
from unittest.mock import patch

from doc_system.commands.test_map import execute, _scan_test_files
from doc_system.core.file_locator import FileLocator


def _setup_project(tmp_path, test_content=None):
    """建立 UC 文件和 tests 目錄。"""
    usecases_dir = tmp_path / "docs" / "usecases"
    usecases_dir.mkdir(parents=True)
    (usecases_dir / "UC-01-import.md").write_text(
        '---\nid: UC-01\ntitle: "Import"\nstatus: approved\n---\n'
    )
    (usecases_dir / "UC-02-export.md").write_text(
        '---\nid: UC-02\ntitle: "Export"\nstatus: approved\n---\n'
    )

    tests_dir = tmp_path / "tests" / "unit"
    tests_dir.mkdir(parents=True)

    if test_content is not None:
        for filename, content in test_content.items():
            (tests_dir / filename).write_text(content)

    return str(tmp_path)


class TestTestMapExecute:
    """test_map.execute 的測試案例。"""

    def test_show_all_uc_map(self, tmp_path, capsys):
        """顯示全部 UC 的測試對應表。"""
        project_root = _setup_project(tmp_path, {
            "test_import.js": "// UC-01 import test\ndescribe('import', () => {});",
        })
        args = argparse.Namespace(uc_id=None)

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            execute(args)

        output = capsys.readouterr().out
        assert "UC-01" in output
        assert "UC-02" in output

    def test_filter_by_uc_id(self, tmp_path, capsys):
        """指定 uc_id 應只顯示該 UC。"""
        project_root = _setup_project(tmp_path, {
            "test_import.js": "// UC-01 import test",
            "test_export.js": "// UC-02 export test",
        })
        args = argparse.Namespace(uc_id="UC-01")

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            execute(args)

        output = capsys.readouterr().out
        assert "UC-01" in output
        # UC-02 不應出現在資料行（表頭除外）
        lines = output.strip().splitlines()
        data_lines = [l for l in lines if l.strip() and not l.startswith("=") and not l.startswith("-") and "UC ID" not in l]
        assert not any("UC-02" in line for line in data_lines)

    def test_scan_test_files_finds_matches(self, tmp_path):
        """_scan_test_files 應能找到包含 UC ID 的測試檔案。"""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_uc01.js").write_text("// UC-01 related test")
        (tests_dir / "test_other.js").write_text("// some other test")

        matches = _scan_test_files(str(tests_dir), "UC-01")

        assert len(matches) == 1
        assert "test_uc01.js" in matches[0]

    def test_scan_test_files_no_matches(self, tmp_path):
        """無匹配時應回傳空 list。"""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_other.js").write_text("// some other test")

        matches = _scan_test_files(str(tests_dir), "UC-99")

        assert matches == []
