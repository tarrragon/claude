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

_REPO_ROOT = hook_dir.parent.parent  # 本 checkout 根目錄（含 .git）
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

    def test_subagent_environment_denied_for_scope_write(self, monkeypatch):
        # 0.5.0-W1-284.1：subagent 不再一律放行，寫入範圍內路徑改為 deny
        exit_code = self._run_main(
            monkeypatch,
            {"tool_name": "Bash", "tool_input": {"command": "cat > lib/foo.dart <<'EOF'\nx\nEOF"}, "agent_id": "sub-1", "cwd": str(_REPO_ROOT)},
            is_subagent=True,
        )
        assert exit_code == 2

    def test_subagent_environment_out_of_scope_allowed(self, monkeypatch):
        exit_code = self._run_main(
            monkeypatch,
            {"tool_name": "Bash", "tool_input": {"command": "echo x > docs/notes.md"}, "agent_id": "sub-1", "cwd": str(_REPO_ROOT)},
            is_subagent=True,
        )
        assert exit_code == 0

    def test_dev_branch_still_denied_for_scope_write(self, monkeypatch):
        # 新的路徑範圍檢查不受開發分支跳過影響（feat/* worktree 內不得失效）
        exit_code = self._run_main(
            monkeypatch,
            {"tool_name": "Bash", "tool_input": {"command": "cat > lib/foo.dart <<'EOF'\nx\nEOF"}, "cwd": str(_REPO_ROOT)},
            branch="feat/some-feature",
        )
        assert exit_code == 2

    def test_dev_branch_skips_main_thread_layer_only(self, monkeypatch):
        # 開發分支跳過仍作用於既有主線程層：*.dart 在範圍外目錄不被擋
        exit_code = self._run_main(
            monkeypatch,
            {"tool_name": "Bash", "tool_input": {"command": "cat > docs/x.dart <<'EOF'\nx\nEOF"}, "cwd": str(_REPO_ROOT)},
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
        ("echo hi 2> lib/foo.dart", ["lib/foo.dart"]),
        ("echo hi &> lib/foo.dart", ["lib/foo.dart"]),
        ("echo hi >& lib/foo.dart", ["lib/foo.dart"]),
        ("echo hi 2>> lib/foo.dart", ["lib/foo.dart"]),
        ("echo hi 2>&1", []),
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


# ============================================================================
# 0.5.0-W1-284.1：主線程與代理人共用的路徑範圍阻擋
# ============================================================================

_SCOPE_TARGETS = [
    ".claude/hooks/x-hook.py",
    "lib/a.dart",
    "test/a_test.dart",
    "integration_test/a_test.dart",
]

# 各寫入寫法，{t} 為目標路徑
_WRITE_FORMS = {
    "cat_append_heredoc": "cat >> {t} <<'EOF'\nx\nEOF",
    "printf_append": "printf '%s' x >> {t}",
    "tee_append": "echo x | tee -a {t}",
    "python_open": "python3 - <<'EOF'\nopen('{t}', 'w').write('x')\nEOF",
    "sed_inplace_bsd_empty": "sed -i \"\" 's/a/b/' {t}",
    "cp_dest": "cp /tmp/src.txt {t}",
    "mv_dest": "mv /tmp/src.txt {t}",
}


@pytest.fixture
def checkout(tmp_path):
    """假 checkout 根目錄（含 .git 目錄）。"""
    (tmp_path / ".git").mkdir()
    return tmp_path.resolve()


def _scope(cmd, cwd, logger):
    return hook_module._find_scope_violation(cmd, str(cwd), logger)


class TestScopeViolationDenied:
    """正向對照：範圍內路徑對任何呼叫身份（主線程、代理人）皆 deny。"""

    @pytest.mark.parametrize("target", _SCOPE_TARGETS)
    @pytest.mark.parametrize("form", sorted(_WRITE_FORMS))
    def test_write_form_to_scope_target_denied(self, form, target, checkout, logger):
        cmd = _WRITE_FORMS[form].format(t=target)
        assert _scope(cmd, checkout, logger) == target

    def test_relative_path_resolved_against_cwd(self, checkout, logger):
        (checkout / "docs").mkdir()
        assert _scope("cat > ../lib/a.dart", checkout / "docs", logger) == "lib/a.dart"

    def test_cwd_inside_scope_dir(self, checkout, logger):
        (checkout / "lib").mkdir()
        assert _scope("echo x > a.dart", checkout / "lib", logger) == "lib/a.dart"

    def test_cd_then_write_in_same_command(self, checkout, logger):
        assert _scope("(cd lib && cat > a.dart <<'EOF'\nx\nEOF\n)", checkout, logger) == "lib/a.dart"

    def test_absolute_path_inside_checkout(self, checkout, logger):
        assert _scope(f"echo x > {checkout}/test/a.dart", checkout, logger) == "test/a.dart"

    def test_claude_project_dir_variable_resolved(self, checkout, logger):
        assert _scope("echo x > $CLAUDE_PROJECT_DIR/lib/a.dart", checkout, logger) == "lib/a.dart"
        assert _scope("echo x > ${CLAUDE_PROJECT_DIR}/lib/a.dart", checkout, logger) == "lib/a.dart"

    def test_worktree_path_seen_from_main_checkout(self, checkout, logger):
        (checkout / ".claude" / "worktrees" / "w1").mkdir(parents=True)
        assert _scope("echo x > .claude/worktrees/w1/lib/a.dart", checkout, logger) == "lib/a.dart"
        assert _scope("echo x > .claude/worktrees/w1/.claude/rules/r.md", checkout, logger) == ".claude/rules/r.md"

    def test_main_checkout_path_seen_from_worktree(self, checkout, logger):
        wt = checkout / ".claude" / "worktrees" / "w1"
        wt.mkdir(parents=True)
        (wt / ".git").write_text("gitdir: x\n")
        assert _scope(f"echo x > {checkout}/lib/a.dart", wt, logger) == "lib/a.dart"
        assert _scope("echo x > lib/a.dart", wt, logger) == "lib/a.dart"

    def test_symlink_into_scope_denied(self, checkout, logger):
        (checkout / "lib").mkdir()
        (checkout / "docs").mkdir()
        (checkout / "docs" / "ln").symlink_to(checkout / "lib")
        assert _scope("echo x > docs/ln/a.dart", checkout, logger) == "lib/a.dart"


class TestScopeViolationAllowed:
    """豁免與範圍外：每個豁免項一筆應放行。"""

    @pytest.mark.parametrize("cmd", [
        # 暫存區、變數路徑、/dev/null
        "echo x > /tmp/out.txt",
        "echo x > $S/x",
        "echo x > ${S}/x",
        "echo x > ~/note.txt",
        "echo x > /dev/null",
        "cmd > /dev/null 2>&1",
        # git 自身
        "git mv old.dart lib/new.dart",
        "git -C . mv test/a.dart test/b.dart",
        "git worktree add .claude/worktrees/w2 -b feat/x",
        "git worktree remove .claude/worktrees/w2",
        "echo x > .git/info/exclude",
        # worktree 目錄本身與其範圍外內容
        "echo x > .claude/worktrees/w2/notes.txt",
        # 建置與快取產物
        "echo x > .venv/pyvenv.cfg",
        "echo x > .pytest_cache/v",
        "echo x > lib/.dart_tool/x",
        # 執行期狀態檔（.gitignore 列出的 .claude 本地產物）
        "echo x > .claude/pm-status.json",
        "echo x > .claude/plans/p.md",
        "touch .claude/.zhtw-mcp-skip",
        "echo x > .claude/.zhtw-mcp-skip",
        # 例行作業：路徑不出現在命令文字
        "uv --directory .claude/hooks run pytest tests/test_x.py -q",
        "uv --directory .claude/hooks run pytest tests/test_x.py -q 2>&1 | tail -20",
        "ticket track claim 0.5.0-W1-1 --as x",
        "doc validate",
        "git worktree add .claude/worktrees/x",
        "git mv a.md b.md",
        "git -C . mv a.md b.md",
        "GIT_X=1 git -c core.a=b -C . mv a.md b.md",
        # 一般文件與其他目錄
        "echo x > docs/notes.md",
        "cat lib/a.dart",
        "grep -rn foo lib/ test/",
        "flutter test test/unit/foo_test.dart",
        # CLI 自寫檔：目標路徑不出現在命令文字，不是 shell 重導向
        "ticket track append-log 0.5.0-W1-1 --section Solution \"text\"",
        "ticket track commit --worktree 0.5.0-W1-1",
        "doc validate",
        "doc uc verify 2>&1",
        # 描述文字不是寫入
        "git commit -m \"fix: cat > lib/a.dart\"",
    ])
    def test_allowed(self, cmd, checkout, logger):
        assert _scope(cmd, checkout, logger) is None

    def test_path_outside_checkout_allowed(self, checkout, tmp_path_factory, logger):
        other = tmp_path_factory.mktemp("other").resolve()
        assert _scope(f"echo x > {other}/lib/a.dart", checkout, logger) is None

    def test_scratchpad_style_absolute_path_allowed(self, checkout, logger):
        cmd = "cat > /private/tmp/claude-501/proj/session/scratchpad/lib/x.txt <<'EOF'\nx\nEOF"
        assert _scope(cmd, checkout, logger) is None


class TestScopeUnparseableFailOpen:
    """動態組成的路徑無法靜態判定：放行並記錄為殘留風險（盤點表列）。"""

    @pytest.mark.parametrize("cmd", [
        "python3 -c \"p=input()+'/a.dart'; open(p,'w')\"",
        "echo x > $OTHER/lib/a.dart",
    ])
    def test_dynamic_path_not_resolved(self, cmd, checkout, logger):
        assert _scope(cmd, checkout, logger) is None


def _git(*args, cwd):
    import subprocess
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True,
                   env={"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
                        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
                        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"})


def _make_repo(base, name):
    repo = base / name
    repo.mkdir()
    _git("init", "-q", "-b", "main", cwd=repo)
    (repo / "README.md").write_text("x\n")
    _git("add", "README.md", cwd=repo)
    _git("commit", "-q", "-m", "init", cwd=repo)
    return repo


@pytest.fixture
def repo_pair(tmp_path):
    """真實主 repo + git worktree add 出的同層 worktree（<repo>-<ticket> 版面）。"""
    main_repo = _make_repo(tmp_path, "proj")
    sibling = tmp_path / "proj-T1"
    _git("worktree", "add", "-q", "-b", "feat/T1", str(sibling), cwd=main_repo)
    return main_repo.resolve(), sibling.resolve()


class TestSiblingWorktreeScope:
    """E2：cwd 與目標分屬同 repo 的不同 checkout（主 checkout 與同層 worktree）。"""

    _SCOPE_FILES = ["lib/a.dart", "test/a_test.dart", "integration_test/a.dart", ".claude/skills/x/y.py"]

    @pytest.mark.parametrize("target", _SCOPE_FILES)
    def test_redirect_main_cwd_to_sibling(self, repo_pair, logger, target):
        main_repo, sibling = repo_pair
        assert _scope(f"echo x > {sibling}/{target}", main_repo, logger) == target

    @pytest.mark.parametrize("target", _SCOPE_FILES)
    def test_redirect_sibling_cwd_to_main(self, repo_pair, logger, target):
        main_repo, sibling = repo_pair
        assert _scope(f"echo x > {main_repo}/{target}", sibling, logger) == target

    def test_python_heredoc_open_main_cwd_to_sibling(self, repo_pair, logger):
        main_repo, sibling = repo_pair
        cmd = f"python3 - <<'EOF'\nopen('{sibling}/.claude/skills/w/x.py', 'w').write('x')\nEOF"
        assert _scope(cmd, main_repo, logger) == ".claude/skills/w/x.py"

    def test_python_heredoc_open_sibling_cwd_to_main(self, repo_pair, logger):
        main_repo, sibling = repo_pair
        cmd = f"python3 - <<'EOF'\nopen('{main_repo}/lib/x.dart', 'w').write('x')\nEOF"
        assert _scope(cmd, sibling, logger) == "lib/x.dart"

    def test_nonexistent_ancestors_resolved(self, repo_pair, logger):
        main_repo, sibling = repo_pair
        assert _scope(f"echo x > {sibling}/lib/deep/er/new.dart", main_repo, logger) == "lib/deep/er/new.dart"

    def test_sibling_non_scope_file_allowed(self, repo_pair, logger):
        main_repo, sibling = repo_pair
        assert _scope(f"echo x > {sibling}/docs/n.md", main_repo, logger) is None
        assert _scope(f"echo x > {sibling}/.claude/plans/p.md", main_repo, logger) is None

    def test_different_repo_same_layout_allowed(self, repo_pair, tmp_path, logger):
        main_repo, _ = repo_pair
        other = _make_repo(tmp_path, "proj-other")
        assert _scope(f"echo x > {other}/lib/a.dart", main_repo, logger) is None
        assert _scope(f"echo x > {other}/.claude/hooks/a.py", main_repo, logger) is None

    def test_same_repo_predicate_contrast(self, repo_pair, tmp_path):
        main_repo, sibling = repo_pair
        other = _make_repo(tmp_path, "proj-other")
        assert hook_module._same_repo(str(sibling), str(main_repo)) is True
        assert hook_module._same_repo(str(other), str(main_repo)) is False

    def test_routine_commands_allowed(self, repo_pair, logger):
        main_repo, sibling = repo_pair
        for cmd in [
            f"git worktree add {main_repo}-T2 -b feat/T2",
            f"git -C {sibling} status",
            f"git worktree add {main_repo}/.claude/worktrees/merge-gate-1 HEAD",
            f"uv --directory {sibling}/.claude/hooks run pytest tests/x.py -q",
            "echo x > /dev/null",
            f"echo x > {sibling}/../notes.txt",
        ]:
            assert _scope(cmd, main_repo, logger) is None, cmd

    def test_unresolvable_gitlink_not_blocked(self, tmp_path, logger):
        """gitlink 無法解析 common dir：不額外阻擋（取向 fail-open，見 Solution）。"""
        main_repo = _make_repo(tmp_path, "proj")
        broken = tmp_path / "proj-broken"
        broken.mkdir()
        (broken / ".git").write_text("gitdir: /nonexistent/zzz\n")
        assert _scope(f"echo x > {broken}/lib/a.dart", main_repo, logger) is None


class TestFailClosedDeclaration:
    """異常語意：守衛宣告 fail_closed（分派層掃描此宣告決定逾時／例外時 exit 2）。"""

    def test_hook_declares_fail_closed(self):
        import re
        text = (hook_dir / "bash-write-boundary-guard-hook.py").read_text(encoding="utf-8")
        assert re.search(r"fail_closed\s*=\s*True", text)

    def test_exception_in_scope_check_yields_block_exit(self, monkeypatch):
        import io
        import json as json_mod
        monkeypatch.setattr(sys, "stdin", io.StringIO(json_mod.dumps(
            {"tool_name": "Bash", "tool_input": {"command": "echo hi"}, "cwd": str(_REPO_ROOT)})))

        def boom(*a, **k):
            raise RuntimeError("boom")

        with patch.object(hook_module, "_find_scope_violation", boom), \
             patch.object(hook_module, "get_current_branch", return_value="main"):
            assert hook_module.run_hook_safely(main, "bash-write-boundary-guard-test", fail_closed=True) == 2


class TestReviewFixes:
    """合併前審查 #1 至 #8 的修正；每筆先紅後綠。"""

    # #1 open() 只有寫入模式才算寫入
    @pytest.mark.parametrize("cmd", [
        "python3 -c \"import json;json.load(open('.claude/settings.json'))\"",
        "python3 - <<'EOF'\nprint(open('lib/x.dart').read())\nEOF",
        "python3 -c \"open('lib/x.dart', 'r')\"",
        "python3 -c \"open('lib/x.dart', 'rb')\"",
        "python3 -c \"open('lib/x.dart', mode='r')\"",
    ])
    def test_open_read_modes_allowed(self, cmd, checkout, logger):
        assert _scope(cmd, checkout, logger) is None

    @pytest.mark.parametrize("mode", ["w", "a", "x", "r+", "wb", "ab"])
    def test_open_write_modes_denied(self, mode, checkout, logger):
        cmd = f"python3 -c \"open('lib/x.dart', '{mode}')\""
        assert _scope(cmd, checkout, logger) == "lib/x.dart"

    def test_open_mode_keyword_write_denied(self, checkout, logger):
        assert _scope("python3 -c \"open('lib/x.dart', mode='w')\"", checkout, logger) == "lib/x.dart"

    # #2 1> 與 1>> 是寫入；2> 等 fd 檔案目標亦為寫入
    @pytest.mark.parametrize("cmd", ["echo x 1> lib/a.dart", "echo x 1>> lib/a.dart"])
    def test_fd1_redirect_denied(self, cmd, checkout, logger):
        assert _scope(cmd, checkout, logger) == "lib/a.dart"

    @pytest.mark.parametrize("cmd,path", [
        ("cmd &> lib/a.dart", "lib/a.dart"),
        ("cmd 2> test/log", "test/log"),
        ("cmd 2>> .claude/x", ".claude/x"),
        ("cmd >& lib/a", "lib/a"),
        ("cmd &>> lib/a.dart", "lib/a.dart"),
        ("cmd 0> lib/a.dart", "lib/a.dart"),
        ("cmd 0>> test/x", "test/x"),
    ])
    def test_fd_redirect_file_target_denied(self, cmd, path, checkout, logger):
        assert _scope(cmd, checkout, logger) == path

    def test_fd_redirect_worktree_path_denied(self, checkout, logger):
        (checkout / ".claude" / "worktrees" / "w1").mkdir(parents=True)
        assert _scope("cmd 2> .claude/worktrees/w1/lib/a.dart", checkout, logger) == "lib/a.dart"

    @pytest.mark.parametrize("cmd", [
        "echo x 2>&1", "echo x 1>&2", "echo x >&2", "echo x <&0",
        "echo x 2> /dev/null", "echo x &>/dev/null", "echo x >& /dev/null",
        "cmd >&-", "cmd < lib/a.dart", "cmd 0<&-", "uv run pytest 2>&1 | tail -20",
    ])
    def test_fd_dup_and_devnull_allowed(self, cmd, checkout, logger):
        assert _scope(cmd, checkout, logger) is None

    # #3 五種新增偵測
    @pytest.mark.parametrize("cmd", [
        "perl -pi -e 's/a/b/' lib/a.dart",
        "perl -i.bak -pe 's/a/b/' lib/a.dart",
        "perl -pi -e 's/a/b/' lib/a.dart test/b.dart",
        "python3 -c \"open(f'lib/a.dart','w')\"",
        "python3 -c \"from pathlib import Path; Path('lib/a.dart').write_text('x')\"",
        "python3 -c \"import pathlib; pathlib.Path('lib/a.dart').write_bytes(b'x')\"",
        "cp -t lib/ a.dart",
        "mv -t lib a.dart",
        "cp --target-directory=lib a.dart",
        "exec 3> lib/a.dart",
        "exec 4>> lib/a.dart",
    ])
    def test_newly_detected_forms_denied(self, cmd, checkout, logger):
        assert _scope(cmd, checkout, logger) is not None

    @pytest.mark.parametrize("cmd", [
        "perl -e 'print 1' lib/a.dart",
        "perl lib/script.pl",
        "python3 -c \"from pathlib import Path; Path('lib/a.dart').read_text()\"",
        "cp -t /tmp a.dart",
        "exec 3>&1",
        "exec 3> /tmp/x",
    ])
    def test_new_forms_nonwrite_allowed(self, cmd, checkout, logger):
        assert _scope(cmd, checkout, logger) is None

    # #4 #5 子殼內的 cd 位移在 ) 後還原
    def test_subshell_cd_restored_after_close(self, checkout, logger):
        (checkout / "lib").mkdir()
        assert _scope("(cd /tmp); echo hi > lib/a.dart", checkout, logger) == "lib/a.dart"

    def test_subshell_cd_into_scope_not_leaked(self, checkout, logger):
        (checkout / "lib").mkdir()
        assert _scope("(cd lib); echo > x", checkout, logger) is None

    def test_cd_inside_subshell_still_applies_inside(self, checkout, logger):
        assert _scope("(cd lib && echo > x)", checkout, logger) == "lib/x"

    # #6 pushd 視同 cd；cd - 無法判定
    def test_pushd_acts_like_cd(self, checkout, logger):
        assert _scope("pushd lib && echo > a", checkout, logger) == "lib/a"

    def test_cd_dash_is_undecidable(self, checkout, logger):
        assert _scope("cd - && echo > lib/a", checkout, logger) is None

    # #8 脫困指引
    def test_deny_message_has_escape_hint(self, monkeypatch, capsys):
        import io
        import json as json_mod
        monkeypatch.setattr(sys, "stdin", io.StringIO(json_mod.dumps(
            {"tool_name": "Bash", "tool_input": {"command": "echo x >> lib/a.dart"}, "cwd": str(_REPO_ROOT)})))
        with patch.object(hook_module, "get_current_branch", return_value="main"):
            assert main() == 2
        assert ".claude/hooks/bash-write-boundary-guard-hook.py" in capsys.readouterr().out


class TestDenyMessage:
    def test_deny_reason_names_edit_write_and_git_mv(self, monkeypatch, capsys):
        import io
        import json as json_mod
        monkeypatch.setattr(sys, "stdin", io.StringIO(json_mod.dumps(
            {"tool_name": "Bash", "tool_input": {"command": "echo x >> test/a_test.dart"},
             "agent_id": "sub-1", "cwd": str(_REPO_ROOT)})))
        with patch.object(hook_module, "get_current_branch", return_value="main"):
            assert main() == 2
        out = capsys.readouterr().out
        assert "Edit" in out and "Write" in out and "git mv" in out
        assert "test/a_test.dart" in out

    def test_deny_reason_forbids_bash_retry_and_names_move_lines(self, monkeypatch, capsys):
        """0.5.0-W1-365.6：被擋當下明示禁止換 Bash 寫法重試，並指向 move-lines 通道。"""
        import io
        import json as json_mod
        monkeypatch.setattr(sys, "stdin", io.StringIO(json_mod.dumps(
            {"tool_name": "Bash", "tool_input": {"command": "echo x >> test/a_test.dart"},
             "agent_id": "sub-1", "cwd": str(_REPO_ROOT)})))
        with patch.object(hook_module, "get_current_branch", return_value="main"):
            assert main() == 2
        out = capsys.readouterr().out
        assert "不得改用其他 Bash 寫法" in out and "python heredoc" in out
        assert "NeedsContext" in out and "回報 PM" in out
        assert "ticket track move-lines" in out and "where.files" in out


class TestExemptionNarrowing:
    """0.5.0-W1-369：收窄後的豁免。E2 應擋輸入、E1 例行放行見 TestScopeViolationAllowed。"""

    @pytest.mark.parametrize("target", [
        ".claude/settings.local.json",
        ".claude/dispatch-active.json", ".claude/dispatch-active.lock",
        ".claude/hook-state/s.json", ".claude/state/s.json", ".claude/handoff/h.json",
        ".claude/hook-logs/foo/a.log", ".claude/logs/worktree-merge.log",
        ".claude/.sync-state.json", ".claude/.version-release.yaml",
    ])
    def test_state_files_with_readers_denied(self, target, checkout, logger):
        assert _scope(f"echo x > {target}", checkout, logger) == target

    @pytest.mark.parametrize("target", [
        ".claude/hooks/__pycache__/a.pyc", ".claude/hooks/.venv/pyvenv.cfg",
        ".claude/lib/__pycache__/a.pyc", ".claude/skills/ticket/.venv/x",
        ".claude/hooks/tests/__pycache__/a.pyc",
    ])
    def test_build_artifacts_under_claude_denied(self, target, checkout, logger):
        assert _scope(f"echo x > {target}", checkout, logger) == target

    def test_cp_pyc_into_hooks_denied(self, checkout, logger):
        t = ".claude/hooks/__pycache__/a.pyc"
        assert _scope(f"cp a.pyc {t}", checkout, logger) == t

    @pytest.mark.parametrize("cmd", [
        "echo git; mv x .claude/y",
        "git status && mv x .claude/y",
        "git log | mv x .claude/y",
        "echo git mv; cp x .claude/y",
    ])
    def test_non_command_word_git_does_not_exempt_mv(self, cmd, checkout, logger):
        assert _scope(cmd, checkout, logger) == ".claude/y"

    @pytest.mark.parametrize("cmd", [
        "git mv x .claude/y", "git -C . mv x .claude/y",
        "FOO=1 git --no-pager mv x .claude/y", "git -c a=b mv x .claude/y",
    ])
    def test_git_mv_command_word_still_exempt(self, cmd, checkout, logger):
        assert _scope(cmd, checkout, logger) is None


class TestDecisionLog:
    """0.5.0-W1-366：每個放行／阻擋分支記一行 decision=... source=... reason=... targets=... cmd=..."""

    def _run(self, monkeypatch, payload, is_subagent=False, branch="main"):
        import io
        import json as json_mod

        records = []

        class _H(logging.Handler):
            def emit(self, record):
                records.append(record.getMessage())

        lg = logging.getLogger("test-decision-log")
        lg.handlers = [_H()]
        lg.setLevel(logging.DEBUG)
        lg.propagate = False
        monkeypatch.setattr(sys, "stdin", io.StringIO(json_mod.dumps(payload)))
        with patch.object(hook_module, "setup_hook_logging", return_value=lg), \
             patch.object(hook_module, "is_subagent_environment", return_value=is_subagent), \
             patch.object(hook_module, "get_current_branch", return_value=branch), \
             patch.object(hook_module, "is_allowed_branch", return_value=(branch != "main")):
            code = main()
        lines = [m for m in records if m.startswith("decision=")]
        assert len(lines) == 1, records
        return code, lines[0]

    def _bash(self, cmd, **extra):
        d = {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": str(_REPO_ROOT)}
        d.update(extra)
        return d

    def test_allow_no_boundary_violation(self, monkeypatch):
        code, line = self._run(monkeypatch, self._bash("echo hi > docs/x.md"))
        assert code == 0
        assert line.startswith("decision=allow source=main reason=no_boundary_violation ")
        assert "targets=['docs/x.md']" in line and "cmd=echo hi > docs/x.md" in line

    def test_allow_empty_targets(self, monkeypatch):
        _, line = self._run(monkeypatch, self._bash("ls -la"))
        assert "reason=no_boundary_violation" in line and "targets=[]" in line

    def test_allow_dev_branch_skip(self, monkeypatch):
        _, line = self._run(monkeypatch, self._bash("echo x > docs/y.dart"), branch="feat/a")
        assert "decision=allow source=main reason=dev_branch_skip" in line
        assert "docs/y.dart" in line

    def test_allow_subagent_source(self, monkeypatch):
        _, line = self._run(
            monkeypatch, self._bash("echo x > docs/n.md", agent_id="sub-9"), is_subagent=True)
        assert "decision=allow source=agent:sub-9 reason=subagent_no_scope_hit" in line

    def test_allow_non_bash(self, monkeypatch):
        _, line = self._run(monkeypatch, {"tool_name": "Read", "tool_input": {}})
        assert "decision=allow" in line and "reason=non_bash_tool" in line

    def test_allow_empty_command(self, monkeypatch):
        _, line = self._run(monkeypatch, self._bash(""))
        assert "decision=allow" in line and "reason=empty_command" in line

    def test_allow_empty_input(self, monkeypatch):
        code, line = self._run(monkeypatch, {})
        assert code == 0 and "decision=allow" in line and "reason=empty_input" in line

    def test_deny_scope_violation_has_source(self, monkeypatch):
        code, line = self._run(
            monkeypatch, self._bash("echo x >> test/a_test.dart", agent_id="sub-1"), is_subagent=True)
        assert code == 2
        assert "decision=deny source=agent:sub-1 reason=scope_violation targets=['test/a_test.dart']" in line

    def test_deny_boundary_violation(self, monkeypatch):
        # 第一層（範圍阻擋）關閉，單獨觸發第二層主線程模型
        with patch.object(hook_module, "_find_scope_violation", return_value=None):
            code, line = self._run(monkeypatch, self._bash("echo x > lib/q.dart"))
        assert code == 2
        assert "decision=deny source=main reason=boundary_violation targets=['lib/q.dart']" in line

    def test_long_heredoc_not_fully_logged(self, monkeypatch):
        body = "SECRETBODY" * 500
        _, line = self._run(monkeypatch, self._bash(f"cat > docs/h.md <<'EOF'\n{body}\nEOF"))
        assert "SECRETBODY" in line
        assert len(line) < 600 and line.count("SECRETBODY") <= 20
        assert "\n" not in line


class TestDenyMessageNoBangClaim:
    def test_deny_reason_states_bang_not_restricted(self, monkeypatch, capsys):
        import io
        import json as json_mod
        monkeypatch.setattr(sys, "stdin", io.StringIO(json_mod.dumps(
            {"tool_name": "Bash", "tool_input": {"command": "echo x >> test/a_test.dart"},
             "cwd": str(_REPO_ROOT)})))
        with patch.object(hook_module, "get_current_branch", return_value="main"):
            assert main() == 2
        out = capsys.readouterr().out
        assert "同樣會被擋" not in out
        assert "不經過本 hook" in out


# ============================================================================
# 0.5.0-W1-365.1：python 內嵌腳本以 ast 追蹤「變數持有字面路徑後寫入」
# ============================================================================

_AST_WRITE_BODIES = {
    "var_open_w": "p = '.claude/skills/x.md'\nopen(p, 'w').write('x')",
    "path_var_write_text": "from pathlib import Path\np = Path('lib/x.dart')\np.write_text('x')",
    "concat_open": "open('lib/' + 'x.dart', 'w')",
    "path_div_write_bytes": "from pathlib import Path\nq = Path('lib') / 'x.dart'\nq.write_bytes(b'x')",
    "os_path_join": "import os\np = os.path.join('lib', 'x.dart')\nopen(p, 'a')",
    "shutil_copy_dest": "import shutil\nd = 'lib/x.dart'\nshutil.copy('/tmp/a', d)",
    "shutil_move_literal": "import shutil\nshutil.move('/tmp/a', 'lib/x.dart')",
    "os_replace_dest": "import os\nd = 'lib/x.dart'\nos.replace('/tmp/a', d)",
    "os_rename_dest": "import os\nos.rename('/tmp/a', 'lib/x.dart')",
    "func_local": "def f():\n    p = 'lib/x.dart'\n    with open(p, mode='w') as h:\n        h.write('x')\nf()",
    "path_var_open_w": "from pathlib import Path\np = Path('lib/x.dart')\np.open('w')",
}
_AST_READ_BODIES = {
    "open_read": "p = 'lib/x.dart'\nopen(p).read()",
    "open_r": "p = 'lib/x.dart'\nopen(p, 'r').read()",
    "read_text": "from pathlib import Path\np = Path('lib/x.dart')\np.read_text()",
    "read_bytes": "from pathlib import Path\nPath('lib') / 'x.dart'\np = Path('lib/x.dart')\np.read_bytes()",
    "copy_source_only": "import shutil\ns = 'lib/x.dart'\nshutil.copy(s, '/tmp/out')",
}


def _heredoc(body):
    return "python3 - <<'EOF'\n" + body + "\nEOF"


class TestPythonAstVariablePaths:
    @pytest.mark.parametrize("name", sorted(_AST_WRITE_BODIES))
    def test_heredoc_write_extracted(self, name):
        paths = _extract_candidate_paths(_heredoc(_AST_WRITE_BODIES[name]))
        assert any(p.endswith("x.dart") or p.endswith("x.md") for p in paths)

    def test_python_c_variable_write_extracted(self):
        cmd = "python3 -c \"p = 'lib/x.dart'; open(p, 'w').write('x')\""
        assert "lib/x.dart" in _extract_candidate_paths(cmd)

    @pytest.mark.parametrize("name", sorted(_AST_READ_BODIES))
    def test_heredoc_read_only_not_extracted(self, name):
        paths = _extract_candidate_paths(_heredoc(_AST_READ_BODIES[name]))
        assert not any(p.endswith("x.dart") for p in paths)

    def test_syntax_error_falls_back_to_regex(self):
        body = "open('lib/x.dart', 'w')\nthis is $(not python"
        assert "lib/x.dart" in _extract_candidate_paths(_heredoc(body))

    def test_syntax_error_does_not_extract_variable_form(self):
        body = "p = 'lib/x.dart'\nopen(p, 'w')\nthis is $(not python"
        assert "lib/x.dart" not in _extract_candidate_paths(_heredoc(body))


# ============================================================================
# 0.5.0-W1-365.2：shell 層解析（-c／eval、同命令變數、~／$HOME／$(pwd)、cwd 不在 checkout）
# ============================================================================


class TestShellLayerDenied:
    """七種形態寫入受限路徑：修正前放行、修正後 deny。"""

    @pytest.mark.parametrize("shell", ["bash", "sh", "zsh"])
    def test_shell_dash_c_literal(self, shell, checkout, logger):
        assert _scope("%s -c 'echo x > lib/a'" % shell, checkout, logger) == "lib/a"

    def test_bash_combined_flags_dash_c(self, checkout, logger):
        assert _scope("bash -lc 'echo x > lib/a'", checkout, logger) == "lib/a"

    def test_eval_literal(self, checkout, logger):
        assert _scope("eval 'echo x > lib/a'", checkout, logger) == "lib/a"

    def test_dash_c_respects_outer_cd(self, checkout, logger):
        assert _scope("cd lib && bash -c 'echo x > a'", checkout, logger) == "lib/a"

    @pytest.mark.parametrize("use", ["$F", "${F}"])
    def test_var_literal_assignment(self, use, checkout, logger):
        assert _scope("F=lib/a; echo x > %s" % use, checkout, logger) == "lib/a"

    def test_export_assignment(self, checkout, logger):
        assert _scope("export F=lib/a && echo x > $F", checkout, logger) == "lib/a"

    def test_var_chain_of_literals(self, checkout, logger):
        assert _scope("F=lib/a; G=$F; echo x > $G", checkout, logger) == "lib/a"

    def test_var_in_tee_argument(self, checkout, logger):
        assert _scope("F=lib/a; echo x | tee $F", checkout, logger) == "lib/a"

    @pytest.mark.parametrize("prefix", ["~", "$HOME", "${HOME}"])
    def test_home_prefix(self, prefix, checkout, logger, monkeypatch):
        monkeypatch.setenv("HOME", str(checkout))
        assert _scope("echo x > %s/lib/a" % prefix, checkout, logger) == "lib/a"

    def test_var_holding_home_prefix(self, checkout, logger, monkeypatch):
        monkeypatch.setenv("HOME", str(checkout))
        assert _scope("F=~/lib/a; echo x > $F", checkout, logger) == "lib/a"

    @pytest.mark.parametrize("pwd", ["$(pwd)", "`pwd`"])
    def test_pwd_prefix(self, pwd, checkout, logger):
        assert _scope("echo x > %s/lib/a" % pwd, checkout, logger) == "lib/a"

    def test_cwd_outside_checkout_uses_project_dir(self, tmp_path, logger, monkeypatch):
        proj = tmp_path / "proj"
        (proj / ".git").mkdir(parents=True)
        out = tmp_path / "out"
        out.mkdir()
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(proj))
        cmd = "echo x > %s/lib/a" % proj.resolve()
        assert _scope(cmd, out, logger) == "lib/a"


class TestShellLayerAllowed:
    """E1：只讀、範圍外、無法判定、無 CLAUDE_PROJECT_DIR 時維持放行。"""

    @pytest.mark.parametrize("cmd", [
        "bash -c 'cat lib/a'",
        "bash -c 'echo x > docs/a'",
        "eval 'cat lib/a'",
        "F=/tmp/out.txt; echo x > $F",
        "F=docs/a; echo x > $F",
        "F=$(date); echo x > $F",
        "F=$OTHER/lib/a; echo x > $F",
        "echo x > $UNSET/lib/a",
        "echo x > ~other/lib/a",
        "F=$(pwd)/lib/a; echo x > $F",
        "bash -c 'echo x > $UNSET/lib/a'",
    ])
    def test_allowed(self, cmd, checkout, logger):
        assert _scope(cmd, checkout, logger) is None

    def test_cwd_outside_without_project_dir_unchanged(self, tmp_path, logger, monkeypatch):
        proj = tmp_path / "proj"
        (proj / ".git").mkdir(parents=True)
        out = tmp_path / "out"
        out.mkdir()
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
        assert _scope("echo x > %s/lib/a" % proj.resolve(), out, logger) is None

    def test_home_outside_checkout_allowed(self, checkout, logger, monkeypatch, tmp_path):
        other = tmp_path / "elsewhere"
        other.mkdir()
        monkeypatch.setenv("HOME", str(other))
        assert _scope("echo x > ~/lib/a", checkout, logger) is None


class TestSkippedReasons:
    """逐候選跳過原因併入判定日誌，不改變放行／阻擋結果。"""

    def test_skipped_collects_reasons(self, checkout, logger):
        skipped = []
        cmd = "echo a > docs/x.md; echo b > $UNSET/y"
        assert hook_module._find_scope_violation(cmd, str(checkout), logger, skipped) is None
        assert skipped == ["docs/x.md:out_of_scope", "$UNSET/y:unresolvable"]

    def test_deny_does_not_list_hit(self, checkout, logger):
        skipped = []
        cmd = "echo a > docs/x.md; echo b > lib/y"
        assert hook_module._find_scope_violation(cmd, str(checkout), logger, skipped) == "lib/y"
        assert skipped == ["docs/x.md:out_of_scope"]

    def test_log_line_has_skipped_field(self, monkeypatch):
        code, line = TestDecisionLog._run(
            self, monkeypatch, TestDecisionLog._bash(self, "echo hi > docs/x.md; echo b > $UNSET/y"))
        assert code == 0
        assert "skipped=['docs/x.md:out_of_scope', '$UNSET/y:unresolvable']" in line

    def test_log_line_empty_skipped_on_early_exit(self, monkeypatch):
        code, line = TestDecisionLog._run(
            self, monkeypatch, {"tool_name": "Read", "tool_input": {}})
        assert code == 0 and "skipped=[]" in line


# ============================================================================
# 0.5.0-W1-365.2 第二輪：非必然執行的賦值、CLAUDE_PROJECT_DIR／HOME 命令內賦值、L7 實例
# ============================================================================


class TestAssignmentCertainty:
    """子殼、管線、&&／|| 之後的賦值不得成為放行依據；CLAUDE_PROJECT_DIR／HOME 賦值不得覆寫。"""

    @pytest.mark.parametrize("cmd", [
        "(CLAUDE_PROJECT_DIR=/tmp); echo x > $CLAUDE_PROJECT_DIR/lib/a",
        "true && CLAUDE_PROJECT_DIR=/tmp; echo x > $CLAUDE_PROJECT_DIR/lib/a",
        "false || CLAUDE_PROJECT_DIR=/tmp; echo x > ${CLAUDE_PROJECT_DIR}/lib/a",
        "CLAUDE_PROJECT_DIR=/tmp; echo x > $CLAUDE_PROJECT_DIR/lib/a",
        "echo y | CLAUDE_PROJECT_DIR=/tmp; echo x > $CLAUDE_PROJECT_DIR/lib/a",
    ])
    def test_project_dir_assignment_never_allows(self, cmd, checkout, logger, monkeypatch):
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(checkout))
        assert _scope(cmd, checkout, logger) == "lib/a"

    def test_home_assignment_expands_tilde(self, checkout, logger):
        assert _scope("HOME=%s; echo x > ~/lib/a" % checkout, checkout, logger) == "lib/a"

    def test_home_assignment_expands_dollar_home(self, checkout, logger):
        assert _scope("HOME=%s; echo x > $HOME/lib/a" % checkout, checkout, logger) == "lib/a"

    def test_real_home_form_still_checked(self, checkout, logger, monkeypatch):
        monkeypatch.setenv("HOME", str(checkout))
        assert _scope("HOME=/tmp; echo x > ~/lib/a", checkout, logger) == "lib/a"

    def test_unresolvable_home_assignment_still_checks_real_home(self, checkout, logger, monkeypatch):
        monkeypatch.setenv("HOME", str(checkout))
        assert _scope("HOME=$(date); echo x > ~/lib/a", checkout, logger) == "lib/a"

    @pytest.mark.parametrize("cmd", [
        "(F=lib/a); echo x > $F",
        "true && F=lib/a; echo x > $F",
        "echo y | F=lib/a; echo x > $F",
    ])
    def test_uncertain_plain_assignment_is_unresolvable(self, cmd, checkout, logger):
        # 365.4：不確定賦值的新值併入可能值集合（原未知併入 unresolvable），新值落在範圍內即擋
        skipped = []
        assert hook_module._find_scope_violation(cmd, str(checkout), logger, skipped) == "lib/a"

    @pytest.mark.parametrize("cmd", [
        "F=/tmp/x; echo > $F",
        "HOME=/tmp; echo > ~/x",
        "true; F=lib/a; echo x > $F",
    ])
    def test_e1_unchanged(self, cmd, checkout, logger):
        expected = "lib/a" if "lib/a" in cmd else None
        assert _scope(cmd, checkout, logger) == expected


class TestL7SiblingWorktreeVariable:
    """變數持有同層 worktree 路徑，代理人身份下 sed -i 受限路徑須 deny。"""

    def test_agent_var_sed_inplace_sibling_denied(self, repo_pair, monkeypatch):
        main_repo, sibling = repo_pair
        cmd = "T=%s/.claude/skills/worktree/tests; sed -i 's/a/b/' $T/x.py" % sibling
        payload = {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": str(main_repo),
                   "agent_id": "sub-371"}
        code, line = TestDecisionLog._run(None, monkeypatch, payload, is_subagent=True, branch="feat/x")
        assert code == 2
        assert "decision=deny source=agent:sub-371 reason=scope_violation" in line


class TestExtraCommandWriteTargets:
    """365.3：十種命令的寫入目標抽取（E2：寫受限路徑 deny；E1：只讀與範圍外放行）。"""

    @pytest.mark.parametrize("cmd,expected", [
        ("dd if=/tmp/a of=lib/x bs=1", "lib/x"),
        ("install -m 644 /tmp/a lib/x", "lib/x"),
        ("install -t lib /tmp/a", "lib"),
        ("install -d lib/newdir", "lib/newdir"),
        ("truncate -s 0 lib/x", "lib/x"),
        ("truncate --size=0 lib/x", "lib/x"),
        ("ln -s /tmp/a lib/x", "lib/x"),
        ("ln -sf /tmp/a .claude/hooks/x", ".claude/hooks/x"),
        ("rsync -a /tmp/src/ lib/", "lib"),
        ("rsync -a --exclude '*.o' /tmp/src/ lib/", "lib"),
        ("tar -xzf /tmp/a.tgz -C lib", "lib"),
        ("tar xzf /tmp/a.tgz --directory=lib", "lib"),
        ("tar --extract -f /tmp/a.tar --directory lib", "lib"),
        ("patch lib/a.py /tmp/d.patch", "lib/a.py"),
        ("patch -p1 -d lib < /tmp/d.patch", "lib"),
        ("patch -o lib/out.py /tmp/a.py /tmp/d.patch", "lib/out.py"),
        ("awk -i inplace '{print}' lib/a", "lib/a"),
        ("gawk -i inplace -v x=1 '{print}' lib/a", "lib/a"),
        ("touch lib/new.dart", "lib/new.dart"),
        ("touch -t 202001010000 lib/new.dart", "lib/new.dart"),
        ("ruby -e 'File.write(\"lib/a\", \"x\")'", "lib/a"),
        ("perl -e 'File.write(\"lib/a\", 1)'", "lib/a"),
        ("ruby -e 'File.open(\"lib/a\", \"w\") { }'", "lib/a"),
    ])
    def test_denied(self, cmd, expected, checkout, logger):
        assert _scope(cmd, checkout, logger) == expected

    @pytest.mark.parametrize("cmd", [
        "tar -czf /tmp/a.tgz lib",
        "tar -tf lib/a.tar",
        "tar -xzf lib/a.tgz -C /tmp/out",
        "dd if=lib/a bs=1 count=1",
        "dd if=lib/a of=/tmp/out",
        "rsync -a lib/ /tmp/out/",
        "rsync -a lib/ host:/srv/lib/",
        "ln -s lib/a /tmp/link",
        "patch --dry-run lib/a.py /tmp/d.patch",
        "patch -d /tmp/x < /tmp/d.patch",
        "touch .claude/.zhtw-mcp-skip",
        "touch /tmp/a",
        "truncate -s 0 /tmp/a",
        "awk '{print}' lib/a",
        "awk -i inplace '{print}' /tmp/a",
        "install -m 644 lib/a /tmp/b",
        "ruby -e 'puts File.read(\"lib/a\")'",
        "ruby -e 'File.write(\"/tmp/a\", 1)'",
        "ticket track move-lines 0.5.0-W1-362 --src .claude/skills/ticket/ticket_system/tests/test_track_move_lines.py --lines 1-1 --dst .claude/skills/ticket/references/track-command-update.md --at 1 2>/tmp/ml.err",
    ])
    def test_allowed(self, cmd, checkout, logger):
        assert _scope(cmd, checkout, logger) is None


# ============================================================================
# 0.5.0-W1-365.5：python heredoc／-c 以 sys.argv[n] 作為寫入目標
# ============================================================================


class TestPythonArgvTargets:
    """sys.argv[n] 對應命令列引數，展開後送邊界檢查。"""

    @pytest.mark.parametrize("cmd", [
        # 386 實例：同命令內字面賦值 W，python3 - "$W" heredoc，p=sys.argv[1] 後 open
        "W=lib/sub\npython3 - \"$W\" <<'EOF'\nimport sys\np = sys.argv[1]\nopen(p, 'w').write('x')\nEOF",
        # 直接作寫入目標
        "python3 - lib/a <<'EOF'\nimport sys\nopen(sys.argv[1], 'w').write('x')\nEOF",
        # 第二個引數
        "python3 - /tmp/x lib/b <<'EOF'\nimport sys\nopen(sys.argv[2], 'a').write('x')\nEOF",
        # 直譯器選項不算引數
        "python3 -u - lib/a <<'EOF'\nimport sys\nopen(sys.argv[1], 'w').write('x')\nEOF",
        # -c 變形：[1] 為 code 之後第一個引數
        "python3 -c \"import sys; open(sys.argv[1], 'w').write('x')\" lib/a",
        # os.path.join 與 Path 變形
        "python3 - lib <<'EOF'\nimport sys, os\nopen(os.path.join(sys.argv[1], 'a.dart'), 'w').write('x')\nEOF",
        "python3 - lib <<'EOF'\nimport sys\nfrom pathlib import Path\n(Path(sys.argv[1]) / 'a').write_text('x')\nEOF",
    ])
    def test_denied(self, cmd, checkout, logger):
        assert _scope(cmd, checkout, logger) is not None

    @pytest.mark.parametrize("cmd", [
        "python3 - /tmp/a <<'EOF'\nimport sys\nopen(sys.argv[1], 'w').write('x')\nEOF",
        "python3 - lib/a <<'EOF'\nimport sys\nprint(open(sys.argv[1]).read())\nEOF",
        # argv[0] 為 '-'，不是第一個引數
        "python3 - lib/a <<'EOF'\nimport sys\nopen(sys.argv[0], 'w').write('x')\nEOF",
        # 索引超出引數個數
        "python3 - lib/a <<'EOF'\nimport sys\nopen(sys.argv[2], 'w').write('x')\nEOF",
        "python3 -c \"import sys; open(sys.argv[1], 'w').write('x')\" /tmp/a",
    ])
    def test_allowed(self, cmd, checkout, logger):
        assert _scope(cmd, checkout, logger) is None

    @pytest.mark.parametrize("cmd,raw", [
        # $W 未在同命令內賦值（來自前一個 Bash 呼叫）：本票固有邊界
        ("python3 - \"$W\" <<'EOF'\nimport sys\nopen(sys.argv[1], 'w').write('x')\nEOF", "$W"),
        ("python3 - \"$(date)x\" <<'EOF'\nimport sys\nopen(sys.argv[1], 'w').write('x')\nEOF", "$(date)x"),
    ])
    def test_unresolvable_argument_allowed_and_logged(self, cmd, raw, checkout, logger):
        skipped = []
        assert hook_module._find_scope_violation(cmd, str(checkout), logger, skipped) is None
        assert "%s:unresolvable" % raw in skipped


# ============================================================================
# 0.5.0-W1-365.4：變數保留可能值集合（不確定賦值併入、延遲綁定、複合命令賦值）
# ============================================================================


class TestPossibleValueSets:
    """E2：不確定賦值、延遲綁定、複合命令內賦值不得讓受限路徑放行。"""

    @pytest.mark.parametrize("cmd", [
        "F=lib/a; false && F=/tmp/x; echo x > $F",
        "F=lib/a; true || F=/tmp/x; echo x > $F",
        "F=lib/a; echo y | F=/tmp/x; echo x > $F",
        "F=lib/a; (F=/tmp/x); echo x > $F",
        "F=lib/a; F=/tmp/x & echo x > $F",
    ])
    def test_uncertain_assignment_keeps_prior_value(self, cmd, checkout, logger):
        assert _scope(cmd, checkout, logger) == "lib/a"

    def test_uncertain_assignment_new_value_also_checked(self, checkout, logger):
        assert _scope("F=/tmp/x; false && F=lib/a; echo x > $F", checkout, logger) == "lib/a"

    def test_tilde_bound_at_assignment_time(self, checkout, logger):
        cmd = "HOME=%s; D=~/lib; HOME=/tmp; echo x > $D/a" % checkout
        assert _scope(cmd, checkout, logger) == "lib/a"

    def test_dollar_home_bound_at_assignment_time(self, checkout, logger):
        cmd = "HOME=%s; D=$HOME/lib; HOME=/tmp; echo x > $D/a" % checkout
        assert _scope(cmd, checkout, logger) == "lib/a"

    @pytest.mark.parametrize("cmd", [
        "F=lib/a\nif false; then\nF=/tmp/x\nfi\necho x > $F",
        "F=lib/a\nwhile false; do\nF=/tmp/x\ndone\necho x > $F",
        "F=lib/a\ncase y in\nn) F=/tmp/x ;;\nesac\necho x > $F",
        "F=lib/a\nf() {\nF=/tmp/x\n}\necho x > $F",
        "F=lib/a\nfor i in 1; do\nF=/tmp/x\ndone\necho x > $F",
        "F=lib/a\nif false; then F=/tmp/x; fi\necho x > $F",
    ])
    def test_compound_command_assignment_is_uncertain(self, cmd, checkout, logger):
        assert _scope(cmd, checkout, logger) == "lib/a"

    def test_project_dir_newline_if_still_denied(self, checkout, logger, monkeypatch):
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(checkout))
        cmd = "if false; then\nCLAUDE_PROJECT_DIR=/tmp\nfi\necho x > $CLAUDE_PROJECT_DIR/lib/a"
        assert _scope(cmd, checkout, logger) == "lib/a"

    def test_e1_certain_reassignment_outside_scope_allowed(self, checkout, logger):
        assert _scope("F=lib/a; F=/tmp/x; echo x > $F", checkout, logger) is None

    def test_e1_sequential_statements_after_compound_are_certain(self, checkout, logger):
        cmd = "if true; then\ntrue\nfi\nF=lib/a\nF=/tmp/x\necho x > $F"
        assert _scope(cmd, checkout, logger) is None

    def test_combination_limit_blocks_conservatively(self, checkout, logger):
        cmd = ("A=/tmp/a; true && A=/tmp/b; true && A=/tmp/c; "
               "B=/tmp/a; true && B=/tmp/b; true && B=/tmp/c; "
               "C=/tmp/a; true && C=/tmp/b; true && C=/tmp/c; "
               "echo x > $A/$B/$C")
        assert _scope(cmd, checkout, logger) == "lib/_bash_guard_combination_overflow"

    def test_within_limit_all_outside_allowed(self, checkout, logger):
        cmd = "A=/tmp/a; true && A=/tmp/b; B=/tmp/a; true && B=/tmp/b; echo x > $A/$B"
        assert _scope(cmd, checkout, logger) is None

    def test_python_argv_checked_for_every_possible_value(self, checkout, logger):
        cmd = ("F=lib/a; false && F=/tmp/x; "
               "python3 - $F <<'EOF'\nimport sys\nopen(sys.argv[1], 'w').write('x')\nEOF")
        assert _scope(cmd, checkout, logger) == "lib/a"


# ============================================================================
# 0.5.0-W1-365.7：argv 的三種常見慣用形態（from sys import argv、負索引、別名）
# ============================================================================


class TestPythonArgvIdioms:
    """from sys import argv（含 as）、sys.argv[-k]、a = sys.argv 後 a[n] 對應出的引數沿用邊界檢查。"""

    @pytest.mark.parametrize("cmd", [
        "W=lib/sub\npython3 - \"$W\" <<'EOF'\nfrom sys import argv\nopen(argv[1], 'w').write('x')\nEOF",
        "python3 - lib/a <<'EOF'\nfrom sys import argv as av\nopen(av[1], 'w').write('x')\nEOF",
        "python3 - lib/a <<'EOF'\nimport sys\nopen(sys.argv[-1], 'w').write('x')\nEOF",
        "python3 - lib/a /tmp/x <<'EOF'\nimport sys\nopen(sys.argv[-2], 'w').write('x')\nEOF",
        "python3 - lib/a <<'EOF'\nimport sys\na = sys.argv\nopen(a[1], 'w').write('x')\nEOF",
        "python3 - lib/a <<'EOF'\nfrom sys import argv\na = argv\np = a[-1]\nopen(p, 'w').write('x')\nEOF",
    ])
    def test_denied(self, cmd, checkout, logger):
        assert _scope(cmd, checkout, logger) is not None

    @pytest.mark.parametrize("cmd", [
        "python3 - /tmp/a <<'EOF'\nfrom sys import argv\nopen(argv[1], 'w').write('x')\nEOF",
        "python3 - lib/a <<'EOF'\nfrom sys import argv\nprint(open(argv[1]).read())\nEOF",
        "python3 - lib/a <<'EOF'\nfrom sys import argv\nopen(argv[2], 'w').write('x')\nEOF",
        # 負索引超出範圍
        "python3 - lib/a <<'EOF'\nimport sys\nopen(sys.argv[-3], 'w').write('x')\nEOF",
        # -k 指向範圍外的引數
        "python3 - lib/a /tmp/x <<'EOF'\nimport sys\nopen(sys.argv[-1], 'w').write('x')\nEOF",
        "python3 - /tmp/a <<'EOF'\nimport sys\na = sys.argv\nopen(a[1], 'w').write('x')\nEOF",
        "python3 - lib/a <<'EOF'\nimport sys\na = sys.argv\nprint(open(a[1]).read())\nEOF",
    ])
    def test_allowed(self, cmd, checkout, logger):
        assert _scope(cmd, checkout, logger) is None

    @pytest.mark.parametrize("idx,args", [("True", "\"$W\" x"), ("-True", "x \"$W\"")])
    def test_bool_index_follows_python_int_semantics(self, idx, args, checkout, logger):
        """True 視為 1、-True 視為 -1（倒數第 1 個）；該位置為受限目錄時 deny。"""
        cmd = "W=lib/sub\npython3 - %s <<'EOF'\nimport sys\nopen(sys.argv[%s], 'w').write('x')\nEOF" % (args, idx)
        assert _scope(cmd, checkout, logger) is not None

    def test_bool_index_outside_scope_allowed(self, checkout, logger):
        cmd = "python3 - x /tmp/a <<'EOF'\nimport sys\nopen(sys.argv[True], 'w').write('x')\nEOF"
        assert _scope(cmd, checkout, logger) is None
