"""pytest 外掛：命令列路徑未涵蓋 pyproject testpaths 時，於終端摘要印警告。

Why：只帶部分 testpaths 執行時，輸出仍是 passed，收集範圍縮小的回歸因此
進入主線。本模組在 pytest 層生效，代理人、CI、人的任何呼叫方式皆涵蓋。

不警告：無路徑參數、參數涵蓋全部 testpaths、參數含檔案或 `::`（單檔/單測呼叫）。
只寫終端摘要，不改 exit code。

本檔於 hooks 包與 ticket 包各有一份相同副本（兩包各自同步到 consumer，須能獨立運作）；
修改時兩份同步。相容 Python 3.9。
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import pytest

_GUARD_ENV = "TESTPATHS_COVERAGE_WARNING_CHILD"
_COLLECTED_RE = re.compile(r"(\d+)(?:/\d+)? tests? collected")


def _resolve_testpaths(config) -> List[Path]:
    raw = config.getini("testpaths") or []
    return [(Path(str(config.rootpath)) / p).resolve() for p in raw]


def find_uncovered_testpaths(config) -> Optional[List[Path]]:
    """回傳未被命令列路徑涵蓋的 testpaths；不適用警告時回傳 None。"""
    testpaths = _resolve_testpaths(config)
    if not testpaths or not config.args:
        return None
    base = Path(str(config.invocation_params.dir))
    arg_paths = []
    for arg in config.args:
        if "::" in str(arg):
            return None
        p = (base / str(arg)).resolve()
        if p.is_file():
            return None
        arg_paths.append(p)
    uncovered = [
        t for t in testpaths
        if not any(a == t or a in t.parents for a in arg_paths)
    ]
    return uncovered or None


def _count_full_collection(config) -> Optional[int]:
    """於 rootdir 以預設選項（無路徑參數）子程序收集，取全量數；失敗回 None。"""
    env = dict(os.environ)
    env[_GUARD_ENV] = "1"
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q",
             "-p", "no:cacheprovider"],
            cwd=str(config.rootpath), env=env, capture_output=True,
            text=True, timeout=600,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        sys.stderr.write(
            "[testpaths-coverage] 全量收集失敗: %s: %s\n"
            % (type(exc).__name__, exc))
        return None
    if proc.returncode != 0:
        sys.stderr.write(
            "[testpaths-coverage] 全量收集子程序 rc=%s，全量數不可用\n"
            % proc.returncode)
        return None
    for line in reversed(proc.stdout.splitlines()):
        m = _COLLECTED_RE.search(line)
        if m:
            return int(m.group(1))
    sys.stderr.write("[testpaths-coverage] 全量收集輸出解析不到 collected 行\n")
    return None


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config, items):
    config._tp_cov_actual = len(items)


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    if os.environ.get(_GUARD_ENV) or hasattr(config, "workerinput"):
        return
    uncovered = find_uncovered_testpaths(config)
    if not uncovered:
        return
    actual = getattr(config, "_tp_cov_actual", None)
    full = _count_full_collection(config)
    root = Path(str(config.rootpath)).resolve()
    names = ", ".join(os.path.relpath(str(p), str(root)) for p in uncovered)
    terminalreporter.write_sep("=", "testpaths 覆蓋警告", yellow=True)
    terminalreporter.write_line(
        "[WARNING] 命令列路徑未涵蓋 pyproject 全部 testpaths，"
        "本次通過不代表全套件通過。"
    )
    terminalreporter.write_line(
        "未涵蓋: %s；實際收集 %s 項，全量 %s 項（預設選項）。"
        % (names, actual if actual is not None else "?",
           full if full is not None else "?")
    )
    terminalreporter.write_line("全套件: 在包目錄不帶路徑執行 pytest。")
