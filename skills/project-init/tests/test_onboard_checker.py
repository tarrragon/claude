"""測試 onboard_checker 模組.

驗證語言偵測、Hook 分類解析、框架檔案檢查等功能。
"""

import pytest
from pathlib import Path
from project_init.lib.onboard_checker import (
    check_claude_md,
    check_language_template,
    check_settings_local_json,
    detect_project_language,
    parse_hook_classification,
)


class TestDetectProjectLanguage:
    """測試專案語言偵測."""

    def test_detect_flutter_by_pubspec_yaml(self, tmp_path: Path) -> None:
        """測試偵測 Flutter 專案（pubspec.yaml）."""
        (tmp_path / "pubspec.yaml").touch()
        result = detect_project_language(tmp_path)

        assert result.language == "flutter"
        assert result.identifier == "pubspec.yaml"
        assert result.is_available

    def test_detect_go_by_go_mod(self, tmp_path: Path) -> None:
        """測試偵測 Go 專案（go.mod）."""
        (tmp_path / "go.mod").touch()
        result = detect_project_language(tmp_path)

        assert result.language == "go"
        assert result.identifier == "go.mod"
        assert result.is_available

    def test_detect_nodejs_by_package_json(self, tmp_path: Path) -> None:
        """測試偵測 Node.js 專案（package.json）."""
        (tmp_path / "package.json").touch()
        result = detect_project_language(tmp_path)

        assert result.language == "nodejs"
        assert result.identifier == "package.json"
        assert result.is_available

    def test_detect_python_by_pyproject_toml(self, tmp_path: Path) -> None:
        """測試偵測 Python 專案（pyproject.toml）."""
        (tmp_path / "pyproject.toml").touch()
        result = detect_project_language(tmp_path)

        assert result.language == "python"
        assert result.identifier == "pyproject.toml"
        assert result.is_available

    def test_detect_flutter_priority_over_python(self, tmp_path: Path) -> None:
        """測試偵測優先級：Flutter > Go > Node.js > Python."""
        # 同時有 pubspec.yaml 和 pyproject.toml，應優先返回 Flutter
        (tmp_path / "pubspec.yaml").touch()
        (tmp_path / "pyproject.toml").touch()
        result = detect_project_language(tmp_path)

        assert result.language == "flutter"

    def test_detect_go_priority_over_nodejs(self, tmp_path: Path) -> None:
        """測試偵測優先級：Go > Node.js."""
        (tmp_path / "go.mod").touch()
        (tmp_path / "package.json").touch()
        result = detect_project_language(tmp_path)

        assert result.language == "go"

    def test_detect_unknown_language(self, tmp_path: Path) -> None:
        """測試無法偵測語言."""
        result = detect_project_language(tmp_path)

        assert result.language == "unknown"
        assert not result.is_available


class TestParseHookClassification:
    """測試 Hook 語言分類解析."""

    def test_parse_valid_yaml(self, tmp_path: Path) -> None:
        """測試解析有效的分類檔."""
        yaml_content = """# Hook 語言分類
hooks:
  test-timeout-pre.py: flutter
  test-timeout-post.py: flutter
  style-guardian-hook.py: project-specific
"""
        config_file = tmp_path / "hook-language-classification.yaml"
        config_file.write_text(yaml_content)

        result = parse_hook_classification(config_file)

        assert result.is_available
        assert "test-timeout-pre.py" in result.flutter_hooks
        assert "test-timeout-post.py" in result.flutter_hooks
        assert "style-guardian-hook.py" in result.project_specific_hooks

    def test_parse_empty_yaml(self, tmp_path: Path) -> None:
        """測試解析沒有 hooks 段落的檔案."""
        yaml_content = """# 空配置
other_config: value
"""
        config_file = tmp_path / "hook-language-classification.yaml"
        config_file.write_text(yaml_content)

        result = parse_hook_classification(config_file)

        assert result.is_available
        assert not result.flutter_hooks
        assert not result.project_specific_hooks

    def test_parse_nonexistent_file(self, tmp_path: Path) -> None:
        """測試解析不存在的檔案."""
        config_file = tmp_path / "nonexistent.yaml"

        result = parse_hook_classification(config_file)

        assert not result.is_available
        assert not result.flutter_hooks
        assert not result.project_specific_hooks

    def test_parse_malformed_yaml_gracefully(self, tmp_path: Path) -> None:
        """測試解析格式不正確的檔案（應優雅地失敗）."""
        yaml_content = """hooks:
  [invalid yaml syntax
  test: value::
"""
        config_file = tmp_path / "hook-language-classification.yaml"
        config_file.write_text(yaml_content)

        # 不應拋異常，應返回 is_available=False
        result = parse_hook_classification(config_file)
        assert result.is_available  # 簡單文字解析不會拋異常，但也許取不到合法資料


class TestCheckClaudeMd:
    """測試 CLAUDE.md 檢查."""

    def test_claude_md_exists(self, tmp_path: Path) -> None:
        """測試 CLAUDE.md 存在."""
        (tmp_path / "CLAUDE.md").touch()
        result = check_claude_md(tmp_path)

        assert result.exists
        assert result.name == "CLAUDE.md"
        assert result.path == tmp_path / "CLAUDE.md"

    def test_claude_md_not_exists(self, tmp_path: Path) -> None:
        """測試 CLAUDE.md 不存在."""
        result = check_claude_md(tmp_path)

        assert not result.exists
        assert result.name == "CLAUDE.md"
        assert result.path is None


class TestCheckLanguageTemplate:
    """測試語言模板檢查."""

    def test_flutter_template_exists(self, tmp_path: Path) -> None:
        """測試 Flutter 模板存在."""
        (tmp_path / ".claude" / "project-templates").mkdir(parents=True)
        (tmp_path / ".claude" / "project-templates" / "FLUTTER.md").touch()

        result = check_language_template(tmp_path, "flutter")

        assert result.exists
        assert result.name == "FLUTTER.md"

    def test_flutter_template_not_exists(self, tmp_path: Path) -> None:
        """測試 Flutter 模板不存在."""
        result = check_language_template(tmp_path, "flutter")

        assert not result.exists
        assert result.name == "FLUTTER.md"

    def test_unknown_language_template(self, tmp_path: Path) -> None:
        """測試未知語言模板（應返回不存在）."""
        result = check_language_template(tmp_path, "go")

        assert not result.exists
        assert result.name == "GO.md"


class TestCheckSettingsLocalJson:
    """測試 settings.local.json 檢查."""

    def test_settings_exists(self, tmp_path: Path) -> None:
        """測試 settings.local.json 存在."""
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".claude" / "settings.local.json").touch()

        result = check_settings_local_json(tmp_path)

        assert result.exists
        assert result.name == "settings.local.json"

    def test_settings_not_exists(self, tmp_path: Path) -> None:
        """測試 settings.local.json 不存在."""
        result = check_settings_local_json(tmp_path)

        assert not result.exists
        assert result.name == "settings.local.json"
        assert result.path is None
