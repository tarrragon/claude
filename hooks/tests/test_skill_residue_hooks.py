#!/usr/bin/env python3
"""skill 殘留雙層防護的 hook 測試。

涵蓋兩個 hook：SessionStart 的可見性層與 PreToolUse 的阻擋層。兩者共用
`skill_residue_detector` 的判準，測試各自釘住的是「接線與決策」而非偵測邏輯
本身——偵測邏輯的測試在 `.claude/scripts/test_skill_residue_detector.py`。

阻擋層特別驗放行路徑：一個永遠阻擋的 gate 會逼使用者一律加 --force，效果
等同沒有 gate。
"""

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

hook_dir = Path(__file__).parent.parent
sys.path.insert(0, str(hook_dir))
sys.path.insert(0, str(hook_dir.parent))
sys.path.insert(0, str(hook_dir.parent / "scripts"))


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, hook_dir / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_hook = _load("skill_residue_check_hook", "skill-residue-check-hook.py")
gate_hook = _load("skill_sync_push_residue_gate_hook", "skill-sync-push-residue-gate-hook.py")


@pytest.fixture
def fake_project(tmp_path, monkeypatch):
    """Build a project tree and point both hooks at it."""
    root = tmp_path / "proj"
    (root / "lib").mkdir(parents=True)
    (root / ".claude" / "skills" / "probe").mkdir(parents=True)

    monkeypatch.setattr(check_hook, "project_root", lambda: root)
    monkeypatch.setattr(gate_hook, "project_root", lambda: root)

    def _write(body: str) -> Path:
        (root / ".claude" / "skills" / "probe" / "SKILL.md").write_text(
            body, encoding="utf-8"
        )
        return root

    return _write


class TestCheckHookVisibility:
    def test_clean_project_reports_pass(self, fake_project, capsys, monkeypatch):
        fake_project("內容乾淨\n")
        monkeypatch.setattr(sys, "argv", ["hook"])
        assert check_hook.main() == 0
        assert "無 blocking 級殘留" in capsys.readouterr().out

    def test_residue_is_listed(self, fake_project, capsys, monkeypatch):
        fake_project("見 `lib/ghost.dart`\n")
        monkeypatch.setattr(sys, "argv", ["hook"])
        out = (check_hook.main(), capsys.readouterr().out)[1]
        assert "lib/ghost.dart" in out
        assert "MISSING_PATH" in out

    def test_never_blocks(self, fake_project, capsys, monkeypatch):
        """可見性層永不阻擋——阻擋屬 push gate 的職責。"""
        fake_project("見 `lib/ghost.dart`\n")
        monkeypatch.setattr(sys, "argv", ["hook"])
        assert check_hook.main() == 0
        capsys.readouterr()

    def test_all_flag_includes_advisory(self, fake_project, capsys, monkeypatch):
        fake_project("出自 9.9.9-W1-001\n")
        monkeypatch.setattr(sys, "argv", ["hook", "--all"])
        check_hook.main()
        assert "FOREIGN_TICKET_ID" in capsys.readouterr().out

    def test_advisory_alone_is_not_listed_by_default(self, fake_project, capsys, monkeypatch):
        fake_project("出自 9.9.9-W1-001\n")
        monkeypatch.setattr(sys, "argv", ["hook"])
        check_hook.main()
        out = capsys.readouterr().out
        assert "無 blocking 級殘留" in out
        assert "FOREIGN_TICKET_ID" not in out


class TestGateTargetParsing:
    @pytest.mark.parametrize(
        "command,expected",
        [
            ("skill-sync push my-skill", "my-skill"),
            ("uv run --project x skill-sync push my-skill", "my-skill"),
            ("skill-sync push my-skill --force", "my-skill"),
            ("skill-sync list", None),
            ("skill-sync pull my-skill", None),
            ("echo skill-sync", None),
        ],
    )
    def test_extract_target(self, command, expected):
        assert gate_hook.extract_target(command) == expected


class TestGateDecision:
    def _run(self, command: str, monkeypatch) -> int:
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
            "tool_input": {"command": command}
        })))
        return gate_hook.main()

    def test_blocks_when_residue_present(self, fake_project, monkeypatch, capsys):
        fake_project("見 `lib/ghost.dart`\n")
        assert self._run("skill-sync push probe", monkeypatch) == 2
        assert "lib/ghost.dart" in capsys.readouterr().err

    def test_passes_clean_skill(self, fake_project, monkeypatch):
        fake_project("內容乾淨\n")
        assert self._run("skill-sync push probe", monkeypatch) == 0

    def test_force_bypasses(self, fake_project, monkeypatch):
        fake_project("見 `lib/ghost.dart`\n")
        assert self._run("skill-sync push probe --force", monkeypatch) == 0

    def test_non_push_command_ignored(self, fake_project, monkeypatch):
        fake_project("見 `lib/ghost.dart`\n")
        assert self._run("skill-sync list", monkeypatch) == 0

    def test_unrelated_command_ignored(self, fake_project, monkeypatch):
        fake_project("見 `lib/ghost.dart`\n")
        assert self._run("git status", monkeypatch) == 0

    def test_unknown_skill_name_ignored(self, fake_project, monkeypatch):
        """目標目錄不存在時不擋——那是 skill-sync 自己該回報的錯誤。"""
        fake_project("見 `lib/ghost.dart`\n")
        assert self._run("skill-sync push no-such-skill", monkeypatch) == 0

    def test_advisory_alone_does_not_block(self, fake_project, monkeypatch):
        fake_project("出自 9.9.9-W1-001\n")
        assert self._run("skill-sync push probe", monkeypatch) == 0

    def test_malformed_stdin_passes_through(self, monkeypatch):
        """解析不了輸入就放行：gate 自身故障不該擋住使用者的工作。"""
        monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))
        assert gate_hook.main() == 0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
