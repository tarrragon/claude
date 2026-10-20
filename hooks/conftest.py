"""hooks 測試包 rootdir conftest：載入 testpaths 覆蓋警告外掛與 gate 計時外掛。

命令列路徑未涵蓋 pyproject 全部 testpaths 時，pytest 終端摘要印警告（不改 exit code）。
單檔 / `::` 呼叫（hooks-test-gate）不警告。邏輯見 testpaths_coverage_warning.py。

gate 計時外掛（2026-10 細化計時）：僅在環境變數 HOOKS_TEST_GATE_TIMING_FILE 有值時定義
pytest_configure / pytest_unconfigure。未設時模組不含這兩個 hook，一般 pytest 執行
行為與輸出不變。外掛只寫時刻檔，任何失敗只寫 stderr，不改測試結果。
"""

import atexit
import json
import os
import sys
import time

from testpaths_coverage_warning import (  # noqa: F401
    pytest_collection_modifyitems,
    pytest_terminal_summary,
)

import importlib.util

# hooks 測試必要的第三方依賴（對應 pyproject.toml dependencies：pyyaml 的匯入名為 yaml）。
# 缺依賴時讀票等路徑會退回快照，以業務斷言失敗出現而被誤判為回歸。
_REQUIRED_MODULES = ("yaml",)


def _missing_required_modules():
    return [m for m in _REQUIRED_MODULES if importlib.util.find_spec(m) is None]


def pytest_sessionstart(session):
    missing = _missing_required_modules()
    if missing:
        import pytest

        pytest.exit(
            "hooks 測試缺少必要依賴: %s。請改用正確指令執行："
            "uv --directory <checkout>/.claude/hooks run pytest <path>" % ", ".join(missing),
            returncode=4,
        )


_TIMING_ENV = "HOOKS_TEST_GATE_TIMING_FILE"
_timing_marks = {}


def _load1():
    try:
        return os.getloadavg()[0]
    except (OSError, AttributeError):
        return None


def _flush_timing_marks():
    """把目前累積的時刻寫入計時檔；失敗只寫 stderr（不影響測試結果）。"""
    path = os.environ.get(_TIMING_ENV)
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(_timing_marks, fh)
    except (OSError, ValueError, TypeError) as exc:
        sys.stderr.write("[gate-timing-plugin] 寫入計時檔失敗: %s: %s\n" % (type(exc).__name__, exc))


def _atexit_mark():
    _timing_marks["atexit"] = time.time()
    _flush_timing_marks()


def _timing_configure(config):
    _timing_marks["configure"] = time.time()
    _timing_marks["load1_start"] = _load1()
    # atexit 為後進先出：在此註冊，晚於本點註冊的處理器會先跑，本處理器盡量排在最後
    atexit.register(_atexit_mark)


def _timing_unconfigure(config):
    # unconfigure 發生於終端摘要之後
    _timing_marks["unconfigure"] = time.time()
    _timing_marks["load1_end"] = _load1()
    _flush_timing_marks()


if os.environ.get(_TIMING_ENV):
    pytest_configure = _timing_configure
    pytest_unconfigure = _timing_unconfigure
