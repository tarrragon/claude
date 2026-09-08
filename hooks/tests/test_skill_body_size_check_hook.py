"""Tests for skill-body-size-check-hook（0.2.1-W3-1357）。

涵蓋：
- 分段 token 估算公式（ASCII 4 字元/token、非 ASCII 1.3 字元/token，兩段加總，
  非全檔比例內插）
- 全檔（含 frontmatter）超過 5,000 tokens 觸發警告；未超標不觸發
- 行數超過 500 行觸發警告（獨立於 token 門檻）
- frontmatter 計入量測的邊界案例：body 本身低於門檻，但含 frontmatter 後
  的全檔超過門檻，仍須觸發（門檻對象為全檔，非 body）
- 掃描跳過非目錄項、無 SKILL.md 的目錄、隱藏目錄
- 失敗安全：hook 永遠退出碼 0（純提醒，不阻擋）
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).resolve().parent.parent / "skill-body-size-check-hook.py"


def _load_module():
    hook_dir = HOOK_PATH.parent
    sys.path.insert(0, str(hook_dir))
    sys.path.insert(0, str(hook_dir.parent))
    spec = importlib.util.spec_from_file_location("skill_body_size_check_hook", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def hook_module():
    return _load_module()


@pytest.fixture
def skills_dir(tmp_path, monkeypatch, hook_module):
    root = tmp_path / "proj"
    (root / ".claude" / "skills").mkdir(parents=True)
    monkeypatch.setattr(hook_module, "get_project_root", lambda: root)
    return root / ".claude" / "skills"


def _write_skill(skills_dir: Path, name: str, content: str) -> None:
    skill_dir = skills_dir / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")


class TestEstimateTokens:
    def test_ascii_only_uses_four_chars_per_token(self, hook_module):
        text = "a" * 400
        assert hook_module.estimate_tokens(text) == 100

    def test_non_ascii_only_uses_1_3_chars_per_token(self, hook_module):
        text = "繁" * 130
        assert hook_module.estimate_tokens(text) == round(130 / 1.3)

    def test_mixed_content_sums_both_segments(self, hook_module):
        text = ("a" * 400) + ("繁" * 130)
        expected = round(400 / 4 + 130 / 1.3)
        assert hook_module.estimate_tokens(text) == expected


class TestScanSkills:
    def test_over_token_threshold_triggers_warning(self, skills_dir, hook_module):
        # 20,500 ASCII chars ≈ 5,125 tokens > 5,000 門檻
        _write_skill(skills_dir, "oversized-skill", "x" * 20_500)

        over_token, over_lines = hook_module.scan_skills(skills_dir)

        names = [item[0] for item in over_token]
        assert "oversized-skill" in names

    def test_compliant_skill_no_warning(self, skills_dir, hook_module):
        _write_skill(skills_dir, "small-skill", "---\nname: small-skill\n---\nbody\n")

        over_token, over_lines = hook_module.scan_skills(skills_dir)

        assert over_token == []
        assert over_lines == []

    def test_over_line_threshold_triggers_warning_independent_of_tokens(
        self, skills_dir, hook_module
    ):
        # 每行內容極短，token 數遠低於門檻，但行數超過 500
        # （"a\n" 重複 501 次 = 501 個換行符，與 wc -l 語意一致）
        content = "a\n" * 501
        _write_skill(skills_dir, "many-lines-skill", content)

        over_token, over_lines = hook_module.scan_skills(skills_dir)

        assert over_token == []
        names = [item[0] for item in over_lines]
        assert "many-lines-skill" in names

    def test_frontmatter_counted_towards_token_threshold(self, skills_dir, hook_module):
        """邊界案例：body 本身低於門檻，含 frontmatter 後的全檔超過門檻。"""
        body = "x" * 19_600  # ≈ 4,900 tokens，body 單獨不超標
        frontmatter = "---\n" + ("y" * 892) + "\n---\n"  # 加上後推過 5,000 tokens
        assert hook_module.estimate_tokens(body) < hook_module.TOKEN_THRESHOLD

        full_content = frontmatter + body
        assert hook_module.estimate_tokens(full_content) > hook_module.TOKEN_THRESHOLD

        _write_skill(skills_dir, "frontmatter-tips-it-over", full_content)

        over_token, _ = hook_module.scan_skills(skills_dir)

        names = [item[0] for item in over_token]
        assert "frontmatter-tips-it-over" in names

    def test_skips_non_directory_entries(self, skills_dir, hook_module):
        (skills_dir / "stray-file.md").write_text("not a skill dir", encoding="utf-8")

        over_token, over_lines = hook_module.scan_skills(skills_dir)

        assert over_token == []
        assert over_lines == []

    def test_skips_directory_without_skill_md(self, skills_dir, hook_module):
        (skills_dir / "no-skill-md").mkdir()
        (skills_dir / "no-skill-md" / "README.md").write_text("x", encoding="utf-8")

        over_token, over_lines = hook_module.scan_skills(skills_dir)

        assert over_token == []
        assert over_lines == []

    def test_skips_hidden_directory(self, skills_dir, hook_module):
        hidden = skills_dir / ".hidden-skill"
        hidden.mkdir()
        (hidden / "SKILL.md").write_text("x" * 30_000, encoding="utf-8")

        over_token, over_lines = hook_module.scan_skills(skills_dir)

        assert over_token == []
        assert over_lines == []


class TestMain:
    def test_main_exits_zero_when_over_threshold(self, skills_dir, hook_module, capsys):
        _write_skill(skills_dir, "oversized-skill", "x" * 20_500)

        exit_code = hook_module.main()

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "oversized-skill" in captured.err

    def test_main_exits_zero_when_compliant(self, skills_dir, hook_module, capsys):
        _write_skill(skills_dir, "small-skill", "---\nname: small-skill\n---\nbody\n")

        exit_code = hook_module.main()

        assert exit_code == 0

    def test_main_handles_missing_skills_dir(self, tmp_path, monkeypatch, hook_module):
        root = tmp_path / "empty-proj"
        root.mkdir()
        monkeypatch.setattr(hook_module, "get_project_root", lambda: root)

        exit_code = hook_module.main()

        assert exit_code == 0
