"""
測試 1.2.0-W1-031：+build 後綴剝離 + monorepo in-dev 版本偵測

涵蓋兩項回歸：
1. preflight 對 `X.Y.Z+build`（Flutter pubspec build number）崩潰
   （int("0+2") -> ValueError）
2. 版本源落後開發中 worklog 版本時誤採落後版本
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from version_release import (
    strip_build_metadata,
    detect_indev_worklog_version,
    normalize_version,
    compare_semantic_versions,
    check_previous_versions_completed,
)


class TestStripBuildMetadata:

    def test_strips_flutter_build_number(self):
        assert strip_build_metadata("1.1.0+2") == "1.1.0"

    def test_plain_version_unchanged(self):
        assert strip_build_metadata("1.2.0") == "1.2.0"

    def test_strips_prerelease_and_build(self):
        assert strip_build_metadata("1.0.0-rc1+5") == "1.0.0"

    def test_strips_prerelease_only(self):
        assert strip_build_metadata("2.0.0-beta") == "2.0.0"

    def test_none_passthrough(self):
        assert strip_build_metadata(None) is None

    def test_empty_passthrough(self):
        assert strip_build_metadata("") == ""


class TestNormalizeVersionWithBuild:

    def test_normalize_strips_build(self):
        assert normalize_version("1.1.0+2") == "1.1.0"

    def test_normalize_two_part_with_build(self):
        # X.Y+build -> 先剝離 -> X.Y -> 補 .0
        assert normalize_version("1.2+3") == "1.2.0"


class TestCompareSemanticVersionsWithBuild:

    def test_compare_with_build_suffix(self):
        # 1.1.0+2 與 1.1.0 應視為相等
        assert compare_semantic_versions("1.1.0+2", "1.1.0") == 0

    def test_compare_indev_ahead(self):
        assert compare_semantic_versions("1.2.0", "1.1.0+2") == 1


class TestCheckPreviousVersionsBuildSuffix:
    """回歸：+build 後綴不再導致 int("0+2") 崩潰。"""

    def test_no_crash_with_build_suffix(self, tmp_path, monkeypatch):
        import version_release
        # 無 work-logs 目錄時應正常回傳 (True, [])，不崩潰
        monkeypatch.setattr(version_release, "get_project_root", lambda: tmp_path)
        ok, errors = check_previous_versions_completed("1.1.0+2")
        assert ok is True
        assert errors == []


class TestDetectIndevWorklogVersion:

    PATTERN = "docs/work-logs/v{major}/v{major_minor}/v{version}"

    def test_detects_nested_indev_version(self, tmp_path):
        nested = tmp_path / "docs" / "work-logs" / "v1" / "v1.2" / "v1.2.0"
        nested.mkdir(parents=True)
        assert detect_indev_worklog_version(tmp_path, self.PATTERN) == "1.2.0"

    def test_picks_highest_version(self, tmp_path):
        base = tmp_path / "docs" / "work-logs"
        (base / "v1" / "v1.1" / "v1.1.0").mkdir(parents=True)
        (base / "v1" / "v1.2" / "v1.2.0").mkdir(parents=True)
        assert detect_indev_worklog_version(tmp_path, self.PATTERN) == "1.2.0"

    def test_flat_structure(self, tmp_path):
        (tmp_path / "docs" / "work-logs" / "v1.2.0").mkdir(parents=True)
        assert detect_indev_worklog_version(tmp_path, self.PATTERN) == "1.2.0"

    def test_no_worklog_returns_none(self, tmp_path):
        assert detect_indev_worklog_version(tmp_path, self.PATTERN) is None
