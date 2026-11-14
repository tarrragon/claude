"""install-skill-clis.py 遇到既有目標檔時的寫入判定。

uv tool install 在 bin 目錄放的是指向 tool 環境入口檔的 symlink；舊版以
write_text 順著 symlink 寫入，把 shim 寫進 tool 環境、改壞該環境。本檔驗證：
symlink 與非 shim 的既有檔不寫入並警告，判定失敗時同樣不寫入；含 SHIM_MARKER
的既有一般檔照常更新（對照組）。

所有寫入都在 tmp_path 下，SKILL_CLI_BIN_DIR 與 HOME 皆指向暫存目錄。
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
    spec = importlib.util.spec_from_file_location("install_skill_clis_existing", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


_MOD = _load_module()
_CLI = "skill-sync"


def _run(bin_dir: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["SKILL_CLI_BIN_DIR"] = str(bin_dir)
    env["HOME"] = str(bin_dir.parent)
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        capture_output=True, text=True, env=env, timeout=60,
    )


@pytest.fixture
def bin_dir(tmp_path: Path) -> Path:
    d = tmp_path / "bin"
    d.mkdir()
    return d


def _uv_style_symlink(tmp_path: Path, bin_dir: Path) -> tuple[Path, bytes]:
    """模擬 uv tool install：<tools>/skill-sync/bin/skill-sync，bin 目錄放 symlink。"""
    entry = tmp_path / "tools" / "skill-sync" / "bin" / _CLI
    entry.parent.mkdir(parents=True)
    original = b"#!/bin/sh\n'''exec' python \"$0\" \"$@\"\n' '''\nprint('uv entry')\n"
    entry.write_bytes(original)
    entry.chmod(0o755)
    (bin_dir / _CLI).symlink_to(entry)
    return entry, original


def test_symlink_target_left_untouched_and_warned(tmp_path, bin_dir):
    entry, original = _uv_style_symlink(tmp_path, bin_dir)

    result = _run(bin_dir)

    assert result.returncode == 0, result.stderr
    assert (bin_dir / _CLI).is_symlink()
    assert entry.read_bytes() == original
    for stream in (result.stdout, result.stderr):
        assert f"{bin_dir / _CLI}" in stream and "symlink" in stream
        assert "uv tool install --force --from <skill 目錄> skill-sync" in stream
        assert "uv tool uninstall skill-sync" in stream
    # 其他 CLI 照常安裝
    others = [c for c in _MOD.CLI_NAMES if c != _CLI]
    for cli in others:
        assert _MOD.SHIM_MARKER in (bin_dir / cli).read_text(encoding="utf-8")


def test_foreign_regular_file_not_overwritten(bin_dir):
    foreign = b"#!/bin/sh\necho user-installed\n"
    (bin_dir / _CLI).write_bytes(foreign)

    result = _run(bin_dir)

    assert result.returncode == 0, result.stderr
    assert (bin_dir / _CLI).read_bytes() == foreign
    assert "不是本機制產生的 shim" in result.stdout
    assert "不是本機制產生的 shim" in result.stderr


def test_existing_shim_is_updated(bin_dir):
    """對照組：含 SHIM_MARKER 的既有一般檔照常更新為目前版本，且不發警告。"""
    (bin_dir / _CLI).write_text(f"#!/bin/sh\n{_MOD.SHIM_MARKER} 舊版\nexit 1\n", encoding="utf-8")

    result = _run(bin_dir)

    assert result.returncode == 0, result.stderr
    assert (bin_dir / _CLI).read_text(encoding="utf-8") == _MOD.shim_body(_CLI)
    assert "WARNING" not in result.stdout + result.stderr


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root 無視檔案權限")
def test_unreadable_file_not_written(bin_dir):
    target = bin_dir / _CLI
    target.write_bytes(b"#!/bin/sh\nexit 0\n")
    target.chmod(0o000)
    try:
        assert _MOD.classify_target(target) == _MOD.UNREADABLE
        result = _run(bin_dir)
        assert result.returncode == 0, result.stderr
        target.chmod(0o600)
        assert target.read_bytes() == b"#!/bin/sh\nexit 0\n"
        assert "狀態讀取失敗" in result.stdout
    finally:
        target.chmod(0o600)


def test_lstat_failure_classified_unreadable_and_not_written(bin_dir, monkeypatch):
    target = bin_dir / _CLI
    real_lstat = os.lstat

    def failing_lstat(path, *args, **kwargs):
        if Path(path) == target:
            raise PermissionError("模擬 lstat 失敗")
        return real_lstat(path, *args, **kwargs)

    monkeypatch.setattr(os, "lstat", failing_lstat)
    monkeypatch.setenv("SKILL_CLI_BIN_DIR", str(bin_dir))
    assert _MOD.classify_target(target) == _MOD.UNREADABLE

    assert _MOD.install() == 0
    assert not target.exists()


def test_check_does_not_count_symlink_as_shim(tmp_path, bin_dir):
    """舊版寫穿後 symlink 指向的入口檔含 SHIM_MARKER；--check 不得把它算成 shim。"""
    entry, _ = _uv_style_symlink(tmp_path, bin_dir)
    entry.write_text(_MOD.shim_body(_CLI), encoding="utf-8")
    _run(bin_dir)  # 其他 CLI 寫成 shim

    result = _run(bin_dir, "--check")

    assert result.returncode == 1
    assert _CLI in result.stderr
