"""
test_bulk_create_version_detection
====================================

覆蓋「ticket batch-create 未指定 --version 時版本偵測與 ticket create
不同源」修復（對應 ticket 0.2.1-W3-1296）。

重現情境：todolist.yaml 已註冊唯一 active 版本 0.2.1，`ticket create`
省略 --version 時可自動偵測；`ticket batch-create` 省略 --version 時
原始實作僅檢查 `args.version` 是否為 None，未呼叫任何版本偵測路徑，
直接回報「無法偵測版本」（即使專案結構與 create 命令下完全相同）。

驗證重點：
1. 省略 --version 時 batch-create（--dry-run）應能偵測出 0.2.1，
   與 create 命令共用同一偵測路徑（resolve_version），非各自實作。
2. 明確指定 --version 時仍尊重顯式值（不被自動偵測覆蓋）。
"""
import argparse
import io
from contextlib import redirect_stderr, redirect_stdout

import pytest

from ticket_system.commands import bulk_create as bulk_create_cmd


@pytest.fixture
def single_active_version_root(tmp_path_factory, monkeypatch):
    """僅一個 active 版本、無 proposals，重現 create 可偵測但
    batch-create 無法偵測的落差情境。"""
    root = tmp_path_factory.mktemp("bulk-create-version-root")
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
        template="impl-parsley",
        targets="測試目標一",
        version=None,
        wave=3,
        parent=None,
        dry_run=True,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _capture(args):
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    exit_code = None
    try:
        with redirect_stdout(out_buf), redirect_stderr(err_buf):
            exit_code = bulk_create_cmd.execute(args)
    except SystemExit as exc:
        exit_code = exc.code
    return out_buf.getvalue(), err_buf.getvalue(), exit_code


def test_batch_create_detects_version_without_explicit_flag(
    single_active_version_root,
):
    """省略 --version 時，batch-create 應與 create 共用偵測路徑，
    在僅有唯一 active 版本的專案結構下成功偵測為 0.2.1（不回報
    「無法偵測版本」）。"""
    args = _make_args(version=None)
    stdout, _, exit_code = _capture(args)

    assert exit_code == 0
    assert "無法偵測版本" not in stdout
    assert "0.2.1" in stdout


def test_batch_create_respects_explicit_version_flag(
    single_active_version_root,
):
    """明確指定 --version 時，不被自動偵測覆蓋。"""
    args = _make_args(version="9.9.9")
    stdout, _, exit_code = _capture(args)

    assert exit_code == 0
    assert "9.9.9" in stdout
