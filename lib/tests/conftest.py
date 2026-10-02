"""lib 測試 rootdir 隔離：只帶 ../lib/tests 執行時補上專案根重導與 liveness 隔離。

Why：hooks 套件的隔離（hooks/tests/conftest.py）只在收集 hooks/tests 時載入；
在 .claude/hooks 下只帶 ../lib/tests 執行時不載入，lib 測試間接呼叫的 hook
（例：markdown-formatter 寫 .cleanup_trigger）會寫進真實 .claude/hook-logs。
實測 .claude/hooks/conftest.py 不被 ../lib/tests 的收集載入（位於收集樹之外），
故改在 lib/tests 自有 conftest 處理。

與 hooks/tests/conftest.py 並存（hooks 套件預設 testpaths 含 ../lib/tests）：
HOOK_TEST_ISOLATION 已為 1 表示 hooks 的隔離已生效，本檔不重複設定。
"""

import os
import shutil
import tempfile
from pathlib import Path

import pytest

from lib import liveness_session_isolation as _liveness_iso

_STATE = {"root": None, "patch": None}


def pytest_configure(config):
    if os.environ.get("HOOK_TEST_ISOLATION") == "1":
        return
    root = Path(tempfile.mkdtemp(prefix="lib_project_root_"))
    (root / "CLAUDE.md").write_text("# isolated test project root\n", encoding="utf-8")
    mp = pytest.MonkeyPatch()
    mp.setenv("CLAUDE_PROJECT_DIR", str(root))
    mp.setenv("HOOK_TEST_ISOLATION", "1")
    mp.setenv(_liveness_iso.ENV_SESSION_ID, _liveness_iso.new_test_session_id())
    _STATE["root"], _STATE["patch"] = root, mp


def pytest_sessionfinish(session, exitstatus):
    """洩漏哨兵：僅在本檔自行建立隔離時檢查（hooks 套件已有同一哨兵）。"""
    if _STATE["patch"] is not None:
        _liveness_iso.apply_leak_sentinel(session, Path(__file__).resolve().parents[3])


def pytest_unconfigure(config):
    if _STATE["patch"] is not None:
        _STATE["patch"].undo()
    if _STATE["root"] is not None:
        shutil.rmtree(_STATE["root"], ignore_errors=True)
    _STATE["root"] = _STATE["patch"] = None
