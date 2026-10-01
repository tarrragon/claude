"""testpaths 覆蓋警告外掛測試：以已知收集數的 fixture 專案（a=3 項、b=2 項）驗證。"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_PLUGIN = Path(__file__).resolve().parents[1] / "testpaths_coverage_warning.py"
_REAL_CONFTEST = Path(__file__).resolve().parents[1] / "conftest.py"
_A_COUNT, _B_COUNT = 3, 2


@pytest.fixture
def proj(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\ntestpaths = ["a", "b"]\n', encoding="utf-8")
    (tmp_path / "conftest.py").write_text(
        "from testpaths_coverage_warning import (\n"
        "    pytest_collection_modifyitems, pytest_terminal_summary)\n",
        encoding="utf-8")
    shutil.copy(_PLUGIN, tmp_path / "testpaths_coverage_warning.py")
    for name, n in (("a", _A_COUNT), ("b", _B_COUNT)):
        (tmp_path / name).mkdir()
        body = "".join("def test_%d():\n    pass\n" % i for i in range(n))
        (tmp_path / name / ("test_%s.py" % name)).write_text(body, encoding="utf-8")
    return tmp_path


def _run(proj, *args):
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *args],
        cwd=str(proj), capture_output=True, text=True)


def test_partial_testpaths_warns_with_both_counts(proj):
    r = _run(proj, "a")
    assert "testpaths 覆蓋警告" in r.stdout
    m = re.search(r"實際收集 (\d+) 項，全量 (\d+) 項", r.stdout)
    assert m, r.stdout
    assert int(m.group(1)) == _A_COUNT
    assert int(m.group(2)) == _A_COUNT + _B_COUNT
    assert "未涵蓋: b" in r.stdout


def test_warning_visible_under_q(proj):
    r = _run(proj, "-q", "a")
    m = re.search(r"實際收集 (\d+) 項，全量 (\d+) 項", r.stdout)
    assert m, r.stdout
    assert (int(m.group(1)), int(m.group(2))) == (_A_COUNT, _A_COUNT + _B_COUNT)


@pytest.mark.parametrize("args", [
    [],
    ["a", "b"],
    ["a/test_a.py"],
    ["a/test_a.py::test_0"],
])
def test_no_warning_when_covered_or_single_target(proj, args):
    r = _run(proj, "-q", *args)
    assert "testpaths 覆蓋警告" not in r.stdout
    assert r.returncode == 0


def test_exit_code_unchanged_by_warning(proj):
    (proj / "b" / "test_b.py").write_text("def test_fail():\n    assert False\n")
    assert _run(proj, "a").returncode == 0
    assert _run(proj, "b").returncode == 1
    assert _run(proj, "a", "b").returncode == 1


def test_real_conftest_exposes_plugin_hooks():
    text = _REAL_CONFTEST.read_text(encoding="utf-8")
    assert "testpaths_coverage_warning" in text
    assert "pytest_terminal_summary" in text
