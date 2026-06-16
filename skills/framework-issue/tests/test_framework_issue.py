"""framework-issue 命令測試：正常路徑 + 三種降級路徑。

全程以 mock 攔截 gh subprocess，不真打 GitHub API。
"""

import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import gh_common  # noqa: E402
import create_issue  # noqa: E402
import list_issues  # noqa: E402
import link_issue  # noqa: E402
import fix_status  # noqa: E402


def _completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(
        args=["gh"], returncode=returncode, stdout=stdout, stderr=stderr
    )


# --- 正常路徑 ---

def test_create_normal_path(monkeypatch):
    """gh 已裝已登入且建立成功 → exit 0，呼叫含正確 repo 與 title。"""
    monkeypatch.setattr(gh_common, "check_gh_available", lambda: True)
    monkeypatch.setattr(gh_common, "check_gh_authenticated", lambda: True)
    with mock.patch.object(
        gh_common.subprocess, "run", return_value=_completed(stdout="issue-url\n")
    ) as run:
        rc = create_issue.main(["--title", "T", "--body", "B", "--label", "bug"])
    assert rc == 0
    called = run.call_args.args[0]
    assert called[:2] == ["gh", "issue"]
    assert "--repo" in called and gh_common.FRAMEWORK_REPO in called
    assert "T" in called


def test_list_normal_path(monkeypatch):
    """list 正常路徑 → exit 0，stdout 原樣輸出。"""
    monkeypatch.setattr(gh_common, "check_gh_available", lambda: True)
    monkeypatch.setattr(gh_common, "check_gh_authenticated", lambda: True)
    with mock.patch.object(
        gh_common.subprocess, "run", return_value=_completed(stdout="#1 title\n")
    ):
        rc = list_issues.main(["--state", "open"])
    assert rc == 0


# --- 降級路徑 1：gh 未安裝 ---

def test_degraded_gh_not_installed(monkeypatch, capsys):
    monkeypatch.setattr(gh_common.shutil, "which", lambda _: None)
    rc = create_issue.main(["--title", "T"])
    assert rc == gh_common.EXIT_DEGRADED
    err = capsys.readouterr().err
    assert "未安裝" in err


# --- 降級路徑 2：gh 未登入 ---

def test_degraded_gh_not_authenticated(monkeypatch, capsys):
    monkeypatch.setattr(gh_common, "check_gh_available", lambda: True)
    with mock.patch.object(
        gh_common.subprocess, "run", return_value=_completed(returncode=1)
    ):
        rc = list_issues.main([])
    assert rc == gh_common.EXIT_DEGRADED
    assert "未登入" in capsys.readouterr().err


# --- 降級路徑 3：目標 repo Issues 停用 ---

def test_degraded_issues_disabled(monkeypatch, capsys):
    monkeypatch.setattr(gh_common, "check_gh_available", lambda: True)
    monkeypatch.setattr(gh_common, "check_gh_authenticated", lambda: True)
    with mock.patch.object(
        gh_common.subprocess,
        "run",
        return_value=_completed(returncode=1, stderr="Issues are disabled for this repo"),
    ):
        rc = create_issue.main(["--title", "T"])
    assert rc == gh_common.EXIT_DEGRADED
    assert "停用" in capsys.readouterr().err


# --- 降級路徑 4：subprocess 例外不 crash ---

def test_degraded_subprocess_exception(monkeypatch, capsys):
    monkeypatch.setattr(gh_common, "check_gh_available", lambda: True)
    monkeypatch.setattr(gh_common, "check_gh_authenticated", lambda: True)
    with mock.patch.object(
        gh_common.subprocess, "run", side_effect=OSError("boom")
    ):
        rc = list_issues.main([])
    assert rc == gh_common.EXIT_DEGRADED
    assert "framework-issue" in capsys.readouterr().err


# --- link 命令 ---

_PATTERN_TEMPLATE = """# PC-099: 範例 error-pattern

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-099 |
| 類別 | process-compliance |
| 風險等級 | 中 |

### 症狀

範例內文。
"""


def _patched_link_env(monkeypatch):
    """link 共用前置：gh 已裝已登入。"""
    monkeypatch.setattr(gh_common, "check_gh_available", lambda: True)
    monkeypatch.setattr(gh_common, "check_gh_authenticated", lambda: True)


def test_link_writes_canonical_issue(monkeypatch, tmp_path):
    """link 把 canonical_issue 寫入分類資訊表格末列，exit 0。"""
    _patched_link_env(monkeypatch)
    pattern_file = tmp_path / "PC-099-example.md"
    pattern_file.write_text(_PATTERN_TEMPLATE, encoding="utf-8")

    rc = link_issue.main([str(pattern_file), "tarrragon/claude#42"])
    assert rc == 0
    content = pattern_file.read_text(encoding="utf-8")
    assert "| canonical_issue | tarrragon/claude#42 |" in content
    # 寫入分類資訊表格內（風險等級列之後、症狀標題之前）
    assert content.index("canonical_issue") < content.index("### 症狀")


def test_link_duplicate_updates_not_appends(monkeypatch, tmp_path):
    """重複 link 為更新既有列，不產生第二列。"""
    _patched_link_env(monkeypatch)
    pattern_file = tmp_path / "PC-099-example.md"
    pattern_file.write_text(_PATTERN_TEMPLATE, encoding="utf-8")

    assert link_issue.main([str(pattern_file), "tarrragon/claude#42"]) == 0
    assert link_issue.main([str(pattern_file), "tarrragon/claude#77"]) == 0

    content = pattern_file.read_text(encoding="utf-8")
    assert content.count("| canonical_issue |") == 1
    assert "tarrragon/claude#77" in content
    assert "tarrragon/claude#42" not in content


def test_link_pattern_not_found_errors(monkeypatch, capsys):
    """不存在的 error-pattern → 降級 exit code + stderr 提示。"""
    _patched_link_env(monkeypatch)
    rc = link_issue.main(["NONEXISTENT-999", "tarrragon/claude#1"])
    assert rc == gh_common.EXIT_DEGRADED
    assert "找不到 error-pattern" in capsys.readouterr().err


def test_link_degraded_gh_not_installed(monkeypatch, capsys, tmp_path):
    """gh 未安裝 → 降級不寫檔。"""
    monkeypatch.setattr(gh_common.shutil, "which", lambda _: None)
    pattern_file = tmp_path / "PC-099-example.md"
    pattern_file.write_text(_PATTERN_TEMPLATE, encoding="utf-8")

    rc = link_issue.main([str(pattern_file), "tarrragon/claude#42"])
    assert rc == gh_common.EXIT_DEGRADED
    assert "未安裝" in capsys.readouterr().err
    # 降級時未寫入 canonical_issue
    assert "canonical_issue" not in pattern_file.read_text(encoding="utf-8")


# --- fix-status 命令 ---

_BODY_WITH_MATRIX = (
    "壞 change 描述\n\n"
    "<!-- fix-matrix -->\n"
    "| consumer | status |\n"
    "|----------|--------|\n"
    "| V1 | fixed |\n"
    "| APP | pending |\n"
    "<!-- /fix-matrix -->\n"
)


def _patched_fix_env(monkeypatch):
    """fix-status 共用前置：gh 已裝已登入。"""
    monkeypatch.setattr(gh_common, "check_gh_available", lambda: True)
    monkeypatch.setattr(gh_common, "check_gh_authenticated", lambda: True)


def test_fix_status_view_parses_matrix(monkeypatch, capsys):
    """view：gh issue view 取含矩陣 body → 解析並印各 consumer 狀態。"""
    _patched_fix_env(monkeypatch)
    payload = '{"body": %s}' % json.dumps(_BODY_WITH_MATRIX)
    with mock.patch.object(
        fix_status.subprocess, "run", return_value=_completed(stdout=payload)
    ):
        rc = fix_status.main(["tarrragon/claude#42"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "| V1 | fixed |" in out
    assert "| APP | pending |" in out


def test_fix_status_mark_fixed_updates_consumer(monkeypatch, tmp_path):
    """mark-fixed：本 consumer（APP）由 pending 更新為 fixed 並走 issue edit 回寫。"""
    _patched_fix_env(monkeypatch)
    monkeypatch.setattr(fix_status, "get_git_toplevel", lambda: "/x/book_overview_app")

    captured = {}

    def fake_run(args, *a, **k):
        if args[:3] == ["gh", "issue", "view"]:
            return _completed(stdout='{"body": %s}' % json.dumps(_BODY_WITH_MATRIX))
        if args[:3] == ["gh", "issue", "edit"]:
            body_file = args[args.index("--body-file") + 1]
            captured["body"] = Path(body_file).read_text(encoding="utf-8")
            return _completed(stdout="edited\n")
        return _completed()

    with mock.patch.object(fix_status.subprocess, "run", side_effect=fake_run):
        rc = fix_status.main(["tarrragon/claude#42", "--mark-fixed"])
    assert rc == 0
    # APP 由 pending → fixed，V1 既有 fixed 保留，不新增重複列
    assert "| APP | fixed |" in captured["body"]
    assert captured["body"].count("| APP |") == 1
    assert "| V1 | fixed |" in captured["body"]


def test_fix_status_mark_fixed_initializes_when_absent(monkeypatch):
    """mark-fixed：body 無矩陣時初始化矩陣並寫入本 consumer 列。"""
    _patched_fix_env(monkeypatch)
    monkeypatch.setattr(fix_status, "get_git_toplevel", lambda: "/x/book_overview_v1")

    captured = {}

    def fake_run(args, *a, **k):
        if args[:3] == ["gh", "issue", "view"]:
            return _completed(stdout='{"body": "純描述無矩陣"}')
        if args[:3] == ["gh", "issue", "edit"]:
            body_file = args[args.index("--body-file") + 1]
            captured["body"] = Path(body_file).read_text(encoding="utf-8")
            return _completed(stdout="edited\n")
        return _completed()

    with mock.patch.object(fix_status.subprocess, "run", side_effect=fake_run):
        rc = fix_status.main(["tarrragon/claude#7", "--mark-fixed"])
    assert rc == 0
    body = captured["body"]
    assert fix_status.MATRIX_BEGIN in body and fix_status.MATRIX_END in body
    assert "| V1 | fixed |" in body
    assert "純描述無矩陣" in body  # 既有內文保留


def test_fix_status_degraded_gh_not_installed(monkeypatch, capsys):
    """gh 未安裝 → 降級 exit 3，不嘗試讀 issue。"""
    monkeypatch.setattr(gh_common.shutil, "which", lambda _: None)
    rc = fix_status.main(["tarrragon/claude#42"])
    assert rc == gh_common.EXIT_DEGRADED
    assert "未安裝" in capsys.readouterr().err


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
