"""fvm-launcher-guard-hook 測試。

正向對照（E2）：有 .fvmrc 時五種裸 flutter／dart 命令被擋；反向對照：fvm 前綴、
無 FVM 設定檔、grep／heredoc／註解中的字樣、釘選 SDK 路徑皆放行。
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

hook_dir = Path(__file__).parent.parent
sys.path.insert(0, str(hook_dir))
sys.path.insert(0, str(hook_dir.parent))

spec = importlib.util.spec_from_file_location("fvm_launcher_guard_hook", hook_dir / "fvm-launcher-guard-hook.py")
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


@pytest.fixture
def fvm_project(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".fvmrc").write_text('{"flutter": "3.24.0"}')
    (tmp_path / "app").mkdir()
    return tmp_path


@pytest.fixture
def plain_project(tmp_path):
    root = tmp_path / "plain"
    root.mkdir()
    (root / ".git").mkdir()
    return root


BLOCKED = [
    "flutter test",
    "flutter analyze",
    "flutter gen-l10n",
    "dart format lib",
    "dart run build_runner build",
    "FOO=1 flutter test test/a_test.dart",
    "python3 .claude/scripts/run-with-timeout.py 600 -- flutter test",
    "/Users/u/fvm/default/bin/flutter test",
    "echo hi && flutter analyze 2>&1 | tail -20",
]

ALLOWED_IN_FVM_PROJECT = [
    "fvm flutter test",
    "fvm dart format lib",
    "python3 .claude/scripts/run-with-timeout.py 600 -- fvm flutter test",
    "grep -rn 'flutter test' lib",
    "rg flutter lib",
    "cat <<'EOF'\nflutter test\nEOF",
    "# flutter test\nls",
    ".fvm/flutter_sdk/bin/flutter test",
    "echo 'flutter analyze'",
]


@pytest.mark.parametrize("command", BLOCKED)
def test_bare_flutter_dart_blocked_in_fvm_project(command, fvm_project):
    found = hook.find_violations(command, str(fvm_project))
    assert found, command


@pytest.mark.parametrize("command", ALLOWED_IN_FVM_PROJECT)
def test_allowed_forms_in_fvm_project(command, fvm_project):
    assert hook.find_violations(command, str(fvm_project)) == []


@pytest.mark.parametrize("command", BLOCKED)
def test_same_commands_allowed_without_fvm(command, plain_project):
    assert hook.find_violations(command, str(plain_project)) == []


def test_subdirectory_of_fvm_project_is_covered(fvm_project):
    assert hook.find_violations("flutter test", str(fvm_project / "app"))


def test_cd_into_fvm_project_updates_base(fvm_project, plain_project):
    assert hook.find_violations(f"cd {fvm_project} && flutter test", str(plain_project))
    assert hook.find_violations(f"cd {plain_project} && flutter test", str(fvm_project)) == []


def test_cd_with_variable_skips_following_statements(fvm_project):
    assert hook.find_violations("cd $DIR && flutter test", str(fvm_project)) == []


def test_unparseable_command_returns_none(fvm_project):
    assert hook.find_violations("flutter test 'unterminated", str(fvm_project)) is None


def test_deny_reason_contains_fvm_rewrite(fvm_project):
    found = hook.find_violations("python3 .claude/scripts/run-with-timeout.py 600 -- flutter test", str(fvm_project))
    reason = hook.build_deny_reason(found)
    assert "  fvm flutter test" in reason
    assert "包裝保留" in reason


def _run_main(monkeypatch, capsys, payload):
    import io
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    assert hook.main() == 0
    return capsys.readouterr()


def test_main_emits_deny(monkeypatch, capsys, fvm_project):
    out = _run_main(monkeypatch, capsys, {
        "tool_name": "Bash", "tool_input": {"command": "flutter analyze"}, "cwd": str(fvm_project)})
    assert '"permissionDecision": "deny"' in out.out


def test_main_silent_for_fvm_prefixed(monkeypatch, capsys, fvm_project):
    out = _run_main(monkeypatch, capsys, {
        "tool_name": "Bash", "tool_input": {"command": "fvm flutter analyze"}, "cwd": str(fvm_project)})
    assert out.out.strip() == ""


def test_main_fail_open_on_exception(monkeypatch, capsys, fvm_project):
    def boom(command, start_dir):
        raise RuntimeError("boom")

    monkeypatch.setattr(hook, "find_violations", boom)
    out = _run_main(monkeypatch, capsys, {
        "tool_name": "Bash", "tool_input": {"command": "flutter analyze"}, "cwd": str(fvm_project)})
    assert out.out.strip() == ""
    assert "fail-open" in out.err
