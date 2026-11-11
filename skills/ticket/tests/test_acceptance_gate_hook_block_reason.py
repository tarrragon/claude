"""acceptance-gate-hook 阻擋時 WARNING 行依阻擋來源寫出各自原因。

每個阻擋來源建出 block_source，describe_block_reason 回傳各自文字；
未標示來源時退回通用文字（不得再誤寫「子任務未完成」）。
"""
import importlib.util
from pathlib import Path

import pytest


def _load_hook_module():
    path = Path(__file__).resolve().parents[1] / "hooks" / "acceptance-gate-hook.py"
    spec = importlib.util.spec_from_file_location("acceptance_gate_hook_reason", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hook = _load_hook_module()


def _blocked(source):
    return hook.AcceptanceCheckResult(
        True, False, "msg", False, [], block_source=source
    )


@pytest.mark.parametrize("source", sorted(hook.BLOCK_REASONS))
def test_each_source_has_own_reason(source):
    reason = hook.describe_block_reason(_blocked(source))
    assert reason == hook.BLOCK_REASONS[source]


def test_reasons_are_pairwise_distinct():
    reasons = list(hook.BLOCK_REASONS.values())
    assert len(set(reasons)) == len(reasons)


@pytest.mark.parametrize(
    "source", [s for s in hook.BLOCK_REASONS if s != "children"]
)
def test_non_children_source_not_labeled_children(source):
    assert "子任務未完成" not in hook.describe_block_reason(_blocked(source))


def test_unlabeled_source_uses_generic_text():
    reason = hook.describe_block_reason(_blocked(""))
    assert "子任務未完成" not in reason
    assert "來源未標示" in reason


def test_default_block_source_is_empty():
    result = hook.AcceptanceCheckResult(False, False, None, False, [])
    assert result.block_source == ""


# 擋下時的評估時點說明：complete 之前串有寫入才附加
_TID = "0.0.0-W1-996"
_CHAINED = (
    f'ticket track append-log {_TID} --section "Solution" "證據" && '
    f"ticket track complete {_TID}"
)
_ALONE = f"ticket track complete {_TID}"


def test_chained_write_block_gets_timing_note():
    result = hook.with_chained_block_note(_blocked("hook_protection"), _CHAINED)
    assert result.message.startswith("msg")
    assert "評估時點" in result.message
    assert "單獨執行" in result.message
    assert result.should_block is True


def test_chained_set_how_block_gets_timing_note():
    """set-how 可改變 how.strategy 盤點表（hook 防護擋下來源），同樣附說明。"""
    command = f'ticket track set-how {_TID} --strategy "表" && ticket track complete {_TID}'
    result = hook.with_chained_block_note(_blocked("hook_protection"), command)
    assert "評估時點" in result.message


def test_read_only_before_complete_has_no_timing_note():
    command = f"ticket track query {_TID} && ticket track complete {_TID}"
    result = hook.with_chained_block_note(_blocked("hook_protection"), command)
    assert result.message == "msg"


def test_lone_complete_block_has_no_timing_note():
    """對照組：單獨的 complete 被擋時訊息不變。"""
    result = hook.with_chained_block_note(_blocked("hook_protection"), _ALONE)
    assert result.message == "msg"


def test_allowed_result_untouched_even_when_chained():
    allowed = hook.AcceptanceCheckResult(False, True, None, False, [])
    assert hook.with_chained_block_note(allowed, _CHAINED) is allowed
