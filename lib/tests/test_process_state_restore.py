"""逐測試還原 cwd 與 os.environ 的注入測試（3.4.0-W1-288）。

正向對照（3.3.1-W1-001.4 E3 手法）：汙染檔改 cwd 與環境變數，檢查檔斷言兩者
未被改動。無 guard 的 conftest 必須紅（證明汙染真的穿透）；有 guard 必須綠。
"""

import subprocess
import sys
from pathlib import Path

LIB_DIR = Path(__file__).resolve().parents[1]

POLLUTE = '''
import os
def test_a_pollute():
    os.chdir("/")
    os.environ["W288_LEAK"] = "1"
    os.environ["PRESET_SESSION_VAR"] = "changed"
    os.environ.pop("W288_BASE", None)
'''
CHECK = '''
import os
def test_b_check():
    assert "W288_LEAK" not in os.environ
    assert os.environ.get("PRESET_SESSION_VAR") == "session"
    assert os.environ.get("W288_BASE") == "base"
    assert os.getcwd() != "/"
'''
CONFTEST_GUARD = f"""
import os, sys
sys.path.insert(0, {str(LIB_DIR)!r})
os.environ["PRESET_SESSION_VAR"] = "session"
os.environ["W288_BASE"] = "base"
from process_state_restore import process_state_guard  # noqa: F401
"""
CONFTEST_PLAIN = """
import os
os.environ["PRESET_SESSION_VAR"] = "session"
os.environ["W288_BASE"] = "base"
"""


def _run(tmp_path: Path, conftest: str) -> int:
    (tmp_path / "conftest.py").write_text(conftest)
    (tmp_path / "test_a_pollute.py").write_text(POLLUTE)
    (tmp_path / "test_b_check.py").write_text(CHECK)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(tmp_path)],
        cwd=tmp_path, capture_output=True, text=True,
    )
    return proc.returncode


def test_without_guard_pollution_leaks(tmp_path):
    assert _run(tmp_path, CONFTEST_PLAIN) != 0


def test_with_guard_pollution_is_restored(tmp_path):
    assert _run(tmp_path, CONFTEST_GUARD) == 0
