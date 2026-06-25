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
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
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


@pytest.fixture(autouse=True)
def _non_shim_by_default(hook_module, monkeypatch):
    """既有 staleness 測試假設 CLI 非 shim（走 SHA 比對）；隔離 host 環境真實
    which 結果，避免本機 ticket/doc 已 shim 化時 is_shimmed_cli 短路成 SHIMMED。
    新增的 shim 測試會在各自 test 內覆寫此 monkeypatch。"""
    monkeypatch.setattr(
        hook_module, "is_shimmed_cli", lambda cli, logger=None: False
    )


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
# 佈局感知 helper（目錄模組 vs 單檔模組共用）
# ----------------------------------------------------------------------------
def _write_source_for_skill(fake_root: Path, skill, files: dict) -> None:
    """
    依 skill 佈局在 fake_root 建立 source。

    - 單檔模組（single_file=True）：module_subpath 指向單一 .py 檔，取 files 第一個值寫入該檔。
    - 目錄模組：module_subpath 為目錄，files 內每個 rel 寫成子檔。
    """
    target = fake_root / skill.module_subpath
    if getattr(skill, "single_file", False):
        target.parent.mkdir(parents=True, exist_ok=True)
        content = next(iter(files.values()))
        target.write_text(content if isinstance(content, str) else content.decode())
    else:
        target.mkdir(parents=True, exist_ok=True)
        for rel, content in files.items():
            p = target / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content if isinstance(content, str) else content.decode())


def _make_installed_for_skill(make_installed, tmp_path, skill, files: dict) -> Path:
    """
    依 skill 佈局建立 installed，回傳 find_installed_module_dir 應回傳的路徑。

    - 單檔模組：建立 site-packages 目錄含單一 .py 檔，回傳「site-packages 目錄」
      （hook 內以 package_dir_name="." 取 site-packages 後再拼檔名定位單檔）。
    - 目錄模組：建立模組目錄含子檔，回傳該模組目錄。
    """
    if getattr(skill, "single_file", False):
        site_dir = tmp_path / "installed_sp" / skill.cli_name
        site_dir.mkdir(parents=True, exist_ok=True)
        content = next(iter(files.values()))
        (site_dir / skill.package_dir_name).write_text(
            content if isinstance(content, str) else content.decode()
        )
        return site_dir
    return make_installed(skill.package_dir_name, files)


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
def test_skills_constant_covers_six_uv_tool_skills(hook_module):
    """1.0.0-W1-068：branch-worktree-guardian（非 uv tool）已移除，剩 6 個真 uv tool。"""
    skills = hook_module.SKILLS
    assert len(skills) == 6
    expected_cli = {
        "ticket", "doc", "version-release", "mermaid-ascii",
        "worktree", "project-init",
    }
    assert {s.cli_name for s in skills} == expected_cli
    for s in skills:
        for attr in ("source_subpath", "module_subpath", "package_name",
                     "package_dir_name", "cli_name"):
            assert hasattr(s, attr)
            assert getattr(s, attr)
        # single_file 旗標存在且為 bool（候選 A：SkillEntry 增 single_file 支援）
        assert hasattr(s, "single_file")
        assert isinstance(s.single_file, bool)


def test_branch_worktree_guardian_not_in_registry(hook_module):
    """1.0.0-W1-068 AC1：非 uv tool entry 已移除，不再被掃描（不誤報 source dir missing）。"""
    cli_names = {s.cli_name for s in hook_module.SKILLS}
    assert "branch-worktree-guardian" not in cli_names
    pkg_names = {s.package_name for s in hook_module.SKILLS}
    assert "branch-worktree-guardian" not in pkg_names


def test_version_release_marked_single_file(hook_module):
    """1.0.0-W1-068：version-release 為單檔模組，single_file=True。"""
    vr = next(s for s in hook_module.SKILLS if s.cli_name == "version-release")
    assert vr.single_file is True
    assert vr.module_subpath.endswith(".py"), "單檔模組 module_subpath 應指向單一 .py 檔"
    assert vr.package_dir_name == "version_release.py"


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
    # W9-003：免 cd 絕對路徑形式（PowerShell 5.1 無 && chain operator）
    expected_path = fake_root / ".claude" / "skills" / "ticket"
    assert f'uv tool install "{expected_path}" --force --reinstall' in msg
    assert "&&" not in msg


# ----------------------------------------------------------------------------
# T08 (AC5): 全部同步 → 簡潔訊息
# ----------------------------------------------------------------------------
def test_all_synced_produces_concise_message(
    hook_module, monkeypatch, tmp_path, capsys, make_installed
):
    fake_root = tmp_path / "repo"
    inst_map = {}
    for skill in hook_module.SKILLS:
        _write_source_for_skill(fake_root, skill, {"a.py": "x"})
        inst_map[skill.cli_name] = _make_installed_for_skill(
            make_installed, tmp_path, skill, {"a.py": "x"}
        )

    def fake_find(cli, pkg, logger):
        return inst_map.get(cli)

    monkeypatch.setattr(hook_module, "get_project_root", lambda: fake_root)
    monkeypatch.setattr(hook_module, "find_installed_module_dir", fake_find)

    _, payload = _run_main(hook_module, capsys)
    msg = payload["hookSpecificOutput"]["additionalContext"]
    assert msg == "[UV Tool Staleness] 全部 6 個 uv tool skill 已同步"


# ----------------------------------------------------------------------------
# T09 (AC6): missing skill → MISSING line, exit 0
# ----------------------------------------------------------------------------
def test_missing_skill_produces_missing_line_and_exit_0(
    hook_module, monkeypatch, tmp_path, capsys
):
    fake_root = tmp_path / "repo"
    for skill in hook_module.SKILLS:
        _write_source_for_skill(fake_root, skill, {"a.py": "x"})

    monkeypatch.setattr(hook_module, "get_project_root", lambda: fake_root)
    monkeypatch.setattr(
        hook_module, "find_installed_module_dir", lambda *a, **k: None
    )

    code, payload = _run_main(hook_module, capsys)
    assert code == 0
    msg = payload["hookSpecificOutput"]["additionalContext"]
    assert "[MISSING]" in msg
    # W9-003：免 cd 絕對路徑形式（PowerShell 5.1 相容）
    assert 'uv tool install "' in msg
    assert "&&" not in msg


# ----------------------------------------------------------------------------
# T10 (AC6): installed 目錄存在但無 .py → MISSING
# ----------------------------------------------------------------------------
def test_installed_dir_no_py_files_treated_as_missing(
    hook_module, monkeypatch, tmp_path, capsys
):
    fake_root = tmp_path / "repo"
    for skill in hook_module.SKILLS:
        _write_source_for_skill(fake_root, skill, {"a.py": "x"})

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
        _write_source_for_skill(fake_root, skill, {"a.py": "x"})

    installed = tmp_path / "inst"
    installed.mkdir()
    (installed / "a.py").write_text("x")
    # 單檔模組安裝點：site-packages 內含 version_release.py
    (installed / "version_release.py").write_text("x")

    monkeypatch.setattr(hook_module, "get_project_root", lambda: fake_root)
    monkeypatch.setattr(
        hook_module, "find_installed_module_dir", lambda *a, **k: installed
    )

    def boom(*a, **k):
        raise IOError("disk error")

    monkeypatch.setattr(hook_module, "compute_file_hashes", boom)
    # 單檔模組走 _compute_single_file_hash，亦需失敗測試覆蓋（不阻塊 exit 0）
    monkeypatch.setattr(hook_module, "_compute_single_file_hash", boom)
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
        _write_source_for_skill(fake_root, skill, {"core.py": "identical"})
        inst_map[skill.cli_name] = _make_installed_for_skill(
            make_installed, tmp_path, skill, {"core.py": "identical"}
        )

    monkeypatch.setattr(hook_module, "get_project_root", lambda: fake_root)
    monkeypatch.setattr(
        hook_module, "find_installed_module_dir",
        lambda cli, pkg, logger: inst_map.get(cli),
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
        _write_source_for_skill(fake_root, skill, {"a.py": "x"})

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
        "worktree", "project-init",
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
        files = {f"f{i}.py": f"content-{i}-{'x' * 200}" for i in range(50)}
        _write_source_for_skill(fake_root, skill, files)
        inst_map[skill.cli_name] = _make_installed_for_skill(
            make_installed, tmp_path, skill, files
        )

    monkeypatch.setattr(hook_module, "get_project_root", lambda: fake_root)
    monkeypatch.setattr(
        hook_module, "find_installed_module_dir",
        lambda cli, pkg, logger: inst_map.get(cli),
    )

    t0 = time.perf_counter()
    hook_module.main()
    capsys.readouterr()
    elapsed = time.perf_counter() - t0
    assert elapsed < 5.0, f"Hook 執行 {elapsed:.2f}s 超過 5s 上限"


# ----------------------------------------------------------------------------
# 1.0.0-W1-068：單檔模組（version-release）回歸測試
# ----------------------------------------------------------------------------
def _vr_skill(hook_module):
    return next(s for s in hook_module.SKILLS if s.cli_name == "version-release")


def test_single_file_skill_synced_is_ok(
    hook_module, monkeypatch, tmp_path, capsys
):
    """AC1：單檔模組 source==installed 時為 OK，不誤報 source dir missing / OUTDATED。"""
    fake_root = tmp_path / "repo"
    vr = _vr_skill(hook_module)
    # 建 source 單檔
    src_file = fake_root / vr.module_subpath
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("VERSION = '1.0.0'")
    # 建 installed site-packages 單檔（內容相同）
    site_dir = tmp_path / "sp"
    site_dir.mkdir()
    (site_dir / vr.package_dir_name).write_text("VERSION = '1.0.0'")
    # 其餘 skill 設為 MISSING（不干擾）
    for skill in hook_module.SKILLS:
        if skill.cli_name != "version-release":
            _write_source_for_skill(fake_root, skill, {"a.py": "x"})

    def fake_find(cli, pkg, logger):
        return site_dir if cli == "version-release" else None

    monkeypatch.setattr(hook_module, "get_project_root", lambda: fake_root)
    monkeypatch.setattr(hook_module, "find_installed_module_dir", fake_find)

    results = [
        hook_module.check_single_skill(s, fake_root, _DummyLogger())
        for s in hook_module.SKILLS
    ]
    vr_result = next(r for r in results if r.skill.cli_name == "version-release")
    assert vr_result.status == "OK"
    _, payload = _run_main(hook_module, capsys)
    msg = payload["hookSpecificOutput"]["additionalContext"]
    assert "version-release [OUTDATED]" not in msg
    assert "source dir missing" not in msg
    assert "source file missing" not in msg


def test_single_file_skill_stale_is_outdated(
    hook_module, monkeypatch, tmp_path, capsys
):
    """AC2：單檔模組 source != installed 時正確偵測 OUTDATED + 修復指令。"""
    fake_root = tmp_path / "repo"
    vr = _vr_skill(hook_module)
    src_file = fake_root / vr.module_subpath
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("VERSION = '2.0.0'")  # source 新
    site_dir = tmp_path / "sp"
    site_dir.mkdir()
    (site_dir / vr.package_dir_name).write_text("VERSION = '1.0.0'")  # installed 舊
    for skill in hook_module.SKILLS:
        if skill.cli_name != "version-release":
            _write_source_for_skill(fake_root, skill, {"a.py": "x"})

    def fake_find(cli, pkg, logger):
        return site_dir if cli == "version-release" else None

    monkeypatch.setattr(hook_module, "get_project_root", lambda: fake_root)
    monkeypatch.setattr(hook_module, "find_installed_module_dir", fake_find)

    code, payload = _run_main(hook_module, capsys)
    assert code == 0
    msg = payload["hookSpecificOutput"]["additionalContext"]
    assert "version-release [OUTDATED]" in msg
    # W9-003：免 cd 絕對路徑形式（PowerShell 5.1 相容）
    expected_path = fake_root / ".claude" / "skills" / "version-release"
    assert f'uv tool install "{expected_path}" --force --reinstall' in msg
    assert "&&" not in msg


def test_single_file_skill_missing_installed_is_missing(
    hook_module, monkeypatch, tmp_path, capsys
):
    """單檔模組 installed 不存在時為 MISSING（非 ERROR）。"""
    fake_root = tmp_path / "repo"
    vr = _vr_skill(hook_module)
    src_file = fake_root / vr.module_subpath
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("VERSION = '1.0.0'")
    for skill in hook_module.SKILLS:
        if skill.cli_name != "version-release":
            _write_source_for_skill(fake_root, skill, {"a.py": "x"})

    monkeypatch.setattr(hook_module, "get_project_root", lambda: fake_root)
    monkeypatch.setattr(
        hook_module, "find_installed_module_dir", lambda *a, **k: None
    )

    results = [
        hook_module.check_single_skill(s, fake_root, _DummyLogger())
        for s in hook_module.SKILLS
    ]
    vr_result = next(r for r in results if r.skill.cli_name == "version-release")
    assert vr_result.status == "MISSING"


class _DummyLogger:
    def warning(self, *a, **k): pass
    def error(self, *a, **k): pass
    def debug(self, *a, **k): pass
    def info(self, *a, **k): pass
    def critical(self, *a, **k): pass


# ----------------------------------------------------------------------------
# 0.37.0-W7-002：cwd-resolving shim 略過行為（ARCH-APP-002）
# ----------------------------------------------------------------------------
def test_shimmed_cli_returns_shimmed_status(hook_module, monkeypatch, tmp_path):
    """shim 化的 CLI 回 SHIMMED，不進入 SHA 比對（不報 OUTDATED/MISSING）。"""
    fake_root = tmp_path / "repo"
    ticket = next(s for s in hook_module.SKILLS if s.cli_name == "ticket")
    _write_source_for_skill(fake_root, ticket, {"a.py": "x"})

    # ticket 為 shim，其餘非 shim
    monkeypatch.setattr(
        hook_module, "is_shimmed_cli",
        lambda cli, logger=None: cli == "ticket",
    )
    # 若誤入比對路徑會因 find 回 None 而成 MISSING；shim 短路應先回 SHIMMED
    monkeypatch.setattr(
        hook_module, "find_installed_module_dir", lambda *a, **k: None
    )

    result = hook_module.check_single_skill(ticket, fake_root, _DummyLogger())
    assert result.status == "SHIMMED"


def test_shimmed_cli_not_reported_outdated_or_missing(
    hook_module, monkeypatch, tmp_path, capsys
):
    """全部 CLI 皆 shim 時，reporting 視同同步，不出現 OUTDATED/MISSING。"""
    fake_root = tmp_path / "repo"
    for skill in hook_module.SKILLS:
        _write_source_for_skill(fake_root, skill, {"a.py": "x"})

    monkeypatch.setattr(hook_module, "get_project_root", lambda: fake_root)
    monkeypatch.setattr(
        hook_module, "is_shimmed_cli", lambda cli, logger=None: True
    )
    monkeypatch.setattr(
        hook_module, "find_installed_module_dir", lambda *a, **k: None
    )

    code, payload = _run_main(hook_module, capsys)
    assert code == 0
    msg = payload["hookSpecificOutput"]["additionalContext"]
    assert "[OUTDATED]" not in msg
    assert "[MISSING]" not in msg
    assert "已同步" in msg


def test_non_shim_cli_behavior_unchanged(hook_module, monkeypatch, tmp_path):
    """非 shim 的 CLI（is_shimmed_cli 回 False）行為不變：仍走原比對 → MISSING。"""
    fake_root = tmp_path / "repo"
    vr = next(s for s in hook_module.SKILLS if s.cli_name == "version-release")
    src_file = fake_root / vr.module_subpath
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("VERSION = '1.0.0'")

    monkeypatch.setattr(
        hook_module, "is_shimmed_cli", lambda cli, logger=None: False
    )
    monkeypatch.setattr(
        hook_module, "find_installed_module_dir", lambda *a, **k: None
    )

    result = hook_module.check_single_skill(vr, fake_root, _DummyLogger())
    assert result.status == "MISSING"
