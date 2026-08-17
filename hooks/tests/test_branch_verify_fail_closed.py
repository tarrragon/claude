"""
Test: branch-verify-hook fail_closed 語意切換（0.2.1-W3-508）

驗證項目：
1. 註冊點以 fail_closed=True 呼叫 run_hook_safely（保護分支類守衛，fail-open
   代價為變更落錯分支的搬移成本）
2. main() 拋未預期例外時，fail_closed=True 回傳 2；對照組 fail_closed=False
   回傳 1（既有 wrapper 語意不變）
3. 豁免清單判定（is_exempt_path_on_protected_branch）拋例外時的行為：同樣
   視為 main() 未預期例外，交由 fail_closed=True 統一轉 DENY——即使目標路徑
   原本應豁免，異常下仍保守阻擋，不因為是豁免判定內部錯誤就特殊放行

Source: 0.2.1-W3-508（承接 0.2.1-W3-506 fail_closed 參數、0.2.1-W3-507 同型
切換模式）
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
    "branch_verify_hook_fail_closed",
    HOOKS_DIR / "branch-verify-hook.py",
)
hook_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook_module)


def _set_stdin(monkeypatch, payload: dict) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))


# ============================================================================
# 註冊點：fail_closed=True
# ============================================================================


class TestRegistrationFailClosed:
    def test_registration_uses_fail_closed_true(self):
        """`__main__` 區塊須以 fail_closed=True 呼叫 run_hook_safely。"""
        source = (HOOKS_DIR / "branch-verify-hook.py").read_text(encoding="utf-8")
        assert 'run_hook_safely(main, "branch-verify", fail_closed=True)' in source

    def test_unhandled_exception_in_main_returns_2_via_fail_closed(self, monkeypatch):
        """main() 拋未預期例外時，run_hook_safely(fail_closed=True) 回傳 2 而非 1。"""
        _set_stdin(
            monkeypatch,
            {"tool_name": "Edit", "tool_input": {"file_path": "/repo/src/foo.py"}},
        )
        monkeypatch.setattr(
            hook_module,
            "get_current_branch",
            lambda cwd=None: (_ for _ in ()).throw(RuntimeError("boom")),
        )

        exit_code = hook_module.run_hook_safely(
            hook_module.main, "branch-verify-test-fail-closed", fail_closed=True
        )

        assert exit_code == 2

    def test_unhandled_exception_in_main_returns_1_via_fail_open(self, monkeypatch):
        """對照組：fail_closed=False 時同一例外仍回傳 1（既有語意不變）。"""
        _set_stdin(
            monkeypatch,
            {"tool_name": "Edit", "tool_input": {"file_path": "/repo/src/foo.py"}},
        )
        monkeypatch.setattr(
            hook_module,
            "get_current_branch",
            lambda cwd=None: (_ for _ in ()).throw(RuntimeError("boom")),
        )

        exit_code = hook_module.run_hook_safely(
            hook_module.main, "branch-verify-test-fail-open", fail_closed=False
        )

        assert exit_code == 1


# ============================================================================
# 豁免清單判定拋例外時的行為（AC2/AC3）
# ============================================================================


class TestExemptPathExceptionBehavior:
    def test_exempt_path_judgment_exception_triggers_fail_closed_deny(self, monkeypatch):
        """豁免清單判定拋例外時，例外向上傳播交由 run_hook_safely(fail_closed=True)
        統一轉為 DENY（exit 2）——即使目標路徑原本應豁免（如 .claude/），異常下
        仍保守阻擋，不因為是豁免判定內部錯誤就特殊放行。

        此為刻意接受的行為（記錄於 ticket Solution）：豁免判定所倚賴的函式
        （get_project_root 4-fallback「永不失敗」、find_target_repo 內部已捕獲
        OSError/RuntimeError）在正常情況下極不易拋例外；一旦真的拋出，代表狀態
        已不可信，此時阻擋優於誤放行到保護分支。
        """
        _set_stdin(
            monkeypatch,
            {"tool_name": "Edit", "tool_input": {"file_path": "/repo/.claude/hooks/x.py"}},
        )
        monkeypatch.setattr(hook_module, "get_current_branch", lambda cwd=None: "main")
        monkeypatch.setattr(hook_module, "is_allowed_branch", lambda branch: False)
        monkeypatch.setattr(hook_module, "is_protected_branch", lambda branch: True)
        monkeypatch.setattr(
            hook_module,
            "is_exempt_path_on_protected_branch",
            lambda file_path, cwd=None, target_repo=None: (_ for _ in ()).throw(
                RuntimeError("exempt check boom")
            ),
        )

        exit_code = hook_module.run_hook_safely(
            hook_module.main, "branch-verify-test-exempt-exception", fail_closed=True
        )

        assert exit_code == 2

    def test_exempt_path_judgment_exception_returns_1_when_fail_open(self, monkeypatch):
        """對照組：同一豁免判定例外，fail_closed=False 時回傳 1（切換前既有行為）。"""
        _set_stdin(
            monkeypatch,
            {"tool_name": "Edit", "tool_input": {"file_path": "/repo/.claude/hooks/x.py"}},
        )
        monkeypatch.setattr(hook_module, "get_current_branch", lambda cwd=None: "main")
        monkeypatch.setattr(hook_module, "is_allowed_branch", lambda branch: False)
        monkeypatch.setattr(hook_module, "is_protected_branch", lambda branch: True)
        monkeypatch.setattr(
            hook_module,
            "is_exempt_path_on_protected_branch",
            lambda file_path, cwd=None, target_repo=None: (_ for _ in ()).throw(
                RuntimeError("exempt check boom")
            ),
        )

        exit_code = hook_module.run_hook_safely(
            hook_module.main, "branch-verify-test-exempt-exception-fail-open", fail_closed=False
        )

        assert exit_code == 1
