"""Minimal gate-satisfying test for uc-fingerprint-drift-check-hook.py（0.2.1-W3-945）。

測試覆蓋：
| 測試 | 場景 | 驗證 |
|------|------|------|
| test_empty_stdin_fail_open | 空 stdin | main() 回傳 0，不崩潰 |
| test_malformed_json_fail_open | 畸形 JSON stdin | main() 回傳 0，不崩潰 |
| test_normal_input_non_target_file_returns_zero | Write 非 app-use-cases.md | main() 回傳 0 |
| test_liveness_entry_written_via_run_hook_safely | 經 run_hook_safely 執行 | _liveness/<session>.jsonl 寫入 1 筆 |
| test_production_uv_isolation_does_not_fail_open | 生產 `uv run --quiet` 隔離 venv 真實執行 | 不落入 uc_registry ImportError 降級分支 |

注意（TEST-BAL-010 覆蓋落差）：上四個 fail_open 測試名稱驗證的是 main()
在「空 stdin / 畸形 JSON / 非目標檔」等輸入下不崩潰，與 uc_registry 模組
是否能在隔離 venv 下真實 import 是完全不同的驗證範圍——本檔案原先沒有
任何測試以生產啟動方式覆蓋 uc_registry import，最後一項
`test_production_uv_isolation_does_not_fail_open` 補上此落差。
"""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest


HOOK_PATH = Path(__file__).parent.parent / "uc-fingerprint-drift-check-hook.py"


def _load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "uc_fingerprint_drift_check_hook_gate", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def hook_mod():
    return _load_hook_module()


def test_empty_stdin_fail_open(hook_mod, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    assert hook_mod.main() == 0


def test_malformed_json_fail_open(hook_mod, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO("{not valid json"))
    assert hook_mod.main() == 0


def test_normal_input_non_target_file_returns_zero(hook_mod, monkeypatch):
    input_data = {
        "tool_name": "Write",
        "tool_input": {"file_path": "docs/other-file.md"},
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(input_data)))
    assert hook_mod.main() == 0


def test_liveness_entry_written_via_run_hook_safely(hook_mod, monkeypatch, tmp_path):
    import lib.hook_logging as hook_logging_mod

    monkeypatch.setattr(hook_logging_mod, "get_project_root", lambda: tmp_path)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "test-session-945")
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))

    exit_code = hook_logging_mod.run_hook_safely(hook_mod.main, hook_mod.HOOK_NAME)
    assert exit_code == 0

    liveness_file = tmp_path / ".claude" / "hook-logs" / "_liveness" / "test-session-945.jsonl"
    assert liveness_file.exists()
    lines = liveness_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["hook"] == hook_mod.HOOK_NAME


def test_production_uv_isolation_does_not_fail_open():
    """以與生產完全相同的啟動方式（`uv run --quiet`，PEP 723 隔離 venv，
    只有 stdlib）執行本 hook，斷言 uc_registry import 正常完成（未走
    fail-open 分支）。

    鑑別力已於本票（TEST-BAL-010 防護）人工反證：暫時在
    doc_system/core/uc_registry.py 頂層加入 `import yaml`，本測試會因
    stderr 出現「uc_registry 載入失敗」而紅燈；還原後綠燈。此反證步驟
    不納入自動化（會真的污染 uc_registry.py），僅記錄於 ticket Solution
    供覆核。
    """
    payload = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": "docs/app-use-cases.md"},
    }

    result = subprocess.run(
        ["uv", "run", "--quiet", str(HOOK_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(HOOK_PATH.parent.parent.parent),  # 專案根目錄，供 get_project_root 定位
        timeout=30,
    )

    assert result.returncode == 0
    assert "載入失敗" not in result.stderr
