#!/usr/bin/env python3
"""
Bash Write Boundary Guard Hook - 測試程式碼

main-thread-edit-restriction-hook.py 僅註冊於 Edit/Write/MultiEdit，可被 Bash
寫入（heredoc / cat > / cat >> / tee / sed -i / python open() / cp / mv）繞過。
本 hook 是該缺口的 Bash matcher 補網，涵蓋：

- 候選寫入路徑抽取（各種語法形態）
- test/、lib/、*.dart 命中時轉呼 check_file_permission 判定違規
- 合法 Bash 使用場景（讀取、非目標路徑寫入）不誤擋（fail-open）
- 非 Bash 工具 / subagent 環境 / 開發分支跳過
"""

import importlib.util
import logging
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

hook_dir = Path(__file__).parent.parent
sys.path.insert(0, str(hook_dir))
sys.path.insert(0, str(hook_dir.parent))

spec = importlib.util.spec_from_file_location(
    "bash_write_boundary_guard_hook_module",
    hook_dir / "bash-write-boundary-guard-hook.py",
)
hook_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook_module)

_extract_candidate_paths = hook_module._extract_candidate_paths
_find_boundary_violation = hook_module._find_boundary_violation
main = hook_module.main


@pytest.fixture
def logger():
    lg = logging.getLogger("test-bash-write-boundary-guard")
    lg.addHandler(logging.NullHandler())
    return lg


# ============================================================================
# 候選路徑抽取：各種寫入語法形態
# ============================================================================


class TestCandidatePathExtraction:
    """各寫入語法形態應正確抽出目標路徑。"""

    def test_cat_redirect_heredoc(self):
        cmd = "cat > lib/foo.dart <<'EOF'\nclass Foo {}\nEOF"
        assert "lib/foo.dart" in _extract_candidate_paths(cmd)

    def test_cat_append_heredoc(self):
        cmd = "cat >> test/foo_test.dart <<'EOF'\nvoid main(){}\nEOF"
        assert "test/foo_test.dart" in _extract_candidate_paths(cmd)

    def test_python_open_in_heredoc(self):
        cmd = "python3 - <<'EOF'\nopen('lib/bar.dart', 'w').write('x')\nEOF"
        assert "lib/bar.dart" in _extract_candidate_paths(cmd)

    def test_sed_inplace(self):
        cmd = "sed -i '' 's/a/b/' lib/foo.dart"
        assert "lib/foo.dart" in _extract_candidate_paths(cmd)

    @pytest.mark.parametrize("cmd", [
        "sed -i 's/a/b/' target.py",
        "sed -i.bak 's/a/b/' target.py",
        "sed --in-place 's/a/b/' target.py",
        "sed --in-place=.bak 's/a/b/' target.py",
        'sed -i "" \'s/a/b/\' target.py',
        "sed -i '' 's/a/b/' target.py",
        "sed -i .bak 's/a/b/' target.py",
        "sed -n -i 's/a/b/' target.py",
        "sed -e 's/a/b/' -i target.py",
        "sed -i -e 's/a/b/' target.py",
        "sed -e 's/a/b/' -e 's/c/d/' -i.bak target.py",
    ])
    def test_sed_inplace_variants_extract_exact_target(self, cmd):
        # 正向對照：舊實作對 BSD 寫法會抽到 s/a/b/（腳本）而非檔案
        assert _extract_candidate_paths(cmd) == ["target.py"]

    @pytest.mark.parametrize("cmd", [
        "sed x " * 32000,
        "sed " * 32000,
        "echo hello " * 17000,
    ])
    def test_padded_input_extracts_nothing(self, cmd):
        # 不計時的正確性斷言；線性由計數測試（TestLinearWorkByCount）保證
        assert _extract_candidate_paths(cmd) == []

    @pytest.mark.wallclock
    @pytest.mark.parametrize("cmd", [
        "sed x " * 32000,
        "sed " * 32000,
        "echo hello " * 17000,
    ])
    def test_padded_input_extracts_in_linear_time(self, cmd):
        # 牆鐘判準（負載敏感，主套件排除）：284.2 的前瞻使 192KB 輸入耗時約 43 秒
        import time
        start = time.monotonic()
        result = _extract_candidate_paths(cmd)
        assert time.monotonic() - start < 1.0
        assert result == []

    def test_padded_input_still_catches_trailing_write(self):
        cmd = "sed x " * 32000 + "; sed -e 's/a/b/' -i lib/foo.dart"
        assert _extract_candidate_paths(cmd) == ["lib/foo.dart"]

    def test_cp_target(self):
        cmd = "cp source.dart lib/dest.dart"
        assert "lib/dest.dart" in _extract_candidate_paths(cmd)

    def test_mv_target(self):
        cmd = "mv old.dart lib/new.dart"
        assert "lib/new.dart" in _extract_candidate_paths(cmd)

    def test_tee_target(self):
        cmd = "tee lib/output.dart <<'EOF'\nfoo\nEOF"
        assert "lib/output.dart" in _extract_candidate_paths(cmd)

    def test_no_candidates_for_read_only_command(self):
        assert _extract_candidate_paths("git status") == []
        assert _extract_candidate_paths("ls -la") == []


# ============================================================================
# 違規偵測：命中 test/lib/dart 且判定不允許
# ============================================================================


class TestBoundaryViolationDetection:
    """重現 0.2.1-W3-825 紀錄的繞過形態，確認修復後被偵測。"""

    def test_heredoc_write_to_lib_dart_is_violation(self, logger):
        cmd = "cat > lib/foo.dart <<'EOF'\nclass Foo {}\nEOF"
        assert _find_boundary_violation(cmd, logger) == "lib/foo.dart"

    def test_python_inline_script_write_to_lib_is_violation(self, logger):
        cmd = "python3 - <<'EOF'\nopen('lib/bar.dart', 'a').write('x')\nEOF"
        assert _find_boundary_violation(cmd, logger) == "lib/bar.dart"

    def test_sed_inplace_write_to_dart_is_violation(self, logger):
        cmd = "sed -i '' 's/a/b/' lib/foo.dart"
        assert _find_boundary_violation(cmd, logger) == "lib/foo.dart"

    def test_cp_into_test_dir_is_violation(self, logger):
        cmd = "cp source_test.dart test/foo_test.dart"
        assert _find_boundary_violation(cmd, logger) == "test/foo_test.dart"

    def test_mv_into_lib_dir_is_violation(self, logger):
        cmd = "mv scratch.dart lib/new_widget.dart"
        assert _find_boundary_violation(cmd, logger) == "lib/new_widget.dart"


# ============================================================================
# 誤判率評估：合法 Bash 使用場景不誤擋
# ============================================================================


class TestLegitimateUsageNotBlocked:
    """至少 3 個合法 Bash 使用場景（非寫入 test/lib/dart 路徑）驗證不誤擋。"""

    def test_flutter_test_command_not_blocked(self, logger):
        cmd = "flutter test test/unit/foo_test.dart"
        assert _find_boundary_violation(cmd, logger) is None

    def test_ticket_cli_not_blocked(self, logger):
        cmd = "ticket track claim ticket-id --as basil-hook-architect"
        assert _find_boundary_violation(cmd, logger) is None

    def test_grep_read_lib_not_blocked(self, logger):
        cmd = "grep -rn 'foo' lib/"
        assert _find_boundary_violation(cmd, logger) is None

    def test_cat_read_dart_file_not_blocked(self, logger):
        cmd = "cat lib/foo.dart"
        assert _find_boundary_violation(cmd, logger) is None

    def test_write_to_docs_not_blocked(self, logger):
        cmd = "echo hi > docs/notes.md"
        assert _find_boundary_violation(cmd, logger) is None

    def test_write_to_allowed_claude_hooks_not_blocked(self, logger):
        cmd = "cat > .claude/hooks/foo-hook.py <<'EOF'\nprint(1)\nEOF"
        assert _find_boundary_violation(cmd, logger) is None


# ============================================================================
# main() 整合：工具過濾 / subagent / 開發分支
# ============================================================================


class TestMainEntryPoint:
    """main() 流程整合測試：非 Bash 工具、subagent、開發分支跳過。"""

    def _run_main(self, monkeypatch, stdin_json, is_subagent=False, branch="main"):
        import io
        import json as json_mod

        monkeypatch.setattr(sys, "stdin", io.StringIO(json_mod.dumps(stdin_json)))
        with patch.object(hook_module, "is_subagent_environment", return_value=is_subagent), \
             patch.object(hook_module, "get_current_branch", return_value=branch), \
             patch.object(hook_module, "is_allowed_branch", return_value=(branch != "main")):
            return main()

    def test_non_bash_tool_allowed(self, monkeypatch):
        exit_code = self._run_main(
            monkeypatch,
            {"tool_name": "Read", "tool_input": {"file_path": "lib/foo.dart"}},
        )
        assert exit_code == 0

    def test_subagent_environment_allowed(self, monkeypatch):
        exit_code = self._run_main(
            monkeypatch,
            {"tool_name": "Bash", "tool_input": {"command": "cat > lib/foo.dart <<'EOF'\nx\nEOF"}, "agent_id": "sub-1"},
            is_subagent=True,
        )
        assert exit_code == 0

    def test_dev_branch_allowed(self, monkeypatch):
        exit_code = self._run_main(
            monkeypatch,
            {"tool_name": "Bash", "tool_input": {"command": "cat > lib/foo.dart <<'EOF'\nx\nEOF"}},
            branch="feat/some-feature",
        )
        assert exit_code == 0

    def test_main_thread_bash_violation_denied(self, monkeypatch):
        exit_code = self._run_main(
            monkeypatch,
            {"tool_name": "Bash", "tool_input": {"command": "cat > lib/foo.dart <<'EOF'\nclass Foo {}\nEOF"}},
            branch="main",
        )
        assert exit_code == 2

    def test_main_thread_legit_command_allowed(self, monkeypatch):
        exit_code = self._run_main(
            monkeypatch,
            {"tool_name": "Bash", "tool_input": {"command": "git status"}},
            branch="main",
        )
        assert exit_code == 0


# ============================================================================
# 0.5.0-W1-284.5：線性 token 走訪的效能（n 與 4n）與 heredoc／引號剔除
# ============================================================================

# 各形態的 n：依實測使 n 的耗時約 10-30ms，比值才不被排程雜訊主導
_PERF_N_BY_SHAPE = {
    "single_sed_long_e_chain": 8000,
    "single_sed_long_e_chain_no_i": 6000,
    "sed_word_padding": 8000,
    "bare_sed_padding": 18000,
    "sed_n_chain": 14000,
    "sed_inplace_repeated": 4000,
    "cp_flag_chain": 8000,
    "mv_repeated": 6000,
    "tee_repeated": 4000,
    "redirect_repeated": 6000,
    "double_quoted_repeated": 6000,
    "single_quoted_repeated": 6000,
    "heredoc_body_long": 90000,
    "heredoc_repeated": 6000,
    "python_open_repeated": 20000,
    "long_single_token": 250000,
    "unterminated_quote": 200000,
    "paren_chain": 24000,
    "backslash_chain": 80000,
}

# 每種可重複的 token 形態：k -> 命令字串
_PERF_SHAPES = {
    "single_sed_long_e_chain": lambda k: "sed -n " + "-e 's/a/b/' " * k + "-i f.txt",
    "single_sed_long_e_chain_no_i": lambda k: "sed " + "-e 's/a/b/' " * k,
    "sed_word_padding": lambda k: "sed x " * k,
    "bare_sed_padding": lambda k: "sed " * k,
    "sed_n_chain": lambda k: "sed " + "-n " * k + "-i f.txt",
    "sed_inplace_repeated": lambda k: "sed -i '' x f; " * k,
    "cp_flag_chain": lambda k: "cp " + "-r " * k + "a b",
    "mv_repeated": lambda k: "mv a b; " * k,
    "tee_repeated": lambda k: "tee -a f.txt | " * k,
    "redirect_repeated": lambda k: "echo hello > out.txt; " * k,
    "double_quoted_repeated": lambda k: 'echo "sed -i x lib/a.dart" ' * k,
    "single_quoted_repeated": lambda k: "echo 'sed -i x lib/a.dart' " * k,
    "heredoc_body_long": lambda k: "cat <<'EOF'\n" + "sed -i x lib/a.dart\n" * k + "EOF",
    "heredoc_repeated": lambda k: "cat <<A\nx\nA\n" * k,
    "python_open_repeated": lambda k: "python3 -c \"" + "open('a.txt') " * k + "\"",
    "long_single_token": lambda k: "echo " + "a" * (k * 10),
    "unterminated_quote": lambda k: 'echo "' + "x " * k,
    "paren_chain": lambda k: "( " * k,
    "backslash_chain": lambda k: "echo " + "\\ " * k,
}


def _best_time(cmd, repeat=3):
    # 取 CPU 時間（排除排程等待）、量測期間停用 GC（世代回收的掃描成本與輸入大小
    # 非線性，屬量測雜訊而非解析複雜度），重複取最小值
    import gc
    import time
    best = None
    gc.collect()
    gc.disable()
    try:
        for _ in range(repeat):
            start = time.process_time()
            _extract_candidate_paths(cmd)
            elapsed = time.process_time() - start
            best = elapsed if best is None else min(best, elapsed)
    finally:
        gc.enable()
    return best


class TestLinearTimeAcrossTokenShapes:
    """每種可重複 token 形態：4n 耗時不超過 n 的 8 倍，且 4n 在 1 秒內。"""

    # 比值測試以牆鐘為判準，基準耗時約 1ms，負載下比值被雜訊推過門檻，
    # 故不進主套件；手動執行 -m wallclock
    @pytest.mark.wallclock
    @pytest.mark.parametrize("shape", sorted(_PERF_SHAPES))
    def test_four_times_length_costs_at_most_eight_times(self, shape):
        build = _PERF_SHAPES[shape]
        n = _PERF_N_BY_SHAPE[shape]
        t_n = _best_time(build(n), repeat=3)
        t_4n = _best_time(build(n * 4), repeat=3)
        assert t_4n < 1.0
        assert t_4n <= 8 * t_n

    # 約 200KB 最壞形態的牆鐘粗門檻（5 秒；線性實測約 0.05 秒）。牆鐘判準，主套件排除。
    _WORST_SHAPES = [
        ("single_sed_long_e_chain", 15000),
        ("sed_word_padding", 33000),
        ("double_quoted_repeated", 7500),
        ("heredoc_body_long", 10000),
    ]

    @pytest.mark.wallclock
    @pytest.mark.parametrize("shape,k", _WORST_SHAPES)
    def test_200kb_worst_shapes_finish_within_coarse_bound(self, shape, k):
        import time
        cmd = _PERF_SHAPES[shape](k)
        assert len(cmd) > 150000
        start = time.monotonic()
        _extract_candidate_paths(cmd)
        assert time.monotonic() - start < 5.0

    @pytest.mark.parametrize("shape,k", _WORST_SHAPES)
    def test_200kb_worst_shapes_extract_without_error(self, shape, k):
        # 不計時：200KB 輸入可完成解析並回傳 list
        cmd = _PERF_SHAPES[shape](k)
        assert len(cmd) > 150000
        assert isinstance(_extract_candidate_paths(cmd), list)


# 計數方法（確定性，不受負載影響）：
#   work = sys.setprofile 觀測到的函式呼叫事件數（Python 與 C 的 call 皆計）
#        + 交給 _scan_sed 的 token 走訪數（每次呼叫從起點到陳述尾的 token 數）
# 線性實作的 work 與輸入長度成正比；平方級回退（重掃）使 4n 的 work 趨近 16 倍。
_WORK_N = 500
_WORK_CONSTANT = 100


def _work_units(cmd, rescan_sed=False):
    import sys as _sys
    visited = [0]
    calls = [0]
    original = hook_module._scan_sed

    def counting_sed(toks, j, out):
        visited[0] += len(toks) - j
        end = original(toks, j, out)
        # rescan_sed：模擬平方級回退（每個 sed 後只前進一格，使後續 token 被重複掃描）
        return j if rescan_sed else end

    def profiler(frame, event, arg):
        if event in ("call", "c_call"):
            calls[0] += 1

    with patch.object(hook_module, "_scan_sed", counting_sed):
        _sys.setprofile(profiler)
        try:
            _extract_candidate_paths(cmd)
        finally:
            _sys.setprofile(None)
    return calls[0] + visited[0]


class TestLinearWorkByCount:
    """4n 長度的工作量 <= 4 * (n 長度的工作量) + 小常數。"""

    @pytest.mark.parametrize("shape", sorted(_PERF_SHAPES))
    def test_work_grows_linearly(self, shape):
        build = _PERF_SHAPES[shape]
        w_n = _work_units(build(_WORK_N))
        w_4n = _work_units(build(_WORK_N * 4))
        assert w_4n <= 4 * w_n + _WORK_CONSTANT

    @pytest.mark.parametrize("shape", ["sed_word_padding", "bare_sed_padding"])
    def test_counting_detects_quadratic_rescan(self, shape):
        # 正向對照：每個 sed 重掃後段 token 的平方級變體，在同一個計數斷言下必須翻紅
        build = _PERF_SHAPES[shape]
        w_n = _work_units(build(_WORK_N), rescan_sed=True)
        w_4n = _work_units(build(_WORK_N * 4), rescan_sed=True)
        assert not (w_4n <= 4 * w_n + _WORK_CONSTANT)


class TestHeredocAndQuotedTextIgnored:
    """284.4：heredoc 正文與引號內的寫入描述不是命令，不擋；真實寫入仍擋。"""

    @pytest.mark.parametrize("cmd", [
        "ticket track append-log x <<'EOF'\nsed -i 's/a/b/' lib/foo.dart\nEOF",
        "ticket track append-log x <<EOF\ncat > lib/foo.dart\ncp a test/b_test.dart\nEOF",
        "git commit -m \"fix: sed -i s/a/b/ lib/foo.dart\"",
        "echo 'cat > lib/foo.dart'",
        "echo \"tee lib/foo.dart\"",
        "echo hi # sed -i x lib/foo.dart",
    ])
    def test_description_text_extracts_nothing(self, cmd, logger):
        assert _extract_candidate_paths(cmd) == []
        assert _find_boundary_violation(cmd, logger) is None

    def test_real_write_after_heredoc_terminator_still_caught(self, logger):
        cmd = "cat <<'EOF'\nnote\nEOF\nsed -i s/a/b/ lib/foo.dart"
        assert _find_boundary_violation(cmd, logger) == "lib/foo.dart"

    def test_real_write_before_heredoc_still_caught(self, logger):
        cmd = "sed -i s/a/b/ lib/foo.dart; cat <<'EOF'\nnote\nEOF"
        assert _find_boundary_violation(cmd, logger) == "lib/foo.dart"

    def test_shell_heredoc_body_is_executed_so_still_caught(self, logger):
        cmd = "bash <<'EOF'\ncat > lib/foo.dart\nEOF"
        assert _find_boundary_violation(cmd, logger) == "lib/foo.dart"

    def test_python_double_quoted_open_still_caught(self, logger):
        cmd = 'python3 -c "open(\'lib/bar.dart\', \'w\')"'
        assert _find_boundary_violation(cmd, logger) == "lib/bar.dart"

    def test_open_text_outside_python_not_caught(self, logger):
        cmd = "echo \"open('lib/bar.dart', 'w')\""
        assert _find_boundary_violation(cmd, logger) is None

    @pytest.mark.parametrize("cmd,expected", [
        ("echo hi 2> lib/foo.dart", []),
        ("echo hi >&2", []),
        ("echo hi > lib/foo.dart", ["lib/foo.dart"]),
        ("echo hi >> \"lib/foo.dart\"", ["lib/foo.dart"]),
        ("cp -r a b lib/dest", ["lib/dest"]),
        ("tee -a one.txt lib/two.dart", ["one.txt", "lib/two.dart"]),
        ("sed -i -e 's/a/b/' -e 's/c/d/' f1 f2", ["f1", "f2"]),
        ("sed -n 's/a/b/p' f1", []),
        ("(sed -i s/a/b/ lib/foo.dart)", ["lib/foo.dart"]),
        ("echo $(sed -i s/a/b/ lib/foo.dart)", ["lib/foo.dart"]),
    ])
    def test_real_write_forms(self, cmd, expected):
        assert _extract_candidate_paths(cmd) == expected
