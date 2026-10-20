"""
測試 acceptance-gate-hook 步驟 2.6 於同命令鏈偵測命中時，略過 multi_view_status
「未標註」警告（0.5.0-W1-357）。

背景：append-log 補上 multi_view_status 與 complete 同鏈時，Hook 讀檔早於
append-log 執行，讀到滯後內容而誤報「缺少標註」。本檔驗證：
- 同鏈命中：multi_view_warning 為 None、訊息不含該警告、清單第 6 項為 [--]
- 未串接：缺標註仍警告（E1 對照）
- 值非法：不論是否同鏈皆阻擋（E1 對照）
- 偵測失敗（未閉合引號、偵測函式拋例外）：落在照常輸出警告一側
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

TICKET_ID = "0.0.0-W1-997"
CHAINED = (
    'ticket track append-log 0.0.0-W1-997 --section "Solution" '
    '"multi_view_status: skipped" && ticket track complete 0.0.0-W1-997'
)
PLAIN = "ticket track complete 0.0.0-W1-997"


def _load_hook_module():
    hook_path = (
        Path(__file__).resolve().parents[1] / "hooks" / "acceptance-gate-hook.py"
    )
    spec = importlib.util.spec_from_file_location("acceptance_gate_hook", hook_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_ana_ticket(tmp_path: Path, solution_body: str) -> None:
    ticket_dir = tmp_path / "docs" / "work-logs" / "v0.0.0" / "tickets"
    ticket_dir.mkdir(parents=True, exist_ok=True)
    (ticket_dir / f"{TICKET_ID}.md").write_text(
        f"""---
id: {TICKET_ID}
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


class _FakeLogger:
    def info(self, *args, **kwargs):
        pass

    def debug(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


def _check(tmp_path, command):
    module = _load_hook_module()
    return module, module.check_acceptance_status(
        TICKET_ID, tmp_path, _FakeLogger(), command=command
    )


class TestChainedSuppressesMissingWarning:
    def test_chained_missing_annotation_has_no_warning(self, tmp_path):
        _write_ana_ticket(tmp_path, "（尚無標註）")
        _, result = _check(tmp_path, CHAINED)
        assert result.should_block is False
        assert result.multi_view_warning is None
        assert "multi_view_status" not in (result.message or "")

    def test_chained_checklist_item_6_is_skipped_marker(self, tmp_path):
        _write_ana_ticket(tmp_path, "（尚無標註）")
        module, result = _check(tmp_path, CHAINED)
        out = module.generate_hook_output(TICKET_ID, result, tmp_path, _FakeLogger())
        text = str(out)
        assert "[--] 6. multi_view_status" in text
        assert "6. multi_view_status 未標註" not in text


class TestUnchainedStillWarns:
    """E1 對照：未串接時缺標註仍警告。"""

    def test_unchained_missing_annotation_warns(self, tmp_path):
        _write_ana_ticket(tmp_path, "（尚無標註）")
        _, result = _check(tmp_path, PLAIN)
        assert result.should_block is False
        assert result.multi_view_warning is not None
        assert "multi_view_status" in result.message


class TestChainWithoutMultiViewWriteStillWarns:
    """0.5.0-W1-389 E2：同鏈有寫入但未寫 multi_view_status 時仍警告。"""

    def test_merge_then_complete_still_warns(self, tmp_path):
        _write_ana_ticket(tmp_path, "（尚無標註）")
        cmd = f"git merge feature && ticket track complete {TICKET_ID}"
        _, result = _check(tmp_path, cmd)
        assert result.multi_view_warning is not None

    def test_append_log_other_content_still_warns(self, tmp_path):
        _write_ana_ticket(tmp_path, "（尚無標註）")
        cmd = (
            f'ticket track append-log {TICKET_ID} --section "Solution" "other" '
            f"&& ticket track complete {TICKET_ID}"
        )
        _, result = _check(tmp_path, cmd)
        assert result.multi_view_warning is not None

    def test_append_log_writes_field_after_complete_still_warns(self, tmp_path):
        _write_ana_ticket(tmp_path, "（尚無標註）")
        cmd = (
            f"ticket track complete {TICKET_ID} && ticket track append-log "
            f'{TICKET_ID} --section "Solution" "multi_view_status: skipped"'
        )
        _, result = _check(tmp_path, cmd)
        assert result.multi_view_warning is not None


class TestIllegalValueStillBlocks:
    """E1 對照：值非法不論是否同鏈皆阻擋。"""

    def test_illegal_value_blocks_when_chained(self, tmp_path):
        _write_ana_ticket(tmp_path, "multi_view_status: single-view-completed")
        _, result = _check(tmp_path, CHAINED)
        assert result.should_block is True
        assert "fix-multi-view-status" in result.message

    def test_illegal_value_blocks_when_unchained(self, tmp_path):
        _write_ana_ticket(tmp_path, "multi_view_status: single-view-completed")
        _, result = _check(tmp_path, PLAIN)
        assert result.should_block is True


class TestDetectionFailureLandsOnWarnSide:
    """偵測本身失敗時落在『照常輸出警告』一側。"""

    def test_unclosed_quote_command_keeps_warning(self, tmp_path):
        _write_ana_ticket(tmp_path, "（尚無標註）")
        broken = 'ticket track append-log x "unclosed && ticket track complete ' + TICKET_ID
        _, result = _check(tmp_path, broken)
        assert result.multi_view_warning is not None

    def test_empty_command_keeps_warning(self, tmp_path):
        _write_ana_ticket(tmp_path, "（尚無標註）")
        _, result = _check(tmp_path, "")
        assert result.multi_view_warning is not None

    def test_detector_exception_keeps_warning(self, tmp_path, monkeypatch):
        _write_ana_ticket(tmp_path, "（尚無標註）")
        module = _load_hook_module()

        def _boom(command):
            raise RuntimeError("detector failure")

        monkeypatch.setattr(module, "detect_chained_pre_complete_write", _boom)
        result = module.check_acceptance_status(
            TICKET_ID, tmp_path, _FakeLogger(), command=CHAINED
        )
        assert result.multi_view_warning is not None
