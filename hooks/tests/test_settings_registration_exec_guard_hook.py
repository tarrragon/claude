"""
Test: settings-registration-exec-guard-hook（攔截面改版：PostToolUse 監控
hook 檔案落地事件，取代舊版解析 settings.json 差集推導）

驗證項目：
1. is_monitored_hook_path：頂層 .claude/hooks/ 的 .py/.sh（非遞迴）與
   .claude/skills/<skill>/hooks/ 下的 .py/.sh（遞迴，略過快取目錄）判定
2. fix_missing_exec_bit：缺可執行位時 chmod +x、已具可執行位/不存在時
   不動作
3. main() 整合：
   - 先註冊後建檔順序下，Write 落地缺可執行位的 hook 檔案時即被自動修復
     （不依賴 settings.json 是否已註冊，附重現測試）
   - MultiEdit 落地缺可執行位的 hook 檔案同樣被偵測修復（原設計此路徑
     完全無防護的維度已因改用檔案落地監控而消失）
   - skill hooks 目錄下的 .py 落地時同樣受監控（子目錄遞迴掃描行為）
   - 非監控範圍（其他工具 / 非 hook 路徑 / 已可執行）不動作

Source: 0.2.1-W3-499（原始設計）Phase 4 五視角審查 -> 攔截面改造 ticket
"""

import importlib.util
import io
import json
import logging
import os
import stat
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent))

_spec = importlib.util.spec_from_file_location(
    "settings_registration_exec_guard_hook",
    HOOKS_DIR / "settings-registration-exec-guard-hook.py",
)
hook_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook_module)

is_monitored_hook_path = hook_module.is_monitored_hook_path
fix_missing_exec_bit = hook_module.fix_missing_exec_bit
main = hook_module.main


def _make_file(path: Path, executable: bool) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/usr/bin/env python3\n")
    mode = path.stat().st_mode
    if executable:
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    else:
        path.chmod(mode & ~stat.S_IXUSR & ~stat.S_IXGRP & ~stat.S_IXOTH)
    return path


# ============================================================================
# is_monitored_hook_path
# ============================================================================


class TestIsMonitoredHookPath:
    def test_top_level_hook_py_is_monitored(self, tmp_path):
        target = tmp_path / ".claude" / "hooks" / "new-hook.py"
        target.parent.mkdir(parents=True)
        target.write_text("x")
        assert is_monitored_hook_path(str(target), tmp_path) == target.resolve()

    def test_top_level_hook_sh_is_monitored(self, tmp_path):
        target = tmp_path / ".claude" / "hooks" / "new-hook.sh"
        target.parent.mkdir(parents=True)
        target.write_text("x")
        assert is_monitored_hook_path(str(target), tmp_path) == target.resolve()

    def test_top_level_subdirectory_not_monitored(self, tmp_path):
        """tests/、acceptance_checkers/、archived/ 等子目錄不受監控（非遞迴）。"""
        target = tmp_path / ".claude" / "hooks" / "tests" / "test_x.py"
        target.parent.mkdir(parents=True)
        target.write_text("x")
        assert is_monitored_hook_path(str(target), tmp_path) is None

    def test_skill_hooks_py_is_monitored(self, tmp_path):
        target = tmp_path / ".claude" / "skills" / "myskill" / "hooks" / "x.py"
        target.parent.mkdir(parents=True)
        target.write_text("x")
        assert is_monitored_hook_path(str(target), tmp_path) == target.resolve()

    def test_skill_hooks_nested_subdirectory_is_monitored(self, tmp_path):
        """hooks/ 下再有子目錄時仍遞迴納入（非快取目錄）。"""
        target = tmp_path / ".claude" / "skills" / "myskill" / "hooks" / "sub" / "y.py"
        target.parent.mkdir(parents=True)
        target.write_text("x")
        assert is_monitored_hook_path(str(target), tmp_path) == target.resolve()

    def test_skill_pycache_not_monitored(self, tmp_path):
        target = (
            tmp_path / ".claude" / "skills" / "myskill" / "hooks" / "__pycache__" / "x.pyc"
        )
        target.parent.mkdir(parents=True)
        target.write_text("x")
        # .pyc 副檔名本就不在 _HOOK_SCRIPT_SUFFIXES，額外驗證同目錄下 .py 也被排除
        py_in_cache = target.parent / "cached.py"
        py_in_cache.write_text("x")
        assert is_monitored_hook_path(str(py_in_cache), tmp_path) is None

    def test_skill_non_hooks_subdirectory_not_monitored(self, tmp_path):
        """skill 目錄下非 hooks/ 子目錄（如 scripts/）不受監控。"""
        target = tmp_path / ".claude" / "skills" / "myskill" / "scripts" / "x.py"
        target.parent.mkdir(parents=True)
        target.write_text("x")
        assert is_monitored_hook_path(str(target), tmp_path) is None

    def test_non_script_extension_not_monitored(self, tmp_path):
        target = tmp_path / ".claude" / "hooks" / "readme.md"
        target.parent.mkdir(parents=True)
        target.write_text("x")
        assert is_monitored_hook_path(str(target), tmp_path) is None

    def test_empty_path_returns_none(self, tmp_path):
        assert is_monitored_hook_path("", tmp_path) is None

    def test_unrelated_path_returns_none(self, tmp_path):
        assert is_monitored_hook_path(str(tmp_path / "src" / "main.py"), tmp_path) is None


# ============================================================================
# fix_missing_exec_bit
# ============================================================================


class TestFixMissingExecBit:
    def test_missing_exec_bit_is_fixed(self, tmp_path):
        target = _make_file(tmp_path / "x.py", executable=False)
        assert fix_missing_exec_bit(target) is True
        assert os.access(target, os.X_OK)

    def test_already_executable_not_touched(self, tmp_path):
        target = _make_file(tmp_path / "x.py", executable=True)
        assert fix_missing_exec_bit(target) is False

    def test_nonexistent_file_returns_false(self, tmp_path):
        assert fix_missing_exec_bit(tmp_path / "ghost.py") is False


# ============================================================================
# main() 整合
# ============================================================================


def _run_hook(monkeypatch, tool_name, tool_input, project_root):
    payload = {"tool_name": tool_name, "tool_input": tool_input}
    stdin_buffer = io.StringIO(json.dumps(payload))
    monkeypatch.setattr(sys, "stdin", stdin_buffer)
    monkeypatch.setattr(hook_module, "get_project_root", lambda: project_root)
    return main()


class TestMainIntegration:
    def test_write_new_hook_without_exec_bit_is_autofixed(
        self, tmp_path, monkeypatch, capsys
    ):
        """重現測試（AC1）：先寫 settings.json 註冊、後 Write 建立 hook 檔案的
        操作順序下，落地當下即被自動修復——本 hook 完全不解析 settings.json，
        故「先註冊」這步是否發生、其內容為何，都不影響判斷結果，直接以
        settings.json 已含註冊項模擬該順序作對照。
        """
        # 模擬「先註冊」：settings.json 已存在且已含此檔的註冊項
        settings_path = tmp_path / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True)
        settings_path.write_text(
            json.dumps(
                {
                    "hooks": {
                        "PostToolUse": [
                            {
                                "matcher": "Write",
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/new-hook.py",
                                    }
                                ],
                            }
                        ]
                    }
                }
            )
        )

        # 「後建檔」：此時目標檔案才落地，缺可執行位
        target = tmp_path / ".claude" / "hooks" / "new-hook.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("#!/usr/bin/env python3\n")
        mode = target.stat().st_mode
        target.chmod(mode & ~stat.S_IXUSR & ~stat.S_IXGRP & ~stat.S_IXOTH)
        assert not os.access(target, os.X_OK)

        exit_code = _run_hook(
            monkeypatch, "Write", {"file_path": str(target), "content": "x"}, tmp_path
        )

        assert exit_code == 0  # PostToolUse 不 deny
        assert os.access(target, os.X_OK)
        err = capsys.readouterr().err
        assert "已自動修復" in err
        assert "new-hook.py" in err

    def test_write_new_hook_with_exec_bit_no_action(self, tmp_path, monkeypatch, capsys):
        target = _make_file(tmp_path / ".claude" / "hooks" / "new-hook.py", executable=True)
        exit_code = _run_hook(
            monkeypatch, "Write", {"file_path": str(target), "content": "x"}, tmp_path
        )
        assert exit_code == 0
        assert capsys.readouterr().err == ""

    def test_edit_existing_hook_without_exec_bit_is_autofixed(
        self, tmp_path, monkeypatch, capsys
    ):
        target = _make_file(tmp_path / ".claude" / "hooks" / "existing.py", executable=False)
        exit_code = _run_hook(
            monkeypatch,
            "Edit",
            {"file_path": str(target), "old_string": "a", "new_string": "b"},
            tmp_path,
        )
        assert exit_code == 0
        assert os.access(target, os.X_OK)

    def test_multiedit_new_hook_without_exec_bit_is_autofixed(
        self, tmp_path, monkeypatch, capsys
    ):
        """MultiEdit 落地缺可執行位的 hook 檔案同樣被偵測修復（原設計此路徑
        完全無防護的維度已因改用檔案落地監控而消失，非本 hook 特別繞道處理）。
        """
        target = _make_file(
            tmp_path / ".claude" / "hooks" / "multiedit-hook.py", executable=False
        )
        exit_code = _run_hook(
            monkeypatch,
            "MultiEdit",
            {"file_path": str(target), "edits": [{"old_string": "a", "new_string": "b"}]},
            tmp_path,
        )
        assert exit_code == 0
        assert os.access(target, os.X_OK)

    def test_skill_hook_without_exec_bit_is_autofixed(self, tmp_path, monkeypatch, capsys):
        """skill hooks 目錄下的 .py 落地時同樣受監控（子目錄遞迴掃描行為）。"""
        target = _make_file(
            tmp_path / ".claude" / "skills" / "myskill" / "hooks" / "x.py",
            executable=False,
        )
        exit_code = _run_hook(
            monkeypatch, "Write", {"file_path": str(target), "content": "x"}, tmp_path
        )
        assert exit_code == 0
        assert os.access(target, os.X_OK)
        err = capsys.readouterr().err
        assert "myskill" in err

    def test_non_hook_path_no_action(self, tmp_path, monkeypatch, capsys):
        target = _make_file(tmp_path / "src" / "main.py", executable=False)
        exit_code = _run_hook(
            monkeypatch, "Write", {"file_path": str(target), "content": "x"}, tmp_path
        )
        assert exit_code == 0
        assert not os.access(target, os.X_OK)
        assert capsys.readouterr().err == ""

    def test_non_monitored_tool_no_action(self, tmp_path, monkeypatch):
        target = _make_file(tmp_path / ".claude" / "hooks" / "y.py", executable=False)
        exit_code = _run_hook(
            monkeypatch, "Read", {"file_path": str(target)}, tmp_path
        )
        assert exit_code == 0
        assert not os.access(target, os.X_OK)

    def test_notebookedit_not_monitored(self, tmp_path, monkeypatch):
        """NotebookEdit 僅操作 .ipynb，刻意不在監控範圍（見 docstring 說明）。"""
        target = _make_file(tmp_path / ".claude" / "hooks" / "z.py", executable=False)
        exit_code = _run_hook(
            monkeypatch, "NotebookEdit", {"notebook_path": str(target)}, tmp_path
        )
        assert exit_code == 0
        assert not os.access(target, os.X_OK)

    def test_empty_stdin_returns_zero(self, monkeypatch):
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
        assert main() == 0


# ============================================================================
# 例外可觀測性（0.2.1-W3-515）
# ============================================================================


class TestOsErrorObservability:
    def test_resolve_oserror_logged_when_logger_provided(self, tmp_path, monkeypatch, caplog):
        """is_monitored_hook_path 的 resolve() OSError 是真實例外，傳入 logger
        時須記錄 warning（observability-rules 規則 1）。"""
        logger_name = "test-w3-515-oserror"
        logger = logging.getLogger(logger_name)

        def _raise_oserror(self):
            raise OSError("simulated resolve failure")

        monkeypatch.setattr(Path, "resolve", _raise_oserror)

        with caplog.at_level(logging.WARNING, logger=logger_name):
            result = is_monitored_hook_path("some/path.py", tmp_path, logger)

        assert result is None
        assert any("解析路徑失敗" in record.message for record in caplog.records)

    def test_resolve_oserror_no_crash_without_logger(self, tmp_path, monkeypatch):
        """未傳 logger（如單元測試直接呼叫）時，OSError 分支仍靜默回傳 None，不拋例外。"""

        def _raise_oserror(self):
            raise OSError("simulated resolve failure")

        monkeypatch.setattr(Path, "resolve", _raise_oserror)

        assert is_monitored_hook_path("some/path.py", tmp_path) is None


# ============================================================================
# 邊界測試（0.2.1-W3-515 AC2）
# ============================================================================


class TestBoundaryChmodOSErrorPropagation:
    def test_chmod_oserror_propagates_through_main_not_swallowed(
        self, tmp_path, monkeypatch
    ):
        """fix_missing_exec_bit 的 chmod() 失敗刻意不在本檔任何函式內捕捉，
        直接呼叫 main() 時例外必須向上傳播（未被局部 try/except 靜默吞掉）。
        """
        target = _make_file(tmp_path / ".claude" / "hooks" / "readonly.py", executable=False)

        def _raise_chmod_oserror(self, mode):
            raise OSError("simulated permission denied")

        monkeypatch.setattr(Path, "chmod", _raise_chmod_oserror)
        payload = {"tool_name": "Write", "tool_input": {"file_path": str(target), "content": "x"}}
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        monkeypatch.setattr(hook_module, "get_project_root", lambda: tmp_path)

        with pytest.raises(OSError, match="simulated permission denied"):
            main()

    def test_chmod_oserror_recorded_by_run_hook_safely_as_exit_1(
        self, tmp_path, monkeypatch
    ):
        """交由 run_hook_safely 統一處理時，chmod OSError 使 exit code 為 1
        （fail_closed 預設 False，與本 hook 的『不 deny』設計一致），非靜默成功。
        """
        target = _make_file(tmp_path / ".claude" / "hooks" / "readonly2.py", executable=False)

        def _raise_chmod_oserror(self, mode):
            raise OSError("simulated permission denied")

        monkeypatch.setattr(Path, "chmod", _raise_chmod_oserror)
        payload = {"tool_name": "Write", "tool_input": {"file_path": str(target), "content": "x"}}
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        monkeypatch.setattr(hook_module, "get_project_root", lambda: tmp_path)

        exit_code = hook_module.run_hook_safely(
            hook_module.main, "settings-registration-exec-guard-test", fail_closed=False
        )

        assert exit_code == 1


class TestBoundarySkipDirs:
    @pytest.mark.parametrize(
        "skip_dir", ["__pycache__", ".venv", "node_modules", ".git"]
    )
    def test_each_skip_dir_entry_excludes_skill_hook_files(self, tmp_path, skip_dir):
        """_SKILL_HOOK_SKIP_DIRS 的每個成員都個別生效，而非只有 __pycache__。"""
        target = (
            tmp_path
            / ".claude"
            / "skills"
            / "myskill"
            / "hooks"
            / skip_dir
            / "inner.py"
        )
        target.parent.mkdir(parents=True)
        target.write_text("x")

        assert is_monitored_hook_path(str(target), tmp_path) is None

    def test_skip_dir_nested_deeper_still_excluded(self, tmp_path):
        """快取目錄底下再有子目錄時仍整段排除（略過清單以路徑各段命中判斷）。"""
        target = (
            tmp_path
            / ".claude"
            / "skills"
            / "myskill"
            / "hooks"
            / "__pycache__"
            / "nested"
            / "deep.py"
        )
        target.parent.mkdir(parents=True)
        target.write_text("x")

        assert is_monitored_hook_path(str(target), tmp_path) is None

    def test_sibling_of_skip_dir_still_monitored(self, tmp_path):
        """同層但非略過清單成員的目錄不受影響（確認排除範圍精確，非整個 hooks/ 失效）。"""
        target = (
            tmp_path / ".claude" / "skills" / "myskill" / "hooks" / "normal" / "x.py"
        )
        target.parent.mkdir(parents=True)
        target.write_text("x")

        assert is_monitored_hook_path(str(target), tmp_path) == target.resolve()


class TestBoundarySymlinkResolution:
    def test_symlink_inside_hooks_dir_pointing_outside_not_monitored(self, tmp_path):
        """符號連結的名義路徑在 .claude/hooks/ 內，但 resolve() 後真實目標在
        監控範圍外時，判定為不受監控——本 hook 修復的是實際會被 runtime
        執行的檔案，符號連結解析後的真實目標才是該檔案（見函式 docstring）。
        """
        outside_target = tmp_path / "outside.py"
        outside_target.write_text("outside")

        hooks_dir = tmp_path / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True)
        symlink_path = hooks_dir / "link.py"
        symlink_path.symlink_to(outside_target)

        assert is_monitored_hook_path(str(symlink_path), tmp_path) is None

    def test_symlink_inside_hooks_dir_pointing_to_another_monitored_file_is_monitored(
        self, tmp_path
    ):
        """對照組：符號連結指向另一個仍在監控範圍內的檔案時，應正常判定為受監控
        （驗證 resolve 判斷邏輯本身不是『看到符號連結一律排除』的過度保守版本）。
        """
        hooks_dir = tmp_path / ".claude" / "hooks"
        hooks_dir.mkdir(parents=True)
        real_target = hooks_dir / "real.py"
        real_target.write_text("real")
        symlink_path = hooks_dir / "link.py"
        symlink_path.symlink_to(real_target)

        assert is_monitored_hook_path(str(symlink_path), tmp_path) == real_target.resolve()
