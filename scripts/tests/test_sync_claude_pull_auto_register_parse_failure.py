"""auto_register_hooks 讀 settings.json / hook-registry.yaml 失敗時須寫 stderr（3.4.0-W1-024）。"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location("sync_claude_pull_ar_parse_failure", _SCRIPT)
assert _spec and _spec.loader
pull = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_ar_parse_failure"] = pull
_spec.loader.exec_module(pull)  # type: ignore[union-attr]

if pull.yaml is None:
    pytest.skip("pyyaml 未安裝", allow_module_level=True)

SKIP_LITERAL = "auto_register 已略過"
VALID_REGISTRY = "hooks: {}\n"


def _setup(root: Path, registry: str, settings: str) -> None:
    (root / ".claude" / "config").mkdir(parents=True)
    (root / ".claude" / "config" / "hook-registry.yaml").write_text(registry, encoding="utf-8")
    (root / ".claude" / "settings.json").write_text(settings, encoding="utf-8")


def test_settings_conflict_marker_warns(tmp_path, capsys):
    bad = '{\n<<<<<<< HEAD\n"a": 1\n=======\n"a": 2\n>>>>>>> up\n}\n'
    _setup(tmp_path, VALID_REGISTRY, bad)
    assert pull.auto_register_hooks(tmp_path) == 0
    err = capsys.readouterr().err
    assert "settings.json" in err and SKIP_LITERAL in err


def test_registry_malformed_warns(tmp_path, capsys):
    _setup(tmp_path, "hooks: [unclosed\n  - : :\n", json.dumps({}))
    assert pull.auto_register_hooks(tmp_path) == 0
    err = capsys.readouterr().err
    assert "hook-registry.yaml" in err and SKIP_LITERAL in err


def test_both_valid_no_warning(tmp_path, capsys):
    _setup(tmp_path, VALID_REGISTRY, json.dumps({}))
    pull.auto_register_hooks(tmp_path)
    assert SKIP_LITERAL not in capsys.readouterr().err
