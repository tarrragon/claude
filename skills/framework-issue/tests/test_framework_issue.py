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
import fix_version  # noqa: E402
import close_issue  # noqa: E402


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


def test_create_body_includes_env_info(monkeypatch):
    """create body 一律附加環境資訊區段（OS / Claude Code 版本 / Python 版本）。"""
    monkeypatch.setattr(gh_common, "check_gh_available", lambda: True)
    monkeypatch.setattr(gh_common, "check_gh_authenticated", lambda: True)
    monkeypatch.setattr(create_issue, "get_os_info", lambda: "macOS-Darwin")
    monkeypatch.setattr(create_issue, "get_claude_code_version", lambda: "1.2.3")
    monkeypatch.setattr(create_issue, "get_python_version", lambda: "3.12.0")
    with mock.patch.object(
        gh_common.subprocess, "run", return_value=_completed(stdout="issue-url\n")
    ) as run:
        rc = create_issue.main(["--title", "T", "--body", "原始描述"])
    assert rc == 0
    called = run.call_args.args[0]
    body = called[called.index("--body") + 1]
    assert create_issue.ENV_INFO_BEGIN in body and create_issue.ENV_INFO_END in body
    assert "原始描述" in body
    assert "- OS: macOS-Darwin" in body
    assert "- Claude Code 版本: 1.2.3" in body
    assert "- Python 版本: 3.12.0" in body


def test_create_body_env_info_when_body_empty(monkeypatch):
    """body 未提供時仍附加環境資訊區段（不因空 body 而省略 --body）。"""
    monkeypatch.setattr(gh_common, "check_gh_available", lambda: True)
    monkeypatch.setattr(gh_common, "check_gh_authenticated", lambda: True)
    with mock.patch.object(
        gh_common.subprocess, "run", return_value=_completed(stdout="issue-url\n")
    ) as run:
        rc = create_issue.main(["--title", "T"])
    assert rc == 0
    called = run.call_args.args[0]
    assert "--body" in called
    body = called[called.index("--body") + 1]
    assert create_issue.ENV_INFO_BEGIN in body


def test_create_env_info_degrades_to_unknown_on_collection_failure(monkeypatch):
    """任一環境資訊收集項失敗時降級為 unknown，不阻擋 issue 建立。"""
    monkeypatch.setattr(gh_common, "check_gh_available", lambda: True)
    monkeypatch.setattr(gh_common, "check_gh_authenticated", lambda: True)

    def _boom():
        raise OSError("boom")

    monkeypatch.setattr(create_issue.platform, "system", _boom)
    monkeypatch.setattr(create_issue.platform, "python_version", _boom)
    with mock.patch.object(
        create_issue.subprocess, "run", side_effect=OSError("claude not found")
    ):
        info = create_issue.collect_env_info()
    assert info["OS"] == create_issue.UNKNOWN
    assert info["Claude Code 版本"] == create_issue.UNKNOWN
    assert info["Python 版本"] == create_issue.UNKNOWN


def test_create_claude_version_degrades_on_nonzero_exit(monkeypatch):
    """`claude --version` 回傳非零 exit code 時降級為 unknown。"""
    with mock.patch.object(
        create_issue.subprocess, "run", return_value=_completed(returncode=1)
    ):
        assert create_issue.get_claude_code_version() == create_issue.UNKNOWN


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


# --- fix-version 命令 ---

_BODY_WITH_VERSIONS = (
    "壞 change 描述\n\n"
    "<!-- fix-versions -->\n"
    "| version | date | summary |\n"
    "|---------|------|---------|\n"
    "| 2.19.0 | 2026-07-01 | 第一類徵狀 |\n"
    "<!-- /fix-versions -->\n"
)


def _patched_fix_version_env(monkeypatch):
    """fix-version 共用前置：gh 已裝已登入。"""
    monkeypatch.setattr(gh_common, "check_gh_available", lambda: True)
    monkeypatch.setattr(gh_common, "check_gh_authenticated", lambda: True)


def _fake_run_factory(body: str, captured: dict):
    """組裝一個 fake subprocess.run：view 回傳指定 body、edit 擷取回寫內容。"""

    def fake_run(args, *a, **k):
        if args[:3] == ["gh", "issue", "view"]:
            return _completed(stdout='{"body": %s}' % json.dumps(body))
        if args[:3] == ["gh", "issue", "edit"]:
            body_file = args[args.index("--body-file") + 1]
            captured["body"] = Path(body_file).read_text(encoding="utf-8")
            return _completed(stdout="edited\n")
        if args[:3] == ["gh", "issue", "close"]:
            captured["close_args"] = args
            return _completed(stdout="closed\n")
        return _completed()

    return fake_run


def test_fix_version_marks_explicit_version(monkeypatch):
    """明確傳入 --version/--date 時直接採用，不讀 .claude/VERSION。"""
    _patched_fix_version_env(monkeypatch)
    captured = {}
    with mock.patch.object(
        fix_version.subprocess,
        "run",
        side_effect=_fake_run_factory("純描述無註記", captured),
    ):
        rc = fix_version.main(
            [
                "tarrragon/claude#42",
                "--version", "2.20.0",
                "--summary", "修正 XXX",
                "--date", "2026-08-05",
            ]
        )
    assert rc == 0
    body = captured["body"]
    assert fix_version.VERSIONS_BEGIN in body and fix_version.VERSIONS_END in body
    assert "| 2.20.0 | 2026-08-05 | 修正 XXX |" in body
    assert "純描述無註記" in body  # 既有內文保留


def test_fix_version_idempotent_same_version_updates_not_duplicates(monkeypatch):
    """重複標記同版本號為更新既有列（覆蓋日期/摘要），不新增重複列。"""
    _patched_fix_version_env(monkeypatch)
    captured = {}
    with mock.patch.object(
        fix_version.subprocess,
        "run",
        side_effect=_fake_run_factory(_BODY_WITH_VERSIONS, captured),
    ):
        rc = fix_version.main(
            [
                "tarrragon/claude#42",
                "--version", "2.19.0",
                "--summary", "第一類徵狀（補充說明）",
                "--date", "2026-08-05",
            ]
        )
    assert rc == 0
    body = captured["body"]
    assert body.count("| 2.19.0 |") == 1
    assert "| 2.19.0 | 2026-08-05 | 第一類徵狀（補充說明） |" in body


def test_fix_version_defaults_from_framework_version_file(monkeypatch):
    """--version 省略時讀取本地 .claude/VERSION 作為版本號。"""
    _patched_fix_version_env(monkeypatch)
    monkeypatch.setattr(fix_version, "read_framework_version", lambda: "9.9.9")
    captured = {}
    with mock.patch.object(
        fix_version.subprocess,
        "run",
        side_effect=_fake_run_factory("純描述無註記", captured),
    ):
        rc = fix_version.main(
            [
                "tarrragon/claude#42",
                "--summary", "修正 YYY",
                "--date", "2026-08-05",
            ]
        )
    assert rc == 0
    assert "| 9.9.9 | 2026-08-05 | 修正 YYY |" in captured["body"]


def test_fix_version_degraded_when_version_file_missing(monkeypatch, capsys):
    """--version 省略且讀取 .claude/VERSION 失敗 → 降級 exit 3，提示可改用 --version。"""
    _patched_fix_version_env(monkeypatch)

    def _boom():
        raise OSError("VERSION 檔不存在")

    monkeypatch.setattr(fix_version, "read_framework_version", _boom)
    rc = fix_version.main(["tarrragon/claude#42", "--summary", "修正 ZZZ"])
    assert rc == gh_common.EXIT_DEGRADED
    assert "版本號" in capsys.readouterr().err


def test_fix_version_degraded_gh_not_installed(monkeypatch, capsys):
    """gh 未安裝 → 降級 exit 3，不嘗試讀 issue。"""
    monkeypatch.setattr(gh_common.shutil, "which", lambda _: None)
    rc = fix_version.main(["tarrragon/claude#42", "--summary", "修正 X"])
    assert rc == gh_common.EXIT_DEGRADED
    assert "未安裝" in capsys.readouterr().err


# --- close 命令 ---

def _patched_close_env(monkeypatch):
    """close 共用前置：gh 已裝已登入。"""
    monkeypatch.setattr(gh_common, "check_gh_available", lambda: True)
    monkeypatch.setattr(gh_common, "check_gh_authenticated", lambda: True)


def test_close_succeeds_when_fix_versions_present(monkeypatch):
    """已有 fix-versions 註記 → 前置檢查通過並執行 gh issue close。"""
    _patched_close_env(monkeypatch)
    captured = {}
    with mock.patch.object(
        fix_version.subprocess,
        "run",
        side_effect=_fake_run_factory(_BODY_WITH_VERSIONS, captured),
    ):
        rc = close_issue.main(["tarrragon/claude#42"])
    assert rc == 0
    assert captured["close_args"][:3] == ["gh", "issue", "close"]
    assert "42" in captured["close_args"]  # 正規化為純數字傳給 gh


def test_close_degraded_when_no_fix_versions(monkeypatch, capsys):
    """無 fix-versions 註記 → exit 3，提示先 sync-push 並用 fix-version 註記。"""
    _patched_close_env(monkeypatch)
    captured = {}
    with mock.patch.object(
        fix_version.subprocess,
        "run",
        side_effect=_fake_run_factory("純描述無註記", captured),
    ):
        rc = close_issue.main(["tarrragon/claude#42"])
    assert rc == gh_common.EXIT_DEGRADED
    err = capsys.readouterr().err
    assert "尚無修復版本號註記" in err
    assert "fix-version" in err
    assert "close_args" not in captured  # 未嘗試關閉


def test_close_degraded_gh_not_installed(monkeypatch, capsys):
    """gh 未安裝 → 降級 exit 3，不嘗試讀 issue。"""
    monkeypatch.setattr(gh_common.shutil, "which", lambda _: None)
    rc = close_issue.main(["tarrragon/claude#42"])
    assert rc == gh_common.EXIT_DEGRADED
    assert "未安裝" in capsys.readouterr().err


def test_fix_version_still_works_after_close(monkeypatch):
    """close 後（body 仍含既有 fix-versions 註記）可再追加新版本號，無需重開。"""
    _patched_close_env(monkeypatch)
    captured = {}
    with mock.patch.object(
        fix_version.subprocess,
        "run",
        side_effect=_fake_run_factory(_BODY_WITH_VERSIONS, captured),
    ):
        rc = fix_version.main(
            [
                "tarrragon/claude#42",
                "--version", "2.21.0",
                "--summary", "close 後發現的新徵狀",
                "--date", "2026-08-06",
            ]
        )
    assert rc == 0
    body = captured["body"]
    assert "| 2.19.0 | 2026-07-01 | 第一類徵狀 |" in body  # 既有版本保留
    assert "| 2.21.0 | 2026-08-06 | close 後發現的新徵狀 |" in body


# --- issue ref 正規化（owner/repo#N、#N、純 N 三形態，issue #64 重現） ---


def test_normalize_issue_ref_accepts_three_forms():
    """owner/repo#N、#N、純 N 三種形態皆正規化為純數字字串。"""
    assert gh_common.normalize_issue_ref("tarrragon/claude#64") == "64"
    assert gh_common.normalize_issue_ref("#64") == "64"
    assert gh_common.normalize_issue_ref("64") == "64"


def test_normalize_issue_ref_rejects_mismatched_repo():
    """owner/repo 前綴與目標 repo 不符時拋 ValueError，不靜默改號。"""
    with pytest.raises(ValueError, match="不符"):
        gh_common.normalize_issue_ref("other/repo#64")


def test_normalize_issue_ref_rejects_invalid_format():
    """三種形態皆不符時拋 ValueError。"""
    with pytest.raises(ValueError, match="無法識別"):
        gh_common.normalize_issue_ref("not-a-ref")


def test_fix_version_accepts_hash_form(monkeypatch):
    """fix-version 對 #64 形態正規化為 64 後成功執行。"""
    _patched_fix_version_env(monkeypatch)
    captured = {}
    with mock.patch.object(
        fix_version.subprocess,
        "run",
        side_effect=_fake_run_factory("純描述無註記", captured),
    ):
        rc = fix_version.main(
            ["#64", "--version", "2.20.0", "--summary", "修正 XXX", "--date", "2026-08-05"]
        )
    assert rc == 0
    assert "| 2.20.0 | 2026-08-05 | 修正 XXX |" in captured["body"]


def test_fix_version_accepts_bare_number_form(monkeypatch):
    """fix-version 對純數字 64 形態直接使用不需正規化。"""
    _patched_fix_version_env(monkeypatch)
    captured = {}
    with mock.patch.object(
        fix_version.subprocess,
        "run",
        side_effect=_fake_run_factory("純描述無註記", captured),
    ):
        rc = fix_version.main(
            ["64", "--version", "2.20.0", "--summary", "修正 XXX", "--date", "2026-08-05"]
        )
    assert rc == 0
    assert "| 2.20.0 | 2026-08-05 | 修正 XXX |" in captured["body"]


def test_fix_version_degraded_when_repo_mismatched(monkeypatch, capsys):
    """fix-version 對 owner/repo#N 但 repo 與框架不符時降級 exit 3，禁止靜默改號。"""
    _patched_fix_version_env(monkeypatch)
    rc = fix_version.main(
        ["other/repo#64", "--version", "2.20.0", "--summary", "修正 XXX"]
    )
    assert rc == gh_common.EXIT_DEGRADED
    assert "不符" in capsys.readouterr().err


def test_close_accepts_hash_and_bare_number_forms(monkeypatch):
    """close 對 #42 與純數字 42 形態皆能通過前置檢查並執行 gh issue close。"""
    _patched_close_env(monkeypatch)
    for ref in ("#42", "42"):
        captured = {}
        with mock.patch.object(
            fix_version.subprocess,
            "run",
            side_effect=_fake_run_factory(_BODY_WITH_VERSIONS, captured),
        ):
            rc = close_issue.main([ref])
        assert rc == 0
        assert "42" in captured["close_args"]


def test_close_degraded_when_repo_mismatched(monkeypatch, capsys):
    """close 對 owner/repo#N 但 repo 與框架不符時降級 exit 3，不嘗試讀 issue。"""
    _patched_close_env(monkeypatch)
    rc = close_issue.main(["other/repo#42"])
    assert rc == gh_common.EXIT_DEGRADED
    assert "不符" in capsys.readouterr().err


def test_fix_status_accepts_hash_and_bare_number_forms(monkeypatch, capsys):
    """fix-status view 對 #42 與純數字 42 形態皆能正確解析矩陣。"""
    _patched_fix_env(monkeypatch)
    payload = '{"body": %s}' % json.dumps(_BODY_WITH_MATRIX)
    for ref in ("#42", "42"):
        with mock.patch.object(
            fix_status.subprocess, "run", return_value=_completed(stdout=payload)
        ):
            rc = fix_status.main([ref])
        assert rc == 0
        assert "| V1 | fixed |" in capsys.readouterr().out


def test_fix_status_degraded_when_repo_mismatched(monkeypatch, capsys):
    """fix-status 對 owner/repo#N 但 repo 與框架不符時降級 exit 3。"""
    _patched_fix_env(monkeypatch)
    rc = fix_status.main(["other/repo#42"])
    assert rc == gh_common.EXIT_DEGRADED
    assert "不符" in capsys.readouterr().err


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
