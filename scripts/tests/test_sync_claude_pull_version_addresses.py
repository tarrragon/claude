"""sync-pull：自動解 SKILL.md 版號衝突後，衍生版號住址一併對齊（3.6.0-W1-321）。

三情境：上游版號較大、本地版號較大、衍生住址缺漏（不能機械對齊 -> 列衝突）。
斷言以 check_skill_versions 為準：pull 後無分歧。
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location("sync_claude_pull_version_addr", _SCRIPT)
assert _spec and _spec.loader
pull = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_version_addr"] = pull
_spec.loader.exec_module(pull)  # type: ignore[union-attr]

from lib.skill_version_diff import check_skill_versions  # noqa: E402


def _git(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit_all(repo: Path, msg: str) -> str:
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", msg], repo)
    return _git(["rev-parse", "HEAD"], repo)


def _skill_md(v: str) -> str:
    return (
        "---\nname: demo\ndescription: d\nmetadata:\n  portable: true\n"
        f"  version: {v}\n  category: test\n---\n\n# demo\n\n內文不變。\n"
    )


def _changelog(v: str) -> str:
    return f"# Changelog\n\n**Version**: {v} - 說明\n\n**Version**: 1.0.0 - 初版\n"


def _pyproject(v: str) -> str:
    return f'[project]\nname = "demo"\nversion = "{v}"\n'


def _write_skill(root: Path, skill_v: str, changelog_v: str, pyproject_v: str) -> None:
    d = root / "skills" / "demo"
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(_skill_md(skill_v), encoding="utf-8")
    (d / "CHANGELOG.md").write_text(_changelog(changelog_v), encoding="utf-8")
    (d / "pyproject.toml").write_text(_pyproject(pyproject_v), encoding="utf-8")


def _setup(tmp_path: Path, up: tuple[str, str, str], local_skill_v: str):
    """base 全 1.7.0；上游 (SKILL, CHANGELOG, pyproject)；本地只 bump SKILL.md。"""
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    _git(["init", "-q"], upstream)
    _git(["config", "user.email", "t@t.t"], upstream)
    _git(["config", "user.name", "t"], upstream)
    _git(["config", "commit.gpgsign", "false"], upstream)
    _write_skill(upstream, "1.7.0", "1.7.0", "1.7.0")
    base = _commit_all(upstream, "base")
    _write_skill(upstream, *up)
    _commit_all(upstream, "head")

    project_root = tmp_path / "proj"
    claude = project_root / ".claude"
    _write_skill(claude, "1.7.0", "1.7.0", "1.7.0")
    (claude / "skills" / "demo" / "SKILL.md").write_text(
        _skill_md(local_skill_v), encoding="utf-8"
    )
    return project_root, upstream, base


def _pull(project_root, upstream, base):
    return pull.apply_upstream_delta(project_root, upstream, base)


def test_local_version_larger_aligns_derived(tmp_path):
    root, up, base = _setup(tmp_path, ("1.8.0", "1.8.0", "1.8.0"), "1.9.1")
    _applied, conflicts, _r = _pull(root, up, base)
    skills = root / ".claude" / "skills"
    assert "1.9.1" in (skills / "demo" / "SKILL.md").read_text(encoding="utf-8")
    assert conflicts == []
    assert check_skill_versions(skills).ok


def test_upstream_version_larger_aligns_derived(tmp_path):
    # 上游只 bump SKILL.md，衍生住址停在 1.7.0
    root, up, base = _setup(tmp_path, ("1.9.0", "1.7.0", "1.7.0"), "1.8.0")
    _applied, conflicts, _r = _pull(root, up, base)
    skills = root / ".claude" / "skills"
    assert "1.9.0" in (skills / "demo" / "SKILL.md").read_text(encoding="utf-8")
    assert conflicts == []
    assert check_skill_versions(skills).ok
    assert 'version = "1.9.0"' in (skills / "demo" / "pyproject.toml").read_text(encoding="utf-8")


def test_unalignable_address_listed_as_conflict(tmp_path):
    # 上游 CHANGELOG 無行首 **Version**：無法機械對齊 -> 列待處理衝突
    root, up, base = _setup(tmp_path, ("1.9.0", "1.7.0", "1.7.0"), "1.8.0")
    (up / "skills" / "demo" / "CHANGELOG.md").write_text("# Changelog\n\n無版號\n", encoding="utf-8")
    _commit_all(up, "nover")
    _applied, conflicts, _r = _pull(root, up, base)
    assert any(c.startswith("skills/demo") and "CHANGELOG" in c for c in conflicts)


def test_no_version_conflict_leaves_derived_untouched(tmp_path):
    # 對照：本地沒改 SKILL.md（非三方衝突），不進對齊流程
    root, up, base = _setup(tmp_path, ("1.9.0", "1.7.0", "1.7.0"), "1.7.0")
    _pull(root, up, base)
    skills = root / ".claude" / "skills"
    assert 'version = "1.7.0"' in (skills / "demo" / "pyproject.toml").read_text(encoding="utf-8")
