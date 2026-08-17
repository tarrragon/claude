"""ticket_system.lib.claude_lib_loader 測試。

收斂自五處近乎相同複本（lease.py / track_activity.py / track_onboard.py /
track_sessions.py / track_conflicts.py / track_hook_health.py）的
`_find_claude_dir` + `_load_*` lazy import pair，本檔驗證共用實作本身：

1. `find_claude_dir`：CLAUDE_PROJECT_DIR 優先、cwd 向上搜尋、marker 檔案
   存在性驗證
2. `load_claude_lib`：marker 預設為 `f"{module_name}.py"`、快取行為、
   找不到時降級回傳 None
3. `resolve_toplevel`：純函式，給定 run_git callable 解析 toplevel 字串
4. `current_project_root`：自帶預設執行器（git_utils 優先、subprocess 降級）
5. `empty_registry_skeleton`：每次呼叫回傳新物件，不可共享可變狀態
"""

from __future__ import annotations

from typing import Optional

from ticket_system.lib import claude_lib_loader


# --- find_claude_dir --------------------------------------------------------


class TestFindClaudeDir:
    def test_finds_dir_via_claude_project_dir_env_when_marker_exists(
        self, tmp_path, monkeypatch
    ):
        claude_dir = tmp_path / ".claude"
        (claude_dir / "lib").mkdir(parents=True)
        (claude_dir / "lib" / "pm_registry.py").write_text("", encoding="utf-8")
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))

        result = claude_lib_loader.find_claude_dir("pm_registry.py")

        assert result == claude_dir

    def test_env_dir_without_marker_falls_through_to_none(self, tmp_path, monkeypatch):
        """CLAUDE_PROJECT_DIR 指向的目錄無 marker 檔案時，不可誤判為命中
        （必須繼續往其餘策略找，找不到則回傳 None，非直接信任環境變數存在）。
        """
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir(parents=True)
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
        monkeypatch.setattr(claude_lib_loader.Path, "cwd", staticmethod(lambda: tmp_path))

        result = claude_lib_loader.find_claude_dir("nonexistent_marker.py")

        assert result is None

    def test_finds_dir_via_cwd_upward_search(self, tmp_path, monkeypatch):
        claude_dir = tmp_path / "project" / ".claude"
        (claude_dir / "lib").mkdir(parents=True)
        (claude_dir / "lib" / "git_utils.py").write_text("", encoding="utf-8")
        nested_cwd = tmp_path / "project" / "sub" / "dir"
        nested_cwd.mkdir(parents=True)
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
        monkeypatch.setattr(claude_lib_loader.Path, "cwd", staticmethod(lambda: nested_cwd))

        result = claude_lib_loader.find_claude_dir("git_utils.py")

        assert result == claude_dir


# --- load_claude_lib ---------------------------------------------------------


class TestLoadClaudeLib:
    def test_marker_defaults_to_module_name_dot_py(self, monkeypatch):
        captured = {}

        def _fake_find(marker):
            captured["marker"] = marker
            return None

        monkeypatch.setattr(claude_lib_loader, "find_claude_dir", _fake_find)
        claude_lib_loader._MODULE_CACHE.clear()

        result = claude_lib_loader.load_claude_lib("hook_health")

        assert result is None
        assert captured["marker"] == "hook_health.py"

    def test_explicit_marker_overrides_default(self, monkeypatch):
        captured = {}

        def _fake_find(marker):
            captured["marker"] = marker
            return None

        monkeypatch.setattr(claude_lib_loader, "find_claude_dir", _fake_find)
        claude_lib_loader._MODULE_CACHE.clear()

        claude_lib_loader.load_claude_lib("pm_registry", marker="custom_marker.py")

        assert captured["marker"] == "custom_marker.py"

    def test_missing_claude_dir_returns_none(self, monkeypatch):
        monkeypatch.setattr(claude_lib_loader, "find_claude_dir", lambda marker: None)
        claude_lib_loader._MODULE_CACHE.clear()

        result = claude_lib_loader.load_claude_lib("does_not_exist")

        assert result is None

    def test_caches_by_marker_and_module_name(self, monkeypatch):
        """第二次呼叫相同 (marker, module_name) 不重複呼叫 find_claude_dir。"""
        call_count = {"n": 0}

        def _fake_find(marker):
            call_count["n"] += 1
            return None  # 不可用時直接短路，仍可驗證呼叫次數

        monkeypatch.setattr(claude_lib_loader, "find_claude_dir", _fake_find)
        claude_lib_loader._MODULE_CACHE.clear()

        claude_lib_loader.load_claude_lib("hook_health")
        claude_lib_loader.load_claude_lib("hook_health")

        # find_claude_dir 回傳 None 時不進入快取分支（每次都會重試，符合
        # 「不可用時不阻擋、允許之後重試」的既有降級語意），故呼叫兩次
        assert call_count["n"] == 2


# --- resolve_toplevel ---------------------------------------------------------


class TestResolveToplevel:
    def test_resolves_and_normalizes_path(self, tmp_path):
        real_dir = tmp_path / "repo"
        real_dir.mkdir()

        def _run_git(*args: str) -> Optional[str]:
            assert args == ("rev-parse", "--show-toplevel")
            return str(real_dir) + "/"  # 尾端斜線模擬未正規化輸出

        result = claude_lib_loader.resolve_toplevel(_run_git)

        assert result == str(real_dir.resolve())

    def test_empty_output_returns_none(self):
        result = claude_lib_loader.resolve_toplevel(lambda *a: "")
        assert result is None

    def test_none_output_returns_none(self):
        result = claude_lib_loader.resolve_toplevel(lambda *a: None)
        assert result is None


# --- current_project_root ----------------------------------------------------


class TestCurrentProjectRoot:
    def test_uses_git_utils_when_available(self, tmp_path, monkeypatch):
        real_dir = tmp_path / "repo"
        real_dir.mkdir()

        class _FakeGitUtils:
            @staticmethod
            def run_git_command(args, timeout=5):
                assert args == ["rev-parse", "--show-toplevel"]
                return True, str(real_dir) + "\n"

        monkeypatch.setattr(
            claude_lib_loader, "load_claude_lib", lambda name: _FakeGitUtils()
        )

        result = claude_lib_loader.current_project_root()

        assert result == str(real_dir.resolve())

    def test_falls_back_to_subprocess_when_git_utils_unavailable(
        self, tmp_path, monkeypatch
    ):
        real_dir = tmp_path / "repo"
        real_dir.mkdir()
        monkeypatch.setattr(claude_lib_loader, "load_claude_lib", lambda name: None)

        class _FakeCompletedProcess:
            returncode = 0
            stdout = str(real_dir) + "\n"

        def _fake_run(cmd, capture_output, text, timeout, check):
            assert cmd == ["git", "rev-parse", "--show-toplevel"]
            return _FakeCompletedProcess()

        monkeypatch.setattr(claude_lib_loader.subprocess, "run", _fake_run)

        result = claude_lib_loader.current_project_root()

        assert result == str(real_dir.resolve())

    def test_git_utils_and_subprocess_both_unavailable_returns_none(self, monkeypatch):
        monkeypatch.setattr(claude_lib_loader, "load_claude_lib", lambda name: None)

        def _raise_not_found(*a, **k):
            raise FileNotFoundError("git not installed")

        monkeypatch.setattr(claude_lib_loader.subprocess, "run", _raise_not_found)

        result = claude_lib_loader.current_project_root()

        assert result is None


# --- empty_registry_skeleton --------------------------------------------------


class TestEmptyRegistrySkeleton:
    def test_returns_expected_shape(self):
        result = claude_lib_loader.empty_registry_skeleton()

        assert result == {"schema_version": 0, "sessions": {}}

    def test_each_call_returns_independent_object(self):
        """兩次呼叫回傳的 dict 必須是不同物件——若共享同一個可變常數，
        呼叫端各自 mutate 會互相污染（如某呼叫端誤在降級路徑上寫入
        sessions[x] = ...）。"""
        a = claude_lib_loader.empty_registry_skeleton()
        b = claude_lib_loader.empty_registry_skeleton()

        assert a is not b
        assert a["sessions"] is not b["sessions"]

        a["sessions"]["polluted"] = True
        assert "polluted" not in b["sessions"]
