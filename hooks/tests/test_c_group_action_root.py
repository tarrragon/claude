"""C 組四支 hook 的作用根測試（3.3.0-W1-204.1.3.3）。

情境 C：CLAUDE_PROJECT_DIR 指向 MAIN，payload.cwd 在 linked worktree（WT）。
判定表 AR 不一致列應改以 WT 判定：
- bash-edit-guard-hook：還原至專案根的 cd 目標
- build-staleness-check-hook：src 與 build
- framework-rule-edit-skill-trigger-hook：編輯目標相對化
- lsp-environment-check：專案型態指標檔

每支含：正向對照（WT 上應偵測者被偵測）、反向對照（僅 MAIN 有的狀態不影響）、
缺 cwd 時 stderr 無 `[get_action_root]`。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parent.parent


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True, capture_output=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"},
    )


@pytest.fixture
def repos(tmp_path: Path):
    """真實 repo（MAIN）與 linked worktree（WT）。"""
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q", "-b", "main")
    (main / "README.md").write_text("x")
    _git(main, "add", "README.md")
    _git(main, "commit", "-q", "-m", "init")
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", "-b", "feat", str(wt))
    return main.resolve(), wt.resolve()


def _run(hook: str, payload: dict, main: Path):
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(main)}
    return subprocess.run(
        [sys.executable, str(HOOKS / hook)],
        input=json.dumps(payload), capture_output=True, text=True, env=env,
        timeout=60,
    )


# ---- bash-edit-guard-hook ----

BASH = "bash-edit-guard-hook.py"


def _bash(cmd: str, cwd: Path | None):
    payload = {"tool_name": "Bash", "tool_input": {"command": cmd}}
    if cwd is not None:
        payload["cwd"] = str(cwd)
    return payload


def test_bash_cd_restore_to_wt_is_allowed(repos):
    main, wt = repos
    r = _run(BASH, _bash(f"cd {wt} && ls", wt), main)
    assert "deny" not in r.stdout


def test_bash_cd_wt_subdir_still_denied(repos):
    """正向對照（E2）：WT 絕對子目錄仍被擋。"""
    main, wt = repos
    r = _run(BASH, _bash(f"cd {wt}/sub && ls", wt), main)
    assert '"deny"' in r.stdout


def test_bash_cd_main_no_longer_exempt_from_wt(repos):
    """反向對照：MAIN 不再是 WT session 的專案根。"""
    main, wt = repos
    r = _run(BASH, _bash(f"cd {main} && ls", wt), main)
    assert '"deny"' in r.stdout


def test_bash_no_cwd_keeps_env_root_and_no_helper_stderr(repos):
    main, _ = repos
    r = _run(BASH, _bash(f"cd {main} && ls", None), main)
    assert "deny" not in r.stdout
    assert "[get_action_root]" not in r.stderr


# ---- build-staleness-check-hook ----

BUILD = "build-staleness-check-hook.py"


def _make_src(root: Path, with_build: bool) -> None:
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "a.js").write_text("x")
    if with_build:
        (root / "build" / "development").mkdir(parents=True, exist_ok=True)
        m = root / "build" / "development" / "manifest.json"
        m.write_text("{}")
        now = time.time()
        os.utime(root / "src" / "a.js", (now, now))
        os.utime(m, (now, now))


def test_build_wt_fresh_ignores_main_missing(repos):
    main, wt = repos
    _make_src(main, with_build=False)   # MAIN 會回報 missing
    _make_src(wt, with_build=True)      # WT fresh
    r = _run(BUILD, {"cwd": str(wt)}, main)
    assert r.stdout.strip() == ""


def test_build_wt_missing_detected(repos):
    """正向對照（E2）：WT 缺 build 被偵測，即使 MAIN 的 build 完整。"""
    main, wt = repos
    _make_src(main, with_build=True)
    _make_src(wt, with_build=False)
    r = _run(BUILD, {"cwd": str(wt)}, main)
    assert "尚未建置" in r.stdout


def test_build_no_cwd_uses_env_root_without_helper_stderr(repos):
    main, wt = repos
    _make_src(main, with_build=False)
    _make_src(wt, with_build=True)
    r = _run(BUILD, {}, main)
    assert "尚未建置" in r.stdout
    assert "[get_action_root]" not in r.stderr


# ---- framework-rule-edit-skill-trigger-hook ----

FRAME = "framework-rule-edit-skill-trigger-hook.py"
RULE_REL = ".claude/rules/core/sample.md"


def _edit(path: Path, cwd: Path | None, sid: str):
    payload = {
        "tool_name": "Edit", "session_id": sid,
        "tool_input": {"file_path": str(path), "old_string": "a", "new_string": "b"},
    }
    if cwd is not None:
        payload["cwd"] = str(cwd)
    return payload


def test_frame_wt_edit_relativized_against_wt(repos):
    """正向對照（E2）：WT 內 framework 檔以 WT 相對化（訊息為相對路徑，非絕對）。"""
    main, wt = repos
    r = _run(FRAME, _edit(wt / RULE_REL, wt, "c-wt"), main)
    assert RULE_REL in r.stderr
    assert str(wt) not in r.stderr


def test_frame_main_file_not_relativized_from_wt(repos):
    """反向對照：MAIN 內的檔案不再相對化（維持絕對路徑）。"""
    main, wt = repos
    r = _run(FRAME, _edit(main / RULE_REL, wt, "c-main"), main)
    assert str(main / RULE_REL) in r.stderr


def test_frame_no_cwd_keeps_env_root_and_no_helper_stderr(repos):
    main, _ = repos
    r = _run(FRAME, _edit(main / RULE_REL, None, "c-nocwd"), main)
    assert RULE_REL in r.stderr
    assert str(main) not in r.stderr
    assert "[get_action_root]" not in r.stderr


# ---- lsp-environment-check ----

LSP = "lsp-environment-check.py"


def test_lsp_wt_indicator_detected_ignores_main(repos):
    main, wt = repos
    (main / "pubspec.yaml").write_text("x")       # 僅 MAIN 有
    (wt / "tsconfig.json").write_text("{}")       # 正向對照：WT 有
    r = _run(LSP, {"cwd": str(wt)}, main)
    assert "專案類型: typescript" in r.stdout
    assert "flutter" not in r.stdout.split("專案類型:")[1].splitlines()[0]


def test_lsp_main_only_indicator_not_detected_from_wt(repos):
    main, wt = repos
    (main / "pubspec.yaml").write_text("x")
    r = _run(LSP, {"cwd": str(wt)}, main)
    assert "專案類型: 未偵測到" in r.stdout


def test_lsp_no_cwd_uses_env_root_without_helper_stderr(repos):
    main, wt = repos
    (main / "pubspec.yaml").write_text("x")
    r = _run(LSP, {}, main)
    assert "專案類型: flutter" in r.stdout
    assert "[get_action_root]" not in r.stderr
