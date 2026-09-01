"""
Test: bare-commit-guard-hook（0.2.1-W3-277，源自 0.2.1-W3-276 ANA 裁決；
0.2.1-W3-725 修正 pathspec/--only/-o 不再無條件豁免；0.2.1-W3-702 /
0.2.1-W3-381 修正 payload（heredoc 本體 / 引號字串）內文被誤判為真實
命令與旗標；0.2.1-W3-708 命令解析改採 `.claude/lib/git_command_parse.py`
的 argv 結構解析，取代自維護的字串前處理；0.2.1-W3-1176 修正單筆空
files 派發記錄使不相交放行路徑對所有人失效）

驗證項目：
1. _contains_git_word：便宜前置判斷（含獨立 'git' 字樣即進入完整解析）
2. _has_amend_or_all_exemption：--amend / -a｜--all 兩種無條件豁免
   （改吃 token 清單，非原始命令字串）
3. _is_index_discarding_form：-- pathspec / --only / -o 三種寫法偵測
   （改吃 token 清單，非原始命令字串）
4. _staged_scope_is_safe_for_bare_commit：staged 範圍是否落在單一活躍
   派發宣告的 files 範圍內
5. main() 整合行為：
   - 並行期（dispatch_count > 0）裸 commit，staged 範圍不落在任一派發
     宣告內 → DENY（exit 2），訊息含 staged 檔案清單與核對／清理步驟
   - 並行期裸 commit，staged 範圍落在單一派發宣告內 → 放行（exit 0）
   - 非並行期（dispatch_count == 0）裸 commit → WARN（exit 0 + stderr）
   - --amend / -a｜--all 在並行期仍放行（exit 0，無輸出）
   - pathspec / --only / -o 在並行期一律 DENY（不再是無條件豁免）
   - pathspec / --only / -o 在非並行期 WARN（不阻擋，但不再靜默）
   - 非 Bash 工具 / 非 git commit 命令不受影響
   - 非 git 命令的 heredoc 本體 / 引號參數提及 git commit 字面不再誤判
   - 真實 git commit 的訊息內文（heredoc 帶入）提及 --only/-o 字面不再
     誤判為 index-discarding form
   - 命令含 git 字樣但無法安全 tokenize（未閉合引號）：並行期 DENY、
     非並行期 WARN（明確失敗語意，見共用 lib「失敗語意」段）
6. 0.2.1-W3-276 回測樣本重放（acceptance #4）：3 筆真實事故案例（並行期裸
   commit，staged 範圍無派發宣告可比對）+ 3 筆代表性無害案例（非並行期
   PM 統一收尾裸 commit）重放，驗證判定方向正確
7. 空 files 派發記錄（0.2.1-W3-1176）：單筆或多筆派發 files 為空時不再
   使整條不相交放行路徑失效（計算聯集時排除空宣告）；全數派發皆空時
   聯集為空集合仍視為安全；存在空宣告時經 logger 發出 warning（可觀測性）

Source: ticket 0.2.1-W3-277（來源 ANA 0.2.1-W3-276）、0.2.1-W3-725、
0.2.1-W3-702、0.2.1-W3-381、0.2.1-W3-708、0.2.1-W3-1176
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

_contains_git_word = hook_module.contains_git_word
_has_amend_or_all_exemption = hook_module._has_amend_or_all_exemption
_is_index_discarding_form = hook_module._is_index_discarding_form
_staged_scope_is_safe_for_bare_commit = hook_module._staged_scope_is_safe_for_bare_commit
main = hook_module.main


def _dispatch(ticket_id: str, files) -> dict:
    """建構最小化的活躍派發記錄（供 `_get_active_dispatches_safe` 回傳）。"""
    return {"ticket_id": ticket_id, "files": list(files)}


def _run_hook(
    monkeypatch,
    command: str,
    dispatches=None,
    staged_files=None,
    tool_name: str = "Bash",
) -> int:
    """以 monkeypatch 模擬 stdin + 依賴（活躍派發清單 / staged 檔案），執行 main()。"""
    payload = {"tool_name": tool_name, "tool_input": {"command": command}}
    stdin_buffer = io.StringIO(json.dumps(payload))
    monkeypatch.setattr(sys, "stdin", stdin_buffer)
    monkeypatch.setattr(hook_module, "get_project_root", lambda: Path("/fake/project"))
    monkeypatch.setattr(
        hook_module, "_get_active_dispatches_safe", lambda root: dispatches or []
    )
    monkeypatch.setattr(
        hook_module, "_get_staged_files", lambda root: staged_files or []
    )
    return main()


# ============================================================================
# _contains_git_word：便宜前置判斷
# ============================================================================


class TestContainsGitWord:
    def test_cwd_implicit_form(self):
        assert _contains_git_word('git commit -m "x"') is True

    def test_dash_c_form(self):
        assert _contains_git_word('git -C /repo commit -m "x"') is True

    def test_subshell_form(self):
        assert _contains_git_word('(cd /repo && git commit -m "x")') is True

    def test_git_add_also_matches(self):
        """本函式只是便宜前置判斷（含 'git' 字樣即可），子命令篩選交由
        `find_git_invocations` 負責，故 `git add` 亦回傳 True。"""
        assert _contains_git_word("git add src/foo.py") is True

    def test_empty_command(self):
        assert _contains_git_word("") is False

    def test_no_git_word(self):
        assert _contains_git_word("pytest tests/") is False

    def test_word_boundary_not_substring(self):
        """'legit commit' 中 'git' 前有字元黏著，不應誤判為 git 指令。"""
        assert _contains_git_word("echo legit commit message") is False


# ============================================================================
# _has_amend_or_all_exemption：兩種無條件豁免（吃 token 清單）
# ============================================================================


class TestHasAmendOrAllExemption:
    def test_amend_exemption(self):
        assert _has_amend_or_all_exemption(["--amend"]) is True

    def test_all_long_flag_exemption(self):
        assert _has_amend_or_all_exemption(["--all", "-m", "x"]) is True

    def test_a_short_flag_exemption(self):
        assert _has_amend_or_all_exemption(["-a", "-m", "x"]) is True

    def test_am_combo_flag_exemption(self):
        assert _has_amend_or_all_exemption(["-am", "x"]) is True

    def test_no_exemption(self):
        assert _has_amend_or_all_exemption(["-m", "x"]) is False

    def test_pathspec_is_not_exempted_here(self):
        """pathspec 不再屬於本函式的豁免範圍（改由 `_is_index_discarding_form` 判斷）。"""
        assert (
            _has_amend_or_all_exemption(["-m", "x", "--", "file1.py", "file2.py"])
            is False
        )

    def test_message_content_token_not_misdetected(self):
        """訊息內容經 shlex tokenize 後為單一完整 token，不含獨立 `-a` 子
        token，不應誤判為豁免（token 化天生解決舊版子字串比對的誤判）。"""
        assert _has_amend_or_all_exemption(["-m", "描述 -a 這個字面"]) is False


# ============================================================================
# _is_index_discarding_form：pathspec / --only / -o 三種寫法（吃 token 清單）
# ============================================================================


class TestIsIndexDiscardingForm:
    def test_pathspec_detected(self):
        assert _is_index_discarding_form(["-m", "x", "--", "file1.py", "file2.py"]) is True

    def test_only_long_flag_detected(self):
        assert _is_index_discarding_form(["--only", "-m", "x"]) is True

    def test_o_short_flag_detected(self):
        assert _is_index_discarding_form(["-o", "-m", "x"]) is True

    def test_bare_commit_not_detected(self):
        assert _is_index_discarding_form(["-m", "x"]) is False

    def test_amend_not_detected(self):
        assert _is_index_discarding_form(["--amend"]) is False

    def test_message_content_token_not_misdetected(self):
        """訊息內容（單一完整 token）提及 --only/-o 字面時不應誤判。"""
        assert (
            _is_index_discarding_form(["-m", "描述本次修正提及 --only 與 -o 兩個 flag"])
            is False
        )


# ============================================================================
# _staged_scope_is_safe_for_bare_commit：staged 範圍安全性驗證
# ============================================================================


class TestStagedScopeIsSafeForBareCommit:
    def test_empty_staged_is_safe(self):
        assert _staged_scope_is_safe_for_bare_commit([], []) is True

    def test_subset_of_single_dispatch_is_safe(self):
        dispatches = [_dispatch("T-1", ["a.py", "b.py", "c.py"])]
        assert _staged_scope_is_safe_for_bare_commit(["a.py", "b.py"], dispatches) is True

    def test_exact_match_is_safe(self):
        dispatches = [_dispatch("T-1", ["a.py"])]
        assert _staged_scope_is_safe_for_bare_commit(["a.py"], dispatches) is True

    def test_disjoint_from_single_dispatch_is_safe(self):
        """staged 與唯一活躍派發宣告完全不相交（如 PM 提交 ticket metadata）
        時，經由不相交路徑放行（0.2.1-W3-738）。"""
        dispatches = [_dispatch("T-1", ["a.py"])]
        assert _staged_scope_is_safe_for_bare_commit(["z.py"], dispatches) is True

    def test_mixed_across_two_dispatches_is_unsafe(self):
        """staged 內容橫跨兩個派發各自宣告的檔案，非任一單一派發的子集，
        也非與所有派發不相交（與聯集相交）。"""
        dispatches = [_dispatch("T-1", ["a.py"]), _dispatch("T-2", ["b.py"])]
        assert _staged_scope_is_safe_for_bare_commit(["a.py", "b.py"], dispatches) is False

    def test_no_dispatches_with_staged_files_is_unsafe(self):
        assert _staged_scope_is_safe_for_bare_commit(["a.py"], []) is False

    def test_dispatch_with_empty_files_declares_no_territory(self):
        """派發 files 欄位為空（ticket_id 無法解析）時不構成任何領地，計算
        不相交聯集時排除，不再使整條不相交路徑失效（修正舊版判定：舊版把
        單筆空宣告等同於「必須阻擋」，但空宣告本身與 staged 內容無關）。"""
        dispatches = [_dispatch("T-1", [])]
        assert _staged_scope_is_safe_for_bare_commit(["a.py"], dispatches) is True

    def test_all_dispatches_with_empty_files_is_safe(self):
        """所有活躍派發的 files 皆為空時，已宣告範圍聯集為空集合，staged
        內容對空集合恆為不相交，視為安全（同一原則的自然延伸）。"""
        dispatches = [_dispatch("T-1", []), _dispatch("T-2", [])]
        assert _staged_scope_is_safe_for_bare_commit(["a.py"], dispatches) is True

    def test_empty_files_dispatch_warns_via_logger(self):
        """存在空 files 派發記錄時，若傳入 logger，應發出 warning（可觀測
        性；記錄本身不因此從 dispatch-active.json 移除，僅範圍判定排除）。"""

        class _RecordingLogger:
            def __init__(self):
                self.warnings = []

            def warning(self, msg, *args):
                self.warnings.append(msg % args if args else msg)

        logger = _RecordingLogger()
        dispatches = [_dispatch("T-1", ["a.py"]), _dispatch("T-2", [])]
        assert (
            _staged_scope_is_safe_for_bare_commit(["z.py"], dispatches, logger=logger)
            is True
        )
        assert len(logger.warnings) == 1
        assert "1" in logger.warnings[0]

    def test_partial_overlap_with_single_dispatch_is_unsafe(self):
        """staged 部分與派發宣告重疊、部分不在其中：非子集，也非不相交。"""
        dispatches = [_dispatch("T-1", ["a.py"])]
        assert _staged_scope_is_safe_for_bare_commit(["a.py", "z.py"], dispatches) is False

    def test_disjoint_from_multiple_dispatches_is_safe(self):
        """staged 與多個活躍派發宣告的聯集皆不相交時放行。"""
        dispatches = [_dispatch("T-1", ["a.py"]), _dispatch("T-2", ["b.py"])]
        assert _staged_scope_is_safe_for_bare_commit(["z.py"], dispatches) is True

    def test_one_dispatch_with_empty_files_does_not_block_disjoint_path(self):
        """多個派發中有一個 files 為空時，不相交路徑僅用有宣告範圍的派發
        驗證（排除空宣告），staged 與有效宣告仍不相交則放行（修正舊版：
        單筆空宣告不應使整條不相交路徑對其他有效宣告的比對全面失效——
        對應真實事故：code-review 型派發 ticket_id 無法解析、files 為
        空，導致與其他有效宣告完全不相交的正常提交被誤擋）。"""
        dispatches = [_dispatch("T-1", ["a.py"]), _dispatch("T-2", [])]
        assert _staged_scope_is_safe_for_bare_commit(["z.py"], dispatches) is True


# ============================================================================
# main() 整合：並行期裸 commit
# ============================================================================


class TestParallelPeriodBareCommit:
    def test_denied_when_staged_scope_unsafe(self, monkeypatch, capsys):
        """staged 部分與派發宣告重疊（a.py）、部分不在其中（b.py）：非子集
        也非不相交，維持 DENY（0.2.1-W3-738 後不能改用完全不相交的檔案，
        那會改走放行路徑）。"""
        exit_code = _run_hook(
            monkeypatch,
            'git commit -m "fix bug"',
            dispatches=[_dispatch("T-1", ["a.py"])],
            staged_files=["a.py", "b.py"],
        )
        assert exit_code == 2

    def test_deny_message_contains_staged_files(self, monkeypatch, capsys):
        """staged 部分與派發宣告重疊（docs/work-logs/foo.md）、部分不在其中
        （src/bar.py）：非子集也非不相交，維持 DENY（0.2.1-W3-738 後不能用
        與宣告完全不相交的檔案，那會改走放行路徑）。"""
        _run_hook(
            monkeypatch,
            'git commit -m "fix bug"',
            dispatches=[_dispatch("T-1", ["docs/work-logs/foo.md"])],
            staged_files=["docs/work-logs/foo.md", "src/bar.py"],
        )
        err = capsys.readouterr().err
        assert "docs/work-logs/foo.md" in err
        assert "src/bar.py" in err

    def test_deny_message_no_longer_recommends_pathspec(self, monkeypatch, capsys):
        """DENY 訊息不得以 `-- <pathspec>` 作為推薦寫法（0.2.1-W3-725）。
        staged 部分與派發宣告重疊（a.py）、部分不在其中（z.py），維持 DENY。"""
        _run_hook(
            monkeypatch,
            'git commit -m "fix bug"',
            dispatches=[_dispatch("T-1", ["a.py"])],
            staged_files=["a.py", "z.py"],
        )
        err = capsys.readouterr().err
        recommend_lines = [
            line
            for line in err.splitlines()
            if "git commit -m" in line and "你的訊息" in line
        ]
        assert recommend_lines, err
        assert all(" -- " not in line for line in recommend_lines), recommend_lines
        # 訊息須含核對與清理步驟
        assert "git diff --cached --name-only" in err
        assert "git restore --staged" in err

    def test_deny_message_contains_dispatch_count(self, monkeypatch, capsys):
        """staged 橫跨兩派發宣告（x.py, y.py），既非子集也非與聯集不相交
        （因命中 z.py 以外的兩檔），維持 DENY（0.2.1-W3-738 後仍需覆蓋
        混合情境，不能改用與所有派發不相交的檔案）。"""
        _run_hook(
            monkeypatch,
            'git commit -m "fix bug"',
            dispatches=[
                _dispatch("T-1", ["x.py"]),
                _dispatch("T-2", ["y.py"]),
                _dispatch("T-3", ["z.py"]),
            ],
            staged_files=["x.py", "y.py"],
        )
        err = capsys.readouterr().err
        assert "3" in err

    def test_deny_message_with_no_staged_files_still_gives_placeholder(
        self, monkeypatch, capsys
    ):
        exit_code = _run_hook(
            monkeypatch,
            'git commit -m "fix bug"',
            dispatches=[_dispatch("T-1", ["only-a.py"])],
            staged_files=[],
        )
        # staged_files 為空時 _staged_scope_is_safe_for_bare_commit 回 True，
        # 應放行而非 DENY（見 TestStagedScopeIsSafeForBareCommit.test_empty_staged_is_safe）
        assert exit_code == 0

    def test_allowed_when_staged_scope_within_single_dispatch(self, monkeypatch, capsys):
        """staged 範圍完整落在單一派發宣告內時，裸 commit 放行（新增放行邏輯，0.2.1-W3-725）。"""
        exit_code = _run_hook(
            monkeypatch,
            'git commit -m "fix bug"',
            dispatches=[_dispatch("T-1", ["a.py", "b.py", "c.py"])],
            staged_files=["a.py", "b.py"],
        )
        assert exit_code == 0
        assert capsys.readouterr().err == ""

    def test_denied_when_staged_scope_mixes_two_dispatches(self, monkeypatch, capsys):
        exit_code = _run_hook(
            monkeypatch,
            'git commit -m "fix bug"',
            dispatches=[_dispatch("T-1", ["a.py"]), _dispatch("T-2", ["b.py"])],
            staged_files=["a.py", "b.py"],
        )
        assert exit_code == 2


# ============================================================================
# main() 整合：非並行期裸 commit WARN
# ============================================================================


class TestNonParallelPeriodBareCommitWarn:
    def test_bare_commit_warned_when_no_parallel(self, monkeypatch, capsys):
        exit_code = _run_hook(
            monkeypatch, 'git commit -m "chore bookkeeping"', dispatches=[]
        )
        assert exit_code == 0
        err = capsys.readouterr().err
        assert "提醒" in err

    def test_warn_does_not_block(self, monkeypatch, capsys):
        exit_code = _run_hook(
            monkeypatch, 'git commit -m "x"', dispatches=[], staged_files=["x.py"]
        )
        assert exit_code == 0

    def test_warn_no_longer_recommends_pathspec(self, monkeypatch, capsys):
        _run_hook(monkeypatch, 'git commit -m "x"', dispatches=[])
        err = capsys.readouterr().err
        assert "git diff --cached --name-only" in err


# ============================================================================
# main() 整合：--amend / -a｜--all 在並行期仍放行
# ============================================================================


class TestAmendAndAllExemptionsPassThroughEvenWhenParallel:
    def test_amend_commit_allowed_even_when_parallel(self, monkeypatch, capsys):
        exit_code = _run_hook(
            monkeypatch,
            "git commit --amend",
            dispatches=[_dispatch("T-1", ["a.py"]) for _ in range(5)],
        )
        assert exit_code == 0
        assert capsys.readouterr().err == ""

    def test_all_flag_commit_allowed_even_when_parallel(self, monkeypatch, capsys):
        exit_code = _run_hook(
            monkeypatch,
            'git commit -a -m "x"',
            dispatches=[_dispatch("T-1", ["a.py"]) for _ in range(5)],
        )
        assert exit_code == 0
        assert capsys.readouterr().err == ""


# ============================================================================
# main() 整合：pathspec / --only / -o 不再是無條件豁免（0.2.1-W3-725）
# ============================================================================


class TestIndexDiscardingFormNoLongerBypassed:
    def test_pathspec_commit_denied_when_parallel(self, monkeypatch, capsys):
        exit_code = _run_hook(
            monkeypatch,
            'git commit -m "x" -- src/foo.py',
            dispatches=[_dispatch("T-1", ["src/foo.py"])],
        )
        assert exit_code == 2
        err = capsys.readouterr().err
        assert "pathspec" in err or "index" in err

    def test_only_flag_commit_denied_when_parallel(self, monkeypatch, capsys):
        exit_code = _run_hook(
            monkeypatch,
            'git commit --only -m "x"',
            dispatches=[_dispatch("T-1", ["src/foo.py"])],
        )
        assert exit_code == 2

    def test_o_flag_commit_denied_when_parallel(self, monkeypatch, capsys):
        exit_code = _run_hook(
            monkeypatch,
            'git commit -o -m "x"',
            dispatches=[_dispatch("T-1", ["src/foo.py"])],
        )
        assert exit_code == 2

    def test_pathspec_commit_warned_not_denied_when_not_parallel(self, monkeypatch, capsys):
        """非並行期不阻擋，但不再靜默（原始行為是無條件放行、無任何輸出）。"""
        exit_code = _run_hook(
            monkeypatch, 'git commit -m "x" -- src/foo.py', dispatches=[]
        )
        assert exit_code == 0
        err = capsys.readouterr().err
        assert "提醒" in err


# ============================================================================
# main() 整合：非 Bash / 非 git commit 不受影響
# ============================================================================


class TestUnaffectedCommands:
    def test_non_bash_tool_allowed(self, monkeypatch, capsys):
        exit_code = _run_hook(
            monkeypatch,
            'git commit -m "x"',
            dispatches=[_dispatch("T-1", ["a.py"]) for _ in range(5)],
            tool_name="Edit",
        )
        assert exit_code == 0

    def test_non_git_command_allowed(self, monkeypatch, capsys):
        exit_code = _run_hook(
            monkeypatch, "pytest tests/ -q", dispatches=[_dispatch("T-1", ["a.py"])]
        )
        assert exit_code == 0

    def test_git_add_only_allowed(self, monkeypatch, capsys):
        exit_code = _run_hook(
            monkeypatch, "git add src/foo.py", dispatches=[_dispatch("T-1", ["a.py"])]
        )
        assert exit_code == 0

    def test_empty_command_allowed(self, monkeypatch, capsys):
        exit_code = _run_hook(
            monkeypatch, "", dispatches=[_dispatch("T-1", ["a.py"])]
        )
        assert exit_code == 0


# ============================================================================
# main() 整合：無法安全 tokenize（未閉合引號）的明確失敗語意（0.2.1-W3-708）
# ============================================================================


class TestUnparsableCommandExplicitFailureSemantics:
    def test_denied_when_parallel_and_unparsable(self, monkeypatch, capsys):
        exit_code = _run_hook(
            monkeypatch,
            'git commit -m "unterminated',
            dispatches=[_dispatch("T-1", ["a.py"])],
        )
        assert exit_code == 2
        err = capsys.readouterr().err
        assert "無法安全解析" in err

    def test_warned_when_not_parallel_and_unparsable(self, monkeypatch, capsys):
        exit_code = _run_hook(
            monkeypatch, 'git commit -m "unterminated', dispatches=[]
        )
        assert exit_code == 0
        err = capsys.readouterr().err
        assert "無法安全解析" in err

    def test_non_git_unparsable_command_allowed(self, monkeypatch, capsys):
        """不含 'git' 字樣的無法解析命令在便宜前置判斷即短路，不進入解析。"""
        exit_code = _run_hook(
            monkeypatch,
            'echo "unterminated',
            dispatches=[_dispatch("T-1", ["a.py"])],
        )
        assert exit_code == 0
        assert capsys.readouterr().err == ""


# ============================================================================
# main() 整合：payload 內文誤判修正重現（0.2.1-W3-702 / 0.2.1-W3-381 /
# 0.2.1-W3-725 自身觸發現場）
# ============================================================================


class TestPayloadFalsePositivesFixed:
    def test_heredoc_content_mentioning_git_commit_in_non_git_command_allowed(
        self, monkeypatch, capsys
    ):
        """0.2.1-W3-702 重現：append-log 的 heredoc 內文描述本 hook 攔截對象
        （提及『git commit』字面），該命令本身不執行任何 git 操作，並行期間
        不應被 DENY。"""
        command = (
            'ticket track append-log W3-691 --section "Context Bundle" '
            '"$(cat <<\'EOF\'\n'
            "此 hook 會偵測裸 git commit 並在並行期間阻擋\n"
            "EOF\n"
            ')")'
        )
        exit_code = _run_hook(
            monkeypatch, command, dispatches=[_dispatch("T-1", ["a.py"]) for _ in range(3)]
        )
        assert exit_code == 0
        assert capsys.readouterr().err == ""

    def test_quoted_parameter_mentioning_git_commit_in_non_git_command_allowed(
        self, monkeypatch, capsys
    ):
        """0.2.1-W3-381 重現：非 heredoc 的引號參數內文含『git』『commit』
        相鄰字樣（版控政策說明文字），該命令不執行任何 git 操作。"""
        command = 'some-cli --why "版控政策說明：不要用 git commit 繞過審查"'
        exit_code = _run_hook(
            monkeypatch, command, dispatches=[_dispatch("T-1", ["a.py"]) for _ in range(2)]
        )
        assert exit_code == 0
        assert capsys.readouterr().err == ""

    def test_real_commit_with_heredoc_message_mentioning_only_flag_not_denied(
        self, monkeypatch, capsys
    ):
        """0.2.1-W3-725 自身觸發現場重現：真實 git commit，訊息透過 heredoc
        帶入且內文提及 --only/-o 字面（描述本次修正內容），修正前會被誤判
        為 index-discarding form；修正後應正常走裸 commit 判斷路徑。"""
        command = (
            'git commit -m "$(cat <<\'EOF\'\n'
            "fix: --only 與 -o 不再無條件豁免\n"
            "EOF\n"
            ')")'
        )
        exit_code = _run_hook(
            monkeypatch,
            command,
            dispatches=[_dispatch("T-1", ["a.py", "b.py"])],
            staged_files=["a.py"],
        )
        # 應走裸 commit 分支（staged 範圍落在單一派發宣告內），非
        # index-discarding form 的 DENY 分支
        assert exit_code == 0
        assert capsys.readouterr().err == ""

    def test_real_pathspec_commit_still_denied_when_message_is_clean(
        self, monkeypatch, capsys
    ):
        """回歸防護：真實 pathspec commit（旗標在引號外）修正後仍應被偵測。"""
        exit_code = _run_hook(
            monkeypatch,
            'git commit -m "fix bug" -- src/foo.py',
            dispatches=[_dispatch("T-1", ["src/foo.py"])],
        )
        assert exit_code == 2


# ============================================================================
# 0.2.1-W3-276 回測樣本重放（acceptance #4）
#
# 事故案例取自 ANA 0.2.1-W3-276 實際回測辨識出的 5 筆確認汙染 commit 中的
# 3 筆（真實 commit message，代表「並行期裸 commit，staged 範圍橫跨派發
# 宣告與非宣告內容」情境）。回測樣本本身未附派發 files 宣告；0.2.1-W3-738
# 新增不相交放行路徑後，「staged 與任一派發宣告皆無交集」的資料會改判
# 放行（不再代表無從驗證安全性），故 fixture 改以「staged 含自身宣告
# 檔案（a.py）與非宣告檔案（b.py）的混合」建模——對應歷史事故的真實
# 形態（某票的裸 commit 掃入其他票的檔案），使其仍落在 DENY 分支。
# 無害案例為代表性重放（ANA 未逐筆列出 27.3% PM 刻意多 ticket 案例的
# hash，故以相同語意特徵——PM chore(): 統一收尾、非並行期——建構代表性
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
        """3 筆真實事故 commit（並行期裸 commit，staged 範圍橫跨派發宣告
        與非宣告內容，混合情境）重放應判定 DENY。staged 需與至少一個派發
        宣告重疊（否則命中 0.2.1-W3-738 新增的不相交放行路徑，不再代表
        「無法確認安全」的歷史事故情境）。"""
        command = f'git commit -m "{commit_message}"'
        exit_code = _run_hook(
            monkeypatch,
            command,
            dispatches=[
                _dispatch("T-1", ["a.py"]),
                _dispatch("T-2", ["unrelated-2.py"]),
            ],
            staged_files=["a.py", "b.py"],
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
        exit_code = _run_hook(monkeypatch, command, dispatches=[])
        assert exit_code == 0, f"無害案例不應被 DENY：{commit_message}"
