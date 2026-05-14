"""Tests for build-staleness-check-hook.

涵蓋三場景：
- build 過期（src 較新且超過閾值）
- build 較新（fresh）
- build 缺失（missing manifest）

加碼：no_src（src 不存在）、剛 build 完（差距在閾值內）。
"""

from __future__ import annotations

import importlib.util
import os
import time
from pathlib import Path

import pytest

HOOK_PATH = (
    Path(__file__).resolve().parent.parent / "build-staleness-check-hook.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "build_staleness_check_hook", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def hook_mod():
    return _load_module()


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "build" / "development").mkdir(parents=True)
    return tmp_path


def _write(path: Path, content: str = "x", mtime: float | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    if mtime is not None:
        os.utime(path, (mtime, mtime))


class TestCheckBuildStaleness:
    def test_stale_when_src_newer_beyond_threshold(self, hook_mod, project_root):
        now = time.time()
        # build 8 個月前
        _write(project_root / "build" / "development" / "manifest.json",
               mtime=now - 8 * 30 * 86400)
        # src 現在
        _write(project_root / "src" / "overview" / "controller.js", mtime=now)

        status, message = hook_mod.check_build_staleness(project_root)
        assert status == "stale"
        assert "npm run build:dev" in message
        assert "過期" in message

    def test_fresh_when_build_newer_than_src(self, hook_mod, project_root):
        now = time.time()
        _write(project_root / "src" / "a.js", mtime=now - 3600)
        _write(project_root / "build" / "development" / "manifest.json", mtime=now)

        status, message = hook_mod.check_build_staleness(project_root)
        assert status == "fresh"
        assert message == ""

    def test_fresh_when_diff_within_threshold(self, hook_mod, project_root):
        """src 比 build 新但差距 < 1 小時（剛 build 完場景）。"""
        now = time.time()
        _write(project_root / "build" / "development" / "manifest.json",
               mtime=now - 600)  # 10 分鐘前
        _write(project_root / "src" / "a.js", mtime=now)

        status, _ = hook_mod.check_build_staleness(project_root)
        assert status == "fresh"

    def test_missing_when_manifest_absent(self, hook_mod, project_root):
        _write(project_root / "src" / "a.js")
        # 不建立 manifest.json
        status, message = hook_mod.check_build_staleness(project_root)
        assert status == "missing"
        assert "npm run build:dev" in message
        assert "尚未" in message or "重建" in message

    def test_no_src_when_src_missing(self, hook_mod, tmp_path):
        """src 不存在 → 不發提示（避免在非 extension 倉誤觸發）。"""
        status, message = hook_mod.check_build_staleness(tmp_path)
        assert status == "no_src"
        assert message == ""


class TestMainEntry:
    def test_main_returns_zero_on_stale(self, hook_mod, project_root, monkeypatch, capsys):
        now = time.time()
        _write(project_root / "build" / "development" / "manifest.json",
               mtime=now - 8 * 30 * 86400)
        _write(project_root / "src" / "a.js", mtime=now)

        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project_root))
        rc = hook_mod.main()
        captured = capsys.readouterr()

        assert rc == 0  # 不阻擋
        assert "npm run build:dev" in captured.out

    def test_main_silent_on_fresh(self, hook_mod, project_root, monkeypatch, capsys):
        now = time.time()
        _write(project_root / "src" / "a.js", mtime=now - 7200)
        _write(project_root / "build" / "development" / "manifest.json", mtime=now)

        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project_root))
        rc = hook_mod.main()
        captured = capsys.readouterr()

        assert rc == 0
        assert captured.out == ""

    def test_main_returns_zero_on_missing(self, hook_mod, project_root, monkeypatch, capsys):
        _write(project_root / "src" / "a.js")
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project_root))
        rc = hook_mod.main()
        captured = capsys.readouterr()

        assert rc == 0
        assert "npm run build:dev" in captured.out
