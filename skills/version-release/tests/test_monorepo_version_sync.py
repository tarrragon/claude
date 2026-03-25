"""
版本發布工具的 Monorepo 三層版本同步測試 - Phase 3b
完整的單元和整合測試覆蓋 39 個測試案例（含實際斷言）
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import sys
import yaml
import os

# 設置 import path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from version_release import (
    load_version_release_config,
    get_monorepo_version,
    check_monorepo_version_sync,
    print_version_sync_report,
    compare_semantic_versions,
    DEFAULT_VERSION_RELEASE_CONFIG,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    SEVERITY_INFO,
    SEVERITY_SUCCESS,
)

# 測試結構設置
TEST_VERSION = "0.1.1"
TEST_L2_VERSION = "1.0.0+1"
TEST_L2_GREATER = "2.0.0"
TEST_L2_LESS = "0.1.0"


# ============================================================================
# Shared Fixtures
# ============================================================================

@pytest.fixture
def monorepo_env(tmp_path):
    """
    建立共享的 monorepo 測試環境。

    設置：
    - docs/todolist.yaml（L1）：current_version = TEST_VERSION
    - 回傳 tmp_path，讓測試根據需要設置 L2（ui/pubspec.yaml）

    用法：
        def test_xxx(monorepo_env):
            tmp_path = monorepo_env
            # 可選：自訂 L2
            ui_dir = tmp_path / "ui"
            ui_dir.mkdir()
            pubspec = ui_dir / "pubspec.yaml"
            pubspec.write_text(f"version: {TEST_L2_VERSION}")
    """
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    todolist_file = docs_dir / "todolist.yaml"
    todolist_file.write_text(f"current_version: {TEST_VERSION}")
    return tmp_path


class TestLoadVersionReleaseConfig:
    """測試 load_version_release_config 函式 (5 個案例)"""

    def test_1_1_config_exists_and_valid(self, tmp_path):
        """場景 1.1：配置檔存在且格式正確"""
        config_file = tmp_path / ".version-release.yaml"
        config_file.write_text("""
versions:
  monorepo:
    source: docs/todolist.yaml
    key: current_version
""")
        config = load_version_release_config(tmp_path)
        assert config is not None
        assert isinstance(config, dict)
        assert "versions" in config
        assert config["versions"]["monorepo"]["source"] == "docs/todolist.yaml"

    def test_1_2_config_not_exists(self, tmp_path):
        """場景 1.2：配置檔不存在"""
        config = load_version_release_config(tmp_path)
        assert config == DEFAULT_VERSION_RELEASE_CONFIG
        assert config is not None

    def test_1_3_config_yaml_error(self, tmp_path):
        """場景 1.3：配置檔 YAML 格式錯誤"""
        config_file = tmp_path / ".version-release.yaml"
        # 使用真正的 YAML 格式錯誤
        config_file.write_text("invalid: {yaml: structure: extra_colon")
        config = load_version_release_config(tmp_path)
        # 應捕獲 yaml.YAMLError 異常，回傳 DEFAULT_VERSION_RELEASE_CONFIG
        assert config == DEFAULT_VERSION_RELEASE_CONFIG

    def test_1_4_config_partial_missing_fields(self, tmp_path):
        """場景 1.4：配置檔部分欄位缺漏"""
        config_file = tmp_path / ".version-release.yaml"
        config_file.write_text("versions: {}")
        config = load_version_release_config(tmp_path)
        # 應回傳完整字典，缺漏欄位使用預設
        assert "sync_rules" in config
        assert "detection" in config

    def test_1_5_config_extra_fields(self, tmp_path):
        """場景 1.5：配置檔包含未知欄位"""
        config_file = tmp_path / ".version-release.yaml"
        config_file.write_text("""
versions:
  monorepo:
    source: docs/todolist.yaml
custom_field: value
""")
        config = load_version_release_config(tmp_path)
        # 應回傳字典包含額外欄位（保留），不拋出異常
        assert isinstance(config, dict)
        assert config is not None


class TestGetMonorepoVersion:
    """測試 get_monorepo_version 函式 (5 個案例)"""

    def test_2_1_todolist_exists_with_version(self, monorepo_env):
        """場景 2.1：todolist.yaml 存在，current_version 欄位有效"""
        version = get_monorepo_version(monorepo_env)
        assert version == TEST_VERSION
        assert isinstance(version, str)

    def test_2_2_todolist_not_exists(self, tmp_path):
        """場景 2.2：todolist.yaml 不存在"""
        version = get_monorepo_version(tmp_path)
        assert version is None

    def test_2_3_todolist_missing_current_version(self, tmp_path):
        """場景 2.3：todolist.yaml 存在，但 current_version 欄位不存在"""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        todolist_file = docs_dir / "todolist.yaml"
        todolist_file.write_text("other_field: value")
        version = get_monorepo_version(tmp_path)
        assert version is None

    def test_2_4_current_version_non_string(self, monorepo_env):
        """場景 2.4：current_version 為非字串型別"""
        # 覆蓋 fixture 的預設值
        docs_dir = monorepo_env / "docs"
        todolist_file = docs_dir / "todolist.yaml"
        todolist_file.write_text("current_version: 0.1")  # 浮點數
        version = get_monorepo_version(monorepo_env)
        assert version == "0.1"

    def test_2_5_current_version_variant_format(self, monorepo_env):
        """場景 2.5：current_version 為版本風格變體"""
        # 覆蓋 fixture 的預設值
        docs_dir = monorepo_env / "docs"
        todolist_file = docs_dir / "todolist.yaml"
        todolist_file.write_text("current_version: v0.1.1")
        version = get_monorepo_version(monorepo_env)
        assert version == "v0.1.1"


class TestCheckMonorepoVersionSync:
    """測試 check_monorepo_version_sync 函式 (6 個案例)"""

    def test_3_1_l1_l2_mismatch_expected(self, monorepo_env):
        """場景 3.1：L1=0.1.1，L2=1.0.0+1（預期不匹配）"""
        # 設置 L2 版本
        ui_dir = monorepo_env / "ui"
        ui_dir.mkdir()
        pubspec_file = ui_dir / "pubspec.yaml"
        pubspec_file.write_text(f"version: {TEST_L2_VERSION}")

        with patch("version_release.get_project_root", return_value=monorepo_env):
            result = check_monorepo_version_sync(TEST_VERSION, DEFAULT_VERSION_RELEASE_CONFIG)
            assert result["passed"] is True
            assert result["l1_version"] == TEST_VERSION
            assert result["l2_version"] == TEST_L2_VERSION
            assert result["l3_has_version"] is False

    def test_3_2_l2_greater_than_l1(self, monorepo_env):
        """場景 3.2：L2 版本大於 L1（警告）"""
        ui_dir = monorepo_env / "ui"
        ui_dir.mkdir()
        pubspec_file = ui_dir / "pubspec.yaml"
        pubspec_file.write_text(f"version: {TEST_L2_GREATER}")

        with patch("version_release.get_project_root", return_value=monorepo_env):
            result = check_monorepo_version_sync(TEST_VERSION, DEFAULT_VERSION_RELEASE_CONFIG)
            assert result["passed"] is True
            assert any(m["level"] == SEVERITY_WARNING for m in result["messages"])

    def test_3_3_l2_less_than_l1(self, tmp_path):
        """場景 3.3：L2 版本小於 L1（資訊）"""
        # 覆蓋 fixture 的預設值（L1=0.2.0，非 TEST_VERSION）
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        todolist_file = docs_dir / "todolist.yaml"
        todolist_file.write_text("current_version: 0.2.0")

        ui_dir = tmp_path / "ui"
        ui_dir.mkdir()
        pubspec_file = ui_dir / "pubspec.yaml"
        pubspec_file.write_text(f"version: {TEST_L2_LESS}")

        with patch("version_release.get_project_root", return_value=tmp_path):
            result = check_monorepo_version_sync("0.2.0", DEFAULT_VERSION_RELEASE_CONFIG)
            assert result["passed"] is True
            assert any(m["level"] == SEVERITY_INFO for m in result["messages"])

    def test_3_4_l2_equal_to_l1(self, monorepo_env):
        """場景 3.4：L2 版本等於 L1（一致）"""
        ui_dir = monorepo_env / "ui"
        ui_dir.mkdir()
        pubspec_file = ui_dir / "pubspec.yaml"
        pubspec_file.write_text(f"version: {TEST_VERSION}")

        with patch("version_release.get_project_root", return_value=monorepo_env):
            result = check_monorepo_version_sync(TEST_VERSION, DEFAULT_VERSION_RELEASE_CONFIG)
            assert result["passed"] is True
            assert result["l2_version"] == TEST_VERSION

    def test_3_5_l2_not_exists(self, monorepo_env):
        """場景 3.5：ui/pubspec.yaml 不存在"""
        with patch("version_release.get_project_root", return_value=monorepo_env):
            result = check_monorepo_version_sync(TEST_VERSION, DEFAULT_VERSION_RELEASE_CONFIG)
            assert result["l2_version"] is None
            assert result["passed"] is True
            assert any("不存在" in m["text"] for m in result["messages"])

    def test_3_6_version_with_build_number(self, monorepo_env):
        """場景 3.6：版本字串含 build number 的比對"""
        ui_dir = monorepo_env / "ui"
        ui_dir.mkdir()
        pubspec_file = ui_dir / "pubspec.yaml"
        pubspec_file.write_text(f"version: {TEST_L2_GREATER}+2")

        with patch("version_release.get_project_root", return_value=monorepo_env):
            result = check_monorepo_version_sync(TEST_VERSION, DEFAULT_VERSION_RELEASE_CONFIG)
            assert result["l2_version"] == f"{TEST_L2_GREATER}+2"
            assert any(m["level"] == SEVERITY_WARNING for m in result["messages"])


class TestPrintVersionSyncReport:
    """測試 print_version_sync_report 函式 (4 個案例)"""

    def test_4_1_normal_output_three_layers(self, capsys):
        """場景 4.1：正常輸出三層版本對比"""
        sync_result = {
            "passed": True,
            "l1_version": TEST_VERSION,
            "l2_version": TEST_L2_VERSION,
            "l3_has_version": False,
            "messages": [{"level": SEVERITY_INFO, "text": "UI 應用版本獨立於 monorepo 版本"}],
            "summary": "通過（版本策略符合 monorepo 三層架構）"
        }
        print_version_sync_report(sync_result)
        captured = capsys.readouterr()
        assert "版本同步檢查" in captured.out
        assert TEST_VERSION in captured.out
        assert TEST_L2_VERSION in captured.out

    def test_4_2_output_without_l2_version(self, capsys):
        """場景 4.2：無 L2 版本的輸出"""
        sync_result = {
            "passed": True,
            "l1_version": TEST_VERSION,
            "l2_version": None,
            "l3_has_version": False,
            "messages": [],
            "summary": "通過"
        }
        print_version_sync_report(sync_result)
        captured = capsys.readouterr()
        assert "未偵測到" in captured.out

    def test_4_3_output_with_warning(self, capsys):
        """場景 4.3：包含警告訊息的輸出"""
        sync_result = {
            "passed": True,
            "l1_version": TEST_VERSION,
            "l2_version": TEST_L2_GREATER,
            "l3_has_version": False,
            "messages": [{"level": SEVERITY_WARNING, "text": "UI 版本大於 monorepo，確認是否故意？"}],
            "summary": "通過（附警告）"
        }
        print_version_sync_report(sync_result)
        captured = capsys.readouterr()
        assert "[WARNING]" in captured.out or "警告" in captured.out

    def test_4_4_output_empty_messages(self, capsys):
        """場景 4.4：空的訊息清單"""
        sync_result = {
            "passed": True,
            "l1_version": TEST_VERSION,
            "l2_version": TEST_L2_VERSION,
            "l3_has_version": False,
            "messages": [],
            "summary": "通過"
        }
        print_version_sync_report(sync_result)
        captured = capsys.readouterr()
        assert TEST_VERSION in captured.out


class TestIntegration:
    """整合測試 (4 個案例)"""

    def test_5_1_standard_check_flow(self, monorepo_env):
        """場景 5.1：標準 check 流程 - 正常三層版本對比"""
        ui_dir = monorepo_env / "ui"
        ui_dir.mkdir()
        pubspec_file = ui_dir / "pubspec.yaml"
        pubspec_file.write_text(f"version: {TEST_L2_VERSION}")

        with patch("version_release.get_project_root", return_value=monorepo_env):
            result = check_monorepo_version_sync(TEST_VERSION, DEFAULT_VERSION_RELEASE_CONFIG)
            assert result["passed"] is True
            assert "通過" in result["summary"]

    def test_5_2_check_without_config_file(self, monorepo_env):
        """場景 5.2：.version-release.yaml 不存在時的 check"""
        ui_dir = monorepo_env / "ui"
        ui_dir.mkdir()
        pubspec_file = ui_dir / "pubspec.yaml"
        pubspec_file.write_text(f"version: {TEST_L2_VERSION}")

        config = load_version_release_config(monorepo_env)
        with patch("version_release.get_project_root", return_value=monorepo_env):
            result = check_monorepo_version_sync(TEST_VERSION, config)
            assert result["passed"] is True

    def test_5_3_check_missing_todolist(self, tmp_path):
        """場景 5.3：check 時 L1 todolist.yaml 不存在"""
        with patch("version_release.get_project_root", return_value=tmp_path):
            result = check_monorepo_version_sync(TEST_VERSION, DEFAULT_VERSION_RELEASE_CONFIG)
            # 目前程式碼允許 L1 不存在（靜默跳過）
            # 應正常執行，L2 檢查會跳過
            assert isinstance(result, dict)
            assert "passed" in result

    def test_5_4_check_l2_greater_than_l1(self, monorepo_env):
        """場景 5.4：L2 版本大於 L1 的 check"""
        ui_dir = monorepo_env / "ui"
        ui_dir.mkdir()
        pubspec_file = ui_dir / "pubspec.yaml"
        pubspec_file.write_text(f"version: {TEST_L2_GREATER}")

        with patch("version_release.get_project_root", return_value=monorepo_env):
            result = check_monorepo_version_sync(TEST_VERSION, DEFAULT_VERSION_RELEASE_CONFIG)
            assert result["passed"] is True
            assert any(m["level"] == SEVERITY_WARNING for m in result["messages"])


class TestEdgeCases:
    """邊界條件測試 (11 個案例)"""

    def test_edge_1_empty_version_string(self):
        """邊界 1：version 為空字串"""
        result = check_monorepo_version_sync("", DEFAULT_VERSION_RELEASE_CONFIG)
        assert result["passed"] is False

    def test_edge_2_permission_denied(self, tmp_path):
        """邊界 2：檔案權限不足"""
        config_file = tmp_path / ".version-release.yaml"
        config_file.write_text("versions: {}")
        # 設定檔案為不可讀
        config_file.chmod(0o000)
        try:
            config = load_version_release_config(tmp_path)
            # 應使用 fallback
            assert config == DEFAULT_VERSION_RELEASE_CONFIG
        finally:
            config_file.chmod(0o644)

    def test_edge_3_path_is_directory(self, tmp_path):
        """邊界 3：路徑為目錄而非檔案"""
        # 正常情況下應處理目錄
        config = load_version_release_config(tmp_path)
        assert isinstance(config, dict)

    def test_edge_4_empty_yaml_file(self, tmp_path):
        """邊界 4：空的 YAML 檔案"""
        config_file = tmp_path / ".version-release.yaml"
        config_file.write_text("")
        config = load_version_release_config(tmp_path)
        assert config == DEFAULT_VERSION_RELEASE_CONFIG

    def test_edge_5_config_yaml_none(self, tmp_path):
        """邊界 5：YAML 解析結果為 None"""
        config_file = tmp_path / ".version-release.yaml"
        config_file.write_text("null")
        config = load_version_release_config(tmp_path)
        assert config == DEFAULT_VERSION_RELEASE_CONFIG

    def test_edge_6_todolist_empty_file(self, monorepo_env):
        """邊界 6：todolist.yaml 為空檔案"""
        # 覆蓋 fixture 的預設值
        docs_dir = monorepo_env / "docs"
        todolist_file = docs_dir / "todolist.yaml"
        todolist_file.write_text("")
        version = get_monorepo_version(monorepo_env)
        assert version is None

    def test_edge_7_current_version_empty_string(self, monorepo_env):
        """邊界 7：current_version 欄位值為空字串"""
        # 覆蓋 fixture 的預設值
        docs_dir = monorepo_env / "docs"
        todolist_file = docs_dir / "todolist.yaml"
        todolist_file.write_text('current_version: ""')
        version = get_monorepo_version(monorepo_env)
        assert version == ""

    def test_edge_8_version_all_zeros(self):
        """邊界 8：版本全為 0（0.0.0）"""
        result = compare_semantic_versions("0.0.0", "0.0.0")
        assert result == 0

    def test_edge_9_version_large_numbers(self):
        """邊界 9：版本數字很大（999.999.999）"""
        result = compare_semantic_versions("999.999.999", "999.999.999")
        assert result == 0
        result = compare_semantic_versions("1000.0.0", "999.999.999")
        assert result == 1

    def test_edge_10_version_with_prefix_v(self, monorepo_env):
        """邊界 10：版本含 v 前綴（v0.1.1）"""
        # 覆蓋 fixture 的預設值
        docs_dir = monorepo_env / "docs"
        todolist_file = docs_dir / "todolist.yaml"
        todolist_file.write_text("current_version: v0.1.1")
        version = get_monorepo_version(monorepo_env)
        assert version == "v0.1.1"

    def test_edge_11_version_malformed(self):
        """邊界 11：版本格式畸形（abc.def.ghi）"""
        # 應使用字符串比較作為 fallback
        result = compare_semantic_versions("abc.def.ghi", "1.0.0")
        assert result == 1  # abc > 1 in lexical order


class TestVersionComparison:
    """版本比較測試（支援函式）"""

    def test_semantic_version_greater(self):
        """語義版本比較：v1 > v2"""
        result = compare_semantic_versions("2.0.0", "1.9.9")
        assert result == 1

    def test_semantic_version_less(self):
        """語義版本比較：v1 < v2"""
        result = compare_semantic_versions("1.0.0", "2.0.0")
        assert result == -1

    def test_semantic_version_equal(self):
        """語義版本比較：v1 = v2"""
        result = compare_semantic_versions("1.0.0", "1.0.0")
        assert result == 0

    def test_semantic_version_short_format(self):
        """語義版本比較：短格式（0.1 vs 0.1.0）"""
        result = compare_semantic_versions("0.1", "0.1.0")
        assert result == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
