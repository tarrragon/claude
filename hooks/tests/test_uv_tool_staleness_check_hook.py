"""
Tests for uv-tool-staleness-check-hook.

對應 W11-037.1 Phase 2 測試設計（19 個測試覆蓋 12 條 acceptance）。
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# 確保 hook 內部 `from lib.uv_tool_utils import ...` 可解析
_HOOKS_DIR = Path(__file__).parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

HOOK_DIR = Path(__file__).parent.parent
HOOK_FILE = HOOK_DIR / "uv-tool-staleness-check-hook.py"
PROJECT_ROOT = HOOK_DIR.parent.parent


def _load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "uv_tool_staleness_check_hook", HOOK_FILE
    )
    module = importlib.util.module_from_spec(spec)
    # 註冊到 sys.modules 讓 dataclass __module__ lookup 成功
    sys.modules["uv_tool_staleness_check_hook"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def hook_module():
    return _load_hook_module()


@pytest.fixture
def make_source(tmp_path):
    def _make(skill_name: str, files: dict) -> Path:
        d = tmp_path / "source" / skill_name
        d.mkdir(parents=True, exist_ok=True)
        for rel, content in files.items():
            p = d / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(content if isinstance(content, bytes) else content.encode())
        return d
    return _make


@pytest.fixture
def make_installed(tmp_path):
    def _make(pkg_name: str, files: dict) -> Path:
        d = tmp_path / "installed" / pkg_name
        d.mkdir(parents=True, exist_ok=True)
        for rel, content in files.items():
            p = d / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(content if isinstance(content, bytes) else content.encode())
        return d
    return _make


# ----------------------------------------------------------------------------
# T01 (AC1): hook file exists and is registered in settings.json
# ----------------------------------------------------------------------------
def test_hook_file_exists_and_registered_in_settings():
    assert HOOK_FILE.exists(), "Hook file must exist"
    settings = json.loads((PROJECT_ROOT / ".claude" / "settings.json").read_text())
    session_start = settings["hooks"]["SessionStart"][0]["hooks"]
    cmds = [h["command"] for h in session_start]
    target = "$CLAUDE_PROJECT_DIR/.claude/hooks/uv-tool-staleness-check-hook.py"
    assert target in cmds, "Hook must be registered in SessionStart chain"

    idx_new = cmds.index(target)
    # 位置：project-init-env-check-hook 之後、version-consistency-guard-hook 之前
    idx_proj_init = next(
        (i for i, c in enumerate(cmds) if c.endswith("project-init-env-check-hook.py")),
        None,
    )
    idx_version = next(
        (i for i, c in enumerate(cmds) if c.endswith("version-consistency-guard-hook.py")),
        None,
    )
    assert idx_proj_init is not None and idx_version is not None
    assert idx_proj_init < idx_new < idx_version, (
        "Hook 必須位於 project-init-env-check 之後、version-consistency-guard 之前"
    )


# ----------------------------------------------------------------------------
# T02 (AC2): SKILLS 涵蓋 7 個 skill
# ----------------------------------------------------------------------------
def test_skills_constant_covers_seven_skills(hook_module):
    skills = hook_module.SKILLS
    assert len(skills) == 7
    expected_cli = {
        "ticket", "doc", "version-release", "mermaid-ascii",
        "worktree", "branch-worktree-guardian", "project-init",
    }
    assert {s.cli_name for s in skills} == expected_cli
    for s in skills:
        for attr in ("source_subpath", "module_subpath", "package_name",
                     "package_dir_name", "cli_name"):
            assert hasattr(s, attr)
            assert getattr(s, attr)


# ----------------------------------------------------------------------------
# T03-T06 (AC3): compute_file_hashes 行為
# ----------------------------------------------------------------------------
def test_compute_file_hashes_excludes_pycache_and_tests(make_source):
    from lib.uv_tool_utils import compute_file_hashes, STALENESS_EXCLUDE_DIRS
    d = make_source("s1", {
        "a.py": "x",
        "__pycache__/a.cpython-312.pyc": b"\x00",
        "tests/test_a.py": "y",
        "sub/b.py": "z",
    })
    # .pyc 不會被 *.py 抓到本就排除；驗證 __pycache__ 與 tests/ 目錄下 .py 被排除
    (d / "__pycache__" / "foo.py").write_text("p")
    hashes = compute_file_hashes(d, STALENESS_EXCLUDE_DIRS)
    keys = set(hashes.keys())
    assert "a.py" in keys
    assert "sub/b.py" in keys
    assert not any("tests" in k for k in keys)
    assert not any("__pycache__" in k for k in keys)


def test_compute_file_hashes_identical_dirs_equal_sets(make_source, make_installed):
    from lib.uv_tool_utils import compute_file_hashes, STALENESS_EXCLUDE_DIRS
    src = make_source("s2", {"a.py": "same", "sub/b.py": "same2"})
    inst = make_installed("s2", {"a.py": "same", "sub/b.py": "same2"})
    assert (compute_file_hashes(src, STALENESS_EXCLUDE_DIRS)
            == compute_file_hashes(inst, STALENESS_EXCLUDE_DIRS))


def test_compute_file_hashes_different_filenames_unequal(make_source, make_installed):
    from lib.uv_tool_utils import compute_file_hashes, STALENESS_EXCLUDE_DIRS
    src = make_source("s3", {"a.py": "same"})
    inst = make_installed("s3", {"b.py": "same"})
    assert (compute_file_hashes(src, STALENESS_EXCLUDE_DIRS)
            != compute_file_hashes(inst, STALENESS_EXCLUDE_DIRS))


def test_compute_file_hashes_same_name_different_content_unequal(make_source, make_installed):
    from lib.uv_tool_utils import compute_file_hashes, STALENESS_EXCLUDE_DIRS
    src = make_source("s4", {"a.py": "v1"})
    inst = make_installed("s4", {"a.py": "v2"})
    sh = compute_file_hashes(src, STALENESS_EXCLUDE_DIRS)
    ih = compute_file_hashes(inst, STALENESS_EXCLUDE_DIRS)
    assert sh["a.py"] != ih["a.py"]


# ----------------------------------------------------------------------------
# Helper: run main() capturing stdout
# ----------------------------------------------------------------------------
def _run_main(hook_module, capsys):
    code = hook_module.main()
    out = capsys.readouterr().out
    try:
        payload = json.loads(out) if out.strip() else {}
    except json.JSONDecodeError:
        payload = {"raw": out}
    return code, payload


# ----------------------------------------------------------------------------
# T07 (AC4): stale skill → OUTDATED 行 + 修復指令
# ----------------------------------------------------------------------------
def test_stale_skill_produces_outdated_line(
    hook_module, monkeypatch, make_source, make_installed, capsys, tmp_path
):
    # 建一個 fake project_root，僅 ticket skill 為 stale，其餘 MISSING
    fake_root = tmp_path / "repo"
    (fake_root / ".claude" / "skills" / "ticket" / "ticket_system").mkdir(parents=True)
    (fake_root / ".claude" / "skills" / "ticket" / "ticket_system" / "a.py").write_text("source")
    inst = make_installed("ticket_system", {"a.py": "installed-different"})

    def fake_find(cli, pkg, logger):
        return inst if cli == "ticket" else None

    monkeypatch.setattr(hook_module, "get_project_root", lambda: fake_root)
    monkeypatch.setattr(hook_module, "find_installed_module_dir", fake_find)

    code, payload = _run_main(hook_module, capsys)
    assert code == 0
    msg = payload["hookSpecificOutput"]["additionalContext"]
    assert "[UV Tool Staleness] ticket-system [OUTDATED]" in msg
    assert "cd .claude/skills/ticket && uv tool install . --force --reinstall" in msg


# ----------------------------------------------------------------------------
# T08 (AC5): 全部同步 → 簡潔訊息
# ----------------------------------------------------------------------------
def test_all_synced_produces_concise_message(
    hook_module, monkeypatch, tmp_path, capsys, make_installed
):
    fake_root = tmp_path / "repo"
    inst_map = {}
    for skill in hook_module.SKILLS:
        src = fake_root / skill.module_subpath
        src.mkdir(parents=True, exist_ok=True)
        (src / "a.py").write_text("x")
        inst_map[skill.package_dir_name] = make_installed(skill.package_dir_name, {"a.py": "x"})

    def fake_find(cli, pkg, logger):
        return inst_map.get(pkg)

    monkeypatch.setattr(hook_module, "get_project_root", lambda: fake_root)
    monkeypatch.setattr(hook_module, "find_installed_module_dir", fake_find)

    _, payload = _run_main(hook_module, capsys)
    msg = payload["hookSpecificOutput"]["additionalContext"]
    assert msg == "[UV Tool Staleness] 全部 7 個 uv tool skill 已同步"


# ----------------------------------------------------------------------------
# T09 (AC6): missing skill → MISSING line, exit 0
# ----------------------------------------------------------------------------
def test_missing_skill_produces_missing_line_and_exit_0(
    hook_module, monkeypatch, tmp_path, capsys
):
    fake_root = tmp_path / "repo"
    for skill in hook_module.SKILLS:
        (fake_root / skill.module_subpath).mkdir(parents=True, exist_ok=True)
        (fake_root / skill.module_subpath / "a.py").write_text("x")

    monkeypatch.setattr(hook_module, "get_project_root", lambda: fake_root)
    monkeypatch.setattr(
        hook_module, "find_installed_module_dir", lambda *a, **k: None
    )

    code, payload = _run_main(hook_module, capsys)
    assert code == 0
    msg = payload["hookSpecificOutput"]["additionalContext"]
    assert "[MISSING]" in msg
    assert "uv tool install ." in msg


# ----------------------------------------------------------------------------
# T10 (AC6): installed 目錄存在但無 .py → MISSING
# ----------------------------------------------------------------------------
def test_installed_dir_no_py_files_treated_as_missing(
    hook_module, monkeypatch, tmp_path, capsys
):
    fake_root = tmp_path / "repo"
    src = fake_root / hook_module.SKILLS[0].module_subpath
    src.mkdir(parents=True)
    (src / "a.py").write_text("x")
    for skill in hook_module.SKILLS[1:]:
        (fake_root / skill.module_subpath).mkdir(parents=True, exist_ok=True)

    empty_installed = tmp_path / "empty_installed"
    empty_installed.mkdir()

    def fake_find(cli, pkg, logger):
        if cli == hook_module.SKILLS[0].cli_name:
            return empty_installed
        return None

    monkeypatch.setattr(hook_module, "get_project_root", lambda: fake_root)
    monkeypatch.setattr(hook_module, "find_installed_module_dir", fake_find)

    _, payload = _run_main(hook_module, capsys)
    msg = payload["hookSpecificOutput"]["additionalContext"]
    assert "[MISSING]" in msg


# ----------------------------------------------------------------------------
# T11 (AC7): hash 計算錯誤 → exit 0，該 skill 為 ERROR
# ----------------------------------------------------------------------------
def test_hook_exits_0_on_internal_error(hook_module, monkeypatch, tmp_path, capsys):
    fake_root = tmp_path / "repo"
    for skill in hook_module.SKILLS:
        (fake_root / skill.module_subpath).mkdir(parents=True, exist_ok=True)
        (fake_root / skill.module_subpath / "a.py").write_text("x")

    installed = tmp_path / "inst"
    installed.mkdir()
    (installed / "a.py").write_text("x")

    monkeypatch.setattr(hook_module, "get_project_root", lambda: fake_root)
    monkeypatch.setattr(
        hook_module, "find_installed_module_dir", lambda *a, **k: installed
    )

    def boom(*a, **k):
        raise IOError("disk error")

    monkeypatch.setattr(hook_module, "compute_file_hashes", boom)
    code, payload = _run_main(hook_module, capsys)
    assert code == 0


# ----------------------------------------------------------------------------
# T12 (AC7): 全域致命錯誤 → suppressOutput
# ----------------------------------------------------------------------------
def test_hook_exits_0_on_global_failure(hook_module, monkeypatch, capsys):
    def boom():
        raise RuntimeError("project root not found")

    monkeypatch.setattr(hook_module, "get_project_root", boom)
    code, payload = _run_main(hook_module, capsys)
    assert code == 0
    assert payload.get("suppressOutput") is True


# ----------------------------------------------------------------------------
# T13 (AC8): false positive 防護 — source==installed 完全一致無 OUTDATED
# ----------------------------------------------------------------------------
def test_no_outdated_when_source_installed_identical(
    hook_module, monkeypatch, tmp_path, capsys, make_installed
):
    fake_root = tmp_path / "repo"
    inst_map = {}
    for skill in hook_module.SKILLS:
        src = fake_root / skill.module_subpath
        src.mkdir(parents=True, exist_ok=True)
        (src / "core.py").write_text("identical")
        inst_map[skill.package_dir_name] = make_installed(
            skill.package_dir_name, {"core.py": "identical"}
        )

    monkeypatch.setattr(hook_module, "get_project_root", lambda: fake_root)
    monkeypatch.setattr(
        hook_module, "find_installed_module_dir",
        lambda cli, pkg, logger: inst_map.get(pkg),
    )
    _, payload = _run_main(hook_module, capsys)
    msg = payload["hookSpecificOutput"]["additionalContext"]
    assert "[OUTDATED]" not in msg


# ----------------------------------------------------------------------------
# T14-T16 (AC9): false negative 防護
# ----------------------------------------------------------------------------
def _setup_one_skill_diff(hook_module, monkeypatch, tmp_path, make_installed,
                          src_files, inst_files):
    fake_root = tmp_path / "repo"
    target = hook_module.SKILLS[0]
    src = fake_root / target.module_subpath
    src.mkdir(parents=True)
    for k, v in src_files.items():
        (src / k).parent.mkdir(parents=True, exist_ok=True)
        (src / k).write_text(v)
    inst = make_installed(target.package_dir_name, inst_files)
    for skill in hook_module.SKILLS[1:]:
        (fake_root / skill.module_subpath).mkdir(parents=True, exist_ok=True)

    def fake_find(cli, pkg, logger):
        return inst if pkg == target.package_dir_name else None

    monkeypatch.setattr(hook_module, "get_project_root", lambda: fake_root)
    monkeypatch.setattr(hook_module, "find_installed_module_dir", fake_find)
    return target


def test_detects_stale_on_added_file(
    hook_module, monkeypatch, tmp_path, capsys, make_installed
):
    target = _setup_one_skill_diff(
        hook_module, monkeypatch, tmp_path, make_installed,
        src_files={"a.py": "x", "new.py": "added"},
        inst_files={"a.py": "x"},
    )
    _, payload = _run_main(hook_module, capsys)
    assert f"{target.package_name} [OUTDATED]" in payload["hookSpecificOutput"]["additionalContext"]


def test_detects_stale_on_removed_file(
    hook_module, monkeypatch, tmp_path, capsys, make_installed
):
    target = _setup_one_skill_diff(
        hook_module, monkeypatch, tmp_path, make_installed,
        src_files={"a.py": "x"},
        inst_files={"a.py": "x", "old.py": "removed"},
    )
    _, payload = _run_main(hook_module, capsys)
    assert f"{target.package_name} [OUTDATED]" in payload["hookSpecificOutput"]["additionalContext"]


def test_detects_stale_on_modified_file(
    hook_module, monkeypatch, tmp_path, capsys, make_installed
):
    target = _setup_one_skill_diff(
        hook_module, monkeypatch, tmp_path, make_installed,
        src_files={"a.py": "v1"},
        inst_files={"a.py": "v2"},
    )
    _, payload = _run_main(hook_module, capsys)
    assert f"{target.package_name} [OUTDATED]" in payload["hookSpecificOutput"]["additionalContext"]


# ----------------------------------------------------------------------------
# T17 (AC10): 7 個 SKILL.md 含 reinstall 警示區塊
# ----------------------------------------------------------------------------
def test_skill_md_files_contain_reinstall_warning():
    skills_dir = PROJECT_ROOT / ".claude" / "skills"
    skill_names = [
        "ticket", "doc", "version-release", "mermaid-ascii",
        "worktree", "branch-worktree-guardian", "project-init",
    ]
    for name in skill_names:
        md = skills_dir / name / "SKILL.md"
        assert md.exists(), f"{md} missing"
        text = md.read_text(encoding="utf-8")
        assert "uv tool install . --force --reinstall" in text, (
            f"{name}/SKILL.md 缺少 reinstall 警示區塊"
        )


# ----------------------------------------------------------------------------
# T18 (AC11): 效能 < 5 秒（7 skill * 50 .py）
# ----------------------------------------------------------------------------
def test_hook_execution_under_5_seconds(
    hook_module, monkeypatch, tmp_path, capsys, make_installed
):
    fake_root = tmp_path / "repo"
    inst_map = {}
    for skill in hook_module.SKILLS:
        src = fake_root / skill.module_subpath
        src.mkdir(parents=True, exist_ok=True)
        files = {f"f{i}.py": f"content-{i}-{'x' * 200}" for i in range(50)}
        for k, v in files.items():
            (src / k).write_text(v)
        inst_map[skill.package_dir_name] = make_installed(skill.package_dir_name, files)

    monkeypatch.setattr(hook_module, "get_project_root", lambda: fake_root)
    monkeypatch.setattr(
        hook_module, "find_installed_module_dir",
        lambda cli, pkg, logger: inst_map.get(pkg),
    )

    t0 = time.perf_counter()
    hook_module.main()
    capsys.readouterr()
    elapsed = time.perf_counter() - t0
    assert elapsed < 5.0, f"Hook 執行 {elapsed:.2f}s 超過 5s 上限"
