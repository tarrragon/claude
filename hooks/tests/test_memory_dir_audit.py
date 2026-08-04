"""
Test: memory-dir-audit-hook（Ticket: 0.2.1-W3-092, 0.2.1-W3-194, 0.2.1-W3-195）

驗證 memory-dir-audit-hook.py 的 SessionStart + Stop 事件式稽核行為：

1. SessionStart / Stop 皆呼叫同一份核心邏輯 `_run_audit()`：candidate 目錄
   快照與 marker 上次記錄的快照相比，非空且變化才告警，並無條件更新 marker
2. marker 不含 session 維度，結構為 {目錄路徑: 檔名清單}
3. 同一份未變化的內容不重複告警（節流核心行為）
4. 跨事件共用同一份 marker 是刻意設計，即使是不同的 session 觸發，變化只要
   已被記錄過就不會再被告知（ticket 明載的接受代價）
5. 零候選交 `_warn_if_comparison_key_may_be_stale()` 判斷
6. 非 SessionStart/Stop 事件（例如 PostToolUse）一律跳過，無 stderr、exit 0
7. main() 對非預期輸入的容錯：空 stdin、malformed JSON 皆 fail-open

`is_memory_dir_nonempty()` 已於 Phase 4 第二輪移除（正式路徑零呼叫者，
`_snapshot_candidates()` 才是快照邏輯的唯一入口，效能短路直接對其驗證）。

測試策略：main() 端對端行為以 monkeypatch 替換 hook.resolve_candidate_memory_dirs
回傳測試用的 tempfile 目錄，並以 `MEMORY_DIR_AUDIT_MARKER_FILE` 環境變數
覆寫 marker 路徑到 tempfile，不觸碰開發者本機真實 marker 檔與真實 home
目錄下的 memory 位置。`resolve_candidate_memory_dirs()` 本體不替身掉函式
本身，改以造假 home 的封閉測試驗證（monkeypatch 協作者 `get_project_root`
與模組層級 `_HOME`，函式本體真跑）——`.claude/` 會 sync 到其他專案，寫死
本專案識別符或依賴真實 `~/.claude/projects/` 狀態的斷言會產生與程式碼
正確性無關的紅燈，見 `TestResolveCandidateMemoryDirsScopeNarrowing`。

參考: 0.2.1-W3-194（三輪修復史完整記錄於該 ticket Solution）、
0.2.1-W3-195（matcher 由 PostToolUse:Bash 改為 SessionStart+Stop；Phase 4
第二輪拿掉 marker 的 session 維度、移除死碼 is_memory_dir_nonempty，
Solution 記錄完整設計取捨）
"""

import importlib.util
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent))


def _load_hook_module():
    """以 importlib 載入連字號命名的 hook 模組（每次呼叫回傳全新模組實例，
    避免測試間 monkeypatch 互相污染）。"""
    hook_file = HOOKS_DIR / "memory-dir-audit-hook.py"
    spec = importlib.util.spec_from_file_location("memory_dir_audit_hook", hook_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_main_with_input(hook_module, input_data):
    """以 stdin 注入 JSON 並呼叫 hook.main()，回傳 (exit_code, stderr_text)。"""
    stdin_buf = io.StringIO(json.dumps(input_data))
    old_stdin = sys.stdin
    old_stderr = sys.stderr
    sys.stdin = stdin_buf
    sys.stderr = io.StringIO()
    try:
        exit_code = hook_module.main()
        stderr_text = sys.stderr.getvalue()
        return exit_code, stderr_text
    finally:
        sys.stdin = old_stdin
        sys.stderr = old_stderr


def _run_main_with_raw_stdin(hook_module, raw_text):
    stdin_buf = io.StringIO(raw_text)
    old_stdin = sys.stdin
    sys.stdin = stdin_buf
    try:
        return hook_module.main()
    finally:
        sys.stdin = old_stdin


class _MemoryDirAuditMainTestCase(unittest.TestCase):
    """main() 端對端測試共用 setUp/tearDown：隔離 tempfile 目錄與 marker
    路徑，避免觸碰開發者本機真實 home / marker 狀態。"""

    def setUp(self):
        self._tmp_root = tempfile.mkdtemp()
        self._marker_file = Path(self._tmp_root) / "marker.json"
        self._old_marker_env = os.environ.get("MEMORY_DIR_AUDIT_MARKER_FILE")
        os.environ["MEMORY_DIR_AUDIT_MARKER_FILE"] = str(self._marker_file)

    def tearDown(self):
        if self._old_marker_env is None:
            os.environ.pop("MEMORY_DIR_AUDIT_MARKER_FILE", None)
        else:
            os.environ["MEMORY_DIR_AUDIT_MARKER_FILE"] = self._old_marker_env
        shutil.rmtree(self._tmp_root, ignore_errors=True)

    def _session_start_input(self):
        return {"hook_event_name": "SessionStart", "session_id": "session-a"}

    def _stop_input(self):
        return {"hook_event_name": "Stop", "session_id": "session-a"}


class TestSnapshotCandidates(unittest.TestCase):
    """`_snapshot_candidates()` 是快照邏輯的唯一入口，效能短路直接對其
    驗證（取代已移除的 `is_memory_dir_nonempty()` 測試）。"""

    def test_nonexistent_dir_skips_listdir_call(self):
        """目錄不存在時 os.listdir 完全不應被呼叫，快照記為空清單。"""
        hook = _load_hook_module()
        tmp_root = tempfile.mkdtemp()
        try:
            nonexistent = str(Path(tmp_root) / "definitely-not-here" / "memory")
            listdir_calls = []
            original_listdir = hook.os.listdir
            hook.os.listdir = lambda path: listdir_calls.append(path) or original_listdir(path)
            try:
                snapshot = hook._snapshot_candidates([nonexistent])
            finally:
                hook.os.listdir = original_listdir

            self.assertEqual(listdir_calls, [], "os.listdir 被呼叫，效能短路未生效")
            self.assertEqual(snapshot, {nonexistent: []})
        finally:
            shutil.rmtree(tmp_root)

    def test_existing_empty_dir_snapshot_is_empty_list(self):
        hook = _load_hook_module()
        tmp_root = tempfile.mkdtemp()
        try:
            memory_dir = Path(tmp_root) / "memory"
            memory_dir.mkdir()
            snapshot = hook._snapshot_candidates([str(memory_dir)])
            self.assertEqual(snapshot, {str(memory_dir): []})
        finally:
            shutil.rmtree(tmp_root)

    def test_existing_nonempty_dir_snapshot_lists_sorted_filenames(self):
        hook = _load_hook_module()
        tmp_root = tempfile.mkdtemp()
        try:
            memory_dir = Path(tmp_root) / "memory"
            memory_dir.mkdir()
            (memory_dir / "b.md").write_text("x")
            (memory_dir / "a.md").write_text("y")
            snapshot = hook._snapshot_candidates([str(memory_dir)])
            self.assertEqual(snapshot, {str(memory_dir): ["a.md", "b.md"]})
        finally:
            shutil.rmtree(tmp_root)


class TestAuditBaseline(_MemoryDirAuditMainTestCase):
    """SessionStart：對零 marker 記錄的候選目錄建立首次快照，非空即提醒。"""

    def test_nonempty_baseline_warns_once_and_writes_marker(self):
        hook = _load_hook_module()
        memory_dir = Path(self._tmp_root) / "memory"
        memory_dir.mkdir()
        (memory_dir / "leaked-fact.md").write_text("x")
        hook.resolve_candidate_memory_dirs = lambda: [str(memory_dir)]

        exit_code, stderr_text = _run_main_with_input(hook, self._session_start_input())

        self.assertEqual(exit_code, 0)
        self.assertIn("[MemoryDirAudit]", stderr_text)
        self.assertIn("換個地方記錄", stderr_text)

        marker_state = json.loads(self._marker_file.read_text(encoding="utf-8"))
        self.assertEqual(
            marker_state,
            {str(memory_dir): ["leaked-fact.md"]},
            "marker 結構須為 {目錄路徑: 檔名清單}，不含 session 維度",
        )

    def test_empty_baseline_no_warning(self):
        hook = _load_hook_module()
        memory_dir = Path(self._tmp_root) / "memory"
        memory_dir.mkdir()
        hook.resolve_candidate_memory_dirs = lambda: [str(memory_dir)]

        exit_code, stderr_text = _run_main_with_input(hook, self._session_start_input())

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr_text, "")

    def test_nonexistent_candidate_no_warning(self):
        hook = _load_hook_module()
        hook.resolve_candidate_memory_dirs = lambda: [
            str(Path(self._tmp_root) / "never-created")
        ]

        exit_code, stderr_text = _run_main_with_input(hook, self._session_start_input())

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr_text, "")


class TestEventDrivenThrottle(_MemoryDirAuditMainTestCase):
    """事件式節流核心行為——未變化不重複告警，變化才發聲；SessionStart
    與 Stop 呼叫同一份邏輯，行為對稱。"""

    def test_unchanged_content_since_baseline_no_warning(self):
        """SessionStart 已對既有殘留提醒過一次；後續 Stop 若內容未變化，
        不得重複告警（節流核心行為，直接對應 acceptance 第二項）。"""
        hook = _load_hook_module()
        memory_dir = Path(self._tmp_root) / "memory"
        memory_dir.mkdir()
        (memory_dir / "leaked-fact.md").write_text("x")
        hook.resolve_candidate_memory_dirs = lambda: [str(memory_dir)]

        start_exit, start_stderr = _run_main_with_input(hook, self._session_start_input())
        self.assertEqual(start_exit, 0)
        self.assertIn("[MemoryDirAudit]", start_stderr)

        stop_exit, stop_stderr = _run_main_with_input(hook, self._stop_input())
        self.assertEqual(stop_exit, 0)
        self.assertEqual(
            stop_stderr,
            "",
            "內容相對 SessionStart 基準線未變化，Stop 不應重複告警",
        )

    def test_new_file_added_since_baseline_warns(self):
        """SessionStart 基準線乾淨，Stop 前新增檔案 -> 本次 Stop 應告警
        （本 session 新增內容，稽核真正要抓的情境）。"""
        hook = _load_hook_module()
        memory_dir = Path(self._tmp_root) / "memory"
        memory_dir.mkdir()
        hook.resolve_candidate_memory_dirs = lambda: [str(memory_dir)]

        start_exit, start_stderr = _run_main_with_input(hook, self._session_start_input())
        self.assertEqual(start_exit, 0)
        self.assertEqual(start_stderr, "")

        (memory_dir / "new-during-session.md").write_text("x")

        stop_exit, stop_stderr = _run_main_with_input(hook, self._stop_input())
        self.assertEqual(stop_exit, 0)
        self.assertIn("[MemoryDirAudit]", stop_stderr)

    def test_second_stop_after_warning_does_not_repeat(self):
        """Stop 告警後 marker 已更新為當前快照，若內容此後不再變化，
        下一次 Stop 不應再次告警。"""
        hook = _load_hook_module()
        memory_dir = Path(self._tmp_root) / "memory"
        memory_dir.mkdir()
        hook.resolve_candidate_memory_dirs = lambda: [str(memory_dir)]

        _run_main_with_input(hook, self._session_start_input())
        (memory_dir / "new-during-session.md").write_text("x")

        first_stop_exit, first_stop_stderr = _run_main_with_input(hook, self._stop_input())
        self.assertIn("[MemoryDirAudit]", first_stop_stderr)

        second_stop_exit, second_stop_stderr = _run_main_with_input(hook, self._stop_input())
        self.assertEqual(second_stop_exit, 0)
        self.assertEqual(
            second_stop_stderr,
            "",
            "同一次新增之後內容未再變化，第二次 Stop 不應重複告警",
        )

    def test_stop_without_prior_marker_treats_nonempty_as_changed(self):
        """無任何 marker 記錄時（例如 marker 檔案不存在），對非空目錄採
        保守預設：視為變化並告警，不會靜默略過殘留內容。"""
        hook = _load_hook_module()
        memory_dir = Path(self._tmp_root) / "memory"
        memory_dir.mkdir()
        (memory_dir / "leaked-fact.md").write_text("x")
        hook.resolve_candidate_memory_dirs = lambda: [str(memory_dir)]

        exit_code, stderr_text = _run_main_with_input(hook, self._stop_input())

        self.assertEqual(exit_code, 0)
        self.assertIn("[MemoryDirAudit]", stderr_text)

    def test_stop_with_empty_dir_no_warning(self):
        hook = _load_hook_module()
        memory_dir = Path(self._tmp_root) / "memory"
        memory_dir.mkdir()
        hook.resolve_candidate_memory_dirs = lambda: [str(memory_dir)]

        _run_main_with_input(hook, self._session_start_input())
        exit_code, stderr_text = _run_main_with_input(hook, self._stop_input())

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr_text, "")

    def test_cross_event_marker_sharing_is_accepted_cost(self):
        """marker 不分 session/event：一次由 SessionStart 記錄過的變化，
        即使後續是名義上「不同 session」的 Stop 呼叫，也不會再被告知——
        這是 ticket 明載接受的代價，非 bug。"""
        hook = _load_hook_module()
        memory_dir = Path(self._tmp_root) / "memory"
        memory_dir.mkdir()
        (memory_dir / "leaked-fact.md").write_text("x")
        hook.resolve_candidate_memory_dirs = lambda: [str(memory_dir)]

        # 第一次 SessionStart（代表 session A）已提醒並寫入 marker。
        _run_main_with_input(hook, self._session_start_input())

        # 名義上屬於另一個 session 的 Stop 呼叫，內容未變 -> 不應再被告知
        # （hook 本身不追蹤事件是哪個 session 觸發的）。
        other_session_stop_input = {"hook_event_name": "Stop", "session_id": "session-b"}
        exit_code, stderr_text = _run_main_with_input(hook, other_session_stop_input)

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr_text, "")


class TestNonAuditEventsSkipped(_MemoryDirAuditMainTestCase):
    """非 SessionStart/Stop 事件一律跳過，不觸發稽核。"""

    def test_post_tool_use_event_skipped_even_if_memory_dir_nonempty(self):
        hook = _load_hook_module()
        memory_dir = Path(self._tmp_root) / "memory"
        memory_dir.mkdir()
        (memory_dir / "leaked-fact.md").write_text("x")
        hook.resolve_candidate_memory_dirs = lambda: [str(memory_dir)]

        input_data = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "echo hi"},
        }
        exit_code, stderr_text = _run_main_with_input(hook, input_data)

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr_text, "")

    def test_empty_stdin_allowed(self):
        hook = _load_hook_module()
        self.assertEqual(_run_main_with_raw_stdin(hook, ""), 0)

    def test_malformed_json_stdin_fails_open(self):
        hook = _load_hook_module()
        self.assertEqual(_run_main_with_raw_stdin(hook, "{not valid json"), 0)


def _full_path_slug(path: str) -> str:
    """把完整路徑轉成「每個非英數字元換成連字號」的字串，模擬 CC slug
    編碼的一種等效形式。用於測試建構「與 project_root 完整路徑正規化後
    相等」的候選目錄名，不受 tempfile 隨機根目錄影響——正規化只保留
    英數字元，故任何非英數分隔符（不論是 `-` 還是別的字元）替換後的
    結果，正規化後都會收斂到同一字串。"""
    return re.sub(r"[^0-9a-zA-Z]", "-", path)


class TestResolveCandidateMemoryDirsBranchCorrectness(unittest.TestCase):
    """驗證兩條分支各自的比對鍵語意（legacy 用 basename、比對鍵取自
    `get_project_root()` 而非環境變數，理由見 `resolve_candidate_memory_dirs()`
    docstring）。不替身 `resolve_candidate_memory_dirs` 本身，只 monkeypatch
    其協作者 `get_project_root` 與模組層級 `_HOME`，resolve 邏輯本體維持
    真實執行。"""

    def setUp(self):
        self._tmp_root = tempfile.mkdtemp()
        self._fake_home = Path(self._tmp_root) / "fake-home"
        self._fake_home.mkdir()

    def tearDown(self):
        shutil.rmtree(self._tmp_root, ignore_errors=True)

    def test_legacy_branch_matches_by_project_basename_not_full_path(self):
        """legacy 分支改用 basename 比對後可命中；沿用完整路徑鍵則恆不可達
        （回歸驗證：故意用完整路徑鍵重算一次，證明兩者確實不相等）。"""
        hook = _load_hook_module()
        project_root = self._fake_home / "workspace" / "demo-project"
        project_root.mkdir(parents=True)

        legacy_dir = self._fake_home / "auto-memory" / "demo-project"
        legacy_dir.mkdir(parents=True)
        (legacy_dir / "leaked-fact.md").write_text("x")

        hook._HOME = str(self._fake_home)
        hook.get_project_root = lambda: project_root

        candidates = hook.resolve_candidate_memory_dirs()

        self.assertIn(
            str(legacy_dir),
            candidates,
            "legacy 分支未命中：basename 比對鍵未生效",
        )

        # 回歸防護：確認「完整路徑」鍵確實無法命中同一組目錄，證明兩把鍵
        # 語意不同，不是巧合相等。
        full_path_key = hook._normalize_for_comparison(
            os.path.normpath(str(project_root))
        )
        legacy_name_key = hook._normalize_for_comparison(legacy_dir.name)
        self.assertNotEqual(
            full_path_key,
            legacy_name_key,
            "測試前提不成立：完整路徑鍵與 legacy 專案名鍵意外相等，"
            "無法證明分支切換的必要性",
        )

    def test_uses_get_project_root_not_raw_env_var(self):
        """比對鍵須來自 get_project_root()，即使 CLAUDE_PROJECT_DIR 指向
        別的路徑也不受影響——模擬 worktree session 中兩者不一致的情境。"""
        hook = _load_hook_module()
        distinct_project_root = (
            self._fake_home / "worktree-copy" / "demo-project-agent-x"
        )
        distinct_project_root.mkdir(parents=True)

        slug = _full_path_slug(os.path.normpath(str(distinct_project_root)))
        matching_dir = (
            self._fake_home / ".claude" / "projects" / slug / "memory"
        )
        matching_dir.mkdir(parents=True)
        (matching_dir / "leaked-fact.md").write_text("x")

        hook._HOME = str(self._fake_home)
        hook.get_project_root = lambda: distinct_project_root

        old_env = os.environ.get("CLAUDE_PROJECT_DIR")
        os.environ["CLAUDE_PROJECT_DIR"] = "/totally/different/main-repo/path"
        try:
            candidates = hook.resolve_candidate_memory_dirs()
        finally:
            if old_env is None:
                os.environ.pop("CLAUDE_PROJECT_DIR", None)
            else:
                os.environ["CLAUDE_PROJECT_DIR"] = old_env

        self.assertIn(
            str(matching_dir),
            candidates,
            "resolve_candidate_memory_dirs() 未依 get_project_root() 命中，"
            "可能仍受 CLAUDE_PROJECT_DIR 或 os.getcwd() 影響",
        )


class TestResolveCandidateMemoryDirsScopeNarrowing(unittest.TestCase):
    """驗證範圍限縮：封閉世界內同時放本專案與他專案各一個候選，
    `resolve_candidate_memory_dirs()` 本體以真實邏輯執行、不被替身，斷言
    結果只含本專案者。與 `TestResolveCandidateMemoryDirsBranchCorrectness`
    同一手法（monkeypatch 協作者 `get_project_root` 與模組層級 `_HOME`，
    隔離出造假 home），不依賴、不查詢任何真實 home 目錄狀態（`.claude/`
    會 sync 到其他專案，斷言不可含專案識別符或依賴真實環境殘留狀態，見
    `reference-stability-rules` 規則 8）。"""

    def setUp(self):
        self._tmp_root = tempfile.mkdtemp()
        self._fake_home = Path(self._tmp_root) / "fake-home"
        self._fake_home.mkdir()

    def tearDown(self):
        shutil.rmtree(self._tmp_root, ignore_errors=True)

    def test_matches_own_project_excludes_other_project(self):
        """封閉世界正向 + 負向對照：本專案候選命中，他專案候選不命中，
        即使他專案候選非空。"""
        hook = _load_hook_module()
        own_project_root = self._fake_home / "workspace" / "this-project"
        own_project_root.mkdir(parents=True)

        own_slug = _full_path_slug(os.path.normpath(str(own_project_root)))
        own_memory_dir = (
            self._fake_home / ".claude" / "projects" / own_slug / "memory"
        )
        own_memory_dir.mkdir(parents=True)
        (own_memory_dir / "leaked-fact.md").write_text("x")

        # 他專案：目錄名與本專案完全不同，內容非空（現成對照組，模擬
        # 「其他專案既有殘留內容」的情境，不依賴真實環境是否真的有這種
        # 殘留）。
        other_memory_dir = (
            self._fake_home / ".claude" / "projects" /
            "-Users-someone-else-project-other-app" / "memory"
        )
        other_memory_dir.mkdir(parents=True)
        (other_memory_dir / "unrelated-fact.md").write_text("y")

        hook._HOME = str(self._fake_home)
        hook.get_project_root = lambda: own_project_root

        candidates = hook.resolve_candidate_memory_dirs()

        self.assertIn(
            str(own_memory_dir),
            candidates,
            "未命中本專案自己的候選目錄",
        )
        self.assertNotIn(
            str(other_memory_dir),
            candidates,
            "範圍限縮失效：命中了他專案的候選目錄",
        )

    def test_zero_candidates_when_only_other_projects_exist(self):
        """封閉世界：projects 下只有他專案條目、無本專案條目時，
        resolve_candidate_memory_dirs() 回傳空清單（而非誤命中他專案）。"""
        hook = _load_hook_module()
        own_project_root = self._fake_home / "workspace" / "this-project"
        own_project_root.mkdir(parents=True)

        other_memory_dir = (
            self._fake_home / ".claude" / "projects" /
            "-Users-someone-else-project-other-app" / "memory"
        )
        other_memory_dir.mkdir(parents=True)
        (other_memory_dir / "unrelated-fact.md").write_text("y")

        hook._HOME = str(self._fake_home)
        hook.get_project_root = lambda: own_project_root

        candidates = hook.resolve_candidate_memory_dirs()

        self.assertEqual(candidates, [])


class TestWarnIfComparisonKeyMayBeStale(unittest.TestCase):
    """零候選與「memory 乾淨」的可觀測性區分。

    `resolve_candidate_memory_dirs()` 回傳空清單是合法值，也可能是比對鍵
    過期，兩者在回傳值上無法區分。`_warn_if_comparison_key_may_be_stale()`
    在「projects 目錄確實有其他條目、但本專案零候選」時記錄 warning 日誌
    （僅寫檔案，不外顯 stderr），是兩者唯一的區分管道。本組驗證告警只在
    該條件成立時發出，避免 projects 目錄本身為空時誤報。
    """

    def test_warns_when_other_entries_exist_but_zero_candidates(self):
        hook = _load_hook_module()
        tmp_root = tempfile.mkdtemp()
        try:
            fake_home = Path(tmp_root) / "fake-home"
            projects_root = fake_home / ".claude" / "projects"
            other_entry = projects_root / "-Users-someone-else-project-other-app"
            other_entry.mkdir(parents=True)

            hook._HOME = str(fake_home)

            logged = []

            class _FakeLogger:
                def warning(self, msg):
                    logged.append(msg)

            hook._warn_if_comparison_key_may_be_stale(_FakeLogger())

            self.assertEqual(len(logged), 1)
            self.assertIn("零候選", logged[0])
        finally:
            shutil.rmtree(tmp_root, ignore_errors=True)

    def test_no_warning_when_projects_dir_has_no_entries_at_all(self):
        """全新環境（projects/ 尚無任何條目，如首次執行或 CI）不應誤報。"""
        hook = _load_hook_module()
        tmp_root = tempfile.mkdtemp()
        try:
            fake_home = Path(tmp_root) / "fake-home"
            (fake_home / ".claude" / "projects").mkdir(parents=True)

            hook._HOME = str(fake_home)

            logged = []

            class _FakeLogger:
                def warning(self, msg):
                    logged.append(msg)

            hook._warn_if_comparison_key_may_be_stale(_FakeLogger())

            self.assertEqual(logged, [])
        finally:
            shutil.rmtree(tmp_root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
