"""
test_create_error_envelope
==========================

W17-008.5.3：覆蓋 commands/create.py 業務錯誤路徑改寫為 ErrorEnvelope 後的整合測試。

每案例呼叫 ticket CLI（subprocess）模擬實際使用，斷言：
- exit code = 1（錯誤路徑）或 envelope 輸出
- stdout / stderr 含 ERROR_ENVELOPE_VERSION_MARKER
- 含對應 component / action / errno

Source: ticket 0.18.0-W17-008.5.3
"""
import argparse
import io
import sys
from contextlib import redirect_stderr, redirect_stdout

from ticket_system.commands import create as create_cmd
from ticket_system.lib.messages import ERROR_ENVELOPE_VERSION_MARKER


# W1-054：opt-out 統一為簽名注入——本檔測試 version=None 自動偵測路徑，需真實 repo
# todolist/work-logs；各測試函式簽名直接加入 `real_repo_root`（取代原 `_use_real_repo_root`
# 中介 autouse fixture），覆蓋 autouse `_isolate_project_root` 的空 tmp 隔離。所有測試走
# early-exit 錯誤路徑（exit 1），不抵達 file_lock，無 lock 污染風險。


def _make_args(**overrides):
    """建立 argparse.Namespace 包含 create.execute 預期欄位的預設值。"""
    defaults = dict(
        version=None,
        wave=None,
        seq=None,
        action="測試",
        target="錯誤路徑",
        title=None,
        type="IMP",
        priority=None,
        who=None,
        what=None,
        when=None,
        where_layer=None,
        where_files=None,
        why="測試錯誤路徑",
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
# 整合測試 1：缺 --wave 參數
# ---------------------------------------------------------------------------


def test_missing_wave_emits_envelope(real_repo_root):
    """根任務未提供 --wave → envelope MISSING_WAVE_PARAMETER。"""
    args = _make_args(wave=None, parent=None)
    stdout, _, exit_code = _capture(args)
    assert exit_code == 1
    assert ERROR_ENVELOPE_VERSION_MARKER in stdout
    assert "component: create" in stdout
    assert "errno: MISSING_WAVE_PARAMETER" in stdout


# ---------------------------------------------------------------------------
# 整合測試 2：非法 --type（會走到 validate_version_registered 之後的邏輯）
# 這裡用 --source-ticket 格式無效作為 errno=INVALID_TICKET_ID_FORMAT 的入口
# ---------------------------------------------------------------------------


def test_invalid_source_ticket_id_emits_envelope(real_repo_root):
    """--source-ticket ID 格式無效 → envelope INVALID_TICKET_ID_FORMAT。"""
    args = _make_args(wave=99, source_ticket="not-a-valid-id", type="IMP")
    stdout, _, exit_code = _capture(args)
    assert exit_code == 1
    assert ERROR_ENVELOPE_VERSION_MARKER in stdout
    assert "errno: INVALID_TICKET_ID_FORMAT" in stdout
    assert "action: validate_source_ticket" in stdout


# ---------------------------------------------------------------------------
# 整合測試 3：--source-ticket 與 --parent 互斥
# ---------------------------------------------------------------------------


def test_source_parent_mutually_exclusive_emits_envelope(real_repo_root):
    """--source-ticket 與 --parent 同用 → envelope SOURCE_PARENT_MUTUALLY_EXCLUSIVE。"""
    args = _make_args(
        wave=99,
        parent="0.99.0-W99-001",
        source_ticket="0.99.0-W99-002",
    )
    stdout, _, exit_code = _capture(args)
    assert exit_code == 1
    assert ERROR_ENVELOPE_VERSION_MARKER in stdout
    assert "errno: SOURCE_PARENT_MUTUALLY_EXCLUSIVE" in stdout


# ---------------------------------------------------------------------------
# 整合測試 4：--why 缺失（IMP 類型）
# ---------------------------------------------------------------------------


def test_why_missing_for_imp_merges_into_checklist_error(real_repo_root):
    """IMP 類型未提供 --why → 併入 CHECKLIST_VALIDATION_FAILED 一次列全。

    1.0.0-W1-024.1 A2：WHY_REQUIRED 提前退出已移除，why 與其他必填欄位
    （when/who/how_strategy）統一由 checklist 合併單一錯誤回報。
    """
    args = _make_args(
        wave=99,
        type="IMP",
        why=None,
        decision_tree_entry="x",
        decision_tree_decision="y",
        decision_tree_rationale="z",
    )
    stdout, stderr, exit_code = _capture(args)
    assert exit_code == 1
    combined = stdout + stderr
    assert "WHY_REQUIRED" not in combined
    assert ERROR_ENVELOPE_VERSION_MARKER in stdout
    assert "errno: CHECKLIST_VALIDATION_FAILED" in stdout
    assert "why" in stdout


# ---------------------------------------------------------------------------
# 整合測試 5：decision-tree 部分參數（非豁免）
# ---------------------------------------------------------------------------


def test_decision_tree_partial_params_emits_envelope(real_repo_root):
    """非豁免（IMP 根任務）但僅提供部分 decision-tree 參數 → envelope DECISION_TREE_MISSING_PARTIAL。"""
    args = _make_args(
        wave=99,
        type="IMP",
        decision_tree_entry="entry only",  # decision/rationale 缺
    )
    stdout, _, exit_code = _capture(args)
    assert exit_code == 1
    assert ERROR_ENVELOPE_VERSION_MARKER in stdout
    assert "errno: DECISION_TREE_MISSING_PARTIAL" in stdout


# ---------------------------------------------------------------------------
# 整合測試 6：decision-tree 全缺（非豁免）
# ---------------------------------------------------------------------------


def test_decision_tree_missing_all_merges_into_checklist(real_repo_root):
    """非豁免全缺 decision-tree → 不再提前退出，併入 CHECKLIST 一次列全（W1-029，A2 同手法）。

    舊行為：DECISION_TREE_MISSING_ALL 在 config 建構階段 sys.exit(1)，早於
    checklist，全欄位缺漏需多輪試錯。新行為：decision_tree_path 缺失與
    when/who/how_strategy 等合併單一 CHECKLIST_VALIDATION_FAILED。
    """
    args = _make_args(
        wave=99,
        type="IMP",
    )
    stdout, stderr, exit_code = _capture(args)
    combined = stdout + stderr
    assert exit_code == 1
    # 提前退出路徑已移除
    assert "DECISION_TREE_MISSING_ALL" not in combined
    # 併入單一 checklist 錯誤，decision_tree_path 與其他必填一次列全
    assert "CHECKLIST_VALIDATION_FAILED" in combined
    assert "decision_tree_path" in combined


def test_decision_tree_only_missing_reported_via_checklist(real_repo_root):
    """其他必填齊全、僅缺 decision-tree → checklist 接住並列 decision_tree_path（W1-029）。

    驗證 decision-tree 缺失確實被併入 checklist（而非靜默忽略）：其他欄位
    填妥時，唯一缺失即 decision_tree_path，仍由 CHECKLIST 阻擋。
    """
    args = _make_args(
        wave=99,
        type="IMP",
        why="理由",
        when="時機",
        who="agent",
        how_strategy="策略",
        where_files="src/x.py",
        acceptance="條件 A",
        # decision-tree 三參數全缺
    )
    stdout, stderr, exit_code = _capture(args)
    combined = stdout + stderr
    assert exit_code == 1
    assert "CHECKLIST_VALIDATION_FAILED" in combined
    assert "decision_tree_path" in combined


# ---------------------------------------------------------------------------
# 整合測試 7：blocked-by 不存在的 ticket
# ---------------------------------------------------------------------------


def test_blocked_by_not_found_emits_envelope(real_repo_root):
    """blockedBy 引用不存在的 ticket → envelope BLOCKED_BY_NOT_FOUND。"""
    args = _make_args(
        wave=99,
        type="DOC",  # DOC 豁免 decision-tree
        blocked_by="0.99.0-W99-DOES-NOT-EXIST",
        why="not required for DOC",
    )
    stdout, _, exit_code = _capture(args)
    # DOC 豁免 why；但 blocked-by 應觸發 envelope
    assert exit_code == 1
    assert ERROR_ENVELOPE_VERSION_MARKER in stdout
    # 可能是 INVALID_TICKET_ID_FORMAT（先驗格式）或 BLOCKED_BY_NOT_FOUND
    assert ("errno: BLOCKED_BY_NOT_FOUND" in stdout
            or "errno: INVALID_TICKET_ID_FORMAT" in stdout)
