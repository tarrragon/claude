"""
測試 acceptance-gate-hook 步驟 8（Layer 1 自檢可觀測性 warning）於
chained_write_detected 時的抑制行為（0.2.1-W3-1181）。

背景：步驟 6（execution log 檢查）已對「complete 與 append-log/
set-acceptance 同鏈串接」的滯後讀檔問題做抑制（0.4.1-W2-006），步驟 8
（self_check_warning）原本未套用相同抑制，導致 append-log 剛新增
`### 自檢結果` 子章節後同鏈串接 complete 時，步驟 8 讀到的仍是滯後
（新增前）內容而誤發 warning。本測試驗證：
- 非串接情境：IMP ticket 缺 `### 自檢結果` 子章節 → warning 正常觸發
- 串接情境（chained_write_detected=True）→ warning 歸零（None）
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_hook_module():
    hook_path = (
        Path(__file__).resolve().parents[1] / "hooks" / "acceptance-gate-hook.py"
    )
    spec = importlib.util.spec_from_file_location("acceptance_gate_hook", hook_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_imp_ticket_without_self_check(tmp_path: Path) -> Path:
    ticket_dir = tmp_path / "docs" / "work-logs" / "v0.0.0" / "tickets"
    ticket_dir.mkdir(parents=True, exist_ok=True)
    ticket_file = ticket_dir / "0.0.0-W1-998.md"
    ticket_file.write_text(
        """---
id: 0.0.0-W1-998
title: dummy
type: IMP
status: in_progress
children: []
---

## Solution

### 修復摘要
做了 X。

## Test Results
通過。
""",
        encoding="utf-8",
    )
    return ticket_file


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


class TestNonChainedWriteStillWarns:
    """非串接情境：IMP 缺 ### 自檢結果 子章節，warning 正常觸發（既有行為不變）。"""

    def test_missing_self_check_without_chained_write_warns(self, tmp_path):
        module = _load_hook_module()
        _write_imp_ticket_without_self_check(tmp_path)

        result = module.check_acceptance_status(
            "0.0.0-W1-998",
            tmp_path,
            _FakeLogger(),
            command="ticket track complete 0.0.0-W1-998",
        )

        assert result.self_check_warning is not None
        assert "自檢結果" in result.self_check_warning


class TestChainedWriteSuppressesWarning:
    """串接情境：append-log 與 complete 同鏈時，self_check_warning 歸零。"""

    def test_missing_self_check_with_chained_append_log_suppressed(self, tmp_path):
        module = _load_hook_module()
        _write_imp_ticket_without_self_check(tmp_path)

        chained_command = (
            'ticket track append-log 0.0.0-W1-998 --section "Solution" '
            '"### 自檢結果\\n- [x] 已檢視" && '
            "ticket track complete 0.0.0-W1-998"
        )

        result = module.check_acceptance_status(
            "0.0.0-W1-998", tmp_path, _FakeLogger(), command=chained_command
        )

        assert result.self_check_warning is None

    def test_missing_self_check_with_chained_set_acceptance_suppressed(self, tmp_path):
        """set-acceptance 亦屬 _CHAINED_WRITE_TRIGGERS，同樣應抑制。"""
        module = _load_hook_module()
        _write_imp_ticket_without_self_check(tmp_path)

        chained_command = (
            "ticket track set-acceptance 0.0.0-W1-998 --check 1 && "
            "ticket track complete 0.0.0-W1-998"
        )

        result = module.check_acceptance_status(
            "0.0.0-W1-998", tmp_path, _FakeLogger(), command=chained_command
        )

        assert result.self_check_warning is None
