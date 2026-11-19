"""
Unit tests for wrap-skill-yaml-consistency-hook.py

驗收項目：
  AC3 Version 非回退：YAML version 與 SKILL footer Version 各自 >= git HEAD（警告級）
  （AC1/AC2/AC4 與映射檔依賴已移除）

測試策略：
  - 直接 import hook module 測純函式（不需 stdin / settings.json）
  - 使用 tmp_path 建立 fake project root + 各檔案內容變體
"""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ============================================================================
# 動態載入 hook（檔名含 dash，無法直接 import）
# ============================================================================

HOOK_PATH = (
    Path(__file__).resolve().parents[2] / "skills" / "wrap-decision" / "hooks" / "wrap-skill-yaml-consistency-hook.py"
)


@pytest.fixture(scope="module")
def hook_module():
    spec = importlib.util.spec_from_file_location(
        "wrap_skill_yaml_consistency_hook", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["wrap_skill_yaml_consistency_hook"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def logger():
    return MagicMock()


# ============================================================================
# AC3：Version 非回退檢查
# ============================================================================

class TestVersionNoRegress:
    def _setup_project(self, tmp_path: Path, yaml_content: str, skill_content: str):
        (tmp_path / ".claude" / "config").mkdir(parents=True)
        (tmp_path / ".claude" / "skills" / "wrap-decision").mkdir(parents=True)
        (tmp_path / ".claude" / "config" / "wrap-triggers.yaml").write_text(
            yaml_content, encoding="utf-8"
        )
        (tmp_path / ".claude" / "skills" / "wrap-decision" / "SKILL.md").write_text(
            skill_content, encoding="utf-8"
        )

    def test_no_git_history_no_warning(self, hook_module, logger, tmp_path):
        """當 git show 失敗（無 HEAD），返回空 warnings。"""
        self._setup_project(
            tmp_path,
            'version: "1.2.0"\n',
            "# SKILL\n\n**Version**: 2.3.0\n",
        )
        with patch.object(hook_module, "_git_show", return_value=None):
            warnings = hook_module.check_version_no_regress(tmp_path, logger)
        assert warnings == []

    def test_yaml_version_regress_warns(self, hook_module, logger, tmp_path):
        self._setup_project(
            tmp_path,
            'version: "1.0.0"\n',  # current
            "# SKILL\n\n**Version**: 2.3.0\n",
        )

        def fake_git_show(rev, rel_path, _root):
            if rel_path.endswith("wrap-triggers.yaml"):
                return 'version: "1.2.0"\n'  # HEAD higher
            return "# SKILL\n\n**Version**: 2.3.0\n"

        with patch.object(hook_module, "_git_show", side_effect=fake_git_show):
            warnings = hook_module.check_version_no_regress(tmp_path, logger)
        assert any("AC3" in w and "1.0.0" in w and "1.2.0" in w for w in warnings)

    def test_skill_footer_version_regress_warns(
        self, hook_module, logger, tmp_path
    ):
        self._setup_project(
            tmp_path,
            'version: "1.2.0"\n',
            "# SKILL\n\n**Version**: 2.0.0\n",  # current
        )

        def fake_git_show(rev, rel_path, _root):
            if rel_path.endswith("wrap-triggers.yaml"):
                return 'version: "1.2.0"\n'
            return "# SKILL\n\n**Version**: 2.3.0\n"  # HEAD higher

        with patch.object(hook_module, "_git_show", side_effect=fake_git_show):
            warnings = hook_module.check_version_no_regress(tmp_path, logger)
        assert any("AC3" in w and "SKILL.md" in w for w in warnings)

    def test_no_regress_no_warning(self, hook_module, logger, tmp_path):
        self._setup_project(
            tmp_path,
            'version: "1.3.0"\n',
            "# SKILL\n\n**Version**: 2.4.0\n",
        )

        def fake_git_show(rev, rel_path, _root):
            if rel_path.endswith("wrap-triggers.yaml"):
                return 'version: "1.2.0"\n'
            return "# SKILL\n\n**Version**: 2.3.0\n"

        with patch.object(hook_module, "_git_show", side_effect=fake_git_show):
            warnings = hook_module.check_version_no_regress(tmp_path, logger)
        assert warnings == []


# ============================================================================
# main() 判定：不讀映射檔；AC3 警告放行（正向對照）
# ============================================================================

class TestMainDecision:
    """main() 層判定：映射檔不再參與，僅 AC3 Version 回退警告（exit 0）。"""

    def _run_main(self, hook_module, tmp_path, file_rel, check_result=None, check_exc=None):
        payload = {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(tmp_path / file_rel)},
        }
        check_mock = MagicMock(return_value=check_result or [], side_effect=check_exc)
        with patch.object(hook_module, "read_json_from_stdin", return_value=payload), \
             patch.object(hook_module, "get_project_root", return_value=tmp_path), \
             patch.object(hook_module, "setup_hook_logging", return_value=MagicMock()), \
             patch.object(hook_module, "check_version_no_regress", check_mock):
            return hook_module.main()

    def test_missing_alignment_no_alignment_output(self, hook_module, tmp_path, capsys):
        code = self._run_main(hook_module, tmp_path, hook_module.SKILL_REL_PATH)
        out = capsys.readouterr()
        assert code == 0
        assert "映射檔" not in out.err
        assert "映射檔" not in out.out

    def test_removed_alignment_symbols(self, hook_module):
        for name in ("load_alignment", "check_signal_orphan",
                     "check_keyword_orphan", "ALIGNMENT_REL_PATH"):
            assert not hasattr(hook_module, name)

    def test_version_regress_input_still_warns(self, hook_module, tmp_path, capsys):
        """正向對照：Version 回退輸入仍輸出 AC3 警告。"""
        code = self._run_main(
            hook_module, tmp_path, hook_module.SKILL_REL_PATH,
            check_result=["AC3 Version 回退：x"],
        )
        out = capsys.readouterr()
        assert code == 0
        assert "AC3 Version 回退" in out.err
        assert "映射檔" not in out.err

    def test_check_exception_allows(self, hook_module, tmp_path, capsys):
        code = self._run_main(
            hook_module, tmp_path, hook_module.SKILL_REL_PATH,
            check_exc=RuntimeError("boom"),
        )
        assert code == 0
        assert "boom" in capsys.readouterr().err

    def test_unwatched_file_skips(self, hook_module, tmp_path):
        code = self._run_main(hook_module, tmp_path, "docs/other.md")
        assert code == 0


# ============================================================================
# 公用工具：路徑正規化、版本提取
# ============================================================================

class TestUtilities:
    def test_is_watched_relative_path(self, hook_module, tmp_path):
        result = hook_module._is_watched(
            ".claude/config/wrap-triggers.yaml", tmp_path
        )
        assert result == ".claude/config/wrap-triggers.yaml"

    def test_is_watched_absolute_path(self, hook_module, tmp_path):
        abs_path = tmp_path / ".claude" / "config" / "wrap-triggers.yaml"
        abs_path.parent.mkdir(parents=True)
        abs_path.touch()
        result = hook_module._is_watched(str(abs_path), tmp_path)
        assert result == ".claude/config/wrap-triggers.yaml"

    def test_is_watched_unrelated_returns_none(self, hook_module, tmp_path):
        assert hook_module._is_watched("src/foo.py", tmp_path) is None

    def test_extract_yaml_version(self, hook_module):
        text = '# comment\nversion: "1.2.0"\nfoo: bar\n'
        assert hook_module._extract_yaml_version(text) == "1.2.0"

    def test_extract_yaml_version_unquoted(self, hook_module):
        text = "version: 2.0.5\n"
        assert hook_module._extract_yaml_version(text) == "2.0.5"

    def test_extract_yaml_version_missing(self, hook_module):
        assert hook_module._extract_yaml_version("foo: bar\n") is None

    def test_extract_skill_version_takes_last(self, hook_module):
        text = "\n".join(
            ["# Title"]
            + ["filler"] * 50
            + [
                "**Last Updated**: 2026",
                "**Version**: 2.3.0 — note",
                "**Source**: book",
            ]
        )
        assert hook_module._extract_skill_version(text) == "2.3.0"

    def test_extract_skill_version_missing(self, hook_module):
        assert hook_module._extract_skill_version("# title only\n") is None

    def test_semver_tuple(self, hook_module):
        assert hook_module._semver_tuple("1.2.3") == (1, 2, 3)
        assert hook_module._semver_tuple("  2.0.5  ") == (2, 0, 5)
        assert hook_module._semver_tuple("not-semver") is None
        assert hook_module._semver_tuple(None) is None
