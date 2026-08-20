#!/usr/bin/env python3
"""
UTF-8 Integrity Check Hook - 測試（0.2.1-W3-632）

驗證 utf8-integrity-check-hook.py 三類覆蓋：
- 類別 A：抽樣計數器路徑解析（_get_sampling_counter_file 於呼叫時求值，非 import 時）
- 類別 B：CLAUDE_PROJECT_DIR 隔離生效（計數器落在 tmp_path 而非 repo 層級）
- 類別 C：hook 主流程（U+FFFD 掃描正常與異常路徑）
- 類別 D：子行程整合（exit code + additionalContext）

結構比照 test_language_guard.py（0.2.1-W3-616 隔離改造後的既有測試）。

硬性約束：
- D 類 subprocess 測試沿用 hook_project_env fixture，全程不觸碰 production
  的 .claude/hook-logs/_sampling/utf8-integrity-check-hook.count
"""

import importlib.util
import json as _json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(HOOK_DIR))

_spec = importlib.util.spec_from_file_location(
    "utf8_integrity_check_hook",
    HOOK_DIR / "utf8-integrity-check-hook.py",
)
hook_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook_module)

_get_sampling_counter_file = hook_module._get_sampling_counter_file
should_sample_run = hook_module.should_sample_run
scan_file_for_replacement_chars = hook_module.scan_file_for_replacement_chars
extract_file_paths = hook_module.extract_file_paths
is_binary_file = hook_module.is_binary_file
SAMPLING_N = hook_module.SAMPLING_N

HOOK_PATH = HOOK_DIR / "utf8-integrity-check-hook.py"


# ============================================================================
# 子行程執行輔助
# ============================================================================


def _prime_sampling_counter(project_root: Path):
    """將抽樣計數器設為 SAMPLING_N - 1，確保下一次 hook 執行命中完整檢查。

    計數器路徑由 project_root 組出（呼應 hook 內 _get_sampling_counter_file()
    以 get_project_root() 動態解析），使 prime 對象與 subprocess 內
    CLAUDE_PROJECT_DIR 指向的隔離目錄一致。
    """
    counter_file = project_root / "hook-logs" / "_sampling" / "utf8-integrity-check-hook.count"
    counter_file.parent.mkdir(parents=True, exist_ok=True)
    counter_file.write_text(str(SAMPLING_N - 1))


def _run_hook(payload: dict, project_root: Path, env: dict) -> tuple:
    """以子行程方式執行 hook，回傳 (exit_code, stdout, stderr)。

    project_root / env 由 hook_project_env fixture 提供（CLAUDE_PROJECT_DIR
    指向 pytest tmp_path），使計數器讀寫完全隔離於 production repo。
    """
    _prime_sampling_counter(project_root)
    full_env = os.environ.copy()
    full_env.update(env)
    proc = subprocess.run(
        ["python3", str(HOOK_PATH)],
        input=_json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=10,
        env=full_env,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _make_write_payload(file_path: str) -> dict:
    """建立 Write tool_input payload。"""
    return {
        "tool_name": "Write",
        "tool_input": {"file_path": file_path},
    }


# ============================================================================
# 類別 A：抽樣計數器路徑解析
# ============================================================================


class TestSamplingCounterPathResolution:
    """類別 A：_get_sampling_counter_file() 於呼叫時求值，非 import 時固定。"""

    def test_counter_path_resolved_at_call_time(self, monkeypatch, tmp_path):
        """A1: 呼叫時才求值 get_project_root()，可被 monkeypatch 動態改變。"""
        fake_root_1 = tmp_path / "root1"
        fake_root_2 = tmp_path / "root2"

        monkeypatch.setattr(hook_module, "get_project_root", lambda: fake_root_1)
        path1 = _get_sampling_counter_file()
        assert path1 == fake_root_1 / "hook-logs" / "_sampling" / "utf8-integrity-check-hook.count"

        monkeypatch.setattr(hook_module, "get_project_root", lambda: fake_root_2)
        path2 = _get_sampling_counter_file()
        assert path2 == fake_root_2 / "hook-logs" / "_sampling" / "utf8-integrity-check-hook.count"

        assert path1 != path2, "同一 process 內兩次呼叫應反映 get_project_root() 的最新值"

    def test_counter_path_uses_hook_logs_sampling_subdir(self, monkeypatch, tmp_path):
        """A2: 計數器路徑固定為 <project_root>/hook-logs/_sampling/utf8-integrity-check-hook.count。"""
        monkeypatch.setattr(hook_module, "get_project_root", lambda: tmp_path)
        path = _get_sampling_counter_file()
        assert path.parent.name == "_sampling"
        assert path.parent.parent.name == "hook-logs"
        assert path.name == "utf8-integrity-check-hook.count"


# ============================================================================
# 類別 B：CLAUDE_PROJECT_DIR 隔離生效
# ============================================================================


class TestProjectDirIsolation:
    """類別 B：CLAUDE_PROJECT_DIR 隔離生效，計數器落在 tmp_path 而非 repo 層級。"""

    def test_should_sample_run_writes_counter_under_isolated_root(
        self, monkeypatch, tmp_path
    ):
        """B1: should_sample_run() 寫入的計數檔落在被 monkeypatch 的隔離根目錄。"""
        import logging

        monkeypatch.setattr(hook_module, "get_project_root", lambda: tmp_path)
        logger = logging.getLogger("test_utf8_integrity_check")

        should_sample_run(logger)

        counter_file = tmp_path / "hook-logs" / "_sampling" / "utf8-integrity-check-hook.count"
        assert counter_file.exists(), "計數檔應建立於隔離根目錄下"

    def test_isolated_counter_independent_of_repo_counter(
        self, monkeypatch, tmp_path
    ):
        """B2: 隔離根目錄下的計數與 production 計數互不影響（不同路徑各自累計）。"""
        import logging

        monkeypatch.setattr(hook_module, "get_project_root", lambda: tmp_path)
        logger = logging.getLogger("test_utf8_integrity_check")

        for _ in range(3):
            should_sample_run(logger)

        counter_file = tmp_path / "hook-logs" / "_sampling" / "utf8-integrity-check-hook.count"
        assert counter_file.read_text().strip() == "3"

    def test_subprocess_isolation_via_hook_project_env(self, hook_project_env):
        """B3: subprocess 執行下 CLAUDE_PROJECT_DIR 覆寫生效，計數檔落在 tmp_path。"""
        project_root, env = hook_project_env
        target = project_root / "sample.txt"
        target.write_text("純繁體文字，無損壞。", encoding="utf-8")

        _run_hook(_make_write_payload(str(target)), project_root, env)

        counter_file = project_root / "hook-logs" / "_sampling" / "utf8-integrity-check-hook.count"
        assert counter_file.exists(), "隔離環境下計數檔應建立於 tmp_path，而非 repo 層級"


# ============================================================================
# 類別 C：hook 主流程（正常與異常路徑）
# ============================================================================


class TestCoreScanLogic:
    """類別 C：U+FFFD 掃描邏輯的正常與異常路徑（純函式，無 subprocess）。"""

    def test_scan_detects_replacement_char(self, tmp_path):
        """C1: 檔案含 U+FFFD 時回傳非空損壞位置清單。"""
        import logging

        f = tmp_path / "corrupted.md"
        f.write_text("正常文字\n損壞位置�結束\n", encoding="utf-8")
        logger = logging.getLogger("test_utf8_integrity_check")

        locations = scan_file_for_replacement_chars(str(f), logger)

        assert len(locations) == 1
        line_num, snippet = locations[0]
        assert line_num == 2
        assert "�" in snippet

    def test_scan_clean_file_returns_empty(self, tmp_path):
        """C2: 無 U+FFFD 的正常檔案回傳空清單。"""
        import logging

        f = tmp_path / "clean.md"
        f.write_text("純繁體中文內容，無任何損壞字元。", encoding="utf-8")
        logger = logging.getLogger("test_utf8_integrity_check")

        assert scan_file_for_replacement_chars(str(f), logger) == []

    def test_scan_nonexistent_file_returns_empty(self, tmp_path):
        """C3: 檔案不存在（OSError）時回傳空清單，不拋例外。"""
        import logging

        missing = tmp_path / "does_not_exist.md"
        logger = logging.getLogger("test_utf8_integrity_check")

        assert scan_file_for_replacement_chars(str(missing), logger) == []

    def test_scan_caps_at_max_reported_locations(self, tmp_path):
        """C4: 損壞位置數超過 MAX_REPORTED_LOCATIONS 時提前截斷。"""
        import logging

        f = tmp_path / "many_corruptions.md"
        lines = [f"第 {i} 行 � 損壞" for i in range(10)]
        f.write_text("\n".join(lines), encoding="utf-8")
        logger = logging.getLogger("test_utf8_integrity_check")

        locations = scan_file_for_replacement_chars(str(f), logger)

        assert len(locations) == hook_module.MAX_REPORTED_LOCATIONS

    def test_is_binary_file_skips_known_extensions(self):
        """C5: 二進位副檔名判定為 True，不掃描。"""
        assert is_binary_file("assets/logo.png")
        assert is_binary_file("archive.zip")
        assert not is_binary_file("README.md")
        assert not is_binary_file("main.dart")

    def test_extract_file_paths_from_write_tool_input(self):
        """C6: 從 Write/Edit/MultiEdit tool_input 提取 file_path。"""
        assert extract_file_paths({"file_path": "a.md"}) == ["a.md"]
        assert extract_file_paths({}) == []
        assert extract_file_paths({"other": "value"}) == []


# ============================================================================
# 類別 D：子行程整合（exit code + additionalContext 雙通道）
# ============================================================================


class TestHookSubprocessIntegration:
    """類別 D：完整 hook 子行程執行（規則 4：失敗必須可見）。"""

    def test_clean_file_exits_zero_silent(self, hook_project_env):
        """D1: 無損壞檔案 → exit 0，stderr 無警告。"""
        project_root, env = hook_project_env
        target = project_root / "clean.md"
        target.write_text("純繁體中文，無損壞。", encoding="utf-8")

        code, _, err = _run_hook(_make_write_payload(str(target)), project_root, env)

        assert code == 0, f"clean 檔案應 exit 0，實際 {code}"
        assert "[UTF-8 INTEGRITY]" not in err, f"clean 檔案不應有警告：{err}"

    def test_corrupted_file_exits_zero_with_warning(self, hook_project_env):
        """D2: U+FFFD 觸發警告但不阻擋（exit 0 + stderr 警告）。"""
        project_root, env = hook_project_env
        target = project_root / "corrupted.md"
        target.write_text("正常內容\n損壞�位置\n", encoding="utf-8")

        code, _, err = _run_hook(_make_write_payload(str(target)), project_root, env)

        assert code == 0, "警告非阻擋，應 exit 0"
        assert "[UTF-8 INTEGRITY]" in err
        assert "U+FFFD" in err

    def test_binary_extension_skipped_silently(self, hook_project_env):
        """D3: 二進位副檔名檔案被跳過，即使內容含 U+FFFD 也不掃描。"""
        project_root, env = hook_project_env
        target = project_root / "image.png"
        target.write_bytes("損壞�內容".encode("utf-8"))

        code, _, err = _run_hook(_make_write_payload(str(target)), project_root, env)

        assert code == 0
        assert "[UTF-8 INTEGRITY]" not in err

    def test_empty_stdin_passes_silently(self, hook_project_env):
        """D4: 無 stdin 輸入靜默通過（已預期非標準輸入路徑）。"""
        project_root, env = hook_project_env
        full_env = os.environ.copy()
        full_env.update(env)
        proc = subprocess.run(
            ["python3", str(HOOK_PATH)],
            input="",
            capture_output=True,
            text=True,
            timeout=10,
            env=full_env,
        )
        assert proc.returncode == 0, f"空 stdin 應 exit 0，實際 {proc.returncode}"
        assert "[UTF-8 INTEGRITY]" not in proc.stderr

    def test_no_file_path_passes_silently(self, hook_project_env):
        """D5: tool_input 無 file_path 時靜默通過。"""
        project_root, env = hook_project_env
        payload = {"tool_name": "Write", "tool_input": {}}

        code, _, err = _run_hook(payload, project_root, env)

        assert code == 0
        assert "[UTF-8 INTEGRITY]" not in err

    def test_nonexistent_file_passes_silently(self, hook_project_env):
        """D6: file_path 指向不存在的檔案時靜默通過（非 crash）。"""
        project_root, env = hook_project_env
        missing = project_root / "ghost.md"

        code, _, err = _run_hook(_make_write_payload(str(missing)), project_root, env)

        assert code == 0
        assert "[UTF-8 INTEGRITY]" not in err

    def test_subprocess_never_touches_production_counter(self, hook_project_env):
        """D7: 核心驗收——subprocess 執行前後，production 抽樣計數器完全不變。

        production 計數器路徑固定於 repo 層級（.claude/hook-logs/_sampling/），
        本測試以真實檔案系統路徑（而非 hook_project_env 隔離路徑）比對，
        確保 CLAUDE_PROJECT_DIR 覆寫確實阻絕了對 production 檔案的任何寫入。
        """
        project_root, env = hook_project_env
        repo_root = Path(__file__).parent.parent.parent
        prod_counter = (
            repo_root / "hook-logs" / "_sampling" / "utf8-integrity-check-hook.count"
        )

        before_exists = prod_counter.exists()
        before_value = prod_counter.read_text() if before_exists else None
        before_mtime = prod_counter.stat().st_mtime if before_exists else None

        target = project_root / "corrupted.md"
        target.write_text("損壞�內容", encoding="utf-8")
        _run_hook(_make_write_payload(str(target)), project_root, env)

        after_exists = prod_counter.exists()
        after_value = prod_counter.read_text() if after_exists else None
        after_mtime = prod_counter.stat().st_mtime if after_exists else None

        assert before_exists == after_exists
        assert before_value == after_value, "production 計數器 value 不應變動"
        assert before_mtime == after_mtime, "production 計數器 mtime 不應變動"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
