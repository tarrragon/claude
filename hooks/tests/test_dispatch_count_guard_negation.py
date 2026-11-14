"""
Test: dispatch-count-guard 否定句不計入期望派發數，警告附命中原句

驗證：
1. 否定句（「不需要三人組」「不走多視角」「without parallel-evaluation」）不計入（修正前計入）
2. 正向對照（E2）：肯定句仍計入；逗號後的肯定句不受前一分句的否定影響；
   頓號列舉在同一否定下皆不計入
3. 同 prompt 有否定與肯定兩次出現時，肯定那次仍計入
4. 端到端：PostToolUse 只含否定句不建狀態檔；含肯定句建狀態檔，
   UserPromptSubmit 警告附命中原句

狀態檔以 monkeypatch 指到 tmp_path（function scope）；不觸及 /tmp 真實狀態檔。
"""

from __future__ import annotations

import importlib.util
import io
import json
import logging
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "dispatch_count_guard_negation", HOOKS_DIR / "dispatch-count-guard-hook.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def guard():
    return _load()


LOG = logging.getLogger("test-dispatch-count-guard-negation")


@pytest.mark.parametrize("text", [
    "這次不需要三人組，單人審查即可",
    "不走多視角",
    "無需 parallel-evaluation",
    "不需要三人組、多視角",
    "review this without parallel-evaluation",
])
def test_negated_keyword_not_counted(guard, text):
    assert guard.detect_dispatch_keywords(text, LOG) is None


@pytest.mark.parametrize("text,expected_count", [
    ("派發三人組審查本票", 3),
    ("不改規則，改走三人組", 3),
    ("執行 parallel-evaluation", 3),
    ("double-track 進行", 2),
])
def test_affirmative_keyword_counted(guard, text, expected_count):
    # E2 正向對照：肯定句仍計入
    result = guard.detect_dispatch_keywords(text, LOG)
    assert result is not None
    assert result[1] == expected_count


def test_mixed_negated_and_affirmative_counts_affirmative(guard):
    text = "上次不需要三人組。這次派三人組審查"
    keywords, expected, clauses = guard.detect_dispatch_keywords(text, LOG)
    assert keywords == ["三人組"]
    assert expected == 3
    assert clauses == ["這次派三人組審查"]


def _post(guard, monkeypatch, tmp_path, prompt):
    state = tmp_path / "batch.json"
    monkeypatch.setattr(guard, "get_batch_state_file", lambda data, logger=None: state)
    payload = {
        "hook_event_name": "PostToolUse",
        "session_id": "s1",
        "tool_name": "Agent",
        "tool_input": {"prompt": prompt, "description": "d"},
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    guard.main()
    return state


def test_post_tool_use_negated_prompt_creates_no_state(guard, monkeypatch, tmp_path, capsys):
    state = _post(guard, monkeypatch, tmp_path, "不需要三人組，直接派 thyme")
    assert not state.exists()


def test_submit_warning_includes_matched_clause(guard, monkeypatch, tmp_path, capsys):
    state = _post(guard, monkeypatch, tmp_path, "派發三人組審查 213.5")
    assert json.loads(state.read_text(encoding="utf-8"))["matched_clauses"] == ["派發三人組審查 213.5"]
    capsys.readouterr()
    payload = {"hook_event_name": "UserPromptSubmit", "session_id": "s1", "prompt": "next"}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    guard.main()
    err = capsys.readouterr().err
    assert "派發計數警告" in err
    assert "命中原句" in err
    assert "派發三人組審查 213.5" in err


def test_warning_truncates_long_clauses(guard):
    long_clause = "派三人組" + "x" * 300
    text = guard.build_count_mismatch_warning(3, 1, ["三人組"], [long_clause] * 5)
    assert text.count("  - ") == guard.MAX_MATCHED_CLAUSES
    assert "…" in text
