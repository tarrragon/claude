"""Tests for sync-claude-pull.py post-sync hook import 驗證（1.4.0-W2-004）。

背景（framework issue #10 斷裂 4）：
  py_compile 只檢查語法不執行 import，consumer sync-pull 後若上游 lib 重構 /
  新增 dependency 導致 runtime import 斷裂（ModuleNotFoundError），同步主流程
  py_compile 全綠卻在 hook 實際觸發時才崩潰。本功能於 sync-pull 完成後自動
  呼叫 scripts/test-hook-imports.sh（W2-007 產出）做 import-level 煙霧測試。

涵蓋 acceptance：
  - sync-pull 完成後自動執行 hook import 煙霧測試（verify_hook_imports）
  - import 失敗時 stderr 輸出失敗清單並回傳非零 exit code
  - 腳本不存在 / 無法執行時 graceful skip（回 0，不阻擋同步主流程）
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location(
    "sync_claude_pull_hook_import_verify", _SCRIPT
)
assert _spec and _spec.loader
pull = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_hook_import_verify"] = pull
_spec.loader.exec_module(pull)  # type: ignore[union-attr]


# ============================================================================
# Helpers
# ============================================================================

def _make_test_script(project_root: Path) -> Path:
    """在 project_root 下建立 .claude/scripts/test-hook-imports.sh 佔位檔。"""
    script = project_root / ".claude" / "scripts" / "test-hook-imports.sh"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    return script


class _FakeCompleted:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


# ============================================================================
# 全通過 → 回 0
# ============================================================================

def test_returns_zero_when_all_pass(tmp_path, monkeypatch):
    """import 煙霧測試全通過時 verify_hook_imports 回 0。"""
    _make_test_script(tmp_path)
    monkeypatch.setattr(
        pull.subprocess, "run",
        lambda *a, **k: _FakeCompleted(0, stdout="All hooks passed import check.\n"),
    )
    assert pull.verify_hook_imports(tmp_path) == 0


# ============================================================================
# 失敗 → 回非零 + stderr 列失敗清單
# ============================================================================

def test_returns_nonzero_and_writes_failure_list_to_stderr(
    tmp_path, monkeypatch, capsys
):
    """import 失敗時回非零 exit code，且失敗清單輸出到 stderr。"""
    _make_test_script(tmp_path)
    failure_output = (
        "[FAIL] .claude/hooks/broken-hook.py\n"
        "Failed hooks:\n"
        "  - .claude/hooks/broken-hook.py\n"
    )
    monkeypatch.setattr(
        pull.subprocess, "run",
        lambda *a, **k: _FakeCompleted(1, stdout=failure_output),
    )

    rc = pull.verify_hook_imports(tmp_path)

    assert rc != 0
    captured = capsys.readouterr()
    assert "broken-hook.py" in captured.err


# ============================================================================
# 腳本不存在 → graceful skip（回 0）
# ============================================================================

def test_graceful_skip_when_script_missing(tmp_path):
    """驗證腳本不存在時 graceful skip 回 0，不阻擋同步主流程。"""
    # tmp_path 下未建立 test-hook-imports.sh
    assert pull.verify_hook_imports(tmp_path) == 0


# ============================================================================
# 子進程無法執行（OSError / Timeout）→ graceful skip（回 0）
# ============================================================================

def test_graceful_skip_on_subprocess_error(tmp_path, monkeypatch):
    """子進程 OSError / Timeout 時 graceful skip 回 0。"""
    _make_test_script(tmp_path)

    def _raise(*a, **k):
        raise subprocess.TimeoutExpired(cmd="bash", timeout=1)

    monkeypatch.setattr(pull.subprocess, "run", _raise)
    assert pull.verify_hook_imports(tmp_path) == 0
