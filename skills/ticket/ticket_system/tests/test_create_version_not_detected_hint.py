"""3.2.0-W1-145：根票無法偵測版本時，hint 說明偵測規則，不要求設定 current_version。"""
import argparse
import io
from contextlib import redirect_stderr, redirect_stdout

import pytest

from ticket_system.commands import create as create_cmd


@pytest.fixture
def no_active_version_root(tmp_path_factory, monkeypatch):
    """todolist 無任何版本、work-logs 無版本目錄：偵測鏈三段皆落空。"""
    root = tmp_path_factory.mktemp("no-active-root")
    (root / "docs" / "work-logs").mkdir(parents=True, exist_ok=True)
    (root / "CLAUDE.md").write_text("# CLAUDE.md\n", encoding="utf-8")
    (root / "docs" / "todolist.yaml").write_text("versions: []\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
    return root


def _args():
    return argparse.Namespace(
        version=None, wave=1, seq=None, action="修正", target="版本偵測提示",
        title=None, type="ADJ", priority=None, who=None, what=None, when=None,
        where_layer=None, where_files=None, why="重現", how_type=None,
        how_strategy=None, parent=None, source_ticket=None, blocked_by=None,
        related_to=None, acceptance=None, decision_tree_entry=None,
        decision_tree_decision=None, decision_tree_rationale=None,
        quiet=False, verbose=False, json_output=False, force=False,
    )


def _run():
    out, err = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            code = create_cmd.execute(_args())
    except SystemExit as exc:
        code = exc.code
    return out.getvalue() + err.getvalue(), code


def test_hint_explains_detection_rule_without_current_version(no_active_version_root):
    output, code = _run()
    assert code == 1
    assert "errno: VERSION_NOT_DETECTED" in output
    assert "status: active" in output
    assert "--version" in output
    assert "current_version" not in output
