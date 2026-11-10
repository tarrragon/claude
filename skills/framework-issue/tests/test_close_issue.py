"""close_issue.py 測試：completed 與 not planned 兩種關閉的前置條件與追溯載體。

completed（或省略 --reason）沿用修復版本表閘門；not planned 不經修復版本表，
改以 --comment 判定理由 + 工具自動附上的判定依據框架版本留下追溯。
"""

import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import close_issue  # noqa: E402
import fix_version  # noqa: E402
import gh_common  # noqa: E402

_BODY_WITHOUT_VERSIONS = "壞 change 描述，無修復版本表"
_BODY_WITH_VERSIONS = (
    "壞 change 描述\n\n"
    "<!-- fix-versions -->\n"
    "| version | date | summary |\n"
    "|---------|------|---------|\n"
    "| 2.19.0 | 2026-07-01 | 第一類徵狀 |\n"
    "<!-- /fix-versions -->\n"
)


@pytest.fixture(autouse=True)
def _gh_ready(monkeypatch):
    monkeypatch.setattr(gh_common, "check_gh_available", lambda: True)
    monkeypatch.setattr(gh_common, "check_gh_authenticated", lambda: True)


@pytest.fixture
def version_file(tmp_path, monkeypatch):
    path = tmp_path / "VERSION"
    path.write_text("3.1.0\n", encoding="utf-8")
    monkeypatch.setattr(
        close_issue, "read_framework_version", lambda: fix_version.read_framework_version(path)
    )
    return path


def _run_close(argv, body):
    calls = {"view": 0, "edit": 0}

    def fake_run(args, *a, **k):
        if args[:3] == ["gh", "issue", "view"]:
            calls["view"] += 1
            return subprocess.CompletedProcess(args, 0, stdout=json.dumps({"body": body}), stderr="")
        if args[:3] == ["gh", "issue", "edit"]:
            calls["edit"] += 1
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        if args[:3] == ["gh", "issue", "close"]:
            calls["close_args"] = args
            return subprocess.CompletedProcess(args, 0, stdout="closed\n", stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    with mock.patch.object(fix_version.subprocess, "run", side_effect=fake_run):
        rc = close_issue.main(argv)
    return rc, calls


def _comment_of(close_args):
    return close_args[close_args.index("--comment") + 1]


class TestCompleted:
    @pytest.mark.parametrize("reason_args", [[], ["--reason", "completed"]])
    def test_rejected_without_fix_versions(self, capsys, reason_args):
        rc, calls = _run_close(["42", *reason_args], _BODY_WITHOUT_VERSIONS)

        assert rc == gh_common.EXIT_DEGRADED
        assert "close_args" not in calls
        err = capsys.readouterr().err
        assert "尚無修復版本號註記" in err
        assert '--reason "not planned"' in err

    def test_passes_with_fix_versions(self):
        rc, calls = _run_close(["42", "--reason", "completed"], _BODY_WITH_VERSIONS)

        assert rc == 0
        assert calls["close_args"][:4] == ["gh", "issue", "close", "42"]


class TestNotPlanned:
    def test_passes_without_fix_versions_and_records_judged_version(self, version_file):
        rc, calls = _run_close(
            ["42", "--reason", "not planned", "--comment", "非框架問題"], _BODY_WITHOUT_VERSIONS
        )

        assert rc == 0
        close_args = calls["close_args"]
        assert close_args[close_args.index("--reason") + 1] == "not planned"
        comment = _comment_of(close_args)
        assert comment.startswith("非框架問題")
        assert comment.endswith("不修關閉，判定依據框架版本：3.1.0")

    def test_does_not_read_or_edit_fix_versions(self, version_file):
        """不修關閉不經修復版本表：不讀 body、不寫 body。"""
        _, calls = _run_close(
            ["42", "--reason", "not planned", "--comment", "過時"], _BODY_WITHOUT_VERSIONS
        )

        assert calls["view"] == 0
        assert calls["edit"] == 0

    @pytest.mark.parametrize("comment_args", [[], ["--comment", "   "]])
    def test_rejected_without_reason_text(self, capsys, version_file, comment_args):
        rc, calls = _run_close(["42", "--reason", "not planned", *comment_args], _BODY_WITH_VERSIONS)

        assert rc == gh_common.EXIT_DEGRADED
        assert "close_args" not in calls
        assert "判定理由" in capsys.readouterr().err

    def test_rejected_when_version_unreadable(self, capsys, tmp_path, monkeypatch):
        missing = tmp_path / "no-such-VERSION"
        monkeypatch.setattr(
            close_issue, "read_framework_version", lambda: fix_version.read_framework_version(missing)
        )

        rc, calls = _run_close(
            ["42", "--reason", "not planned", "--comment", "重複"], _BODY_WITHOUT_VERSIONS
        )

        assert rc == gh_common.EXIT_DEGRADED
        assert "close_args" not in calls
        assert ".claude/VERSION" in capsys.readouterr().err
