"""
Test: settings.json hook timeout 單位守衛（0.4.0-W1-047）

平台 hook timeout 單位為「秒」（code.claude.com/docs/en/hooks："Seconds before canceling."）。
以毫秒數值（如 5000）填寫會變成 83 分鐘以上的實際上限，等同未設逾時。
本測試斷言每一筆 timeout 都小於 1000，作為單位誤用的訊號。

E1：對現行 settings.json 斷言（修前為紅、修後為綠）。
E2：構造含 5000 的 fixture 設定，斷言檢查函式判其為紅（守衛正向對照輸入）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

SETTINGS_PATH = Path(__file__).resolve().parents[2] / "settings.json"
UNIT_MISUSE_THRESHOLD = 1000


def find_oversized_timeouts(settings: Dict[str, Any]) -> List[Tuple[str, Any]]:
    """回傳 (command, timeout) 清單：timeout 為數值且 >= 1000 者。"""
    bad: List[Tuple[str, Any]] = []
    for matchers in settings.get("hooks", {}).values():
        for matcher in matchers:
            for hook in matcher.get("hooks", []):
                timeout = hook.get("timeout")
                if isinstance(timeout, (int, float)) and timeout >= UNIT_MISUSE_THRESHOLD:
                    bad.append((hook.get("command", ""), timeout))
    return bad


def test_e1_current_settings_timeouts_are_seconds():
    settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    bad = find_oversized_timeouts(settings)
    assert bad == [], f"{len(bad)} 筆 timeout >= 1000（疑似毫秒誤用），首筆：{bad[:1]}"


def test_e2_fixture_with_millisecond_timeout_is_flagged():
    fixture = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [
                        {"type": "command", "command": "x.py", "timeout": 5000},
                        {"type": "command", "command": "y.py", "timeout": 30},
                    ],
                }
            ]
        }
    }
    assert find_oversized_timeouts(fixture) == [("x.py", 5000)]


TIMEOUT_FLOOR_SECONDS = 30


def find_undersized_timeouts(settings: Dict[str, Any]) -> List[Tuple[str, Any]]:
    """回傳 timeout 為數值且 < 30 者（須蓋過 uv 冷啟動約 14.5 秒）。"""
    bad: List[Tuple[str, Any]] = []
    for matchers in settings.get("hooks", {}).values():
        for matcher in matchers:
            for hook in matcher.get("hooks", []):
                timeout = hook.get("timeout")
                if isinstance(timeout, (int, float)) and timeout < TIMEOUT_FLOOR_SECONDS:
                    bad.append((hook.get("command", ""), timeout))
    return bad


def test_e1_current_settings_timeouts_meet_floor():
    settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    bad = find_undersized_timeouts(settings)
    assert bad == [], f"{len(bad)} 筆 timeout < 30，首筆：{bad[:1]}"


def test_e2_fixture_with_ten_second_timeout_is_flagged():
    fixture = {"hooks": {"Stop": [{"hooks": [{"command": "a.py", "timeout": 10}]}]}}
    assert find_undersized_timeouts(fixture) == [("a.py", 10)]


def test_fixture_with_second_timeouts_passes():
    fixture = {
        "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "z.py", "timeout": 999}]}]}
    }
    assert find_oversized_timeouts(fixture) == []
