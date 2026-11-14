"""
測試 acceptance-gate-hook 的 error-pattern 衝突提醒只列前段並附總數。

背景：衝突清單曾整份塞入 additionalContext（單一 hook 檔可達數百筆），
淹沒同一則輸出中的其他警告。checker 已依相關度排序，gate 只顯示前
ERROR_PATTERN_CONFLICT_DISPLAY_LIMIT 筆並寫出總數。
"""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path


def _load_hook_module():
    hook_path = Path(__file__).resolve().parents[1] / "hooks" / "acceptance-gate-hook.py"
    spec = importlib.util.spec_from_file_location("acceptance_gate_hook_limit", hook_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _logger():
    log = logging.getLogger("test-conflict-display-limit")
    log.addHandler(logging.NullHandler())
    return log


def _output_text(module, conflicts, tmp_path) -> str:
    result = module.AcceptanceCheckResult(
        should_block=False,
        has_acceptance=True,
        message=None,
        has_new_error_patterns=False,
        new_error_pattern_files=[],
        error_pattern_conflicts=conflicts,
    )
    return str(module.generate_hook_output("0.0.0-W1-999", result, tmp_path, _logger()))


def test_long_conflict_list_is_truncated_with_total(tmp_path):
    module = _load_hook_module()
    limit = module.ERROR_PATTERN_CONFLICT_DISPLAY_LIMIT
    conflicts = [f".claude/error-patterns/x/PC-{i:03d}.md" for i in range(limit + 15)]

    text = _output_text(module, conflicts, tmp_path)

    assert f"與 {limit + 15} 個 error-pattern 相關" in text
    assert f"列出前 {limit} 個" in text
    assert conflicts[0] in text
    assert conflicts[limit - 1] in text
    assert conflicts[limit] not in text


def test_short_conflict_list_shown_in_full(tmp_path):
    module = _load_hook_module()
    conflicts = [".claude/error-patterns/x/PC-001.md", ".claude/error-patterns/x/PC-002.md"]

    text = _output_text(module, conflicts, tmp_path)

    assert "與 2 個 error-pattern 相關" in text
    assert "列出前 2 個" in text
    assert all(c in text for c in conflicts)
