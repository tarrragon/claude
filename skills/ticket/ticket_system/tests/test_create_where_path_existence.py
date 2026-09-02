"""create.execute 的 where.files 路徑存在性 WARNING 整合測試。

覆蓋範圍：`missing_where_paths` 已在 test_field_validators.py 單元測試，本檔
只驗證掛載於 create.execute 的整合行為——不存在路徑輸出 WARNING、不阻擋建票
（exit 0）；存在路徑不輸出無關 WARNING。
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
        target="where 路徑存在性測試",
        title=None,
        type="IMP",
        priority=None,
        who="待派發",
        what=None,
        when="立即",
        where_layer=None,
        where_files="does-not-exist-dir/does-not-exist-file.py",
        why="測試 where.files 路徑存在性 WARNING",
        how_type=None,
        how_strategy="驗證路徑存在性檢查行為",
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


def test_create_with_missing_where_path_warns_but_succeeds(seeded_repo_root):
    args = _make_args()
    out, _err, exit_code = _capture(args)

    assert exit_code == 0
    assert "[WARNING]" in out
    assert "路徑不存在" in out
    assert "does-not-exist-dir/does-not-exist-file.py" in out


def test_create_with_existing_where_path_no_path_warning(seeded_repo_root):
    existing = seeded_repo_root / "CLAUDE.md"
    assert existing.exists()

    args = _make_args(where_files="CLAUDE.md")
    out, _err, exit_code = _capture(args)

    assert exit_code == 0
    assert "路徑不存在" not in out
