"""test-map 子命令測試。"""

import argparse
from unittest.mock import patch

from doc_system.commands.test_map import execute, _scan_test_files, _load_traceability_tests
from doc_system.core.constants import TEST_SCAN_DIRS, TEST_SCAN_DIRS_CONFIG_KEY
from doc_system.core.file_locator import FileLocator
from doc_system.core.tracking_schema import TRACEABILITY_SCHEMA


def _setup_project(tmp_path, test_content=None, scan_dir="test"):
    """建立 UC 文件和測試目錄（預設 test/，Flutter 專案佈局）。"""
    usecases_dir = tmp_path / "docs" / "usecases"
    usecases_dir.mkdir(parents=True)
    (usecases_dir / "UC-01-import.md").write_text(
        '---\nid: UC-01\ntitle: "Import"\nstatus: approved\n---\n'
    )
    (usecases_dir / "UC-02-export.md").write_text(
        '---\nid: UC-02\ntitle: "Export"\nstatus: approved\n---\n'
    )

    tests_dir = tmp_path / scan_dir / "unit"
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
            "test_import.dart": "// UC-01 import test",
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
            "test_import.dart": "// UC-01 import test",
            "test_export.dart": "// UC-02 export test",
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

    def test_scans_integration_test_dir(self, tmp_path, capsys):
        """integration_test/ 目錄也應被掃描（非僅 test/）。"""
        project_root = _setup_project(
            tmp_path,
            {"test_import.dart": "// UC-01 import test"},
            scan_dir="integration_test",
        )
        args = argparse.Namespace(uc_id="UC-01")

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            execute(args)

        output = capsys.readouterr().out
        lines = output.strip().splitlines()
        data_line = next(l for l in lines if l.startswith("UC-01"))
        assert "1" in data_line

    def test_traceability_yaml_takes_priority_over_scan(self, tmp_path, capsys):
        """traceability.yaml 已回填 tests 時，優先採用而非檔案掃描結果。"""
        project_root = _setup_project(tmp_path, {
            "test_import.dart": "// UC-01 import test",
        })
        docs_dir = tmp_path / "docs"
        (docs_dir / "traceability.yaml").write_text(
            "version: \"1.0\"\n"
            "last_updated: \"2026-09-08\"\n"
            "mappings:\n"
            "  - spec: SPEC-001\n"
            "    usecase: UC-01\n"
            "    title: Import\n"
            "    tests:\n"
            "      - test/unit/from_traceability_test.dart\n"
        )
        args = argparse.Namespace(uc_id="UC-01")

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            execute(args)

        output = capsys.readouterr().out
        assert "from_traceability_test.dart" in output
        assert "test_import.dart" not in output

    def test_scan_test_files_finds_matches(self, tmp_path):
        """_scan_test_files 應能找到包含 UC ID 的測試檔案。"""
        tests_dir = tmp_path / "test"
        tests_dir.mkdir()
        (tests_dir / "test_uc01.dart").write_text("// UC-01 related test")
        (tests_dir / "test_other.dart").write_text("// some other test")

        matches = _scan_test_files(str(tests_dir), "UC-01")

        assert len(matches) == 1
        assert "test_uc01.dart" in matches[0]

    def test_scan_test_files_no_matches(self, tmp_path):
        """無匹配時應回傳空 list。"""
        tests_dir = tmp_path / "test"
        tests_dir.mkdir()
        (tests_dir / "test_other.dart").write_text("// some other test")

        matches = _scan_test_files(str(tests_dir), "UC-99")

        assert matches == []


class TestLoadTraceabilityTests:
    """_load_traceability_tests 的測試案例。"""

    def test_missing_file_returns_empty_dict(self, tmp_path):
        """traceability.yaml 不存在時回傳空字典（降級，不拋錯）。"""
        assert _load_traceability_tests(str(tmp_path)) == {}

    def test_empty_tests_field_excluded(self, tmp_path):
        """tests 欄位為空的條目不應出現在結果中（留給檔案掃描補上）。"""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "traceability.yaml").write_text(
            "version: \"1.0\"\n"
            "last_updated: \"2026-09-08\"\n"
            "mappings:\n"
            "  - spec: SPEC-001\n"
            "    usecase: UC-01\n"
            "    title: Import\n"
            "    tests: []\n"
        )

        assert _load_traceability_tests(str(tmp_path)) == {}


def _run_test_map(project_root, capsys, uc_id=None):
    with patch.object(FileLocator, "get_project_root", return_value=project_root):
        execute(argparse.Namespace(uc_id=uc_id))
    return capsys.readouterr()


def _uc_count(stdout, uc_id):
    line = next(l for l in stdout.splitlines() if l.startswith(uc_id))
    return int(line.split()[-1])


def _write_traceability(tmp_path, extra=""):
    (tmp_path / "docs" / "traceability.yaml").write_text(
        'version: "1.0"\nlast_updated: "2026-11-09"\nmappings: []\n' + extra,
        encoding="utf-8",
    )


class TestScanDirs:
    """掃描目錄：預設含 tests/、可由 traceability.yaml 覆寫、零命中時警示。"""

    def test_default_dirs_keep_flutter_layout_and_add_tests(self):
        assert {"test", "integration_test", "tests"} <= set(TEST_SCAN_DIRS)

    def test_config_key_is_allowed_by_traceability_schema(self):
        assert TEST_SCAN_DIRS_CONFIG_KEY in TRACEABILITY_SCHEMA["top_level_keys"]

    def test_tests_dir_scanned_by_default(self, tmp_path, capsys):
        project_root = _setup_project(
            tmp_path, {"test_import.py": "# UC-01 import"}, scan_dir="tests"
        )

        result = _run_test_map(project_root, capsys, "UC-01")

        assert _uc_count(result.out, "UC-01") == 1
        assert "WARNING" not in result.err

    def test_configured_dirs_replace_defaults(self, tmp_path, capsys):
        """同一批 fixture：未設定時掃到 test/，設定 [spec] 後只掃 spec/。"""
        project_root = _setup_project(tmp_path, {"a_test.dart": "// UC-01"}, scan_dir="test")
        spec_dir = tmp_path / "spec"
        spec_dir.mkdir()
        (spec_dir / "b_test.js").write_text("// UC-01 UC-02")

        without_config = _run_test_map(project_root, capsys).out
        _write_traceability(tmp_path, "test_scan_dirs:\n  - spec\n")
        with_config = _run_test_map(project_root, capsys).out

        assert without_config != with_config
        assert "test/unit/a_test.dart" in without_config
        assert "b_test.js" not in without_config
        assert "spec/b_test.js" in with_config
        assert "a_test.dart" not in with_config
        assert _uc_count(with_config, "UC-02") == 1

    def test_zero_scan_hits_warns_with_scanned_dirs(self, tmp_path, capsys):
        project_root = _setup_project(
            tmp_path, {"unrelated.py": "# no uc here"}, scan_dir="tests"
        )

        result = _run_test_map(project_root, capsys)

        assert "檔案掃描零命中" in result.err
        assert "2 個 UC" in result.err
        assert "test/（不存在）" in result.err
        assert "integration_test/（不存在）" in result.err
        assert "tests/（1 個測試檔）" in result.err

    def test_no_warning_when_any_scan_hits(self, tmp_path, capsys):
        project_root = _setup_project(tmp_path, {"t.dart": "// UC-01"})

        result = _run_test_map(project_root, capsys)

        assert _uc_count(result.out, "UC-02") == 0
        assert "WARNING" not in result.err

    def test_no_warning_when_all_ucs_backfilled(self, tmp_path, capsys):
        """全數 UC 由 traceability.yaml 回填時沒有改走掃描，不算零命中。"""
        project_root = _setup_project(tmp_path)
        (tmp_path / "docs" / "traceability.yaml").write_text(
            'version: "1.0"\nlast_updated: "2026-11-09"\nmappings:\n'
            "  - {spec: SPEC-001, usecase: UC-01, title: A, tests: [x_test.py]}\n"
            "  - {spec: SPEC-001, usecase: UC-02, title: B, tests: [y_test.py]}\n",
            encoding="utf-8",
        )

        result = _run_test_map(project_root, capsys)

        assert _uc_count(result.out, "UC-01") == 1
        assert "WARNING" not in result.err

    def test_invalid_config_warns_and_falls_back_to_defaults(self, tmp_path, capsys):
        project_root = _setup_project(tmp_path, {"t.dart": "// UC-01"})
        _write_traceability(tmp_path, "test_scan_dirs: spec\n")

        result = _run_test_map(project_root, capsys, "UC-01")

        assert "test_scan_dirs 須為非空的目錄字串清單" in result.err
        assert _uc_count(result.out, "UC-01") == 1
