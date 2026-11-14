"""l10n-sync-verification-hook 自動 gen-l10n 的命令組成測試。

有 FVM 設定檔的專案須以 fvm 執行，否則生成檔由全域預設版產生；找不到 fvm 時
回報失敗，不改用裸 flutter。
"""

import importlib.util
import logging
import subprocess
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).resolve().parent.parent / "l10n-sync-verification-hook.py"
spec = importlib.util.spec_from_file_location("l10n_sync_verification_hook", HOOK_PATH)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

LOGGER = logging.getLogger("test-l10n-sync")


@pytest.fixture
def project(tmp_path):
    (tmp_path / ".git").mkdir()
    return tmp_path


def _capture_run(monkeypatch, returncode=0, raises=None):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(list(argv))
        if raises is not None:
            raise raises
        return subprocess.CompletedProcess(argv, returncode, stdout="", stderr="")

    monkeypatch.setattr(hook.subprocess, "run", fake_run)
    return calls


def test_with_fvmrc_runs_through_fvm(project, monkeypatch):
    (project / ".fvmrc").write_text('{"flutter": "3.24.0"}')
    calls = _capture_run(monkeypatch)

    ok, message = hook.run_flutter_gen_l10n(project, LOGGER)

    assert ok is True
    assert calls == [["fvm", "flutter", "gen-l10n"]]
    assert "fvm flutter gen-l10n" in message


def test_without_fvmrc_runs_bare_flutter(project, monkeypatch):
    calls = _capture_run(monkeypatch)

    ok, _ = hook.run_flutter_gen_l10n(project, LOGGER)

    assert ok is True
    assert calls == [["flutter", "gen-l10n"]]


def test_fvm_missing_reports_failure_without_bare_flutter_fallback(project, monkeypatch):
    (project / ".fvmrc").write_text('{"flutter": "3.24.0"}')
    calls = _capture_run(monkeypatch, raises=FileNotFoundError("fvm"))

    ok, message = hook.run_flutter_gen_l10n(project, LOGGER)

    assert ok is False
    assert calls == [["fvm", "flutter", "gen-l10n"]], "不得在 fvm 失敗後改呼叫裸 flutter"
    assert "fvm" in message
    assert "未改用全域 flutter" in message


def test_flutter_missing_without_fvm_keeps_original_message(project, monkeypatch):
    _capture_run(monkeypatch, raises=FileNotFoundError("flutter"))

    ok, message = hook.run_flutter_gen_l10n(project, LOGGER)

    assert ok is False
    assert "找不到 flutter 命令" in message


def test_error_message_repair_steps_follow_fvm(project):
    (project / ".fvmrc").write_text('{"flutter": "3.24.0"}')

    message = hook.generate_error_message({}, project)

    assert "1. 執行命令: fvm flutter gen-l10n" in message
    assert "2. 驗證生成成功: fvm flutter analyze" in message


def test_error_message_repair_steps_without_fvm(project):
    message = hook.generate_error_message({}, project)

    assert "1. 執行命令: flutter gen-l10n" in message
    assert "fvm" not in message
