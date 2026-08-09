#!/usr/bin/env python3
"""skill-description-length-check-hook 與 warn_skill_md_case_mismatch 的接線測試。

本 hook 原掃描依賴 `skill_md.exists()`（case-insensitive 檔案系統上對小寫
`skill.md` 一樣回傳 True，不代表精確大寫），從未告警大小寫不符。這裡只驗
接線本身：混合大小寫目錄能觸發告警，全大寫目錄維持靜默。
"""

import importlib.util
import sys
from pathlib import Path

import pytest

hook_dir = Path(__file__).parent.parent
sys.path.insert(0, str(hook_dir))
sys.path.insert(0, str(hook_dir.parent))

spec = importlib.util.spec_from_file_location(
    "skill_description_length_check_hook",
    hook_dir / "skill-description-length-check-hook.py",
)
hook_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook_module)


@pytest.fixture
def skills_dir(tmp_path, monkeypatch):
    root = tmp_path / "proj"
    (root / ".claude" / "skills").mkdir(parents=True)
    monkeypatch.setattr(hook_module, "get_project_root", lambda: root)
    return root / ".claude" / "skills"


def test_lowercase_skill_md_emits_case_warning(skills_dir, capsys):
    skill_dir = skills_dir / "wrong-case"
    skill_dir.mkdir()
    (skill_dir / "skill.md").write_text(
        "---\ndescription: short\n---\nbody\n", encoding="utf-8"
    )

    hook_module.main()

    captured = capsys.readouterr()
    assert "wrong-case" in captured.err
    assert "skill.md" in captured.err


def test_correct_uppercase_no_case_warning(skills_dir, capsys):
    skill_dir = skills_dir / "correct-case"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\ndescription: short\n---\nbody\n", encoding="utf-8"
    )

    hook_module.main()

    captured = capsys.readouterr()
    assert "大小寫" not in captured.err
