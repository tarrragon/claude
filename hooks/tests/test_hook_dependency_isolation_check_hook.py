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
| test_lib_submodule_import_transitive_dependency_flagged | `from lib.X import`，X 內部 import 第三方套件，無宣告 | undeclared_or_uncovered_import |
| test_lib_symbol_import_resolved_via_symbol_index | `from lib import foo`，foo 定義於需要第三方套件的 lib 子模組 | undeclared_or_uncovered_import |
| test_lib_transitive_dependency_covered_by_uv_declaration | uv + PEP723 宣告涵蓋 lib 間接依賴 | 無問題 |
| test_lib_internal_circular_import_resolved_without_hang | 兩個 lib 子模組互相 import | 遞迴終止，兩者依賴皆併入 |
| test_lib_submodule_without_third_party_import_not_flagged | `from lib.X import`，X 僅用 stdlib | 不誤報（避免過度擴大比對基準） |
| test_settings_uv_run_overrides_plain_shebang | settings.json 以 uv run 登記，shebang 卻是 python3 | uses_uv=True，不誤報（0.2.1-W3-1084） |
| test_settings_python3_prefix_overrides_uv_shebang | settings.json 以 python3 登記，shebang 卻是 uv run | uses_uv=False，隔離確定不生效 |
| test_settings_bare_path_falls_back_to_shebang | settings.json 裸路徑登記 | 回退讀檔案自身 shebang（既有行為） |
| test_resolve_uses_uv_unit_cases | `_resolve_uses_uv` 單元測試（5 種前綴組合） | 判準優先序正確 |
| test_extract_hook_command_prefixes_multiple_registrations | 同路徑被多個 event 重複登記 | 前綴集合正確聚合 |

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


def _make_project(
    tmp_path: Path,
    hook_rel_path: str,
    hook_content: str,
    command_prefix: str = "",
) -> Path:
    """建立最小專案骨架：.claude/settings.json 登記一個 hook 檔案。

    `command_prefix` 預設為空字串（裸路徑登記，無直譯器前綴），對應既有
    測試假設的「登記依賴檔案自身 shebang」情境。傳入 `"uv run --quiet"`
    或 `"python3"` 等值可構造「settings.json 登記方式優先於 shebang」的
    情境（見 `TestUsesUvSettingsPrecedence`）。
    """
    hook_file = tmp_path / hook_rel_path
    hook_file.parent.mkdir(parents=True, exist_ok=True)
    hook_file.write_text(hook_content, encoding="utf-8")

    command = f"{command_prefix} $CLAUDE_PROJECT_DIR/{hook_rel_path}" if command_prefix else f"$CLAUDE_PROJECT_DIR/{hook_rel_path}"

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
                                    "command": command,
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


def _add_lib_module(project_root: Path, module_name: str, content: str) -> None:
    """在既有專案骨架中追加一個 `.claude/lib/<module_name>.py` 子模組（含
    `.claude/lib/__init__.py`，使 `build_local_module_index` 能識別 `lib`
    本身為本地套件，維持與 `test_local_module_not_flagged_as_external`
    相同前提）。
    """
    lib_dir = project_root / ".claude" / "lib"
    lib_dir.mkdir(parents=True, exist_ok=True)
    init_file = lib_dir / "__init__.py"
    if not init_file.exists():
        init_file.write_text("", encoding="utf-8")
    (lib_dir / f"{module_name}.py").write_text(content, encoding="utf-8")


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
# lib 遞移依賴解析（0.2.1-W3-1077）
#
# 背景：check_file_consistency 原先將 `lib` 整體排除於外部依賴比對之外
# （理由：透過 sys.path.insert 動態掛載，非 PyPI 依賴）。該理由對 `lib`
# 這個套件名稱本身成立，但解析在此中止，未追進 lib 模組內部的第三方
# import——本專案 lib 模組中，config_loader / framework_paths /
# frontmatter_parser / hook_ticket / phase_contract_validator 需要
# pyyaml、pyproject_scanner 需要 tomli，hook 只要間接觸及任一者而未宣告
# 對應套件，即在 ambient 環境缺套件時於 import 階段崩潰卻不被本檢查回報
# （active-dispatch-tracker-hook.py 即為實例，存活 5 日零告警）。
#
# 以下測試使用 tmp_path 構造的 lib fixture 驗證鑑別力，不依賴生產檔案
# `.claude/lib/` 的當前狀態——生產狀態會隨其他 ticket 修復而改變。
# ---------------------------------------------------------------------------


class TestLibTransitiveDependencies:
    def test_lib_submodule_import_transitive_dependency_flagged(self, hook_mod, tmp_path):
        content = "#!/usr/bin/env python3\nfrom lib.some_module import foo\n"
        project_root = _make_project(tmp_path, ".claude/hooks/foo-hook.py", content)
        _add_lib_module(
            project_root, "some_module", "import yaml\n\n\ndef foo():\n    return yaml\n"
        )

        stdlib = hook_mod._get_stdlib_module_names()
        local = hook_mod.build_local_module_index(project_root / ".claude")
        issues = hook_mod.check_file_consistency(
            ".claude/hooks/foo-hook.py", project_root, stdlib, local
        )

        kinds = [i.kind for i in issues]
        assert "undeclared_or_uncovered_import" in kinds
        assert any("yaml" in i.detail for i in issues)

    def test_lib_symbol_import_resolved_via_symbol_index(self, hook_mod, tmp_path):
        content = "#!/usr/bin/env python3\nfrom lib import foo\n"
        project_root = _make_project(tmp_path, ".claude/hooks/foo-hook.py", content)
        _add_lib_module(
            project_root, "other_module", "import requests\n\n\ndef foo():\n    return requests\n"
        )

        stdlib = hook_mod._get_stdlib_module_names()
        local = hook_mod.build_local_module_index(project_root / ".claude")
        issues = hook_mod.check_file_consistency(
            ".claude/hooks/foo-hook.py", project_root, stdlib, local
        )

        kinds = [i.kind for i in issues]
        assert "undeclared_or_uncovered_import" in kinds
        assert any("requests" in i.detail for i in issues)

    def test_lib_transitive_dependency_covered_by_uv_declaration(self, hook_mod, tmp_path):
        content = (
            "#!/usr/bin/env -S uv run --quiet --script\n"
            "# /// script\n"
            "# dependencies = [\"pyyaml\"]\n"
            "# ///\n"
            "from lib.some_module import foo\n"
        )
        project_root = _make_project(tmp_path, ".claude/hooks/foo-hook.py", content)
        _add_lib_module(
            project_root, "some_module", "import yaml\n\n\ndef foo():\n    return yaml\n"
        )

        stdlib = hook_mod._get_stdlib_module_names()
        local = hook_mod.build_local_module_index(project_root / ".claude")
        issues = hook_mod.check_file_consistency(
            ".claude/hooks/foo-hook.py", project_root, stdlib, local
        )

        assert issues == []

    def test_lib_internal_circular_import_resolved_without_hang(self, hook_mod, tmp_path):
        content = "#!/usr/bin/env python3\nfrom lib.mod_a import x\n"
        project_root = _make_project(tmp_path, ".claude/hooks/foo-hook.py", content)
        _add_lib_module(project_root, "mod_a", "import yaml\nfrom .mod_b import y\n")
        _add_lib_module(project_root, "mod_b", "import requests\nfrom .mod_a import x\n")

        stdlib = hook_mod._get_stdlib_module_names()
        local = hook_mod.build_local_module_index(project_root / ".claude")
        issues = hook_mod.check_file_consistency(
            ".claude/hooks/foo-hook.py", project_root, stdlib, local
        )

        assert len(issues) == 1
        assert issues[0].kind == "undeclared_or_uncovered_import"
        assert "yaml" in issues[0].detail
        assert "requests" in issues[0].detail

    def test_lib_submodule_without_third_party_import_not_flagged(self, hook_mod, tmp_path):
        content = "#!/usr/bin/env python3\nfrom lib.plain_module import bar\n"
        project_root = _make_project(tmp_path, ".claude/hooks/foo-hook.py", content)
        _add_lib_module(project_root, "plain_module", "import os\n\n\ndef bar():\n    return os\n")

        stdlib = hook_mod._get_stdlib_module_names()
        local = hook_mod.build_local_module_index(project_root / ".claude")
        issues = hook_mod.check_file_consistency(
            ".claude/hooks/foo-hook.py", project_root, stdlib, local
        )

        assert issues == []


# ---------------------------------------------------------------------------
# uses_uv 判準：settings.json 登記方式優先於檔案自身 shebang（0.2.1-W3-1084）
#
# 背景：實際決定 PEP 723 隔離是否生效的是 settings.json 登記的呼叫方式，
# 非檔案自身 shebang——`uv run <path>` 直接呼叫時 uv 讀的是目標檔的 PEP
# 723 metadata，與 shebang 無關；`python3 <path>` 等明確直譯器呼叫時
# shebang 同樣完全不被讀取。舊版 uses_uv 僅讀 shebang，對 settings.json
# 以 `uv run <path>` 登記但 shebang 非 uv 的檔案（如
# active-dispatch-tracker-hook.py）產生誤報。
# ---------------------------------------------------------------------------


class TestUsesUvSettingsPrecedence:
    def test_settings_uv_run_overrides_plain_shebang(self, hook_mod, tmp_path):
        content = (
            "#!/usr/bin/env python3\n"
            "# /// script\n"
            "# dependencies = [\"pyyaml\"]\n"
            "# ///\n"
            "import yaml\n"
        )
        project_root = _make_project(
            tmp_path, ".claude/hooks/foo-hook.py", content, command_prefix="uv run --quiet"
        )

        stdlib = hook_mod._get_stdlib_module_names()
        local = hook_mod.build_local_module_index(project_root / ".claude")
        command_prefixes = hook_mod.extract_hook_command_prefixes(
            project_root / ".claude" / "settings.json"
        )
        issues = hook_mod.check_file_consistency(
            ".claude/hooks/foo-hook.py",
            project_root,
            stdlib,
            local,
            command_prefixes=command_prefixes.get(".claude/hooks/foo-hook.py"),
        )

        assert issues == []

    def test_settings_python3_prefix_overrides_uv_shebang(self, hook_mod, tmp_path):
        content = (
            "#!/usr/bin/env -S uv run --quiet --script\n"
            "# /// script\n"
            "# dependencies = [\"pyyaml\"]\n"
            "# ///\n"
            "import yaml\n"
        )
        project_root = _make_project(
            tmp_path, ".claude/hooks/foo-hook.py", content, command_prefix="python3"
        )

        stdlib = hook_mod._get_stdlib_module_names()
        local = hook_mod.build_local_module_index(project_root / ".claude")
        command_prefixes = hook_mod.extract_hook_command_prefixes(
            project_root / ".claude" / "settings.json"
        )
        issues = hook_mod.check_file_consistency(
            ".claude/hooks/foo-hook.py",
            project_root,
            stdlib,
            local,
            command_prefixes=command_prefixes.get(".claude/hooks/foo-hook.py"),
        )

        kinds = [i.kind for i in issues]
        assert "declared_but_unused" in kinds
        assert "undeclared_or_uncovered_import" in kinds

    def test_settings_bare_path_falls_back_to_shebang(self, hook_mod, tmp_path):
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
        command_prefixes = hook_mod.extract_hook_command_prefixes(
            project_root / ".claude" / "settings.json"
        )
        issues = hook_mod.check_file_consistency(
            ".claude/hooks/foo-hook.py",
            project_root,
            stdlib,
            local,
            command_prefixes=command_prefixes.get(".claude/hooks/foo-hook.py"),
        )

        assert issues == []

    def test_resolve_uses_uv_unit_cases(self, hook_mod):
        resolve = hook_mod._resolve_uses_uv
        assert resolve("#!/usr/bin/env python3", {"uv run --quiet"}) is True
        assert resolve("#!/usr/bin/env -S uv run --script", {"python3"}) is False
        assert resolve("#!/usr/bin/env -S uv run --script", {""}) is True
        assert resolve("#!/usr/bin/env python3", {""}) is False
        assert resolve("#!/usr/bin/env -S uv run --script", None) is True
        assert resolve("#!/usr/bin/env python3", set()) is False

    def test_extract_hook_command_prefixes_multiple_registrations(self, hook_mod, tmp_path):
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
                                        "command": "uv run --quiet $CLAUDE_PROJECT_DIR/.claude/hooks/dual-hook.py",
                                    }
                                ],
                            },
                            {
                                "matcher": "Write",
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "uv run --quiet $CLAUDE_PROJECT_DIR/.claude/hooks/dual-hook.py",
                                    }
                                ],
                            },
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )

        prefixes = hook_mod.extract_hook_command_prefixes(settings_path)

        assert prefixes[".claude/hooks/dual-hook.py"] == {"uv run --quiet"}


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
