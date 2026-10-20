"""hooks conftest 依賴檢查的行為測試（0.5.0-W1-353.1）。

E2：缺 yaml 的環境以單一明確訊息結束；E1：正常環境不觸發。
以子程序執行 pytest，缺 yaml 以 sitecustomize 阻擋 yaml 匯入模擬。
"""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
EXPECTED_CMD = "uv --directory <checkout>/.claude/hooks run pytest <path>"


def _make_project(tmp_path):
    """在 tmp 建最小 rootdir：複製 conftest 與其匯入的外掛，附一個必過測試。"""
    (tmp_path / "conftest.py").write_text((HOOKS_DIR / "conftest.py").read_text(encoding="utf-8"), encoding="utf-8")
    plugin = HOOKS_DIR / "testpaths_coverage_warning.py"
    (tmp_path / plugin.name).write_text(plugin.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")


def _run(tmp_path, block_yaml):
    env = dict(os.environ)
    env.pop("HOOKS_TEST_GATE_TIMING_FILE", None)
    env["PYTHONPATH"] = str(tmp_path)
    if block_yaml:
        # 包裝 find_spec 使 yaml 視為缺失（不動 import 機制，避免干擾 pytest 自身匯入）
        (tmp_path / "sitecustomize.py").write_text(
            textwrap.dedent(
                """
                import importlib.util

                _orig = importlib.util.find_spec

                def _find_spec(name, package=None):
                    if name == "yaml":
                        return None
                    return _orig(name, package)

                importlib.util.find_spec = _find_spec
                """
            ),
            encoding="utf-8",
        )
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "--rootdir", str(tmp_path), str(tmp_path / "test_ok.py")],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_missing_yaml_exits_with_single_clear_message(tmp_path):
    _make_project(tmp_path)
    result = _run(tmp_path, block_yaml=True)
    out = result.stdout + result.stderr
    assert result.returncode != 0
    assert EXPECTED_CMD in out
    assert "yaml" in out
    assert "passed" not in out and "failed" not in out


def test_normal_environment_does_not_trigger(tmp_path):
    _make_project(tmp_path)
    result = _run(tmp_path, block_yaml=False)
    out = result.stdout + result.stderr
    assert EXPECTED_CMD not in out
    assert result.returncode == 0
    assert "1 passed" in out
