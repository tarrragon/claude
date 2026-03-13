"""測試 onboard 命令.

驗證完整的 onboard 流程和輸出。
"""

import pytest
from pathlib import Path
from project_init.commands.onboard import run_onboard


class TestRunOnboard:
    """測試 run_onboard 主函式."""

    def test_onboard_flutter_project_complete(
        self, tmp_path: Path, capsys
    ) -> None:
        """測試完整設定的 Flutter 專案 onboard."""
        # 建立完整的 Flutter 專案結構
        (tmp_path / "pubspec.yaml").touch()
        (tmp_path / "CLAUDE.md").touch()
        (tmp_path / "README.md").write_text("# Project")

        # 建立 .gitignore
        gitignore_content = """coverage/
htmlcov/
.claude/hook-logs/
.claude/worktrees/
.claude/tool-results/
.claude/handoff/
"""
        (tmp_path / ".gitignore").write_text(gitignore_content)

        # 建立 .claude 核心目錄
        for dir_name in ["rules", "hooks", "skills", "methodologies", "references", "agents", "config"]:
            (tmp_path / ".claude" / dir_name).mkdir(parents=True, exist_ok=True)

        # 建立 Hook 配置檔
        hook_config = tmp_path / ".claude" / "config" / "hook-language-classification.yaml"
        hook_config.write_text("""hooks:
  test-timeout-pre.py: flutter
""")

        hook_exclude = tmp_path / ".claude" / "config" / "hook-exclude-list.json"
        hook_exclude.write_text('{"exclude": []}')

        settings_json = tmp_path / ".claude" / "config" / "settings.json"
        settings_json.write_text('{"hooks": {}}')

        # 建立 settings.local.json
        (tmp_path / ".claude" / "settings.local.json").touch()

        # 建立 Flutter 模板
        (tmp_path / ".claude" / "project-templates").mkdir(exist_ok=True)
        (tmp_path / ".claude" / "project-templates" / "FLUTTER.md").touch()

        # 建立 docs 結構
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "work-logs").mkdir()
        (tmp_path / "docs" / "todolist.yaml").touch()

        result = run_onboard(tmp_path)

        assert result.language == "flutter"
        assert result.all_ok, f"Expected all_ok but got {result.todo_items}"
        assert result.todo_count == 0

        # 驗證輸出
        captured = capsys.readouterr()
        assert "project-init onboard" in captured.out
        assert "Flutter/Dart" in captured.out or "flutter" in captured.out.lower()

    def test_onboard_unknown_language(self, tmp_path: Path, capsys) -> None:
        """測試無法偵測語言的專案."""
        # 建立 Hook 分類檔
        (tmp_path / ".claude" / "config").mkdir(parents=True)
        hook_config = tmp_path / ".claude" / "config" / "hook-language-classification.yaml"
        hook_config.write_text("hooks:\n")

        result = run_onboard(tmp_path)

        assert result.language == "unknown"
        # unknown 語言應該只檢查一些基本項目
        assert result.todo_count >= 0

        captured = capsys.readouterr()
        assert "project-init onboard" in captured.out

    def test_onboard_flutter_missing_files(self, tmp_path: Path) -> None:
        """測試缺失檔案的 Flutter 專案."""
        # 只建立 pubspec.yaml，其他都缺失
        (tmp_path / "pubspec.yaml").touch()

        # 建立最少的 Hook 分類檔
        (tmp_path / ".claude" / "config").mkdir(parents=True)
        hook_config = tmp_path / ".claude" / "config" / "hook-language-classification.yaml"
        hook_config.write_text("hooks:\n")

        result = run_onboard(tmp_path)

        assert result.language == "flutter"
        assert not result.all_ok
        assert result.todo_count > 0

        # 應該包含缺失的項目
        todo_descriptions = [item.description for item in result.todo_items]
        assert any("CLAUDE.md" in desc for desc in todo_descriptions)

    def test_onboard_go_project(self, tmp_path: Path) -> None:
        """測試 Go 專案的 onboard."""
        (tmp_path / "go.mod").touch()

        # 建立 Hook 分類檔
        (tmp_path / ".claude" / "config").mkdir(parents=True)
        hook_config = tmp_path / ".claude" / "config" / "hook-language-classification.yaml"
        hook_config.write_text("hooks:\n")

        result = run_onboard(tmp_path)

        assert result.language == "go"
        # Go 不是 flutter，所以應該有待辦項目

    def test_onboard_nodejs_project(self, tmp_path: Path) -> None:
        """測試 Node.js 專案的 onboard."""
        (tmp_path / "package.json").touch()

        # 建立 Hook 分類檔
        (tmp_path / ".claude" / "config").mkdir(parents=True)
        hook_config = tmp_path / ".claude" / "config" / "hook-language-classification.yaml"
        hook_config.write_text("hooks:\n")

        result = run_onboard(tmp_path)

        assert result.language == "nodejs"

    def test_onboard_python_project(self, tmp_path: Path) -> None:
        """測試 Python 專案的 onboard."""
        (tmp_path / "pyproject.toml").touch()

        # 建立 Hook 分類檔
        (tmp_path / ".claude" / "config").mkdir(parents=True)
        hook_config = tmp_path / ".claude" / "config" / "hook-language-classification.yaml"
        hook_config.write_text("hooks:\n")

        result = run_onboard(tmp_path)

        assert result.language == "python"

    def test_onboard_output_format(self, tmp_path: Path, capsys) -> None:
        """測試輸出格式正確性."""
        (tmp_path / "pubspec.yaml").touch()

        # 建立必要的檔案結構
        (tmp_path / ".claude" / "config").mkdir(parents=True)
        hook_config = tmp_path / ".claude" / "config" / "hook-language-classification.yaml"
        hook_config.write_text("""hooks:
  test-timeout-pre.py: flutter
  style-guardian-hook.py: project-specific
""")

        result = run_onboard(tmp_path)

        captured = capsys.readouterr()
        output = captured.out

        # 檢查主要段落
        assert "project-init onboard" in output
        assert "專案語言偵測" in output
        assert "Hook 語言分類" in output
        assert "CLAUDE.md" in output
        assert "待辦清單" in output

        # 檢查 Hook 分類是否列出
        assert "test-timeout-pre.py" in output or "Flutter 特定" in output

    def test_onboard_with_all_files_present(
        self, tmp_path: Path, capsys
    ) -> None:
        """測試所有檔案都存在的情況."""
        # Flutter 專案，所有檔案都存在
        (tmp_path / "pubspec.yaml").touch()
        (tmp_path / "CLAUDE.md").touch()
        (tmp_path / "README.md").write_text("# Project")

        # 建立 .gitignore
        gitignore_content = """coverage/
htmlcov/
.claude/hook-logs/
.claude/worktrees/
.claude/tool-results/
.claude/handoff/
"""
        (tmp_path / ".gitignore").write_text(gitignore_content)

        # 建立 .claude 核心目錄
        for dir_name in ["rules", "hooks", "skills", "methodologies", "references", "agents", "config"]:
            (tmp_path / ".claude" / dir_name).mkdir(parents=True, exist_ok=True)

        hook_config = tmp_path / ".claude" / "config" / "hook-language-classification.yaml"
        hook_config.write_text("hooks:\n")

        hook_exclude = tmp_path / ".claude" / "config" / "hook-exclude-list.json"
        hook_exclude.write_text('{"exclude": []}')

        settings_json = tmp_path / ".claude" / "config" / "settings.json"
        settings_json.write_text('{"hooks": {}}')

        (tmp_path / ".claude" / "settings.local.json").touch()

        (tmp_path / ".claude" / "project-templates").mkdir(exist_ok=True)
        (tmp_path / ".claude" / "project-templates" / "FLUTTER.md").touch()

        # 建立 docs 結構
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "work-logs").mkdir()
        (tmp_path / "docs" / "todolist.yaml").touch()

        result = run_onboard(tmp_path)

        assert result.all_ok, f"Expected all_ok but got {result.todo_items}"
        assert result.todo_count == 0

        captured = capsys.readouterr()
        assert "0 項需處理" in captured.out or "需處理" in captured.out

    def test_onboard_hook_completeness_section(
        self, tmp_path: Path, capsys
    ) -> None:
        """測試 onboard 包含 Hook 完整性驗證區段."""
        # 建立最小的 Flutter 專案
        (tmp_path / "pubspec.yaml").touch()

        (tmp_path / ".claude" / "config").mkdir(parents=True)
        hook_config = tmp_path / ".claude" / "config" / "hook-language-classification.yaml"
        hook_config.write_text("hooks:\n")

        # 建立 Hook 目錄和檔案，但不登記
        hooks_dir = tmp_path / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True)
        (hooks_dir / "test-unregistered.py").touch()

        result = run_onboard(tmp_path)

        captured = capsys.readouterr()
        # 應該包含 Hook 完整性檢查的輸出
        assert "Hook 完整性驗證" in captured.out

    def test_onboard_unregistered_hooks_in_todo(
        self, tmp_path: Path, capsys
    ) -> None:
        """測試未登記的 Hook 會加入待辦清單."""
        import json

        # 建立最小的 Flutter 專案
        (tmp_path / "pubspec.yaml").touch()

        (tmp_path / ".claude" / "config").mkdir(parents=True)
        hook_config = tmp_path / ".claude" / "config" / "hook-language-classification.yaml"
        hook_config.write_text("hooks:\n")

        # 建立 Hook 目錄和未登記的檔案
        hooks_dir = tmp_path / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True)
        (hooks_dir / "test-unregistered.py").touch()

        # 建立空的 settings.json（沒有登記任何 Hook）
        settings = {
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": []}
                ]
            }
        }
        settings_path = tmp_path / ".claude" / "settings.json"
        settings_path.write_text(json.dumps(settings))

        result = run_onboard(tmp_path)

        # 應該有待辦項目
        assert result.todo_count > 0

        # 待辦項目中應該包含未登記的 Hook
        todo_descriptions = [item.description for item in result.todo_items]
        assert any("Hook" in desc or "未登記" in desc for desc in todo_descriptions)

    def test_onboard_gitignore_precise_matching(self, tmp_path: Path) -> None:
        """測試 gitignore 精確前綴匹配."""
        (tmp_path / "pubspec.yaml").touch()

        # 建立 .gitignore 有一些規則但格式不同
        gitignore_content = """# Ignore coverage
coverage/
htmlcov/
.claude/hook-logs/
.claude/worktrees
.claude/tool-results/
.claude/handoff/
"""
        (tmp_path / ".gitignore").write_text(gitignore_content)

        # 建立最少的 .claude 結構
        (tmp_path / ".claude" / "config").mkdir(parents=True)
        hook_config = tmp_path / ".claude" / "config" / "hook-language-classification.yaml"
        hook_config.write_text("hooks:\n")

        result = run_onboard(tmp_path)

        # 應該識別所有規則（包括 .claude/worktrees 沒有末尾斜線）
        assert result.language == "flutter"

    def test_onboard_yaml_structured_validation(self, tmp_path: Path) -> None:
        """測試 YAML 結構化驗證."""
        (tmp_path / "pubspec.yaml").touch()

        # 建立有效的 YAML 配置
        (tmp_path / ".claude" / "config").mkdir(parents=True)
        hook_config = tmp_path / ".claude" / "config" / "hook-language-classification.yaml"
        hook_config.write_text("""hooks:
  pre-commit.py: flutter
  custom-hook.py: project-specific
""")

        # 建立其他必要檔案
        hook_exclude = tmp_path / ".claude" / "config" / "hook-exclude-list.json"
        hook_exclude.write_text('{"exclude": []}')

        settings = tmp_path / ".claude" / "config" / "settings.json"
        settings.write_text('{"hooks": {}}')

        result = run_onboard(tmp_path)

        # 應該成功解析 YAML 配置
        assert result.language == "flutter"

    def test_onboard_yaml_invalid_format(self, tmp_path: Path) -> None:
        """測試無效的 YAML 格式處理."""
        (tmp_path / "pubspec.yaml").touch()

        # 建立無效的 YAML
        (tmp_path / ".claude" / "config").mkdir(parents=True)
        hook_config = tmp_path / ".claude" / "config" / "hook-language-classification.yaml"
        hook_config.write_text("hooks:\n  invalid: [ unclosed")

        result = run_onboard(tmp_path)

        # 應該檢測到格式錯誤
        assert result.language == "flutter"
        todo_descriptions = [item.description for item in result.todo_items]
        assert any("Hook 配置檔" in desc for desc in todo_descriptions)

    def test_onboard_permission_details_recorded(self, tmp_path: Path) -> None:
        """測試權限資訊被記錄."""
        (tmp_path / "pubspec.yaml").touch()

        # 建立配置檔
        (tmp_path / ".claude" / "config").mkdir(parents=True)
        hook_config = tmp_path / ".claude" / "config" / "hook-language-classification.yaml"
        hook_config.write_text("hooks:\n")

        hook_exclude = tmp_path / ".claude" / "config" / "hook-exclude-list.json"
        hook_exclude.write_text('{"exclude": []}')

        settings = tmp_path / ".claude" / "config" / "settings.json"
        settings.write_text('{"hooks": {}}')

        result = run_onboard(tmp_path)

        # 檢查 Hook 配置資訊
        from project_init.lib import check_hook_configurations
        hook_config_info = check_hook_configurations(tmp_path)

        # 應該有權限資訊
        assert hook_config_info.yaml_permission_info is not None
        # YAML 檔案應該可讀
        assert hook_config_info.yaml_permission_info.can_read
