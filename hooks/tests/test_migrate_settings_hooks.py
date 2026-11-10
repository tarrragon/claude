"""settings.json hook 註冊正規形式遷移/對帳工具單元測試

測試 .claude/skills/project-init/tools/migrate_settings_hooks.py 的公開 API。
不變式：每筆 command 必須等於 "uv run --quiet <path>" 或 "python3 <path>" 之一。
"""

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import pytest

TOOL_PATH = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "project-init"
    / "tools"
    / "migrate_settings_hooks.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("migrate_settings_hooks", TOOL_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["migrate_settings_hooks"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mod():
    return _load_module()


@pytest.fixture
def hook_scripts(tmp_path):
    """建立一支 PEP 723 hook 與一支純 python3 shebang hook。"""
    hooks_dir = tmp_path / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True)

    pep723 = hooks_dir / "pep723-hook.py"
    pep723.write_text(
        "#!/usr/bin/env python3\n"
        "# /// script\n"
        '# requires-python = ">=3.9"\n'
        "# ///\n"
        "print('pep723 hook')\n"
    )

    plain = hooks_dir / "plain-hook.py"
    plain.write_text("#!/usr/bin/env python3\nprint('plain hook')\n")

    return {"root": tmp_path, "pep723": pep723, "plain": plain}


def _settings_with_commands(commands_by_event):
    hooks = {}
    for event, cmd in commands_by_event.items():
        hooks[event] = [{"matcher": "*", "hooks": [{"type": "command", "command": cmd}]}]
    return {"hooks": hooks}


class TestClassify:
    def test_classifies_pep723_as_uv(self, mod, hook_scripts):
        assert mod.classify(hook_scripts["pep723"]) == "uv"

    def test_classifies_plain_shebang_as_python3(self, mod, hook_scripts):
        assert mod.classify(hook_scripts["plain"]) == "python3"

    def test_missing_file_raises(self, mod, tmp_path):
        with pytest.raises(SystemExit):
            mod.classify(tmp_path / "nonexistent.py")

    def test_bash_script_raises(self, mod, tmp_path):
        script = tmp_path / "x.sh"
        script.write_text("#!/bin/bash\necho hi\n")
        with pytest.raises(SystemExit):
            mod.classify(script)

    def test_unclassifiable_raises(self, mod, tmp_path):
        script = tmp_path / "unclassifiable.py"
        script.write_text("print('no shebang, no pep723')\n")
        with pytest.raises(SystemExit):
            mod.classify(script)


class TestRewriteCommand:
    """核心不變式：任何輸入形態都收斂到正規形式。"""

    def test_bare_path_pep723_becomes_uv_quiet(self, mod, hook_scripts, monkeypatch):
        monkeypatch.setattr(mod, "PROJECT_ROOT", hook_scripts["root"])
        cmd = f"$CLAUDE_PROJECT_DIR/.claude/hooks/pep723-hook.py"
        result = mod.rewrite_command(cmd)
        assert result == "uv run --quiet $CLAUDE_PROJECT_DIR/.claude/hooks/pep723-hook.py"

    def test_bare_path_plain_becomes_python3(self, mod, hook_scripts, monkeypatch):
        monkeypatch.setattr(mod, "PROJECT_ROOT", hook_scripts["root"])
        cmd = f"$CLAUDE_PROJECT_DIR/.claude/hooks/plain-hook.py"
        result = mod.rewrite_command(cmd)
        assert result == "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/plain-hook.py"

    def test_uv_run_without_quiet_gains_quiet(self, mod, hook_scripts, monkeypatch):
        """收斂案例：既有 uv run 形式但缺 --quiet，必須改寫加上 --quiet。"""
        monkeypatch.setattr(mod, "PROJECT_ROOT", hook_scripts["root"])
        cmd = f"uv run $CLAUDE_PROJECT_DIR/.claude/hooks/pep723-hook.py"
        result = mod.rewrite_command(cmd)
        assert result == "uv run --quiet $CLAUDE_PROJECT_DIR/.claude/hooks/pep723-hook.py"

    def test_already_canonical_uv_is_unchanged(self, mod, hook_scripts, monkeypatch):
        monkeypatch.setattr(mod, "PROJECT_ROOT", hook_scripts["root"])
        cmd = "uv run --quiet $CLAUDE_PROJECT_DIR/.claude/hooks/pep723-hook.py"
        assert mod.rewrite_command(cmd) == cmd

    def test_already_canonical_python3_is_unchanged(self, mod, hook_scripts, monkeypatch):
        monkeypatch.setattr(mod, "PROJECT_ROOT", hook_scripts["root"])
        cmd = "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/plain-hook.py"
        assert mod.rewrite_command(cmd) == cmd

    def test_preserves_trailing_args(self, mod, hook_scripts, monkeypatch):
        monkeypatch.setattr(mod, "PROJECT_ROOT", hook_scripts["root"])
        cmd = "uv run $CLAUDE_PROJECT_DIR/.claude/hooks/pep723-hook.py $CLAUDE_FILE_PATH"
        result = mod.rewrite_command(cmd)
        assert result == (
            "uv run --quiet $CLAUDE_PROJECT_DIR/.claude/hooks/pep723-hook.py $CLAUDE_FILE_PATH"
        )

    def test_no_placeholder_raises(self, mod):
        with pytest.raises(SystemExit):
            mod.rewrite_command("echo hi")


class TestWalkAndRewrite:
    def test_reports_diffs_for_non_canonical(self, mod, hook_scripts, monkeypatch):
        monkeypatch.setattr(mod, "PROJECT_ROOT", hook_scripts["root"])
        data = _settings_with_commands(
            {
                "PreToolUse": "uv run $CLAUDE_PROJECT_DIR/.claude/hooks/pep723-hook.py",
                "PostToolUse": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/plain-hook.py",
            }
        )
        stats, diffs = mod.walk_and_rewrite(data["hooks"])
        assert stats["unchanged"] == 1
        assert stats["uv"] == 1
        assert len(diffs) == 1
        assert diffs[0][0] == "PreToolUse"

    def test_all_canonical_produces_no_diffs(self, mod, hook_scripts, monkeypatch):
        monkeypatch.setattr(mod, "PROJECT_ROOT", hook_scripts["root"])
        data = _settings_with_commands(
            {
                "PreToolUse": "uv run --quiet $CLAUDE_PROJECT_DIR/.claude/hooks/pep723-hook.py",
            }
        )
        stats, diffs = mod.walk_and_rewrite(data["hooks"])
        assert diffs == []
        assert stats["unchanged"] == 1


class TestRunCheck:
    """對帳模式：非正規形式必須回報非 0，且不寫檔。"""

    def test_check_returns_zero_when_canonical(self, mod, hook_scripts, monkeypatch, tmp_path):
        monkeypatch.setattr(mod, "PROJECT_ROOT", hook_scripts["root"])
        settings_path = tmp_path / "settings.json"
        data = _settings_with_commands(
            {"PreToolUse": "uv run --quiet $CLAUDE_PROJECT_DIR/.claude/hooks/pep723-hook.py"}
        )
        settings_path.write_text(json.dumps(data))
        before = settings_path.read_text()

        exit_code = mod.run_check(settings_path)

        assert exit_code == 0
        assert settings_path.read_text() == before  # no write in check mode

    def test_check_returns_nonzero_when_missing_quiet(self, mod, hook_scripts, monkeypatch, tmp_path):
        monkeypatch.setattr(mod, "PROJECT_ROOT", hook_scripts["root"])
        settings_path = tmp_path / "settings.json"
        data = _settings_with_commands(
            {"PreToolUse": "uv run $CLAUDE_PROJECT_DIR/.claude/hooks/pep723-hook.py"}
        )
        settings_path.write_text(json.dumps(data))
        before = settings_path.read_text()

        exit_code = mod.run_check(settings_path)

        assert exit_code == 1
        assert settings_path.read_text() == before  # no write in check mode

    def test_check_returns_nonzero_for_bare_path(self, mod, hook_scripts, monkeypatch, tmp_path):
        monkeypatch.setattr(mod, "PROJECT_ROOT", hook_scripts["root"])
        settings_path = tmp_path / "settings.json"
        data = _settings_with_commands(
            {"PreToolUse": "$CLAUDE_PROJECT_DIR/.claude/hooks/pep723-hook.py"}
        )
        settings_path.write_text(json.dumps(data))

        exit_code = mod.run_check(settings_path)

        assert exit_code == 1


class TestRunMigrate:
    def test_migrate_rewrites_and_writes_file(self, mod, hook_scripts, monkeypatch, tmp_path):
        monkeypatch.setattr(mod, "PROJECT_ROOT", hook_scripts["root"])
        settings_path = tmp_path / "settings.json"
        data = _settings_with_commands(
            {"PreToolUse": "uv run $CLAUDE_PROJECT_DIR/.claude/hooks/pep723-hook.py"}
        )
        settings_path.write_text(json.dumps(data))

        exit_code = mod.run_migrate(settings_path)

        assert exit_code == 0
        written = json.loads(settings_path.read_text())
        cmd = written["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        assert cmd == "uv run --quiet $CLAUDE_PROJECT_DIR/.claude/hooks/pep723-hook.py"

    def test_migrate_is_idempotent(self, mod, hook_scripts, monkeypatch, tmp_path):
        monkeypatch.setattr(mod, "PROJECT_ROOT", hook_scripts["root"])
        settings_path = tmp_path / "settings.json"
        data = _settings_with_commands(
            {"PreToolUse": "uv run $CLAUDE_PROJECT_DIR/.claude/hooks/pep723-hook.py"}
        )
        settings_path.write_text(json.dumps(data))

        mod.run_migrate(settings_path)
        after_first = settings_path.read_text()
        mod.run_migrate(settings_path)
        after_second = settings_path.read_text()

        assert after_first == after_second
