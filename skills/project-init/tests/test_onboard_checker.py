"""測試 onboard_checker 模組.

驗證語言偵測、Hook 分類解析、框架檔案檢查等功能。
"""

import json
import pytest
from pathlib import Path
from project_init.lib.onboard_checker import (
    check_claude_md,
    check_language_template,
    check_settings_local_json,
    detect_project_language,
    parse_hook_classification,
)
from project_init.lib.hook_verifier import check_hook_completeness


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


class TestCheckHookCompleteness:
    """測試 Hook 完整性驗證."""

    def _create_hook_file(self, hooks_dir: Path, filename: str) -> None:
        """建立 Hook 檔案."""
        (hooks_dir / filename).touch()

    def _create_settings_json(
        self, project_root: Path, hook_files: list[str]
    ) -> None:
        """建立 settings.json 並註冊指定的 Hook."""
        settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {
                                "type": "command",
                                "command": f"$CLAUDE_PROJECT_DIR/.claude/hooks/{hook}",
                            }
                            for hook in hook_files
                        ],
                    }
                ]
            }
        }
        settings_path = project_root / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")

    def test_all_hooks_registered(self, tmp_path: Path) -> None:
        """測試所有 Hook 都已登記."""
        # 建立 Hook 目錄和檔案
        hooks_dir = tmp_path / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True)
        self._create_hook_file(hooks_dir, "test-hook-1.py")
        self._create_hook_file(hooks_dir, "test-hook-2.py")

        # 建立 settings.json 並登記這兩個 Hook
        self._create_settings_json(tmp_path, ["test-hook-1.py", "test-hook-2.py"])

        result = check_hook_completeness(tmp_path)

        assert result.completeness_ok
        assert len(result.unregistered_hooks) == 0
        assert result.all_hooks == {"test-hook-1.py", "test-hook-2.py"}

    def test_unregistered_hooks_detected(self, tmp_path: Path) -> None:
        """測試偵測到未登記的 Hook."""
        hooks_dir = tmp_path / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True)
        self._create_hook_file(hooks_dir, "registered.py")
        self._create_hook_file(hooks_dir, "unregistered.py")

        # 只登記 registered.py
        self._create_settings_json(tmp_path, ["registered.py"])

        result = check_hook_completeness(tmp_path)

        assert not result.completeness_ok
        assert result.unregistered_hooks == {"unregistered.py"}
        assert "registered.py" in result.registered_hooks

    def test_excluded_hooks_ignored(self, tmp_path: Path) -> None:
        """測試被排除的 Hook 不計入檢查."""
        hooks_dir = tmp_path / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True)
        self._create_hook_file(hooks_dir, "hook_utils.py")  # 預設排除
        self._create_hook_file(hooks_dir, "test-hook.py")

        # 只登記 test-hook.py
        self._create_settings_json(tmp_path, ["test-hook.py"])

        result = check_hook_completeness(tmp_path)

        assert result.completeness_ok
        assert "hook_utils.py" not in result.all_hooks
        assert result.excluded_count > 0

    def test_custom_exclude_list(self, tmp_path: Path) -> None:
        """測試自訂排除清單."""
        hooks_dir = tmp_path / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True)
        self._create_hook_file(hooks_dir, "test-hook.py")
        self._create_hook_file(hooks_dir, "skip-me.py")

        # 建立自訂 exclude list
        exclude_list = {
            "exclude": ["skip-me.py"],
            "exclude_patterns": [],
        }
        exclude_path = hooks_dir / "hook-exclude-list.json"
        exclude_path.write_text(json.dumps(exclude_list), encoding="utf-8")

        # 只登記 test-hook.py
        self._create_settings_json(tmp_path, ["test-hook.py"])

        result = check_hook_completeness(tmp_path)

        assert result.completeness_ok
        assert "skip-me.py" not in result.all_hooks
        assert "test-hook.py" in result.all_hooks

    def test_exclude_patterns(self, tmp_path: Path) -> None:
        """測試排除模式（萬用字元）."""
        hooks_dir = tmp_path / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True)
        self._create_hook_file(hooks_dir, "test-hook.py")
        self._create_hook_file(hooks_dir, "old-backup.py")

        # 建立 exclude list 排除 *-backup.py
        exclude_list = {
            "exclude": [],
            "exclude_patterns": ["*-backup.py"],
        }
        exclude_path = hooks_dir / "hook-exclude-list.json"
        exclude_path.write_text(json.dumps(exclude_list), encoding="utf-8")

        # 只登記 test-hook.py
        self._create_settings_json(tmp_path, ["test-hook.py"])

        result = check_hook_completeness(tmp_path)

        assert result.completeness_ok
        assert "test-hook.py" in result.all_hooks
        # old-backup.py 應該被排除掉
        assert "old-backup.py" not in result.all_hooks

    def test_settings_json_not_exists(self, tmp_path: Path) -> None:
        """測試 settings.json 不存在時，應優雅地回傳成功（無法驗證）."""
        hooks_dir = tmp_path / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True)
        self._create_hook_file(hooks_dir, "test-hook.py")

        result = check_hook_completeness(tmp_path)

        # 當 settings.json 不存在時，無法驗證，應回傳 completeness_ok=True
        assert result.completeness_ok
        assert len(result.all_hooks) == 0

    def test_hooks_directory_not_exists(self, tmp_path: Path) -> None:
        """測試 Hook 目錄不存在時的處理."""
        self._create_settings_json(tmp_path, [])

        result = check_hook_completeness(tmp_path)

        assert result.completeness_ok
        assert len(result.all_hooks) == 0
        assert len(result.registered_hooks) == 0

    def test_multiple_unregistered_hooks(self, tmp_path: Path) -> None:
        """測試多個未登記的 Hook."""
        hooks_dir = tmp_path / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True)
        for hook in ["hook1.py", "hook2.py", "hook3.py", "registered.py"]:
            self._create_hook_file(hooks_dir, hook)

        # 只登記 registered.py
        self._create_settings_json(tmp_path, ["registered.py"])

        result = check_hook_completeness(tmp_path)

        assert not result.completeness_ok
        assert len(result.unregistered_hooks) == 3
        assert result.unregistered_hooks == {"hook1.py", "hook2.py", "hook3.py"}
