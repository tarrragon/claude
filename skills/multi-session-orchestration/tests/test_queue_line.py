"""queue_line.py 測試：與 line-board lanes.ts 讀同一份 queue-line-cases.json，斷言分類相同。

1. parse_lanes 逐筆等於案例表 expect（lanes.test.ts 對同一表做同樣斷言）
2. is_current_lane 與 statusline_lane.active_lanes 逐筆等於案例表推導的現行線
   （ended 為 null 且 tickets 非空；lanes.test.ts 以看板判定比對同一推導）
3. E2 正向對照：無票號與附說明收線的行，舊的狀態列判定（只排除（無）／（結束））會當成現行線，新判定不會
"""

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import queue_line as ql  # noqa: E402
import statusline_lane  # noqa: E402

CASES_JSON = (
    Path(__file__).resolve().parents[2] / "line-board" / "tests" / "queue-line-cases.json"
)
CASES = json.loads(CASES_JSON.read_text(encoding="utf-8"))["cases"]
IDS = [c["name"] for c in CASES]


def expected_current(case):
    return {lane["lane"]: lane["session"] for lane in case["expect"] if lane["ended"] is None and lane["tickets"]}


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_parse_lanes_matches_shared_case(case):
    assert ql.parse_lanes(case["text"], case["prefix"]) == case["expect"]


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_is_current_lane_matches_shared_case(case):
    lanes = ql.parse_lanes(case["text"], case["prefix"])
    assert {lane["lane"]: lane["session"] for lane in lanes if ql.is_current_lane(lane)} == expected_current(case)


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_statusline_active_lanes_matches_shared_case(case):
    assert statusline_lane.active_lanes(case["text"], case["prefix"]) == expected_current(case)


def _old_statusline_active(text):
    """改用共用模組前的狀態列判定：只排除恰為（無）或（結束）的行。"""
    return {line["lane"]: line["session"] for line in ql.parse_lane_lines(text) if line["queue"] not in ("（無）", "（結束）")}


@pytest.mark.parametrize(
    "queue",
    ["待命，等用戶裁定", " → ", "", "無（今天收工）", "（無）（全數終態）"],
)
def test_e2_text_only_or_noted_end_is_not_current(queue):
    text = "## Solution\n**L5 現行佇列**（s-a）：%s\n" % queue
    assert _old_statusline_active(text) == {5: "s-a"}  # 舊判定照常顯示為現行線
    assert statusline_lane.active_lanes(text, "0.5.0-W1-") == {}


def test_ticket_prefix_of():
    assert ql.ticket_prefix_of("0.5.0-W1-349") == "0.5.0-W1-"
    assert ql.ticket_prefix_of("v1.2.3-W4-005.1") == "1.2.3-W4-"
    assert ql.ticket_prefix_of("coord") is None


def test_wave_id_needs_prefix_to_count_as_ticket():
    """W<波次>-<序號> 寫法要有前綴才能補全；狀態列以協調票檔名推導前綴，否則該線會被當成無票號。"""
    text = "## Solution\n**L5 現行佇列**（s-a）：W3-012\n"
    assert statusline_lane.active_lanes(text, "0.5.0-W1-") == {5: "s-a"}
    assert statusline_lane.active_lanes(text, "") == {}
