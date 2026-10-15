#!/usr/bin/env python3
"""
git_command_parse 模組單元測試（0.2.1-W3-708）

驗證項目：
1. strip_heredoc_bodies：本體剝離 + 找不到收尾界線時的保底還原
2. normalize_newlines_to_separators：換行轉語句分隔符，引號內換行不受影響
3. is_literal_pathspec_token：廣域 pathspec 判定（. / ./ / :/ / 萬用字元 / 尾斜線）
4. is_shell_redirection_token：重導向 token 辨識
5. find_git_invocations：
   - 失敗語意：None（無法 tokenize）vs []（可解析但無命中）明確區分
   - 前綴包裹穿透：sudo / nohup / time / xargs / env KEY=VAL / 裸 KEY=VAL
   - git 全域選項穿透：-c / --git-dir / --work-tree 等，-C 特別擷取
   - 子命令別名：stage -> add
   - 多語句（&&/;/|/||/()）各自命中
   - heredoc 內文與引號內容不誤判為真實呼叫
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.git_command_parse import (
    contains_git_word,
    strip_heredoc_bodies,
    normalize_newlines_to_separators,
    is_literal_pathspec_token,
    is_shell_redirection_token,
    find_git_invocations,
    GitInvocation,
)


class TestContainsGitWord:
    def test_git_word_present(self):
        assert contains_git_word("git commit -m x") is True

    def test_empty_command(self):
        assert contains_git_word("") is False

    def test_no_git_word(self):
        assert contains_git_word("pytest tests/") is False

    def test_word_boundary_not_substring(self):
        assert contains_git_word("echo legit commit message") is False


class TestStripHeredocBodies:
    def test_no_heredoc_marker_unchanged(self):
        assert strip_heredoc_bodies("git commit -m x") == "git commit -m x"

    def test_single_quoted_delimiter_stripped(self):
        command = "cat <<'EOF'\nsome content\nEOF\n"
        result = strip_heredoc_bodies(command)
        assert "some content" not in result
        assert "<<'EOF'" in result

    def test_unquoted_delimiter_stripped(self):
        command = "cat <<EOF\nsome content\nEOF\n"
        result = strip_heredoc_bodies(command)
        assert "some content" not in result

    def test_dash_delimiter_stripped(self):
        command = "cat <<-EOF\n\tsome content\nEOF\n"
        result = strip_heredoc_bodies(command)
        assert "some content" not in result

    def test_missing_end_delimiter_rolls_back_unchanged(self):
        """找不到收尾界線行時，保底還原整段原文，不做任何剝離。"""
        command = "cat <<'EOF'\nsome content without closing delimiter\n"
        assert strip_heredoc_bodies(command) == command

    def test_multiple_heredocs_both_stripped(self):
        command = "cat <<'A'\nfirst\nA\ncat <<'B'\nsecond\nB\n"
        result = strip_heredoc_bodies(command)
        assert "first" not in result
        assert "second" not in result


class TestNormalizeNewlinesToSeparators:
    def test_bare_newline_becomes_separator(self):
        result = normalize_newlines_to_separators("git add a\ngit commit -m x")
        assert "\n" not in result
        assert " ; " in result

    def test_newline_inside_single_quotes_preserved(self):
        result = normalize_newlines_to_separators("echo 'line1\nline2'")
        assert "\n" in result

    def test_newline_inside_double_quotes_preserved(self):
        result = normalize_newlines_to_separators('echo "line1\nline2"')
        assert "\n" in result


class TestIsLiteralPathspecToken:
    def test_dot_is_broad(self):
        assert is_literal_pathspec_token(".") is False

    def test_dot_slash_is_broad(self):
        assert is_literal_pathspec_token("./") is False

    def test_colon_slash_is_broad(self):
        assert is_literal_pathspec_token(":/") is False

    def test_glob_is_broad(self):
        assert is_literal_pathspec_token("src/*.py") is False
        assert is_literal_pathspec_token("file?.py") is False
        assert is_literal_pathspec_token("[abc].py") is False

    def test_trailing_slash_directory_is_broad(self):
        assert is_literal_pathspec_token("src/") is False

    def test_literal_file_path_is_not_broad(self):
        assert is_literal_pathspec_token("src/foo.py") is True
        assert is_literal_pathspec_token("README.md") is True


class TestIsShellRedirectionToken:
    def test_simple_redirect(self):
        assert is_shell_redirection_token(">") is True
        assert is_shell_redirection_token(">>") is True

    def test_fd_redirect(self):
        assert is_shell_redirection_token("2>&1") is True

    def test_literal_path_not_redirect(self):
        assert is_shell_redirection_token("src/foo.py") is False


class TestFindGitInvocationsFailureSemantics:
    def test_unbalanced_quote_returns_none(self):
        result = find_git_invocations('git commit -m "unterminated', {"commit"})
        assert result is None

    def test_no_match_returns_empty_list_not_none(self):
        result = find_git_invocations("pytest tests/ -q", {"commit"})
        assert result == []

    def test_empty_command_returns_empty_list(self):
        assert find_git_invocations("", {"commit"}) == []


class TestFindGitInvocationsBasic:
    def test_simple_commit(self):
        result = find_git_invocations('git commit -m "x"', {"commit"})
        assert len(result) == 1
        inv = result[0]
        assert inv.subcommand == "commit"
        assert inv.dash_c_path is None
        assert inv.args == ["-m", "x"]

    def test_dash_c_captured(self):
        result = find_git_invocations("git -C /repo commit -m x", {"commit"})
        assert len(result) == 1
        assert result[0].dash_c_path == "/repo"
        assert result[0].args == ["-m", "x"]

    def test_non_matching_subcommand_not_returned(self):
        result = find_git_invocations("git status", {"commit"})
        assert result == []

    def test_add_not_matched_when_only_commit_requested(self):
        result = find_git_invocations("git add foo.py", {"commit"})
        assert result == []


class TestFindGitInvocationsSubcommandAlias:
    def test_stage_alias_matches_add_request(self):
        result = find_git_invocations("git stage foo.py", {"add"})
        assert len(result) == 1
        assert result[0].subcommand == "add"

    def test_add_literal_also_matches(self):
        result = find_git_invocations("git add foo.py", {"add"})
        assert len(result) == 1
        assert result[0].subcommand == "add"


class TestFindGitInvocationsPrefixWrappers:
    def test_sudo_prefix_skipped(self):
        result = find_git_invocations("sudo git commit -m x", {"commit"})
        assert len(result) == 1
        assert result[0].subcommand == "commit"
        # statement 保留完整原文供訊息顯示
        assert result[0].statement[0] == "sudo"

    def test_nohup_prefix_skipped(self):
        result = find_git_invocations("nohup git commit -m x", {"commit"})
        assert len(result) == 1

    def test_time_prefix_skipped(self):
        result = find_git_invocations("time git commit -m x", {"commit"})
        assert len(result) == 1

    def test_xargs_prefix_skipped(self):
        result = find_git_invocations("xargs git commit -m x", {"commit"})
        assert len(result) == 1

    def test_env_with_assignments_skipped(self):
        result = find_git_invocations("env FOO=bar BAZ=qux git commit -m x", {"commit"})
        assert len(result) == 1

    def test_bare_env_assignment_skipped(self):
        result = find_git_invocations("FOO=bar git commit -m x", {"commit"})
        assert len(result) == 1


class TestFindGitInvocationsGlobalOptions:
    def test_dash_c_option_skipped(self):
        result = find_git_invocations('git -c user.name=x commit -m "y"', {"commit"})
        assert len(result) == 1
        assert result[0].args == ["-m", "y"]

    def test_git_dir_option_equals_form_skipped(self):
        """`--git-dir=<path>` 單一 token（含等號）形式亦須正確跳過。"""
        result = find_git_invocations("git --git-dir=/repo/.git commit -m x", {"commit"})
        assert len(result) == 1
        assert result[0].subcommand == "commit"
        assert result[0].args == ["-m", "x"]

    def test_git_dir_option_space_form_skipped(self):
        result = find_git_invocations("git --git-dir /repo/.git commit -m x", {"commit"})
        assert len(result) == 1
        assert result[0].args == ["-m", "x"]

    def test_no_pager_option_skipped(self):
        result = find_git_invocations("git --no-pager commit -m x", {"commit"})
        assert len(result) == 1
        assert result[0].args == ["-m", "x"]


class TestFindGitInvocationsMultiStatement:
    def test_and_and_separator(self):
        result = find_git_invocations("git add foo.py && git commit -m x", {"commit"})
        assert len(result) == 1
        assert result[0].args == ["-m", "x"]

    def test_semicolon_separator(self):
        result = find_git_invocations("git status; git commit -m x", {"commit"})
        assert len(result) == 1

    def test_both_add_and_commit_found_when_both_requested(self):
        result = find_git_invocations(
            "git add foo.py && git commit -m x", {"add", "commit"}
        )
        assert len(result) == 2
        subcommands = {inv.subcommand for inv in result}
        assert subcommands == {"add", "commit"}

    def test_subshell_parens_flattened(self):
        result = find_git_invocations("(cd /repo && git commit -m x)", {"commit"})
        assert len(result) == 1


class TestFindGitInvocationsPayloadNotMisdetected:
    def test_heredoc_body_mentioning_commit_not_matched(self):
        command = (
            'ticket track append-log X --section "Y" '
            '"$(cat <<\'EOF\'\n'
            "描述 git commit 相關文字\n"
            "EOF\n"
            ')")'
        )
        result = find_git_invocations(command, {"commit"})
        assert result == []

    def test_quoted_message_content_not_matched_as_separate_invocation(self):
        result = find_git_invocations(
            'some-cli --why "please avoid git commit here"', {"commit"}
        )
        assert result == []


def test_git_invocation_args_property():
    inv = GitInvocation(
        statement=["git", "commit", "-m", "x"],
        subcommand="commit",
        subcommand_index=1,
        dash_c_path=None,
    )
    assert inv.args == ["-m", "x"]


# ============================================================================
# 0.5.0-W1-120.7.1：包裝命令、巢狀 shell、別名、有效目錄
# ============================================================================

import shlex
import subprocess

import pytest

import lib.git_command_parse as gcp


def _subs(command, base_dir=None, wanted=("commit",)):
    result = find_git_invocations(command, set(wanted), base_dir=base_dir)
    assert result is not None
    return result


@pytest.mark.parametrize(
    "command",
    [
        "/usr/bin/git commit -m x",
        "command git commit -m x",
        "command -p git commit -m x",
        "exec git commit -m x",
        "bash -c 'git commit -m x'",
        "sh -c \"git commit -m x\"",
        "zsh -c 'git commit -m x'",
        "bash -lc 'git commit -m x'",
        "/bin/bash -c 'git commit -m x'",
        "eval 'git commit -m x'",
        "eval git commit -m x",
        "bash -c \"bash -c 'git commit -m x'\"",
        "sudo bash -c 'true && git commit -m x'",
    ],
)
def test_wrapped_commit_detected(command):
    invs = _subs(command)
    assert [i.subcommand for i in invs] == ["commit"]


@pytest.mark.parametrize(
    "command",
    [
        "echo git commit",
        "echo '/usr/bin/git commit'",
        "echo \"bash -c 'git commit'\"",
        "bash -c 'echo git commit'",
        "eval 'echo git commit'",
        "command -v git commit",
        "bash script.sh git commit",
        "printf '%s' 'eval git commit'",
    ],
)
def test_text_mentioning_commit_not_detected(command):
    assert _subs(command) == []


def test_nesting_depth_is_bounded():
    cmd = "git commit -m x"
    for _ in range(8):
        cmd = "bash -c " + shlex.quote(cmd)
    assert find_git_invocations(cmd, {"commit"}) is None  # 超過深度上限：與頂層無法解析同形


class TestEffectiveDir:
    def test_defaults_when_nothing_changes(self):
        inv = _subs("git commit -m x")[0]
        assert (inv.effective_dir, inv.dir_unknown, inv.dash_c_paths) == (None, False, ())

    def test_base_dir_returned_when_nothing_changes(self):
        assert _subs("git commit", base_dir="/base")[0].effective_dir == "/base"

    def test_dash_c_chain_joins_relative_paths(self):
        inv = _subs("git -C a -C b commit")[0]
        assert inv.dash_c_path == "a"
        assert inv.dash_c_paths == ("a", "b")
        assert inv.effective_dir == "a/b"

    def test_absolute_dash_c_replaces(self):
        assert _subs("git -C a -C /x commit")[0].effective_dir == "/x"

    def test_cd_then_git(self):
        assert _subs("cd /repo && git commit")[0].effective_dir == "/repo"

    def test_cd_relative_to_base(self):
        inv = _subs("cd sub && git -C inner commit", base_dir="/base")[0]
        assert inv.effective_dir == "/base/sub/inner"

    def test_cd_in_subshell_does_not_leak(self):
        inv = _subs("(cd /other && git status); git commit", base_dir="/base")[0]
        assert inv.effective_dir == "/base"

    def test_cd_inside_subshell_applies_within(self):
        assert _subs("(cd /other && git commit)")[0].effective_dir == "/other"

    def test_cd_in_pipeline_does_not_leak(self):
        assert _subs("cd /other | cat; git commit", base_dir="/base")[0].effective_dir == "/base"

    def test_cd_inside_bash_c_does_not_leak(self):
        inv = _subs("bash -c 'cd /other'; git commit", base_dir="/base")[0]
        assert inv.effective_dir == "/base"

    def test_cd_inside_bash_c_applies_within(self):
        assert _subs("bash -c 'cd /other && git commit'")[0].effective_dir == "/other"

    @pytest.mark.parametrize(
        "command",
        [
            "cd $X && git commit",
            "cd `pwd`/x && git commit",
            "git -C $DIR commit",
            "cd - && git commit",
            "cd && git commit",
            "cd /a || git commit",
            "false || cd /a; git commit",
            "popd; git commit",
        ],
    )
    def test_dynamic_directory_marks_unknown(self, command):
        inv = _subs(command)[0]
        assert inv.dir_unknown is True
        assert inv.effective_dir is None

    def test_echo_cd_does_not_change_dir(self):
        assert _subs("echo cd /other; git commit", base_dir="/base")[0].effective_dir == "/base"


class TestAliasExpansion:
    def _patch(self, monkeypatch, table):
        calls = []

        def fake(directory, name):
            calls.append((directory, name))
            return table.get(name)

        monkeypatch.setattr(gcp, "_read_git_alias", fake)
        return calls

    def test_simple_alias_hits(self, monkeypatch):
        self._patch(monkeypatch, {"ci": "commit"})
        inv = _subs("git ci -m x")[0]
        assert inv.subcommand == "commit"
        assert inv.args == ["-m", "x"]

    def test_alias_with_default_flags_visible_in_args(self, monkeypatch):
        self._patch(monkeypatch, {"ci": "commit -a"})
        assert "-a" in _subs("git ci -m x")[0].args

    def test_alias_chain(self, monkeypatch):
        self._patch(monkeypatch, {"ci": "co2", "co2": "commit"})
        assert len(_subs("git ci")) == 1

    def test_alias_loop_terminates(self, monkeypatch):
        self._patch(monkeypatch, {"a": "b", "b": "a"})
        assert find_git_invocations("git a", {"commit"}) is None

    def test_alias_lookup_uses_effective_dir(self, monkeypatch):
        calls = self._patch(monkeypatch, {"ci": "commit"})
        _subs("cd /repo && git ci", base_dir="/base")
        assert calls[0] == ("/repo", "ci")

    def test_unrelated_alias_not_hit(self, monkeypatch):
        self._patch(monkeypatch, {"st": "status"})
        assert _subs("git st") == []

    def test_builtin_never_looked_up(self, monkeypatch):
        calls = self._patch(monkeypatch, {})
        _subs("git status")
        assert calls == []

    def test_shell_alias_hit_is_marked_unknown(self, monkeypatch):
        self._patch(monkeypatch, {"go": "!git commit -m x"})
        inv = _subs("git go")[0]
        assert (inv.dir_unknown, inv.effective_dir) == (True, None)

    def test_shell_alias_without_git_commit_not_hit(self, monkeypatch):
        self._patch(monkeypatch, {"go": "!echo hi"})
        assert _subs("git go") == []

    def test_alias_read_failure_does_not_raise(self, monkeypatch):
        def boom(*args, **kwargs):
            raise OSError("no git")

        monkeypatch.setattr(gcp.subprocess, "run", boom)
        assert _subs("git ci -m x") == []

    def test_real_git_config_alias(self, tmp_path):
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
        subprocess.run(["git", "-C", str(tmp_path), "config", "alias.ci", "commit"], check=True)
        invs = _subs(f"git -C {tmp_path} ci -m x")
        assert [i.subcommand for i in invs] == ["commit"]
        assert invs[0].effective_dir == str(tmp_path)

    def test_mutation_without_alias_expansion_misses(self, monkeypatch):
        """變異確認：別名讀取永遠回 None 時，正向對照輸入必須變為漏判。"""
        self._patch(monkeypatch, {})
        assert _subs("git ci -m x") == []


def test_mutation_without_nested_script_support_misses(monkeypatch):
    """變異確認：停用巢狀 shell 解析時，bash -c 正向對照輸入必須漏判。"""
    monkeypatch.setattr(gcp, "_nested_script", lambda statement, idx: None)
    assert _subs("bash -c 'git commit -m x'") == []
    assert _subs("git commit -m x") != []


class TestUnparseableIsNone:
    """0.5.0-W1-120.7.1 審查修正：巢狀與別名的無法解析一律回 None（同頂層 tokenize 失敗）。"""

    def test_nested_tokenize_failure_is_none(self):
        assert find_git_invocations("bash -c \"git commit -m 'x\"", {"commit"}) is None

    def test_nested_ok_control_is_list(self):
        assert find_git_invocations("bash -c \"git commit -m 'x'\"", {"commit"}) is not None

    def test_alias_lookup_cap_is_none(self, monkeypatch):
        monkeypatch.setattr(gcp, "_read_git_alias", lambda d, n: None)
        many = "; ".join(f"git zz{i} x" for i in range(gcp._MAX_ALIAS_LOOKUPS + 1))
        assert find_git_invocations(many, {"commit"}) is None

    def test_alias_lookup_under_cap_is_list(self, monkeypatch):
        monkeypatch.setattr(gcp, "_read_git_alias", lambda d, n: None)
        few = "; ".join(f"git zz{i} x" for i in range(gcp._MAX_ALIAS_LOOKUPS))
        assert find_git_invocations(few, {"commit"}) == []

    def test_alias_lookup_is_cached(self, monkeypatch):
        calls = []
        monkeypatch.setattr(gcp, "_read_git_alias", lambda d, n: calls.append(n))
        same = "; ".join("git zz x" for _ in range(30))
        assert find_git_invocations(same, {"commit"}) == []
        assert len(calls) == 1

    def test_alias_total_time_budget_is_none(self, monkeypatch):
        monkeypatch.setattr(gcp, "_read_git_alias", lambda d, n: None)
        clock = iter(range(0, 1000, 5))
        monkeypatch.setattr(gcp.time, "monotonic", lambda: next(clock))
        assert find_git_invocations("git aa x; git bb x", {"commit"}) is None

    def test_alias_timeout_is_none(self, monkeypatch):
        def slow(*args, **kwargs):
            raise subprocess.TimeoutExpired("git", 1)

        monkeypatch.setattr(gcp.subprocess, "run", slow)
        assert find_git_invocations("git ci -m x", {"commit"}) is None

    def test_mutation_without_cap_returns_list(self, monkeypatch):
        """變異確認：上限放寬後，超限輸入不再回 None（證明測試鑑別力）。"""
        monkeypatch.setattr(gcp, "_read_git_alias", lambda d, n: None)
        monkeypatch.setattr(gcp, "_MAX_ALIAS_LOOKUPS", 1000)
        many = "; ".join(f"git zz{i} x" for i in range(9))
        assert find_git_invocations(many, {"commit"}) == []

    def test_mutation_nested_failure_swallowed_returns_list(self, monkeypatch):
        """變異確認：舊行為（巢狀失敗回空）會使上面的 None 斷言翻紅。"""
        original = gcp._scan_script

        def swallowing(script, state, depth, ctx):
            try:
                return original(script, state, depth, ctx)
            except gcp._Unparseable:
                return []

        monkeypatch.setattr(gcp, "_scan_script", swallowing)
        assert find_git_invocations("bash -c \"git commit -m 'x\"", {"commit"}) == []


# ===== match_git_commit（三態 commit 判定，0.5.0-W1-120.7.7）=====

import lib.git_command_parse as _gcp  # noqa: E402
from lib.git_command_parse import match_git_commit  # noqa: E402


def test_match_git_commit_dash_c_hits():
    assert match_git_commit("git -C x commit -m y") is True


def test_match_git_commit_echo_not_hit():
    assert match_git_commit("echo git commit") is False


def test_match_git_commit_no_git_word_not_hit():
    assert match_git_commit("npm test") is False
    assert match_git_commit("") is False


def test_match_git_commit_non_commit_subcommand_not_hit():
    assert match_git_commit("git log --oneline") is False


def test_match_git_commit_amend_excluded_by_default():
    assert match_git_commit("git commit --amend") is False
    assert match_git_commit("git commit --amend", exclude_amend=False) is True


def test_match_git_commit_amend_with_other_commit_hits():
    assert match_git_commit("git commit --amend && git commit -m y") is True


def test_match_git_commit_unparseable_is_none():
    result = match_git_commit("git commit -m 'unclosed")
    assert result is None  # 區分於 False


def test_match_git_commit_discriminates_when_parser_mutated(monkeypatch):
    """變異確認：解析器失效時正反向輸入都會翻轉，證明測試有鑑別力。"""
    monkeypatch.setattr(_gcp, "find_git_invocations", lambda *a, **k: [])
    assert match_git_commit("git -C x commit -m y") is not True
    monkeypatch.undo()
    monkeypatch.setattr(
        _gcp,
        "find_git_invocations",
        lambda *a, **k: [_gcp.GitInvocation.__new__(_gcp.GitInvocation)],
    )
    # 恆回非空：amend 排除路徑讀 inv.args，以 exclude_amend=False 驗反向輸入被誤判為命中
    assert match_git_commit("echo git commit", exclude_amend=False) is True


# ===== 控制結構、背景符號、前綴命令、行內別名（0.5.0-W1-120.7.5）=====

_CONTROL_AND_PREFIX_POSITIVE = [
    "{ git commit -m x; }",
    "true & git commit -m x",
    "git status & git commit -m x",
    "if true; then git commit -m x; fi",
    "if git diff --quiet; then :; else git commit -m x; fi",
    "if false; then :; elif true; then git commit -m x; fi",
    "for f in a b; do git commit -m x; done",
    "while true; do git commit -m x; done",
    "until false; do git commit -m x; done",
    "nice git commit -m x",
    "nice -n 5 git commit -m x",
    "nice -5 git commit -m x",
    "timeout 5 git commit -m x",
    "timeout -k 1 -s TERM 5 git commit -m x",
    "stdbuf -oL git commit -m x",
    "stdbuf -o L git commit -m x",
    "caffeinate git commit -m x",
    "caffeinate -t 60 git commit -m x",
    "sudo -u me git commit -m x",
    "sudo -n git commit -m x",
    "env -i git commit -m x",
    "env -u FOO BAR=1 git commit -m x",
    "builtin command git commit -m x",
    "git -C. commit -m x",
    "git -C/tmp/r commit -m x",
    "git -c alias.ci=commit ci -m x",
]

_CONTROL_AND_PREFIX_NEGATIVE = [
    "echo git commit -m x",
    "echo 'if true; then git commit; fi'",
    "echo 'nice git commit'",
    "echo \"true & git commit\"",
    "for git in a b; do echo $git; done",
    "if true; then echo hi; fi",
    "nice -n 5 ls",
    "timeout 5 ls",
    "git -c alias.ci=commit status",
    "git -c alias.ci=log ci",
]


@pytest.mark.parametrize("command", _CONTROL_AND_PREFIX_POSITIVE)
def test_control_structure_and_prefix_forms_detected(command):
    found = _subs(command)
    assert [inv.subcommand for inv in found] == ["commit"]


@pytest.mark.parametrize("command", _CONTROL_AND_PREFIX_NEGATIVE)
def test_control_structure_and_prefix_negative_controls(command):
    assert _subs(command) == []


def test_while_condition_git_call_detected():
    assert len(_subs("while git commit -m x; do :; done")) == 1


def test_dash_c_glued_path_recorded():
    inv = _subs("git -C/tmp/r commit -m x")[0]
    assert inv.dash_c_paths == ("/tmp/r",)
    assert inv.effective_dir == "/tmp/r"


def test_inline_alias_beats_config_and_skips_lookup(monkeypatch):
    monkeypatch.setattr(gcp, "_read_git_alias", lambda d, n: pytest.fail("不應查設定檔"))
    assert len(_subs("git -c alias.ci=commit ci -m x")) == 1


def test_inline_alias_cannot_shadow_builtin():
    assert _subs("git -c alias.commit=log commit -m x") != []


def test_cd_after_control_keyword_affects_effective_dir():
    inv = _subs("if true; then cd /a; git commit -m x; fi")[0]
    assert inv.effective_dir == "/a"


def test_background_cd_does_not_leak():
    inv = _subs("cd /a & git commit -m x", base_dir="/base")[0]
    assert inv.effective_dir == "/base"


@pytest.mark.parametrize(
    "command",
    [
        "bash <<< 'git commit -m x'",
        "echo 'git commit -m x' | bash",
        "echo x | sudo sh",
        "cat s | bash -s",
    ],
)
def test_stdin_shell_forms_are_none(command):
    assert find_git_invocations(command, {"commit"}) is None
    if "git" in command:  # match_git_commit 先以 git 字樣短路，無字樣者不進解析
        assert match_git_commit(command) is None


@pytest.mark.parametrize(
    "command",
    [
        "echo 'git commit' | cat",
        "echo x | bash script.sh",
        "echo x | bash -c 'ls'",
        "bash -c 'git commit -m x' <<< y",
    ],
)
def test_stdin_shell_negative_controls_not_none(command):
    assert find_git_invocations(command, {"commit"}) is not None


def test_mutation_without_background_separator_misses(monkeypatch):
    """變異確認：移除 & 分隔符後，背景符號正向輸入必須漏判。"""
    monkeypatch.setattr(gcp, "_STATEMENT_SEPARATORS", gcp._STATEMENT_SEPARATORS - {"&"})
    assert _subs("true & git commit -m x") == []


def test_mutation_without_control_keywords_misses(monkeypatch):
    """變異確認：控制關鍵字清單清空後，控制結構正向輸入必須漏判。"""
    monkeypatch.setattr(gcp, "_CONTROL_KEYWORDS", frozenset())
    assert _subs("if true; then git commit -m x; fi") == []
    assert _subs("{ git commit -m x; }") == []


def test_mutation_without_wrapper_options_misses(monkeypatch):
    """變異確認：前綴選項表清空後，帶選項前綴正向輸入必須漏判。"""
    monkeypatch.setattr(
        gcp, "_WRAPPER_VALUE_OPTIONS", {k: frozenset() for k in gcp._WRAPPER_VALUE_OPTIONS}
    )
    assert _subs("sudo -u me git commit -m x") == []
    assert _subs("nice -n 5 git commit -m x") == []


_ROUND2_POSITIVE = [
    "echo `git commit -m x`",
    "x=`git commit -m x`",
    "echo \"`git commit -m x`\"",
    "! git commit -m x",
    "coproc git commit -m x",
    "function f { git commit -m x; }",
    "time -p git commit -m x",
    "env -S 'git commit -m x'",
    "env -i -S'git commit -m x'",
    "env --split-string='git commit -m x'",
    "doas git commit -m x",
    "doas -u me git commit -m x",
    "flock /tmp/l git commit -m x",
    "flock -w 5 /tmp/l git commit -m x",
    "flock /tmp/l -c 'git commit -m x'",
    "chronic git commit -m x",
    "chronic -e git commit -m x",
    "watch git commit -m x",
    "watch -n 5 'git commit -m x'",
]

_ROUND2_NEGATIVE = [
    "echo '`git commit -m x`'",
    "echo \"! git commit\"",
    "echo 'function f { git commit; }'",
    "echo `date`",
    "echo \"`date`\"",
    "time -p ls",
    "env -S 'ls -l'",
    "doas ls",
    "flock /tmp/l ls",
    "flock /tmp/l -c 'ls'",
    "chronic ls",
    "watch -n 5 ls",
    "echo watch git commit",
]


@pytest.mark.parametrize("command", _ROUND2_POSITIVE)
def test_round2_forms_detected(command):
    assert [inv.subcommand for inv in _subs(command)] == ["commit"]


@pytest.mark.parametrize("command", _ROUND2_NEGATIVE)
def test_round2_negative_controls(command):
    assert _subs(command) == []


def test_mutation_without_backtick_spacing_misses(monkeypatch):
    """變異確認：不取反引號本體時，反引號正向輸入必須漏判。"""
    monkeypatch.setattr(gcp, "extract_backtick_bodies", lambda command: [])
    assert _subs("echo `git commit -m x`") == []


def test_mutation_without_string_wrappers_misses(monkeypatch):
    """變異確認：停用字串命令包裹解析後，env -S／flock -c／watch 正向輸入必須漏判。"""
    monkeypatch.setattr(gcp, "_wrapper_script", lambda tokens, idx: None)
    assert _subs("env -S 'git commit -m x'") == []
    assert _subs("flock /tmp/l -c 'git commit -m x'") == []
    assert _subs("watch 'git commit -m x'") == []


def test_mutation_without_new_control_words_misses(monkeypatch):
    """變異確認：清空控制關鍵字後，`!`／coproc／function 正向輸入必須漏判。"""
    monkeypatch.setattr(gcp, "_CONTROL_KEYWORDS", frozenset({"{", "}"}))
    assert _subs("! git commit -m x") == []
    assert _subs("coproc git commit -m x") == []


def test_mutation_without_stdin_shell_check_returns_list(monkeypatch):
    """變異確認：停用 stdin shell 判定後，pipe 與 here-string 輸入不再回 None。"""
    monkeypatch.setattr(gcp, "_is_stdin_shell", lambda statement, idx: False)
    assert find_git_invocations("echo x | bash", {"commit"}) == []
    assert find_git_invocations("bash <<< x", {"commit"}) == []


# ===== 註解處理（0.5.0-W1-120.7.9.4）=====


def _commits(command):
    return find_git_invocations(command, {"commit"})


_POSITIVE_COMMENT_CASES = [
    "# 前導註解\ngit commit -m x",
    "git status # 行尾註解\ngit commit -m x",
    "git status\n# 中段註解\ngit status\ngit commit -m x",
]


@pytest.mark.parametrize("command", _POSITIVE_COMMENT_CASES)
def test_comment_does_not_swallow_following_commit(command):
    assert len(_commits(command)) == 1


@pytest.mark.parametrize(
    "command",
    ["# git commit -m x", "git status # git commit -m x", "echo a\n# git commit\necho b"],
)
def test_commit_text_inside_comment_not_matched(command):
    assert _commits(command) == []


def test_hash_in_quotes_is_not_comment():
    assert len(_commits("echo '# x'; git commit -m \"a # b\"")) == 1
    assert gcp.strip_line_comments("echo '# x' \"# y\"") == "echo '# x' \"# y\""


def test_hash_inside_word_is_not_comment():
    assert len(_commits("echo a#b; git commit -m x")) == 1


def test_mutation_comment_to_end_of_command_misses(monkeypatch):
    """變異確認：註解延伸到命令結尾（原缺陷）時，三種位置的正向輸入必須漏判。"""
    monkeypatch.setattr(gcp, "strip_line_comments", lambda c: c.split("#")[0])
    for command in _POSITIVE_COMMENT_CASES:
        assert _commits(command) == []


def test_mutation_without_comment_strip_matches_comment_text(monkeypatch):
    """變異確認：註解不被當註解（僅去掉 # 字元）時，註解內的 git commit 字樣必須被誤判。"""
    monkeypatch.setattr(gcp, "strip_line_comments", lambda c: c.replace("#", ""))
    assert len(_commits("# git commit -m x")) == 1


# ===== 行接續與註解（0.5.0-W1-120.7.9.4）=====

_CONT = "\\\n"  # 反斜線加換行


def test_line_continuation_makes_hash_in_word_not_comment():
    """行接續後為 `echo a#x`，# 在詞中不是註解，commit 會執行。"""
    assert len(_commits(f"echo a{_CONT}#x; git commit -m x")) == 1


def test_line_continuation_after_space_keeps_comment():
    """行接續後 # 前為空白，屬註解，commit 不執行。"""
    assert _commits(f"echo a {_CONT}#x; git commit -m x") == []


def test_multiple_line_continuations_merge():
    assert len(_commits(f"echo a{_CONT}{_CONT}#x; git commit -m x")) == 1
    assert _commits(f"echo a {_CONT}{_CONT}#x; git commit -m x") == []


def test_line_continuation_in_double_quotes_is_merged():
    assert gcp.strip_line_comments(f'echo "a{_CONT}b"') == 'echo "ab"'
    assert len(_commits(f'echo "a{_CONT}#b"; git commit -m x')) == 1


def test_escaped_backslash_before_newline_is_not_continuation():
    """雙反斜線加換行：反斜線被跳脫，換行是真換行，下一行 # 為註解。"""
    assert _commits("echo a\\\\\n#x; git commit -m x") == []


def test_backslash_newline_in_single_quotes_preserved():
    command = f"echo 'a{_CONT}b'; git commit -m x"
    assert gcp.strip_line_comments(command) == command
    assert len(_commits(command)) == 1


def test_mutation_without_line_continuation_handling_misses(monkeypatch):
    """變異確認：移除行接續處理後，繞過案例正向輸入必須翻回 0 筆。"""
    import inspect

    source = inspect.getsource(gcp.strip_line_comments)
    start = source.index('            if ch == "\\n":\n                # 行接續')
    end = source.index("                continue\n", start) + len("                continue\n")
    namespace = dict(vars(gcp))
    exec(source[:start] + source[end:], namespace)
    monkeypatch.setattr(gcp, "strip_line_comments", namespace["strip_line_comments"])
    assert _commits(f"echo a{_CONT}#x; git commit -m x") == []


# ===== scan 模式（0.5.0-W1-120.7.9.1） =====

_SCAN_SUBS = {"commit", "add"}

# 本機會執行 git 寫入的命令（120.7.9 分析的正向輸入）
_SCAN_POSITIVE = [
    "xargs -I{} git commit -m x", "echo a | xargs -I{} git commit -m {}",
    "find . -name x -exec git commit -m x {} \\;", "find . -exec sh -c 'git commit -m x' \\;",
    "parallel git commit -m x ::: a b", "xargs -0 git add", "time -p git commit -m x",
    "! git commit -m x", "coproc git commit -m x", "doas git commit -m x",
    "flock /tmp/l git commit -m x", "chronic git commit -m x", "watch git commit -m x",
    "env -S 'git commit -m x'", "`git commit -m x`", "echo $(git commit -m x)",
    "{ git commit -m x; }", "true & git commit -m x", "if true; then git commit -m x; fi",
    "for i in 1; do git commit -m x; done", "nice git commit -m x", "timeout 5 git commit -m x",
    "stdbuf -oL git commit -m x", "caffeinate git commit -m x", "sudo -u me git commit -m x",
    "env -i git commit -m x", "builtin command git commit -m x",
    "git -c alias.ci=commit ci -m x", "git -C. commit -m x", "setsid git commit -m x",
    "unbuffer git commit -m x", "ionice -c3 git commit -m x", "taskset 1 git commit -m x",
    "numactl -C 0 git commit -m x", "strace -f git commit -m x",
    "systemd-run --user git commit -m x", "xargs sh -c 'git commit -m x'",
    "/usr/bin/env git commit -m x", "busybox git commit -m x", "chroot / git commit -m x",
    "exec -a foo git commit -m x", "command time git commit -m x",
    "gtimeout 5 git commit -m x", "arch -arm64 git commit -m x", "dtruss git commit -m x",
    "unshare -m git commit -m x", "ssh-agent git commit -m x",
    "cat f | while read x; do git commit -m $x; done", "git status && git commit -m x",
    "(cd sub && git commit -m x)", "git commit -m x | tee log", "tee >(git commit -m x) </dev/null",
]

# 不應命中：輸出文字、查詢、heredoc、引號內、註解、非寫入
_SCAN_NEGATIVE = [
    "echo git commit", "printf '%s' git commit", "echo 'git commit'", "command -v git commit",
    "ls # git commit", "cat <<'EOF'\ngit commit -m x\nEOF",
    "ticket track append-log T --section S \"git commit\"", "ls .git/commit",
    "cd git && commit", "git status", "git log --oneline", "echo x | grep git",
    "echo done; git status", "echo \"git add\"",
]

# 掃描設計上的已知漏判（字串腳本載體與 echo 引號內命令替換）
_SCAN_KNOWN_MISSES = [
    "su -c 'git commit -m x'", "script -q -c 'git commit -m x' /dev/null",
    "sg staff -c 'git commit -m x'", "echo \"$(git commit -m x)\"",
]


def _hit(command, scan):
    return bool(gcp.find_git_invocations(command, _SCAN_SUBS, scan=scan))


def test_scan_positive_inputs_each_hit():
    for command in _SCAN_POSITIVE:
        assert _hit(command, True), command


def test_scan_hit_count_meets_floor():
    hits = sum(_hit(c, True) for c in _SCAN_POSITIVE + _SCAN_KNOWN_MISSES)
    assert len(_SCAN_POSITIVE) + len(_SCAN_KNOWN_MISSES) >= 55 and hits >= 52


def test_scan_negative_inputs_do_not_hit():
    for command in _SCAN_NEGATIVE:
        assert not _hit(command, True), command


def test_scan_known_misses_stay_missed():
    for command in _SCAN_KNOWN_MISSES:
        assert not _hit(command, True), command


def test_scan_default_false_keeps_position_only_semantics():
    assert _hit("find . -exec sh -c 'git commit -m x' \\;", False) is False
    assert _hit("setsid git commit -m x", False) is False
    assert _hit("git commit -m x", False) is True


def test_scan_false_equals_omitted_argument():
    for command in _SCAN_POSITIVE + _SCAN_NEGATIVE:
        assert gcp.find_git_invocations(command, _SCAN_SUBS) == gcp.find_git_invocations(
            command, _SCAN_SUBS, scan=False
        )


def test_scan_eval_and_watch_not_double_counted():
    assert len(gcp.find_git_invocations("setsid eval git commit -m x", {"commit"}, scan=True)) == 1
    assert len(gcp.find_git_invocations("setsid watch git commit -m x", {"commit"}, scan=True)) == 1


def test_scan_unclosed_quote_still_none():
    assert gcp.find_git_invocations("git commit -m 'x", {"commit"}, scan=True) is None


def test_scan_match_git_commit():
    assert gcp.match_git_commit("setsid git commit -m x") is False
    assert gcp.match_git_commit("setsid git commit -m x", scan=True) is True
    assert gcp.match_git_commit("command -v git commit", scan=True) is False


def test_scan_known_false_positive_argument_position():
    """已記錄的有意誤判：git 作為其他命令的參數。"""
    assert _hit("bash script.sh git commit", True) is True
    assert _hit("bash script.sh git commit", False) is False


def test_mutation_scan_disabled_flips_positives(monkeypatch):
    monkeypatch.setattr(gcp, "_scan_statement", lambda *args, **kwargs: [])
    flipped = [c for c in _SCAN_POSITIVE if not _hit(c, True)]
    assert len(flipped) >= 10  # 掃描失效時僅位置命中者仍命中，其餘必翻紅


def test_mutation_output_exemption_removed_flips_negative(monkeypatch):
    monkeypatch.setattr(gcp, "_SCAN_OUTPUT_COMMANDS", frozenset())
    assert _hit("echo git commit", True) is True


def test_via_scan_false_for_position_hit():
    found = gcp.find_git_invocations("git commit -m x", {"commit"}, scan=True)
    assert [inv.via_scan for inv in found] == [False]
    found = gcp.find_git_invocations("sudo git commit -m x", {"commit"}, scan=True)
    assert [inv.via_scan for inv in found] == [False]


def test_via_scan_true_for_scan_only_hit():
    found = gcp.find_git_invocations("setsid git commit -m x", {"commit"}, scan=True)
    assert [inv.via_scan for inv in found] == [True]


def test_via_scan_false_when_scan_off_and_default_value():
    found = gcp.find_git_invocations("git commit -m x", {"commit"})
    assert [inv.via_scan for inv in found] == [False]
    inv = gcp.GitInvocation(statement=["git", "commit"], subcommand="commit",
                            subcommand_index=1, dash_c_path=None)
    assert inv.via_scan is False


def test_via_scan_flags_mixed_statements_separately():
    found = gcp.find_git_invocations(
        "git commit -m a && setsid git commit -m b", {"commit"}, scan=True
    )
    assert sorted(inv.via_scan for inv in found) == [False, True]


# ===== 無法解析：lib 不寫 stderr、成因分類（0.5.0-W1-120.7.10）=====

_NESTED_UNPARSEABLE = "bash -c \"git commit -m 'unclosed\""


def test_unparseable_writes_no_stderr(capsys, caplog):
    """_Unparseable 路徑回傳 None，且 lib 不得寫 stderr（hook-dispatcher 單行程會重複印出）。"""
    with caplog.at_level("DEBUG", logger="git_command_parse"):
        assert _gcp.find_git_invocations(_NESTED_UNPARSEABLE, {"commit"}, scan=True) is None
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == ""
    assert not [r for r in caplog.records if r.levelno >= 30]


def test_unparseable_mutation_warning_is_detected(monkeypatch, capsys):
    """變異確認：把 debug 改回 warning 並掛 stderr handler，stderr 會有輸出，證明上一測試有鑑別力。"""
    import logging
    import sys

    handler = logging.StreamHandler(sys.stderr)
    _gcp._logger.addHandler(handler)
    monkeypatch.setattr(_gcp._logger, "debug", _gcp._logger.warning)
    try:
        _gcp.find_git_invocations(_NESTED_UNPARSEABLE, {"commit"}, scan=True)
    finally:
        _gcp._logger.removeHandler(handler)
    assert capsys.readouterr().err != ""


def test_classify_parse_cause():
    assert _gcp.classify_parse_cause(None) == _gcp.PARSE_CAUSE_TOKENIZE
    scan_only = _gcp.find_git_invocations("find . -exec git commit -m x \\;", {"commit"}, scan=True)
    assert _gcp.classify_parse_cause(scan_only) == _gcp.PARSE_CAUSE_SCAN_ONLY
    positional = _gcp.find_git_invocations("git commit -m x", {"commit"}, scan=True)
    assert _gcp.classify_parse_cause(positional) is None
    assert _gcp.classify_parse_cause([]) is None


def test_explain_parse_cause_distinguishes():
    assert "非命令位置" in _gcp.explain_parse_cause(_gcp.PARSE_CAUSE_SCAN_ONLY)
    assert "引號" in _gcp.explain_parse_cause(_gcp.PARSE_CAUSE_SCAN_ONLY)
    assert "未閉合引號" in _gcp.explain_parse_cause(_gcp.PARSE_CAUSE_TOKENIZE)
    assert "非命令位置" not in _gcp.explain_parse_cause(_gcp.PARSE_CAUSE_TOKENIZE)
