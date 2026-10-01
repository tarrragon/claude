"""requires-python 宣告與實際最低可 import 版本一致（0.4.1-W1-039）。

以 subprocess 執行 `uv run --python <版本> --no-project` 實際 import 套件內全部模組：
- 宣告下限版本：必須全部 import 成功。
- 下限減一版（>= 3.9 時）：必須有模組 import 失敗，否則宣告偏高，應下調。
直譯器或 uv 不存在時 skip。
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "ticket_system"
RUNTIME_DEPS = ("pyyaml", "filelock")
PROBE = """
import importlib, pkgutil, sys
pkg = sys.argv[1]
root = importlib.import_module(pkg)
failed = []
for info in pkgutil.walk_packages(root.__path__, pkg + "."):
    if ".tests" in info.name:
        continue
    try:
        importlib.import_module(info.name)
    except Exception as exc:
        failed.append(info.name + ": " + type(exc).__name__ + ": " + str(exc))
print("\\n".join(failed))
sys.exit(1 if failed else 0)
"""
MIN_TESTED_MINOR = 9


def _declared_floor():
    text = (PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'requires-python\s*=\s*">=3\.(\d+)"', text)
    assert match, "pyproject.toml 的 requires-python 不是 >=3.N 形式"
    return int(match.group(1))


def _probe(minor):
    """回傳 (returncode, 輸出)；直譯器取不到時 skip。"""
    if shutil.which("uv") is None:
        pytest.skip("找不到 uv，無法以指定版本直譯器驗證")
    version = "3.%d" % minor
    found = subprocess.run(
        ["uv", "python", "find", version],
        capture_output=True, text=True, timeout=60,
    )
    if found.returncode != 0:
        pytest.skip("本機無 Python %s 直譯器，無法驗證宣告下限" % version)
    cmd = ["uv", "run", "--python", version, "--no-project"]
    for dep in RUNTIME_DEPS:
        cmd += ["--with", dep]
    cmd += ["python", "-c", PROBE, PACKAGE_NAME]
    env_cwd = str(PACKAGE_ROOT)
    result = subprocess.run(
        cmd, cwd=env_cwd, capture_output=True, text=True, timeout=600,
        env={**os.environ, "PYTHONPATH": env_cwd},
    )
    return result.returncode, result.stdout + result.stderr


def test_declared_floor_imports_all_modules():
    floor = _declared_floor()
    code, out = _probe(floor)
    assert code == 0, "宣告下限 3.%d 下有模組無法 import:\n%s" % (floor, out[-2000:])


def test_one_below_declared_floor_fails_to_import():
    """對照：下限減一版必須失敗，證明宣告沒有偏高（E1 對照）。"""
    below = _declared_floor() - 1
    if below < MIN_TESTED_MINOR:
        pytest.skip("下限減一版 3.%d 低於測試支援的最低版本" % below)
    code, _ = _probe(below)
    assert code != 0, (
        "3.%d 下所有模組皆可 import，requires-python 宣告偏高，請下調" % below
    )


def test_probe_detects_failure_positive_control():
    """正向對照：探針對必定失敗的輸入確實回非零。"""
    result = subprocess.run(
        [sys.executable, "-c", PROBE, "no_such_package_w1_039"],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode != 0
