#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
並行派發驗證 Hook 單元測試

測試 parallel-dispatch-verification-hook.py 的所有功能。

結構：
- Fixtures 配置
- 場景測試（1-6）
- 邊界條件測試（A-E）
- 否定測試（NAC）
- 異常處理測試（E1-E4）
- 輔助函式測試
"""

import importlib.util
import json
import logging
import subprocess
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open
from typing import Any, Optional

import pytest


# ============================================================================
# Hook 模組動態導入
# ============================================================================

def load_hook_module():
    """動態載入 parallel-dispatch-verification-hook.py 模組"""
    hook_path = Path(__file__).parent.parent / "parallel-dispatch-verification-hook.py"
    spec = importlib.util.spec_from_file_location("parallel_dispatch_verification_hook", hook_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["parallel_dispatch_verification_hook"] = module
    spec.loader.exec_module(module)
    return module

# 預先載入 hook 模組
hook_module = load_hook_module()


# ============================================================================
# Fixtures 配置
# ============================================================================


@pytest.fixture
def mock_stdin(monkeypatch):
    """Mock stdin 以提供 PostToolUse 格式的 JSON 輸入"""
    def set_stdin_data(data: dict) -> None:
        stdin_text = json.dumps(data)
        monkeypatch.setattr('sys.stdin', StringIO(stdin_text))
    return set_stdin_data


@pytest.fixture
def temp_ticket_file(tmp_path, monkeypatch):
    """建立臨時 Ticket 檔案（含有效的 YAML frontmatter）"""
    def create_ticket(
        ticket_id: str = "0.1.0-W41-002",
        where_files: Optional[list[str]] = None
    ) -> Path:
        # 建立 Ticket 目錄結構
        version = ticket_id.split("-")[0]
        ticket_dir = tmp_path / "docs" / "work-logs" / f"v{version}" / "tickets"
        ticket_dir.mkdir(parents=True, exist_ok=True)

        ticket_file = ticket_dir / f"{ticket_id}.md"

        # 構建 YAML frontmatter
        frontmatter = "---\n"
        frontmatter += f"id: {ticket_id}\n"
        frontmatter += "title: Test Ticket\n"
        frontmatter += "type: IMP\n"
        frontmatter += "status: completed\n"

        if where_files is not None and len(where_files) > 0:
            frontmatter += "where:\n"
            frontmatter += "  layer: test\n"
            frontmatter += "  files:\n"
            for file in where_files:
                # 確保 YAML 列表格式正確
                frontmatter += f"  - {file}\n"

        frontmatter += "---\n\n"
        frontmatter += "# Test Content\n"

        ticket_file.write_text(frontmatter, encoding='utf-8')

        # Mock get_project_root 返回 tmp_path
        monkeypatch.setattr(
            hook_module,
            'get_project_root',
            lambda: tmp_path
        )

        return ticket_file

    return create_ticket


@pytest.fixture
def mock_git_diff(monkeypatch):
    """Mock subprocess.run 以控制 git diff 的輸出"""
    def setup_git_mock(
        output: str = "",
        exit_code: int = 0,
        exception: Optional[Exception] = None
    ) -> None:
        def mock_run(*args, **kwargs):
            if exception:
                raise exception

            result = MagicMock()
            result.returncode = exit_code
            result.stdout = output
            result.stderr = ""
            return result

        monkeypatch.setattr('subprocess.run', mock_run)

    return setup_git_mock


@pytest.fixture
def temp_log_dir(tmp_path, monkeypatch):
    """建立臨時日誌目錄"""
    log_dir = tmp_path / ".claude" / "hook-logs" / "parallel-dispatch-verification"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Mock 日誌初始化函式
    def mock_setup_logging(hook_name: str) -> logging.Logger:
        logger = logging.getLogger(hook_name)
        # 清除已有的 handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

        # 僅添加 StreamHandler
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        return logger

    monkeypatch.setattr(
        hook_module,
        'setup_hook_logging',
        mock_setup_logging
    )

    return log_dir


# ============================================================================
# 測試類
# ============================================================================


class TestParallelDispatchVerificationHook:
    """並行派發驗證 Hook 單元測試"""

    # 場景測試已移至 Phase 4 集成測試
    # 核心邏輯單位測試足以驗證功能


    # ==========================================================================
    # 輔助函式測試
    # ==========================================================================

    @pytest.mark.parametrize("input_path,expected", [
        ("./ui/lib/x.dart", "ui/lib/x.dart"),
        ("ui/lib/x.dart", "ui/lib/x.dart"),
        ("ui/lib/x.dart/", "ui/lib/x.dart"),
        ("./ui/lib/x.dart/", "ui/lib/x.dart"),
        ("UI/LIB/X.DART", "ui/lib/x.dart"),
        ("ui\\lib\\x.dart", "ui/lib/x.dart"),
        ("./ui\\LIB/X.DART/", "ui/lib/x.dart"),
        ("//ui//lib//x.dart", "/ui/lib/x.dart"),  # 絕對路徑保持前綴 /
    ])
    def test_normalize_path_all_cases(self, input_path, expected):
        """normalize_path 函式的規範化規則驗證"""
        result = hook_module.normalize_path(input_path)
        assert result == expected, f"normalize_path('{input_path}') = '{result}', expected '{expected}'"


    @pytest.mark.parametrize("where_files,git_changed,expected_missing", [
        (["a.py", "b.py"], ["a.py", "b.py", "c.py"], []),  # 全部匹配
        (["a.py", "b.py", "c.py"], ["a.py", "b.py"], ["c.py"]),  # 部分缺失
        (["a.py", "b.py"], ["c.py", "d.py"], ["a.py", "b.py"]),  # 全部缺失
        ([], ["a.py", "b.py"], []),  # 空 where.files
        (["a.py"], ["a.py"], []),  # 單一檔案匹配
        (["a.py"], ["b.py"], ["a.py"]),  # 單一檔案缺失
    ])
    def test_find_missing_files_logic(self, where_files, git_changed, expected_missing):
        """find_missing_files 函式的集合比對邏輯"""
        result = hook_module.find_missing_files(where_files, git_changed)
        assert sorted(result) == sorted(expected_missing)


    @pytest.mark.parametrize("input_data,expected", [
        (
            {
                "tool_name": "Bash",
                "tool_input": {"command": "ticket track complete 0.1.0-W41-002"},
                "tool_response": {"stdout": "[OK] 已完成 Ticket", "exit_code": 0}
            },
            True
        ),
        (
            {
                "tool_name": "Bash",
                "tool_input": {"command": "git commit"},
                "tool_response": {"stdout": "success", "exit_code": 0}
            },
            False  # 非 ticket complete
        ),
        (
            {
                "tool_name": "Bash",
                "tool_input": {"command": "ticket track complete 0.1.0-W41-002"},
                "tool_response": {"stdout": "failed", "exit_code": 1}
            },
            False  # exit code != 0
        ),
    ])
    def test_is_ticket_complete_success(self, input_data, expected):
        """is_ticket_complete_success 函式的觸發條件驗證"""
        result = hook_module.is_ticket_complete_success(input_data)
        assert result == expected


# ============================================================================
# 0.5.0-W1-270.8：完成命令辨識（finish 別名）
# ============================================================================

def _run_main_with(input_data, where_files, git_changed):
    """以 patch 取代外部依賴執行 main()，回傳 (rc, stdout_payload, where_mock)。"""
    out = StringIO()
    with patch.object(hook_module, "read_json_from_stdin", return_value=input_data), \
         patch.object(hook_module, "is_subagent_environment", return_value=False), \
         patch.object(hook_module, "get_project_root", return_value=Path("/nonexistent")), \
         patch.object(hook_module, "read_ticket_where_files",
                      return_value=where_files) as where_mock, \
         patch.object(hook_module, "get_git_changed_files", return_value=git_changed), \
         patch("sys.stdout", out):
        rc = hook_module.main()
    return rc, json.loads(out.getvalue()), where_mock


def _payload(command):
    return {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_response": {"stdout": "[OK] 已完成 Ticket", "exit_code": 0},
    }


class TestCompleteCommandRecognition:
    """E2：finish 觸發原本對 complete 的處理（缺失檔案警告）"""

    def test_finish_triggers_missing_file_warning(self):
        rc, payload, where_mock = _run_main_with(
            _payload("ticket track finish 0.1.0-W41-002"), ["a.py"], [])
        assert rc == 0
        assert where_mock.call_args[0][0] == "0.1.0-W41-002"
        ctx = payload["hookSpecificOutput"]["additionalContext"]
        assert "  - a.py" in ctx.splitlines()

    def test_batch_complete_recognized(self):
        assert hook_module.is_ticket_complete_success(
            _payload("ticket track batch-complete 0.1.0-W41-002")) is True

    def test_quoted_literal_not_recognized(self):
        assert hook_module.is_ticket_complete_success(
            _payload("echo 'ticket track complete 0.1.0-W41-002'")) is False

    def test_unparseable_command_fail_open(self):
        rc, payload, where_mock = _run_main_with(
            _payload("echo 'ticket track finish 0.1.0-W41-002"), ["a.py"], [])
        assert rc == 0
        assert "additionalContext" not in payload["hookSpecificOutput"]
        where_mock.assert_not_called()


REAL_KEYS = {"stderr": "", "interrupted": False, "isImage": False, "noOutputExpected": False}


def _real_payload(command, stdout="[OK] 已完成 Ticket", **extra):
    """真實 payload 形狀：五個鍵、無 exit_code"""
    resp = dict(REAL_KEYS, stdout=stdout, **extra)
    return {"tool_name": "Bash", "tool_input": {"command": command},
            "tool_response": resp}


class TestRealPayloadShape:
    """E2：真實形狀（無 exit_code）的成功命令須觸發缺失檔案警告"""

    def test_real_payload_triggers_missing_file_warning(self):
        rc, payload, where_mock = _run_main_with(
            _real_payload("ticket track complete 0.1.0-W41-002"), ["a.py"], [])
        assert rc == 0
        assert where_mock.call_args[0][0] == "0.1.0-W41-002"
        ctx = payload["hookSpecificOutput"]["additionalContext"]
        assert "  - a.py" in ctx.splitlines()

    def test_real_payload_failure_not_triggered(self):
        rc, payload, where_mock = _run_main_with(
            _real_payload("ticket track complete X-NONE; echo rc=$?", stdout="[Error] x"),
            ["a.py"], [])
        assert rc == 0
        where_mock.assert_not_called()

    def test_unmasked_recomplete_outside_window_not_triggered(self):
        """E1：未遮蔽、stdout「已完成於 ...」，completed_at 窗外不觸發、窗內觸發"""
        for verdict, triggered in ((False, False), (True, True)):
            with patch.object(hook_module, "make_completed_verifier",
                              return_value=lambda v=verdict: v):
                rc, _p, where_mock = _run_main_with(
                    _real_payload("ticket track complete 0.1.0-W41-002",
                                  stdout="0.1.0-W41-002 已完成於 2026-10-15T11:52:55"),
                    ["a.py"], [])
            assert rc == 0
            assert (where_mock.call_count == 1) is triggered

    @pytest.mark.parametrize("command", [
        "ticket track finish 0.1.0-W41-002 > log 2>&1; echo rc=$?",
        "out=$(ticket track complete 0.1.0-W41-002 2>&1); rc=$?",
    ])
    def test_masked_form_follows_ticket_state(self, command):
        """E1：stdout 僅 rc=0 時，票面剛完成才觸發驗證；票面未完成（或舊票）不觸發"""
        for verdict, triggered in ((True, True), (False, False)):
            with patch.object(hook_module, "make_completed_verifier",
                              return_value=lambda v=verdict: v):
                rc, _payload_out, where_mock = _run_main_with(
                    _real_payload(command, stdout="rc=0"), ["a.py"], [])
            assert rc == 0
            assert (where_mock.call_count == 1) is triggered

    def test_interrupted_not_triggered(self):
        data = _real_payload("ticket track complete 0.1.0-W41-002", interrupted=True)
        assert hook_module.is_ticket_complete_success(data) is False

    def test_legacy_exit_code_compat(self):
        for code, expected in ((0, True), (75, True), (1, False)):
            data = _real_payload("ticket track complete 0.1.0-W41-002", exit_code=code)
            assert hook_module.is_ticket_complete_success(data) is expected

    @pytest.mark.parametrize("resp", ["[OK] 已完成", None, 7])
    def test_non_dict_response_fail_open(self, resp):
        data = _real_payload("ticket track complete 0.1.0-W41-002")
        data["tool_response"] = resp
        assert hook_module.is_ticket_complete_success(data) is False


# ============================================================================
# 0.5.0-W1-279.3：子任務票號擷取 + 以票相關 commit 範圍為比對基準
# ============================================================================

SUB_ID = "0.1.0-W41-002.1"
DEEP_ID = "0.1.0-W41-002.1.2"


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True, text=True)


def _commit(repo, files, message):
    for name in files:
        f = repo / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(f"{message}\n{name}\n", encoding="utf-8")
        _git(repo, "add", name)
    _git(repo, "commit", "-m", message)


@pytest.fixture
def repo(tmp_path):
    """真實 git fixture：base、父票 commit、子任務票 commit、merge commit"""
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "t")
    _git(r, "config", "commit.gpgsign", "false")
    _commit(r, ["base.txt"], "base")
    _commit(r, ["parent_only.py"], "fix(0.1.0-W41-002): parent work")
    _git(r, "checkout", "-q", "-b", "wt")
    _commit(r, ["src/a.py", "src/b.py"], f"fix({SUB_ID}): sub work")
    _git(r, "checkout", "-q", "main")
    _git(r, "merge", "--no-ff", "-m", f"merge({SUB_ID}): land", "wt")
    return r


def _run_real(command, where_files, repo):
    """main() 走真實 git；僅 patch stdin、票面讀取與專案根目錄"""
    out = StringIO()
    with patch.object(hook_module, "read_json_from_stdin",
                      return_value=_real_payload(command)), \
         patch.object(hook_module, "is_subagent_environment", return_value=False), \
         patch.object(hook_module, "get_project_root", return_value=repo), \
         patch.object(hook_module, "read_ticket_where_files",
                      return_value=where_files) as where_mock, \
         patch("sys.stdout", out):
        rc = hook_module.main()
    return rc, json.loads(out.getvalue()), where_mock


class TestSubtaskTicketIdExtraction:
    """E2：子任務票號須含完整後綴，警告對象為該子任務票"""

    @pytest.mark.parametrize("cmd,expected", [
        (f"ticket track complete {SUB_ID}", SUB_ID),
        (f"ticket track finish {DEEP_ID}", DEEP_ID),
        ("ticket track complete 0.1.0-W41-002", "0.1.0-W41-002"),
        (f"ticket track complete {SUB_ID} --as x", SUB_ID),
    ])
    def test_extract_keeps_suffix(self, cmd, expected):
        assert hook_module.extract_ticket_id(_real_payload(cmd)) == expected

    def test_extract_ignores_stdout_and_other_statements(self):
        data = _real_payload(f"echo 0.9.9-W9-9; ticket track complete {SUB_ID}",
                             stdout="[OK] 已完成 Ticket 0.8.8-W8-8")
        assert hook_module.extract_ticket_id(data) == SUB_ID

    def test_warning_target_is_subtask(self):
        rc, payload, where_mock = _run_main_with(
            _real_payload(f"ticket track complete {SUB_ID}"), ["a.py"], [])
        assert where_mock.call_args[0][0] == SUB_ID
        ctx = payload["hookSpecificOutput"]["additionalContext"]
        assert f"Ticket {SUB_ID} 完成後" in ctx


class TestCommitRangeBaseline:
    """E2：同一 git fixture 的正反對照；complete 時變更已提交（working tree 乾淨）"""

    def test_committed_where_files_no_warning(self, repo):
        rc, payload, _ = _run_real(
            f"ticket track complete {SUB_ID}", ["src/a.py", "src/b.py"], repo)
        assert rc == 0
        assert "additionalContext" not in payload["hookSpecificOutput"]

    def test_truly_missing_file_warned_and_listed(self, repo):
        rc, payload, _ = _run_real(
            f"ticket track complete {SUB_ID}",
            ["src/a.py", "src/never_touched.py"], repo)
        assert rc == 0
        ctx = payload["hookSpecificOutput"]["additionalContext"]
        lines = ctx.splitlines()
        assert "  - src/never_touched.py" in lines
        missing_block = lines[lines.index("缺失檔案（1 個）：") + 1]
        assert missing_block == "  - src/never_touched.py"

    def test_parent_does_not_absorb_subtask_commits(self, repo):
        """父票只認自己的 commit：子任務的檔案對父票而言是缺失"""
        rc, payload, _ = _run_real(
            "ticket track complete 0.1.0-W41-002",
            ["parent_only.py", "src/a.py"], repo)
        ctx = payload["hookSpecificOutput"]["additionalContext"]
        lines = ctx.splitlines()
        assert lines[lines.index("缺失檔案（1 個）：") + 1] == "  - src/a.py"

    def test_uncommitted_change_still_counted(self, repo):
        (repo / "src").mkdir(exist_ok=True)
        (repo / "base.txt").write_text("dirty\n", encoding="utf-8")
        rc, payload, _ = _run_real(
            f"ticket track complete {SUB_ID}", ["src/a.py", "base.txt"], repo)
        assert "additionalContext" not in payload["hookSpecificOutput"]

    def test_git_failure_fail_open(self, tmp_path):
        """非 git 目錄：git 命令全數失敗，仍 exit 0 不阻擋、不拋例外"""
        not_repo = tmp_path / "plain"
        not_repo.mkdir()
        rc, payload, _ = _run_real(
            f"ticket track complete {SUB_ID}", ["a.py"], not_repo)
        assert rc == 0
        assert "hookSpecificOutput" in payload

    def test_git_timeout_fail_open(self, repo):
        with patch.object(hook_module.subprocess, "run",
                          side_effect=subprocess.TimeoutExpired("git", 1)):
            rc, payload, _ = _run_real(
                f"ticket track complete {SUB_ID}", ["a.py"], repo)
        assert rc == 0


MERGE_ID = "0.1.0-W42-001"


@pytest.fixture
def merge_repo(tmp_path):
    """分支改 A，主線同期改 B，以含票號的合併 commit 併入（第二親代帶入他線變更）"""
    r = tmp_path / "merge_repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "t")
    _git(r, "config", "commit.gpgsign", "false")
    _commit(r, ["base.txt"], "base")
    _git(r, "checkout", "-q", "-b", "wt")
    _commit(r, ["src/a.py"], "feat: branch work without ticket id")
    _git(r, "checkout", "-q", "main")
    _commit(r, ["other/b.py"], "feat: mainline work without ticket id")
    _git(r, "merge", "--no-ff", "-m", f"merge({MERGE_ID}): land", "wt")
    return r


class TestMergeCommitFirstParent:
    """合併 commit 只取相對第一親代的變更，主線他線檔案不進入票相關集合"""

    def test_changed_set_excludes_mainline_file(self, merge_repo):
        import logging
        changed = hook_module.get_git_changed_files(
            merge_repo, logging.getLogger("t"), MERGE_ID)
        assert "src/a.py" in changed
        assert "other/b.py" not in changed

    def test_where_file_untouched_by_ticket_reported_missing(self, merge_repo):
        rc, payload, _ = _run_real(
            f"ticket track complete {MERGE_ID}",
            ["src/a.py", "other/b.py"], merge_repo)
        lines = payload["hookSpecificOutput"]["additionalContext"].splitlines()
        assert lines[lines.index("缺失檔案（1 個）：") + 1] == "  - other/b.py"

    def test_ordinary_commit_unchanged(self, repo):
        import logging
        changed = hook_module.get_git_changed_files(
            repo, logging.getLogger("t"), "0.1.0-W41-002")
        assert "parent_only.py" in changed


PARENT_ID = "0.1.0-W41-002"


def _run_real_meta(ticket_type, has_children, where_files, repo, ticket_id=PARENT_ID):
    """同 _run_real，另 patch 票的 type / 有無子票；回傳 (rc, payload)"""
    out = StringIO()
    with patch.object(hook_module, "read_json_from_stdin",
                      return_value=_real_payload(f"ticket track complete {ticket_id}")), \
         patch.object(hook_module, "is_subagent_environment", return_value=False), \
         patch.object(hook_module, "get_project_root", return_value=repo), \
         patch.object(hook_module, "read_ticket_where_files", return_value=where_files), \
         patch.object(hook_module, "read_ticket_type_and_children",
                      return_value=(ticket_type, has_children)), \
         patch("sys.stdout", out):
        rc = hook_module.main()
    return rc, json.loads(out.getvalue())


class TestAnaAndParentWithChildren:
    """0.5.0-W1-283：ANA 與修改落在子票的父票不誤報；無子票 IMP 漏改仍警告（同一 repo fixture）"""

    WHERE = ["parent_only.py", "src/a.py"]

    def test_ana_with_children_no_warning(self, repo):
        rc, payload = _run_real_meta("ANA", True, self.WHERE, repo)
        assert rc == 0
        assert "additionalContext" not in payload["hookSpecificOutput"]

    def test_ana_without_children_no_warning(self, repo):
        rc, payload = _run_real_meta("ANA", False, ["never.py"], repo)
        assert rc == 0
        assert "additionalContext" not in payload["hookSpecificOutput"]

    def test_imp_parent_with_children_counts_descendant_commits(self, repo):
        rc, payload = _run_real_meta("IMP", True, self.WHERE, repo)
        assert rc == 0
        assert "additionalContext" not in payload["hookSpecificOutput"]

    def test_imp_without_children_missing_still_warned(self, repo):
        rc, payload = _run_real_meta("IMP", False, self.WHERE, repo)
        lines = payload["hookSpecificOutput"]["additionalContext"].splitlines()
        assert lines[lines.index("缺失檔案（1 個）：") + 1] == "  - src/a.py"

    def test_imp_parent_with_children_truly_missing_still_warned(self, repo):
        rc, payload = _run_real_meta("IMP", True, ["parent_only.py", "never.py"], repo)
        lines = payload["hookSpecificOutput"]["additionalContext"].splitlines()
        assert lines[lines.index("缺失檔案（1 個）：") + 1] == "  - never.py"

    def test_descendants_flag_does_not_absorb_sibling_prefix(self, repo):
        """0.1.0-W41-0021 不是 0.1.0-W41-002 的子孫"""
        import logging
        _commit(repo, ["other.py"], "fix(0.1.0-W41-0021): unrelated")
        changed = hook_module.get_git_changed_files(
            repo, logging.getLogger("t"), PARENT_ID, include_descendants=True)
        assert "other.py" not in changed
        assert "src/a.py" in changed


class TestTicketMetaFailOpen:
    """讀取票面失敗：回 (None, False)，不拋例外，main 仍 exit 0 並照舊驗證"""

    def test_missing_ticket_returns_default(self, tmp_path):
        import logging
        assert hook_module.read_ticket_type_and_children(
            PARENT_ID, tmp_path, logging.getLogger("t")) == (None, False)

    def test_reader_exception_fail_open(self, tmp_path):
        import logging
        with patch.object(hook_module, "find_ticket_file", side_effect=OSError("boom")):
            assert hook_module.read_ticket_type_and_children(
                PARENT_ID, tmp_path, logging.getLogger("t")) == (None, False)

    def test_real_ticket_file_parsed(self, tmp_path):
        import logging
        d = tmp_path / "docs" / "work-logs" / "v0.1.0" / "tickets"
        d.mkdir(parents=True)
        (d / f"{PARENT_ID}.md").write_text(
            f"---\nid: {PARENT_ID}\ntype: ANA\nchildren:\n- {SUB_ID}\n---\n\nbody\n",
            encoding="utf-8")
        assert hook_module.read_ticket_type_and_children(
            PARENT_ID, tmp_path, logging.getLogger("t")) == ("ANA", True)

    def test_main_exit_zero_when_meta_reader_unavailable(self, repo):
        rc, payload = _run_real_meta(None, False, self.WHERE_MISSING, repo)
        assert rc == 0
        assert "additionalContext" in payload["hookSpecificOutput"]

    WHERE_MISSING = ["src/a.py"]


def _run_real_raw_where(raw_where, repo, ticket_id=SUB_ID):
    """走真實 read_ticket_where_files（僅 patch 原始 where.files 抽取）+ 真實 git"""
    out = StringIO()
    with patch.object(hook_module, "read_json_from_stdin",
                      return_value=_real_payload(f"ticket track complete {ticket_id}")), \
         patch.object(hook_module, "is_subagent_environment", return_value=False), \
         patch.object(hook_module, "get_project_root", return_value=repo), \
         patch("lib.hook_ticket.find_ticket_file", return_value=repo), \
         patch("lib.hook_ticket.parse_ticket_frontmatter",
               return_value={"where": {"files": raw_where}}), \
         patch.object(hook_module, "read_ticket_type_and_children",
                      return_value=("IMP", False)), \
         patch("sys.stdout", out):
        rc = hook_module.main()
    return rc, json.loads(out.getvalue())


def _missing_block(payload):
    lines = payload["hookSpecificOutput"]["additionalContext"].splitlines()
    start = lines.index(next(l for l in lines if l.startswith("缺失檔案（")))
    return lines[start], lines[start + 1]


class TestIntentSuffixStripping:
    """0.5.0-W1-317：where.files 的 ::write / ::read 後綴比對前剝除（同一 repo fixture 正反對照）"""

    def test_write_marked_modified_file_not_missing(self, repo):
        rc, payload = _run_real_raw_where(
            ["src/a.py::write", "src/b.py::write"], repo)
        assert rc == 0
        assert "additionalContext" not in payload["hookSpecificOutput"]

    def test_write_marked_untouched_file_still_missing(self, repo):
        rc, payload = _run_real_raw_where(
            ["src/a.py::write", "never.py::write"], repo)
        header, first = _missing_block(payload)
        assert header == "缺失檔案（1 個）："
        assert first == "  - never.py"

    def test_read_marked_not_expected_modification(self, repo):
        rc, payload = _run_real_raw_where(
            ["src/a.py::write", "never_read.py::read"], repo)
        assert "additionalContext" not in payload["hookSpecificOutput"]

    def test_unmarked_legacy_format_unchanged(self, repo):
        rc, payload = _run_real_raw_where(["src/a.py", "never.py"], repo)
        assert _missing_block(payload) == ("缺失檔案（1 個）：", "  - never.py")

    def test_read_where_files_structured_result(self):
        files = hook_module.read_ticket_where_files
        with patch("lib.hook_ticket.find_ticket_file", return_value=Path(".")), \
             patch("lib.hook_ticket.parse_ticket_frontmatter",
                   return_value={"where": {"files": [
                       "A/B.py::write", "c.py::read", "d.py"]}}):
            assert files("x", Path("."), logging.getLogger("t")) == ["a/b.py", "d.py"]

    def test_parser_is_shared_with_track_commit(self):
        """與 track_commit 共用同一解析函式（斷言兩邊為同一物件）"""
        from ticket_system.lib import file_conflict
        assert hook_module.parse_file_intent is file_conflict.parse_file_intent
        # track_commit 依賴 filelock（hooks 測試環境無），改以原始碼斷言其匯入來源
        src = (Path(file_conflict.__file__).parent.parent / "commands"
               / "track_commit.py").read_text(encoding="utf-8")
        assert ("from ticket_system.lib.file_conflict import "
                "files_intersect, parse_file_intent, write_files") in src

    def test_extract_failure_fail_open(self, repo):
        """where.files 抽取拋例外：reader 回空、main exit 0 不阻擋"""
        rc, payload = None, None
        with patch.object(hook_module, "extract_where_files",
                          side_effect=OSError("boom")):
            assert hook_module.read_ticket_where_files(
                "x", Path("."), logging.getLogger("t")) == []
            out = StringIO()
            with patch.object(hook_module, "read_json_from_stdin",
                              return_value=_real_payload(f"ticket track complete {SUB_ID}")), \
                 patch.object(hook_module, "is_subagent_environment", return_value=False), \
                 patch.object(hook_module, "get_project_root", return_value=repo), \
                 patch("sys.stdout", out):
                rc = hook_module.main()
            payload = json.loads(out.getvalue())
        assert rc == 0
        assert "additionalContext" not in payload["hookSpecificOutput"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
