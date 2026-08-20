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
