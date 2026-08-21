"""
test_create_version_not_registered_fallback_hint
==================================================

覆蓋「ticket create 依動詞自動選版命中未註冊版本時無退場路徑」修復
（對應 ticket：修正 ticket create 依動詞自動選版命中未註冊版本時無退場
路徑）。

重現情境：僅帶 --wave 與 --type IMP --action 新增（不傳 --version），
動詞「新增」被 suggest_version_for_ticket 分類為新功能，導向下一個
大版本；若該大版本未在 todolist.yaml 註冊，即命中本測試覆蓋的路徑。

驗證重點：
1. 硬失敗仍發生（exit code 1，errno VERSION_NOT_REGISTERED）。
2. hint 附加可立即執行的 --version 繞過指令（採 how.strategy 方向 b，
   輔以 --source-ticket ID 前綴 / 當前 active 版本推導，對應方向 c 的
   可靠子集）。
"""
import argparse
import io
from contextlib import redirect_stderr, redirect_stdout

import pytest

from ticket_system.commands import create as create_cmd


@pytest.fixture
def single_active_version_root(tmp_path_factory, monkeypatch):
    """僅一個 active 版本、無 proposals，強制 _suggest_next_major 落到
    「max_ver minor+1」分支，產生未註冊的建議版本，精確重現原始情境
    （PM 於既有版本內建 spawn ticket 時，動詞分類選中未開版的次版本）。
    """
    root = tmp_path_factory.mktemp("single-active-root")
    (root / "docs" / "work-logs").mkdir(parents=True, exist_ok=True)
    (root / "CLAUDE.md").write_text("# CLAUDE.md\n", encoding="utf-8")
    (root / "docs" / "todolist.yaml").write_text(
        "versions:\n"
        "  - version: 0.2.1\n"
        "    status: active\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
    return root


def _make_args(**overrides):
    defaults = dict(
        version=None,
        wave=3,
        seq=None,
        action="新增",
        target="ticket create 的 when-blockedBy 一致性警告",
        title=None,
        type="IMP",
        priority=None,
        who=None,
        what=None,
        when=None,
        where_layer=None,
        where_files=None,
        why="重現未註冊版本無退場路徑",
        how_type=None,
        how_strategy=None,
        parent=None,
        source_ticket=None,
        blocked_by=None,
        related_to=None,
        acceptance=None,
        decision_tree_entry=None,
        decision_tree_decision=None,
        decision_tree_rationale=None,
        quiet=False,
        verbose=False,
        json_output=False,
        force=False,
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


def test_unregistered_version_hint_falls_back_to_current_active_version(
    single_active_version_root,
):
    """未傳 --source-ticket 時，hint 應建議當前 active 版本（0.2.1）。"""
    args = _make_args(source_ticket=None)
    stdout, _, exit_code = _capture(args)

    assert exit_code == 1
    assert "errno: VERSION_NOT_REGISTERED" in stdout
    assert "--version 0.2.1" in stdout
    assert "目前進行中版本" in stdout


def test_unregistered_version_hint_prefers_source_ticket_version(
    single_active_version_root,
):
    """帶 --source-ticket 時，優先以其 ID 前綴推導版本（比 wave 更可靠）。"""
    args = _make_args(source_ticket="0.2.1-W3-387")
    stdout, _, exit_code = _capture(args)

    assert exit_code == 1
    assert "errno: VERSION_NOT_REGISTERED" in stdout
    assert "--version 0.2.1" in stdout
    assert "--source-ticket 0.2.1-W3-387" in stdout


def test_unregistered_version_hint_omitted_when_no_registered_candidate(
    tmp_path_factory, monkeypatch,
):
    """todolist.yaml 無任何已註冊版本可推導時，不附加繞過指令（避免建議
    另一個同樣未註冊的版本）。"""
    root = tmp_path_factory.mktemp("no-candidate-root")
    (root / "docs" / "work-logs").mkdir(parents=True, exist_ok=True)
    (root / "CLAUDE.md").write_text("# CLAUDE.md\n", encoding="utf-8")
    # 僅一個 completed 版本、無 active：suggest_version_for_ticket 仍能算出
    # 未註冊的建議版本（1.1.0），但 get_current_version 無 active 可回退，
    # 使 determine_fallback_version 兩條推導路徑皆落空。
    (root / "docs" / "todolist.yaml").write_text(
        "versions:\n"
        "  - version: 1.0.0\n"
        "    status: completed\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))

    args = _make_args(source_ticket=None)
    stdout, _, exit_code = _capture(args)

    assert exit_code == 1
    assert "errno: VERSION_NOT_REGISTERED" in stdout
    assert "若此票應歸屬既有版本" not in stdout
