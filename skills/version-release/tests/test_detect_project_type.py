"""
測試 detect_project_type() 函式 - 專案類型自動偵測
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from version_release import (
    detect_project_type,
    PROJECT_TYPE_FLUTTER,
    PROJECT_TYPE_GO,
    PROJECT_TYPE_CHROME_EXT,
    PROJECT_TYPE_PHP,
    PROJECT_TYPE_NPM,
    PROJECT_TYPE_PYTHON,
    PROJECT_TYPE_MONOREPO,
    PROJECT_TYPE_UNKNOWN,
)


class TestDetectProjectType:

    def test_flutter_project(self, tmp_path):
        (tmp_path / "pubspec.yaml").write_text("name: my_app\nversion: 1.0.0\n")
        assert detect_project_type(tmp_path) == PROJECT_TYPE_FLUTTER

    def test_go_project(self, tmp_path):
        (tmp_path / "go.mod").write_text("module example.com/foo\n")
        assert detect_project_type(tmp_path) == PROJECT_TYPE_GO

    def test_chrome_ext_project(self, tmp_path):
        (tmp_path / "package.json").write_text('{"name":"ext","version":"1.0.0"}')
        (tmp_path / "manifest.json").write_text('{"manifest_version":3,"version":"1.0.0"}')
        assert detect_project_type(tmp_path) == PROJECT_TYPE_CHROME_EXT

    def test_php_project(self, tmp_path):
        (tmp_path / "composer.json").write_text('{"name":"vendor/pkg"}')
        assert detect_project_type(tmp_path) == PROJECT_TYPE_PHP

    def test_npm_project(self, tmp_path):
        (tmp_path / "package.json").write_text('{"name":"my-pkg","version":"1.0.0"}')
        assert detect_project_type(tmp_path) == PROJECT_TYPE_NPM

    def test_python_project(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "foo"\nversion = "1.0.0"\n')
        assert detect_project_type(tmp_path) == PROJECT_TYPE_PYTHON

    def test_monorepo_with_subproject(self, tmp_path):
        sub = tmp_path / "ui"
        sub.mkdir()
        (sub / "pubspec.yaml").write_text("name: ui\nversion: 1.0.0\n")
        assert detect_project_type(tmp_path) == PROJECT_TYPE_MONOREPO

    def test_monorepo_go_subproject(self, tmp_path):
        sub = tmp_path / "server"
        sub.mkdir()
        (sub / "go.mod").write_text("module example.com/server\n")
        assert detect_project_type(tmp_path) == PROJECT_TYPE_MONOREPO

    def test_unknown_empty_dir(self, tmp_path):
        assert detect_project_type(tmp_path) == PROJECT_TYPE_UNKNOWN

    def test_unknown_no_version_files(self, tmp_path):
        (tmp_path / "README.md").write_text("# Hello")
        (tmp_path / "src").mkdir()
        assert detect_project_type(tmp_path) == PROJECT_TYPE_UNKNOWN


class TestDetectProjectTypePriority:

    def test_flutter_over_npm(self, tmp_path):
        """pubspec.yaml 優先於 package.json"""
        (tmp_path / "pubspec.yaml").write_text("name: app\nversion: 1.0.0\n")
        (tmp_path / "package.json").write_text('{"name":"app","version":"1.0.0"}')
        assert detect_project_type(tmp_path) == PROJECT_TYPE_FLUTTER

    def test_go_over_npm(self, tmp_path):
        """go.mod 優先於 package.json"""
        (tmp_path / "go.mod").write_text("module example.com/foo\n")
        (tmp_path / "package.json").write_text('{"name":"app","version":"1.0.0"}')
        assert detect_project_type(tmp_path) == PROJECT_TYPE_GO

    def test_php_over_npm(self, tmp_path):
        """composer.json 優先於 package.json"""
        (tmp_path / "composer.json").write_text('{"name":"vendor/pkg"}')
        (tmp_path / "package.json").write_text('{"name":"app","version":"1.0.0"}')
        assert detect_project_type(tmp_path) == PROJECT_TYPE_PHP


class TestDetectProjectTypeStderr:

    def test_stderr_output_for_detected_type(self, tmp_path, capsys):
        (tmp_path / "package.json").write_text('{"name":"app","version":"1.0.0"}')
        detect_project_type(tmp_path)
        captured = capsys.readouterr()
        assert "[INFO]" in captured.err
        assert "npm" in captured.err
        assert captured.out == ""

    def test_stderr_output_for_unknown(self, tmp_path, capsys):
        detect_project_type(tmp_path)
        captured = capsys.readouterr()
        assert "[INFO]" in captured.err
        assert "unknown" in captured.err
        assert ".version-release.yaml" in captured.err
        assert captured.out == ""

    def test_no_stdout_pollution(self, tmp_path, capsys):
        (tmp_path / "pubspec.yaml").write_text("name: app\n")
        detect_project_type(tmp_path)
        captured = capsys.readouterr()
        assert captured.out == ""


class TestDetectProjectTypeMonorepoEdgeCases:

    def test_hidden_dirs_ignored(self, tmp_path):
        """隱藏目錄（.開頭）不參與 monorepo 偵測"""
        hidden = tmp_path / ".cache"
        hidden.mkdir()
        (hidden / "package.json").write_text('{"name":"cache"}')
        assert detect_project_type(tmp_path) == PROJECT_TYPE_UNKNOWN

    def test_files_not_dirs_ignored(self, tmp_path):
        """根目錄的普通檔案不觸發 monorepo 偵測"""
        (tmp_path / "some_file").write_text("not a dir")
        assert detect_project_type(tmp_path) == PROJECT_TYPE_UNKNOWN

    def test_nested_depth_2_not_detected(self, tmp_path):
        """深度 > 1 的子目錄不觸發 monorepo"""
        deep = tmp_path / "a" / "b"
        deep.mkdir(parents=True)
        (deep / "package.json").write_text('{"name":"deep"}')
        assert detect_project_type(tmp_path) == PROJECT_TYPE_UNKNOWN
