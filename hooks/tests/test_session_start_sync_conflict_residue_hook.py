"""session-start-sync-conflict-residue-hook 測試（tarrragon/claude#54）。

以子程序實跑 hook，CLAUDE_PROJECT_DIR 指向暫存專案，斷言 stdout 的
additionalContext 內容。正反對照（E2）：同步範圍內的標記檔與 .sync-conflicts/
副本要列出；hook-logs 等非同步範圍檔案含標記字樣時不列出、不輸出。
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
HOOK_PATH = HOOKS_DIR / "session-start-sync-conflict-residue-hook.py"
SETTINGS_PATH = HOOKS_DIR.parent / "settings.json"

_MARKER_TEXT = "a\n<<<<<<< local\nLOCAL\n=======\nUPSTREAM\n>>>>>>> upstream\nc\n"


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / ".claude").mkdir(parents=True)
    return root


def _write(root: Path, rel: str, text: str = _MARKER_TEXT) -> None:
    target = root / ".claude" / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _run_hook(root: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(root)}
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps({"hook_event_name": "SessionStart"}),
        capture_output=True, text=True, env=env, timeout=60,
    )


def _context(result: subprocess.CompletedProcess) -> str:
    return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]


def test_no_residue_outputs_nothing(tmp_path):
    root = _project(tmp_path)
    _write(root, "rules/clean.md", "正常內容\n")

    result = _run_hook(root)

    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_lists_sync_conflicts_copies(tmp_path):
    root = _project(tmp_path)
    _write(root, ".sync-conflicts/rules/conflict.md")

    result = _run_hook(root)

    assert result.returncode == 0
    context = _context(result)
    assert "rules/conflict.md" in context
    assert ".sync-conflicts" in context


def test_lists_in_scope_marker_files_but_not_out_of_scope(tmp_path):
    """同一 fixture：hooks/ 下的標記檔列出，hook-logs/ 下的不列出（E2 正反對照）。"""
    root = _project(tmp_path)
    _write(root, "hooks/broken-hook.py")
    _write(root, "hook-logs/some-hook/run.log")

    result = _run_hook(root)

    context = _context(result)
    assert "hooks/broken-hook.py" in context
    assert "hook-logs" not in context


def test_out_of_scope_marker_text_only_outputs_nothing(tmp_path):
    root = _project(tmp_path)
    _write(root, "hook-logs/some-hook/run.log")
    _write(root, "handoff/pending/x.md")

    result = _run_hook(root)

    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_hook_reuses_sync_pull_scan_functions():
    """hook 與 sync-pull 匯入同一份判準函式，不另寫一份。"""
    sys.path.insert(0, str(HOOKS_DIR.parent))
    from lib import sync_conflict_residue

    spec = importlib.util.spec_from_file_location("residue_hook", HOOK_PATH)
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)

    assert hook.scan_conflict_marker_residue is sync_conflict_residue.scan_conflict_marker_residue
    assert hook.detect_conflict_residue is sync_conflict_residue.detect_conflict_residue


def test_registered_in_settings_session_start():
    settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    commands = [
        hook["command"]
        for group in settings["hooks"]["SessionStart"]
        for hook in group["hooks"]
    ]
    assert any(c.endswith("/session-start-sync-conflict-residue-hook.py") for c in commands)
