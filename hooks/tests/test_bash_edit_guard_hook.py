#!/usr/bin/env python3
"""
Bash Edit Guard Hook - 測試程式碼

涵蓋:
- 裸 cd 偵測各命中形式（行首 / && cd / ; cd / || cd）
- 各排除分支（子 shell (cd ...) / git -C / uv -d / 絕對路徑還原）
- 既有原地編輯偵測 regression（sed -i / perl -pi）
- 非 Bash 工具跳過
"""

import sys
from pathlib import Path

# 將 Hook 腳本路徑加入 sys.path
hook_dir = Path(__file__).parent.parent
sys.path.insert(0, str(hook_dir))

# 動態導入 Hook 模組（移除 .py 副檔名）
import importlib.util

spec = importlib.util.spec_from_file_location(
    "bash_edit_guard_hook_module",
    hook_dir / "bash-edit-guard-hook.py",
)
hook_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook_module)

_detect_bare_cd = hook_module._detect_bare_cd
_detect_bash_edit_patterns = hook_module._detect_bash_edit_patterns

import pytest


# ============================================================================
# 裸 cd 偵測：命中形式
# ============================================================================


class TestBareCdDetectionHits:
    """裸 cd 各命中形式應回傳 True。"""

    def test_leading_cd(self):
        """行首裸 cd 命中。"""
        assert _detect_bare_cd("cd .claude/skills/ticket") is True

    def test_leading_cd_with_chained_command(self):
        """行首裸 cd 後串接命令命中。"""
        assert _detect_bare_cd("cd .claude/skills && uv run pytest") is True

    def test_and_chained_cd(self):
        """&& cd 串接命中。"""
        assert _detect_bare_cd("git status && cd subdir") is True

    def test_semicolon_chained_cd(self):
        """; cd 串接命中。"""
        assert _detect_bare_cd("echo start; cd subdir") is True

    def test_or_chained_cd(self):
        """|| cd 串接命中。"""
        assert _detect_bare_cd("test -d x || cd fallback") is True

    def test_relative_path_cd(self):
        """相對路徑裸 cd 命中（非絕對路徑、非子 shell）。"""
        assert _detect_bare_cd("cd ../sibling && npm test") is True


# ============================================================================
# 裸 cd 偵測：排除分支
# ============================================================================


class TestBareCdDetectionExclusions:
    """各合法形式不應命中（回傳 False）。"""

    def test_subshell_cd(self):
        """子 shell (cd ...) 排除。"""
        assert _detect_bare_cd("(cd .claude/skills/ticket && uv run pytest)") is False

    def test_subshell_cd_with_space(self):
        """子 shell 含空白 ( cd ...) 排除。"""
        assert _detect_bare_cd("( cd subdir && ls )") is False

    def test_git_c_flag(self):
        """git -C <path> 不含 cd 指令，排除。"""
        assert _detect_bare_cd("git -C /Users/tarragon/repo status") is False

    def test_uv_d_flag(self):
        """uv -d <path> 不含 cd 指令，排除。"""
        assert _detect_bare_cd("uv -d .claude/skills/ticket run pytest") is False

    def test_repo_root_restore(self, monkeypatch):
        """還原至專案根 cd /<repo-root> 排除（污染補救合法用途）。"""
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", "/Users/tarragon/Projects/book_overview_v1")
        assert (
            _detect_bare_cd("cd /Users/tarragon/Projects/book_overview_v1 && git status")
            is False
        )

    def test_repo_root_restore_trailing_slash(self, monkeypatch):
        """專案根 trailing slash 正規化後仍排除。"""
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", "/Users/tarragon/Projects/book_overview_v1")
        assert _detect_bare_cd("cd /Users/tarragon/Projects/book_overview_v1/") is False

    def test_no_cd_command(self):
        """完全不含 cd 的命令排除。"""
        assert _detect_bare_cd("git status && npm test") is False

    def test_cdrom_word_not_matched(self):
        """含 cd 字面但非指令（cdrom）不命中。"""
        assert _detect_bare_cd("ls /mnt/cdrom") is False


# ============================================================================
# 裸 cd 偵測：絕對路徑收窄（W1-026）
# 排除條件收窄為「僅 target == 專案根（CLAUDE_PROJECT_DIR）」才排除，
# 絕對子目錄與其他絕對路徑 cd 恢復 warn。
# ============================================================================

_REPO_ROOT = "/Users/tarragon/Projects/book_overview_v1"


class TestBareCdAbsolutePathNarrowing:
    """絕對路徑 cd 收窄：僅 repo-root 還原排除，其餘恢復命中。"""

    def test_repo_root_subdir_hits(self, monkeypatch):
        """cd /<repo-root>/subdir 絕對子目錄恢復 warn（命中）。"""
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", _REPO_ROOT)
        assert (
            _detect_bare_cd(f"cd {_REPO_ROOT}/.claude/skills/ticket && uv run pytest")
            is True
        )

    def test_other_absolute_path_hits(self, monkeypatch):
        """cd /abs/other 非專案根的絕對路徑恢復 warn（命中）。"""
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", _REPO_ROOT)
        assert _detect_bare_cd("cd /tmp/other && ls") is True

    def test_chained_subdir_hits(self, monkeypatch):
        """&& cd /<repo-root>/subdir 串接絕對子目錄命中。"""
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", _REPO_ROOT)
        assert _detect_bare_cd(f"echo x && cd {_REPO_ROOT}/docs && ls") is True

    def test_env_unset_absolute_subdir_hits(self, monkeypatch):
        """CLAUDE_PROJECT_DIR 未設時保守不排除，絕對子目錄仍命中。"""
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
        assert _detect_bare_cd(f"cd {_REPO_ROOT}/.claude && ls") is True

    def test_env_unset_repo_root_also_hits(self, monkeypatch):
        """CLAUDE_PROJECT_DIR 未設時，連 repo-root 還原也命中（保守 fallback，warn 不 deny）。"""
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
        assert _detect_bare_cd(f"cd {_REPO_ROOT} && git status") is True


# ============================================================================
# 裸 cd 偵測：newline 多行命令（W1-035 修復）
# connector 集補 \n，多行命令第二行行首裸 cd 應命中。
# ============================================================================


class TestBareCdNewlineMultiline:
    """換行分隔多行命令的行首裸 cd 應命中（修復前漏報）。"""

    def test_newline_leading_cd_hits(self):
        """第二行行首裸 cd 命中。"""
        assert _detect_bare_cd("echo hi\ncd subdir") is True

    def test_newline_leading_cd_with_chained_hits(self):
        """第二行行首裸 cd 後串接命令命中。"""
        assert _detect_bare_cd("npm install\ncd build && make") is True

    def test_newline_first_line_clean_second_line_cd_hits(self):
        """首行乾淨、第二行裸 cd 命中。"""
        assert _detect_bare_cd("git status\ncd /tmp/other") is True

    def test_multiline_no_bare_cd_not_hit(self):
        """多行命令皆無裸 cd 不命中。"""
        assert _detect_bare_cd("git status\nnpm test\nls") is False


# ============================================================================
# 裸 cd 偵測：pushd 涵蓋（W1-035 修復）
# pushd 同樣改變持久 cwd 並觸發 chpwd，納入偵測。
# ============================================================================


class TestPushdDetection:
    """pushd 改變持久 cwd，視同裸 cd 處理。"""

    def test_leading_pushd_hits(self):
        """行首 pushd 命中。"""
        assert _detect_bare_cd("pushd subdir") is True

    def test_and_chained_pushd_hits(self):
        """&& pushd 串接命中。"""
        assert _detect_bare_cd("git status && pushd subdir") is True

    def test_newline_pushd_hits(self):
        """換行後行首 pushd 命中。"""
        assert _detect_bare_cd("echo hi\npushd /tmp") is True

    def test_subshell_pushd_not_hit(self):
        """子 shell 內 pushd 不命中（不改持久 cwd）。"""
        assert _detect_bare_cd("(pushd subdir && ls)") is False

    def test_pushd_word_in_path_not_matched(self):
        """含 pushd 字面但非指令不誤命中。"""
        assert _detect_bare_cd("ls /mnt/pushder") is False


# ============================================================================
# 裸 cd 偵測：子 shell FP 一致性（W1-035 修復）
# 子 shell 內所有 cd（無論 connector 為 (、&& 或 ;）皆不改變持久 cwd，
# 應一致排除。修復前 (cd a && cd b) 第二個 cd 因 connector 為 && 誤報。
# ============================================================================


class TestSubshellConsistency:
    """子 shell 內串接 cd 不論連接符皆排除。"""

    def test_subshell_nested_and_cd_not_hit(self):
        """子 shell 內 && cd 不命中（修復前誤報）。"""
        assert _detect_bare_cd("(cd a && cd b)") is False

    def test_subshell_nested_semicolon_cd_not_hit(self):
        """子 shell 內 ; cd 不命中（與 && 形式一致）。"""
        assert _detect_bare_cd("(cd a; cd b)") is False

    def test_subshell_then_outer_cd_hits(self):
        """子 shell 閉合後外層裸 cd 命中。"""
        assert _detect_bare_cd("(cd a && ls); cd b") is True

    def test_outer_cd_before_subshell_hits(self):
        """子 shell 前的外層裸 cd 命中。"""
        assert _detect_bare_cd("cd outer && (cd inner && ls)") is True


# ============================================================================
# 既有原地編輯偵測 regression
# ============================================================================


class TestBashEditPatternsRegression:
    """確保既有 sed -i / perl -pi 偵測未被破壞。"""

    def test_sed_inplace_short(self):
        assert _detect_bash_edit_patterns("sed -i 's/a/b/' file.txt") is True

    def test_sed_inplace_long(self):
        assert _detect_bash_edit_patterns("sed --in-place 's/a/b/' file.txt") is True

    def test_perl_pi(self):
        assert _detect_bash_edit_patterns("perl -pi -e 's/a/b/' file.txt") is True

    def test_perl_i_bak(self):
        assert _detect_bash_edit_patterns("perl -i.bak -e 's/a/b/' file.txt") is True

    def test_normal_command_not_edit(self):
        assert _detect_bash_edit_patterns("cat file.txt") is False

    def test_bare_cd_not_edit_pattern(self):
        """裸 cd 不應被原地編輯偵測命中（兩偵測獨立）。"""
        assert _detect_bash_edit_patterns("cd subdir") is False


# ============================================================================
# main() 端到端行為（非 Bash 跳過、warn 不 deny）
# ============================================================================


class TestMainBehavior:
    """透過 stdin 驅動 main() 驗證輸出行為。"""

    def _run_main(self, monkeypatch, capsys, input_dict):
        import io
        import json

        monkeypatch.setattr(
            "sys.stdin", io.StringIO(json.dumps(input_dict))
        )
        exit_code = hook_module.main()
        captured = capsys.readouterr()
        return exit_code, captured.out

    def test_non_bash_tool_skipped(self, monkeypatch, capsys):
        """非 Bash 工具直接允許，無警告輸出。"""
        exit_code, out = self._run_main(
            monkeypatch, capsys, {"tool_name": "Edit", "tool_input": {}}
        )
        assert exit_code == 0
        assert out.strip() == "" or "BARE_CD" not in out

    def test_bare_cd_emits_deny(self, monkeypatch, capsys):
        """裸 cd 命中 → permission_decision=deny（IMP-008 升級），reason 含指引。"""
        import json

        exit_code, out = self._run_main(
            monkeypatch,
            capsys,
            {
                "tool_name": "Bash",
                "tool_input": {"command": "cd subdir && npm test"},
            },
        )
        assert exit_code == 0
        assert out.strip() != ""
        payload = json.loads(out)
        hso = payload.get("hookSpecificOutput", {})
        assert hso.get("permissionDecision") == "deny"
        reason = hso.get("permissionDecisionReason", "")
        # reason 含命中 target + 三種替代指引
        assert "subdir" in reason
        assert "git -C" in reason
        assert "uv -d" in reason
        assert "cd <dir>" in reason or "(cd" in reason

    def test_clean_command_no_warning(self, monkeypatch, capsys):
        """合法命令（git -C）無警告輸出。"""
        exit_code, out = self._run_main(
            monkeypatch,
            capsys,
            {
                "tool_name": "Bash",
                "tool_input": {"command": "git -C /abs status"},
            },
        )
        assert exit_code == 0
        assert out.strip() == ""

    def test_long_bare_cd_logged_untruncated(self, monkeypatch, capsys, caplog):
        """長裸 cd 命令的診斷日誌不截斷（修復前 command[:100] 截斷妨礙 FP 診斷）。"""
        import logging

        long_target = "cd /tmp/" + "a" * 200 + "/deeply/nested/path && ls"
        with caplog.at_level(logging.INFO):
            exit_code, _ = self._run_main(
                monkeypatch,
                capsys,
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": long_target},
                },
            )
        assert exit_code == 0
        # 命中日誌應包含完整命令（含被截斷區段尾端的特徵）
        joined = "\n".join(rec.getMessage() for rec in caplog.records)
        assert long_target in joined


# ============================================================================
# DENY 升級行為（1.2.0-W1-003）：bare cd 各 connector → deny
# ============================================================================

_literal_offset_ranges = hook_module._literal_offset_ranges
_offset_in_literal = hook_module._offset_in_literal


def _run_main_local(monkeypatch, capsys, command):
    import io
    import json

    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})),
    )
    exit_code = hook_module.main()
    out = capsys.readouterr().out
    return exit_code, out


def _decision(out):
    import json

    if not out.strip():
        return None
    return json.loads(out).get("hookSpecificOutput", {}).get("permissionDecision")


class TestBareCdDenyBehavior:
    """bare cd 各命中形式 → permission_decision == deny。"""

    def test_leading_cd_deny(self, monkeypatch, capsys):
        _, out = _run_main_local(monkeypatch, capsys, "cd subdir")
        assert _decision(out) == "deny"

    def test_and_chained_cd_deny(self, monkeypatch, capsys):
        _, out = _run_main_local(monkeypatch, capsys, "git status && cd subdir")
        assert _decision(out) == "deny"

    def test_semicolon_chained_cd_deny(self, monkeypatch, capsys):
        _, out = _run_main_local(monkeypatch, capsys, "echo x; cd subdir")
        assert _decision(out) == "deny"

    def test_or_chained_cd_deny(self, monkeypatch, capsys):
        _, out = _run_main_local(monkeypatch, capsys, "test -d x || cd fallback")
        assert _decision(out) == "deny"

    def test_pushd_deny(self, monkeypatch, capsys):
        _, out = _run_main_local(monkeypatch, capsys, "pushd subdir")
        assert _decision(out) == "deny"

    def test_subshell_cd_not_deny(self, monkeypatch, capsys):
        """子 shell 內 cd 不 deny（無輸出 = allow）。"""
        _, out = _run_main_local(monkeypatch, capsys, "(cd subdir && ls)")
        assert _decision(out) is None


class TestSedPerlStillWarn:
    """sed/perl 原地編輯維持 warn（allow），未被 deny 波及。"""

    def test_sed_inplace_allow(self, monkeypatch, capsys):
        _, out = _run_main_local(monkeypatch, capsys, "sed -i 's/a/b/' f.txt")
        assert _decision(out) == "allow"

    def test_perl_pi_allow(self, monkeypatch, capsys):
        _, out = _run_main_local(monkeypatch, capsys, "perl -pi -e 's/a/b/' f.txt")
        assert _decision(out) == "allow"

    def test_cd_plus_edit_deny_wins(self, monkeypatch, capsys):
        """cd + sed 同時命中 → 以 deny 為準。"""
        _, out = _run_main_local(
            monkeypatch, capsys, "cd subdir && sed -i 's/a/b/' f.txt"
        )
        assert _decision(out) == "deny"


# ============================================================================
# FP 抑制（1.2.0-W1-003）：heredoc body / quoted 字串內的字面 cd 不算裸 cd
# ============================================================================


class TestLiteralCdSuppression:
    """heredoc/quoted 內字面 cd 不命中 → 不 deny（_detect_bare_cd False）。"""

    def test_heredoc_body_cd_not_hit(self):
        cmd = "cat <<EOF > script.sh\ncd /x\nrun\nEOF"
        assert _detect_bare_cd(cmd) is False

    def test_heredoc_dash_body_cd_not_hit(self):
        cmd = "cat <<-EOF\n\tcd /x\nEOF"
        assert _detect_bare_cd(cmd) is False

    def test_heredoc_quoted_delim_cd_not_hit(self):
        cmd = "cat <<'EOF'\ncd /x\nEOF"
        assert _detect_bare_cd(cmd) is False

    def test_single_quoted_cd_not_hit(self):
        assert _detect_bare_cd("echo 'cd /x'") is False

    def test_double_quoted_cd_not_hit(self):
        assert _detect_bare_cd('echo "cd /x"') is False

    def test_heredoc_body_cd_not_deny(self, monkeypatch, capsys):
        cmd = "cat <<EOF > s.sh\ncd /x\nEOF"
        _, out = _run_main_local(monkeypatch, capsys, cmd)
        assert _decision(out) is None

    def test_quoted_cd_not_deny(self, monkeypatch, capsys):
        _, out = _run_main_local(monkeypatch, capsys, "echo 'cd /x'")
        assert _decision(out) is None

    def test_real_cd_outside_heredoc_still_hit(self):
        """heredoc 之外的真正裸 cd 仍命中（抑制不過度）。"""
        cmd = "cd /real\ncat <<EOF\ncd /x\nEOF"
        assert _detect_bare_cd(cmd) is True

    def test_real_cd_after_quoted_still_hit(self):
        """quoted 之後的真正裸 cd 仍命中。"""
        assert _detect_bare_cd("echo 'cd /x' && cd /real") is True


class TestLiteralOffsetRanges:
    """字面區段 offset 計算單元測試。"""

    def test_quote_range(self):
        cmd = "echo 'cd /x'"
        ranges = _literal_offset_ranges(cmd)
        # 找出 cd 的 offset，應落在某區段內
        idx = cmd.index("cd")
        assert _offset_in_literal(idx, ranges) is True

    def test_heredoc_range(self):
        cmd = "cat <<EOF\ncd /x\nEOF"
        ranges = _literal_offset_ranges(cmd)
        idx = cmd.index("cd /x")
        assert _offset_in_literal(idx, ranges) is True

    def test_outside_literal(self):
        cmd = "cd /x"
        ranges = _literal_offset_ranges(cmd)
        assert _offset_in_literal(0, ranges) is False


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
