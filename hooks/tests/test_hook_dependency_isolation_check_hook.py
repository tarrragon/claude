"""Tests for hook-dependency-isolation-check-hook.py（0.2.1-W3-665.5）

背景：`.claude/hooks/*.py` / `.claude/skills/<skill>/hooks/*.py` 可用
`uv run --script` + PEP 723 inline metadata 建立依賴隔離，也可用純
`python3` shebang 依賴 ambient 環境。兩者各自可能出現「宣告與現實不一致」
——本 hook 掃描 settings.json 登記的所有 hook 檔案，區分三態：

1. 危險宣告：shebang 非 uv 但 PEP 723 dependencies 宣告非空（宣告不生效）
2. 隱性依賴：無 uv 隔離且實際 import 非 stdlib 套件（依賴 ambient 環境）
3. 一致：無 uv 隔離但也無外部 import（純 stdlib，完全無風險）—— 此態
   刻意與狀態 2 分開判定，不可誤報

另涵蓋 uv shebang 但宣告依賴未涵蓋實際 import 的「宣告不完整」情況。

測試覆蓋：
| 測試 | 場景 | 驗證 |
|------|------|------|
| test_state_consistent_no_pep723_stdlib_only | 無 uv、無 PEP723、純 stdlib | 無問題（狀態 3，不誤報） |
| test_state_declared_but_unused | 無 uv、PEP723 宣告非空 | declared_but_unused |
| test_state_ambient_reliant_real_import | 無 uv、無 PEP723、實際 import 外部套件 | undeclared_or_uncovered_import |
| test_state_uv_consistent_covered | uv + PEP723 涵蓋實際 import | 無問題 |
| test_state_uv_incomplete_coverage | uv + PEP723 未涵蓋實際 import | undeclared_or_uncovered_import |
| test_local_module_not_flagged_as_external | import 本地模組（索引命中） | 不誤報為外部依賴 |
| test_nested_import_inside_try_except_detected | try/except 內的 import | 仍被偵測（不因巢狀漏判） |
| test_sessionstart_trigger_scans | SessionStart 事件 | 觸發全量掃描 |
| test_posttooluse_settings_json_edit_triggers | 編輯 settings.json | 觸發掃描 |
| test_posttooluse_hook_py_edit_triggers | 編輯 .claude/hooks/*.py | 觸發掃描 |
| test_posttooluse_unrelated_file_skipped | 編輯不相關檔案 | 不觸發 |
| test_missing_stdin_input_allowed | stdin 無 JSON | exit 0 |
| test_never_blocks_even_with_issues | 有問題時仍 exit 0（warning-only） | rc == 0 |

策略：
- importlib 動態載入（檔名含 hyphen）
- 以真實 tmp_path 建立最小 `.claude/settings.json` + hook 檔案，驗證
  `scan_all` / `check_file_consistency` 端到端行為
- monkeypatch `get_project_root` 指向 tmp_path，隔離對本專案真實
  settings.json 的依賴
- monkeypatch sys.stdin 餵入 stdin JSON，呼叫 main() 驗證分流邏輯
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest


HOOK_PATH = Path(__file__).parent.parent / "hook-dependency-isolation-check-hook.py"


def _load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "hook_dependency_isolation_check_hook", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def hook_mod():
    return _load_hook_module()


def _stdin_json(payload: dict) -> io.StringIO:
    return io.StringIO(json.dumps(payload))


def _make_project(tmp_path: Path, hook_rel_path: str, hook_content: str) -> Path:
    """建立最小專案骨架：.claude/settings.json 登記一個 hook 檔案。"""
    hook_file = tmp_path / hook_rel_path
    hook_file.parent.mkdir(parents=True, exist_ok=True)
    hook_file.write_text(hook_content, encoding="utf-8")

    settings_path = tmp_path / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "PostToolUse": [
                        {
                            "matcher": "Edit",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": f"$CLAUDE_PROJECT_DIR/{hook_rel_path}",
                                }
                            ],
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


# ---------------------------------------------------------------------------
# 三態分類（核心邏輯）
# ---------------------------------------------------------------------------


class TestThreeStateClassification:
    def test_state_consistent_no_pep723_stdlib_only(self, hook_mod, tmp_path):
        content = "#!/usr/bin/env python3\nimport os\nimport json\n"
        project_root = _make_project(tmp_path, ".claude/hooks/foo-hook.py", content)

        stdlib = hook_mod._get_stdlib_module_names()
        local = hook_mod.build_local_module_index(project_root / ".claude")
        issues = hook_mod.check_file_consistency(
            ".claude/hooks/foo-hook.py", project_root, stdlib, local
        )

        assert issues == []

    def test_state_declared_but_unused(self, hook_mod, tmp_path):
        content = (
            "#!/usr/bin/env python3\n"
            "# /// script\n"
            "# dependencies = [\"pyyaml\"]\n"
            "# ///\n"
            "import os\n"
        )
        project_root = _make_project(tmp_path, ".claude/hooks/foo-hook.py", content)

        stdlib = hook_mod._get_stdlib_module_names()
        local = hook_mod.build_local_module_index(project_root / ".claude")
        issues = hook_mod.check_file_consistency(
            ".claude/hooks/foo-hook.py", project_root, stdlib, local
        )

        kinds = [i.kind for i in issues]
        assert "declared_but_unused" in kinds

    def test_state_ambient_reliant_real_import(self, hook_mod, tmp_path):
        content = "#!/usr/bin/env python3\nimport yaml\n"
        project_root = _make_project(tmp_path, ".claude/hooks/foo-hook.py", content)

        stdlib = hook_mod._get_stdlib_module_names()
        local = hook_mod.build_local_module_index(project_root / ".claude")
        issues = hook_mod.check_file_consistency(
            ".claude/hooks/foo-hook.py", project_root, stdlib, local
        )

        kinds = [i.kind for i in issues]
        assert "undeclared_or_uncovered_import" in kinds
        assert "declared_but_unused" not in kinds

    def test_state_uv_consistent_covered(self, hook_mod, tmp_path):
        content = (
            "#!/usr/bin/env -S uv run --quiet --script\n"
            "# /// script\n"
            "# dependencies = [\"pyyaml\"]\n"
            "# ///\n"
            "import yaml\n"
        )
        project_root = _make_project(tmp_path, ".claude/hooks/foo-hook.py", content)

        stdlib = hook_mod._get_stdlib_module_names()
        local = hook_mod.build_local_module_index(project_root / ".claude")
        issues = hook_mod.check_file_consistency(
            ".claude/hooks/foo-hook.py", project_root, stdlib, local
        )

        assert issues == []

    def test_state_uv_incomplete_coverage(self, hook_mod, tmp_path):
        content = (
            "#!/usr/bin/env -S uv run --quiet --script\n"
            "# /// script\n"
            "# dependencies = [\"pyyaml\"]\n"
            "# ///\n"
            "import yaml\n"
            "import requests\n"
        )
        project_root = _make_project(tmp_path, ".claude/hooks/foo-hook.py", content)

        stdlib = hook_mod._get_stdlib_module_names()
        local = hook_mod.build_local_module_index(project_root / ".claude")
        issues = hook_mod.check_file_consistency(
            ".claude/hooks/foo-hook.py", project_root, stdlib, local
        )

        assert len(issues) == 1
        assert issues[0].kind == "undeclared_or_uncovered_import"
        assert "requests" in issues[0].detail

    def test_local_module_not_flagged_as_external(self, hook_mod, tmp_path):
        # lib 套件實際存在於 .claude/lib/__init__.py（本地掛載，非 PyPI）
        (tmp_path / ".claude" / "lib").mkdir(parents=True, exist_ok=True)
        (tmp_path / ".claude" / "lib" / "__init__.py").write_text("", encoding="utf-8")

        content = "#!/usr/bin/env python3\nfrom lib import setup_hook_logging\n"
        project_root = _make_project(tmp_path, ".claude/hooks/foo-hook.py", content)

        stdlib = hook_mod._get_stdlib_module_names()
        local = hook_mod.build_local_module_index(project_root / ".claude")
        issues = hook_mod.check_file_consistency(
            ".claude/hooks/foo-hook.py", project_root, stdlib, local
        )

        assert issues == []

    def test_nested_import_inside_try_except_detected(self, hook_mod, tmp_path):
        content = (
            "#!/usr/bin/env python3\n"
            "try:\n"
            "    import yaml\n"
            "except ImportError:\n"
            "    yaml = None\n"
        )
        project_root = _make_project(tmp_path, ".claude/hooks/foo-hook.py", content)

        stdlib = hook_mod._get_stdlib_module_names()
        local = hook_mod.build_local_module_index(project_root / ".claude")
        issues = hook_mod.check_file_consistency(
            ".claude/hooks/foo-hook.py", project_root, stdlib, local
        )

        kinds = [i.kind for i in issues]
        assert "undeclared_or_uncovered_import" in kinds


# ---------------------------------------------------------------------------
# 觸發時機（SessionStart + PostToolUse）
# ---------------------------------------------------------------------------


class TestTriggerRouting:
    def test_sessionstart_trigger_scans(self, hook_mod, monkeypatch, tmp_path, capsys):
        content = "#!/usr/bin/env python3\nimport yaml\n"
        project_root = _make_project(tmp_path, ".claude/hooks/foo-hook.py", content)

        monkeypatch.setattr(hook_mod, "get_project_root", lambda: project_root)
        monkeypatch.setattr(
            sys, "stdin", _stdin_json({"hook_event_name": "SessionStart"})
        )
        rc = hook_mod.main()
        err = capsys.readouterr().err

        assert rc == 0
        assert "WARNING" in err
        assert "foo-hook.py" in err

    def test_posttooluse_settings_json_edit_triggers(
        self, hook_mod, monkeypatch, tmp_path, capsys
    ):
        content = "#!/usr/bin/env python3\nimport yaml\n"
        project_root = _make_project(tmp_path, ".claude/hooks/foo-hook.py", content)

        monkeypatch.setattr(hook_mod, "get_project_root", lambda: project_root)
        payload = {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(project_root / ".claude" / "settings.json")},
        }
        monkeypatch.setattr(sys, "stdin", _stdin_json(payload))
        rc = hook_mod.main()
        err = capsys.readouterr().err

        assert rc == 0
        assert "WARNING" in err

    def test_posttooluse_hook_py_edit_triggers(
        self, hook_mod, monkeypatch, tmp_path, capsys
    ):
        content = "#!/usr/bin/env python3\nimport yaml\n"
        project_root = _make_project(tmp_path, ".claude/hooks/foo-hook.py", content)

        monkeypatch.setattr(hook_mod, "get_project_root", lambda: project_root)
        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(project_root / ".claude" / "hooks" / "foo-hook.py")
            },
        }
        monkeypatch.setattr(sys, "stdin", _stdin_json(payload))
        rc = hook_mod.main()
        err = capsys.readouterr().err

        assert rc == 0
        assert "WARNING" in err

    def test_posttooluse_unrelated_file_skipped(
        self, hook_mod, monkeypatch, tmp_path, capsys
    ):
        content = "#!/usr/bin/env python3\nimport yaml\n"
        project_root = _make_project(tmp_path, ".claude/hooks/foo-hook.py", content)

        monkeypatch.setattr(hook_mod, "get_project_root", lambda: project_root)
        payload = {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(project_root / "docs" / "readme.md")},
        }
        monkeypatch.setattr(sys, "stdin", _stdin_json(payload))
        rc = hook_mod.main()
        err = capsys.readouterr().err

        assert rc == 0
        assert err == ""

    def test_missing_stdin_input_allowed(self, hook_mod, monkeypatch):
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
        rc = hook_mod.main()
        assert rc == 0

    def test_never_blocks_even_with_issues(self, hook_mod, monkeypatch, tmp_path):
        content = "#!/usr/bin/env python3\nimport yaml\n"
        project_root = _make_project(tmp_path, ".claude/hooks/foo-hook.py", content)

        monkeypatch.setattr(hook_mod, "get_project_root", lambda: project_root)
        monkeypatch.setattr(
            sys, "stdin", _stdin_json({"hook_event_name": "SessionStart"})
        )
        rc = hook_mod.main()

        assert rc == 0


# ---------------------------------------------------------------------------
# PostToolUse 觸發範圍判定（單元）
# ---------------------------------------------------------------------------


class TestIsRelevantEditTarget:
    def test_settings_json_matches(self, hook_mod):
        assert hook_mod.is_relevant_edit_target("/proj/.claude/settings.json")

    def test_hook_py_under_hooks_matches(self, hook_mod):
        assert hook_mod.is_relevant_edit_target("/proj/.claude/hooks/foo-hook.py")

    def test_hook_py_under_skill_hooks_matches(self, hook_mod):
        assert hook_mod.is_relevant_edit_target(
            "/proj/.claude/skills/ticket/hooks/foo-hook.py"
        )

    def test_unrelated_md_does_not_match(self, hook_mod):
        assert not hook_mod.is_relevant_edit_target("/proj/docs/readme.md")

    def test_empty_path_does_not_match(self, hook_mod):
        assert not hook_mod.is_relevant_edit_target("")
