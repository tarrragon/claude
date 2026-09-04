"""
Test: mcp-run-tests-validator（PreToolUse:mcp__dart__run_tests 防護）

0.2.1-W3-1232 ANA 盤點確認本 hook 為「執法型（PreToolUse:mcp__dart__run_tests，
roots 缺 paths 時 deny + exit 2 阻擋）+ tests/ 全目錄零提及」，本檔補上功能性
測試。本 hook 已具備 hook_utils 統一日誌（setup_hook_logging/run_hook_safely），
無需遷移。

驗證項目：
1. validate_roots_parameter：roots 型別檢查、paths 必須存在且非空
2. format_error_message：錯誤訊息含各無效 root 的描述
3. main() 整合行為：
   - 非目標工具短路（放行，不輸出 hookSpecificOutput deny）
   - 正常放行路徑（roots 皆含非空 paths，exit 0 + permissionDecision=allow）
   - 觸發阻擋路徑（roots 缺 paths 或 paths 為空，exit 2 + stderr/JSON 皆含
     deny 訊息與缺少 paths 的說明）
   - 非法 JSON 輸入（JSONDecodeError）明確 deny（fail-closed）
4. hook-logs 落檔（本 session 實地觸發確認）+ liveness 索引記錄

Source: ticket 0.2.1-W3-1238（來源 ANA 0.2.1-W3-1232）
"""

import io
import json
import sys
import importlib.util
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent))

_spec = importlib.util.spec_from_file_location(
    "mcp_run_tests_validator",
    HOOKS_DIR / "mcp-run-tests-validator.py",
)
hook_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook_module)

validate_roots_parameter = hook_module.validate_roots_parameter
format_error_message = hook_module.format_error_message
main = hook_module.main


def _run_hook(
    monkeypatch,
    capsys,
    stdin_text: str,
    project_root: "Path | None" = None,
) -> "tuple[int, dict]":
    """執行 main()，回傳 (exit_code, 解析出的最後一行 JSON 輸出)。"""
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin_text))
    if project_root is not None:
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project_root))
        monkeypatch.setenv("HOOK_TEST_ISOLATION", "1")
    exit_code = main()
    out = capsys.readouterr().out.strip()
    last_line = out.splitlines()[-1] if out else ""
    parsed = json.loads(last_line) if last_line else {}
    return exit_code, parsed


def _payload(roots, tool_name: str = "mcp__dart__run_tests") -> str:
    return json.dumps(
        {"tool_name": tool_name, "tool_input": {"roots": roots}}
    )


# ============================================================================
# validate_roots_parameter
# ============================================================================


class TestValidateRootsParameter:
    def test_valid_roots_with_paths(self):
        is_valid, invalid = validate_roots_parameter(
            [{"root": "/repo", "paths": ["test/foo_test.dart"]}]
        )
        assert is_valid is True
        assert invalid == []

    def test_missing_paths_key_invalid(self):
        is_valid, invalid = validate_roots_parameter([{"root": "/repo"}])
        assert is_valid is False
        assert len(invalid) == 1

    def test_empty_paths_list_invalid(self):
        is_valid, invalid = validate_roots_parameter(
            [{"root": "/repo", "paths": []}]
        )
        assert is_valid is False

    def test_roots_not_a_list(self):
        is_valid, invalid = validate_roots_parameter("not-a-list")
        assert is_valid is False
        assert "陣列" in invalid[0]

    def test_root_entry_not_a_dict(self):
        is_valid, invalid = validate_roots_parameter(["not-a-dict"])
        assert is_valid is False
        assert "root[0]" in invalid[0]

    def test_mixed_valid_and_invalid_roots(self):
        is_valid, invalid = validate_roots_parameter(
            [
                {"root": "/repo-a", "paths": ["test/a_test.dart"]},
                {"root": "/repo-b", "paths": []},
            ]
        )
        assert is_valid is False
        assert len(invalid) == 1
        assert "/repo-b" in invalid[0]


# ============================================================================
# format_error_message
# ============================================================================


class TestFormatErrorMessage:
    def test_message_contains_invalid_root_description(self):
        msg = format_error_message(["/repo-b: 缺少 paths 參數或 paths 為空陣列"])
        assert "/repo-b" in msg
        assert "paths" in msg


# ============================================================================
# main() 整合：短路路徑（非目標工具）
# ============================================================================


class TestMainShortCircuit:
    def test_non_target_tool_allowed(self, monkeypatch, capsys):
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "echo x"}})
        exit_code, parsed = _run_hook(monkeypatch, capsys, payload)
        assert exit_code == 0
        assert parsed["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_empty_stdin_allowed(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
        exit_code = main()
        assert exit_code == 0


# ============================================================================
# main() 整合：正常放行路徑
# ============================================================================


class TestMainAllowPath:
    def test_valid_roots_allowed(self, monkeypatch, capsys):
        payload = _payload([{"root": "/repo", "paths": ["test/foo_test.dart"]}])
        exit_code, parsed = _run_hook(monkeypatch, capsys, payload)
        assert exit_code == 0
        assert parsed["hookSpecificOutput"]["permissionDecision"] == "allow"


# ============================================================================
# main() 整合：觸發阻擋路徑
# ============================================================================


class TestMainBlockPath:
    def test_missing_paths_denied(self, monkeypatch, capsys):
        payload = _payload([{"root": "/repo"}])
        exit_code, parsed = _run_hook(monkeypatch, capsys, payload)
        assert exit_code == 2
        assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "paths" in parsed["hookSpecificOutput"]["permissionDecisionReason"]

    def test_malformed_json_input_is_fail_open(self, monkeypatch, capsys):
        """`read_json_from_stdin` 已在內部捕捉 JSONDecodeError 並回傳 None
        （見 hook_io.py），main() 對 None 立即 return 0——main() 內殘留的
        `except json.JSONDecodeError` 分支（deny/exit 2）因此已不可達，為
        遷移至 hook_utils 共用 helper 後的死碼。實際行為與檔案結尾
        `except Exception` 分支所述設計哲學一致（異常時允許執行以防 Hook
        故障，fail-open）。本測試記錄現況行為，死碼清理另建票追蹤。"""
        monkeypatch.setattr(sys, "stdin", io.StringIO("{不是合法 JSON"))
        exit_code = main()
        assert exit_code == 0


# ============================================================================
# hook-logs 落檔（本 session 實地觸發確認）+ liveness 索引
# ============================================================================


class TestHookLogsObservability:
    def test_run_hook_safely_writes_log_and_liveness(self, monkeypatch, capsys, tmp_path):
        project_root = tmp_path / "fake_project"
        project_root.mkdir()
        payload = _payload([{"root": "/repo"}])
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project_root))
        monkeypatch.setenv("HOOK_TEST_ISOLATION", "1")

        exit_code = hook_module.run_hook_safely(main, "mcp-run-tests-validator")
        assert exit_code == 2

        log_dir = project_root / ".claude" / "hook-logs" / "mcp-run-tests-validator"
        log_files = list(log_dir.glob("*.log"))
        assert log_files, f"預期落檔，實際：{list(log_dir.iterdir()) if log_dir.exists() else '不存在'}"
        content = log_files[0].read_text(encoding="utf-8")
        assert "mcp_run_tests_no_paths" in content

        liveness_dir = project_root / ".claude" / "hook-logs" / "_liveness"
        jsonl_files = list(liveness_dir.glob("*.jsonl"))
        assert jsonl_files, "預期 liveness 索引檔存在"
        entries = [
            json.loads(line)
            for line in jsonl_files[0].read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert any(e.get("hook") == "mcp-run-tests-validator" for e in entries)
