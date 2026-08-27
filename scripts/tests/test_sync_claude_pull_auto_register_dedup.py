"""Tests for sync-claude-pull.py 的 auto_register_hooks 去重 key 修復。

背景（0.2.1-W3-1141）：
  auto_register_hooks 收尾自動登記時，原本以「完整 command 字串」判斷腳本
  是否已註冊。但同一腳本在 settings.json 可能同時以裸路徑與
  `uv run --quiet` 前綴兩種呼叫形式存在，字串不同故被判為未登記而補登一次
  ——實測本專案 pull 前 193 登記 0 重複組，pull 後 303 登記 105 重複組。

  去重 key 必須改為「剝除呼叫前綴與 $CLAUDE_PROJECT_DIR 變數後的腳本路徑」
  （腳本身分），而非完整 command 字串。

涵蓋 acceptance：
  - 同一腳本的裸路徑與帶 `uv run --quiet` 前綴形式判為同一項，不重複登記
  - 同名不同路徑的 skill hook（basename 相同、skill_name 不同）不被誤判為
    重複，缺失的一支仍會被正確補登
  - 既有登記項的呼叫形式不被改寫（本次修復不重寫既有 command 字串）
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location(
    "sync_claude_pull_auto_register_dedup", _SCRIPT
)
assert _spec and _spec.loader
pull = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_auto_register_dedup"] = pull
_spec.loader.exec_module(pull)  # type: ignore[union-attr]


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _registered_commands(settings_data: dict, event: str) -> list[str]:
    cmds: list[str] = []
    for entry in settings_data.get("hooks", {}).get(event, []):
        for hook in entry.get("hooks", []):
            cmds.append(hook.get("command", ""))
    return cmds


# ---------------------------------------------------------------------------
# 單元測試：_collect_registered_hook_script_paths 的正規化行為
# ---------------------------------------------------------------------------


def test_normalizes_prefixed_and_bare_command_to_same_script_path():
    settings_data = {
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "",
                    "hooks": [
                        {
                            "type": "command",
                            "command": (
                                "uv run --quiet "
                                "$CLAUDE_PROJECT_DIR/.claude/hooks/foo.py"
                            ),
                        }
                    ],
                }
            ]
        }
    }
    paths = pull._collect_registered_hook_script_paths(settings_data)
    assert paths == {"hooks/foo.py"}


def test_bare_and_prefixed_forms_collapse_to_one_key():
    bare = {
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/foo.py",
                        }
                    ],
                }
            ]
        }
    }
    prefixed = {
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "",
                    "hooks": [
                        {
                            "type": "command",
                            "command": (
                                "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/foo.py"
                            ),
                        }
                    ],
                }
            ]
        }
    }
    assert pull._collect_registered_hook_script_paths(
        bare
    ) == pull._collect_registered_hook_script_paths(prefixed)


def test_skill_hooks_same_basename_different_skill_not_collapsed():
    settings_data = {
        "hooks": {
            "Stop": [
                {
                    "matcher": "",
                    "hooks": [
                        {
                            "type": "command",
                            "command": (
                                "$CLAUDE_PROJECT_DIR/.claude/skills/alpha/hooks/x.py"
                            ),
                        },
                        {
                            "type": "command",
                            "command": (
                                "uv run --quiet "
                                "$CLAUDE_PROJECT_DIR/.claude/skills/beta/hooks/x.py"
                            ),
                        },
                    ],
                }
            ]
        }
    }
    paths = pull._collect_registered_hook_script_paths(settings_data)
    assert paths == {"skills/alpha/hooks/x.py", "skills/beta/hooks/x.py"}


# ---------------------------------------------------------------------------
# 整合測試：auto_register_hooks 端對端行為
# ---------------------------------------------------------------------------


def _base_settings() -> dict:
    return {"permissions": {"allow": []}, "hooks": {}}


def test_same_script_two_call_forms_not_duplicated(tmp_path):
    claude_dir = tmp_path / ".claude"
    _write_text(claude_dir / "hooks" / "foo.py", "# dummy hook\n")
    _write_text(
        claude_dir / "config" / "hook-registry.yaml",
        (
            "hooks:\n"
            "  foo.py:\n"
            "    event: SessionStart\n"
            "    matcher: ''\n"
        ),
    )
    settings = _base_settings()
    settings["hooks"]["SessionStart"] = [
        {
            "matcher": "",
            "hooks": [
                {
                    "type": "command",
                    "command": (
                        "uv run --quiet $CLAUDE_PROJECT_DIR/.claude/hooks/foo.py"
                    ),
                }
            ],
        }
    ]
    _write_json(claude_dir / "settings.json", settings)

    added = pull.auto_register_hooks(tmp_path)

    assert added == 0
    final = json.loads((claude_dir / "settings.json").read_text(encoding="utf-8"))
    cmds = _registered_commands(final, "SessionStart")
    assert len(cmds) == 1
    # 既有登記項的呼叫形式不被改寫
    assert cmds[0] == "uv run --quiet $CLAUDE_PROJECT_DIR/.claude/hooks/foo.py"


def test_skill_hooks_same_filename_different_path_not_falsely_deduped(tmp_path):
    claude_dir = tmp_path / ".claude"
    _write_text(claude_dir / "skills" / "alpha" / "hooks" / "x.py", "# alpha\n")
    _write_text(claude_dir / "skills" / "beta" / "hooks" / "x.py", "# beta\n")
    _write_text(
        claude_dir / "config" / "hook-registry.yaml",
        (
            "skill_hooks:\n"
            "  alpha/x.py:\n"
            "    event: Stop\n"
            "    matcher: ''\n"
            "  beta/x.py:\n"
            "    event: Stop\n"
            "    matcher: ''\n"
        ),
    )
    settings = _base_settings()
    settings["hooks"]["Stop"] = [
        {
            "matcher": "",
            "hooks": [
                {
                    "type": "command",
                    "command": (
                        "$CLAUDE_PROJECT_DIR/.claude/skills/alpha/hooks/x.py"
                    ),
                }
            ],
        }
    ]
    _write_json(claude_dir / "settings.json", settings)

    added = pull.auto_register_hooks(tmp_path)

    # beta/x.py 尚未登記，應被補登；alpha/x.py 已登記不應重複
    assert added == 1
    final = json.loads((claude_dir / "settings.json").read_text(encoding="utf-8"))
    cmds = _registered_commands(final, "Stop")
    assert len(cmds) == 2
    assert "$CLAUDE_PROJECT_DIR/.claude/skills/alpha/hooks/x.py" in cmds
    assert "$CLAUDE_PROJECT_DIR/.claude/skills/beta/hooks/x.py" in cmds


def test_all_hooks_already_registered_via_prefixed_form_yields_zero_added(tmp_path):
    """迴歸測試：模擬本次缺陷的實際觸發情境——registry 內多支腳本皆已以
    `uv run --quiet` 前綴形式登記，sync-pull 收尾不應再補登任何一支。"""
    claude_dir = tmp_path / ".claude"
    registry_lines = ["hooks:"]
    settings = _base_settings()
    settings["hooks"]["PreToolUse"] = [{"matcher": "Bash", "hooks": []}]
    for name in ("a-hook.py", "b-hook.py", "c-hook.py"):
        _write_text(claude_dir / "hooks" / name, "# dummy\n")
        registry_lines.append(f"  {name}:")
        registry_lines.append("    event: PreToolUse")
        registry_lines.append("    matcher: Bash")
        settings["hooks"]["PreToolUse"][0]["hooks"].append(
            {
                "type": "command",
                "command": f"uv run --quiet $CLAUDE_PROJECT_DIR/.claude/hooks/{name}",
            }
        )
    _write_text(
        claude_dir / "config" / "hook-registry.yaml", "\n".join(registry_lines) + "\n"
    )
    _write_json(claude_dir / "settings.json", settings)

    added = pull.auto_register_hooks(tmp_path)

    assert added == 0
    final = json.loads((claude_dir / "settings.json").read_text(encoding="utf-8"))
    cmds = _registered_commands(final, "PreToolUse")
    assert len(cmds) == 3
