"""
Test: git_command_parse 子 shell 括號盲點（0.4.0-W1-065）

成因：`parse_command_statements` / `find_git_invocations` 的切詞把 `)`、`);` 黏成
單一 token，子 shell 閉合後的語句併進前一個語句，使 `(A); git X` 的 X 漏抓，
共用此解析器的守衛可被繞過。

層次：
- 共用層：`(A); git X` 等形式必須抓到 X；`(A && git X)` 抓到 X。
- E2 端到端（走 hook main）：wipe-guard / merge-staged-index-guard / bare-commit-guard
  對 `(…); git <危險命令>` 必須照既有規則處理。
- E1 對照：無括號寫法結果與有括號寫法一致。
- 釘住既有行為：引號內括號、`$(...)`、heredoc 內括號、括號無法配對不拋例外。
"""

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent))

from lib.git_command_parse import (  # noqa: E402
    find_git_invocations,
    parse_command_statements,
)


def _load(module_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(module_name, HOOKS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _subcommands(command: str, wanted):
    invocations = find_git_invocations(command, wanted)
    assert invocations is not None, "不應解析失敗"
    return [inv.subcommand for inv in invocations]


# ============================================================================
# 共用層：括號後的 git 呼叫必須被抓到
# ============================================================================


class TestSharedLayerSubshellBoundary:
    def test_subshell_semicolon_then_merge(self):
        assert _subcommands("(cd /tmp/x && git status); git merge foo", {"merge"}) == ["merge"]

    def test_subshell_semicolon_then_commit(self):
        assert _subcommands("(cd /tmp/x && git status); git commit -m x", {"commit"}) == ["commit"]

    def test_subshell_semicolon_then_reset(self):
        assert _subcommands("(true); git reset --hard", {"reset"}) == ["reset"]

    def test_subshell_newline_then_reset(self):
        assert _subcommands("(true)\ngit reset --hard", {"reset"}) == ["reset"]

    def test_git_inside_subshell_after_and(self):
        assert _subcommands("(A && git reset --hard)", {"reset"}) == ["reset"]

    def test_subshell_and_then_git(self):
        assert _subcommands("(true) && git merge foo", {"merge"}) == ["merge"]

    def test_subshell_or_then_git(self):
        assert _subcommands("(false) || git merge foo", {"merge"}) == ["merge"]

    def test_nested_subshell_close_then_git(self):
        assert _subcommands("((true)); git merge foo", {"merge"}) == ["merge"]

    def test_git_status_inside_not_mistaken_as_wanted(self):
        # 括號內的 status 不是目標子命令，只抓括號後的 merge
        invs = find_git_invocations("(git status); git merge foo", {"merge"})
        assert [i.subcommand for i in invs] == ["merge"]
        assert invs[0].args == ["foo"]

    def test_statements_split_at_close_paren(self):
        stmts = parse_command_statements("(cd /tmp/x && git status); git merge foo")
        assert ["git", "merge", "foo"] in stmts
        assert ["git", "status"] in stmts
        assert not any(")" in tok or ");" in tok for s in stmts for tok in s)


# ============================================================================
# E1：無括號寫法結果不變，且與有括號寫法一致
# ============================================================================


class TestNoParenBaselineUnchanged:
    def test_plain_semicolon(self):
        assert _subcommands("git status; git merge foo", {"merge"}) == ["merge"]

    def test_plain_and(self):
        assert _subcommands("git add a && git commit -m x", {"commit"}) == ["commit"]

    def test_plain_statements_shape(self):
        assert parse_command_statements("git status; git merge foo") == [
            ["git", "status"],
            ["git", "merge", "foo"],
        ]

    def test_paren_and_plain_agree(self):
        with_paren = _subcommands("(true); git reset --hard", {"reset"})
        without = _subcommands("true; git reset --hard", {"reset"})
        assert with_paren == without

    def test_empty_command(self):
        assert parse_command_statements("") == []
        assert find_git_invocations("", {"commit"}) == []


# ============================================================================
# 釘住既有行為：引號內括號 / 命令替換 / heredoc / 無法配對
# ============================================================================


class TestPinnedExistingBehavior:
    def test_quoted_parens_stay_inside_token(self):
        stmts = parse_command_statements('git commit -m "fix (a); b"')
        assert stmts == [["git", "commit", "-m", "fix (a); b"]]

    def test_quoted_git_in_parens_is_not_a_call(self):
        assert _subcommands('echo "(git reset --hard)"', {"reset"}) == []

    def test_single_quoted_close_paren_stays(self):
        stmts = parse_command_statements("git commit -m 'x);y'")
        assert stmts == [["git", "commit", "-m", "x);y"]]

    def test_command_substitution_inner_git_detected(self):
        # 現行行為：`$(` 的括號當語句邊界，內部 git 被視為獨立語句
        assert _subcommands("echo $(git reset --hard)", {"reset"}) == ["reset"]

    def test_command_substitution_then_git(self):
        # 修正前 `);` 黏連使其後的 merge 漏抓；修正後應抓到
        assert _subcommands("x=$(git rev-parse HEAD); git merge a", {"merge"}) == ["merge"]

    def test_heredoc_body_parens_ignored(self):
        cmd = "cat <<EOF\n(git reset --hard)\nEOF\ngit status"
        assert _subcommands(cmd, {"reset"}) == []
        assert _subcommands(cmd, {"status"}) == ["status"]

    def test_unbalanced_open_paren_no_exception(self):
        assert _subcommands("(git commit -m x", {"commit"}) == ["commit"]

    def test_unbalanced_close_paren_no_exception(self):
        assert _subcommands("git commit -m x)", {"commit"}) == ["commit"]

    def test_unclosed_quote_still_none(self):
        assert find_git_invocations('git commit -m "x', {"commit"}) is None
        assert parse_command_statements('git commit -m "x') is None

    def test_unbalanced_paren_logs(self, caplog):
        import logging

        with caplog.at_level(logging.DEBUG):
            find_git_invocations("(git commit -m x", {"commit"})
        assert any("括號" in r.getMessage() for r in caplog.records)


# ============================================================================
# E2：workspace-wipe-guard
# ============================================================================


def _run_wipe(
    monkeypatch, command: str, dispatch_count: int = 1, root: Path = Path("/fake/project")
) -> int:
    hook = _load("wipe_guard_e2", "workspace-wipe-guard-hook.py")
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr(hook, "get_project_root", lambda: root)
    monkeypatch.setattr(hook, "_get_active_dispatch_count", lambda root, logger: dispatch_count)
    monkeypatch.setattr(
        hook, "_has_main_repo_uncommitted_tracked_changes", lambda root, logger: False
    )
    return hook.main()


def _two_repos(tmp_path: Path):
    repos = []
    for name in ("main", "other"):
        repo = tmp_path / name
        repo.mkdir()
        subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
        repos.append(repo)
    return repos[0], repos[1]


class TestWipeGuardEndToEnd:
    def test_subshell_then_reset_hard_denied(self, monkeypatch):
        assert _run_wipe(monkeypatch, "(cd /tmp/x && git status); git reset --hard") == 2

    def test_true_subshell_then_reset_hard_denied(self, monkeypatch):
        assert _run_wipe(monkeypatch, "(true); git reset --hard") == 2

    def test_newline_form_denied(self, monkeypatch):
        assert _run_wipe(monkeypatch, "(true)\ngit reset --hard") == 2

    def test_positive_control_plain_denied(self, monkeypatch):
        assert _run_wipe(monkeypatch, "true; git reset --hard") == 2

    def test_single_subshell_cd_other_repo_scope_kept(self, monkeypatch, tmp_path):
        # cd 作用域規則保留：整個命令恰為單一 ( cd X && … ) 時，目標為其他 repo 放行
        main_repo, other = _two_repos(tmp_path)
        assert _run_wipe(monkeypatch, f"(cd {other} && git reset --hard)", root=main_repo) == 0

    def test_subshell_cd_other_repo_then_wipe_not_exempt(self, monkeypatch, tmp_path):
        # 括號外還有其他語句時不採用 cd 推導（fail-closed）
        main_repo, other = _two_repos(tmp_path)
        cmd = f"(cd {other} && git status); git reset --hard"
        assert _run_wipe(monkeypatch, cmd, root=main_repo) == 2


# ============================================================================
# E2：merge-staged-index-guard
# ============================================================================


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def staged_repo(tmp_path):
    repo = tmp_path / "main"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "a.txt").write_text("a\n")
    _git(repo, "add", "a.txt")
    _git(repo, "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q", "-m", "init")
    (repo / "s.txt").write_text("x\n")
    _git(repo, "add", "s.txt")
    return repo


def _run_merge_guard(monkeypatch, command: str, cwd: Path) -> int:
    hook = _load("merge_guard_e2", "merge-staged-index-guard-hook.py")
    payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    return hook.main()


class TestMergeStagedIndexGuardEndToEnd:
    def test_subshell_then_merge_denied(self, monkeypatch, staged_repo):
        assert _run_merge_guard(monkeypatch, "(cd /tmp && git status); git merge x", staged_repo) == 2

    def test_true_subshell_then_merge_denied(self, monkeypatch, staged_repo):
        assert _run_merge_guard(monkeypatch, "(true); git merge x", staged_repo) == 2

    def test_positive_control_plain_denied(self, monkeypatch, staged_repo):
        assert _run_merge_guard(monkeypatch, "true; git merge x", staged_repo) == 2

    def test_clean_index_still_allowed(self, monkeypatch, staged_repo):
        _git(staged_repo, "reset", "-q")
        assert _run_merge_guard(monkeypatch, "(true); git merge x", staged_repo) == 0

    def test_deny_title_names_target_repo(self, monkeypatch, staged_repo, capsys):
        _run_merge_guard(monkeypatch, "git merge x", staged_repo)
        err = capsys.readouterr().err
        assert "目標 repo 的 index 有 staged 變更" in err
        assert "主工作區 index 有 staged 變更" not in err


# ============================================================================
# E2：bare-commit-guard（並行期 + staged 超出派發宣告範圍 -> DENY）
# ============================================================================


def _run_bare_commit(monkeypatch, command: str) -> int:
    hook = _load("bare_commit_e2", "bare-commit-guard-hook.py")
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr(hook, "get_project_root", lambda: Path("/fake/project"))
    monkeypatch.setattr(
        hook,
        "_get_active_dispatches_safe",
        lambda root: [{"ticket_id": "T-1", "files": ["a.py"]}],
    )
    monkeypatch.setattr(hook, "_get_staged_files", lambda root: ["a.py", "b.py"])
    monkeypatch.setattr(hook, "_get_unstaged_tracked_files", lambda root: [])
    return hook.main()


class TestBareCommitGuardEndToEnd:
    def test_subshell_then_bare_commit_denied(self, monkeypatch):
        assert _run_bare_commit(monkeypatch, "(cd /tmp/x && git status); git commit -m x") == 2

    def test_true_subshell_then_bare_commit_denied(self, monkeypatch):
        assert _run_bare_commit(monkeypatch, "(true); git commit -m x") == 2

    def test_positive_control_plain_denied(self, monkeypatch):
        assert _run_bare_commit(monkeypatch, "true; git commit -m x") == 2

    def test_amend_after_subshell_still_exempt(self, monkeypatch):
        assert _run_bare_commit(monkeypatch, "(true); git commit --amend -m x") == 0
