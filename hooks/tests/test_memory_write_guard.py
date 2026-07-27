"""
Test: memory-write-guard-hook（Ticket: 0.2.1-W3-084）

驗證 memory-write-guard-hook.py 的 PreToolUse deny 行為：

1. 命中：Write/Edit/MultiEdit 寫入 memory 目錄（現行格式 + legacy auto-memory
   格式，皆錨定至使用者 home 目錄）一律 deny（exit 2），且 deny 訊息含判別
   問句、三個目的地、明示可改地方記錄
2. 路徑正規化：`./` `../` 收斂、大小寫不敏感（macOS APFS 慣例）、legacy 形式
   僅在 home 目錄下才命中（非 home 下同名目錄不誤判，Phase 4 審查 A1-A3）
3. 豁免：非 memory 路徑一律 allow（exit 0）；非 Write/Edit/MultiEdit 工具
   （如 Bash）不受本 hook 管轄，一律 allow——matcher 刻意不含 Bash，
   避免擋住 0.2.1-W3-085 的 memory 目錄清空作業（此為已知、docstring 已
   誠實記載的豁免範圍，非測試盲區）
4. 無節流：同檔案連續兩次寫入皆 deny（既有 hook 30 分鐘節流已移除）
5. main() 對非預期輸入的容錯：malformed JSON、tool_input 缺 file_path 鍵
   皆 fail-open（allow），與三層 fail-open 設計一致

注意：測試路徑一律以 `os.path.expanduser("~")` 為基底建構字串，不建立實際
檔案——is_memory_path 只做字串層級比對，不觸及檔案系統，故無需真實存在的
目錄即可驗證比對邏輯，也不會污染真實 home 目錄。

來源：0.2.1-W3-082（決策）-> 0.2.1-W3-084（本票，Phase 4 審查修正）
"""

import importlib.util
import io
import json
import os
import sys
import unittest
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent))

_HOME = os.path.expanduser("~")


def _home_path(*parts: str) -> str:
    """組出以真實 home 目錄為基底的測試路徑字串（不建立實際檔案）。"""
    return os.path.join(_HOME, *parts)


def _load_hook_module():
    """以 importlib 載入連字號命名的 hook 模組。"""
    hook_file = HOOKS_DIR / "memory-write-guard-hook.py"
    spec = importlib.util.spec_from_file_location("memory_write_guard_hook", hook_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_main_with_input(hook_module, input_data):
    """以 stdin 注入 JSON 並呼叫 hook.main()，回傳 exit code。"""
    stdin_buf = io.StringIO(json.dumps(input_data))
    old_stdin = sys.stdin
    sys.stdin = stdin_buf
    try:
        return hook_module.main()
    finally:
        sys.stdin = old_stdin


def _run_main_with_raw_stdin(hook_module, raw_text):
    """以 stdin 注入任意文字（含 malformed JSON）並呼叫 hook.main()。"""
    stdin_buf = io.StringIO(raw_text)
    old_stdin = sys.stdin
    sys.stdin = stdin_buf
    try:
        return hook_module.main()
    finally:
        sys.stdin = old_stdin


class TestIsMemoryPath(unittest.TestCase):
    """路徑判別邏輯：命中條件為目錄結構而非檔名（AC-1）。"""

    def test_current_format_hits_regardless_of_filename(self):
        hook = _load_hook_module()
        for filename in ["MEMORY.md", "worktree-dispatch-needs-origin-sync.md", "any-name.md"]:
            path = _home_path(".claude", "projects", "-Users-tester-project-demo", "memory", filename)
            self.assertTrue(hook.is_memory_path(path), f"{filename} 應命中（不比對檔名）")

    def test_legacy_auto_memory_format_hits_when_anchored_to_home(self):
        hook = _load_hook_module()
        path = _home_path("auto-memory", "demo-project", "feedback_legacy.md")
        self.assertTrue(hook.is_memory_path(path), "home 下的 legacy auto-memory 路徑應命中")

    def test_legacy_auto_memory_format_outside_home_does_not_hit(self):
        """Phase 4 審查 A3：legacy 形式須錨定 home，非 home 下同名目錄不應誤判。"""
        hook = _load_hook_module()
        self.assertFalse(hook.is_memory_path("/tmp/anything/auto-memory/x/y.md"))

    def test_project_local_auto_memory_dir_does_not_hit(self):
        """專案內若剛好有 auto-memory/foo/ 目錄，不應被誤判為 legacy memory 位置。"""
        hook = _load_hook_module()
        self.assertFalse(hook.is_memory_path("/some/repo/auto-memory/foo/z.md"))

    def test_non_memory_project_path_does_not_hit(self):
        """豁免案例：一般專案檔案路徑不命中（不誤傷）。"""
        hook = _load_hook_module()
        path = "/Users/tester/project/flutter_balance/docs/README.md"
        self.assertFalse(hook.is_memory_path(path))

    def test_coincidental_memory_named_dir_outside_claude_projects_does_not_hit(self):
        """僅目錄名含 memory 但不在 .claude/projects/<x>/memory/ 結構下不應誤判。"""
        hook = _load_hook_module()
        path = "/Users/tester/project/flutter_balance/docs/memory/notes.md"
        self.assertFalse(hook.is_memory_path(path))

    def test_empty_path_does_not_hit(self):
        hook = _load_hook_module()
        self.assertFalse(hook.is_memory_path(""))

    def test_dot_segment_normalized_before_match(self):
        """Phase 4 審查 A1：`/./` 須先正規化才比對，避免以此繞過。"""
        hook = _load_hook_module()
        path = _home_path(".claude", "projects", "demo", ".", "memory", "a.md")
        self.assertTrue(hook.is_memory_path(path))

    def test_dotdot_traversal_normalized_before_match(self):
        """Phase 4 審查 A1：`../` 須先收斂才比對，避免以此繞過。"""
        hook = _load_hook_module()
        path = _home_path(".claude", "projects", "demo", "sub", "..", "memory", "a.md")
        self.assertTrue(hook.is_memory_path(path))

    def test_uppercase_memory_segment_hits(self):
        """Phase 4 審查 A2：大小寫變體須命中（macOS APFS 預設大小寫不敏感）。"""
        hook = _load_hook_module()
        path = _home_path(".claude", "projects", "demo", "MEMORY", "a.md")
        self.assertTrue(hook.is_memory_path(path))

    def test_mixed_case_memory_segment_hits(self):
        hook = _load_hook_module()
        path = _home_path(".claude", "projects", "demo", "Memory", "a.md")
        self.assertTrue(hook.is_memory_path(path))


class TestMainDenyBehavior(unittest.TestCase):
    """main() 端對端行為：exit code + deny 訊息內容（AC-1/AC-3）。"""

    def test_write_to_memory_dir_denied(self):
        """命中案例：Write 到 memory 目錄 -> exit 2。"""
        hook = _load_hook_module()
        input_data = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": _home_path(".claude", "projects", "-Users-tester-demo", "memory", "new-fact.md")
            },
        }
        self.assertEqual(_run_main_with_input(hook, input_data), 2)

    def test_edit_to_memory_dir_denied(self):
        hook = _load_hook_module()
        input_data = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": _home_path(".claude", "projects", "-Users-tester-demo", "memory", "MEMORY.md")
            },
        }
        self.assertEqual(_run_main_with_input(hook, input_data), 2)

    def test_multiedit_to_memory_dir_denied(self):
        hook = _load_hook_module()
        input_data = {
            "tool_name": "MultiEdit",
            "tool_input": {
                "file_path": _home_path(".claude", "projects", "-Users-tester-demo", "memory", "MEMORY.md")
            },
        }
        self.assertEqual(_run_main_with_input(hook, input_data), 2)

    def test_deny_message_contains_required_elements(self):
        """AC-3：deny 訊息含判別問句、三個目的地、明示可改地方記錄、後果、權威來源指標。"""
        hook = _load_hook_module()
        reason = hook.DENY_REASON
        self.assertTrue(
            reason.startswith("[MemoryWriteGuard] 這不是不能記錄，是換個地方記錄"),
            "首句須為改道明示，而非純禁令（Phase 4 審查項 7）",
        )
        self.assertIn("另一個專案的 session 讀到這段，能用嗎", reason, "判別問句")
        self.assertIn("框架相關", reason)
        self.assertIn("專案相關", reason)
        self.assertIn("兩者皆非", reason)
        self.assertIn("/error-pattern add", reason, "框架相關內錯誤學習類 opinionated default（審查項 8）")
        self.assertIn("docs/", reason)
        self.assertIn("CLAUDE.md", reason)
        self.assertIn("不記錄就永久遺失", reason, "Consequence：不改道的後果（審查項 6）")
        self.assertIn("在別的專案消失", reason, "Why：實質理由而非純訴諸票號（審查項 5）")
        self.assertIn("pm-quality-baseline.md 規則 7", reason, "指向權威來源而非逐字複製（審查項 4）")
        # 不應逐字複製三分流表格（審查項 4：複本會漂移，改為指標）
        self.assertNotIn("| 學習成果性質 | 判別 | 目的地 |", reason)

    def test_non_memory_edit_allowed(self):
        """豁免案例：一般檔案 Edit -> exit 0。"""
        hook = _load_hook_module()
        input_data = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "/Users/tester/project/flutter_balance/docs/README.md"},
        }
        self.assertEqual(_run_main_with_input(hook, input_data), 0)

    def test_bash_tool_not_governed_by_this_hook(self):
        """matcher 刻意不含 Bash：即使 command 涉及 memory 目錄仍放行（0.2.1-W3-085 清空作業前提；
        此豁免範圍的獨立封閉方案另案追蹤）。"""
        hook = _load_hook_module()
        input_data = {
            "tool_name": "Bash",
            "tool_input": {
                "command": "rm " + _home_path(".claude", "projects", "-Users-tester-demo", "memory", "x.md")
            },
        }
        self.assertEqual(_run_main_with_input(hook, input_data), 0)

    def test_no_throttle_repeated_writes_both_denied(self):
        """既有 hook 的 30 分鐘節流已移除：同檔案連續兩次寫入皆 deny。"""
        hook = _load_hook_module()
        input_data = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": _home_path(".claude", "projects", "-Users-tester-demo", "memory", "repeat.md")
            },
        }
        first = _run_main_with_input(hook, input_data)
        second = _run_main_with_input(hook, input_data)
        self.assertEqual(first, 2)
        self.assertEqual(second, 2, "不應節流放行第二次寫入")

    def test_empty_stdin_allowed(self):
        hook = _load_hook_module()
        self.assertEqual(_run_main_with_raw_stdin(hook, ""), 0)

    def test_malformed_json_stdin_fails_open(self):
        """三層 fail-open 之一：stdin 非合法 JSON -> allow（docstring 已明文記錄）。"""
        hook = _load_hook_module()
        self.assertEqual(_run_main_with_raw_stdin(hook, "{not valid json"), 0)

    def test_tool_input_missing_file_path_key_allowed(self):
        """tool_input 存在但缺 file_path 鍵 -> 視為空路徑，allow。"""
        hook = _load_hook_module()
        input_data = {"tool_name": "Write", "tool_input": {"content": "x"}}
        self.assertEqual(_run_main_with_input(hook, input_data), 0)

    def test_tool_input_missing_entirely_allowed(self):
        """tool_input 整個鍵不存在（非僅值為 None）-> allow。"""
        hook = _load_hook_module()
        input_data = {"tool_name": "Edit"}
        self.assertEqual(_run_main_with_input(hook, input_data), 0)


if __name__ == "__main__":
    unittest.main()
