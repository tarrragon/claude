"""create.execute 一律回報本次存入的驗收條數與逐條內容整合測試。

覆蓋範圍：`--acceptance` 是四個多值參數中唯一不用逗號分隔者，逗號輸入會被
當成內文字面靜默摺疊為單一條目（不像 `--where`/`--blocked-by`/`--related-to`
會依逗號拆開）。既有的 `|` 拆條 preview（ACCEPTANCE_PIPE_SPLIT_WARNING）只在
偵測到分隔符拆條時才輸出，逗號摺疊完全無聲。本測試驗證修復後的回報改為
「一律」輸出，呼叫者對照自己輸入的預期條數即可當場發現摺疊，不論摺疊成因
是逗號、頓號或任何其他未被特別偵測的分隔符。
"""
from __future__ import annotations

import argparse
import io
from contextlib import redirect_stderr, redirect_stdout

from ticket_system.commands import create as create_cmd


def _make_args(**overrides):
    defaults = dict(
        version="1.0.1",
        wave=1,
        seq=None,
        action="實作",
        target="acceptance 回報測試",
        title=None,
        type="IMP",
        priority=None,
        who="待派發",
        what=None,
        when="立即",
        where_layer=None,
        where_files="ticket_system/tests/test_create_acceptance_stored_report.py",
        why="測試 acceptance 存入回報",
        how_type=None,
        how_strategy="驗證 acceptance 存入回報行為",
        parent=None,
        source_ticket=None,
        blocked_by=None,
        related_to=None,
        acceptance=["測試通過"],
        decision_tree_entry="Ticket",
        decision_tree_decision="直接派發",
        decision_tree_rationale="測試情境",
        quiet=False,
        verbose=False,
        json_output=False,
        force=False,
        allow_duplicate=False,
        topic=None,
        new_topic=None,
        no_topic=False,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _capture(args):
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    exit_code = None
    try:
        with redirect_stdout(out_buf), redirect_stderr(err_buf):
            exit_code = create_cmd.execute(args)
    except SystemExit as exc:
        exit_code = exc.code
    return out_buf.getvalue(), err_buf.getvalue(), exit_code


def test_comma_joined_acceptance_reports_single_stored_item(seeded_repo_root):
    # 逗號在 --acceptance 不是分隔符（與 --where 等三參數不同），六條判準
    # 以逗號串接會被整段當成一條內文收下——這正是本票要修的靜默摺疊。
    raw = "條件A,條件B,條件C"
    args = _make_args(acceptance=[raw])
    out, _err, exit_code = _capture(args)

    assert exit_code == 0
    assert "本次存入 1 條驗收條件" in out
    assert raw in out


def test_multiple_acceptance_flags_report_each_item_and_count(seeded_repo_root):
    args = _make_args(acceptance=["條件一", "條件二", "條件三"])
    out, _err, exit_code = _capture(args)

    assert exit_code == 0
    assert "本次存入 3 條驗收條件" in out
    for item in ("條件一", "條件二", "條件三"):
        assert item in out


def test_pipe_split_acceptance_also_reports_final_stored_count(seeded_repo_root):
    # 分隔符（|）拆條後，回報的條數應與拆條結果一致（3 條，不是 1 條）。
    args = _make_args(acceptance=["條件甲|條件乙|條件丙"])
    out, _err, exit_code = _capture(args)

    assert exit_code == 0
    assert "本次存入 3 條驗收條件" in out
    for item in ("條件甲", "條件乙", "條件丙"):
        assert item in out
