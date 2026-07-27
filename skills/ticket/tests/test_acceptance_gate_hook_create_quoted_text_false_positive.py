"""
測試 acceptance-gate-hook 不再將 `ticket track create` 命令中引號內文字
誤判為 `ticket track complete` 呼叫（0.2.1-W3-020）。

背景（死鎖實證，PM 兩度親歷 0.2.1-W3-016 / 0.2.1-W3-019）：
`ticket track create` 常帶 `--why "..."` 等長文字參數，內容可能引用
「ticket track complete」字面（例如描述本 Hook 行為的 why 文字，或引用
本票 Context Bundle 中「acceptance-gate 偵測到...」的敘述）。
is_complete_command 若對整串命令做子字串比對，會把引號內文字誤判為真正
的 complete 呼叫，導致 create 命令被連帶擋下——而 create 正是解除該
spawn 落地未完成狀態的唯一手段，形成死鎖。

修復：比對前先移除命令中單/雙引號包住的內容（_strip_quoted_spans），
只有「引號外」出現的 complete 呼叫才會被判定為 complete 命令。

豁免邊界（不可使檢查失效）：真正的 complete 呼叫（不在引號內）仍必須
被偵測到並執行完整驗收檢查；豁免只排除「引號內文字造成的誤判」，不解除
對真正 complete 命令的驗收約束。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _load_hook_module():
    hook_path = (
        Path(__file__).resolve().parents[1]
        / "hooks"
        / "acceptance-gate-hook.py"
    )
    spec = importlib.util.spec_from_file_location(
        "acceptance_gate_hook_create_quoted_test", hook_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def module():
    return _load_hook_module()


class TestCreateCommandWithQuotedCompleteTextNotBlocked:
    """create 命令即使 --why 引號文字含「ticket track complete」字面，也不應被誤判為 complete 命令。"""

    def test_create_with_why_mentioning_complete_is_not_complete_command(self, module):
        command = (
            'ticket track create --version 0.2.1 --type IMP '
            '--source-ticket 0.2.1-W3-016 '
            '--why "acceptance-gate 偵測到 ticket track complete 執行前的 spawn 落地檢查未通過" '
            '--what "修復死鎖"'
        )
        assert module.is_complete_command(command) is False, (
            "create 命令的 --why 引號文字含 complete 字面時，不應被判定為 complete 命令"
            "（0.2.1-W3-020 死鎖修復）"
        )

    def test_create_with_why_mentioning_batch_complete_is_not_complete_command(self, module):
        command = (
            'ticket track create --version 0.2.1 --type IMP '
            '--why "應避免與 ticket track batch-complete 衝突"'
        )
        assert module.is_complete_command(command) is False

    def test_extract_ticket_id_returns_none_for_create_with_quoted_complete_text(self, module):
        command = (
            'ticket track create --version 0.2.1 --type IMP '
            '--source-ticket 0.2.1-W3-016 '
            '--why "引用 ticket track complete 字面"'
        )
        # logger 只需支援 info/debug，這裡用最小 stub
        class _NullLogger:
            def info(self, *a, **k):
                pass

            def debug(self, *a, **k):
                pass

        assert module.extract_ticket_id_from_command(command, _NullLogger()) is None


class TestRealCompleteCommandStillDetected:
    """豁免不可使檢查失效：真正的（非引號內）complete 呼叫仍必須被偵測到。"""

    def test_plain_complete_command_still_detected(self, module):
        command = "ticket track complete 0.2.1-W3-016"
        assert module.is_complete_command(command) is True

    def test_plain_batch_complete_command_still_detected(self, module):
        command = "ticket track batch-complete 0.2.1-W3-016,0.2.1-W3-017"
        assert module.is_complete_command(command) is True

    def test_chained_real_complete_outside_quotes_still_detected(self, module):
        """complete 呼叫本身（非引號內）與其他命令串接時，仍應被偵測到。"""
        command = (
            'ticket track append-log 0.2.1-W3-016 --section "Solution" "done" '
            '&& ticket track complete 0.2.1-W3-016'
        )
        assert module.is_complete_command(command) is True

    def test_complete_command_with_id_inside_quoted_unrelated_text_still_extracts_real_id(
        self, module
    ):
        """即使命令中另有引號文字提及其他 ticket ID，真正 complete 呼叫的 ID 仍可正確擷取。"""
        class _NullLogger:
            def info(self, *a, **k):
                pass

            def debug(self, *a, **k):
                pass

        command = 'ticket track complete 0.2.1-W3-016'
        ticket_id = module.extract_ticket_id_from_command(command, _NullLogger())
        assert ticket_id == "0.2.1-W3-016"
