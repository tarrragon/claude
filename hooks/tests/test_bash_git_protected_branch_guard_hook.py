"""
Test: bash-git-protected-branch-guard-hook（0.2.1-W3-151 / 154 / 156）

驗證項目：
1. _contains_git_word: 便宜前置判斷（非 git 命令短路）
2. _find_write_invocations: git -C 形式 + 子 shell cd 形式兩種目標 repo 表達
3. _resolve_repo_root: 三態回傳（resolved / shell_expansion / unresolvable）
4. main() 整合行為：
   - 本專案內的 git 操作不被誤擋（含 git -C 指向本專案的形式、add-and-commit 串接）
   - 跨專案保護分支 + 非豁免 staged 檔案 → deny
   - 跨專案保護分支 + 全豁免 staged 檔案 → allow
   - 跨專案非保護分支 → allow
   - 非 git 命令不進入解析路徑（行為斷言，非計時斷言）
5. 0.2.1-W3-154 add-and-commit 串接繞道修復：
   - git add <非豁免檔> && git commit → deny（PreToolUse 時機 add 尚未執行，
     需從命令字串推導，而非只讀當下 staged 狀態）
   - git commit -a/-am/--all → fail-closed deny
   - git add 含萬用字元 / -A / . → fail-closed deny
   - git commit 帶明確 pathspec → 併入檔案集合判斷
   - 真正無變更的 commit（無 add、無 -a、無 staged）→ 仍放行
6. 0.2.1-W3-156 -C 目標 shell 展開語法繞道修復：
   - -C/cd 目標含 $/`` ` ``/~ → fail-closed deny（不分是否指向本專案，殘留限制）
   - -C 目標為不存在的字面絕對路徑 → 維持 fail-open（該命令本身會失敗）
   - pathspec 解析不再把 shell 重導向 token（2>&1 等）誤列為檔案

Source: ticket 0.2.1-W3-151（PC-V1-012 實例）、0.2.1-W3-154（add-and-commit 串接繞道）、
0.2.1-W3-156（-C 目標 shell 展開語法繞道）
"""

import io
import json
import subprocess
import sys
import importlib.util
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent))

_spec = importlib.util.spec_from_file_location(
    "bash_git_protected_branch_guard_hook",
    HOOKS_DIR / "bash-git-protected-branch-guard-hook.py",
)
hook_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook_module)

_contains_git_word = hook_module._contains_git_word
_find_write_invocations = hook_module._find_write_invocations
_resolve_repo_root = hook_module._resolve_repo_root
build_bash_cross_repo_deny_message = hook_module.build_bash_cross_repo_deny_message


def _init_git_repo(path: Path, branch: str = "main") -> None:
    subprocess.run(["git", "init", "-q", "-b", branch], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)


def _stage_file(repo: Path, rel_path: str, content: str = "x") -> None:
    target = repo / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    subprocess.run(["git", "add", rel_path], cwd=repo, check=True)


# ============================================================================
# _contains_git_word：便宜前置判斷
# ============================================================================


class TestContainsGitWord:
    def test_git_word_present(self):
        assert _contains_git_word("git -C /repo commit -m x") is True

    def test_no_git_word(self):
        assert _contains_git_word("ls -la && pytest tests/") is False

    def test_empty_command(self):
        assert _contains_git_word("") is False

    def test_git_as_substring_not_word_boundary(self):
        """'digit' 含 'git' 子字串但非獨立單詞，不應命中。"""
        assert _contains_git_word("echo digit") is False


# ============================================================================
# _find_write_invocations：兩種目標 repo 表達形式
# ============================================================================


def _invocation_keys(inv):
    """僅比對穩定的 repo_hint/subcmd 欄位（rest/scope_content 由個別測試檢查）。"""
    return {"repo_hint": inv["repo_hint"], "subcmd": inv["subcmd"]}


class TestFindWriteInvocations:
    def test_dash_c_form(self):
        invocations = _find_write_invocations('git -C /Users/x/repo commit -m "msg"')
        assert [_invocation_keys(i) for i in invocations] == [
            {"repo_hint": "/Users/x/repo", "subcmd": "commit"}
        ]
        assert invocations[0]["scope_content"] is None

    def test_dash_c_form_captures_rest(self):
        """0.2.1-W3-154：rest 用於後續推導 pathspec/flag（-a/-am/--all）。"""
        invocations = _find_write_invocations("git -C /repo commit -a")
        assert "-a" in invocations[0]["rest"]

    def test_subshell_cd_form(self):
        invocations = _find_write_invocations('(cd /Users/x/repo && git commit -m "msg")')
        assert [_invocation_keys(i) for i in invocations] == [
            {"repo_hint": "/Users/x/repo", "subcmd": "commit"}
        ]
        assert invocations[0]["scope_content"] is not None

    def test_subshell_cd_semicolon_form(self):
        invocations = _find_write_invocations("(cd /Users/x/repo; git commit -m x)")
        assert [_invocation_keys(i) for i in invocations] == [
            {"repo_hint": "/Users/x/repo", "subcmd": "commit"}
        ]

    def test_dash_c_non_write_subcommand_no_match(self):
        """git -C <path> status 非 write 子命令，不命中。"""
        assert _find_write_invocations("git -C /Users/x/repo status") == []

    def test_no_c_no_subshell_cwd_implied_no_match(self):
        """cwd 隱含形式（無 -C、無子 shell cd）不解析，範疇邊界。"""
        assert _find_write_invocations('git commit -m "msg"') == []

    def test_plain_non_git_command_no_match(self):
        assert _find_write_invocations("ls -la") == []

    def test_subshell_without_cd_no_match(self):
        """子 shell 內無 cd（例如僅 git -C），不套用子 shell cd 規則（由 -C 規則涵蓋）。"""
        invocations = _find_write_invocations("(git -C /repo commit)")
        assert [_invocation_keys(i) for i in invocations] == [
            {"repo_hint": "/repo", "subcmd": "commit"}
        ]


# ============================================================================
# _resolve_repo_root：只接受絕對路徑
# ============================================================================


class TestResolveRepoRoot:
    """0.2.1-W3-156：回傳型別改為 (outcome, target_root) 三態。"""

    def test_relative_path_unresolvable(self):
        outcome, target_root = _resolve_repo_root("../sibling")
        assert outcome == "unresolvable"
        assert target_root is None

    def test_empty_unresolvable(self):
        outcome, target_root = _resolve_repo_root("")
        assert outcome == "unresolvable"
        assert target_root is None

    def test_absolute_path_resolves_to_repo_root(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        sub = repo / "sub"
        sub.mkdir()
        # git -C 語意：路徑可指向 repo 內任意子目錄，仍解析回 repo 根
        outcome, target_root = _resolve_repo_root(str(sub))
        assert outcome == "resolved"
        assert Path(target_root).resolve() == repo.resolve()

    def test_nonexistent_absolute_path_unresolvable(self):
        """acceptance 3：不存在的字面絕對路徑維持 unresolvable（fail-open）。"""
        outcome, target_root = _resolve_repo_root("/nonexistent/path/xyz")
        assert outcome == "unresolvable"
        assert target_root is None

    def test_dollar_variable_shell_expansion(self):
        outcome, target_root = _resolve_repo_root("$T")
        assert outcome == "shell_expansion"
        assert target_root is None

    def test_dollar_variable_embedded_in_path_shell_expansion(self):
        outcome, target_root = _resolve_repo_root("/Users/$USER/project/blog")
        assert outcome == "shell_expansion"

    def test_backtick_command_substitution_shell_expansion(self):
        outcome, target_root = _resolve_repo_root("`pwd`/repo")
        assert outcome == "shell_expansion"

    def test_tilde_home_expansion_shell_expansion(self):
        outcome, target_root = _resolve_repo_root("~/project/blog")
        assert outcome == "shell_expansion"


# ============================================================================
# build_bash_cross_repo_deny_message
# ============================================================================


class TestBuildDenyMessage:
    def test_contains_target_repo_and_branch(self):
        msg = build_bash_cross_repo_deny_message(
            target_repo="/repo", target_branch="main", non_exempt_files=["src/x.py"]
        )
        assert "/repo" in msg
        assert "main" in msg
        assert "src/x.py" in msg

    def test_contains_checkout_instruction(self):
        msg = build_bash_cross_repo_deny_message(
            target_repo="/repo", target_branch="main", non_exempt_files=["a.py"]
        )
        assert "git -C /repo checkout -b" in msg

    def test_empty_non_exempt_files_shows_uncertain_note(self):
        msg = build_bash_cross_repo_deny_message(
            target_repo="/repo", target_branch="main", non_exempt_files=[]
        )
        assert "無法確認" in msg


# ============================================================================
# main() 整合行為
# ============================================================================


def _run_main(monkeypatch, capsys, input_dict):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(input_dict)))
    exit_code = hook_module.main()
    captured = capsys.readouterr()
    return exit_code, captured.out


class TestMainNonGitOrNonBash:
    def test_non_bash_tool_skipped(self, monkeypatch, capsys):
        exit_code, out = _run_main(
            monkeypatch, capsys, {"tool_name": "Edit", "tool_input": {}}
        )
        assert exit_code == 0
        assert out.strip() == ""

    def test_non_git_bash_command_no_output(self, monkeypatch, capsys):
        exit_code, out = _run_main(
            monkeypatch,
            capsys,
            {"tool_name": "Bash", "tool_input": {"command": "pytest tests/ -q"}},
        )
        assert exit_code == 0
        assert out.strip() == ""

    def test_non_git_command_short_circuits_before_parsing(self, monkeypatch, capsys):
        """行為斷言（非計時斷言）：非 git 命令不應進入 _find_write_invocations 解析路徑。"""

        def _boom(command):
            raise AssertionError("非 git 命令不應進入解析路徑")

        monkeypatch.setattr(hook_module, "_find_write_invocations", _boom)
        exit_code, out = _run_main(
            monkeypatch,
            capsys,
            {"tool_name": "Bash", "tool_input": {"command": "npm install && npm test"}},
        )
        assert exit_code == 0
        assert out.strip() == ""


class TestMainHostRepoNeverBlocked:
    """不可回歸項：本專案內的正常 git 操作不被誤擋（含 git -C 指向本專案的形式）。"""

    def test_git_dash_c_pointing_to_host_repo_allowed(self, monkeypatch, capsys):
        host_root = str(hook_module.get_project_root())
        exit_code, out = _run_main(
            monkeypatch,
            capsys,
            {
                "tool_name": "Bash",
                "tool_input": {"command": f'git -C {host_root} commit -m "msg"'},
            },
        )
        assert exit_code == 0
        assert out.strip() == ""

    def test_git_commit_no_c_no_subshell_allowed(self, monkeypatch, capsys):
        """cwd 隱含形式（PM 日常最常見寫法）無法解析目標 repo，安全預設放行。"""
        exit_code, out = _run_main(
            monkeypatch,
            capsys,
            {"tool_name": "Bash", "tool_input": {"command": 'git commit -m "msg"'}},
        )
        assert exit_code == 0
        assert out.strip() == ""


class TestMainCrossRepoProtectedBranch:
    def test_non_exempt_staged_files_denied(self, monkeypatch, capsys, tmp_path):
        host = tmp_path / "host"
        host.mkdir()
        _init_git_repo(host)

        external = tmp_path / "external"
        external.mkdir()
        _init_git_repo(external, branch="main")
        _stage_file(external, ".claude/skills/x/y.md")

        monkeypatch.setattr(hook_module, "get_project_root", lambda: host)

        exit_code, out = _run_main(
            monkeypatch,
            capsys,
            {
                "tool_name": "Bash",
                "tool_input": {"command": f'git -C {external} commit -m "msg"'},
            },
        )
        assert exit_code == 0
        payload = json.loads(out)
        hso = payload["hookSpecificOutput"]
        assert hso["permissionDecision"] == "deny"
        reason = hso["permissionDecisionReason"]
        assert str(external) in reason
        assert ".claude/skills/x/y.md" in reason
        assert "main" in reason

    def test_all_staged_files_exempt_allowed(self, monkeypatch, capsys, tmp_path):
        host = tmp_path / "host"
        host.mkdir()
        _init_git_repo(host)

        external = tmp_path / "external"
        external.mkdir()
        _init_git_repo(external, branch="main")
        _stage_file(external, "README.md")

        monkeypatch.setattr(hook_module, "get_project_root", lambda: host)

        exit_code, out = _run_main(
            monkeypatch,
            capsys,
            {
                "tool_name": "Bash",
                "tool_input": {"command": f'git -C {external} commit -m "msg"'},
            },
        )
        assert exit_code == 0
        assert out.strip() == ""

    def test_non_protected_branch_allowed(self, monkeypatch, capsys, tmp_path):
        host = tmp_path / "host"
        host.mkdir()
        _init_git_repo(host)

        external = tmp_path / "external"
        external.mkdir()
        _init_git_repo(external, branch="feat/wip")
        _stage_file(external, "src/x.py")

        monkeypatch.setattr(hook_module, "get_project_root", lambda: host)

        exit_code, out = _run_main(
            monkeypatch,
            capsys,
            {
                "tool_name": "Bash",
                "tool_input": {"command": f'git -C {external} commit -m "msg"'},
            },
        )
        assert exit_code == 0
        assert out.strip() == ""

    def test_subshell_cd_form_denied(self, monkeypatch, capsys, tmp_path):
        """子 shell cd 形式與 git -C 形式行為一致（acceptance：兩種形式測試覆蓋）。"""
        host = tmp_path / "host"
        host.mkdir()
        _init_git_repo(host)

        external = tmp_path / "external"
        external.mkdir()
        _init_git_repo(external, branch="main")
        _stage_file(external, "src/x.py")

        monkeypatch.setattr(hook_module, "get_project_root", lambda: host)

        exit_code, out = _run_main(
            monkeypatch,
            capsys,
            {
                "tool_name": "Bash",
                "tool_input": {"command": f'(cd {external} && git commit -m "msg")'},
            },
        )
        assert exit_code == 0
        payload = json.loads(out)
        assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_no_staged_files_allowed(self, monkeypatch, capsys, tmp_path):
        """保護分支但無 staged 檔案（commit 本身會 no-op），允許。"""
        host = tmp_path / "host"
        host.mkdir()
        _init_git_repo(host)

        external = tmp_path / "external"
        external.mkdir()
        _init_git_repo(external, branch="main")

        monkeypatch.setattr(hook_module, "get_project_root", lambda: host)

        exit_code, out = _run_main(
            monkeypatch,
            capsys,
            {
                "tool_name": "Bash",
                "tool_input": {"command": f'git -C {external} commit -m "msg"'},
            },
        )
        assert exit_code == 0
        assert out.strip() == ""

    def test_nonexistent_target_repo_allowed(self, monkeypatch, capsys, tmp_path):
        """target repo 不存在（find_target_repo 回 None）：無法確認一律放行。"""
        host = tmp_path / "host"
        host.mkdir()
        _init_git_repo(host)

        monkeypatch.setattr(hook_module, "get_project_root", lambda: host)

        exit_code, out = _run_main(
            monkeypatch,
            capsys,
            {
                "tool_name": "Bash",
                "tool_input": {
                    "command": 'git -C /nonexistent/path/xyz commit -m "msg"'
                },
            },
        )
        assert exit_code == 0
        assert out.strip() == ""


# ============================================================================
# 0.2.1-W3-154: add-and-commit 串接繞道修復
# ============================================================================
#
# 根因：舊版只讀「PreToolUse 評估當下」的 git diff --cached，串接命令中的
# git add 尚未執行、staged 為空，誤判為 no-op 而放行。新版改為從命令字串
# 額外推導 commit 完成後的完整檔案集合（commit pathspec + 同範圍 git add +
# 當下已 staged 三者聯集），無法靜態推導者 fail-closed。


class TestAddAndCommitChain:
    def test_add_non_exempt_file_then_commit_denied(self, monkeypatch, capsys, tmp_path):
        """PM 實測案例：git add <非豁免檔> && git commit 對外部保護分支應被攔截。"""
        host = tmp_path / "host"
        host.mkdir()
        _init_git_repo(host)

        external = tmp_path / "external"
        external.mkdir()
        _init_git_repo(external, branch="main")
        (external / "content").mkdir()
        (external / "content" / "note.md").write_text("hi")

        monkeypatch.setattr(hook_module, "get_project_root", lambda: host)

        command = (
            f'git -C {external} add content/note.md && '
            f'git -C {external} commit -m "msg"'
        )
        exit_code, out = _run_main(
            monkeypatch, capsys, {"tool_name": "Bash", "tool_input": {"command": command}}
        )
        assert exit_code == 0
        payload = json.loads(out)
        hso = payload["hookSpecificOutput"]
        assert hso["permissionDecision"] == "deny"
        assert "content/note.md" in hso["permissionDecisionReason"]

    def test_add_exempt_file_then_commit_allowed(self, monkeypatch, capsys, tmp_path):
        """git add <豁免檔> && git commit：豁免檔案不受攔截。"""
        host = tmp_path / "host"
        host.mkdir()
        _init_git_repo(host)

        external = tmp_path / "external"
        external.mkdir()
        _init_git_repo(external, branch="main")
        (external / "README.md").write_text("hi")

        monkeypatch.setattr(hook_module, "get_project_root", lambda: host)

        command = (
            f'git -C {external} add README.md && git -C {external} commit -m "msg"'
        )
        exit_code, out = _run_main(
            monkeypatch, capsys, {"tool_name": "Bash", "tool_input": {"command": command}}
        )
        assert exit_code == 0
        assert out.strip() == ""

    def test_subshell_add_then_commit_denied(self, monkeypatch, capsys, tmp_path):
        """子 shell 形式的 add-and-commit 串接同樣受偵測。"""
        host = tmp_path / "host"
        host.mkdir()
        _init_git_repo(host)

        external = tmp_path / "external"
        external.mkdir()
        _init_git_repo(external, branch="main")
        (external / "src").mkdir()
        (external / "src" / "x.py").write_text("hi")

        monkeypatch.setattr(hook_module, "get_project_root", lambda: host)

        command = f'(cd {external} && git add src/x.py && git commit -m "msg")'
        exit_code, out = _run_main(
            monkeypatch, capsys, {"tool_name": "Bash", "tool_input": {"command": command}}
        )
        assert exit_code == 0
        payload = json.loads(out)
        assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_host_repo_add_and_commit_chain_unaffected(self, monkeypatch, capsys):
        """acceptance 4：本專案內的 add-and-commit 串接不受影響（host repo 一律放行）。"""
        host_root = str(hook_module.get_project_root())
        command = (
            f'git -C {host_root} add docs/some-note.md && '
            f'git -C {host_root} commit -m "msg"'
        )
        exit_code, out = _run_main(
            monkeypatch, capsys, {"tool_name": "Bash", "tool_input": {"command": command}}
        )
        assert exit_code == 0
        assert out.strip() == ""


class TestCommitAllFlagFailClosed:
    def test_commit_dash_a_denied(self, monkeypatch, capsys, tmp_path):
        """acceptance 2：git commit -a 對外部保護分支應被攔截（fail-closed）。"""
        host = tmp_path / "host"
        host.mkdir()
        _init_git_repo(host)

        external = tmp_path / "external"
        external.mkdir()
        _init_git_repo(external, branch="main")

        monkeypatch.setattr(hook_module, "get_project_root", lambda: host)

        command = f'git -C {external} commit -a -m "msg"'
        exit_code, out = _run_main(
            monkeypatch, capsys, {"tool_name": "Bash", "tool_input": {"command": command}}
        )
        assert exit_code == 0
        payload = json.loads(out)
        assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_commit_dash_am_denied(self, monkeypatch, capsys, tmp_path):
        host = tmp_path / "host"
        host.mkdir()
        _init_git_repo(host)

        external = tmp_path / "external"
        external.mkdir()
        _init_git_repo(external, branch="main")

        monkeypatch.setattr(hook_module, "get_project_root", lambda: host)

        command = f'git -C {external} commit -am "msg"'
        exit_code, out = _run_main(
            monkeypatch, capsys, {"tool_name": "Bash", "tool_input": {"command": command}}
        )
        assert exit_code == 0
        assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_commit_dash_dash_all_denied(self, monkeypatch, capsys, tmp_path):
        host = tmp_path / "host"
        host.mkdir()
        _init_git_repo(host)

        external = tmp_path / "external"
        external.mkdir()
        _init_git_repo(external, branch="main")

        monkeypatch.setattr(hook_module, "get_project_root", lambda: host)

        command = f'git -C {external} commit --all -m "msg"'
        exit_code, out = _run_main(
            monkeypatch, capsys, {"tool_name": "Bash", "tool_input": {"command": command}}
        )
        assert exit_code == 0
        assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_host_repo_commit_dash_a_unaffected(self, monkeypatch, capsys):
        """host repo 的 -a 不受影響（host-repo skip 在 pending-files 推導之前）。"""
        host_root = str(hook_module.get_project_root())
        command = f'git -C {host_root} commit -a -m "msg"'
        exit_code, out = _run_main(
            monkeypatch, capsys, {"tool_name": "Bash", "tool_input": {"command": command}}
        )
        assert exit_code == 0
        assert out.strip() == ""


class TestUnenumerableAddFailClosed:
    def test_add_wildcard_denied(self, monkeypatch, capsys, tmp_path):
        host = tmp_path / "host"
        host.mkdir()
        _init_git_repo(host)

        external = tmp_path / "external"
        external.mkdir()
        _init_git_repo(external, branch="main")

        monkeypatch.setattr(hook_module, "get_project_root", lambda: host)

        command = f'git -C {external} add *.py && git -C {external} commit -m "msg"'
        exit_code, out = _run_main(
            monkeypatch, capsys, {"tool_name": "Bash", "tool_input": {"command": command}}
        )
        assert exit_code == 0
        payload = json.loads(out)
        assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "無法" in payload["hookSpecificOutput"]["permissionDecisionReason"]

    def test_add_dash_capital_a_denied(self, monkeypatch, capsys, tmp_path):
        host = tmp_path / "host"
        host.mkdir()
        _init_git_repo(host)

        external = tmp_path / "external"
        external.mkdir()
        _init_git_repo(external, branch="main")

        monkeypatch.setattr(hook_module, "get_project_root", lambda: host)

        command = f'git -C {external} add -A && git -C {external} commit -m "msg"'
        exit_code, out = _run_main(
            monkeypatch, capsys, {"tool_name": "Bash", "tool_input": {"command": command}}
        )
        assert exit_code == 0
        assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_add_dot_denied(self, monkeypatch, capsys, tmp_path):
        host = tmp_path / "host"
        host.mkdir()
        _init_git_repo(host)

        external = tmp_path / "external"
        external.mkdir()
        _init_git_repo(external, branch="main")

        monkeypatch.setattr(hook_module, "get_project_root", lambda: host)

        command = f'git -C {external} add . && git -C {external} commit -m "msg"'
        exit_code, out = _run_main(
            monkeypatch, capsys, {"tool_name": "Bash", "tool_input": {"command": command}}
        )
        assert exit_code == 0
        assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"


class TestCommitExplicitPathspec:
    def test_commit_with_non_exempt_pathspec_denied(self, monkeypatch, capsys, tmp_path):
        """git commit <path> 明確 pathspec：併入檔案集合判斷。"""
        host = tmp_path / "host"
        host.mkdir()
        _init_git_repo(host)

        external = tmp_path / "external"
        external.mkdir()
        _init_git_repo(external, branch="main")
        (external / "src").mkdir()
        (external / "src" / "x.py").write_text("hi")

        monkeypatch.setattr(hook_module, "get_project_root", lambda: host)

        command = f'git -C {external} commit -m "msg" src/x.py'
        exit_code, out = _run_main(
            monkeypatch, capsys, {"tool_name": "Bash", "tool_input": {"command": command}}
        )
        assert exit_code == 0
        payload = json.loads(out)
        assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "src/x.py" in payload["hookSpecificOutput"]["permissionDecisionReason"]

    def test_commit_with_exempt_pathspec_allowed(self, monkeypatch, capsys, tmp_path):
        host = tmp_path / "host"
        host.mkdir()
        _init_git_repo(host)

        external = tmp_path / "external"
        external.mkdir()
        _init_git_repo(external, branch="main")
        (external / "README.md").write_text("hi")

        monkeypatch.setattr(hook_module, "get_project_root", lambda: host)

        command = f'git -C {external} commit -m "msg" README.md'
        exit_code, out = _run_main(
            monkeypatch, capsys, {"tool_name": "Bash", "tool_input": {"command": command}}
        )
        assert exit_code == 0
        assert out.strip() == ""


class TestTrueNoOpStillAllowed:
    def test_bare_commit_no_add_no_staged_allowed(self, monkeypatch, capsys, tmp_path):
        """acceptance 3：真正無變更的 commit 仍放行（無 add、無 -a、無 staged）。"""
        host = tmp_path / "host"
        host.mkdir()
        _init_git_repo(host)

        external = tmp_path / "external"
        external.mkdir()
        _init_git_repo(external, branch="main")

        monkeypatch.setattr(hook_module, "get_project_root", lambda: host)

        command = f'git -C {external} commit -m "empty"'
        exit_code, out = _run_main(
            monkeypatch, capsys, {"tool_name": "Bash", "tool_input": {"command": command}}
        )
        assert exit_code == 0
        assert out.strip() == ""


# ============================================================================
# 內部推導函式單元測試（_determine_pending_files 及其輔助函式）
# ============================================================================

_parse_literal_paths = hook_module._parse_literal_paths
_parse_commit_pathspec = hook_module._parse_commit_pathspec
_ADD_UNENUMERABLE_FLAGS = hook_module._ADD_UNENUMERABLE_FLAGS


class TestParseLiteralPaths:
    def test_simple_paths(self):
        assert _parse_literal_paths(" a.py b.py", _ADD_UNENUMERABLE_FLAGS) == ["a.py", "b.py"]

    def test_dash_capital_a_unenumerable(self):
        assert _parse_literal_paths(" -A", _ADD_UNENUMERABLE_FLAGS) is None

    def test_dot_unenumerable(self):
        assert _parse_literal_paths(" .", _ADD_UNENUMERABLE_FLAGS) is None

    def test_wildcard_unenumerable(self):
        assert _parse_literal_paths(" *.py", _ADD_UNENUMERABLE_FLAGS) is None

    def test_unclosed_quote_unenumerable(self):
        assert _parse_literal_paths(' "unclosed', _ADD_UNENUMERABLE_FLAGS) is None

    def test_flag_then_path(self):
        assert _parse_literal_paths(" -v a.py", _ADD_UNENUMERABLE_FLAGS) == ["a.py"]


class TestParseCommitPathspec:
    def test_message_only_no_pathspec(self):
        has_all, paths = _parse_commit_pathspec(' -m "msg"')
        assert has_all is False
        assert paths == []

    def test_dash_a_flag(self):
        has_all, paths = _parse_commit_pathspec(" -a -m msg")
        assert has_all is True
        assert paths is None

    def test_dash_am_combined_flag(self):
        has_all, paths = _parse_commit_pathspec(' -am "msg"')
        assert has_all is True
        assert paths is None

    def test_dash_dash_all_flag(self):
        has_all, paths = _parse_commit_pathspec(' --all -m "msg"')
        assert has_all is True
        assert paths is None

    def test_explicit_pathspec(self):
        has_all, paths = _parse_commit_pathspec(' -m "msg" src/x.py')
        assert has_all is False
        assert paths == ["src/x.py"]

    def test_amend_not_treated_as_all(self):
        """--amend 不含 'a' 短 flag 語意，不應誤判為 stage-all。"""
        has_all, paths = _parse_commit_pathspec(" --amend --no-edit")
        assert has_all is False
        assert paths == []


# ============================================================================
# 0.2.1-W3-156: -C 目標 shell 展開語法繞道修復
# ============================================================================
#
# 根因：舊版 _resolve_repo_root 對非絕對路徑字串（含未展開的 $VAR）一律回
# None，呼叫端一律視為「無法解析、安全放行」（fail-open）。這與同 hook 對
# pathspec 無法靜態列舉時採 fail-closed 的原則矛盾。新版區分「含 shell 展開
# 語法」（fail-closed）與「純粹無法解析的字面路徑」（維持 fail-open）。


class TestShellExpansionFailClosed:
    def test_dollar_variable_c_target_denied(self, monkeypatch, capsys, tmp_path):
        """PM 實測案例：git -C $T add x && git -C $T commit 應被攔截。"""
        host = tmp_path / "host"
        host.mkdir()
        _init_git_repo(host)
        monkeypatch.setattr(hook_module, "get_project_root", lambda: host)

        command = 'git -C $T add x && git -C $T commit -m "msg"'
        exit_code, out = _run_main(
            monkeypatch, capsys, {"tool_name": "Bash", "tool_input": {"command": command}}
        )
        assert exit_code == 0
        payload = json.loads(out)
        hso = payload["hookSpecificOutput"]
        assert hso["permissionDecision"] == "deny"
        assert "$T" in hso["permissionDecisionReason"]
        assert "無法" in hso["permissionDecisionReason"]

    def test_backtick_command_substitution_denied(self, monkeypatch, capsys, tmp_path):
        host = tmp_path / "host"
        host.mkdir()
        _init_git_repo(host)
        monkeypatch.setattr(hook_module, "get_project_root", lambda: host)

        command = 'git -C `pwd`/repo commit -m "msg"'
        exit_code, out = _run_main(
            monkeypatch, capsys, {"tool_name": "Bash", "tool_input": {"command": command}}
        )
        assert exit_code == 0
        assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_tilde_expansion_denied(self, monkeypatch, capsys, tmp_path):
        host = tmp_path / "host"
        host.mkdir()
        _init_git_repo(host)
        monkeypatch.setattr(hook_module, "get_project_root", lambda: host)

        command = 'git -C ~/project/blog commit -m "msg"'
        exit_code, out = _run_main(
            monkeypatch, capsys, {"tool_name": "Bash", "tool_input": {"command": command}}
        )
        assert exit_code == 0
        assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_subshell_cd_dollar_variable_denied(self, monkeypatch, capsys, tmp_path):
        """子 shell cd 形式的變數目標同樣受偵測。"""
        host = tmp_path / "host"
        host.mkdir()
        _init_git_repo(host)
        monkeypatch.setattr(hook_module, "get_project_root", lambda: host)

        command = '(cd $T && git commit -m "msg")'
        exit_code, out = _run_main(
            monkeypatch, capsys, {"tool_name": "Bash", "tool_input": {"command": command}}
        )
        assert exit_code == 0
        assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_nonexistent_literal_absolute_path_still_allowed(self, monkeypatch, capsys, tmp_path):
        """acceptance 3：不存在的字面絕對路徑（不含展開語法）維持放行。"""
        host = tmp_path / "host"
        host.mkdir()
        _init_git_repo(host)
        monkeypatch.setattr(hook_module, "get_project_root", lambda: host)

        command = 'git -C /nonexistent/absolute/path commit -m "msg"'
        exit_code, out = _run_main(
            monkeypatch, capsys, {"tool_name": "Bash", "tool_input": {"command": command}}
        )
        assert exit_code == 0
        assert out.strip() == ""

    def test_host_repo_shell_expansion_target_documented_residual(
        self, monkeypatch, capsys, tmp_path
    ):
        """已知殘留限制（非 bug）：即使變數實際展開後等於本專案路徑，hook
        無法在 PreToolUse 時機得知這件事（os.environ 不含 Bash 工具持久 shell
        的變數賦值），仍會 fail-closed。此測試記錄該限制存在，而非驗證
        「不受影響」——見 ticket Solution「殘留清單」。
        """
        host_root = str(hook_module.get_project_root())
        command = f'T={host_root}; git -C $T commit -m "msg"'
        exit_code, out = _run_main(
            monkeypatch, capsys, {"tool_name": "Bash", "tool_input": {"command": command}}
        )
        assert exit_code == 0
        # 即使 $T 語意上等於 host_root，字面字串仍含 '$'，一律 fail-closed。
        payload = json.loads(out)
        assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_variable_in_commit_message_not_c_target_unaffected(
        self, monkeypatch, capsys, tmp_path
    ):
        """變數出現在非 -C 目標位置（如 commit message）不觸發 shell 展開偵測；
        本專案內操作仍走既有 host-repo skip 放行（acceptance 4 的可行讀法）。
        """
        host_root = str(hook_module.get_project_root())
        command = f'git -C {host_root} add docs/note.md && git -C {host_root} commit -m "$MSG"'
        exit_code, out = _run_main(
            monkeypatch, capsys, {"tool_name": "Bash", "tool_input": {"command": command}}
        )
        assert exit_code == 0
        assert out.strip() == ""


class TestRedirectionTokenFiltering:
    def test_stderr_redirect_not_listed_as_file(self, monkeypatch, capsys, tmp_path):
        """acceptance 5：2>&1 等重導向 token 不應被解析為非豁免檔案。"""
        host = tmp_path / "host"
        host.mkdir()
        _init_git_repo(host)

        external = tmp_path / "external"
        external.mkdir()
        _init_git_repo(external, branch="main")
        (external / "src").mkdir()
        (external / "src" / "x.py").write_text("hi")

        monkeypatch.setattr(hook_module, "get_project_root", lambda: host)

        command = f'git -C {external} commit -m "msg" src/x.py 2>&1'
        exit_code, out = _run_main(
            monkeypatch, capsys, {"tool_name": "Bash", "tool_input": {"command": command}}
        )
        assert exit_code == 0
        payload = json.loads(out)
        reason = payload["hookSpecificOutput"]["permissionDecisionReason"]
        assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "src/x.py" in reason
        assert "2>" not in reason

    def test_redirection_token_unit(self):
        _is_shell_redirection_token = hook_module._is_shell_redirection_token
        assert _is_shell_redirection_token("2>&1") is True
        assert _is_shell_redirection_token(">") is True
        assert _is_shell_redirection_token(">>") is True
        assert _is_shell_redirection_token("<") is True
        assert _is_shell_redirection_token("&>") is True
        assert _is_shell_redirection_token("src/x.py") is False
        assert _is_shell_redirection_token("2") is False


class TestHasShellExpansionSyntaxUnit:
    def test_dollar(self):
        assert hook_module._has_shell_expansion_syntax("$T") is True

    def test_backtick(self):
        assert hook_module._has_shell_expansion_syntax("`pwd`") is True

    def test_tilde(self):
        assert hook_module._has_shell_expansion_syntax("~/x") is True

    def test_plain_absolute_path_false(self):
        assert hook_module._has_shell_expansion_syntax("/Users/x/repo") is False

    def test_empty_false(self):
        assert hook_module._has_shell_expansion_syntax("") is False
