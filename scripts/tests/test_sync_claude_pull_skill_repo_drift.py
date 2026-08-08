"""sync-claude-pull.py 的 skill 庫漂移檢查對稱化（0.2.1-W3-356）。

沿革：extract_skill_versions / format_skill_version_diff / report_skill_repo_drift
原只在 sync-claude-push.py 定義（前兩者在 pull 端另有逐字重複的第二份），
0.2.1-W3-351/353 只讓 push 收尾呼叫 report_skill_repo_drift，pull 端從未對稱
呼叫——但 pull 才是本地 skills 被遠端覆寫的時刻，漂移在 pull 之後產生的機率
高於 push 之後。本檔驗證：(1) 三者由 pull 端從 .claude/lib/skill_version_diff.py
匯入而非自行定義，(2) pull 模組持有與 push 端相同的 report_skill_repo_drift
物件（同一份定義，格式必然一致）。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_PULL_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_PUSH_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-push.py"


def _load(script: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, script)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_pull_source_holds_no_duplicate_definition():
    """pull 端原始碼不得再自行定義 extract_skill_versions 等函式（僅提升，不重寫）。"""
    source = _PULL_SCRIPT.read_text(encoding="utf-8")

    assert "def extract_skill_versions" not in source
    assert "def format_skill_version_diff" not in source
    assert "def report_skill_repo_drift" not in source


def test_push_source_holds_no_duplicate_definition():
    """push 端同理：本 ticket 前 push 持有定義，本 ticket 後應只 import。"""
    source = _PUSH_SCRIPT.read_text(encoding="utf-8")

    assert "def extract_skill_versions" not in source
    assert "def format_skill_version_diff" not in source
    assert "def report_skill_repo_drift" not in source


def test_pull_and_push_share_the_same_function_object():
    """兩端匯入同一顆函式物件——輸出格式不一致的可能性從架構上消除。"""
    pull = _load(_PULL_SCRIPT, "sync_claude_pull_skill_drift")
    push = _load(_PUSH_SCRIPT, "sync_claude_push_skill_drift")

    assert pull.report_skill_repo_drift is push.report_skill_repo_drift
    assert pull.extract_skill_versions is push.extract_skill_versions
    assert pull.format_skill_version_diff is push.format_skill_version_diff


def test_pull_calls_drift_report_in_update_claude_folder():
    """pull 收尾流程須呼叫 report_skill_repo_drift，恢復與 push 對稱的收尾區塊。"""
    source = _PULL_SCRIPT.read_text(encoding="utf-8")

    assert "drift_report = report_skill_repo_drift(claude_dir)" in source
    assert "print_color(drift_report" in source
