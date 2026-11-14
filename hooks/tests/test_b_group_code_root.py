"""204.1.4.2 B 組六支 SessionStart hook 改用 get_code_root 的情境測試。

情境 C：CLAUDE_PROJECT_DIR 與 cwd 指向 other（WT），載入中的 .claude 在 code（MAIN）。
兩份 .claude 內容不同以區分讀取來源；「舊碼對照」以 get_code_root -> get_project_root
字串替換得到舊行為（SR/LR 呼叫點本就不含 get_code_root，不受影響）。
全部以 subprocess 在 tmp 目錄執行，不寫入真實 repo。
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
REAL_CLAUDE_DIR = HOOKS_DIR.parent


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _checkout(root: Path, hook_file: str, with_code: bool) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "CLAUDE.md").write_text("x", encoding="utf-8")
    if not with_code:
        return
    shutil.copytree(
        REAL_CLAUDE_DIR / "lib", root / ".claude" / "lib",
        ignore=shutil.ignore_patterns("tests", "__pycache__"),
    )
    src = (HOOKS_DIR / hook_file).read_text(encoding="utf-8")
    _write(root, ".claude/hooks/" + hook_file, src)
    _write(root, ".claude/hooks/old-" + hook_file, src.replace("get_code_root", "get_project_root"))


def _env(project: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if k != "HOOK_TEST_ISOLATION"}
    env["CLAUDE_PROJECT_DIR"] = str(project)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _run(code: Path, script: str, project: Path, stdin: str = "{}") -> str:
    proc = subprocess.run(
        [sys.executable, str(code / ".claude" / "hooks" / script)],
        cwd=str(project), env=_env(project), input=stdin,
        capture_output=True, text=True, timeout=60,
    )
    return proc.stdout + proc.stderr


@pytest.fixture
def pair(tmp_path):
    return tmp_path / "code", tmp_path / "other"


# ---------------------------------------------------------------- dependency-isolation

DEP = "hook-dependency-isolation-check-hook.py"


def _dep_settings(root: Path, name: str) -> None:
    _write(root, ".claude/settings.json", json.dumps({"hooks": {"Stop": [{"hooks": [
        {"type": "command", "command": "uv run --quiet $CLAUDE_PROJECT_DIR/.claude/hooks/" + name}]}]}}))
    _write(root, ".claude/hooks/" + name, "#!/usr/bin/env python3\nimport yaml\n")


@pytest.mark.parametrize("script,expect_code", [(DEP, True), ("old-" + DEP, False)])
def test_dependency_isolation_scenario_c(pair, script, expect_code):
    code, other = pair
    _checkout(code, DEP, True)
    _checkout(other, DEP, False)
    _dep_settings(code, "code-marker-hook.py")
    _dep_settings(other, "other-marker-hook.py")
    out = _run(code, script, other, '{"hook_event_name": "SessionStart"}')
    assert ("code-marker-hook.py" in out) is expect_code
    assert ("other-marker-hook.py" in out) is (not expect_code)


# ---------------------------------------------------------------- liveness-summary

LIVE = "hook-liveness-summary-hook.py"


def _live_settings(root: Path, name: str) -> None:
    _write(root, ".claude/settings.json", json.dumps({"hooks": {"Stop": [{"hooks": [
        {"type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/" + name}]}]}}))
    _write(root, ".claude/hooks/" + name, "#!/usr/bin/env python3\n")


@pytest.mark.parametrize("script,expect_code", [(LIVE, True), ("old-" + LIVE, False)])
def test_liveness_summary_scenario_c(pair, script, expect_code):
    code, other = pair
    _checkout(code, LIVE, True)
    _checkout(other, LIVE, False)
    _live_settings(code, "bare-code-marker-hook.py")
    _live_settings(other, "bare-other-marker-hook.py")
    out = _run(code, script, other)
    assert ("bare-code-marker-hook.py" in out) is expect_code
    assert ("bare-other-marker-hook.py" in out) is (not expect_code)


# ---------------------------------------------------------------- registry-sync

SYNC = "project-hook-registry-sync-hook.py"
MANIFEST = ".claude/project-integration/hook-registry.yaml"
LOCAL = ".claude/settings.local.json"


def _manifest(root: Path, name: str) -> None:
    _write(root, ".claude/project-integration/hooks/" + name, "#!/bin/sh\n")
    _write(root, MANIFEST, "version: 1\nhooks:\n  {n}:\n    script: .claude/project-integration/hooks/{n}\n"
           "    event: Stop\n".format(n=name))
    _write(root, ".claude/settings.json", "{}")


def _local_text(root: Path) -> str:
    p = root / LOCAL
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def _generated(root: Path) -> list:
    return sorted(root.glob(".claude/hook-logs/project-hook-registry-sync*/generated*.json"))


def test_sync_scenario_c_reads_and_writes_code_root(pair):
    """項 1、2：讀 registry、寫 settings.local.json 都取 code root；WT 的 registry 列不進 MAIN。"""
    code, other = pair
    _checkout(code, SYNC, True)
    _checkout(other, SYNC, False)
    _manifest(code, "main-row.sh")
    _manifest(other, "wt-only-row.sh")
    _run(code, SYNC, other)
    assert "main-row.sh" in _local_text(code)
    assert "wt-only-row.sh" not in _local_text(code)
    assert _local_text(other) == ""
    # LR：generated.json 隨日誌目錄（project 側），不落在 code
    assert not _generated(code)
    assert _generated(other)


def test_sync_scenario_c_old_code_writes_other(pair):
    """舊碼對照（同一輸入）：讀 WT 的 registry、寫 WT，MAIN 不動。"""
    code, other = pair
    _checkout(code, SYNC, True)
    _checkout(other, SYNC, False)
    _manifest(code, "main-row.sh")
    _manifest(other, "wt-only-row.sh")
    _run(code, "old-" + SYNC, other)
    assert "wt-only-row.sh" in _local_text(other)
    assert _local_text(code) == ""


@pytest.mark.parametrize("name", ["main", "wt"])
@pytest.mark.parametrize("script_prefix", ["", "old-"])
def test_sync_scenario_a_b_target_unchanged(tmp_path, name, script_prefix):
    """項 4：情境 A（MAIN 啟動）、B（WT 啟動載入 WT .claude）新舊寫入對象相同，皆為載入中那份。"""
    root = tmp_path / name
    _checkout(root, SYNC, True)
    _manifest(root, "row.sh")
    _run(root, script_prefix + SYNC, root)
    assert "row.sh" in _local_text(root)


def test_sync_code_root_without_settings_and_manifest_writes_nothing(pair):
    """項 3：載入中的根底下沒有 settings.json 也沒有 registry -> 完全不寫（other 的清冊不被採用）。"""
    code, other = pair
    _checkout(code, SYNC, True)
    _checkout(other, SYNC, False)
    _manifest(other, "wt-only-row.sh")
    _run(code, SYNC, other)
    assert _local_text(code) == ""
    assert _local_text(other) == ""


def test_sync_code_root_with_manifest_but_no_settings_writes_code_only(pair):
    """項 3：有 registry 但無 settings.json -> 仍只寫 code 那份（framework 身分集為空），不寫 other。"""
    code, other = pair
    _checkout(code, SYNC, True)
    _checkout(other, SYNC, False)
    _manifest(code, "main-row.sh")
    (code / ".claude/settings.json").unlink()
    _run(code, SYNC, other)
    assert "main-row.sh" in _local_text(code)
    assert _local_text(other) == ""


def _alternating_setup(tmp_path, script_prefix):
    main, wt, project = tmp_path / "main", tmp_path / "wt", tmp_path / "project"
    for root in (main, wt):
        _checkout(root, SYNC, True)
        src = (root / ".claude/hooks" / SYNC).read_text(encoding="utf-8")
        # 上一版行為：所有 code root 共用單一 generated.json
        _write(root, ".claude/hooks/shared-" + SYNC, src.replace(
            '"generated-{}.json".format(_root_digest(root))', '"generated.json"'))
    _checkout(project, SYNC, False)
    _manifest(main, "m1.sh")
    _manifest(wt, "m1.sh")
    # WT 清冊多一列 w1；MAIN 內有 w1 腳本供用戶自行註冊
    _write(wt, MANIFEST, (wt / MANIFEST).read_text(encoding="utf-8") +
           "  w1.sh:\n    script: .claude/project-integration/hooks/w1.sh\n    event: Stop\n")
    _write(wt, ".claude/project-integration/hooks/w1.sh", "#!/bin/sh\n")
    _write(main, ".claude/project-integration/hooks/w1.sh", "#!/bin/sh\n")
    # env 固定在 project（共用同一日誌目錄），載入的 code root 交替
    _run(main, script_prefix + SYNC, project)  # A
    _run(wt, script_prefix + SYNC, project)  # B
    w1 = "$CLAUDE_PROJECT_DIR/.claude/project-integration/hooks/w1.sh"
    local = json.loads((main / LOCAL).read_text(encoding="utf-8"))
    local.setdefault("hooks", {}).setdefault("Notification", []).append(
        {"hooks": [{"type": "command", "command": w1}]})  # 用戶自加，指令同 WT 清冊 w1
    (main / LOCAL).write_text(json.dumps(local), encoding="utf-8")
    _run(main, script_prefix + SYNC, project)  # A
    return main, wt, project, w1


def test_sync_alternating_code_roots_keep_separate_generated(tmp_path):
    main, wt, project, w1 = _alternating_setup(tmp_path, "")
    files = sorted((project / ".claude/hook-logs/project-hook-registry-sync").glob("generated-*.json"))
    assert len(files) == 2 and all(len(f.stem.split("-", 1)[1]) == 16 for f in files)
    cmds = [json.loads(f.read_text(encoding="utf-8"))["commands"] for f in files]
    assert sorted(len(c) for c in cmds) == [1, 2]  # MAIN {m1}、WT {m1,w1} 互不覆蓋
    assert w1 in _local_text(main)  # 用戶自加條目未被誤刪


def test_sync_alternating_code_roots_shared_single_file_deletes_user_entry(tmp_path):
    """對照：上一版共用單檔，同一輸入下用戶自加的 w1 被判 manifest_removed 而刪除。"""
    main, wt, project, w1 = _alternating_setup(tmp_path, "shared-")
    assert w1 not in _local_text(main)


# ---------------------------------------------------------------- gitignore-check

GIT = "session-start-gitignore-check-hook.py"


def _tix(root: Path, value: str) -> None:
    _write(root, ".claude/skills/ticket/ticket_system/constants.py", 'WORK_LOGS_DIR = "{}"\n'.format(value))


@pytest.mark.parametrize("script,expect_code", [(GIT, True), ("old-" + GIT, False)])
def test_gitignore_check_scenario_c(pair, script, expect_code):
    code, other = pair
    _checkout(code, GIT, True)
    _checkout(other, GIT, False)
    _tix(code, "code-tix")
    _tix(other, "other-tix")
    _write(other, ".gitignore", "")  # .gitignore 屬被檢查的 project 側（不改）
    out = _run(code, script, other)
    assert ("code-tix/**/*.md.lock" in out) is expect_code
    assert ("other-tix/**/*.md.lock" in out) is (not expect_code)


# ---------------------------------------------------------------- verification-environment

VER = "verification-environment-check-hook.py"


@pytest.mark.parametrize("script,expect_recipe", [(VER, True), ("old-" + VER, False)])
def test_verification_environment_scenario_c(pair, script, expect_recipe):
    code, other = pair
    _checkout(code, VER, True)
    _checkout(other, VER, False)
    _write(other, "pubspec.yaml", "dependencies:\n  flutter:\n    sdk: flutter\n")  # project 側
    _write(code, ".claude/skills/verify/SKILL.md", "no udid here\n")
    out = _run(code, script, other)
    assert ("配方存在" in out) is expect_recipe


# ---------------------------------------------------------------- issue-check

ISSUE = "session-start-issue-check-hook.py"

_DRIVER = r"""
import importlib.util, sys, subprocess, json
from unittest.mock import MagicMock, patch
spec = importlib.util.spec_from_file_location("h", sys.argv[1])
h = importlib.util.module_from_spec(spec); spec.loader.exec_module(h)
seen = {}
real_run = h.subprocess.run
def fake(args, **kw):
    if args[0] != sys.executable:
        return real_run(args, **kw)
    seen["script"] = args[1]
    raise OSError("stop")
with patch.object(h.subprocess, "run", fake):
    h._run_check(7, MagicMock())
from pathlib import Path
sys.modules["owned_issues_registry"] = MagicMock(
    owned_issue_numbers=lambda project_root: [project_root.name])
reg = h._read_owned_issue_numbers(Path(sys.argv[2]), MagicMock())
print(json.dumps({"script": seen["script"], "scripts_dir": sys.path[0], "registry_root": reg}))
"""


@pytest.mark.parametrize("script,expect_code", [(ISSUE, True), ("old-" + ISSUE, False)])
def test_issue_check_scenario_c(pair, script, expect_code):
    code, other = pair
    _checkout(code, ISSUE, True)
    _checkout(other, ISSUE, False)
    proc = subprocess.run(
        [sys.executable, "-c", _DRIVER, str(code / ".claude/hooks" / script), str(other)],
        cwd=str(other), env=_env(other), capture_output=True, text=True, timeout=60,
    )
    assert proc.stdout.strip(), proc.stderr
    data = json.loads(proc.stdout.strip().splitlines()[-1])
    base = code if expect_code else other
    assert data["script"] == str(base / ".claude/skills/framework-issue/scripts/section_comment.py")
    assert data["scripts_dir"] == str(base / ".claude/skills/framework-issue/scripts")
    # SR：登記檔資料一律取 project_root（other），新舊相同
    assert data["registry_root"] == ["other"]
