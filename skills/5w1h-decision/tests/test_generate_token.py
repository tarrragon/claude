"""generate_token --save：有框架 lib 沿用 get_hook_log_dir；無 lib 退回 cwd 並寫 stderr。"""

import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "generate_token.py"


def _run(script: Path, cwd: Path):
    return subprocess.run(
        [sys.executable, str(script), "--save"], cwd=cwd, capture_output=True, text=True
    )


def test_without_lib_falls_back_and_warns(tmp_path):
    # 腳本副本放在無 lib 的目錄樹（對照：拿掉 lib）
    script = tmp_path / "skills" / "5w1h-decision" / "scripts" / "generate_token.py"
    script.parent.mkdir(parents=True)
    shutil.copy(SCRIPT, script)
    work = tmp_path / "work"
    work.mkdir()
    r = _run(script, work)
    expected = work / ".claude" / "hook-logs" / "5w1h-tokens"
    assert r.returncode == 0, r.stderr
    assert str(expected) in r.stderr
    assert len(list(expected.glob("session-*.token"))) == 1


def test_with_lib_uses_framework_dir_without_fallback_message(tmp_path):
    r = _run(SCRIPT, tmp_path)
    assert r.returncode == 0, r.stderr
    assert "退回" not in r.stderr
    saved = Path(r.stdout.split("Saved: ")[1].strip())
    try:
        assert saved.parent.name == "5w1h-tokens"
        assert saved.parent.parent.name == "hook-logs"
    finally:
        saved.unlink(missing_ok=True)
