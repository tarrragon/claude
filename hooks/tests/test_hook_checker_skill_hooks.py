"""Tests for skill hook scanning + registration extraction (W10-091).

雙層 Hook 架構：除了 .claude/hooks/ 外，每個 skill 可在自身
`.claude/skills/<skill>/hooks/` 維護私有 Hook。本測試覆蓋：

1. `scan_skill_hooks` 遞迴掃描 skill hooks/ 子目錄
2. `extract_registered_skill_hooks` 從 settings.json 取出 skill hook 註冊
3. 兩者集合相減判斷未註冊 skill hook（hook-completeness-check 主流程語意）
4. 主層 hook 與 skill hook 命名空間獨立（同檔名不相互混淆）
"""

import sys
from pathlib import Path

# 將 project-init 加入 import path
_REPO_ROOT = Path(__file__).resolve().parents[3]
_PROJECT_INIT = _REPO_ROOT / ".claude" / "skills" / "project-init"
sys.path.insert(0, str(_PROJECT_INIT))

from project_init.lib.hook_checker import (  # noqa: E402
    extract_registered_hooks,
    extract_registered_skill_hooks,
    get_exclude_patterns,
    scan_skill_hooks,
)


def _make_skill_hook(skills_dir: Path, skill: str, name: str) -> Path:
    hooks_dir = skills_dir / skill / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    path = hooks_dir / name
    path.write_text("# stub hook\n", encoding="utf-8")
    return path


class TestScanSkillHooks:
    def test_empty_skills_dir_returns_empty_set(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        result = scan_skill_hooks(skills_dir, set(), set())
        assert result == set()

    def test_missing_skills_dir_returns_empty_set(self, tmp_path):
        skills_dir = tmp_path / "skills"  # 不建立
        result = scan_skill_hooks(skills_dir, set(), set())
        assert result == set()

    def test_skill_without_hooks_subdir_is_skipped(self, tmp_path):
        skills_dir = tmp_path / "skills"
        (skills_dir / "no-hooks-skill").mkdir(parents=True)
        # 沒有 hooks/ 子目錄
        result = scan_skill_hooks(skills_dir, set(), set())
        assert result == set()

    def test_scans_skill_hooks_with_relative_path(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _make_skill_hook(skills_dir, "test-async-guardian", "pre-test-scan.py")
        _make_skill_hook(skills_dir, "another-skill", "post-action.py")

        result = scan_skill_hooks(skills_dir, set(), set())
        assert result == {
            "test-async-guardian/hooks/pre-test-scan.py",
            "another-skill/hooks/post-action.py",
        }

    def test_skip_pycache_and_venv(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _make_skill_hook(skills_dir, "skill-a", "real.py")
        # 製造應排除的目錄
        cache_dir = skills_dir / "skill-a" / "hooks" / "__pycache__"
        cache_dir.mkdir(parents=True)
        (cache_dir / "real.cpython-311.pyc.py").write_text("", encoding="utf-8")
        venv_dir = skills_dir / "skill-a" / "hooks" / ".venv" / "lib"
        venv_dir.mkdir(parents=True)
        (venv_dir / "fake.py").write_text("", encoding="utf-8")

        result = scan_skill_hooks(skills_dir, set(), set())
        assert result == {"skill-a/hooks/real.py"}

    def test_respects_exclude_list(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _make_skill_hook(skills_dir, "skill-a", "hook_utils.py")  # exact exclude
        _make_skill_hook(skills_dir, "skill-a", "real-hook.py")
        _make_skill_hook(skills_dir, "skill-a", "old-backup.py")  # pattern exclude

        exact_excludes, patterns = get_exclude_patterns(None)
        # 確認預設 exclude 含 hook_utils.py 與 *-backup.py
        assert "hook_utils.py" in exact_excludes
        assert "*-backup.py" in patterns

        result = scan_skill_hooks(skills_dir, exact_excludes, patterns)
        assert result == {"skill-a/hooks/real-hook.py"}


def _settings_with(commands):
    return {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "*",
                    "hooks": [{"type": "command", "command": c} for c in commands],
                }
            ]
        }
    }


class TestExtractRegisteredSkillHooks:
    def test_extracts_skill_hook_paths(self):
        settings = _settings_with(
            [
                "$CLAUDE_PROJECT_DIR/.claude/skills/test-async-guardian/hooks/pre-test-scan.py",
                "$CLAUDE_PROJECT_DIR/.claude/hooks/agent-dispatch-logger-hook.py",
            ]
        )
        result = extract_registered_skill_hooks(settings)
        assert result == {"test-async-guardian/hooks/pre-test-scan.py"}

    def test_excludes_skill_files_outside_hooks_subdir(self):
        # 例如 strategic-compact/suggest-compact.py（非 hooks/ 子目錄）不算 skill hook
        settings = _settings_with(
            [
                "$CLAUDE_PROJECT_DIR/.claude/skills/strategic-compact/suggest-compact.py",
                "$CLAUDE_PROJECT_DIR/.claude/skills/continuous-learning/evaluate-session.py",
            ]
        )
        result = extract_registered_skill_hooks(settings)
        assert result == set()

    def test_trailing_args_are_stripped(self):
        settings = _settings_with(
            [
                "$CLAUDE_PROJECT_DIR/.claude/skills/skill-a/hooks/x.py --flag value",
            ]
        )
        result = extract_registered_skill_hooks(settings)
        assert result == {"skill-a/hooks/x.py"}

    def test_main_hook_extraction_unaffected_by_skill_paths(self):
        # 保證 extract_registered_hooks 不會把 skill hook 誤收為主層 hook
        settings = _settings_with(
            [
                "$CLAUDE_PROJECT_DIR/.claude/hooks/main-hook.py",
                "$CLAUDE_PROJECT_DIR/.claude/skills/skill-a/hooks/skill-hook.py",
            ]
        )
        main = extract_registered_hooks(settings)
        skill = extract_registered_skill_hooks(settings)
        assert main == {"main-hook.py"}
        assert skill == {"skill-a/hooks/skill-hook.py"}


class TestUnregisteredSkillHookDetection:
    """模擬 hook-completeness-check 主流程之集合相減語意."""

    def test_registered_skill_hook_passes(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _make_skill_hook(skills_dir, "skill-a", "pre.py")
        scanned = scan_skill_hooks(skills_dir, set(), set())
        registered = extract_registered_skill_hooks(
            _settings_with(["$CLAUDE_PROJECT_DIR/.claude/skills/skill-a/hooks/pre.py"])
        )
        assert scanned - registered == set()

    def test_unregistered_skill_hook_detected(self, tmp_path):
        skills_dir = tmp_path / "skills"
        _make_skill_hook(skills_dir, "skill-a", "pre.py")
        _make_skill_hook(skills_dir, "skill-b", "post.py")
        scanned = scan_skill_hooks(skills_dir, set(), set())
        # 只註冊 skill-a/hooks/pre.py
        registered = extract_registered_skill_hooks(
            _settings_with(["$CLAUDE_PROJECT_DIR/.claude/skills/skill-a/hooks/pre.py"])
        )
        unregistered = scanned - registered
        assert unregistered == {"skill-b/hooks/post.py"}

    def test_dual_namespace_independence(self, tmp_path):
        """主層 hook 與 skill hook 同檔名不相互混淆."""
        skills_dir = tmp_path / "skills"
        _make_skill_hook(skills_dir, "skill-a", "shared-name.py")
        scanned_skill = scan_skill_hooks(skills_dir, set(), set())

        settings = _settings_with(
            [
                "$CLAUDE_PROJECT_DIR/.claude/hooks/shared-name.py",  # 註冊主層同名
            ]
        )
        # 主層註冊不應該滿足 skill 那邊的需求
        registered_skill = extract_registered_skill_hooks(settings)
        assert registered_skill == set()
        assert scanned_skill - registered_skill == {"skill-a/hooks/shared-name.py"}
