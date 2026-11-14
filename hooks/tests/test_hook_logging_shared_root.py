"""hook 日誌與 liveness 落共用狀態根（主 repo）的契約測試。

以 tmp 內建 main 與 linked worktree（wt）；子行程在 wt 內執行，環境不帶隔離旗標，
斷言日誌與 _liveness 寫到 main 而非 wt。附兩個正向對照：
1. 帶 HOOK_TEST_ISOLATION=1 時寫入不落 main（證明 fixture 能鑑別落點）。
2. 在 wt 內刻意洩漏到 main 時，哨兵（雙根）判紅。
"""

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from lib import liveness_session_isolation as iso

_CLAUDE_DIR = Path(__file__).resolve().parents[2]
_SCRIPT = (
    "import sys; sys.path.insert(0, sys.argv[1]);"
    "from lib.hook_logging import setup_hook_logging, mark_hook_entry;"
    "lg = setup_hook_logging('shared-root-probe');"
    "mark_hook_entry('shared-root-probe', lg)"
)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


@pytest.fixture
def main_and_wt(tmp_path):
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q", "-b", "main")
    _git(main, "config", "user.email", "t@example.com")
    _git(main, "config", "user.name", "t")
    (main / "CLAUDE.md").write_text("# main\n", encoding="utf-8")
    _git(main, "add", "CLAUDE.md")
    _git(main, "commit", "-q", "-m", "init")
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", str(wt), "-b", "wt-branch")
    return main.resolve(), wt.resolve()


def _probe(wt: Path, session_id: str, isolated_root: Path = None):
    env = {k: v for k, v in os.environ.items()
           if k not in ("CLAUDE_PROJECT_DIR", "HOOK_TEST_ISOLATION")}
    env["CLAUDE_CODE_SESSION_ID"] = session_id
    if isolated_root is not None:
        env["HOOK_TEST_ISOLATION"] = "1"
        env["CLAUDE_PROJECT_DIR"] = str(isolated_root)
    else:
        env["CLAUDE_PROJECT_DIR"] = str(wt)
    subprocess.run(
        [sys.executable, "-c", _SCRIPT, str(_CLAUDE_DIR)],
        cwd=str(wt), env=env, check=True, capture_output=True,
    )


def test_logs_and_liveness_land_in_main_not_wt(main_and_wt):
    main, wt = main_and_wt
    _probe(wt, "sess-shared")
    assert (main / ".claude" / "hook-logs" / "shared-root-probe").is_dir()
    assert (main / ".claude" / "hook-logs" / "_liveness" / "sess-shared.jsonl").is_file()
    assert not (wt / ".claude" / "hook-logs").exists()


def test_isolation_flag_keeps_writes_out_of_main(main_and_wt, tmp_path):
    """正向對照一：帶隔離旗標時不落 main；不帶時（上一測試）落 main，落點可鑑別。"""
    main, wt = main_and_wt
    iso_root = tmp_path / "iso"
    iso_root.mkdir()
    (iso_root / "CLAUDE.md").write_text("# iso\n", encoding="utf-8")
    _probe(wt, "sess-iso", isolated_root=iso_root)
    assert (iso_root / ".claude" / "hook-logs" / "_liveness" / "sess-iso.jsonl").is_file()
    assert not (main / ".claude" / "hook-logs").exists()


def test_sentinel_flags_leak_to_main_from_wt(main_and_wt):
    """正向對照二：real_root=wt 時，洩漏到主 repo 仍被雙根哨兵判紅。"""
    main, wt = main_and_wt
    before = iso.take_snapshot(wt, shared_root=main)
    _probe(wt, "real-looking-session-id")
    session = SimpleNamespace(exitstatus=0)
    leaks = iso.apply_snapshot_sentinel(session, wt, before, "real-looking-session-id")
    assert any("_liveness/real-looking-session-id.jsonl" in x for x in leaks)
    assert session.exitstatus == 1


def test_sentinel_same_root_snapshots_once(tmp_path):
    snap = iso.take_snapshot(tmp_path, shared_root=tmp_path)
    assert not any(k.startswith("shared:") for k in snap)
