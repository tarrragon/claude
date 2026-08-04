"""
Test: bare-commit-guard-hook（0.2.1-W3-277，源自 0.2.1-W3-276 ANA 裁決）

驗證項目：
1. _contains_git_commit：cwd 隱含 / `-C <path>` / 子 shell 三種形式偵測
2. _has_natural_exemption：三種自然豁免（-- pathspec / --amend / -a｜--all）
3. main() 整合行為：
   - 並行期（dispatch_count > 0）裸 commit → DENY（exit 2），訊息含
     staged 檔案清單與 path-limited 逐字範例
   - 非並行期（dispatch_count == 0）裸 commit → WARN（exit 0 + stderr）
   - 三種自然豁免在並行期仍放行（exit 0，無輸出）
   - 非 Bash 工具 / 非 git commit 命令不受影響
4. 0.2.1-W3-276 回測樣本重放（acceptance #4）：3 筆真實事故案例（並行期裸
   commit）+ 3 筆代表性無害案例（非並行期 PM 統一收尾裸 commit）重放，
   驗證判定方向正確

Source: ticket 0.2.1-W3-277（來源 ANA 0.2.1-W3-276）
"""

import io
import json
import sys
import importlib.util
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent))

_spec = importlib.util.spec_from_file_location(
    "bare_commit_guard_hook",
    HOOKS_DIR / "bare-commit-guard-hook.py",
)
hook_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook_module)

_contains_git_commit = hook_module._contains_git_commit
_has_natural_exemption = hook_module._has_natural_exemption
main = hook_module.main


def _run_hook(
    monkeypatch,
    command: str,
    dispatch_count: int = 0,
    staged_files=None,
    tool_name: str = "Bash",
) -> int:
    """以 monkeypatch 模擬 stdin + 依賴（dispatch 計數 / staged 檔案），執行 main()。"""
    payload = {"tool_name": tool_name, "tool_input": {"command": command}}
    stdin_buffer = io.StringIO(json.dumps(payload))
    monkeypatch.setattr(sys, "stdin", stdin_buffer)
    monkeypatch.setattr(hook_module, "get_project_root", lambda: Path("/fake/project"))
    monkeypatch.setattr(
        hook_module, "_get_active_dispatch_count", lambda root: dispatch_count
    )
    monkeypatch.setattr(
        hook_module, "_get_staged_files", lambda root: staged_files or []
    )
    return main()


# ============================================================================
# _contains_git_commit：偵測形式
# ============================================================================


class TestContainsGitCommit:
    def test_cwd_implicit_form(self):
        assert _contains_git_commit('git commit -m "x"') is True

    def test_dash_c_form(self):
        assert _contains_git_commit('git -C /repo commit -m "x"') is True

    def test_subshell_form(self):
        assert _contains_git_commit('(cd /repo && git commit -m "x")') is True

    def test_git_add_only_not_commit(self):
        assert _contains_git_commit("git add src/foo.py") is False

    def test_git_status_not_commit(self):
        assert _contains_git_commit("git status") is False

    def test_empty_command(self):
        assert _contains_git_commit("") is False

    def test_no_git_word(self):
        assert _contains_git_commit("pytest tests/") is False

    def test_word_boundary_not_substring(self):
        """'legit commit' 中 'git' 前有字元黏著，不應誤判為 git 指令。"""
        assert _contains_git_commit("echo legit commit message") is False


# ============================================================================
# _has_natural_exemption：三種自然豁免
# ============================================================================


class TestHasNaturalExemption:
    def test_pathspec_exemption(self):
        assert _has_natural_exemption('git commit -m "x" -- file1.py file2.py') is True

    def test_amend_exemption(self):
        assert _has_natural_exemption("git commit --amend") is True

    def test_all_long_flag_exemption(self):
        assert _has_natural_exemption('git commit --all -m "x"') is True

    def test_a_short_flag_exemption(self):
        assert _has_natural_exemption('git commit -a -m "x"') is True

    def test_am_combo_flag_exemption(self):
        assert _has_natural_exemption('git commit -am "x"') is True

    def test_no_exemption(self):
        assert _has_natural_exemption('git commit -m "x"') is False

    def test_no_exemption_with_only_message_flag(self):
        assert _has_natural_exemption('git commit -m "fix bug"') is False


# ============================================================================
# main() 整合：並行期 DENY
# ============================================================================


class TestParallelPeriodDeny:
    def test_bare_commit_denied_when_parallel_active(self, monkeypatch, capsys):
        exit_code = _run_hook(
            monkeypatch,
            'git commit -m "fix bug"',
            dispatch_count=2,
            staged_files=["a.py", "b.py"],
        )
        assert exit_code == 2

    def test_deny_message_contains_staged_files(self, monkeypatch, capsys):
        _run_hook(
            monkeypatch,
            'git commit -m "fix bug"',
            dispatch_count=1,
            staged_files=["docs/work-logs/foo.md", "src/bar.py"],
        )
        err = capsys.readouterr().err
        assert "docs/work-logs/foo.md" in err
        assert "src/bar.py" in err

    def test_deny_message_contains_verbatim_example(self, monkeypatch, capsys):
        _run_hook(
            monkeypatch,
            'git commit -m "fix bug"',
            dispatch_count=1,
            staged_files=["a.py"],
        )
        err = capsys.readouterr().err
        assert "git commit -m" in err
        assert " -- a.py" in err

    def test_deny_message_contains_dispatch_count(self, monkeypatch, capsys):
        _run_hook(
            monkeypatch,
            'git commit -m "fix bug"',
            dispatch_count=3,
            staged_files=["a.py"],
        )
        err = capsys.readouterr().err
        assert "3" in err

    def test_deny_message_with_no_staged_files_still_gives_placeholder(
        self, monkeypatch, capsys
    ):
        exit_code = _run_hook(
            monkeypatch, 'git commit -m "fix bug"', dispatch_count=1, staged_files=[]
        )
        assert exit_code == 2
        err = capsys.readouterr().err
        assert "git commit -m" in err


# ============================================================================
# main() 整合：非並行期 WARN
# ============================================================================


class TestNonParallelPeriodWarn:
    def test_bare_commit_warned_when_no_parallel(self, monkeypatch, capsys):
        exit_code = _run_hook(
            monkeypatch, 'git commit -m "chore bookkeeping"', dispatch_count=0
        )
        assert exit_code == 0
        err = capsys.readouterr().err
        assert "提醒" in err

    def test_warn_does_not_block(self, monkeypatch, capsys):
        exit_code = _run_hook(
            monkeypatch, 'git commit -m "x"', dispatch_count=0, staged_files=["x.py"]
        )
        assert exit_code == 0


# ============================================================================
# main() 整合：三種自然豁免在並行期仍放行
# ============================================================================


class TestExemptionsPassThroughEvenWhenParallel:
    def test_pathspec_commit_allowed_even_when_parallel(self, monkeypatch, capsys):
        exit_code = _run_hook(
            monkeypatch,
            'git commit -m "x" -- src/foo.py',
            dispatch_count=5,
        )
        assert exit_code == 0
        assert capsys.readouterr().err == ""

    def test_amend_commit_allowed_even_when_parallel(self, monkeypatch, capsys):
        exit_code = _run_hook(monkeypatch, "git commit --amend", dispatch_count=5)
        assert exit_code == 0
        assert capsys.readouterr().err == ""

    def test_all_flag_commit_allowed_even_when_parallel(self, monkeypatch, capsys):
        exit_code = _run_hook(
            monkeypatch, 'git commit -a -m "x"', dispatch_count=5
        )
        assert exit_code == 0
        assert capsys.readouterr().err == ""


# ============================================================================
# main() 整合：非 Bash / 非 git commit 不受影響
# ============================================================================


class TestUnaffectedCommands:
    def test_non_bash_tool_allowed(self, monkeypatch, capsys):
        exit_code = _run_hook(
            monkeypatch, 'git commit -m "x"', dispatch_count=5, tool_name="Edit"
        )
        assert exit_code == 0

    def test_non_git_command_allowed(self, monkeypatch, capsys):
        exit_code = _run_hook(monkeypatch, "pytest tests/ -q", dispatch_count=5)
        assert exit_code == 0

    def test_git_add_only_allowed(self, monkeypatch, capsys):
        exit_code = _run_hook(monkeypatch, "git add src/foo.py", dispatch_count=5)
        assert exit_code == 0

    def test_empty_command_allowed(self, monkeypatch, capsys):
        exit_code = _run_hook(monkeypatch, "", dispatch_count=5)
        assert exit_code == 0


# ============================================================================
# 0.2.1-W3-276 回測樣本重放（acceptance #4）
#
# 事故案例取自 ANA 0.2.1-W3-276 實際回測辨識出的 5 筆確認汙染 commit 中的
# 3 筆（真實 commit message，代表「並行期裸 commit」情境）；無害案例為
# 代表性重放（ANA 未逐筆列出 27.3% PM 刻意多 ticket 案例的 hash，故以
# 相同語意特徵——PM chore(): 統一收尾、無 pathspec、非並行期——建構代表性
# 樣本，非虛構為特定歷史 hash 的逐字重現）。
# ============================================================================


class TestBacktestReplaySample:
    """3 事故 + 3 代表性無害案例重放，驗證判定方向正確。"""

    @pytest.mark.parametrize(
        "commit_message",
        [
            # b74abeb4：0.2.1-W3-236 fix commit，裸 commit 掃入 W3-079/136/152
            "fix(0.2.1-W3-236): 修正 skill-shadowing-check-hook docstring 優先序方向與過時數量",
            # 82e7c571：0.2.1-W3-228 docs commit，裸 commit 掃入 W3-222/229
            "docs(0.2.1-W3-228): 處置 PM 先寫後建的順序問題，主防線放工具層",
            # ed79c8bc：0.2.1-W3-205 fix commit，裸 commit 掃入 W3-206/207/208
            "fix(0.2.1-W3-205): 依 shell 語意分流處理跳脫引號，消除配對錯位繞過",
        ],
    )
    def test_incident_replay_denied_in_parallel_period(
        self, monkeypatch, capsys, commit_message
    ):
        """3 筆真實事故 commit（並行期裸 commit）重放應判定 DENY。"""
        command = f'git commit -m "{commit_message}"'
        exit_code = _run_hook(
            monkeypatch, command, dispatch_count=2, staged_files=["a.py", "b.py"]
        )
        assert exit_code == 2, f"事故案例應被 DENY：{commit_message}"

    @pytest.mark.parametrize(
        "commit_message",
        [
            "chore(W3): append-log Context Bundle 批次同步",
            "chore(W3): metadata sync post-completion 批次收尾",
            "chore(W3): ticket 狀態批次更新（PM 統一收尾）",
        ],
    )
    def test_harmless_replay_warned_in_non_parallel_period(
        self, monkeypatch, capsys, commit_message
    ):
        """3 筆代表性無害案例（PM 非並行期統一收尾裸 commit）重放應僅 WARN。"""
        command = f'git commit -m "{commit_message}"'
        exit_code = _run_hook(monkeypatch, command, dispatch_count=0)
        assert exit_code == 0, f"無害案例不應被 DENY：{commit_message}"
