"""install-skill-clis.py 引數解析：查用法與未知引數不得寫入 shim。

舊版只比對 sys.argv 是否含 --check，其餘引數（含 --help）一律執行安裝，
改寫 bin 目錄下全部 shim。本檔以子行程執行腳本，SKILL_CLI_BIN_DIR 與 HOME
皆指向暫存目錄，不觸及真實 ~/.local/bin。

對照：無引數安裝確實寫入 shim（證明「不寫入」斷言有鑑別力）。
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "install-skill-clis.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("install_skill_clis", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


_MOD = _load_module()


def _run(bin_dir: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["SKILL_CLI_BIN_DIR"] = str(bin_dir)
    env["HOME"] = str(bin_dir.parent)
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


def _written(bin_dir: Path) -> list:
    if not bin_dir.exists():
        return []
    return sorted(p.name for p in bin_dir.iterdir())


@pytest.fixture
def bin_dir(tmp_path: Path) -> Path:
    return tmp_path / "bin"


def test_no_args_installs_all_shims(bin_dir):
    """對照組：無引數執行會寫入全部 shim。"""
    result = _run(bin_dir)
    assert result.returncode == 0, result.stderr
    assert _written(bin_dir) == sorted(_MOD.CLI_NAMES)
    for cli in _MOD.CLI_NAMES:
        assert _MOD.SHIM_MARKER in (bin_dir / cli).read_text(encoding="utf-8")


@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_help_prints_usage_without_installing(bin_dir, flag):
    result = _run(bin_dir, flag)
    assert result.returncode == 0
    assert "usage" in result.stdout.lower()
    assert "--check" in result.stdout
    assert _written(bin_dir) == []


@pytest.mark.parametrize("args", [("--bogus",), ("extra",), ("--check", "--bogus")])
def test_unknown_args_error_without_installing(bin_dir, args):
    result = _run(bin_dir, *args)
    assert result.returncode != 0
    assert "unrecognized arguments" in result.stderr or "error" in result.stderr.lower()
    assert _written(bin_dir) == []


def test_check_reports_missing_without_writing(bin_dir):
    result = _run(bin_dir, "--check")
    assert result.returncode == 1
    assert "尚未 shim 化" in result.stderr
    assert _written(bin_dir) == []


def test_check_passes_after_install(bin_dir):
    assert _run(bin_dir).returncode == 0
    before = {cli: (bin_dir / cli).stat().st_mtime_ns for cli in _MOD.CLI_NAMES}
    result = _run(bin_dir, "--check")
    assert result.returncode == 0, result.stderr
    after = {cli: (bin_dir / cli).stat().st_mtime_ns for cli in _MOD.CLI_NAMES}
    assert before == after
