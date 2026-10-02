"""liveness 隔離：洩漏哨兵 E2 正向對照與 session id 前綴。"""

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from lib import liveness_session_isolation as iso

_HOOKS_ROOT = Path(__file__).resolve().parents[1]
_LEAK_SCRIPT = (
    "import sys; sys.path.insert(0, sys.argv[1]);"
    "from pathlib import Path;"
    "from lib.hook_logging import mark_hook_entry;"
    "mark_hook_entry('leak-probe', project_root=Path(sys.argv[2]))"
)


def _bypass_write(real_root: Path, session_id: str) -> None:
    """繞過重導：subprocess 直接以 project_root 指向「真實根」寫 liveness。"""
    env = {**os.environ, iso.ENV_SESSION_ID: session_id}
    subprocess.run(
        [sys.executable, "-c", _LEAK_SCRIPT, str(_HOOKS_ROOT.parent), str(real_root)],
        env=env, check=True, capture_output=True,
    )


class TestSessionId:
    def test_current_test_session_uses_pytest_prefix(self):
        assert os.environ[iso.ENV_SESSION_ID].startswith(iso.SESSION_ID_PREFIX)


class TestLeakSentinel:
    def test_e2_bypass_write_is_judged_failure_then_clean_passes(self, tmp_path):
        fake_real = tmp_path / "real"
        session = SimpleNamespace(exitstatus=0)

        _bypass_write(fake_real, iso.SESSION_ID_PREFIX + "bypass")
        leaked = iso.apply_leak_sentinel(session, fake_real)
        assert [p.name for p in leaked] == ["pytest-bypass.jsonl"]
        assert session.exitstatus == 1

        for p in leaked:
            p.unlink()
        session2 = SimpleNamespace(exitstatus=0)
        assert iso.apply_leak_sentinel(session2, fake_real) == []
        assert session2.exitstatus == 0

    def test_real_session_file_is_not_a_leak(self, tmp_path):
        _bypass_write(tmp_path, "real-session-abc")
        assert iso.find_leaked_liveness_files(tmp_path) == []

    def test_missing_liveness_dir_is_clean(self, tmp_path):
        assert iso.find_leaked_liveness_files(tmp_path) == []
