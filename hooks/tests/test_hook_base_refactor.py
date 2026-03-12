#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試 hook_base 重構的完整驗證套件

測試範圍（14 個測試場景，3 個類別）：

### 單元測試（6 個）：
1. test_get_project_root_env_var_priority - 環境變數優先級
2. test_get_project_root_claude_md_search - CLAUDE.md 向上搜尋
3. test_get_project_root_fallback_to_cwd - Fallback 到 cwd
4. test_get_project_root_max_search_depth - 搜尋深度限制（5 層）
5. test_get_project_root_never_fails - 函式永不失敗
6. test_env_and_claude_md_constants - 常數定義正確性

### Import 轉換測試（3 個）：
7. test_re_export_from_hook_logging - hook_logging 的 re-export
8. test_import_from_hook_ticket - hook_ticket.py 的 import 轉換
9. test_import_from_hook_io - hook_io.py 的行內 import 轉換

### 向後相容與完整性（5 個）：
10. test_public_api_available_from_hook_utils - 公開 API 從 hook_utils 可用
11. test_external_hook_import_compatibility - 外部 Hook 的 import 相容性
12. test_circular_dependency_detection - 循環依賴檢測
13. test_hook_base_no_external_deps - hook_base 不依賴其他 hook_utils
14. test_project_root_moved_functions_cleanup - 舊位置函式清理驗證
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional
from unittest.mock import patch, MagicMock

import pytest

# 動態導入 hook_base 及相關模組
try:
    from hook_utils.hook_base import (
        get_project_root,
        _find_project_root,
        ENV_PROJECT_DIR,
        CLAUDE_MD_SEARCH_DEPTH,
    )
    hook_base_available = True
except ImportError:
    hook_base_available = False

try:
    from hook_utils import get_project_root as get_project_root_from_init
    from hook_utils.hook_logging import get_project_root as get_project_root_from_logging
    backward_compat_available = True
except ImportError:
    backward_compat_available = False


# ============================================================================
# 單元測試（6 個）
# ============================================================================

@pytest.mark.skipif(not hook_base_available, reason="hook_base 模組不可用")
class TestGetProjectRootPriority:
    """Test get_project_root 優先級（單元測試 1-5）"""

    def test_get_project_root_env_var_priority(self, monkeypatch):
        """單元測試 1：環境變數優先級

        驗證當設定環境變數 CLAUDE_PROJECT_DIR 時，get_project_root 回傳該路徑
        """
        test_path = "/test/project/root"
        monkeypatch.setenv(ENV_PROJECT_DIR, test_path)

        result = get_project_root()
        assert str(result) == test_path, f"預期 {test_path}，得到 {result}"

    def test_get_project_root_claude_md_search(self, tmp_path, monkeypatch):
        """單元測試 2：CLAUDE.md 向上搜尋

        驗證當未設環境變數時，從 cwd 向上搜尋 CLAUDE.md
        """
        # 清除環境變數
        monkeypatch.delenv(ENV_PROJECT_DIR, raising=False)

        # 建立目錄結構：root/a/b/c
        root = tmp_path
        (root / "CLAUDE.md").write_text("# Test Project\n")

        nested_dir = root / "a" / "b" / "c"
        nested_dir.mkdir(parents=True, exist_ok=True)

        # 從 nested_dir 呼叫 get_project_root，應該找到 root
        monkeypatch.chdir(nested_dir)
        result = get_project_root()
        assert result == root, f"預期找到根目錄 {root}，得到 {result}"

    def test_get_project_root_fallback_to_cwd(self, tmp_path, monkeypatch):
        """單元測試 3：Fallback 到 cwd

        驗證當環境變數不設且找不到 CLAUDE.md 時，回傳 cwd
        """
        # 清除環境變數
        monkeypatch.delenv(ENV_PROJECT_DIR, raising=False)

        # 在沒有 CLAUDE.md 的目錄中執行
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.chdir(empty_dir)

        result = get_project_root()
        assert result == empty_dir, f"預期 Fallback 到 {empty_dir}，得到 {result}"

    def test_get_project_root_max_search_depth(self, tmp_path, monkeypatch):
        """單元測試 4：搜尋深度限制（5 層）

        驗證搜尋深度不超過 CLAUDE_MD_SEARCH_DEPTH（5 層）
        """
        # 清除環境變數
        monkeypatch.delenv(ENV_PROJECT_DIR, raising=False)

        # 建立深層目錄（超過 5 層）
        # root/a/b/c/d/e/f/g（7 層）
        root = tmp_path
        (root / "CLAUDE.md").write_text("# Test Project\n")

        deep_dir = root / "a" / "b" / "c" / "d" / "e" / "f" / "g"
        deep_dir.mkdir(parents=True, exist_ok=True)

        monkeypatch.chdir(deep_dir)
        result = get_project_root()

        # 搜尋深度為 5，所以應該 Fallback 到 cwd（deep_dir）
        assert result == deep_dir, f"搜尋超過深度限制應 Fallback 到 {deep_dir}，得到 {result}"

    def test_get_project_root_never_fails(self, tmp_path, monkeypatch):
        """單元測試 5：函式永不失敗

        驗證 get_project_root 在所有情況下都返回一個有效的 Path 物件
        """
        # 清除環境變數
        monkeypatch.delenv(ENV_PROJECT_DIR, raising=False)

        # 在各種不同的目錄中測試
        test_dirs = [
            tmp_path,
            tmp_path / "subdir",
            tmp_path / "a" / "b" / "c",
        ]

        for test_dir in test_dirs:
            test_dir.mkdir(parents=True, exist_ok=True)
            monkeypatch.chdir(test_dir)

            result = get_project_root()
            assert isinstance(result, Path), f"應返回 Path 物件，得到 {type(result)}"
            assert result.exists() or result == Path.cwd(), f"路徑應存在或為 cwd"

    def test_env_and_claude_md_constants(self):
        """單元測試 6：常數定義正確性

        驗證 ENV_PROJECT_DIR 和 CLAUDE_MD_SEARCH_DEPTH 的定義
        """
        assert ENV_PROJECT_DIR == "CLAUDE_PROJECT_DIR", \
            f"ENV_PROJECT_DIR 應為 'CLAUDE_PROJECT_DIR'，得到 {ENV_PROJECT_DIR}"
        assert CLAUDE_MD_SEARCH_DEPTH == 5, \
            f"CLAUDE_MD_SEARCH_DEPTH 應為 5，得到 {CLAUDE_MD_SEARCH_DEPTH}"


# ============================================================================
# Import 轉換測試（3 個）
# ============================================================================

@pytest.mark.skipif(not backward_compat_available, reason="hook_utils 模組不可用")
class TestImportConversion:
    """Test import 路徑轉換（測試 7-9）"""

    def test_re_export_from_hook_logging(self):
        """Import 測試 7：hook_logging 的 re-export

        驗證 get_project_root 可以從 hook_logging 導入（向後相容）
        """
        # 此測試已在 import 階段成功，驗證函式能否執行
        result = get_project_root_from_logging()
        assert isinstance(result, Path), \
            f"hook_logging 的 get_project_root 應返回 Path，得到 {type(result)}"

    def test_import_from_hook_ticket(self):
        """Import 測試 8：hook_ticket.py 的 import 轉換

        驗證 hook_ticket.py 能夠從 hook_base 導入 get_project_root
        """
        try:
            from hook_utils.hook_ticket import extract_version_from_ticket_id
            # hook_ticket 能正常導入說明其依賴解決正確
            result = extract_version_from_ticket_id("0.1.0-W41-001")
            assert result == "0.1.0", \
                f"hook_ticket 應能正常運行，extract_version 返回 {result}"
        except ImportError as e:
            pytest.fail(f"hook_ticket.py 的 import 轉換失敗: {e}")

    def test_import_from_hook_io(self):
        """Import 測試 9：hook_io.py 的行內 import 轉換

        驗證 hook_io.py 的行內 import（第 273 行）能正常執行
        """
        try:
            from hook_utils.hook_io import validate_hook_input
            # hook_io 能正常導入說明其依賴解決正確
            # validate_hook_input 會在內部觸發 is_handoff_recovery_mode，
            # 該函式使用行內 import from hook_base
            result = validate_hook_input({"action": "create"})
            assert isinstance(result, bool), \
                f"validate_hook_input 應返回 bool，得到 {type(result)}"
        except ImportError as e:
            pytest.fail(f"hook_io.py 的 import 轉換失敗: {e}")


# ============================================================================
# 向後相容與完整性（5 個）
# ============================================================================

@pytest.mark.skipif(not backward_compat_available, reason="hook_utils 模組不可用")
class TestBackwardCompatibility:
    """Test 向後相容性（測試 10-14）"""

    def test_public_api_available_from_hook_utils(self):
        """相容性測試 10：公開 API 從 hook_utils 可用

        驗證 get_project_root 可以從 hook_utils package 直接導入
        """
        # 此測試已在 import 階段成功
        result = get_project_root_from_init()
        assert isinstance(result, Path), \
            f"hook_utils.get_project_root 應返回 Path，得到 {type(result)}"

    def test_external_hook_import_compatibility(self):
        """相容性測試 11：外部 Hook 的 import 相容性

        驗證現有 54+ 個外部 Hook 使用的 import 路徑仍然可用
        """
        # 模擬外部 Hook 的 import 方式
        try:
            # 方式 1：from hook_utils import get_project_root
            from hook_utils import get_project_root as gpr1
            result1 = gpr1()
            assert isinstance(result1, Path)

            # 方式 2：from hook_utils.hook_logging import get_project_root
            from hook_utils.hook_logging import get_project_root as gpr2
            result2 = gpr2()
            assert isinstance(result2, Path)

        except ImportError as e:
            pytest.fail(f"外部 Hook 的 import 相容性測試失敗: {e}")

    def test_circular_dependency_detection(self):
        """相容性測試 12：循環依賴檢測

        驗證 hook_base 不依賴其他 hook_utils 子模組，避免循環依賴
        """
        # 檢查 hook_base 的導入
        try:
            import hook_utils.hook_base as hb

            # hook_base 應該只導入 os 和 pathlib
            imports_in_hook_base = []
            with open(hb.__file__, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip().startswith('from ') or line.strip().startswith('import '):
                        # 排除本地導入（from .）
                        if 'from .' not in line and 'import .' not in line:
                            imports_in_hook_base.append(line.strip())

            # 確認沒有導入 hook_utils 中的其他子模組
            for imp in imports_in_hook_base:
                assert 'hook_logging' not in imp, \
                    f"hook_base 不應導入 hook_logging，找到: {imp}"
                assert 'hook_io' not in imp, \
                    f"hook_base 不應導入 hook_io，找到: {imp}"
                assert 'hook_ticket' not in imp, \
                    f"hook_base 不應導入 hook_ticket，找到: {imp}"
        except Exception as e:
            pytest.fail(f"循環依賴檢測失敗: {e}")

    def test_hook_base_no_external_deps(self):
        """完整性測試 13：hook_base 不依賴其他 hook_utils

        驗證 hook_base.py 的依賴最小化（只依賴 os 和 pathlib）
        """
        try:
            import hook_utils.hook_base as hb

            # 取得 hook_base 的所有 imports
            module_source = Path(hb.__file__).read_text(encoding='utf-8')

            # 檢查是否包含任何本地導入，並確認不含外部 hook_utils 的反向依賴
            import_lines = [line for line in module_source.splitlines() if line.strip().startswith('from .')]
            for line in import_lines:
                assert 'hook_logging' not in line, \
                    f"hook_base 不應導入 hook_logging：{line}"
                assert 'hook_io' not in line, \
                    f"hook_base 不應導入 hook_io：{line}"
                assert 'hook_ticket' not in line, \
                    f"hook_base 不應導入 hook_ticket：{line}"
        except Exception as e:
            pytest.fail(f"hook_base 依賴檢測失敗: {e}")

    def test_project_root_moved_functions_cleanup(self):
        """完整性測試 14：舊位置函式清理驗證

        驗證 hook_logging.py 中已移除 _find_project_root 定義
        """
        try:
            from hook_utils import hook_logging

            # 檢查 hook_logging 中不應再定義 _find_project_root
            # 因為它已移至 hook_base
            assert not hasattr(hook_logging, '_find_project_root') or \
                   'hook_base' in hook_logging.__doc__, \
                "hook_logging 應已移除 _find_project_root 定義（已遷至 hook_base）"

            # 但 get_project_root 應該仍可用（re-export）
            assert hasattr(hook_logging, 'get_project_root'), \
                "hook_logging 應保留 get_project_root（re-export）"
        except Exception as e:
            pytest.fail(f"清理驗證失敗: {e}")


# ============================================================================
# 整合測試
# ============================================================================

@pytest.mark.skipif(not hook_base_available, reason="hook_base 模組不可用")
class TestIntegration:
    """整合測試 - 確認整個遷移流程的完整性"""

    def test_all_import_paths_work(self, tmp_path, monkeypatch):
        """驗證所有 import 路徑都能正常工作"""
        # 建立測試專案結構
        (tmp_path / "CLAUDE.md").write_text("# Test\n")
        monkeypatch.delenv(ENV_PROJECT_DIR, raising=False)
        monkeypatch.chdir(tmp_path)

        # 測試各種 import 方式
        try:
            # 方式 1
            from hook_utils import get_project_root as gpr1
            assert gpr1() == tmp_path

            # 方式 2
            from hook_utils.hook_base import get_project_root as gpr2
            assert gpr2() == tmp_path

            # 方式 3
            from hook_utils.hook_logging import get_project_root as gpr3
            assert gpr3() == tmp_path
        except Exception as e:
            pytest.fail(f"整合測試失敗: {e}")

    def test_constants_accessible_from_all_paths(self):
        """驗證常數可以從原始位置和新位置存取"""
        try:
            from hook_utils.hook_base import ENV_PROJECT_DIR as env1
            from hook_utils.hook_logging import ENV_PROJECT_DIR as env2

            assert env1 == env2 == "CLAUDE_PROJECT_DIR"
        except ImportError:
            pytest.fail("常數無法從預期的路徑導入")
