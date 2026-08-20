"""
creation-acceptance-gate-hook 的 creation_accepted 型別正規化測試
（0.2.1-W3-665.8）。

背景：frontmatter 已改用 yaml.safe_load 原生型別解析（0.2.1-W3-665.2），
unquoted true/false 恆回 bool。`check_creation_accepted` 舊有的
`isinstance(str)` 分支（比對 "true"/"yes"/"1"）是手寫 parser 一律回字串
時代的相容補償，已隨遷移退役（0.2.1-W3-665.3 判定 B5 可退役）。

退役後改為 fail-closed：非 bool 型別一律視為 False，避免手動編輯成
`creation_accepted: "false"`（加引號字串）時因「非 None 即真值」被誤判為
True（繞過驗收閘門）。本測試鎖定此行為。
"""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from unittest.mock import patch

import pytest


def _load_hook_module():
    """動態 import hook（檔名含 dash，無法用一般 import）。"""
    hook_path = (
        Path(__file__).resolve().parents[1]
        / "hooks"
        / "creation-acceptance-gate-hook.py"
    )
    spec = importlib.util.spec_from_file_location(
        "creation_acceptance_gate_hook", hook_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def hook_module():
    return _load_hook_module()


def _logger():
    log = logging.getLogger("test_creation_accepted_gate_bool_normalization")
    log.addHandler(logging.NullHandler())
    return log


def _check(hook_module, creation_accepted_value):
    """以 mock 的 ticket 檔案 + frontmatter 呼叫 check_creation_accepted。"""
    with patch.object(
        hook_module, "find_ticket_file", return_value=Path("/fake/ticket.md")
    ), patch.object(
        hook_module,
        "parse_ticket_frontmatter",
        return_value={
            "creation_accepted": creation_accepted_value,
            "status": "pending",
        },
    ):
        return hook_module.check_creation_accepted("0.1.0-W1-001", _logger())


class TestNativeBoolInput:
    """yaml.safe_load 對 unquoted true/false 的原生輸出（現行主路徑）"""

    def test_bool_true_accepted(self, hook_module):
        is_accepted, message = _check(hook_module, True)
        assert is_accepted is True
        assert message is None

    def test_bool_false_blocked(self, hook_module):
        is_accepted, _message = _check(hook_module, False)
        assert is_accepted is False


class TestMissingOrNoneInput:
    def test_none_blocked(self, hook_module):
        is_accepted, _message = _check(hook_module, None)
        assert is_accepted is False


class TestQuotedStringInputFailClosed:
    """手動編輯成字串（加引號）時的 fail-closed 行為，退役後不再解析字串內容。"""

    def test_quoted_true_string_not_accepted(self, hook_module):
        """0.2.1-W3-665.3 判定退役前，字串 'true' 會被 .lower() 判為 True；
        退役後一律 fail-closed 為 False（非本票行為改善目標，僅副作用）。"""
        is_accepted, _message = _check(hook_module, "true")
        assert is_accepted is False

    def test_quoted_false_string_not_accepted(self, hook_module):
        """關鍵回歸案例：加引號的 'false' 字串在舊碼下正確判為 False；
        若退役後改為「非 None 即真值」會被誤判為 True（繞過驗收閘門）。
        fail-closed（非 bool 一律 False）避免此回歸。"""
        is_accepted, _message = _check(hook_module, "false")
        assert is_accepted is False
