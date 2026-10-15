"""pre-test-scan（dart-test-async-guardian）liveness 進入紀錄測試。

涵蓋：單獨執行與分派程序內兩種情況皆寫入 liveness；既有行為不變（E1 對照）；
未包裝版本不寫 liveness（E2 正向對照，證明斷言有鑑別力）。
liveness 寫入落在每測試專屬暫存專案根，不碰真實 .claude/hook-logs。
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
WORKTREE_ROOT = HOOKS_DIR.parent.parent
HOOK_REL = ".claude/skills/dart-test-async-guardian/hooks/pre-test-scan.py"
HOOK_PATH = WORKTREE_ROOT / HOOK_REL
SESSION = "pytest-pre-test-scan-liveness"

_WRAPPED_CALL = 'sys.exit(run_hook_safely(main, "pre-test-scan"))'

_spec = importlib.util.spec_from_file_location("hook_dispatcher_module", HOOKS_DIR / "hook-dispatcher.py")
disp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(disp)

NON_TEST_PAYLOAD = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls -la"}})
MISSING_PATH_PAYLOAD = json.dumps(
    {"tool_name": "Bash", "tool_input": {"command": "flutter test test/no_such_dir_xyz/a_test.dart"}})
NON_BASH_PAYLOAD = json.dumps({"tool_name": "Read", "tool_input": {}})
EQUIVALENCE_PAYLOADS = [NON_TEST_PAYLOAD, MISSING_PATH_PAYLOAD, NON_BASH_PAYLOAD, "", "not json"]


@pytest.fixture
def proj(tmp_path, monkeypatch):
    """每測試專屬專案根；env 子程序繼承、in-process 分派同樣讀得到。"""
    root = tmp_path / "proj"
    root.mkdir()
    (root / "CLAUDE.md").write_text("# t\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
    monkeypatch.setenv("HOOK_TEST_ISOLATION", "1")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SESSION)
    monkeypatch.chdir(root)
    return root


def _liveness_hooks(root: Path):
    f = root / ".claude" / "hook-logs" / "_liveness" / (SESSION + ".jsonl")
    if not f.exists():
        return []
    return [json.loads(line)["hook"] for line in f.read_text(encoding="utf-8").splitlines() if line]


def _run_standalone(script: Path, payload: str, cwd: Path):
    r = subprocess.run([sys.executable, str(script)], input=payload, capture_output=True,
                       text=True, cwd=str(cwd), env=os.environ.copy())
    return r.returncode, r.stdout


def _unwrapped_copy(tmp_path: Path) -> Path:
    """改動前行為的等價版本：去掉 lib 匯入與包裝，入口回到 sys.exit(main())。"""
    src = HOOK_PATH.read_text(encoding="utf-8")
    assert _WRAPPED_CALL in src
    src = src.replace(_WRAPPED_CALL, "sys.exit(main())")
    src = src.replace("from lib import run_hook_safely  # noqa: E402\n", "")
    copy = tmp_path / "legacy-pre-test-scan.py"
    copy.write_text(src, encoding="utf-8")
    return copy


class TestLivenessWritten:
    def test_standalone_run_writes_one_liveness_entry(self, proj):
        code, _ = _run_standalone(HOOK_PATH, NON_TEST_PAYLOAD, proj)
        assert code == 0
        assert _liveness_hooks(proj) == ["pre-test-scan"]

    def test_standalone_run_writes_liveness_on_each_trigger(self, proj):
        _run_standalone(HOOK_PATH, NON_TEST_PAYLOAD, proj)
        _run_standalone(HOOK_PATH, MISSING_PATH_PAYLOAD, proj)
        assert _liveness_hooks(proj) == ["pre-test-scan", "pre-test-scan"]

    def test_dispatch_inprocess_writes_liveness(self, proj):
        results = disp.dispatch([{"path": HOOK_REL}], NON_TEST_PAYLOAD, WORKTREE_ROOT,
                                budget=30.0, inprocess=True)
        assert [(r.name, r.code) for r in results] == [("pre-test-scan", 0)]
        assert _liveness_hooks(proj) == ["pre-test-scan"]

    def test_dispatch_subprocess_writes_liveness(self, proj):
        results = disp.dispatch([{"path": HOOK_REL}], NON_TEST_PAYLOAD, WORKTREE_ROOT,
                                budget=30.0, inprocess=False)
        assert [(r.name, r.code) for r in results] == [("pre-test-scan", 0)]
        assert _liveness_hooks(proj) == ["pre-test-scan"]


class TestBehaviorUnchanged:
    """E1：同一組 payload，未包裝版本與現行版本的 exit code 與 stdout 相同。"""

    @pytest.mark.parametrize("payload", EQUIVALENCE_PAYLOADS)
    def test_exit_code_and_stdout_match_legacy(self, proj, tmp_path, payload):
        legacy = _unwrapped_copy(tmp_path)
        assert _run_standalone(HOOK_PATH, payload, proj) == _run_standalone(legacy, payload, proj)

    def test_non_test_command_and_missing_path_exit_zero_silently(self, proj):
        assert _run_standalone(HOOK_PATH, NON_TEST_PAYLOAD, proj) == (0, "")
        assert _run_standalone(HOOK_PATH, MISSING_PATH_PAYLOAD, proj) == (0, "")


class TestDiscrimination:
    """E2：未包裝版本不寫 liveness，證明 liveness 斷言會對缺口翻紅。"""

    def test_unwrapped_version_writes_no_liveness(self, proj, tmp_path):
        legacy = _unwrapped_copy(tmp_path)
        code, _ = _run_standalone(legacy, NON_TEST_PAYLOAD, proj)
        assert code == 0
        assert _liveness_hooks(proj) == []
