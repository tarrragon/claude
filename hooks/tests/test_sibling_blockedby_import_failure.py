"""sibling-blockedby-validator：ticket_system 無法匯入時的處置（fail-closed）。

修改前，終態常數在模組層匯入，失敗時在 run_hook_safely 之外中止（exit 1，等同放行）。
修改後延遲到確認是 claim／complete 命令才匯入，失敗即阻擋並說明原因；其他命令不受影響。
"""

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).parent.parent
_HOOK_PATH = _HOOKS_DIR / "sibling-blockedby-validator-hook.py"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))


@pytest.fixture
def hook_module():
    spec = importlib.util.spec_from_file_location("sibling_blockedby_validator_import", _HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_main(hook_module, monkeypatch, command):
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    return hook_module.main()


def _break_import(hook_module, monkeypatch):
    def unavailable():
        raise ImportError("No module named 'ticket_system'")
    monkeypatch.setattr(hook_module, "terminal_statuses", unavailable)


@pytest.mark.parametrize("command", [
    "ticket track claim 3.3.0-W1-001",
    "ticket track complete 3.3.0-W1-001",
])
def test_import_failure_blocks_ticket_transition(hook_module, monkeypatch, capsys, command):
    _break_import(hook_module, monkeypatch)
    assert _run_main(hook_module, monkeypatch, command) == 2
    err = capsys.readouterr().err
    assert "無法載入 ticket_system" in err and "claim／complete" in err


@pytest.mark.parametrize("command", [
    "git status",
    "ticket track query 3.3.0-W1-001",
])
def test_import_failure_does_not_affect_other_commands(hook_module, monkeypatch, command):
    """反向對照：非 claim／complete 命令在匯入失敗時照常放行。"""
    _break_import(hook_module, monkeypatch)
    assert _run_main(hook_module, monkeypatch, command) == 0


def test_module_loads_without_ticket_system_on_path(tmp_path):
    """模組本身不再於載入期匯入 ticket_system：只複製 hooks 與 lib，載入不拋例外。"""
    probe = (
        "import importlib.util, sys\n"
        "spec = importlib.util.spec_from_file_location('h', sys.argv[1])\n"
        "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
        "try:\n"
        "    m.terminal_statuses()\n"
        "except ImportError:\n"
        "    print('IMPORT_DEFERRED')\n"
    )
    import shutil
    claude = tmp_path / ".claude"
    shutil.copytree(_HOOKS_DIR.parent / "lib", claude / "lib",
                    ignore=shutil.ignore_patterns("tests", "__pycache__"))
    (claude / "hooks").mkdir(parents=True)
    shutil.copy(_HOOK_PATH, claude / "hooks" / _HOOK_PATH.name)
    proc = subprocess.run(
        [sys.executable, "-c", probe, str(claude / "hooks" / _HOOK_PATH.name)],
        capture_output=True, text=True, timeout=60, cwd=tmp_path,
    )
    assert proc.returncode == 0, proc.stderr
    assert "IMPORT_DEFERRED" in proc.stdout


def test_entry_does_not_declare_fail_closed():
    """本 hook 對每個 Bash 命令執行，不整支宣告 fail_closed。

    dispatcher 以檔案中的 fail_closed=True 判定逾時與載入期例外的結束碼；宣告後
    單支逾時就會擋下全部 Bash 命令。阻擋只限 main() 已辨識的 claim／complete。
    """
    assert "fail_closed=True" not in _HOOK_PATH.read_text(encoding="utf-8")
