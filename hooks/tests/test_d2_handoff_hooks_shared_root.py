"""D2：三支 handoff hook 在 linked worktree 內改用共用狀態根（3.3.0-W1-204.1.2.11）。

不設 HOOK_TEST_ISOLATION：以真實 git linked worktree 驗證 cleanup 刪的是 MAIN 的
pending，兩支 reminder 掃描的是 MAIN 的根。E1 對照：把 get_shared_state_root 換回
原根（恆等函式）後，同一組情境的結果相反。
"""
import importlib.util
import subprocess
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

_CLAUDE_DIR = Path(__file__).resolve().parents[2]
for _p in (_CLAUDE_DIR, _CLAUDE_DIR / "hooks"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

_HOOK_DIR = _CLAUDE_DIR / "skills" / "ticket" / "hooks"
TID = "0.1.0-W1-001"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, _HOOK_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True)


@pytest.fixture
def checkouts(tmp_path, monkeypatch):
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q")
    _git(main, "config", "user.email", "t@t")
    _git(main, "config", "user.name", "t")
    (main / "CLAUDE.md").write_text("# t\n", encoding="utf-8")
    _git(main, "add", "CLAUDE.md")
    _git(main, "commit", "-q", "-m", "init")
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", str(wt), "-b", "wt-branch")
    main, wt = main.resolve(), wt.resolve()
    monkeypatch.delenv("HOOK_TEST_ISOLATION", raising=False)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(wt))
    monkeypatch.chdir(wt)
    return main, wt


def _run_main(hook, extra_patches, revert: bool):
    patches = list(extra_patches) + [patch("sys.stdout", StringIO())]
    if revert:
        patches.append(patch.object(hook, "get_shared_state_root", lambda r: r, create=True))
    for p in patches:
        p.start()
    try:
        return hook.main()
    finally:
        patch.stopall()


@pytest.mark.parametrize("revert", [False, True])
def test_cleanup_deletes_main_pending(checkouts, revert):
    main, _wt = checkouts
    hook = _load("d2_cleanup", "handoff-cleanup-hook.py")
    pending = main / ".claude" / "handoff" / "pending"
    pending.mkdir(parents=True)
    f = pending / f"{TID}.json"
    f.write_text("{}", encoding="utf-8")
    data = {"tool_name": "Bash",
            "tool_input": {"command": f"ticket track complete {TID}"},
            "tool_response": {"stdout": f"[OK] 已完成 Ticket {TID}", "stderr": "",
                              "interrupted": False, "isImage": False,
                              "noOutputExpected": False}}
    rc = _run_main(hook, [
        patch.object(hook, "read_json_from_stdin", return_value=data),
        patch.object(hook, "is_subagent_environment", return_value=False),
    ], revert)
    assert rc == 0
    # E1：換回原根（revert=True）時 MAIN 的檔案不會被刪，斷言翻紅
    assert (not f.exists()) is (not revert)


@pytest.mark.parametrize("filename", ["handoff-prompt-reminder-hook.py",
                                      "handoff-reminder-hook.py"])
@pytest.mark.parametrize("revert", [False, True])
def test_reminders_scan_main_root(checkouts, filename, revert):
    main, wt = checkouts
    hook = _load("d2_" + filename.split("-hook")[0].replace("-", "_"), filename)
    seen = []

    def spy(root, logger):
        seen.append(Path(root).resolve())
        return ([], 0) if filename == "handoff-reminder-hook.py" else []

    _run_main(hook, [
        patch.object(hook, "read_json_from_stdin",
                     return_value={"session_id": "d2", "prompt": "x"}),
        patch.object(hook, "scan_handoff_pending_directory", spy),
    ], revert)
    assert seen, "scan_handoff_pending_directory 未被呼叫"
    assert (seen[0] == main) is (not revert)
    assert (seen[0] == wt) is revert
