"""
Unit tests for wrap-skill-yaml-consistency-hook.py

驗收項目（W10-055 acceptance）：
  AC1 Signal orphan：YAML signal id 在映射檔有對應 SKILL 情境（警告級）
  AC2 Keyword orphan：YAML keyword 在映射檔有 belongs_to 類別（警告級）
  AC3 Version 非回退：YAML version 與 SKILL footer Version 各自 >= git HEAD（警告級）
  AC4 映射檔存在性：triggers-alignment.yaml 存在且可解析（阻擋級 exit 2）

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
    Path(__file__).resolve().parents[1] / "wrap-skill-yaml-consistency-hook.py"
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
# AC1：Signal orphan 檢查
# ============================================================================

class TestSignalOrphan:
    def test_all_signals_have_mapping_no_warning(self, hook_module, logger):
        yaml_data = {
            "signals": [
                {"id": "consecutive_failures"},
                {"id": "restrictive_keywords"},
            ]
        }
        alignment = {
            "signal_to_skill_triggers": {
                "consecutive_failures": ["連續失敗"],
                "restrictive_keywords": ["被困住"],
            }
        }
        warnings = hook_module.check_signal_orphan(yaml_data, alignment, logger)
        assert warnings == []

    def test_signal_missing_from_mapping_warns(self, hook_module, logger):
        yaml_data = {"signals": [{"id": "new_orphan_signal"}]}
        alignment = {"signal_to_skill_triggers": {}}
        warnings = hook_module.check_signal_orphan(yaml_data, alignment, logger)
        assert len(warnings) == 1
        assert "new_orphan_signal" in warnings[0]
        assert "AC1" in warnings[0]

    def test_signal_with_empty_situations_warns(self, hook_module, logger):
        yaml_data = {"signals": [{"id": "sig_x"}]}
        alignment = {"signal_to_skill_triggers": {"sig_x": []}}
        warnings = hook_module.check_signal_orphan(yaml_data, alignment, logger)
        assert len(warnings) == 1


# ============================================================================
# AC2：Keyword orphan 檢查
# ============================================================================

class TestKeywordOrphan:
    def test_all_keywords_mapped_no_warning(self, hook_module, logger):
        yaml_data = {
            "signals": [
                {
                    "id": "restrictive_keywords",
                    "keywords": ["做不到", "無法"],
                }
            ]
        }
        alignment = {
            "keyword_to_trigger_category": {
                "做不到": "限制性解法",
                "無法": "限制性解法",
            }
        }
        warnings = hook_module.check_keyword_orphan(yaml_data, alignment, logger)
        assert warnings == []

    def test_orphan_direct_keyword_warns(self, hook_module, logger):
        yaml_data = {
            "signals": [
                {"id": "sig_a", "keywords": ["新關鍵字"]}
            ]
        }
        alignment = {"keyword_to_trigger_category": {}}
        warnings = hook_module.check_keyword_orphan(yaml_data, alignment, logger)
        assert len(warnings) == 1
        assert "新關鍵字" in warnings[0]
        assert "AC2" in warnings[0]

    def test_orphan_failure_detection_keyword_warns(self, hook_module, logger):
        yaml_data = {
            "signals": [
                {
                    "id": "consecutive_failures",
                    "failure_detection": {"keywords": ["panic"]},
                }
            ]
        }
        alignment = {
            "keyword_to_trigger_category": {
                "error": "stuck",
            }
        }
        warnings = hook_module.check_keyword_orphan(yaml_data, alignment, logger)
        assert len(warnings) == 1
        assert "panic" in warnings[0]
        assert "failure_detection" in warnings[0]


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
# AC4：映射檔存在性（阻擋級）
# ============================================================================

class TestAlignmentFile:
    def test_missing_file_returns_error(self, hook_module, logger, tmp_path):
        data, err = hook_module.load_alignment(tmp_path, logger)
        assert data is None
        assert err is not None
        assert "映射檔不存在" in err

    def test_invalid_yaml_returns_error(self, hook_module, logger, tmp_path):
        target = (
            tmp_path
            / ".claude"
            / "skills"
            / "wrap-decision"
            / "references"
            / "project-integration"
            / "triggers-alignment.yaml"
        )
        target.parent.mkdir(parents=True)
        target.write_text("::: not yaml :::\n  - bad\n bad", encoding="utf-8")
        data, err = hook_module.load_alignment(tmp_path, logger)
        assert data is None
        assert err is not None

    def test_valid_file_loads(self, hook_module, logger, tmp_path):
        target = (
            tmp_path
            / ".claude"
            / "skills"
            / "wrap-decision"
            / "references"
            / "project-integration"
            / "triggers-alignment.yaml"
        )
        target.parent.mkdir(parents=True)
        target.write_text(
            'version: "1.0.0"\nsignal_to_skill_triggers:\n  a: ["x"]\n',
            encoding="utf-8",
        )
        data, err = hook_module.load_alignment(tmp_path, logger)
        assert err is None
        assert data["version"] == "1.0.0"

    def test_top_level_non_mapping_returns_error(
        self, hook_module, logger, tmp_path
    ):
        target = (
            tmp_path
            / ".claude"
            / "skills"
            / "wrap-decision"
            / "references"
            / "project-integration"
            / "triggers-alignment.yaml"
        )
        target.parent.mkdir(parents=True)
        target.write_text("- 1\n- 2\n", encoding="utf-8")
        data, err = hook_module.load_alignment(tmp_path, logger)
        assert data is None
        assert "頂層非 mapping" in err


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
