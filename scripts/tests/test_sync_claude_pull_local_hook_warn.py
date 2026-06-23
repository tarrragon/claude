"""Tests for sync-claude-pull.py post-sync settings.local.json hook 告警（1.4.0-W2-013.6）。

背景（framework issue #11）：
  framework hook 一律註冊於 settings.json；settings.local.json 為 sync 排除檔
  （local-only），框架版本遷移 / relocate 無法觸及，殘留註冊 relocate 後成幽靈
  （ARCH-TUNL-001、PC-148 單一註冊來源原則）。本功能於 sync-pull 完成後告警，
  warn-only 不阻擋同步，補上 sync 端的偵測時機（對齊 SessionStart 偵測）。

涵蓋 acceptance：
  - sync-pull 後偵測 settings.local.json 含 hook 即明確告警（stderr）
  - 不阻擋 sync（warn-only，函式回 None 不 raise / 不 exit）
  - 無 hook / 無檔 / 解析失敗時靜默跳過
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location(
    "sync_claude_pull_local_hook_warn", _SCRIPT
)
assert _spec and _spec.loader
pull = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_local_hook_warn"] = pull
_spec.loader.exec_module(pull)  # type: ignore[union-attr]


def _write_local(project_root: Path, data: dict) -> Path:
    p = project_root / ".claude" / "settings.local.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def _hooks_block() -> dict:
    return {
        "Stop": [
            {
                "matcher": "",
                "hooks": [
                    {
                        "type": "command",
                        "command": "$CLAUDE_PROJECT_DIR/.claude/skills/x/hooks/y.py",
                    }
                ],
            }
        ]
    }


def test_warns_when_local_has_hooks(tmp_path, capsys):
    _write_local(tmp_path, {"permissions": {"allow": []}, "hooks": _hooks_block()})
    result = pull.verify_local_settings_no_hooks(tmp_path)
    assert result is None  # warn-only，不回傳 exit code
    err = capsys.readouterr().err
    assert "settings.local.json 含 hook" in err
    assert "Stop" in err


def test_no_warn_when_no_hooks_key(tmp_path, capsys):
    _write_local(tmp_path, {"permissions": {"allow": ["Edit"]}})
    pull.verify_local_settings_no_hooks(tmp_path)
    assert "含 hook" not in capsys.readouterr().err


def test_no_warn_when_hooks_empty(tmp_path, capsys):
    _write_local(tmp_path, {"hooks": {}})
    pull.verify_local_settings_no_hooks(tmp_path)
    assert "含 hook" not in capsys.readouterr().err


def test_no_warn_when_missing_file(tmp_path, capsys):
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    pull.verify_local_settings_no_hooks(tmp_path)
    assert "含 hook" not in capsys.readouterr().err


def test_no_warn_on_invalid_json(tmp_path, capsys):
    p = tmp_path / ".claude" / "settings.local.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{ not valid json ", encoding="utf-8")
    # 解析失敗應靜默跳過，不 raise
    pull.verify_local_settings_no_hooks(tmp_path)
    assert "含 hook" not in capsys.readouterr().err
