"""
test_create_ux_merged_validation
================================

create 命令 UX 改善的回歸測試（1.0.0-W1-024.1）。

- A2：必填欄位（why/when/who/how_strategy）缺漏時一次列全於單一
  CHECKLIST_VALIDATION_FAILED，不再由 WHY_REQUIRED 提前退出造成分批報錯。
- A3：`--how` 因 argparse prefix matching 撞 --how-type / --how-strategy 時，
  給含用途說明的友善提示（任務類型／實作策略），取代原生英文 ambiguous 訊息。

Source: ticket 1.0.0-W1-024.1（parent ANA 1.0.0-W1-024 裁決 A2+A3）
"""
import argparse
import io

from contextlib import redirect_stderr, redirect_stdout

import pytest

from ticket_system.commands import create as create_cmd


# W1-054：opt-out 統一為簽名注入——本檔測試 version=None 自動偵測路徑，需真實 repo
# todolist/work-logs；各測試函式簽名直接加入 `real_repo_root`（取代原 `_use_real_repo_root`
# 中介 autouse fixture），覆蓋 autouse `_isolate_project_root` 的空 tmp 隔離。測試走
# early-exit 錯誤路徑（exit 1），不抵達 file_lock，無 lock 污染風險。


def _make_args(**overrides):
    """建立 argparse.Namespace 包含 create.execute 預期欄位的預設值。"""
    defaults = dict(
        version=None,
        wave=None,
        seq=None,
        action="測試",
        target="UX 合併驗證",
        title=None,
        type="IMP",
        priority=None,
        who=None,
        what=None,
        when=None,
        where_layer=None,
        where_files=None,
        why="測試 UX 路徑",
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
    """執行 create.execute(args) 並擷取 stdout / stderr / exit code。"""
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    exit_code = None
    try:
        with redirect_stdout(out_buf), redirect_stderr(err_buf):
            exit_code = create_cmd.execute(args)
    except SystemExit as exc:
        exit_code = exc.code
    return out_buf.getvalue(), err_buf.getvalue(), exit_code


# ---------------------------------------------------------------------------
# A2：必填欄位缺漏一次列全（why 不再提前退出）
# ---------------------------------------------------------------------------


def test_missing_required_fields_listed_in_single_error(real_repo_root):
    """why/when/who/how_strategy 全缺 → 單一 CHECKLIST_VALIDATION_FAILED 一次列全。

    舊行為：WHY_REQUIRED 在 parse 階段 sys.exit(1)，其餘缺漏要再跑一次才看到
    （本 session 實證 3 次試錯）。新行為：所有缺漏合併單一錯誤。
    """
    args = _make_args(
        wave=99,
        type="IMP",
        why=None,
        when=None,
        who=None,
        how_strategy=None,
        decision_tree_entry="x",
        decision_tree_decision="y",
        decision_tree_rationale="z",
    )
    stdout, stderr, exit_code = _capture(args)
    combined = stdout + stderr

    assert exit_code == 1
    # 提前退出路徑已移除
    assert "WHY_REQUIRED" not in combined
    # 單一合併錯誤
    assert "CHECKLIST_VALIDATION_FAILED" in combined
    # 四個必填欄位一次列全
    for field in ("why", "when", "who", "how_strategy"):
        assert field in combined, f"缺漏欄位 {field} 未出現在合併錯誤清單"


def test_why_only_missing_still_reported_via_checklist(real_repo_root):
    """僅 why 缺漏（其餘補齊）→ 仍走 CHECKLIST_VALIDATION_FAILED，不再有 WHY_REQUIRED。"""
    args = _make_args(
        wave=99,
        type="IMP",
        why=None,
        when="測試時機",
        who="thyme-python-developer",
        how_strategy="測試策略",
        where_files="a.py",
        acceptance=["條件A"],
        decision_tree_entry="x",
        decision_tree_decision="y",
        decision_tree_rationale="z",
    )
    stdout, stderr, exit_code = _capture(args)
    combined = stdout + stderr

    assert exit_code == 1
    assert "WHY_REQUIRED" not in combined
    assert "CHECKLIST_VALIDATION_FAILED" in combined
    assert "why" in combined


def test_doc_type_still_exempts_why(real_repo_root):
    """DOC 類型豁免 why、IMP 不豁免（行為不變的回歸防護）。

    直接呼叫 _validate_create_checklist（單元層級，無持久化副作用），
    避免整合層測試在 persist 前被 blocked_by 驗證攔截造成永真斷言。
    """
    from ticket_system.commands.create import _validate_create_checklist
    from ticket_system.lib.constants import DEFAULT_UNDEFINED_VALUE

    config = {
        "where_files": ["a.md"],
        "acceptance": ["條件A"],
        "parent_id": None,
        "decision_tree_path": {
            "entry_point": "x", "final_decision": "y", "rationale": "z",
        },
        "when": "測試時機",
        "who": "rosemary-project-manager",
        "what": "測試",
        "why": DEFAULT_UNDEFINED_VALUE,
        "how_strategy": "測試策略",
    }
    assert "why" not in _validate_create_checklist(config, "DOC")
    assert "why" in _validate_create_checklist(config, "IMP")


# ---------------------------------------------------------------------------
# A3：--how 縮寫歧義給友善提示
# ---------------------------------------------------------------------------


def _build_parser():
    parser = argparse.ArgumentParser(prog="ticket")
    sub = parser.add_subparsers(dest="command")
    create_cmd.register(sub)
    return parser


def test_how_flag_gives_friendly_hint_with_value(real_repo_root, capsys):
    """`--how X` → 友善提示含兩個完整旗標名與中文用途說明。"""
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            ["create", "--action", "a", "--target", "b", "--how", "策略文字"]
        )
    err = capsys.readouterr().err
    assert "--how-type" in err
    assert "--how-strategy" in err
    # 中文用途說明（區別於 argparse 原生 ambiguous 英文訊息）
    assert "任務類型" in err
    assert "實作策略" in err


def test_how_flag_gives_friendly_hint_without_value(real_repo_root, capsys):
    """`--how`（無值）→ 同樣觸發友善提示，不報 expected one argument。"""
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["create", "--action", "a", "--target", "b", "--how"])
    err = capsys.readouterr().err
    assert "任務類型" in err
    assert "實作策略" in err


def test_full_flags_unaffected_by_how_trap(real_repo_root):
    """--how-type / --how-strategy 完整旗標不受 --how 攔截影響（回歸防護）。"""
    parser = _build_parser()
    args = parser.parse_args(
        [
            "create",
            "--action", "a",
            "--target", "b",
            "--how-type", "Implementation",
            "--how-strategy", "策略",
        ]
    )
    assert args.how_type == "Implementation"
    assert args.how_strategy == "策略"
