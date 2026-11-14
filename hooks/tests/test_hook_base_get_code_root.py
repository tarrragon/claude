"""hook_base.get_code_root 單元與情境 C 測試（3.3.0-W1-204.1.4.1）。

情境 C：CLAUDE_PROJECT_DIR 與 cwd 指向另一個 checkout，載入中的 .claude
（lib 所在）在別處。get_code_root 必須回傳載入中那份的上層目錄。
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from lib import hook_base
from lib.hook_base import get_code_root

HOOKS_DIR = Path(__file__).resolve().parent.parent
REAL_CLAUDE_DIR = HOOKS_DIR.parent
HOOK_NAME = "skill-body-size-check-hook.py"


def _expected_code_root() -> Path:
    return Path(hook_base.__file__).resolve().parents[2]


def test_ignores_env_and_cwd(tmp_path, monkeypatch):
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.delenv("HOOK_TEST_ISOLATION", raising=False)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(other))
    monkeypatch.chdir(other)
    hook_base.clear_project_root_cache()
    try:
        assert get_code_root() == _expected_code_root()
    finally:
        hook_base.clear_project_root_cache()


def test_isolation_falls_back_to_project_root(tmp_path, monkeypatch):
    fixture_root = tmp_path / "fixture"
    fixture_root.mkdir()
    (fixture_root / "CLAUDE.md").write_text("x", encoding="utf-8")
    monkeypatch.setenv("HOOK_TEST_ISOLATION", "1")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(fixture_root))
    hook_base.clear_project_root_cache()
    try:
        assert get_code_root() == hook_base.get_project_root()
        assert get_code_root() == fixture_root.resolve()
    finally:
        hook_base.clear_project_root_cache()


def _make_checkout(root: Path, skill_name: str, with_code: bool) -> None:
    skill = root / ".claude" / "skills" / skill_name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("line\n" * 600, encoding="utf-8")
    (root / "CLAUDE.md").write_text("x", encoding="utf-8")
    if with_code:
        shutil.copytree(
            REAL_CLAUDE_DIR / "lib",
            root / ".claude" / "lib",
            ignore=shutil.ignore_patterns("tests", "__pycache__"),
        )
        hooks = root / ".claude" / "hooks"
        hooks.mkdir()
        src = (HOOKS_DIR / HOOK_NAME).read_text(encoding="utf-8")
        (hooks / HOOK_NAME).write_text(src, encoding="utf-8")
        (hooks / ("old-" + HOOK_NAME)).write_text(
            src.replace("get_code_root", "get_project_root"), encoding="utf-8"
        )


def _run(code_root: Path, script: str, other: Path) -> str:
    env = {k: v for k, v in os.environ.items() if k != "HOOK_TEST_ISOLATION"}
    env["CLAUDE_PROJECT_DIR"] = str(other)
    proc = subprocess.run(
        [sys.executable, str(code_root / ".claude" / "hooks" / script)],
        cwd=str(other),
        env=env,
        input="{}",
        capture_output=True,
        text=True,
        timeout=60,
    )
    return proc.stdout + proc.stderr


@pytest.fixture
def two_checkouts(tmp_path):
    code, other = tmp_path / "code", tmp_path / "other"
    _make_checkout(code, "code-skill", with_code=True)
    _make_checkout(other, "other-skill", with_code=False)
    return code, other


def test_scenario_c_reads_loaded_claude(two_checkouts):
    code, other = two_checkouts
    out = _run(code, HOOK_NAME, other)
    assert "code-skill" in out
    assert "other-skill" not in out


def test_scenario_c_old_code_reads_other_checkout(two_checkouts):
    """舊碼對照：get_project_root 版本在情境 C 讀到別份 .claude。"""
    code, other = two_checkouts
    out = _run(code, "old-" + HOOK_NAME, other)
    assert "other-skill" in out
    assert "code-skill" not in out
