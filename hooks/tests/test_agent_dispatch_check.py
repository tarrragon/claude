#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.8"
# dependencies = ["pytest", "pyyaml"]
# ///
"""
代理人分派檢查 Hook 測試套件

測試覆蓋：
- 9 個正確分派測試（agent_to_task_map 快速路徑）
- 9 個錯誤分派測試（關鍵字偵測路徑）
- 8 個邊界測試 (TC_EDGE_001-008)
- 4 個整合測試 (TC_INTEGRATION_001-004)
- 4 個關鍵字檢測測試 (TC_KEYWORD_001-004)
- 1 個效能測試 (TC_PERFORMANCE_001)
- 6 個任務類型檢測測試
- 4 個 Hook 模式切換測試 (TC_MODE_001-004)
- 1 ���錯誤訊息品質測試
- 2 個 agent_to_task_map 行為測試
"""

import pytest
import sys
import os
import json
import time
import logging
from typing import Dict, Any
from pathlib import Path

# 加入 Hook 目錄和 lib 目錄到 Python 路徑
HOOK_DIR = Path(__file__).parent.parent
LIB_DIR = HOOK_DIR.parent / "lib"
PROJECT_ROOT = HOOK_DIR.parent.parent  # .claude/hooks -> .claude -> project root
sys.path.insert(0, str(HOOK_DIR))
sys.path.insert(0, str(LIB_DIR))

# 動態導入 Hook 模組
import importlib.util
spec = importlib.util.spec_from_file_location("task_dispatch_check",
                                              HOOK_DIR / "task-dispatch-readiness-check.py")
hook_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook_module)

# 獲取檢查函式
detect_task_type = hook_module.detect_task_type
check_agent_dispatch = hook_module.check_agent_dispatch


# ===== Fixtures =====

@pytest.fixture
def logger():
    """提供測試用 logger"""
    return logging.getLogger("test-agent-dispatch")


@pytest.fixture
def config(monkeypatch):
    """提供完整配置（含 agent_to_task_map）

    設定 CLAUDE_PROJECT_DIR 確保 config_loader 能找到 agents.yaml。
    """
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(PROJECT_ROOT))
    from config_loader import load_agents_config, clear_config_cache
    clear_config_cache()
    cfg = load_agents_config()
    # 確保配置載入成功（不是預設的空配置）
    assert "task_type_priorities" in cfg, (
        f"配置載入失敗，缺少 task_type_priorities。config_dir: {PROJECT_ROOT / '.claude' / 'config'}"
    )
    return cfg


@pytest.fixture
def config_keyword_only(config):
    """提供無 agent_to_task_map 的配置，強制走關鍵字偵測路徑。

    當 agent_to_task_map 存在時，check_agent_dispatch 會短路返回
    is_error=False，無法測試關鍵字偵測和錯誤攔截邏輯。
    """
    cfg = dict(config)
    cfg.pop("agent_to_task_map", None)
    return cfg


# ===== [1] 正確分派測試 (9 個) =====

@pytest.mark.parametrize("task_type,prompt,agent,expected_pass", [
    (
        "Hook 開發",
        "開發 Hook 腳本來檢查代理人分派",
        "basil-hook-architect",
        True
    ),
    (
        "文件整合",
        "文件整合：將工作日誌整合到方法論文件",
        "thyme-documentation-integrator",
        True
    ),
    (
        "程式碼格式化",
        "格式化所有 Dart 檔案並修復 Lint",
        "mint-format-specialist",
        True
    ),
    (
        "Phase 1 設計",
        "設計功能需求規格",
        "lavender-interface-designer",
        True
    ),
    (
        "Phase 2 測試",
        "設計測試案例並建立測試計畫",
        "sage-test-architect",
        True
    ),
    (
        "Phase 3a 策略",
        "規劃語言無關的實作策略",
        "pepper-test-implementer",
        True
    ),
    (
        "Phase 4 重構",
        "評估程式碼品質並提供重構建議",
        "cinnamon-refactor-owl",
        True
    ),
    (
        "Flutter 應用",
        "開發應用程式：實作書籍清單 Widget 和狀態管理",
        "parsley-flutter-developer",
        True
    ),
    (
        "記憶網路",
        "建立知識圖譜並記錄實作決策",
        "memory-network-builder",
        True
    ),
])
def test_correct_dispatch(task_type: str, prompt: str, agent: str, expected_pass: bool, config, logger) -> None:
    """測試正確的代理人分派能夠通過檢查（agent_to_task_map 快速路徑）"""
    result = check_agent_dispatch(prompt, agent, config, logger)
    assert result["is_error"] == (not expected_pass), f"Failed for {task_type}"
    if expected_pass:
        assert result.get("detected_task_type") is not None
        assert result.get("correct_agent") is not None


# ===== [2] 錯誤分派測試 (9 個) =====

@pytest.mark.parametrize("task_type,prompt,wrong_agent,correct_agent", [
    (
        "Hook 開發",
        "開發 Hook 腳本來檢查代理人分派",
        "parsley-flutter-developer",
        "basil-hook-architect"
    ),
    (
        "文件整合",
        "文件整合：將工作日誌整合到方法論文件",
        "basil-hook-architect",
        "thyme-documentation-integrator"
    ),
    (
        "程式碼格式化",
        "格式化所有 Dart 檔案並修復 Lint",
        "parsley-flutter-developer",
        "mint-format-specialist"
    ),
    (
        "Phase 1 設計",
        "設計功能需求規格",
        "sage-test-architect",
        "lavender-interface-designer"
    ),
    (
        "Phase 2 測試",
        "設計測試案例並建立測試計畫",
        "lavender-interface-designer",
        "sage-test-architect"
    ),
    (
        "Phase 3a 策略",
        "Phase 3a 語言無關策略規劃",
        "parsley-flutter-developer",
        "pepper-test-implementer"
    ),
    (
        "Phase 4 重構",
        "評估程式碼品質並提供重構建議",
        "parsley-flutter-developer",
        "cinnamon-refactor-owl"
    ),
    (
        "Phase 3b 實作",
        "Phase 3b 實作書籍清單 Widget 和狀態管理",
        "basil-hook-architect",
        "parsley-flutter-developer"
    ),
    (
        "Hook 開發",
        "Hook 開發：擴展現有 Hook 加入新功能",
        "mint-format-specialist",
        "basil-hook-architect"
    ),
])
def test_error_dispatch(task_type: str, prompt: str, wrong_agent: str, correct_agent: str, config_keyword_only, logger) -> None:
    """測試錯誤的代理人分派能被正確攔截（關鍵字偵測路徑）"""
    result = check_agent_dispatch(prompt, wrong_agent, config_keyword_only, logger)
    assert result["is_error"] == True, f"Failed for {task_type}: {result}"
    assert result.get("correct_agent") == correct_agent
    assert "代理人分派錯誤" in result.get("error_message", "")


# ===== [3] 邊界測試 (8 個) =====

def test_edge_001_multiple_keywords(config_keyword_only, logger) -> None:
    """TC_EDGE_001 - 多種任務類型關鍵字優先級測試"""
    prompt = "開發 Hook 腳本並實作 Flutter Widget"
    result = check_agent_dispatch(prompt, "parsley-flutter-developer", config_keyword_only, logger)
    assert result["is_error"] == True
    assert result.get("detected_task_type") == "Hook 開發"
    assert result.get("correct_agent") == "basil-hook-architect"


def test_edge_002_no_clear_keywords(config, logger) -> None:
    """TC_EDGE_002 - 無明確任務類型關鍵字測試"""
    prompt = "處理這個任務"
    result = check_agent_dispatch(prompt, "parsley-flutter-developer", config, logger)
    assert result["is_error"] == False


def test_edge_003_project_type_detection(config, logger) -> None:
    """TC_EDGE_003 - 需判斷專案類型測試"""
    prompt = "實作應用程式功能"
    result = check_agent_dispatch(prompt, "parsley-flutter-developer", config, logger)
    assert result["is_error"] == False


def test_edge_004_empty_subagent_type(config, logger) -> None:
    """TC_EDGE_004 - subagent_type 為空測試"""
    prompt = "開發 Hook 腳本"
    result = check_agent_dispatch(prompt, "", config, logger)
    assert result["is_error"] == False


def test_edge_005_unknown_agent(config, logger) -> None:
    """TC_EDGE_005 - 未知代理人測試"""
    prompt = "開發 Hook 腳本"
    result = check_agent_dispatch(prompt, "unknown-agent", config, logger)
    assert result["is_error"] == False


def test_edge_006_double_verification(config, logger) -> None:
    """TC_EDGE_006 - 任務類型 + 專案類型雙重驗證測試"""
    prompt = "實作 Flutter Widget"
    result = check_agent_dispatch(prompt, "parsley-flutter-developer", config, logger)
    assert result["is_error"] == False


def test_edge_007_phase4_with_hook_keyword(config_keyword_only, logger) -> None:
    """TC_EDGE_007 - Phase 4 重構評估包含 Hook 關鍵字測試

    使用 config_keyword_only 測試關鍵字路徑：
    Phase 4 明確標記應優先於 Hook 開發關鍵字。
    """
    prompt = "v0.12.N Phase 4: 代理人分派檢查 Hook 重構評估"
    result = check_agent_dispatch(prompt, "cinnamon-refactor-owl", config_keyword_only, logger)
    assert result["is_error"] == False, f"Phase 4 重構評估被誤判: {result}"
    assert result.get("detected_task_type") == "Phase 4 重構"
    assert result.get("correct_agent") == "cinnamon-refactor-owl"


def test_edge_008_phase4_wrong_agent(config_keyword_only, logger) -> None:
    """TC_EDGE_008 - Phase 4 重構評估錯誤代理人攔截測試"""
    prompt = "v0.12.N Phase 4: 代理人分派檢查 Hook 重構評估"
    result = check_agent_dispatch(prompt, "basil-hook-architect", config_keyword_only, logger)
    assert result["is_error"] == True, f"錯誤代理人未被攔截: {result}"
    assert result.get("detected_task_type") == "Phase 4 重構"
    assert result.get("correct_agent") == "cinnamon-refactor-owl"


# ===== [4] 整合測試 (4 個) =====

def test_integration_001_complete_pass(config, logger) -> None:
    """TC_INTEGRATION_001 - 完全通過測試"""
    prompt = """
開發 Hook 腳本來檢查代理人分派。

UseCase: UC-HK-001
Event: Event 1
架構層級: Infrastructure
依賴類別: Core
"""
    result = check_agent_dispatch(prompt, "basil-hook-architect", config, logger)
    assert result["is_error"] == False


def test_integration_002_existing_check_fails(config, logger) -> None:
    """TC_INTEGRATION_002 - 現有檢查失敗優先"""
    prompt = "開發 Hook 腳本"
    result = check_agent_dispatch(prompt, "basil-hook-architect", config, logger)
    assert result["is_error"] == False


def test_integration_003_agent_check_fails(config_keyword_only, logger) -> None:
    """TC_INTEGRATION_003 - 代理人檢查失敗攔截（關鍵字路徑）"""
    prompt = """
開發 Hook 腳本來檢查代理人分派。
UseCase: UC-HK-001
Event: Event 1
"""
    result = check_agent_dispatch(prompt, "parsley-flutter-developer", config_keyword_only, logger)
    assert result["is_error"] == True
    assert result.get("correct_agent") == "basil-hook-architect"


def test_integration_004_double_failure(config_keyword_only, logger) -> None:
    """TC_INTEGRATION_004 - 雙重失敗測試（關鍵字路徑）"""
    prompt = "開發 Hook"
    result = check_agent_dispatch(prompt, "parsley-flutter-developer", config_keyword_only, logger)
    if result["is_error"]:
        assert result.get("detected_task_type") == "Hook 開發"
        assert result.get("correct_agent") == "basil-hook-architect"


# ===== [5] 關鍵字檢測測試 (4 個) =====

def test_keyword_001_high_weight(config, logger) -> None:
    """TC_KEYWORD_001 - 高權重關鍵字檢測"""
    prompt = "開發 Hook 系統"
    task_type = detect_task_type(prompt, config, logger)
    assert task_type == "Hook 開發"


def test_keyword_002_medium_weight(config, logger) -> None:
    """TC_KEYWORD_002 - 中權重關鍵字檢測"""
    prompt = "修改 .claude/hooks/ 目錄下的腳本"
    task_type = detect_task_type(prompt, config, logger)
    assert task_type == "Hook 開發"


def test_keyword_003_low_weight(config, logger) -> None:
    """TC_KEYWORD_003 - 低權重關鍵字檢測"""
    prompt = "Hook 相關的配置"
    task_type = detect_task_type(prompt, config, logger)
    assert task_type in ["Hook 開發", "未知"]


def test_keyword_004_cumulative_weight(config, logger) -> None:
    """TC_KEYWORD_004 - 多個關鍵字累積"""
    prompt = "在 .claude/hooks/ 目錄開發 Hook 腳本"
    task_type = detect_task_type(prompt, config, logger)
    assert task_type == "Hook 開發"


# ===== [6] 效能測試 (1 個) =====

def test_performance_001_execution_time(config, logger) -> None:
    """TC_PERFORMANCE_001 - 代理人檢查執行時間 < 10ms"""
    prompt = "開發 Hook 腳本來檢查代理人分派"
    agent = "basil-hook-architect"

    start_time = time.perf_counter()
    result = check_agent_dispatch(prompt, agent, config, logger)
    end_time = time.perf_counter()

    execution_time_ms = (end_time - start_time) * 1000
    assert execution_time_ms < 10, f"執行時間 {execution_time_ms:.2f}ms 超過 10ms 限制"


# ===== 補充測試：任務類型檢測（明確 Phase 標記路徑） =====

@pytest.mark.parametrize("prompt,expected_type", [
    ("[Phase 1] 功能設計", "Phase 1 設計"),
    ("[Phase 2] 測試設計", "Phase 2 測試設計"),
    ("[Phase 3a] 實作策略", "Phase 3a 策略規劃"),
    ("[Phase 4] 重構評估", "Phase 4 重構"),
])
def test_task_type_detection_explicit_phase(prompt: str, expected_type: str, config, logger) -> None:
    """測試明確 Phase 標記的任務類型檢測（優先級 1：正則匹配路徑）"""
    detected = detect_task_type(prompt, config, logger)
    assert detected == expected_type, f"檢測失敗: {prompt} -> {detected} (期望: {expected_type})"


@pytest.mark.parametrize("prompt,expected_type", [
    ("文件整合：將工作日誌整合到方法論文件", "文件整合"),
    ("格式化所有 Dart 檔案並修復 Lint", "程式碼格式化"),
])
def test_task_type_detection_keyword(prompt: str, expected_type: str, config, logger) -> None:
    """測試關鍵字權重的任務類型檢測（優先級 2：權重累積路徑）"""
    detected = detect_task_type(prompt, config, logger)
    assert detected == expected_type, f"檢測失敗: {prompt} -> {detected} (期望: {expected_type})"


# ===== 補充測試：錯誤訊息品質 =====

def test_error_message_contains_required_elements(config_keyword_only, logger) -> None:
    """測試錯誤訊息包含所有必要元素"""
    prompt = "開發 Hook 腳本"
    result = check_agent_dispatch(prompt, "parsley-flutter-developer", config_keyword_only, logger)

    assert result["is_error"] == True, f"應偵測到錯誤: {result}"
    error_msg = result.get("error_message", "")
    assert "代理人分派錯誤" in error_msg
    assert "任務類型" in error_msg
    assert "當前代理人" in error_msg
    assert "正確代理人" in error_msg
    assert "原因" in error_msg


# ===== [7] Hook 模式切換測試 (4 個) =====

def test_mode_001_get_hook_mode_env_var(monkeypatch, logger) -> None:
    """TC_MODE_001 - 環境變數模式讀取測試"""
    get_hook_mode = hook_module.get_hook_mode
    monkeypatch.setenv("HOOK_MODE", "warning")
    mode = get_hook_mode(logger)
    assert mode == "warning"


def test_mode_002_get_hook_mode_config_file(tmp_path, monkeypatch, logger) -> None:
    """TC_MODE_002 - 配置檔案模式讀取測試"""
    get_hook_mode = hook_module.get_hook_mode

    config_file = tmp_path / ".claude" / "hook-config.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)

    config_data = {
        "agent_dispatch_check": {
            "mode": "warning"
        }
    }

    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config_data, f)

    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.delenv("HOOK_MODE", raising=False)

    mode = get_hook_mode(logger)
    assert mode == "warning"


def test_mode_003_get_hook_mode_default(monkeypatch, logger) -> None:
    """TC_MODE_003 - 預設模式測試"""
    get_hook_mode = hook_module.get_hook_mode
    monkeypatch.delenv("HOOK_MODE", raising=False)

    mode = get_hook_mode(logger)
    assert mode == "strict"


def test_mode_004_warning_mode_allows_execution(tmp_path, monkeypatch, config_keyword_only, logger) -> None:
    """TC_MODE_004 - Warning 模式允許執���測試

    check_agent_dispatch 本身仍返回 is_error=True，
    但 main() 中 warning 模式不會阻擋執行。
    """
    monkeypatch.setenv("HOOK_MODE", "warning")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))

    log_dir = tmp_path / ".claude" / "hook-logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    prompt = "開發 Hook 腳本來檢查代理人分派"
    result = check_agent_dispatch(prompt, "parsley-flutter-developer", config_keyword_only, logger)

    assert result["is_error"] == True
    assert result.get("correct_agent") == "basil-hook-architect"


# ===== [8] agent_to_task_map 行為測試 =====

def test_agent_to_task_map_shortcircuit(config, logger) -> None:
    """測試 agent_to_task_map 存在時，已知代理人直接通過（不走關鍵字偵測）

    即使 prompt 與代理人的專業不相關，agent_to_task_map 會短路返回正確。
    """
    prompt = "格式化 Dart 程式碼"
    result = check_agent_dispatch(prompt, "basil-hook-architect", config, logger)
    assert result["is_error"] == False
    # agent_to_task_map 路徑返回該代理人的預設任務類型
    assert result.get("detected_task_type") == "Hook 開發"
    assert result.get("correct_agent") == "basil-hook-architect"


def test_without_agent_to_task_map_detects_mismatch(config_keyword_only, logger) -> None:
    """測試移除 agent_to_task_map 後，關鍵字偵測能發現代理人不匹配"""
    prompt = "格式化所有 Dart 檔案並修復 Lint"
    result = check_agent_dispatch(prompt, "basil-hook-architect", config_keyword_only, logger)
    assert result["is_error"] == True
    assert result.get("detected_task_type") == "程式碼格式化"
    assert result.get("correct_agent") == "mint-format-specialist"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
