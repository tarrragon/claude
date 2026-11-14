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
    assert "settings.local.json 含不在專案 hook 清冊的 hook 註冊" in err
    assert "Stop" in err


def _write_manifest(project_root: Path, text: str) -> None:
    p = project_root / ".claude" / "project-integration" / "hook-registry.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_no_warn_when_all_local_hooks_from_manifest(tmp_path, capsys):
    """3.3.0-W1-036.3：清冊產生的條目合法，不示警。"""
    _write_manifest(tmp_path, (
        "version: 1\nhooks:\n  api.py:\n"
        "    script: .claude/project-integration/hooks/api.py\n    event: Stop\n"
    ))
    _write_local(tmp_path, {"hooks": {"Stop": [{"hooks": [{
        "type": "command",
        "command": "uv run --quiet $CLAUDE_PROJECT_DIR/.claude/project-integration/hooks/api.py",
    }]}]}})
    pull.verify_local_settings_no_hooks(tmp_path)
    assert "含不在專案 hook 清冊" not in capsys.readouterr().err


def test_warns_for_entry_outside_manifest_even_when_manifest_exists(tmp_path, capsys):
    """正向對照：清冊存在時，清冊外的條目仍示警。"""
    _write_manifest(tmp_path, (
        "version: 1\nhooks:\n  api.py:\n"
        "    script: .claude/project-integration/hooks/api.py\n    event: Stop\n"
    ))
    _write_local(tmp_path, {"hooks": _hooks_block()})
    pull.verify_local_settings_no_hooks(tmp_path)
    assert "含不在專案 hook 清冊的 hook 註冊（事件: Stop）" in capsys.readouterr().err


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


def test_advice_triages_instead_of_telling_consumer_to_edit_settings_json(
    tmp_path, capsys
):
    """W1-135：修復建議不得叫 consumer 移至 settings.json，須含分流說法。"""
    _write_local(tmp_path, {"hooks": _hooks_block()})
    pull.verify_local_settings_no_hooks(tmp_path)
    out = capsys.readouterr()
    text = out.out + out.err
    assert "移至 settings.json" not in text
    assert "framework issue" in text
    assert "--fix" in text
