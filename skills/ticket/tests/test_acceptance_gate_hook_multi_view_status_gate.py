"""
測試 acceptance-gate-hook 步驟 2.6 對 multi_view_status 的分層處置（0.2.1-W3-785）。

背景：0.2.1-W3-783 分析指出非法 multi_view_status 值可帶著非法值成功
complete（0.2.1-W3-769 實證）。0.2.1-W3-784 提供 `ticket track
fix-multi-view-status` CLI 作為合法修正途徑後，本票將非法值升級為阻擋。

存量掃描（本票 Solution 記錄）顯示 ANA 票缺標註（missing）佔比遠高於
非法值（invalid），故兩情況分別處置：
- 非法值（值不在 reviewed/skipped/n_a 之列）：阻擋，訊息含修正命令
- 未標註（缺欄位／缺子欄位）：維持警告，不阻擋（相容性考量）
- 合法值：正常放行，無警告
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _load_hook_module():
    hook_path = (
        Path(__file__).resolve().parents[1] / "hooks" / "acceptance-gate-hook.py"
    )
    spec = importlib.util.spec_from_file_location("acceptance_gate_hook", hook_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_ana_ticket(tmp_path: Path, solution_body: str) -> Path:
    ticket_dir = tmp_path / "docs" / "work-logs" / "v0.0.0" / "tickets"
    ticket_dir.mkdir(parents=True, exist_ok=True)
    ticket_file = ticket_dir / "0.0.0-W1-999.md"
    ticket_file.write_text(
        f"""---
id: 0.0.0-W1-999
title: dummy
type: ANA
status: in_progress
children: []
---

## Solution

{solution_body}

## Test Results

placeholder
""",
        encoding="utf-8",
    )
    return ticket_file


class TestIllegalValueBlocksComplete:
    """非法值（不在 reviewed/skipped/n_a）阻擋 complete，訊息含修正命令。"""

    def test_illegal_value_blocks_and_message_has_fix_command(self, tmp_path):
        module = _load_hook_module()
        ticket_file = _write_ana_ticket(
            tmp_path, "multi_view_status: single-view-completed"
        )

        result = module.check_acceptance_status(
            "0.0.0-W1-999", tmp_path, _FakeLogger()
        )

        assert result.should_block is True
        assert result.message is not None
        assert "fix-multi-view-status" in result.message
        assert "0.0.0-W1-999" in result.message
        assert "--value" in result.message
        assert "--reason" in result.message


class TestMissingValueStaysWarningOnly:
    """未標註（缺欄位）維持警告，不阻擋（相容性考量：存量票普遍缺標註）。"""

    def test_missing_field_does_not_block(self, tmp_path):
        module = _load_hook_module()
        ticket_file = _write_ana_ticket(tmp_path, "（尚無標註）")

        result = module.check_acceptance_status(
            "0.0.0-W1-999", tmp_path, _FakeLogger()
        )

        assert result.should_block is False
        assert result.message is not None
        assert "multi_view_status" in result.message


class TestLegalValuePassesWithoutWarning:
    """合法值（reviewed / skipped / n_a）正常放行，不產生 multi_view 警告。"""

    @pytest.mark.parametrize(
        "solution_body",
        [
            "multi_view_status: skipped\nreason: 單一視角已足夠評估此問題",
            "multi_view_status: n_a\nreason: 本票不涉及設計決策，判定不適用",
            "multi_view_status: reviewed\nreviewers: [thyme, basil]\nconclusion: 結論一致",
        ],
    )
    def test_legal_value_passes(self, tmp_path, solution_body):
        module = _load_hook_module()
        _write_ana_ticket(tmp_path, solution_body)

        result = module.check_acceptance_status(
            "0.0.0-W1-999", tmp_path, _FakeLogger()
        )

        assert result.should_block is False
        assert result.multi_view_warning is None


class _FakeLogger:
    """最小 logger 替身，滿足 checker 模組的 logger.info/debug/warning/error 呼叫。"""

    def info(self, *args, **kwargs):
        pass

    def debug(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass
