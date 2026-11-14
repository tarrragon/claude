#!/usr/bin/env python3
"""
Bash Edit Guard Hook - 測試程式碼

涵蓋:
- 裸 cd 偵測各命中形式（行首 / && cd / ; cd / || cd）
- 各排除分支（子 shell (cd ...) / git -C / uv --directory / 絕對路徑還原）
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
        """uv --directory <path> 不含 cd 指令，排除。"""
        assert _detect_bare_cd("uv --directory .claude/skills/ticket run pytest") is False

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


class TestRepoRootRestoreWithAttachedConnector:
    """專案根還原：target 緊接連接符時不把連接符算進 target（3.3.0-W1-098.10）。"""

    @pytest.mark.parametrize("suffix", ["; git status", ";git status", "&&git status",
                                        "||true", "/; ls", ")"])
    def test_root_restore_with_attached_connector_not_hit(self, monkeypatch, suffix):
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", _REPO_ROOT)
        assert _detect_bare_cd(f"cd {_REPO_ROOT}{suffix}") is False

    @pytest.mark.parametrize("cmd", ["cd /tmp/other; ls", "cd /tmp/other&&ls", "cd sub;ls"])
    def test_other_dir_with_attached_connector_still_hits(self, monkeypatch, cmd):
        """正向對照：非專案根的 cd 緊接連接符仍命中。"""
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", _REPO_ROOT)
        assert _detect_bare_cd(cmd) is True

    @pytest.mark.parametrize("sep", ["; ", ";", "&&", " && "])
    def test_root_restore_does_not_release_following_bare_cd(self, monkeypatch, sep):
        """正向對照：還原到專案根之後再接的裸 cd 仍命中（排除不得延伸到後續命令）。"""
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", _REPO_ROOT)
        assert _detect_bare_cd(f"cd {_REPO_ROOT}{sep}cd /tmp/x") is True
        assert hook_module._find_bare_cd_target(f"cd {_REPO_ROOT}{sep}cd /tmp/x") == "/tmp/x"

    def test_target_excludes_connector(self, monkeypatch):
        """回報的 target 不含連接符。"""
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", _REPO_ROOT)
        assert hook_module._find_bare_cd_target("cd /tmp/other;ls") == "/tmp/other"


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


class TestParenDepthIgnoresLiterals:
    """括號深度計算跳過字面區段（3.3.0-W1-094）：引號與 heredoc 內的括號不是子 shell 邊界。"""

    def test_quoted_close_paren_before_subshell_not_hit(self):
        """原重現：echo 字串內的 1) 不把後續子 shell 內的 cd 判為裸 cd。"""
        cmd = 'echo "1) check" && (cd $R/x && ls)'
        assert _detect_bare_cd(cmd) is False

    def test_single_quoted_close_paren_not_hit(self):
        """單引號內的右括號同樣不影響深度。"""
        cmd = "echo 'a) b)' ; (cd sub && ls)"
        assert _detect_bare_cd(cmd) is False

    def test_heredoc_close_paren_not_hit(self):
        """heredoc 正文內的右括號不影響深度。"""
        cmd = "cat <<EOF\nitem 1)\nEOF\n(cd sub && ls)"
        assert _detect_bare_cd(cmd) is False

    def test_quoted_open_paren_does_not_hide_bare_cd(self):
        """正向對照：引號內的左括號不得把其後真正的裸 cd 藏進子 shell。"""
        cmd = 'echo "(note" && cd /tmp/x'
        assert _detect_bare_cd(cmd) is True

    def test_real_bare_cd_after_quoted_paren_still_hits(self):
        """正向對照：引號內有右括號、其後是真正的裸 cd，仍命中。"""
        cmd = 'echo "1) check" && cd /tmp/x'
        assert _detect_bare_cd(cmd) is True


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
        assert "uv --directory" in reason
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
    """sed/perl 原地編輯維持 warn（只帶 additionalContext），未被 deny 波及。"""

    def test_sed_inplace_allow(self, monkeypatch, capsys):
        _, out = _run_main_local(monkeypatch, capsys, "sed -i 's/a/b/' f.txt")
        assert _decision(out) is None
        assert "additionalContext" in out

    def test_perl_pi_allow(self, monkeypatch, capsys):
        _, out = _run_main_local(monkeypatch, capsys, "perl -pi -e 's/a/b/' f.txt")
        assert _decision(out) is None
        assert "additionalContext" in out

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


class TestBashEditPatternsLiteralSuppression:
    """模式 A（sed -i / perl -pi）字面區段抑制（0.2.1-W3-193）。

    抑制機制與模式 B 共用 _literal_offset_ranges()，同一套判斷邏輯。
    """

    def test_heredoc_body_sed_inplace_not_hit(self):
        """heredoc body 內的字面 sed -i 不觸發模式 A 警告。"""
        cmd = "cat <<EOF\n列舉不可靠命令：sed -i 's/a/b/' file.txt\nEOF"
        assert _detect_bash_edit_patterns(cmd) is False

    def test_double_quoted_sed_inplace_not_hit(self):
        """雙引號參數內的字面 sed -i 不觸發模式 A 警告。"""
        cmd = 'ticket create --target "避免使用 sed -i 直接改檔"'
        assert _detect_bash_edit_patterns(cmd) is False

    def test_real_sed_inplace_outside_literal_still_hit(self):
        """字面區段外的真實 sed -i 仍正常觸發（抑制不過度）。"""
        cmd = "sed -i 's/a/b/' file.txt"
        assert _detect_bash_edit_patterns(cmd) is True

    def test_real_sed_inplace_after_heredoc_still_hit(self):
        """heredoc 之外的真實 sed -i 仍命中。"""
        cmd = "cat <<EOF\n說明文字\nEOF\nsed -i 's/a/b/' file.txt"
        assert _detect_bash_edit_patterns(cmd) is True

    def test_double_quoted_perl_pi_not_hit(self):
        """雙引號參數內的字面 perl -pi 不觸發模式 A 警告（補 perl -pi 抑制一例）。"""
        cmd = 'ticket create --target "避免使用 perl -pi 直接改檔"'
        assert _detect_bash_edit_patterns(cmd) is False

    def test_mixed_single_and_double_quote_sed_inplace_not_hit(self):
        """同一命令混合單/雙引號時，字面 sed -i 仍正確被抑制（模式 A 混合引號一例）。"""
        cmd = "echo 'first segment' && ticket create --target \"避免使用 sed -i 直接改檔\""
        assert _detect_bash_edit_patterns(cmd) is False


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


# ============================================================================
# 單趟狀態機（0.2.1-W3-204）：兩個實測反例 + 未閉合 heredoc 不延伸
# why 欄兩個實測反例：引號內含 heredoc 標頭字面時，舊版兩趟獨立掃描
# （heredoc 一趟不知道自己身在引號內）會把引號內字面誤判為真 heredoc 標頭，
# 找不到結束 delimiter 便抑制延伸至命令結尾，導致其後的真實裸 cd / 真實原地
# 編輯被漏放（DENY 繞過）。
# ============================================================================


class TestQuotedHeredocLookAlikeNoBypass:
    """引號內的 heredoc 標頭字面不得讓其後的真實命中被漏放。"""

    def test_quoted_heredoc_lookalike_real_cd_still_hit(self):
        """反例一：引號內 <<EOF 字面後接真實裸 cd，裸 cd 仍須被偵測（不得 DENY 繞過）。"""
        cmd = 'grep -n "<<EOF" README.md\ncd /tmp'
        assert _detect_bare_cd(cmd) is True

    def test_quoted_heredoc_lookalike_real_sed_inplace_still_hit(self):
        """反例二：引號內含 heredoc 字樣後接真實 sed -i，原地編輯仍須被偵測（不得漏放）。"""
        cmd = 'echo "heredoc 用 << EOF 開頭"\nsed -i s/a/b/ f'
        assert _detect_bash_edit_patterns(cmd) is True

    def test_quoted_heredoc_lookalike_does_not_extend_range_to_end(self):
        """引號內字面 <<EOF 不應被當成標頭而產生延伸至命令結尾的字面區段。"""
        cmd = 'grep -n "<<EOF" README.md\ncd /tmp'
        ranges = _literal_offset_ranges(cmd)
        # cd /tmp 的 offset 不應落在任何字面區段內
        idx = cmd.index("cd /tmp")
        assert _offset_in_literal(idx, ranges) is False

    def test_unclosed_real_heredoc_produces_no_range(self):
        """未閉合的真實（非引號內）heredoc 標頭不再延伸至命令結尾產生 range。"""
        cmd = "cat <<EOF\ncd /x"
        ranges = _literal_offset_ranges(cmd)
        idx = cmd.index("cd /x")
        assert _offset_in_literal(idx, ranges) is False


# ============================================================================
# 單趟狀態機分支覆蓋補測（0.2.1-W3-204 補測輪，linux Phase 4 審查後）
# 狀態機本體已由 linux 審查通過（Acceptable）。本節補測其 4 個分支中原本
# 零覆蓋的「未閉合引號 → break」分支，並釘住 linux 手測過但無測試看守的
# 五種組合（跳脫引號為已知繞過，另建 0.2.1-W3-205 追蹤，此處僅斷言現況）。
# ============================================================================


class TestUnclosedQuoteBreakBranch:
    """未閉合引號 → break 分支：中止掃描，不再產生後續字面區段。

    刻意選擇的方向：不足額抑制優於過度抑制。後果是「假 DENY」——heredoc
    body 內的字面 cd 因未被抑制而被當成真實裸 cd 抓出，擋掉合法工作，但
    可觀測性不對稱（假 DENY 會被使用者立刻回報，漏放則無聲無息）。
    """

    def test_unclosed_quote_stops_scan_ranges_empty(self):
        """未閉合單引號後，掃描中止，ranges 為空（heredoc body 未被納入抑制）。"""
        cmd = "echo dont' X\ncat <<EOF\ncd /x\nEOF"
        ranges = _literal_offset_ranges(cmd)
        assert ranges == []

    def test_unclosed_quote_causes_false_deny_on_heredoc_body_cd(self):
        """未閉合引號中止掃描後，heredoc body 內字面 cd 未被抑制，被當真實裸 cd（假 DENY，方向刻意選擇）。"""
        cmd = "echo dont' X\ncat <<EOF\ncd /x\nEOF"
        assert _detect_bare_cd(cmd) is True


class TestEscapedQuoteHandled:
    """0.2.1-W3-205：反斜線跳脫引號已被辨識，不再造成引號配對錯位。

    雙引號內反斜線具跳脫作用；單引號內反斜線為字面字元（shell 語意），
    引號外的反斜線跳脫下一字元，不會誤開啟引號狀態。
    """

    def test_escaped_quote_no_longer_swallows_real_bare_cd(self):
        """修復後：跳脫引號不再使引號配對錯位，真實裸 cd 仍被偵測。"""
        cmd = 'echo \\"foo && cd /tmp && echo "bar"'
        assert _detect_bare_cd(cmd) is True

    def test_escaped_quote_no_longer_swallows_real_inplace_edit(self):
        """修復後：跳脫引號不再使引號配對錯位，真實原地編輯仍被偵測。"""
        cmd = 'echo \\"note && sed -i s/a/b/ f && echo "x"'
        assert _detect_bash_edit_patterns(cmd) is True

    def test_backslash_literal_inside_single_quote_not_treated_as_escape(self):
        """單引號內反斜線不具跳脫作用，引號在下一個引號字元處閉合（shell 語意）。"""
        cmd = r"echo 'a\' && cd /x"
        ranges = _literal_offset_ranges(cmd)
        assert ranges == [(5, 9)]
        assert _detect_bare_cd(cmd) is True

    def test_escape_inside_double_quote_does_not_end_string_early_bare_cd(self):
        """雙引號內的跳脫引號（\\"）不提前收尾，區分 _find_closing_quote() 內的
        跳脫分支（i += 2）與外層迴圈跳脫分支——本例的 \\" 在引號內，只有內層
        分支被行使；若該分支退化為只跳過反斜線（i += 1），\\" 的第二個字元
        會被誤判為收尾引號，造成後方真實 cd 被吞（PM 變異測試發現）。"""
        cmd = 'echo "a\\"b" && cd /tmp && echo "x"'
        assert _detect_bare_cd(cmd) is True

    def test_escape_inside_double_quote_does_not_end_string_early_inplace_edit(self):
        """同上，區分案例二：雙引號內跳脫引號不提前收尾，真實原地編輯仍被偵測。"""
        cmd = 'echo "x\\"y" && sed -i s/a/b/ f && echo "z"'
        assert _detect_bash_edit_patterns(cmd) is True


class TestObservedButUnguardedCombinations:
    """linux 手測過但原本無測試看守的四種組合（現況皆正確，此處補測釘住）。"""

    def test_double_quote_wrapping_single_quote_content_suppressed(self):
        """巢狀引號：雙引號包單引號，內層字面 cd 被外層雙引號整段抑制。"""
        cmd = "echo \"outer 'inner cd /x' end\""
        assert _detect_bare_cd(cmd) is False

    def test_single_quote_wrapping_double_quote_content_suppressed(self):
        """巢狀引號：單引號包雙引號，內層字面 cd 被外層單引號整段抑制。"""
        cmd = 'echo \'outer "inner cd /x" end\''
        assert _detect_bare_cd(cmd) is False

    def test_multiple_heredocs_in_same_command(self):
        """同命令多個 heredoc：各自 body 皆被抑制，body 外的真實 cd 仍命中。"""
        cmd = "cat <<A\ncd /x\nA\ncat <<B\ncd /y\nB\ncd /real"
        ranges = _literal_offset_ranges(cmd)
        assert _offset_in_literal(cmd.index("cd /x"), ranges) is True
        assert _offset_in_literal(cmd.index("cd /y"), ranges) is True
        assert _offset_in_literal(cmd.index("cd /real"), ranges) is False
        assert _detect_bare_cd(cmd) is True

    def test_heredoc_body_containing_quotes_not_hit(self):
        """heredoc body 內出現引號字元：body 以整段跳過方式消耗，內部引號不干擾抑制。"""
        cmd = "cat <<EOF\nit's a \"quoted\" cd /x line\nEOF"
        assert _detect_bare_cd(cmd) is False

    def test_end_delimiter_lookalike_inside_quotes_does_not_end_body_early(self):
        """結束 delimiter 字面出現在引號內（非獨立成行）不會提前終結 body，真正結束行才生效。"""
        cmd = 'cat <<EOF\necho "EOF"\ncd /x\nEOF'
        ranges = _literal_offset_ranges(cmd)
        assert _offset_in_literal(cmd.index("cd /x"), ranges) is True
        assert _detect_bare_cd(cmd) is False


# ============================================================================
# 受管路徑分級：ticket md 擋下；其餘受管路徑只送 additionalContext；
# 非受管路徑維持現行（只對 sed -i／perl -pi 警告並帶 allow）
# ============================================================================

_TICKET_MD = "docs/work-logs/v0/v0.0/v0.0.1/tickets/0.0.1-W1-001.md"


@pytest.fixture
def checkout(tmp_path):
    """假 checkout 根目錄（含 .git 目錄），作為 payload cwd。"""
    (tmp_path / ".git").mkdir()
    return tmp_path.resolve()


def _run_in(monkeypatch, capsys, command, cwd):
    import io
    import json

    payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    exit_code = hook_module.main()
    out = capsys.readouterr().out
    hso = json.loads(out).get("hookSpecificOutput", {}) if out.strip() else None
    return exit_code, hso


_WRITE_FORMS = {
    "python_inline": "python3 -c \"open('{t}', 'w').write('x')\"",
    "heredoc": "cat > {t} <<'EOF'\nx\nEOF",
    "redirect": "echo x > {t}",
    "redirect_append": "echo x >> {t}",
    "awk_inplace": "awk -i inplace '{{print}}' {t}",
    "ed": "ed -s {t} <<'EOF'\n1d\nw\nq\nEOF",
    "sed_inplace": "sed -i '' 's/a/b/' {t}",
    "perl_inplace": "perl -pi -e 's/a/b/' {t}",
}


class TestTicketMdDenied:
    """正向對照（E2）：寫入 ticket md 的各型 Bash 寫入一律 deny。"""

    @pytest.mark.parametrize("form", sorted(_WRITE_FORMS))
    def test_write_form_denied(self, form, checkout, monkeypatch, capsys):
        cmd = _WRITE_FORMS[form].format(t=_TICKET_MD)
        code, hso = _run_in(monkeypatch, capsys, cmd, checkout)
        assert code == 0
        assert hso is not None and hso.get("permissionDecision") == "deny"

    def test_deny_reason_points_to_ticket_cli_and_edit(self, checkout, monkeypatch, capsys):
        _, hso = _run_in(monkeypatch, capsys, "echo x >> " + _TICKET_MD, checkout)
        reason = hso.get("permissionDecisionReason", "")
        assert _TICKET_MD in reason
        assert "ticket track" in reason
        assert "Edit" in reason
        assert "停手" in reason

    def test_absolute_path_inside_checkout_denied(self, checkout, monkeypatch, capsys):
        cmd = "echo x > %s/%s" % (checkout, _TICKET_MD)
        _, hso = _run_in(monkeypatch, capsys, cmd, checkout)
        assert hso.get("permissionDecision") == "deny"


_OTHER_MANAGED = ["docs/x.md", "docs/work-logs/v0/notes.md", "CLAUDE.md", "CHANGELOG.md"]


class TestOtherManagedPathsWarnOnly:
    """其餘受管路徑命中：放行並送模型可見警告，不帶 permission_decision。"""

    @pytest.mark.parametrize("target", _OTHER_MANAGED)
    @pytest.mark.parametrize("form", sorted(_WRITE_FORMS))
    def test_warn_without_decision(self, form, target, checkout, monkeypatch, capsys):
        cmd = _WRITE_FORMS[form].format(t=target)
        _, hso = _run_in(monkeypatch, capsys, cmd, checkout)
        assert hso is not None
        assert "permissionDecision" not in hso
        assert target in hso.get("additionalContext", "")
        assert "Edit" in hso.get("additionalContext", "")


class TestUnmanagedPathsUnchanged:
    """非受管路徑維持現行：sed -i／perl -pi 警告並帶 allow，其他寫入無輸出。"""

    def test_sed_inplace_unmanaged_allow(self, checkout, monkeypatch, capsys):
        _, hso = _run_in(monkeypatch, capsys, "sed -i '' 's/a/b/' src/a.txt", checkout)
        assert "permissionDecision" not in hso
        assert hso.get("additionalContext")

    @pytest.mark.parametrize("cmd", [
        "echo x > /tmp/out.txt",
        "cat > /tmp/a.md <<'EOF'\nx\nEOF",
        "echo x > build/out.txt",
        "python3 -c \"print(open('docs/x.md').read())\"",
        "python3 -c \"import sys; print(open('%s').read())\"" % _TICKET_MD,
        "cat " + _TICKET_MD,
        "grep -n x docs/x.md > /tmp/hits.txt",
        "echo 'echo x > docs/x.md'",
    ])
    def test_reverse_controls_silent(self, cmd, checkout, monkeypatch, capsys):
        _, hso = _run_in(monkeypatch, capsys, cmd, checkout)
        assert hso is None

    _MENTION_BODY = (
        "改動見 docs/work-logs/v3/v3.3/v3.3.0/tickets/0.0.1-W1-222.md 與 " + _TICKET_MD
        + "\n> " + _TICKET_MD + "\necho x >> " + _TICKET_MD
    )

    @pytest.mark.parametrize("prefix", [
        "ticket track append-log 0.0.1-W1-001 --section Solution",
        "git commit -m",
    ])
    def test_heredoc_text_mentioning_ticket_md_allowed(self, prefix, checkout, monkeypatch, capsys):
        """例行記錄寫法：heredoc 內文提及 ticket md 路徑（含重導向字樣）不是寫入，必須放行。"""
        cmd = "%s \"$(cat <<'EOF'\n%s\nEOF\n)\"" % (prefix, self._MENTION_BODY)
        _, hso = _run_in(monkeypatch, capsys, cmd, checkout)
        assert hso is None or hso.get("permissionDecision") != "deny"
        assert hso is None


class TestTierPrecedence:
    """多種命中並存時的處置。"""

    def test_ticket_md_and_other_managed_deny(self, checkout, monkeypatch, capsys):
        cmd = "echo x > docs/x.md && echo y >> " + _TICKET_MD
        _, hso = _run_in(monkeypatch, capsys, cmd, checkout)
        assert hso.get("permissionDecision") == "deny"

    def test_managed_and_unmanaged_sed_drops_allow(self, checkout, monkeypatch, capsys):
        """受管與非受管 sed -i 並存：以受管路徑的處置為準，不帶 allow。"""
        cmd = "sed -i '' 's/a/b/' src/a.txt docs/x.md"
        _, hso = _run_in(monkeypatch, capsys, cmd, checkout)
        assert "permissionDecision" not in hso
        assert "docs/x.md" in hso.get("additionalContext", "")

    def test_bare_cd_with_managed_write_deny(self, checkout, monkeypatch, capsys):
        _, hso = _run_in(monkeypatch, capsys, "cd sub && echo x > docs/x.md", checkout)
        assert hso.get("permissionDecision") == "deny"


class TestSharedExtractorUnavailable:
    """共用抽取模組載入失敗時退回現行行為（fail-open），並寫入日誌。"""

    def test_fallback_to_legacy(self, checkout, monkeypatch, capsys, caplog):
        import logging

        monkeypatch.setattr(hook_module, "_load_boundary_guard", lambda: None)
        with caplog.at_level(logging.INFO):
            _, hso = _run_in(monkeypatch, capsys, "sed -i '' 's/a/b/' " + _TICKET_MD, checkout)
        assert "permissionDecision" not in hso
        assert hso.get("additionalContext")
        _, hso2 = _run_in(monkeypatch, capsys, "echo x > " + _TICKET_MD, checkout)
        assert hso2 is None
        assert any("共用寫入目標抽取不可用" in r.getMessage() for r in caplog.records)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
