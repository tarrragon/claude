"""where.files 路徑存在性檢查 helper（field_validators.missing_where_paths）測試。

覆蓋範圍：純函式 missing_where_paths 本身。三處呼叫端（create.py / fields.py /
track_dispatch_readiness.py）的整合測試分別在 test_directory_declaration_warnings.py
（fields.py execute_set_where）與 test_track_dispatch_readiness_where_paths.py
（dispatch-readiness 檢查 5）。
"""
from __future__ import annotations

from ticket_system.lib import field_validators


class TestMissingWherePaths:
    def test_all_paths_exist_returns_empty(self, tmp_path):
        existing = tmp_path / "a.py"
        existing.write_text("", encoding="utf-8")

        missing = field_validators.missing_where_paths(tmp_path, ["a.py"])

        assert missing == []

    def test_missing_path_returned(self, tmp_path):
        missing = field_validators.missing_where_paths(tmp_path, ["does-not-exist.py"])

        assert missing == ["does-not-exist.py"]

    def test_mixed_existing_and_missing(self, tmp_path):
        existing = tmp_path / "a.py"
        existing.write_text("", encoding="utf-8")

        missing = field_validators.missing_where_paths(
            tmp_path, ["a.py", "b.py", "c.py"]
        )

        assert missing == ["b.py", "c.py"]

    def test_empty_tokens_returns_empty(self, tmp_path):
        assert field_validators.missing_where_paths(tmp_path, []) == []

    def test_blank_token_skipped(self, tmp_path):
        assert field_validators.missing_where_paths(tmp_path, [""]) == []

    def test_read_marker_stripped_before_existence_check(self, tmp_path):
        existing = tmp_path / "a.py"
        existing.write_text("", encoding="utf-8")

        missing = field_validators.missing_where_paths(tmp_path, ["a.py::read"])

        assert missing == []

    def test_read_marker_preserved_in_missing_output(self, tmp_path):
        missing = field_validators.missing_where_paths(tmp_path, ["b.py::read"])

        assert missing == ["b.py::read"]

    def test_existing_directory_is_not_missing(self, tmp_path):
        directory = tmp_path / "subdir"
        directory.mkdir()

        missing = field_validators.missing_where_paths(tmp_path, ["subdir/"])

        assert missing == []

    def test_preserves_input_order(self, tmp_path):
        missing = field_validators.missing_where_paths(
            tmp_path, ["z-missing.py", "y-missing.py"]
        )

        assert missing == ["z-missing.py", "y-missing.py"]
