#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""comment-qa-hook 以真實形狀 PostToolUse payload 執行時須進入檢查流程（3.4.0-W1-083）。

修正前：main() 以 tool_response.get("success", False) 判定工具是否成功。
Write／Edit 的真實 tool_response 沒有 success 欄位（Write 為 type、filePath、
content、structuredPatch；Edit 為 filePath、oldString、newString 等），判定恆為
失敗，hook 每次都寫「執行失敗，跳過檢查」後 return 0，檢查從未執行。

修正後：PostToolUse 只在工具成功後觸發（失敗走 PostToolUseFailure），
觸發本身即代表成功，不再讀 success。

隔離：以 conftest 的 hook_project_env 執行，日誌與報告寫進 tmp，不寫真實 hook-logs。
"""

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK = (
    REPO_ROOT / ".claude" / "skills" / "dart-comment-traceability"
    / "hooks" / "comment-qa-hook.py"
)

SKIP_LINE = "執行失敗，跳過檢查"
PROCESS_LINE = "處理檔案"
REPORT_TITLE = "註解品質檢查報告"

DART_SOURCE = (
    "class Foo {\n"
    "  void handleTap() {\n"
    "    print('x');\n"
    "  }\n"
    "}\n"
)


def _run(payload: dict, env: dict):
    full_env = os.environ.copy()
    full_env.pop("CLAUDE_EFFORT", None)
    full_env.update(env)
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=full_env,
        timeout=60,
    )
    return result.returncode, result.stdout, result.stderr


def _log_text(project_root: Path) -> str:
    log_dir = project_root / ".claude" / "hook-logs" / "comment-qa-hook"
    return "".join(p.read_text(encoding="utf-8") for p in sorted(log_dir.glob("*.log")))


def _dart_file(project_root: Path) -> Path:
    # 預設配置的 priority_dirs 只處理 lib/domains/、lib/presentation/、lib/use_cases/
    target = project_root / "lib" / "presentation" / "foo.dart"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(DART_SOURCE, encoding="utf-8")
    return target


def _write_payload(file_path: Path) -> dict:
    """Write 工具的真實回應形狀：無 success 欄位。"""
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": str(file_path), "content": DART_SOURCE},
        "tool_response": {
            "type": "create",
            "filePath": str(file_path),
            "content": DART_SOURCE,
            "structuredPatch": [],
        },
    }


def _edit_payload(file_path: Path) -> dict:
    """Edit 工具的真實回應形狀：無 success 欄位。"""
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(file_path),
            "old_string": "print('x');",
            "new_string": "print('y');",
        },
        "tool_response": {
            "filePath": str(file_path),
            "oldString": "print('x');",
            "newString": "print('y');",
            "originalFile": DART_SOURCE,
            "structuredPatch": [],
            "userModified": False,
            "replaceAll": False,
        },
    }


class TestRealPayloadEntersCheck:
    def test_write_payload_runs_check(self, hook_project_env):
        project_root, env = hook_project_env
        target = _dart_file(project_root)

        rc, out, _ = _run(_write_payload(target), env)

        log = _log_text(project_root)
        assert rc == 0
        assert SKIP_LINE not in log
        assert PROCESS_LINE in log
        assert REPORT_TITLE in out

    def test_edit_payload_runs_check(self, hook_project_env):
        project_root, env = hook_project_env
        target = _dart_file(project_root)

        rc, out, _ = _run(_edit_payload(target), env)

        log = _log_text(project_root)
        assert rc == 0
        assert SKIP_LINE not in log
        assert PROCESS_LINE in log
        assert REPORT_TITLE in out

    def test_non_source_file_still_skipped_by_scope(self, hook_project_env):
        """對照：範圍外檔案照舊由 should_process_file 排除，不產生報告。"""
        project_root, env = hook_project_env
        target = project_root / "notes.txt"
        target.write_text("x\n", encoding="utf-8")

        rc, out, _ = _run(_write_payload(target), env)

        log = _log_text(project_root)
        assert rc == 0
        assert "不需要處理" in log
        assert REPORT_TITLE not in out
