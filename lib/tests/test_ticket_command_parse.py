#!/usr/bin/env python3
"""ticket_command_parse 單元測試。

驗證項目：
1. find_complete_invocations（任意位置掃描）：
   - 被辨識：前綴包裝、串接、shell -c 巢狀、絕對路徑的 ticket、未知包裝器
   - 不被辨識：echo、printf、command -v 位置的語句、引號內字面、非完成類動詞
   - 失敗語意：未閉合引號回傳 None（呼叫端自行 fail-closed）
2. 既有函式 complete_statement_args／is_complete_statement／has_complete_command 行為不變
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.ticket_command_parse import (
    COMPLETE_VERBS,
    complete_statement_args,
    find_complete_invocations,
    find_ticket_track_invocations,
    has_complete_command,
    is_complete_statement,
    is_invocation_masked,
)

TID = "0.5.0-W1-001"


def _verbs(command):
    found = find_complete_invocations(command)
    assert found is not None
    return [verb for verb, _ in found]


class TestRecognized:
    """正向對照：這些命令必須被辨識為完成類命令。"""

    def test_direct(self):
        assert _verbs(f"ticket track complete {TID}") == ["complete"]

    def test_finish_and_batch_complete(self):
        assert _verbs(f"ticket track finish {TID}") == ["finish"]
        assert _verbs(f"ticket track batch-complete {TID} {TID}") == ["batch-complete"]

    def test_args_after_verb(self):
        found = find_complete_invocations(f"ticket track complete {TID} --force")
        assert found == [("complete", [TID, "--force"])]

    def test_known_prefix_wrapper(self):
        assert _verbs(f"env FOO=1 nohup ticket track complete {TID}") == ["complete"]

    def test_unlisted_prefix_wrapper(self):
        # 前綴白名單之外的包裝器（現行位置判定漏判的集合）
        assert _verbs(f"timeout 30 ticket track complete {TID}") == ["complete"]
        assert _verbs(f"ionice -c3 caffeinate ticket track complete {TID}") == ["complete"]

    def test_chained_after_other_statement(self):
        assert _verbs(f"git status && ticket track complete {TID}") == ["complete"]
        assert _verbs(f"echo hi; ticket track complete {TID}") == ["complete"]
        assert _verbs(f"cat x | ticket track complete {TID}") == ["complete"]

    def test_control_flow_block(self):
        assert _verbs(f"for i in 1; do ticket track complete {TID}; done") == ["complete"]
        assert _verbs(f"if true; then ticket track complete {TID}; fi") == ["complete"]

    def test_shell_c_nested(self):
        assert _verbs(f"bash -c 'ticket track complete {TID}'") == ["complete"]
        assert _verbs(f"sh -c \"cd x && ticket track finish {TID}\"") == ["finish"]
        assert _verbs(f"bash -lc 'ticket track complete {TID}'") == ["complete"]

    def test_shell_c_nested_twice(self):
        inner = f"sh -c \"ticket track complete {TID}\""
        assert _verbs(f"bash -c '{inner}'") == ["complete"]

    def test_absolute_path_ticket(self):
        assert _verbs(f"/usr/local/bin/ticket track complete {TID}") == ["complete"]
        assert _verbs(f"~/.local/bin/ticket track complete {TID}") == ["complete"]

    def test_multiple_invocations(self):
        found = find_complete_invocations(
            f"ticket track complete {TID} && ticket track finish {TID}.1"
        )
        assert [v for v, _ in found] == ["complete", "finish"]


class TestNotRecognized:
    """反向對照：動詞字樣只是輸出文字、查詢或引號內字面時不辨識。"""

    def test_echo(self):
        assert _verbs(f"echo ticket track complete {TID}") == []

    def test_printf(self):
        assert _verbs(f"printf '%s' ticket track complete {TID}") == []
        assert _verbs(f"printf %s ticket track complete {TID}") == []

    def test_command_v(self):
        assert _verbs("command -v ticket track complete") == []

    def test_echo_does_not_hide_later_statement(self):
        assert _verbs(f"echo ticket track complete; ticket track complete {TID}") == ["complete"]

    def test_quoted_literal(self):
        assert _verbs(f"ticket track create --why 'ticket track complete {TID}'") == []

    def test_other_verbs(self):
        assert _verbs(f"ticket track claim {TID}") == []
        assert _verbs(f"ticket track query {TID}") == []

    def test_empty(self):
        assert find_complete_invocations("") == []

    def test_no_ticket(self):
        assert _verbs("git status && ls") == []


class TestFailureSemantics:
    def test_unclosed_quote_returns_none(self):
        assert find_complete_invocations("ticket track complete 'abc") is None

    def test_stdin_shell_returns_none(self):
        for cmd in (
            f'echo "ticket track complete {TID}" | bash',
            f'printf %s "ticket track complete {TID}" | sh',
            f'bash <<< "ticket track complete {TID}"',
            "cat f | bash",
            "echo x | bash -s",
        ):
            assert find_complete_invocations(cmd) is None, cmd

    def test_plain_complete_still_returns_list(self):
        assert find_complete_invocations(f"ticket track complete {TID}") == [("complete", [TID])]
        # 對照：管線但接收端非 shell 不 fail-closed
        assert find_complete_invocations(f"echo x | grep y") == []

    def test_nested_unparseable_returns_none(self):
        assert find_complete_invocations("bash -c \"ticket track complete 'abc\"") is None


class TestGenericScan:
    """find_ticket_track_invocations：動詞集合參數化，含 phase 形態。"""

    VERBS = ("phase",) + COMPLETE_VERBS

    def _found(self, command):
        found = find_ticket_track_invocations(command, self.VERBS)
        assert found is not None
        return found

    def test_phase_direct(self):
        assert self._found(f"ticket track phase {TID} phase4") == [("phase", [TID, "phase4"])]

    def test_phase_wrapped_chained_nested_abs(self):
        for cmd in (
            f"timeout 30 ticket track phase {TID} phase4",
            f"git status && ticket track phase {TID} phase4",
            f"bash -c 'ticket track phase {TID} phase4'",
            f"/usr/local/bin/ticket track phase {TID} phase4",
        ):
            assert self._found(cmd) == [("phase", [TID, "phase4"])], cmd

    def test_multi_ids_mixed(self):
        found = self._found(
            f"ticket track phase {TID} phase4 && ticket track complete {TID}.1"
        )
        assert found == [("phase", [TID, "phase4"]), ("complete", [f"{TID}.1"])]

    def test_stdin_shell_none(self):
        assert find_ticket_track_invocations(
            f'echo "ticket track phase {TID} phase4" | bash', self.VERBS
        ) is None

    def test_phase_not_seen_by_complete_scan(self):
        assert find_complete_invocations(f"ticket track phase {TID} phase4") == []

    def test_echo_phase_not_recognized(self):
        assert self._found(f"echo ticket track phase {TID} phase4") == []


class TestIsInvocationMasked:
    """is_invocation_masked：結束碼是否可能被遮蔽。"""

    UNMASKED = [
        f"ticket track finish {TID}",
        f"ticket track finish {TID} > /tmp/log 2>&1",
        f"ticket track finish {TID} 2>&1 && echo done",
        f"git add x && ticket track complete {TID}",
        f"ticket track finish {TID};",
        f"out=$(ticket track append-log {TID} x 2>&1)",
        f"(ticket track finish {TID})",
    ]
    MASKED = [
        # 285 實例
        f"ticket track finish {TID} > /tmp/log 2>&1; echo rc=$?",
        # bash-tool-usage-rules 要求的寫法
        f"out=$(ticket track append-log {TID} x 2>&1); rc=$?",
        f"ticket track finish {TID} 2>&1 | head -30",
        f"ticket track finish {TID} || true",
        f"ticket track finish {TID} & wait",
        f"ticket track finish {TID}\necho rc=$?",
        f"bash -c 'ticket track finish {TID}; echo rc=$?'",
    ]

    def test_unmasked_forms(self):
        for cmd in self.UNMASKED:
            assert is_invocation_masked(cmd) is False, cmd

    def test_masked_forms(self):
        for cmd in self.MASKED:
            assert is_invocation_masked(cmd) is True, cmd

    def test_substitution_under_non_assignment_is_masked(self):
        for cmd in (
            f"echo $(ticket track complete {TID})",
            f'echo "$(ticket track complete {TID})"',
            f"export x=$(ticket track complete {TID})",
            f"local x=$(ticket track complete {TID})",
            f"declare x=$(ticket track complete {TID})",
        ):
            assert is_invocation_masked(cmd) is True, cmd

    def test_pure_assignment_substitution_stays_unmasked(self):
        """E2 對照：純賦值把替換的結束碼傳出。"""
        for cmd in (
            f"out=$(ticket track complete {TID})",
            f'out="$(ticket track complete {TID})"',
            f"a=$(ticket track complete {TID}) b=$(echo y)",
        ):
            assert is_invocation_masked(cmd) is False, cmd

    def test_subshell_inner_substitution_is_masked(self):
        for cmd in (
            f"(echo $(ticket track complete {TID}))",
            f"(a; ticket track complete {TID})",
            f"((echo $(ticket track complete {TID})))",
            f"(export x=$(ticket track complete {TID}))",
            f"(ticket track complete {TID}) && (echo $(date))",
        ):
            assert is_invocation_masked(cmd) is True, cmd

    def test_subshell_e2_controls_stay_unmasked(self):
        for cmd in (
            f"(ticket track complete {TID})",
            f"(out=$(ticket track complete {TID}))",
            f"((ticket track complete {TID}))",
            f"(ticket track complete {TID}) && (ticket track finish {TID})",
        ):
            assert is_invocation_masked(cmd) is False, cmd

    def test_subshell_over_nesting_is_conservatively_masked(self):
        cmd = "(" * 20 + "ticket track complete X" + ")" * 20
        assert is_invocation_masked(cmd) is True

    def test_process_substitution_is_unmasked(self):
        assert is_invocation_masked(f"ticket track finish {TID} > >(tee /tmp/log)") is False

    def test_quoted_separator_is_not_masking(self):
        assert is_invocation_masked(f"ticket track append-log {TID} 'a; b | c'") is False

    def test_unparseable_is_none(self):
        assert is_invocation_masked("ticket track finish 'abc") is None

    def test_empty_command_is_unmasked(self):
        assert is_invocation_masked("") is False

    def test_help_flag_does_not_change_masking(self):
        """294 的 -h/--help 排除只影響呼叫辨識；遮蔽判斷只看結構，兩者互不干擾。"""
        assert is_invocation_masked("ticket track complete --help") is False
        assert is_invocation_masked("ticket track complete --help; echo rc=$?") is True


class TestHelpFlagExcluded:
    """只查說明的寫法（-h、--help）不是收尾；位置判定與掃描判定結果一致。"""

    VERBS = ("phase",) + COMPLETE_VERBS
    HELP_COMMANDS = (
        "ticket track complete --help",
        "ticket track finish -h",
        f"ticket track complete {TID} --help",
        "ticket track batch-complete -h",
    )

    def test_position_judgement_excludes_help(self):
        for cmd in self.HELP_COMMANDS:
            assert has_complete_command(cmd) is False, cmd
        assert complete_statement_args(["ticket", "track", "complete", "--help"]) is None
        assert complete_statement_args(["ticket", "track", "finish", "-h"]) is None

    def test_scan_judgement_excludes_help(self):
        for cmd in self.HELP_COMMANDS:
            assert find_complete_invocations(cmd) == [], cmd
            assert find_ticket_track_invocations(cmd, self.VERBS) == [], cmd

    def test_phase_help_excluded(self):
        cmd = f"ticket track phase {TID} phase4 --help"
        assert find_ticket_track_invocations(cmd, self.VERBS) == []

    def test_wrapped_and_nested_help_excluded(self):
        assert find_complete_invocations("timeout 30 ticket track complete --help") == []
        assert find_complete_invocations("bash -c 'ticket track complete -h'") == []

    def test_positive_control_complete_still_recognized(self):
        assert has_complete_command(f"ticket track complete {TID}") is True
        assert find_complete_invocations(f"ticket track complete {TID}") == [("complete", [TID])]

    def test_help_inside_quotes_still_complete(self):
        cmd = f"ticket track complete {TID} --why '見 --help'"
        assert has_complete_command(cmd) is True
        assert _verbs(cmd) == ["complete"]

    def test_help_after_double_dash_still_complete(self):
        cmd = f"ticket track complete {TID} -- --help"
        assert has_complete_command(cmd) is True
        assert _verbs(cmd) == ["complete"]

    def test_help_prefix_lookalike_still_complete(self):
        assert _verbs(f"ticket track complete {TID} --helpful") == ["complete"]


class TestExistingFunctionsUnchanged:
    """既有函式維持命令位置判定，另有 hook 引用，行為不得改變。"""

    def test_complete_statement_args(self):
        assert complete_statement_args(["ticket", "track", "complete", TID]) == [TID]
        assert complete_statement_args(["nohup", "ticket", "track", "finish", TID]) == [TID]
        assert complete_statement_args(["ticket", "track", "claim", TID]) is None

    def test_position_only_not_scan(self):
        # 位置判定不辨識 timeout 包裝；掃描函式才辨識（兩者刻意不同）
        assert is_complete_statement(["timeout", "30", "ticket", "track", "complete", TID]) is False
        assert is_complete_statement(["ticket", "track", "complete", TID]) is True

    def test_has_complete_command(self):
        assert has_complete_command(f"git x && ticket track complete {TID}") is True
        assert has_complete_command(f"bash -c 'ticket track complete {TID}'") is False
        assert has_complete_command("ticket track complete 'abc") is None
